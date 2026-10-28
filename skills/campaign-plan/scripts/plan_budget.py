#!/usr/bin/env python3
"""Budget one campaign from the programme file and per-tier assumptions, in two scenarios.

Usage:
  python3 -I scripts/plan_budget.py WORKSPACE --campaign SLUG --assumptions FILE
        [--shortlist FILE] [--window FROM TO]
        [--rail-fee-pct PCT --rail-fee-basis commission|sales]
        [--sale-pct PCT] [--conservative-factor F] [--as-of DATE]

Reads programme sections 1 (average order value, gross margin band, store currency) and 4
(commission rate, commission basis, customer discount, the flat-and-hybrid rule); with
--window also section 5 (holdback days) and section 11 (usage-rights window); with
--shortlist also section 3 (which platforms allow organic creator posts).

Computes, per assumptions row and in total, for a base case and a conservative case:
expected tracked orders, net sales, discount given, commission, fees, gift cost, rail fees,
total cost, cost per tracked order, sales per unit of cost, and contribution at the low and
high margin. With --sale-pct it adds a sale case: a store-wide percentage sale taken before
the creator's code. Every projected figure is Estimated.

Writes WORKSPACE/campaigns/SLUG/budget.csv (a changed earlier file is kept as
budget-superseded-<UTC stamp>.csv) and, when WORKSPACE/campaigns/SLUG/plan.md carries the
markers, fills its generated budget and dates blocks. Prints both blocks and a coverage line.

Exit 0: complete. Exit 1: bad input; one sentence says what to fix. Exit 2: partial; the
output says what was skipped. Never touches the network.
"""
import argparse
import calendar
import csv
import hashlib
import io
import re
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path

sys.dont_write_bytecode = True  # leave no __pycache__ inside the installed skill
sys.path.insert(0, str(Path(__file__).resolve().parent))
import programme as pg  # noqa: E402

# Planning convention set by the campaign-plan brief (session lead, 2026-10-20): the
# conservative case assumes half the base case's orders. It is not evidence about this
# brand. Change it per run with --conservative-factor.
CONSERVATIVE_FACTOR = Decimal("0.5")

# Follower bands from the pack's schemas.md section 4 (2026-10-20): nano under 10,000, micro
# 10,000 to 49,999, mid 50,000 to 499,999, macro 500,000 and up.
TIER_FLOORS = [("macro", 500000), ("mid", 50000), ("micro", 10000), ("nano", 0)]
TIERS = ["nano", "micro", "mid", "macro"]
COMPENSATION = ["cpa", "hybrid", "flat", "gift"]
SLUG = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])-[a-z0-9]+(?:-[a-z0-9]+)*$")
BASE_COLUMNS = ["tier", "creators", "expected_orders_per_creator", "orders_source",
                "flat_fee", "gift_units", "gift_unit_cost"]
OPTIONAL_COLUMNS = ["compensation", "basis"]
BUDGET_COLUMNS = ["campaign_slug", "scenario", "tier", "compensation", "creators",
                  "expected_tracked_orders", "orders_source", "revenue", "commission_basis",
                  "discount_cost", "commission_cost", "fee_cost", "gift_cost", "rail_fee_cost",
                  "programme_cost", "cost_per_tracked_order", "commission_return_on_sales",
                  "contribution_low_margin", "contribution_high_margin", "label", "basis"]
MARKERS = {
    "budget": ("<!-- plan_budget:budget:begin -->", "<!-- plan_budget:budget:end -->"),
    "dates": ("<!-- plan_budget:dates:begin -->", "<!-- plan_budget:dates:end -->"),
}
TITLE = re.compile(r"^# Campaign plan: (?P<slug>\S+) \((?P<status>[^)]*)\)\s*$")
CENT = Decimal("0.01")


class InputError(Exception):
    """Bad input; the message is the sentence the person reads."""


def q2(x):
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def dec(text, what):
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        raise InputError(f"{what}: '{text}' is not a number.")
    if not value.is_finite():
        raise InputError(f"{what}: '{text}' is not a number.")
    return value


def fmt(x):
    return "" if x is None else str(q2(x))


def money(cur, x):
    return "unknown" if x is None else f"{cur} {q2(x):,}"


def pct(x):
    """A percentage as written by a person: 15, 2.9, 55."""
    s = format(x.normalize(), "f")
    return s


# ---------------------------------------------------------------- programme inputs

def programme_inputs(sections, need_fee_rule):
    p = {}
    text, marks = pg.require(sections, "aov")
    nums = pg.numbers(text)
    if not nums:
        raise InputError("Programme section 1: the average order value has no number; write it as, for example, '42.00 USD, measured 2026-09-30'.")
    p["aov"], p["aov_label"] = Decimal(nums[0]), pg.label_for(marks)
    if p["aov"] <= 0:
        raise InputError("Programme section 1: the average order value must be above 0.")

    text, marks = pg.require(sections, "margin")
    nums = [Decimal(n) for n in pg.numbers(text)]
    if not nums:
        raise InputError("Programme section 1: the gross margin band has no number; write it as, for example, '55 to 65 percent'.")
    low, high = (min(nums[:2]), max(nums[:2])) if len(nums) > 1 else (nums[0], nums[0])
    if not (Decimal(0) < low <= high < Decimal(100)):
        raise InputError("Programme section 1: the gross margin band must be percentages above 0 and below 100.")
    if "net revenue" in text.lower() and "list price" not in text.lower():
        raise InputError("Programme section 1 states the gross margin band on net revenue; the shared per-order arithmetic (schemas.md section 12) and this script read it on list price only. Restate the band on list price with the owner, or have the shared definition extended.")
    p["m_low"], p["m_high"], p["margin_label"] = low, high, pg.label_for(marks)

    text, _ = pg.require(sections, "currency")
    m = re.search(r"\b[A-Z]{3}\b", text)
    if not m:
        raise InputError("Programme section 1: the store currency should be a three-letter code such as USD.")
    p["cur"] = m.group(0)

    text, marks = pg.require(sections, "commission_rate")
    if text.lower().startswith("none"):
        p["rate"] = Decimal(0)
    else:
        nums = pg.numbers(text)
        if not nums:
            raise InputError("Programme section 4: the commission rate has no number; write it as, for example, '15 percent'.")
        p["rate"] = Decimal(nums[0])
    if not (Decimal(0) <= p["rate"] < Decimal(100)):
        raise InputError("Programme section 4: the commission rate must be a percentage from 0 to below 100.")
    p["rate_label"] = pg.label_for(marks)

    text, _ = pg.require(sections, "commission_basis")
    low_text = text.lower()
    if "after discount" in low_text:
        p["basis"] = "after"
    elif "before discount" in low_text:
        p["basis"] = "before"
    else:
        raise InputError(f"Programme section 4: the commission basis must say 'after discounts' or 'before discounts' for the script to compute commission; it says '{text}'.")

    text, marks = pg.require(sections, "discount")
    low_text = text.lower()
    nums = pg.numbers(text)
    if low_text.startswith("none") or low_text.startswith("no discount"):
        p["disc_kind"], p["disc_value"] = "percentage", Decimal(0)
    elif not nums:
        raise InputError("Programme section 4: the customer-facing discount has no number; write it as '15 percent' or 'fixed 5.00 USD'.")
    elif "%" in text or "percent" in low_text:
        p["disc_kind"], p["disc_value"] = "percentage", Decimal(nums[0])
        if p["disc_value"] >= 100:
            raise InputError("Programme section 4: a percentage discount must be below 100.")
    elif "fixed" in low_text or "amount" in low_text or p["cur"] in text:
        p["disc_kind"], p["disc_value"] = "fixed", Decimal(nums[0])
    else:
        raise InputError("Programme section 4: say whether the customer-facing discount is a percent or a fixed amount, for example '15 percent' or 'fixed 5.00 USD'.")
    p["disc_label"] = pg.label_for(marks)
    if p["disc_kind"] == "percentage":
        p["disc_per_order"] = p["aov"] * p["disc_value"] / 100
        p["disc_text"] = f"{pct(p['disc_value'])} percent off the order"
    else:
        p["disc_per_order"] = min(p["disc_value"], p["aov"])
        p["disc_text"] = f"{money(p['cur'], p['disc_value'])} off the order"

    value, _ = pg.field(sections, "combine")
    p["combine"] = value
    value, _ = pg.field(sections, "codes_after")
    p["codes_after"] = value
    value, _ = pg.field(sections, "thin")
    nums = pg.numbers(value or "")
    p["thin"] = Decimal(nums[0]) if nums else None
    value, _ = pg.field(sections, "fee_rule")
    p["fee_rule"] = value
    if need_fee_rule and value is None:
        raise InputError("Programme section 4: 'when a flat or hybrid deal is allowed, and who approves one' is blank or [open], and the assumptions carry a fee; the owner fills it with program-setup first.")
    if need_fee_rule and value.lower().startswith(("none", "never", "not allowed")):
        raise InputError(f"Programme section 4 allows no flat or hybrid deals ('{value}'), and the assumptions carry a fee; remove the fee rows or have the owner change section 4.")
    return p


# ---------------------------------------------------------------- assumptions

def resolve(workspace, path_text):
    p = Path(path_text)
    if p.is_file() or p.is_absolute():
        return p
    alt = Path(workspace) / path_text
    return alt if alt.is_file() else p


def read_assumptions(path):
    if not path.is_file():
        raise InputError(f"{path} was not found; copy assets/assumptions-template.csv there and fill one row per tier and compensation.")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise InputError(f"{path} is empty; it needs the header row and one row per tier and compensation.")
    header = [h.strip() for h in rows[0]]
    allowed = [BASE_COLUMNS, BASE_COLUMNS + ["compensation"], BASE_COLUMNS + ["basis"],
               BASE_COLUMNS + OPTIONAL_COLUMNS]
    if header not in allowed:
        missing = [c for c in BASE_COLUMNS if c not in header]
        extra = [c for c in header if c not in BASE_COLUMNS + OPTIONAL_COLUMNS]
        raise InputError(f"{path}: the header must be {','.join(BASE_COLUMNS)}, optionally followed by compensation and then basis; missing: {', '.join(missing) or 'none'}; extra: {', '.join(extra) or 'none'} (or the order differs).")
    out, seen = [], set()
    for line_no, raw in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in raw):
            continue
        if len(raw) != len(header):
            raise InputError(f"{path} line {line_no}: {len(raw)} cells for {len(header)} columns.")
        r = dict(zip(header, (c.strip() for c in raw)))
        where = f"{path.name} line {line_no}"
        tier = r["tier"].lower()
        if tier not in TIERS:
            raise InputError(f"{where}: tier '{r['tier']}' is not one of nano, micro, mid, macro (schemas.md section 4).")
        for col in BASE_COLUMNS[1:]:
            if col != "orders_source" and r[col] == "":
                if col == "expected_orders_per_creator":
                    raise InputError(f"{where}: expected_orders_per_creator is empty; the person gives a working figure, or an estimate with its basis; the script does not supply one.")
                raise InputError(f"{where}: {col} is empty; the budget needs a number here (write 0 if there is none).")
        creators = dec(r["creators"], f"{where}, creators")
        if creators < 1 or creators != creators.to_integral_value():
            raise InputError(f"{where}: creators must be a whole number of 1 or more; remove the row if the tier is not used.")
        epc = dec(r["expected_orders_per_creator"], f"{where}, expected_orders_per_creator")
        source = r["orders_source"].lower()
        if source not in ("user", "estimate"):
            raise InputError(f"{where}: orders_source must be 'user' (the person's figure) or 'estimate' (with its basis named).")
        fee = dec(r["flat_fee"], f"{where}, flat_fee")
        units = dec(r["gift_units"], f"{where}, gift_units")
        unit_cost = dec(r["gift_unit_cost"], f"{where}, gift_unit_cost")
        if epc < 0 or fee < 0 or units < 0 or unit_cost < 0:
            raise InputError(f"{where}: numbers cannot be negative.")
        if units != units.to_integral_value():
            raise InputError(f"{where}: gift_units must be a whole number.")
        if units > 0 and unit_cost == 0:
            raise InputError(f"{where}: gift_units is above 0 but gift_unit_cost is 0; give the brand's cost per unit landed at the creator (product cost plus shipping).")
        comp = (r.get("compensation") or "").lower() or ("hybrid" if fee > 0 else "cpa")
        if comp not in COMPENSATION:
            raise InputError(f"{where}: compensation '{comp}' is not one of cpa, hybrid, flat, gift.")
        if comp in ("cpa", "gift") and fee > 0:
            raise InputError(f"{where}: a {comp} row carries no fee; use hybrid or flat for a fee, or set flat_fee to 0.")
        if comp in ("hybrid", "flat") and fee == 0:
            raise InputError(f"{where}: a {comp} row needs its flat_fee per creator above 0.")
        if comp == "gift" and units == 0:
            raise InputError(f"{where}: a gift row needs gift_units above 0.")
        basis = r.get("basis", "")
        if source == "estimate" and not basis:
            raise InputError(f"{where}: an estimate needs its basis named in the basis column, for example the file or past result it rests on.")
        key = (tier, comp)
        if key in seen:
            raise InputError(f"{where}: a second {tier} {comp} row; combine them into one row.")
        seen.add(key)
        out.append({"tier": tier, "comp": comp, "creators": creators, "epc": epc, "source": source,
                    "fee": fee, "units": units, "unit_cost": unit_cost, "basis": basis})
    if not out:
        raise InputError(f"{path} has a header but no rows; add one row per tier and compensation.")
    out.sort(key=lambda r: (TIERS.index(r["tier"]), COMPENSATION.index(r["comp"])))
    return out


# ---------------------------------------------------------------- arithmetic
# Every quantity below is defined in the pack's schemas.md section 12, "Shared definitions"
# (2026-10-20), so a plan, an offer, a statement and a report agree. Two extensions, both
# marked where they occur: a fixed-amount discount, and a store-wide sale taken before the code.

def per_order(p, comp, rail, sale=Decimal(0)):
    """Per-order quantities for one compensation type (schemas.md section 12).

    Average order value is section 1's, before discounts. Revenue per order = AOV times
    (1 minus the customer discount); extension: a fixed-amount discount is taken off the
    basket instead, capped at it, and a store sale (the sale case) is taken off first.
    Commission basis per order: revenue per order by default, or the AOV when programme
    section 4 sets a before-discounts basis. Commission per order = rate times the basis,
    for cpa and hybrid rows. Cost of goods per order = AOV times (1 minus the margin), at
    each end of the band. Contribution per order = revenue minus cost of goods minus
    commission (section 12 leaves rail fees out of it; programme cost includes them).
    """
    after_sale = p["aov"] * (1 - sale / 100)
    if p["disc_kind"] == "percentage":
        disc = after_sale * p["disc_value"] / 100
    else:
        disc = min(p["disc_value"], after_sale)
    revenue = after_sale - disc
    basis = revenue if p["basis"] == "after" else p["aov"]
    commission = basis * p["rate"] / 100 if comp in ("cpa", "hybrid") else Decimal(0)
    rail_fee = None
    if rail is not None:
        rail_fee = commission * rail[0] / 100 if rail[1] == "commission" else revenue * rail[0] / 100
    cogs_low = p["aov"] * (1 - p["m_low"] / 100)
    cogs_high = p["aov"] * (1 - p["m_high"] / 100)
    return {"disc": disc, "revenue": revenue, "basis": basis, "commission": commission, "rail": rail_fee,
            "cogs_low": cogs_low, "cogs_high": cogs_high,
            "contrib_low": revenue - cogs_low - commission, "contrib_high": revenue - cogs_high - commission}


def break_even(fee, contrib):
    """Tracked orders for a flat fee to break even: fee over contribution per order, rounded up."""
    if contrib <= 0:
        return None
    return int((fee / contrib).to_integral_value(rounding=ROUND_CEILING))


def compute(slug, rows, p, factor, rail, sale):
    out = []
    cases = [("base", Decimal(1), Decimal(0)), ("conservative", factor, Decimal(0))]
    if sale is not None:
        cases.append(("sale", Decimal(1), sale))
    keys = ("revenue", "basis", "disc", "comm", "fee", "gift", "rail", "cost", "low", "high")
    for scenario, f, s in cases:
        tot = {k: Decimal(0) for k in keys}
        tot["creators"], tot["orders"] = Decimal(0), Decimal(0)
        for r in rows:
            po = per_order(p, r["comp"], rail, s)
            orders = r["creators"] * r["epc"] * f
            row = {
                "revenue": q2(orders * po["revenue"]), "basis": q2(orders * po["basis"]),
                "disc": q2(orders * po["disc"]), "comm": q2(orders * po["commission"]),
                "fee": q2(r["creators"] * r["fee"]), "gift": q2(r["creators"] * r["units"] * r["unit_cost"]),
                "rail": None if po["rail"] is None else q2(orders * po["rail"]),
            }
            # Programme cost (section 12): commission + flat fees + gifted units at unit cost
            # + customer discount given + rail or app fee.
            row["cost"] = row["comm"] + row["fee"] + row["gift"] + row["disc"] + (row["rail"] or 0)
            # Contribution for the row: tracked orders times contribution per order, less the
            # costs section 12 keeps out of the per-order figure (fees, gifts, rail fees).
            fixed = row["fee"] + row["gift"] + (row["rail"] or 0)
            row["low"] = q2(orders * po["contrib_low"]) - fixed
            row["high"] = q2(orders * po["contrib_high"]) - fixed
            note = f"orders_source={r['source']}" + (f"; {r['basis']}" if r["basis"] else "")
            if scenario == "conservative":
                note += f"; base orders times {factor}"
            if scenario == "sale":
                note += f"; store sale of {pct(s)} percent taken before the creator code, base orders (verify the stacking on a test order)"
            out.append(make_row(slug, scenario, r["tier"], r["comp"], r["creators"], orders, r["source"], row, note))
            tot["creators"] += r["creators"]
            tot["orders"] += orders
            for k in keys:
                if k == "rail":
                    tot["rail"] = None if (row["rail"] is None or tot["rail"] is None) else tot["rail"] + row["rail"]
                else:
                    tot[k] += row[k]
        out.append(make_row(slug, scenario, "total", "", tot["creators"], tot["orders"], "", tot, "sum of the rows above"))
    return out


def make_row(slug, scenario, tier, comp, creators, orders, source, m, note):
    return {
        "campaign_slug": slug, "scenario": scenario, "tier": tier, "compensation": comp,
        "creators": str(int(creators)), "expected_tracked_orders": fmt(orders), "orders_source": source,
        "revenue": fmt(m["revenue"]), "commission_basis": fmt(m["basis"]),
        "discount_cost": fmt(m["disc"]), "commission_cost": fmt(m["comm"]),
        "fee_cost": fmt(m["fee"]), "gift_cost": fmt(m["gift"]), "rail_fee_cost": fmt(m["rail"]),
        "programme_cost": fmt(m["cost"]),
        "cost_per_tracked_order": fmt(m["cost"] / orders) if orders > 0 else "",
        "commission_return_on_sales": fmt(m["basis"] / m["cost"]) if m["cost"] > 0 else "",
        "contribution_low_margin": fmt(m["low"]),
        "contribution_high_margin": fmt(m["high"]),
        "label": "Estimated", "basis": note,
    }


# ---------------------------------------------------------------- shortlist supply

def band(followers_text):
    t = (followers_text or "").replace(",", "").strip()
    if not t.isdigit():
        return "unknown"
    n = int(t)
    for name, floor in TIER_FLOORS:
        if n >= floor:
            return name
    return "unknown"


def read_shortlist(path, table, filled):
    if not path.is_file():
        raise InputError(f"{path} was not found; give the latest data/shortlist-YYYY-MM-DD.csv from creator-vetting, or run without --shortlist (the plan is then partial).")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = [f.strip() for f in (reader.fieldnames or [])]
        missing = {"platform", "verdict"} - set(fields)
        if "tier" not in fields and "followers" not in fields:
            missing.add("followers")
        if missing:
            raise InputError(f"{path}: column(s) {', '.join(sorted(missing))} missing; the supply count needs platform, verdict and followers (or tier).")
        rows = [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in reader]
    supply = {t: {"engage": 0, "negotiate": 0, "not_cleared": 0} for t in TIERS + ["unknown"]}
    platforms, others, disagree = {}, 0, 0
    for r in rows:
        verdict = r.get("verdict", "").lower()
        if verdict not in ("engage", "negotiate"):
            others += 1
            continue
        tier = r.get("tier", "").lower()
        banded = band(r.get("followers"))
        if tier not in TIERS:
            tier = banded
        elif banded != "unknown" and banded != tier:
            disagree += 1
        plat = r.get("platform", "").lower() or "unknown"
        status, text, via = pg.platform_ruling(table, plat) if filled else ("not checked", "", "")
        cleared = (not filled) or pg.eligible(status)
        supply[tier][verdict if cleared else "not_cleared"] += 1
        entry = platforms.setdefault(plat, {"status": status, "text": text, "via": via, "count": 0})
        entry["count"] += 1
    return {"rows": len(rows), "others": others, "supply": supply, "platforms": platforms, "disagree": disagree}


# ---------------------------------------------------------------- dates

def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_date(text, what):
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InputError(f"{what}: '{text}' is not a date in YYYY-MM-DD form.")


def window_dates(sections, start, end, today):
    """Rows of (date, what, label, rule, start event), and notes on what was not computed."""
    text, _ = pg.require(sections, "holdback")
    nums = pg.numbers(text)
    if not nums or "." in nums[0]:
        raise InputError("Programme section 5: the holdback must be a whole number of days, for example '30 [default]'.")
    hold = int(nums[0])
    rule = f"programme section 5 holdback, {hold} calendar days"
    rows = [(start, "live window opens", "User-provided", "--window", "none"),
            (end, "live window closes", "User-provided", "--window", "none")]
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last = date(y, m, calendar.monthrange(y, m)[1])
        rows.append((last + timedelta(days=hold), f"statement period {y:04d}-{m:02d} clears its holdback; commission-statement can close it",
                     "User-provided inputs, computed", rule, f"last order date of {y:04d}-{m:02d}"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    rows.append((end + timedelta(days=hold), "the last order in the window clears its holdback; earliest full performance report",
                 "User-provided inputs, computed", rule, "window close"))
    notes = []
    value, _ = pg.field(sections, "rights_window")
    found = re.search(r"(\d+)\s*(day|week|month|year)s?", value or "", re.I)
    if value is None:
        notes.append("rights end dates not computed: programme section 11 usage-rights window is blank or [open]")
    elif not found:
        notes.append(f"rights end dates not computed: programme section 11 says '{value}', not 'N days', 'N weeks', 'N months' or 'N years'")
    else:
        n, unit = int(found.group(1)), found.group(2).lower()
        def plus(d):
            if unit == "day":
                return d + timedelta(days=n)
            if unit == "week":
                return d + timedelta(days=7 * n)
            return add_months(d, n * (12 if unit == "year" else 1))
        wrule = f"programme section 11 usage-rights window, {n} {unit}s from posting (same day number, month end if shorter)"
        rows.append((plus(start), "reuse rights end for a post made on the first window day", "User-provided inputs, computed", wrule, "post date"))
        rows.append((plus(end), "reuse rights end for a post made on the last window day", "User-provided inputs, computed", wrule, "post date"))
    after, _ = pg.field(sections, "codes_after")
    if after is None:
        notes.append("programme section 4 does not say whether codes end with the window or stay active; the owner rules (plan section 8)")
    elif after.lower().startswith("end"):
        rows.append((end, "creator codes end with the window; affiliate-onboarding sets this end date", "User-provided",
                     "programme section 4, codes after a campaign window: end", "window close"))
    else:
        notes.append(f"codes stay active after the window (programme section 4: '{after}'); later orders still attribute to the creator but fall outside this plan's window")
    rows.sort(key=lambda r: r[0])
    lead = (start - today).days
    notes.insert(0, f"lead time: {lead} calendar days from the plan's date ({today.isoformat()}, UTC unless --as-of was given) to the window opening; every stage in the timeline table has to fit inside it")
    return rows, notes


# ---------------------------------------------------------------- rendering

def short_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def seal(lines):
    body = "\n".join(lines)
    return body + "\nblock sha256: " + short_hash(body)


def scenario_table(rows, scenario, cur):
    head = ("| tier | compensation | creators | tracked orders | revenue | discount given | commission | fees | gift cost | rail fees | programme cost | cost per tracked order | commission return on sales | contribution, low to high margin |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    out = list(head)
    for r in rows:
        if r["scenario"] != scenario:
            continue
        rail = money(cur, Decimal(r["rail_fee_cost"])) if r["rail_fee_cost"] else "not included"
        cpo = money(cur, Decimal(r["cost_per_tracked_order"])) if r["cost_per_tracked_order"] else "no orders"
        spc = r["commission_return_on_sales"] or "no cost"
        tier = "**total**" if r["tier"] == "total" else r["tier"]
        out.append(f"| {tier} | {r['compensation']} | {r['creators']} | {r['expected_tracked_orders']} | {money(cur, Decimal(r['revenue']))} | "
                   f"{money(cur, Decimal(r['discount_cost']))} | {money(cur, Decimal(r['commission_cost']))} | {money(cur, Decimal(r['fee_cost']))} | "
                   f"{money(cur, Decimal(r['gift_cost']))} | {rail} | {money(cur, Decimal(r['programme_cost']))} | {cpo} | {spc} | "
                   f"{money(cur, Decimal(r['contribution_low_margin']))} to {money(cur, Decimal(r['contribution_high_margin']))} |")
    return out


def render_budget(stamp, p, rail, factor, sale, assumptions_path, rows_in, rows, supply, shortlist_path, flags, partial, csv_hash):
    cur = p["cur"]
    basis_word = "after discounts" if p["basis"] == "after" else "before discounts"
    L = [f"Generated by scripts/plan_budget.py at {stamp}. Do not edit inside this block: change the assumptions or the programme file and re-run the script.", ""]
    L.append("Status: complete" if not partial else "Status: partial. Not done: " + "; ".join(partial) + ".")
    L += ["", "Inputs read", "", "| input | value | label | from |", "|---|---|---|---|",
          f"| average order value | {money(cur, p['aov'])} | {p['aov_label']} | programme section 1 |",
          f"| gross margin band | {pct(p['m_low'])} to {pct(p['m_high'])} percent | {p['margin_label']} | programme section 1 |",
          f"| commission rate | {pct(p['rate'])} percent of the subtotal {basis_word} | {p['rate_label']} | programme section 4 |",
          f"| customer discount | {p['disc_text']} | {p['disc_label']} | programme section 4 |"]
    if rail is None:
        L.append("| rail fee | not given; the totals leave it out | none | --rail-fee-pct |")
    else:
        L.append(f"| rail fee | {pct(rail[0])} percent of {'commission paid' if rail[1] == 'commission' else 'tracked net sales'} | User-provided | --rail-fee-pct, --rail-fee-basis |")
    L.append(f"| conservative case | base orders times {factor} | Estimated (planning convention, not evidence) | plan_budget.py constant or --conservative-factor |")
    L.append(f"| creator codes combining with other discounts | {p['combine'] or 'not set'} | {'User-provided' if p['combine'] else 'none'} | programme section 4 |")
    if sale is None:
        L.append("| store-wide sale during the window | none given; no sale case | none | --sale-pct |")
    else:
        L.append(f"| store-wide sale during the window | {pct(sale)} percent, combined with the creator code | User-provided | --sale-pct |")
    L.append(f"| assumptions | {assumptions_path}, {len(rows_in)} rows | per row below | the person |")
    L.append(f"| codes after the window | {p['codes_after'] or 'not set'} | {'User-provided' if p['codes_after'] else 'none'} | programme section 4 |")
    L += ["", "Per order, by the shared definitions (schemas.md section 12). Estimated: an average order, before any fee, gift or rail fee.", "",
          "| compensation | revenue per order | commission basis per order | commission per order | cost of goods per order, low to high margin | contribution per order, low to high margin |",
          "|---|---|---|---|---|---|"]
    for comp in sorted({r["comp"] for r in rows_in}, key=COMPENSATION.index):
        po = per_order(p, comp, rail)
        L.append(f"| {comp} | {money(cur, po['revenue'])} | {money(cur, po['basis'])} | {money(cur, po['commission'])} | "
                 f"{money(cur, po['cogs_low'])} to {money(cur, po['cogs_high'])} | {money(cur, po['contrib_low'])} to {money(cur, po['contrib_high'])} |")
    L += ["", "Base case. Every figure in this table is Estimated, from the inputs above and the assumptions below.", ""]
    L += scenario_table(rows, "base", cur)
    L += ["", f"Conservative case: base orders times {factor}; fees and gifts unchanged. Every figure is Estimated.", ""]
    L += scenario_table(rows, "conservative", cur)
    if sale is not None:
        L += ["", f"Sale case: base orders, with a store-wide sale of {pct(sale)} percent taken before the creator's code. The discount column is the code's discount only; the sale's discount lowers contribution, not the programme's cost. Every figure is Estimated; how the store combines the two depends on its discount settings, so a test order confirms it (M2).", ""]
        L += scenario_table(rows, "sale", cur)
    units = sum(int(r["creators"] * r["units"]) for r in rows_in)
    L += ["", f"Gift units to ship: {units} (creators times gift units, summed over the rows). Stock for the campaign's products covers these and the base case's tracked orders (M4)."]
    L += ["", "Supply from the shortlist", ""]
    if supply is None:
        L.append("Not counted: no shortlist was given.")
    else:
        L.append(f"Counted from {shortlist_path}: {supply['rows']} rows, of which {supply['rows'] - supply['others']} engage or negotiate. The verdicts are the vetting's, confirmed by the programme lead (User-provided); the counts are rows in that file.")
        L += ["", "| tier | engage, platform cleared | negotiate, platform cleared | engage or negotiate, platform not cleared | planned creators |", "|---|---|---|---|---|"]
        planned = {}
        for r in rows_in:
            planned[r["tier"]] = planned.get(r["tier"], 0) + int(r["creators"])
        for t in TIERS + ["unknown"]:
            s = supply["supply"][t]
            if t == "unknown" and not any(s.values()):
                continue
            L.append(f"| {t} | {s['engage']} | {s['negotiate']} | {s['not_cleared']} | {planned.get(t, 0)} |")
        L += ["", "| platform | programme section 3, organic creator posts | engage or negotiate rows |", "|---|---|---|"]
        for plat in sorted(supply["platforms"]):
            e = supply["platforms"][plat]
            ruling = (e["text"] if e["status"] == "with conditions" and e["text"] else e["status"]) + (f" (row: {e['via']})" if e["via"] and e["via"] != plat else "")
            L.append(f"| {plat} | {ruling} | {e['count']} |")
    L += ["", "Assumptions, by row", ""]
    for r in rows_in:
        L.append(f"- {r['tier']} {r['comp']}: creators {r['creators']}; expected tracked orders per creator over the window {r['epc']} ({'User-provided' if r['source'] == 'user' else 'Estimated'}{'; basis: ' + r['basis'] if r['basis'] else ''}); fee per creator {money(cur, r['fee'])}; gift units per creator {r['units']}, at {money(cur, r['unit_cost'])} each.")
    L.append("- A coded order's basket before discount is taken to equal the programme's average order value (Estimated).")
    L.append("- Every tracked order is counted as the creator's; orders that would have happened anyway are not separated (could not judge).")
    L.append("- Refunds are not modelled: every planned order is taken as paid and kept, so the programme section 4 partial-refund rule does not enter the plan.")
    L += ["", "Flags for the owner", ""]
    L += [f"- {f}" for f in flags] if flags else ["- none"]
    L += ["", f"budget.csv sha256: {csv_hash}"]
    return seal(L)


def render_dates(stamp, rows, notes, window_given):
    L = [f"Generated by scripts/plan_budget.py at {stamp}. Calendar days; dates are UTC calendar dates. Do not edit inside this block; re-run the script.", ""]
    if not window_given:
        L.append("Not computed: no --window was given. Ask the person for the first and last day posts may go live, then re-run.")
    else:
        L += ["| date | what | label | rule | start event |", "|---|---|---|---|---|"]
        L += [f"| {d.isoformat()} | {what} | {label} | {rule} | {ev} |" for d, what, label, rule, ev in rows]
        if notes:
            L.append("")
            L += [f"- {n[0].upper() + n[1:]}." for n in notes]
    return seal(L)


# ---------------------------------------------------------------- writing

def csv_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=BUDGET_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def write_budget(path, text, n_rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = path.read_text(encoding="utf-8")
        old_rows = max(0, len(old.splitlines()) - 1)
        if old == text:
            return f"{path}: read {old_rows} rows; unchanged, nothing written."
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        keep = path.with_name(f"budget-superseded-{stamp}.csv")
        n = 2
        while keep.exists():
            keep = path.with_name(f"budget-superseded-{stamp}-{n}.csv")
            n += 1
        path.rename(keep)
        path.write_text(text, encoding="utf-8")
        return f"{path}: read {old_rows} rows from the previous file, kept it as {keep.name}; wrote {n_rows} rows (regenerated from the assumptions)."
    path.write_text(text, encoding="utf-8")
    return f"{path}: no previous file; wrote {n_rows} rows."


def plan_status(plan_path):
    if not plan_path.is_file():
        return None
    first = plan_path.read_text(encoding="utf-8").splitlines()[:1]
    m = TITLE.match(first[0]) if first else None
    return m.group("status").strip() if m else ""


def insert_blocks(plan_path, blocks):
    text = plan_path.read_text(encoding="utf-8")
    written, missing = [], []
    for name, body in blocks.items():
        begin, end = MARKERS[name]
        i, j = text.find(begin), text.find(end)
        if i < 0 or j < 0 or j < i:
            missing.append(name)
            continue
        text = text[:i + len(begin)] + "\n" + body + "\n" + text[j:]
        written.append(name)
    if written:
        plan_path.write_text(text, encoding="utf-8")
    return written, missing


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Exit 0 complete, 1 bad input, 2 partial. No network.")
    ap.add_argument("workspace", help="the workspace folder (holds program/program.md)")
    ap.add_argument("--campaign", required=True, help="campaign slug, YYYY-MM-words (schemas.md section 2)")
    ap.add_argument("--assumptions", required=True, help="per-tier assumptions CSV, usually campaigns/SLUG/assumptions.csv")
    ap.add_argument("--shortlist", help="the latest data/shortlist-YYYY-MM-DD.csv, to count supply by tier and platform")
    ap.add_argument("--window", nargs=2, metavar=("FROM", "TO"), help="first and last day posts may go live, YYYY-MM-DD")
    ap.add_argument("--rail-fee-pct", help="the rail's own fee in percent (0 if the rail charges none)")
    ap.add_argument("--rail-fee-basis", choices=["commission", "sales"], help="what the rail fee is a percent of")
    ap.add_argument("--as-of", help="the date the plan is made, YYYY-MM-DD (default: today, UTC); lead time is counted from it")
    ap.add_argument("--sale-pct", help="a store-wide percentage sale running during the window that the creator code combines with; adds a sale case")
    ap.add_argument("--conservative-factor", default=str(CONSERVATIVE_FACTOR), help=f"multiplier on base orders for the conservative case (default {CONSERVATIVE_FACTOR})")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except (InputError, pg.ProgrammeError) as e:
        print(f"plan_budget: {e}", file=sys.stderr)
        return 1


def run(a):
    ws = Path(a.workspace)
    if not ws.is_dir():
        raise InputError(f"{ws} is not a folder; give the workspace path first.")
    slug = a.campaign
    sm = SLUG.match(slug)
    if not sm:
        raise InputError(f"'{slug}' is not a campaign slug: lowercase words joined by hyphens after YYYY-MM-, for example 2026-12-holiday-tote (schemas.md section 2).")
    factor = dec(a.conservative_factor, "--conservative-factor")
    if not (Decimal(0) < factor <= Decimal(1)):
        raise InputError("--conservative-factor must be above 0 and at most 1.")
    rail = None
    if a.rail_fee_pct is not None or a.rail_fee_basis is not None:
        if a.rail_fee_pct is None or a.rail_fee_basis is None:
            raise InputError("Give both --rail-fee-pct and --rail-fee-basis, or neither.")
        pct = dec(a.rail_fee_pct, "--rail-fee-pct")
        if not (Decimal(0) <= pct < Decimal(100)):
            raise InputError("--rail-fee-pct must be from 0 to below 100.")
        rail = (pct, a.rail_fee_basis)
    sale = None
    if a.sale_pct is not None:
        sale = dec(a.sale_pct, "--sale-pct")
        if not (Decimal(0) < sale < Decimal(100)):
            raise InputError("--sale-pct must be above 0 and below 100.")

    camp = ws / "campaigns" / slug
    plan_path = camp / "plan.md"
    status = plan_status(plan_path)
    if status and status.lower().startswith("approved"):
        raise InputError(f"{plan_path} is marked '{status}'; the script will not change an approved plan's budget. With the owner's word, set the title status to draft, add a line under Revisions saying what changes and why, then re-run.")

    sections = pg.load(ws)
    assumptions_path = resolve(ws, a.assumptions)
    rows_in = read_assumptions(assumptions_path)
    p = programme_inputs(sections, need_fee_rule=any(r["fee"] > 0 for r in rows_in))

    partial, used, missing = [], ["programme sections 1 and 4", f"assumptions ({len(rows_in)} rows)"], []
    flags = []
    if rail is None:
        partial.append("rail fees not included (no --rail-fee-pct given)")
        missing.append("the rail's fee")
    else:
        used.append("the rail fee given on the command line")

    rows = compute(slug, rows_in, p, factor, rail, sale)

    for r in rows_in:
        if r["fee"] > 0:
            flags.append(f"{r['tier']} {r['comp']}: a fee of {money(p['cur'], r['fee'])} per creator, paid whatever the orders. Programme section 4 says: \"{p['fee_rule']}\". Owner approval is needed before any offer.")
    for comp in sorted({r["comp"] for r in rows_in}, key=COMPENSATION.index):
        for s, when in ((Decimal(0), ""), (sale, " during the sale")):
            if s is None:
                continue
            po = per_order(p, comp, rail, s)
            if po["contrib_low"] < 0:
                flags.append(f"{comp} rows{when}: contribution per order (schemas.md section 12) is {money(p['cur'], po['contrib_low'])} at the low margin, so every order loses money before any fee, gift or rail fee.")
    for r in rows_in:
        if r["fee"] > 0:
            po = per_order(p, r["comp"], rail)
            lo, hi = break_even(r["fee"], po["contrib_low"]), break_even(r["fee"], po["contrib_high"])
            if lo is None:
                flags.append(f"{r['tier']} {r['comp']}: the fee never breaks even at the low margin, because contribution per order is not above 0.")
            else:
                flags.append(f"{r['tier']} {r['comp']}: the fee breaks even at {lo} tracked orders per creator at the low margin and {hi} at the high margin (fee over contribution per order, rounded up, schemas.md section 12), against {r['epc']} assumed.")
    if p["thin"] is not None:
        for r in rows_in:
            if r["epc"] < p["thin"]:
                flags.append(f"{r['tier']} {r['comp']}: {r['epc']} expected tracked orders per creator is below the {p['thin']} at which programme section 5 calls a creator's read thin; performance-report will judge these creators as a group, not one by one.")
    for r in rows:
        low = Decimal(r["contribution_low_margin"])
        if low >= 0:
            continue
        if r["tier"] == "total":
            flags.append(f"{r['scenario']} case: the campaign as a whole loses {money(p['cur'], -low)} at the low margin.")
        elif r["scenario"] == "base":
            flags.append(f"{r['tier']} {r['compensation']}: loses {money(p['cur'], -low)} at the low margin even in the base case.")

    if sale is not None:
        ruling = (p["combine"] or "").lower()
        if not ruling:
            flags.append("programme section 4 does not say whether creator codes combine with other discounts, so the sale case is a question, not a plan: the owner rules (plan section 8).")
        elif ruling.startswith(("no", "none", "never", "not")):
            flags.append(f"programme section 4 says \"{p['combine']}\": a creator code and the sale would not stack, so the sale case shows something the store will not allow. During the sale a buyer picks one, and an order without the code is not attributed (R9).")
    supply = None
    shortlist_path = None
    if a.shortlist:
        shortlist_path = resolve(ws, a.shortlist)
        table, filled = pg.platform_table(sections)
        supply = read_shortlist(shortlist_path, table, filled)
        used.append(f"shortlist {shortlist_path.name}")
        if filled:
            used.append("programme section 3")
        else:
            partial.append("programme section 3 has no platform rulings, so supply was counted without the platform rule")
            missing.append("programme section 3 rulings")
        planned = {}
        for r in rows_in:
            planned[r["tier"]] = planned.get(r["tier"], 0) + int(r["creators"])
        for t, n in planned.items():
            s = supply["supply"][t]
            have = s["engage"] + s["negotiate"]
            if n > have:
                flags.append(f"{t}: the plan needs {n} creators and the shortlist has {have} engage or negotiate rows on cleared platforms; find more (creator-discovery, creator-vetting) or plan fewer.")
        if supply["disagree"]:
            flags.append(f"{supply['disagree']} engage or negotiate rows in the shortlist carry a tier that differs from their follower band (schemas.md section 4); the tier column was used, as the vetting wrote it. Re-run creator-vetting if the follower counts are newer.")
        blocked = sum(e["count"] for e in supply["platforms"].values() if filled and not pg.eligible(e["status"]))
        if blocked:
            flags.append(f"{blocked} engage or negotiate rows are on platforms programme section 3 does not clear for creator posts; they are not counted as supply.")
    else:
        partial.append("supply not counted (no --shortlist given)")
        missing.append("the shortlist")

    window_given = a.window is not None
    date_rows, date_notes = [], []
    if window_given:
        start = parse_date(a.window[0], "--window FROM")
        end = parse_date(a.window[1], "--window TO")
        if end < start:
            raise InputError("--window: the last day is before the first day.")
        as_of = parse_date(a.as_of, "--as-of") if a.as_of else datetime.now(timezone.utc).date()
        date_rows, date_notes = window_dates(sections, start, end, as_of)
        if start <= as_of:
            flags.append(f"the window opens on {start.isoformat()}, on or before the plan's date ({as_of.isoformat()}): the lead time is {(start - as_of).days} days, so no stage before posting can happen in time. Move the window, or give --as-of if the plan is being dated earlier.")
        used.append("programme sections 5 and 11")
        if any(n.startswith("rights end dates not computed") for n in date_notes):
            partial.append("rights end dates not computed")
            missing.append("programme section 11 usage-rights window in 'N months' form")
        if (start.year, start.month) != (int(sm.group(1)), int(sm.group(2))):
            flags.append(f"the slug's month ({sm.group(1)}-{sm.group(2)}) is not the month the window opens ({start.year:04d}-{start.month:02d}); the pack names a campaign by its opening month.")
    else:
        partial.append("dates not computed (no --window given)")
        missing.append("the live window")

    text = csv_text(rows)
    csv_hash = short_hash(text)
    write_note = write_budget(camp / "budget.csv", text, len(rows))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    # The plan write is judged before rendering so the block's own status line is right.
    plan_note, will_miss = "", []
    if not plan_path.is_file():
        will_miss = ["budget", "dates"]
        partial.append(f"blocks not written into the plan ({plan_path} does not exist yet; copy assets/plan-template.md there and re-run)")
    else:
        plan_text = plan_path.read_text(encoding="utf-8")
        will_miss = [n for n, (b, e) in MARKERS.items() if b not in plan_text or e not in plan_text]
        if will_miss:
            partial.append(f"the {' and '.join(will_miss)} block markers are missing from {plan_path}")
    budget_block = render_budget(stamp, p, rail, factor, sale, assumptions_path, rows_in, rows, supply, shortlist_path, flags, partial, csv_hash)
    dates_block = render_dates(stamp, date_rows, date_notes, window_given)
    if plan_path.is_file():
        written, _ = insert_blocks(plan_path, {"budget": budget_block, "dates": dates_block})
        plan_note = f"{plan_path}: wrote the {' and '.join(written)} block(s)." if written else f"{plan_path}: no block written."

    print(budget_block)
    print()
    print(dates_block)
    print()
    print(write_note)
    if plan_note:
        print(plan_note)
    print(f"Coverage: inputs used: {'; '.join(used)}. Inputs missing: {'; '.join(missing) or 'none'}. "
          "Could not judge: whether tracked orders are caused by the creators, reach and views, the store's real code and rail set-up (not visible to this script).")
    if partial:
        print("Result: partial. " + "; ".join(partial) + ".")
        return 2
    print("Result: complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
