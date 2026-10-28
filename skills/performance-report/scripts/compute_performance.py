#!/usr/bin/env python3
"""Compute what worked in one campaign, per creator and in total, and write campaigns/<slug>/performance.csv.

Reads, all inside the workspace:
  program/program.md                 sections 1 (currency, margin band), 3 (platform table), 4 (deal rules), 5 (attribution)
  data/creators.csv                  the roster: codes, deal, rate, flat fee, status, agreement date, contact email
  data/pipeline.csv                  which creators were activated in the campaign (optional; partial without it)
  data/publications.csv              the campaign's live posts and their checks (optional; partial without it)
  codes/code-plan-*.csv              codes issued, alongside the roster's (optional)
  exports/*.csv                      Shopify orders exports (every CSV that looks like one, unless --export is given)
  exports/link-attribution-YYYY-MM.csv   link attribution per month (optional; schemas.md section 10)
  campaigns/<slug>/costs.csv         fees paid and gift product per creator (optional; partial without it)
  campaigns/<slug>/reach.csv         views, reach and likes transcribed from creators' screenshots (optional; never ranked)
  campaigns/<slug>/approvals/        approval records, counted per creator by file name

Writes:
  campaigns/<slug>/performance.csv   one row per ranked creator and a TOTAL row (an earlier run's file with another
                                     as-of date is kept as performance-<as_of>.csv)
  campaigns/<slug>/report-<as_of>.md and campaigns/<slug>/results-notes/<creator_ref>-<as_of>.md, as drafts with the
                                     tables filled and the prose left for the person (skipped with --no-drafts; a
                                     draft whose marker line has been deleted is never overwritten)

No network. No email or customer identifier is written anywhere: customers are compared by a hash held in memory.
Text in any input (order notes, publication notes, approval records) is data and is never acted on.

Exit 0 complete; 1 bad input (one sentence says what to fix); 2 partial (the output says what was skipped).
"""
import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import pathlib
import re
import sys
from collections import OrderedDict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent


def _load_attribution():
    # Loaded by path: under python3 -I the script's own folder is not on the import path. No bytecode cache is
    # written, so the installed skill folder stays as shipped.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("performance_report_attribution", HERE / "attribution.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ATTR = _load_attribution()
BadInput = ATTR.InputError

# ------------------------------------------------------------------------------------------------
# Constants. Each names where it comes from; change it here or with the flag named.

# The ranking metric and the thin-read floor are the owner's, read from programme section 5 (template 0.1.2:
# "Ranking metric for performance reports [default cost per tracked order]" and "Tracked orders below which a
# creator's read is called thin [default 5]"). --rank-by and --min-orders replace them for one run only.
# Metric names as the programme may write them; longer phrases are matched first. Definitions: schemas.md
# section 12 (cost per tracked order, commission return on sales, new customer).
RANK_METRICS = OrderedDict([
    ("cost_per_tracked_order", ("cost per tracked order", "lower")),
    ("cost_per_new_customer", ("cost per new customer", "lower")),
    ("commission_return_on_sales", ("commission return on sales", "higher")),
    ("tracked_orders", ("tracked orders", "higher")),
    ("net_sales", ("net sales", "higher")),
    ("new_customers", ("new customers", "higher")),
])
# Build's choice: a creator is in the ranked set from the stage at which terms were agreed (schemas.md section 5).
ACTIVATED_STAGES = {"agreed", "onboarded", "briefed", "content_due", "content_submitted", "approved", "live", "closed"}
# Financial Status values that count as a sale: the same two commission-statement counts
# (shopify-affiliate-rails.md section 6 lists paid, authorized, refunded and so on).
STATUS_PAID, STATUS_PART_REFUNDED, STATUS_REFUNDED = "paid", "partially_refunded", "refunded"
# Exclusion reasons, tested in this order, the same order as commission-statement; each order gets the first.
REASONS = OrderedDict([
    ("test_order", "the onboarding test order (named in the creator's roster notes as test order <Name>)"),
    ("no_agreement_date", "not assessed: the creator has no agreement_date on the roster"),
    ("before_agreement", "dated before the creator's agreement_date"),
    ("status_unknown", "financial status unknown"),
    ("cancelled", "cancelled"),
    ("refunded", "fully refunded"),
    ("not_paid", "financial status not paid"),
    ("self_referral", "self-referral (the order email is the creator's)"),
    ("amount_unreadable", "sale amount unreadable"),
    ("refund_unknown", "partly refunded, amount unknown"),
])
COMMISSION_MODELS, FEE_MODELS = {"cpa", "hybrid"}, {"flat", "hybrid"}
MODELS = {"cpa", "flat", "hybrid", "gift", "none"}
LABEL_ORDER = ["Estimated", "User-provided", "Measured"]   # weakest first; a number takes its weakest input's label
REACH_SOURCES = {"screenshot": "User-provided", "public_counter": "User-provided",
                 "platform_export": "Measured", "estimate": "Estimated"}
COST_SOURCES = {"owner": "User-provided", "invoice": "User-provided", "rail": "User-provided", "estimate": "Estimated"}
# Orders-export columns, matched case-insensitively: schemas.md section 10 (first choice, fallback), names as
# listed in shopify-affiliate-rails.md section 6. "Discount Amount" and "Canceled at" are in that list too.
ORDER_COLUMNS = OrderedDict([
    ("order", (["name"], ["id"])),
    ("date", (["created at"], ["paid at"])),
    ("status", (["financial status"], [])),
    ("code", (["discount code"], [])),
    ("discount", (["discount amount"], [])),
    ("subtotal", (["subtotal"], ["total"])),
    ("refund", (["refunded amount"], [])),
    ("email", (["email"], ["customer id"])),
    ("cancelled", (["canceled at", "cancelled at"], [])),
    ("total", (["total"], [])),
])
COLUMN_LABEL = {"order": "Name", "date": "Created at", "status": "Financial Status", "code": "Discount Code",
                "discount": "Discount Amount", "subtotal": "Subtotal", "refund": "Refunded Amount",
                "email": "Email", "cancelled": "Canceled at", "total": "Total"}
OPTIONAL_COLUMNS = {"cancelled", "total"}
# Same recognition rule as commission-statement: an order identifier plus at least two known columns.
SIGNATURE = {"created at", "paid at", "financial status", "discount code", "subtotal", "total",
             "refunded amount", "email", "fulfillment status", "lineitem name"}
SIGNATURE_MIN = 2
DRAFT_MARKER = "<!-- performance-report draft: the script may regenerate this file until this line is deleted -->"

# schemas.md sections 4, 5 and 6 (2026-10-20); the roster skill's runtime copy is the one the pack enforces.
CREATORS_HEADER = ("creator_ref,display_name,primary_platform,primary_handle,profile_url,other_platforms,tier,"
                   "followers_primary,followers_as_of,engagement_rate_pct,engagement_as_of,niche_tags,"
                   "audience_fit_score,brand_safety_flag,contact_path,contact_email,status,compensation_model,"
                   "commission_rate_pct,flat_fee,code,affiliate_link,rail,agreement_date,agreement_file,"
                   "usage_rights_until,exclusivity_until,first_campaign,last_activity,notes").split(",")
PIPELINE_HEADER = ("campaign_slug,creator_ref,stage,stage_date,next_action,next_action_date,owner_role,"
                   "last_message_date,offer_summary,notes").split(",")
PUBLICATIONS_HEADER = ("publication_id,campaign_slug,creator_ref,platform,post_url,posted_at,format,disclosure_seen,"
                       "disclosure_form,code_in_post,link_in_post,approval_id,check_day1,check_day7,check_day30,"
                       "rights_until,notes").split(",")
# This skill's own input shapes (assets/costs-template.csv, assets/reach-template.csv), proposed for schemas.md.
COSTS_HEADER = "creator_ref,fee_paid,gift_units,gift_unit_cost,rail_app_fee,source,notes".split(",")
REACH_HEADER = "publication_id,creator_ref,views,reach,likes,source,observed_at,notes".split(",")
PERF_HEADER = (
    "campaign_slug,window_from,window_to,as_of,creator_ref,display_name,primary_platform,tier,compensation_model,"
    "commission_rate_pct,pipeline_stage,roster_status,"
    "tracked_orders,orders_by_code,orders_by_link,gross_sales,refunds,net_sales,new_customers,repeat_customers,"
    "orders_customer_unknown,orders_in_holdback,excluded_orders,excluded_detail,"
    "cost_commission,cost_fee,cost_gift,cost_rail_app_fee,cost_discount,cost_total,cost_label,cost_missing,"
    "cost_per_tracked_order,cost_per_new_customer,commission_return_on_sales,contribution_low_margin,"
    "contribution_high_margin,pays_back,cpo_vs_target,"
    "posts,posts_live_at_last_check,posts_removed,posts_edited,disclosure_yes,disclosure_partial,disclosure_no,"
    "disclosure_not_checked,disclosure_yes_pct,rights_active,rights_expired,rights_unknown,approval_attempts,"
    "rank_metric,rank,read,notes,reported_posts,views_reported,reach_reported,likes_reported,reported_label").split(",")

# Programme lines, found by section number and the template's own text (template 0.1.2, 2026-10-20: "never
# edit the template's text, because scripts find each line by it"). A line whose text was reworded is still
# read by its first words, with the value taken after its last colon.
PROGRAMME_FIELDS = OrderedDict([
    ("currency", (1, "Store currency", "Store currency:")),
    ("margin", (1, "Gross margin band", "Gross margin band (a range is fine; it sets the commission ceiling):")),
    ("model", (4, "Default model for new creators",
               "Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), "
               "`hybrid` (small fee plus commission), `gift` (product only). Default for this programme:")),
    ("rate", (4, "Commission rate for", "Commission rate for `cpa` and `hybrid`, percent of the commission basis:")),
    ("basis", (4, "Commission basis",
               "Commission basis: `subtotal after discounts, before shipping and tax` [default] or another:")),
    ("discount", (4, "Customer-facing discount",
                  "Customer-facing discount carried by each creator's code, percent or fixed amount:")),
    ("refund_mode", (4, "Partial refunds",
                     "Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to "
                     "the refunded share of the order:")),
    ("attribution", (5, "Attribution model",
                     "Attribution model, declared once: a matching code wins; a tracked link without a code is "
                     "second; nothing else is attributed [default]. Changes here change every report:")),
    ("holdback", (5, "Holdback before a sale",
                  "Holdback before a sale counts as commissionable, in days (refund window) [default 30]:")),
    ("selfref", (5, "Self-referral rule",
                 "Self-referral rule: an order placed by the creator, or shipped to the creator's own address, "
                 "does not earn commission [default]:")),
    ("rank_metric", (5, "Ranking metric for performance reports",
                     "Ranking metric for performance reports [default cost per tracked order]:")),
    ("thin", (5, "Tracked orders below which", "Tracked orders below which a creator's read is called thin [default 5]:")),
    ("promo_codes", (5, "Store promotion codes",
                     "Store promotion codes that are not creators' codes (so the unattributed list shows only unknown "
                     "codes), one per indented line:")),
])
# Indented instruction lines in template 0.1.2 that sit under a field the script reads. They are template text:
# a marked value may follow one on the same line, and only that value is read.
MARGIN_BASIS_TEXT = ("State whether the band is on list price or on net revenue; the pack's scripts read it as on list "
                     "price unless this says otherwise.")
INDENTED_INSTRUCTIONS = [MARGIN_BASIS_TEXT]
SOURCE_MARK_RE = re.compile(r"\[(owner|observed[^\]]*|default)\]", re.I)
# Pack defaults written into the template's labels, used only when the owner marked the line [default] with no value.
TEMPLATE_DEFAULTS = {"holdback": "30", "basis": "subtotal", "attribution": "code first, link second", "selfref": "applies",
                     "refund_mode": "full", "rank_metric": "cost per tracked order", "thin": "5"}

CENT, TENTH, ZERO, HUNDRED = Decimal("0.01"), Decimal("0.1"), Decimal("0"), Decimal("100")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
MARK_RE = re.compile(r"\[[^\]]*\]")
SLUG_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-[a-z0-9]+(?:-[a-z0-9]+)*$")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
UNUM_RE = re.compile(r"\d+(?:\.\d+)?")
# The roster's fixed notes entry for the onboarding test order (schemas.md section 4), as affiliate-onboarding's
# record script writes it: "test order #1001 is the brand's own and earns no commission".
TEST_ORDER_RE = re.compile(r"\btest order (#?[A-Za-z0-9][A-Za-z0-9\-]*)", re.I)   # same pattern as commission_statement.py
# Self-referral (schemas.md section 12): the rule is off only when the line's whole value, after the template text,
# is exactly one of these; a word inside a sentence ("earns no commission") leaves it on. Same list as
# commission-statement's reader; a change is made in both.
SELFREF_OFF_VALUES = {"off", "no", "none", "not applied", "does not apply", "disabled"}


# ------------------------------------------------------------------------------------------------
# Small helpers

def money(text):
    """Parse a money cell; None when empty or unreadable, never a silent zero."""
    s = re.sub(r"[^0-9.\-]", "", (text or "").strip())
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def fmt(d):
    return "" if d is None else "{:.2f}".format(d.quantize(CENT, rounding=ROUND_HALF_UP))


def pct(n, d):
    return None if not d else (Decimal(n) * HUNDRED / Decimal(d)).quantize(TENTH, rounding=ROUND_HALF_UP)


def ratio(n, d):
    return None if d is None or d == 0 or n is None else (n / d).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_date(text):
    m = DATE_RE.match((text or "").strip())
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def arg_date(text, flag):
    d = parse_date(text)
    if d is None or len(text.strip()) != 10:
        raise BadInput("{} must be a date written YYYY-MM-DD, not '{}'.".format(flag, text))
    return d


def norm_status(s):
    return re.sub(r"[\s\-]+", "_", (s or "").strip().lower())


def is_paid(o):
    return norm_status(o.get("status")) in (STATUS_PAID, STATUS_PART_REFUNDED) and not o.get("cancelled")


def customer_key(value, kind):
    v = (value or "").strip().lower()
    if not v:
        return None
    return hashlib.sha256("{}:{}".format(kind, v).encode("utf-8")).hexdigest()


def order_sort_key(o):
    digits = re.sub(r"\D", "", o["name"])
    return (o["date"], int(digits) if digits else 0, o["name"])


def weakest(labels):
    labels = [x for x in labels if x]
    return min(labels, key=LABEL_ORDER.index) if labels else ""


def months_between(a, b):
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append("{:04d}-{:02d}".format(y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# ------------------------------------------------------------------------------------------------
# Programme file

def read_programme(ws):
    path = ws / "program" / "program.md"
    if not path.exists():
        raise BadInput("program/program.md is not in the workspace; run program-setup first.")
    sections, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m:
            current = int(m.group(1))
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    for n in (1, 3, 4, 5):
        if n not in sections:
            raise BadInput("program/program.md has no section {} heading; restore the template headings.".format(n))
    values = {}
    for key, (sec, start, label) in PROGRAMME_FIELDS.items():
        values[key] = None
        lines = sections.get(sec, [])
        for i, line in enumerate(lines):
            if not line.startswith("- "):        # indented detail lines belong to the field above them
                continue
            body = line[2:].strip()
            if not body.lower().startswith(start.lower()):
                continue
            if body.startswith(label):
                raw = body[len(label):]
            else:
                cut = [m.end() for m in re.finditer(r":(?!//)", body)]
                raw = body[cut[-1]:] if cut else ""
            raw = raw.strip()
            tags = {t.strip("[]").split()[0].lower() for t in MARK_RE.findall(raw) if t.strip("[]").strip()}
            value = MARK_RE.sub("", raw).replace("`", "").strip().rstrip(".").strip()
            # A field's value is only what follows the template text on its own line, plus indented lines that carry
            # a source mark ([owner], [observed], [default]). Unmarked indented lines are the template's own
            # instructions and are ignored; a blank value or [open] counts as missing (lead's rule, 2026-10-20).
            detail = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("- ") or nxt.startswith("#") or (nxt.strip() and not nxt.startswith((" ", "\t"))):
                    break
                d = nxt.strip().lstrip("-").strip()
                if not SOURCE_MARK_RE.search(d) or "[open]" in d.lower():
                    continue
                for instruction in INDENTED_INSTRUCTIONS:
                    if d.startswith(instruction):
                        d = d[len(instruction):].strip()
                if MARK_RE.sub("", d).replace("`", "").strip():
                    detail.append(d)
            if "open" in tags and not detail:
                break
            if not value and "default" in tags and key in TEMPLATE_DEFAULTS:
                value = TEMPLATE_DEFAULTS[key]
            if value or detail:
                values[key] = {"raw": raw, "value": value, "tags": tags, "detail": detail}
            break
    values["_platforms"] = platform_table(sections.get(3, []))
    return values


def platform_table(lines):
    rows = OrderedDict()
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or not cells[0] or cells[0].lower() == "platform" or set(cells[0]) <= set("-: "):
            continue
        rows[cells[0].lower()] = MARK_RE.sub("", cells[1]).strip().lower()
    return rows


def organic_rule(platform, table):
    p = (platform or "").lower()
    alias = "podcasts" if p in ("podcast", "newsletter") else p
    for key, val in table.items():
        if key.split()[0] == alias:
            return val
    return table.get("other", "")


def programme_rules(prog, need_rate):
    r = {}
    v = prog.get("rate")
    m = NUM_RE.search(v["value"]) if v else None
    r["rate"] = Decimal(m.group(0)) if m else None
    if need_rate and r["rate"] is None:
        raise BadInput("program/program.md section 4 has no commission rate, and a ranked creator on a cpa or hybrid "
                       "deal has none on the roster; fill section 4 or the roster's commission_rate_pct.")
    b = prog.get("basis")
    if b is None:
        raise BadInput("program/program.md section 4 has no commission basis; fill the 'Commission basis' line.")
    bv = b["value"].lower()
    if "subtotal" in bv:
        r["basis"] = "subtotal"
    elif "total" in bv:
        r["basis"] = "total"
    else:
        raise BadInput("program/program.md section 4 commission basis '{}' is not one this script computes "
                       "(subtotal after discounts, or total).".format(b["value"]))
    a = prog.get("attribution")
    r["model"] = ATTR.read_model(a["value"] if a else "", a["tags"] if a else set())
    h = prog.get("holdback")
    m = NUM_RE.search(h["value"]) if h else None
    r["holdback"] = int(Decimal(m.group(0))) if m else None
    s = prog.get("selfref")
    if s is None or not s["value"]:
        raise BadInput("program/program.md section 5 has no value on the 'Self-referral rule' line; fill it with the "
                       "owner (the rule applies unless the value is off, no, none, not applied, does not apply or disabled).")
    r["selfref"] = re.sub(r"\s+", " ", s["value"].strip().lower()) not in SELFREF_OFF_VALUES
    mv = prog.get("model")
    mm = re.search(r"\b(cpa|flat|hybrid|gift|none)\b", mv["value"].lower()) if mv else None
    r["default_model"] = mm.group(1) if mm else None
    d = prog.get("discount")
    r["discount"] = None
    if d:
        dv, n = d["value"].lower(), NUM_RE.search(d["value"])
        if n and ("percent" in dv or "%" in dv or "pct" in dv):
            r["discount"] = ("percent", Decimal(n.group(0)))
        elif n and re.search(r"\b(usd|dollars?|fixed|[a-z]{3})\b", dv):
            r["discount"] = ("fixed", Decimal(n.group(0)))
    mg = prog.get("margin")
    r["margin"] = None
    if mg and mg["value"]:
        # A band may be written "60 to 70", "60-70" or "60–70" percent: split on the range word or dash and read
        # unsigned figures, so a hyphen is never a minus sign (review 3, F8).
        parts = [x for x in re.split(r"\s+to\s+|[-\u2013\u2014]", mg["value"]) if x.strip()]
        nums = [Decimal(m.group(0)) for x in parts for m in [UNUM_RE.search(x)] if m]
        ranged = bool(re.search(r"\s+to\s+|[-\u2013\u2014]", mg["value"]))
        if (ranged and len(nums) < 2) or not nums or any(not (ZERO < x < HUNDRED) for x in nums[:2]):
            raise BadInput("program/program.md section 1 gross margin band '{}' does not read as one or two percentages "
                           "between 0 and 100 (for example '60 to 70 percent').".format(mg["value"]))
        r["margin"] = (min(nums[:2]), max(nums[:2]))
    # schemas.md section 12: the margin is read on list price unless section 1's detail line says net revenue.
    basis_said = " ".join(MARK_RE.sub("", d).lower() for d in (mg["detail"] if mg else []))
    r["margin_basis"] = "net revenue" if "net revenue" in basis_said else "list price"
    rm = prog.get("refund_mode")
    r["refund_mode"] = "proportion" if rm and "proportion" in rm["value"].lower() else "full"
    rk = prog.get("rank_metric")
    r["rank_metric"] = None
    if rk and rk["value"]:
        v = rk["value"].lower()
        for key, (phrase, _) in sorted(RANK_METRICS.items(), key=lambda kv: -len(kv[1][0])):
            if phrase in v or phrase.rstrip("s") in v:
                r["rank_metric"] = key
                break
        if r["rank_metric"] is None:
            raise BadInput("program/program.md section 5 names a ranking metric this script does not compute ('{}'); "
                           "use one of: {}.".format(rk["value"], ", ".join(n for n, _ in RANK_METRICS.values())))
    th = prog.get("thin")
    m = re.search(r"\d+", th["value"]) if th and th["value"] else None
    r["thin"] = int(m.group(0)) if m else None
    # schemas.md section 10: a store promotion code is the first word before any colon on its line, on the field's
    # own line or a marked indented line ("WELCOME10: newsletter first-order offer [owner]").
    pc = prog.get("promo_codes")
    lines_ = ([pc["value"]] if pc and pc["value"] else []) + (pc["detail"] if pc else [])
    r["promo_codes"] = set()
    for d in lines_:
        head = MARK_RE.sub("", d).replace("`", "").split(":", 1)[0].split()
        if head:
            r["promo_codes"].add(head[0].upper())
    c = prog.get("currency")
    m = re.search(r"\b[A-Z]{3}\b", c["raw"]) if c else None
    r["currency"] = m.group(0) if m else "store currency"
    return r


# ------------------------------------------------------------------------------------------------
# Orders exports

def looks_like_orders(header_lower):
    return ("name" in header_lower or "id" in header_lower) and len(SIGNATURE & set(header_lower)) >= SIGNATURE_MIN


def read_orders_export(path, basis):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None) or []
        index = {}
        for i, h in enumerate(h.strip().lower() for h in header):
            index.setdefault(h, i)
        cols, missing, fallbacks = {}, [], []
        for key, (first, fallback) in ORDER_COLUMNS.items():
            if key == "subtotal" and basis == "total":
                first, fallback = ["total"], []
            hit = next((n for n in first if n in index), None)
            if hit is not None:
                cols[key] = index[hit]
                continue
            alt = next((n for n in fallback if n in index), None)
            if alt is not None:
                cols[key] = index[alt]
                fallbacks.append((key, alt))
            elif key not in OPTIONAL_COLUMNS:
                missing.append(key)
        if "order" not in cols or "date" not in cols:
            raise BadInput("{} has no order identifier (Name or Id) or no order date (Created at or Paid at); "
                           "export the orders again from the Shopify admin.".format(path.name))
        email_kind = "id" if ("email", "customer id") in fallbacks else "email"
        orders, rows, no_id = OrderedDict(), 0, 0
        for row in reader:
            if not any(c.strip() for c in row):
                continue
            rows += 1
            ident = row[cols["order"]].strip() if cols["order"] < len(row) else ""
            if not ident:
                no_id += 1
                continue
            key_ = ATTR.norm_order(ident)
            if key_ in orders:
                # schemas.md section 10 (pack rule until a real export settles it): order-level cells come from the
                # first row of each order; later line-item rows are ignored for order-level values.
                orders[key_]["_rows"] += 1
                continue
            o = orders[key_] = {"name": ident, "file": path.name, "_rows": 1}
            for key, i in cols.items():
                if key == "order" or i >= len(row):
                    continue
                v = row[i].strip()
                if v:
                    o[key] = v
        for o in orders.values():
            o["_has_discount"] = "discount" in cols
            o["_has_refund"] = "refund" in cols
            o["_has_status"] = "status" in cols
            o["_cust"] = customer_key(o.get("email"), email_kind)
    return {"path": path, "cols": cols, "missing": missing, "fallbacks": fallbacks, "orders": orders,
            "rows": rows, "no_id": no_id}


def classify(o, creator, rules, creator_hash, test_orders):
    """Return (reason, sale, refund). reason is '' for a tracked order, else a key of REASONS."""
    # schemas.md sections 4 and 12: the onboarding test order, named in the roster's notes as "test order <Name>",
    # is the brand's own and is never a tracked order.
    if ATTR.norm_order(o["name"]) in test_orders:
        return "test_order", None, None
    # schemas.md section 12: a tracked order is dated on or after the creator's agreement_date; an order before
    # it, or a creator with none, is excluded from the ranking as from commission and listed under exclusions.
    agreement = parse_date(creator["agreement_date"])
    if agreement is None:
        return "no_agreement_date", None, None
    if o["date"] < agreement:
        return "before_agreement", None, None
    status = norm_status(o.get("status"))
    if not status:
        return "status_unknown", None, None
    if o.get("cancelled"):
        return "cancelled", None, None
    if status == STATUS_REFUNDED:
        return "refunded", None, None
    if status not in (STATUS_PAID, STATUS_PART_REFUNDED):
        return "not_paid", None, None
    if rules["selfref"] and creator_hash and o["_cust"] == creator_hash:
        return "self_referral", None, None
    sale = money(o.get("subtotal"))
    if sale is None:
        return "amount_unreadable", None, None
    if status == STATUS_PART_REFUNDED and not o["_has_refund"]:
        return "refund_unknown", None, None
    refund = money(o.get("refund")) if o.get("refund") else ZERO
    if refund is None:
        return "refund_unknown", None, None
    # schemas.md section 12 and programme section 4: the refunded amount comes off the basis in full, or in
    # proportion to the refunded share of the order's Total when section 4 says so; never below zero.
    if rules["refund_mode"] == "proportion" and refund > ZERO:
        total = money(o.get("total"))
        if total is None or total <= ZERO:
            return "refund_unknown", None, None
        refund = sale * min(refund / total, Decimal(1))
    refund = min(max(refund, ZERO), sale).quantize(CENT, rounding=ROUND_HALF_UP)
    # schemas.md section 12: an order refunded to nothing stays a tracked order with a zero basis (as in
    # commission-statement); the row notes how many.
    return "", sale, refund


# ------------------------------------------------------------------------------------------------
# The run

def new_stats(r, stage):
    return {"r": r, "stage": stage, "tracked": 0, "code": 0, "link": 0, "gross": ZERO, "refunds": ZERO,
            "discount": ZERO, "discount_est": False, "discount_missing": False, "new": set(), "repeat": set(),
            "cust_unknown": 0, "holdback": 0, "excluded": OrderedDict(), "posts": [], "notes": [],
            "approvals": 0, "reach": [], "zero_basis": 0}


def run(a):
    ws = pathlib.Path(a.workspace)
    if not ws.is_dir():
        raise BadInput("the workspace folder {} does not exist.".format(a.workspace))
    as_of = arg_date(a.as_of, "--as-of") if a.as_of else dt.datetime.now(dt.timezone.utc).date()
    slug = a.campaign.strip()
    if not SLUG_RE.match(slug):
        raise BadInput("--campaign '{}' is not a campaign slug (lowercase, starting YYYY-MM-, for example "
                       "2026-12-holiday-tote).".format(slug))
    target = None
    if a.target_cpo is not None:
        target = money(a.target_cpo)
        if target is None or target <= ZERO:
            raise BadInput("--target-cpo must be a positive amount in the store currency, for example 12.50.")

    used, missing, cannot, fine, partial = [], [], [], [], []
    prog = read_programme(ws)

    # --- roster, pipeline, publications
    cpath = ws / "data" / "creators.csv"
    if not cpath.exists():
        raise BadInput("data/creators.csv is not in the workspace; set up the roster with creator-roster first.")
    creators = OrderedDict((r["creator_ref"], r) for r in ATTR.read_exact(cpath, CREATORS_HEADER, "data/creators.csv"))
    used.append("data/creators.csv ({} rows)".format(len(creators)))
    ppath, pubpath = ws / "data" / "pipeline.csv", ws / "data" / "publications.csv"
    pipeline = ATTR.read_exact(ppath, PIPELINE_HEADER, "data/pipeline.csv") if ppath.exists() else None
    pubs = ATTR.read_exact(pubpath, PUBLICATIONS_HEADER, "data/publications.csv") if pubpath.exists() else None

    known = set()
    for rows in (pipeline or [], pubs or []):
        known |= {r["campaign_slug"] for r in rows}
    if (ws / "campaigns").is_dir():
        known |= {p.name for p in (ws / "campaigns").iterdir() if p.is_dir()}
    if slug not in known:
        listed = ", ".join(sorted(k for k in known if k)) or "none"
        raise BadInput("campaign {} is not found in campaigns/, data/pipeline.csv or data/publications.csv; check "
                       "the slug (known campaigns: {}).".format(slug, listed))

    stages, not_activated, other_campaigns = OrderedDict(), OrderedDict(), {}
    for r in pipeline or []:
        if r["campaign_slug"] == slug:
            (stages if r["stage"] in ACTIVATED_STAGES else not_activated)[r["creator_ref"]] = r["stage"]
        else:
            other_campaigns.setdefault(r["creator_ref"], set()).add(r["campaign_slug"])
    camp_pubs = [p for p in (pubs or []) if p["campaign_slug"] == slug]
    for p in camp_pubs:
        stages.setdefault(p["creator_ref"], "")
        not_activated.pop(p["creator_ref"], None)
    for ref in list(stages) + list(not_activated):
        if ref not in creators:
            raise BadInput("{} appears for campaign {} but is not in data/creators.csv; run creator-roster check "
                           "and fix the row.".format(ref, slug))
    # schemas.md section 4: a duplicate retired by a merge stays ended with a "merged into c-xxxxxx" note and is
    # never counted. Its rows are listed apart, not ranked.
    merged = OrderedDict()
    for ref in list(stages):
        r = creators[ref]
        m = re.search(r"merged into (c-[a-z0-9]{6})", r["notes"])
        if r["status"] == "ended" and m:
            merged[ref] = m.group(1)
            del stages[ref]
            not_activated.pop(ref, None)
    if merged:
        cannot.append("rows of merged duplicates, never counted: {}".format(
            ", ".join("{} (merged into {})".format(k, v) for k, v in merged.items())))
    if not stages:
        raise BadInput("campaign {} has no creator at stage agreed or later in data/pipeline.csv and no publication; "
                       "there is nothing to report yet.".format(slug))
    if pipeline is None:
        missing.append("data/pipeline.csv")
        partial.append("data/pipeline.csv is absent, so creators who agreed but never posted cannot be listed")
    else:
        used.append("data/pipeline.csv ({} rows for {})".format(sum(1 for r in pipeline if r["campaign_slug"] == slug), slug))
    if pubs is None:
        missing.append("data/publications.csv")
        partial.append("data/publications.csv is absent, so posts, disclosure and rights are not counted")

    # --- deal rules
    need_rate = False
    for ref in stages:
        r = creators[ref]
        model = (r["compensation_model"].strip().lower() or None)
        r["_model_source"] = "roster"
        if model is None:
            r["_model_source"] = "programme section 4 default"
        r["_model"] = model
        if model is not None and model not in MODELS:
            raise BadInput("{} has compensation_model '{}', which is not one of {}.".format(ref, model, ", ".join(sorted(MODELS))))
    rules = programme_rules(prog, need_rate=False)
    for ref in stages:
        r = creators[ref]
        if r["_model"] is None:
            if rules["default_model"] is None:
                raise BadInput("{} has no compensation_model on the roster and program/program.md section 4 names no "
                               "default model; fill one of them.".format(ref))
            r["_model"] = rules["default_model"]
        if r["_model"] in COMMISSION_MODELS and not r["commission_rate_pct"] and rules["rate"] is None:
            need_rate = True
        rate = money(r["commission_rate_pct"]) if r["commission_rate_pct"] else rules["rate"]
        if r["commission_rate_pct"] and rate is None:
            raise BadInput("{} has an unreadable commission_rate_pct '{}'.".format(ref, r["commission_rate_pct"]))
        if rate is not None and not (ZERO <= rate <= HUNDRED):
            raise BadInput("{} has a commission rate of {} percent; a rate is between 0 and 100.".format(ref, rate))
        r["_rate"] = rate if r["_model"] in COMMISSION_MODELS else None
    if need_rate:
        programme_rules(prog, need_rate=True)   # raises with the section 4 message
    used.append("program/program.md sections 1, 3, 4, 5")
    if a.rank_by:
        a.metric_source = "--rank-by for this run, as declared by {}".format(a.rank_by_source)
    elif rules["rank_metric"]:
        a.rank_by = rules["rank_metric"]
        a.metric_source = "programme section 5"
    else:
        raise BadInput("program/program.md section 5 has no ranking metric for performance reports; fill that line "
                       "with the owner, or pass --rank-by for this run with --rank-by-source naming who chose it.")
    if a.min_orders is not None:
        if a.min_orders < 1:
            raise BadInput("--min-orders must be 1 or more.")
        a.thin_source = "--min-orders for this run"
    elif rules["thin"]:
        a.min_orders, a.thin_source = rules["thin"], "programme section 5"
    else:
        raise BadInput("program/program.md section 5 has no number of tracked orders below which a read is called "
                       "thin; fill that line with the owner, or pass --min-orders for this run.")
    if rules["holdback"] is None:
        missing.append("programme section 5 holdback")
        cannot.append("which orders are still inside the refund window (section 5 holdback is not set)")
    if rules["margin"] is None:
        missing.append("programme section 1 gross margin band")
        cannot.append("contribution after programme cost (no margin band in section 1)")

    # --- window
    pub_dates = [parse_date(p["posted_at"]) for p in camp_pubs if parse_date(p["posted_at"])]
    if a.date_from:
        w_from = arg_date(a.date_from, "--from")
    elif pub_dates:
        w_from = min(pub_dates)
    else:
        raise BadInput("campaign {} has no dated publication to start the window from; pass --from and --to.".format(slug))
    w_to = arg_date(a.date_to, "--to") if a.date_to else as_of
    if w_from > w_to:
        raise BadInput("--from {} is after --to {}.".format(w_from, w_to))
    if w_to > as_of:
        raise BadInput("--to {} is after --as-of {}; a report cannot cover days that have not happened.".format(w_to, as_of))

    # --- codes and links
    plans = sorted((ws / "codes").glob("code-plan-*.csv")) if (ws / "codes").is_dir() else []
    code_owner = ATTR.build_code_map(creators, plans)
    if plans:
        used.append("codes/ ({} code plan file{})".format(len(plans), "" if len(plans) == 1 else "s"))
    months = months_between(w_from, w_to)
    link_paths = [ws / "exports" / "link-attribution-{}.csv".format(m) for m in months]
    present = [p for p in link_paths if p.exists()]
    absent = [m for m, p in zip(months, link_paths) if not p.exists()]
    # schemas.md section 10: a missing month makes the run partial only when an active creator holds a link and
    # some order in that month carries no active creator's code (so a link could have attributed it).
    links_issued = any(r["affiliate_link"] and r["status"] == "active" for r in creators.values())
    links, link_notes = {}, {"rows": 0, "conflict": [], "not_active": [], "bad_source": 0, "files": []}
    link_check_months = []
    if rules["model"] == ATTR.CODE_ONLY:
        link_state = "not used: programme section 5 attributes codes only"
    else:
        links, link_notes = ATTR.load_links(present, creators)
        if present:
            used.append("link attribution: {} ({} rows)".format(", ".join("exports/" + p.name for p in present), link_notes["rows"]))
        link_state = "present for {}".format(", ".join(m for m in months if m not in absent)) if present else "absent"
        if absent:
            missing.append("link attribution for {}".format(", ".join(absent)))
            link_state += ("; " if present else ": ") + "no file for {}, so only codes attribute there".format(", ".join(absent))
            link_check_months = absent if links_issued else []
        if link_notes["bad_source"]:
            cannot.append("{} link rows with a source outside collabs, app, api, manual".format(link_notes["bad_source"]))

    # --- orders exports
    if a.export:
        files = []
        for e in a.export:
            p = pathlib.Path(e)
            p = p if p.is_absolute() else ws / e
            if not p.exists():
                raise BadInput("--export {} does not exist in the workspace.".format(e))
            files.append(p)
    else:
        ex = ws / "exports"
        if not ex.is_dir():
            raise BadInput("exports/ is not in the workspace; save the Shopify orders export there.")
        files = sorted(p for p in ex.glob("*.csv") if not p.name.startswith("link-attribution-"))
    exports = []
    for p in files:
        with p.open(newline="", encoding="utf-8-sig") as f:
            head = [h.strip().lower() for h in (next(csv.reader(f), None) or [])]
        if not looks_like_orders(head):
            if a.export:
                raise BadInput("{} does not look like a Shopify orders export (no Name or Id column with the usual "
                               "order columns).".format(p.name))
            continue
        exports.append(read_orders_export(p, rules["basis"]))
    if not exports:
        raise BadInput("no Shopify orders export was found in exports/; export the orders for {} to {} from the "
                       "Shopify admin and save the CSV there.".format(w_from, w_to))
    all_orders, conflicts_dup, dup_same = OrderedDict(), [], 0
    for e in exports:
        name = e["path"].name
        for k in e["missing"]:
            missing.append("{} column in {}".format(COLUMN_LABEL[k], name))
        if ("email", "customer id") in e["fallbacks"]:
            cannot.append("self-referral in {} (it carries Customer Id, not Email, and the roster holds emails)".format(name))
        for k, alt in e["fallbacks"]:
            note = " (Total includes shipping and tax, so sales are overstated)" if k == "subtotal" else ""
            missing.append("{} column in {}; used {} instead{}".format(COLUMN_LABEL[k], name, alt.title(), note))
        if "status" in e["missing"]:
            partial.append("{} has no Financial Status column, so its orders cannot be counted as sales".format(name))
        if "code" in e["missing"]:
            partial.append("{} has no Discount Code column, so no order in it attributes by code".format(name))
        if "subtotal" in e["missing"]:
            partial.append("{} has no Subtotal or Total column, so no sale amount can be read".format(name))
        if "refund" in e["missing"]:
            partial.append("{} has no Refunded Amount column, so partly refunded orders cannot be valued".format(name))
        if "email" in e["missing"]:
            partial.append("{} has no Email or Customer Id column, so new and repeat customers cannot be told apart and "
                           "self-referral cannot be checked".format(name))
        if e["no_id"]:
            partial.append("{}: {} rows without an order identifier were not read".format(name, e["no_id"]))
        used.append("exports/{} ({} rows, {} orders)".format(name, e["rows"], len(e["orders"])))
        for key, o in e["orders"].items():
            if key in all_orders:
                prev = all_orders[key]
                if any((prev.get(f) or "") != (o.get(f) or "") for f in ("status", "subtotal", "refund", "code")):
                    conflicts_dup.append(o["name"])
                else:
                    dup_same += 1
                continue
            all_orders[key] = o
    if not any("cancelled" in e["cols"] for e in exports):
        cannot.append("cancellations other than by financial status (no Canceled at column)")
    if conflicts_dup:
        partial.append("{} orders appear in two exports with different values ({}); the first file's values were used, "
                       "so pass only the latest export with --export".format(len(conflicts_dup), ", ".join(conflicts_dup[:5])))
    elif len(exports) > 1:
        fine.append("orders found in more than one export carried the same values ({} repeated)".format(dup_same))

    unreadable = 0
    dated = []
    for o in all_orders.values():
        o["date"] = parse_date(o.get("date"))
        if o["date"] is None:
            unreadable += 1
        else:
            dated.append(o)
    if unreadable:
        partial.append("{} orders have no readable order date and were left out".format(unreadable))
    # schemas.md section 12: a new customer is a hashed customer whose first paid order in the exports supplied
    # falls inside the window; repeat otherwise. "Paid" is the payment state a tracked order needs.
    first_paid = {}
    for o in sorted(dated, key=order_sort_key):
        if o["_cust"] and o["_cust"] not in first_paid and is_paid(o):
            first_paid[o["_cust"]] = o["date"]
    earliest = min((o["date"] for o in dated), default=None)
    if earliest is not None and earliest >= w_from:
        cannot.append("whether a customer had a paid order before {} (the exports start there, so every customer whose "
                      "first paid order is in the window counts as new)".format(earliest))

    # --- costs and reach inputs
    costs_path, reach_path = ws / "campaigns" / slug / "costs.csv", ws / "campaigns" / slug / "reach.csv"
    costs = OrderedDict()
    if costs_path.exists():
        for row in ATTR.read_exact(costs_path, COSTS_HEADER, "campaigns/{}/costs.csv".format(slug)):
            if row["source"] and row["source"].lower() not in COST_SOURCES:
                raise BadInput("campaigns/{}/costs.csv has source '{}' for {}; use owner, invoice, rail or "
                               "estimate.".format(slug, row["source"], row["creator_ref"]))
            for col in ("fee_paid", "gift_unit_cost", "rail_app_fee"):
                if row[col] and money(row[col]) is None:
                    raise BadInput("campaigns/{}/costs.csv has an unreadable {} '{}' for {}.".format(slug, col, row[col], row["creator_ref"]))
            if row["gift_units"] and not row["gift_units"].isdigit():
                raise BadInput("campaigns/{}/costs.csv gift_units must be a whole number for {}.".format(slug, row["creator_ref"]))
            costs[row["creator_ref"]] = row
        used.append("campaigns/{}/costs.csv ({} rows)".format(slug, len(costs)))
    else:
        missing.append("campaigns/{}/costs.csv".format(slug))
    reach_rows = []
    if reach_path.exists():
        reach_rows = ATTR.read_exact(reach_path, REACH_HEADER, "campaigns/{}/reach.csv".format(slug))
        used.append("campaigns/{}/reach.csv ({} rows; reported apart, never ranked)".format(slug, len(reach_rows)))
    else:
        missing.append("campaigns/{}/reach.csv (reach not reported; optional)".format(slug))

    # --- attribute every order in the window
    stats = OrderedDict((ref, new_stats(creators[ref], stages[ref])) for ref in stages)
    creator_hash = {ref: customer_key(creators[ref]["contact_email"], "email") for ref in stages}
    test_orders = {ATTR.norm_order(m) for r in creators.values() for m in TEST_ORDER_RE.findall(r["notes"])}
    unattributed, promos, outside, code_conflicts, overridden = OrderedDict(), OrderedDict(), OrderedDict(), [], []
    uncoded_months = set()
    store = {"orders": 0, "paid": 0}
    for o in sorted((o for o in dated if w_from <= o["date"] <= w_to), key=order_sort_key):
        store["orders"] += 1
        if is_paid(o):
            store["paid"] += 1
        if not any(c in code_owner and creators[code_owner[c][0]]["status"] == "active" for c in ATTR.split_codes(o.get("code"))):
            uncoded_months.add(o["date"].strftime("%Y-%m"))
        att = ATTR.attribute(o["name"], o.get("code"), code_owner, creators, links, rules["model"])
        if att["conflict"]:
            code_conflicts.append("{} ({})".format(o["name"], ", ".join(att["conflict"])))
            continue
        ref = att["creator_ref"]
        if ref is None:
            for code, owner in att["unmatched"]:
                # programme section 5 lists the store's own promotion codes; they are counted apart.
                book = promos if code in rules["promo_codes"] and not owner else unattributed
                u = book.setdefault(code, {"orders": 0, "sales": ZERO, "owner": owner})
                u["orders"] += 1
                u["sales"] += money(o.get("subtotal")) or ZERO
            continue
        if ref not in stats:
            outside[ref] = outside.get(ref, 0) + 1
            continue
        s = stats[ref]
        if att["link_overridden"]:
            overridden.append("{} (code {}, link {})".format(o["name"], ref, att["link_overridden"]))
        reason, sale, refund = classify(o, creators[ref], rules, creator_hash[ref], test_orders)
        if reason:
            s["excluded"][reason] = s["excluded"].get(reason, 0) + 1
            continue
        s["tracked"] += 1
        s[att["method"]] += 1
        s["gross"] += sale
        s["refunds"] += refund
        if sale - refund <= ZERO:
            s["zero_basis"] += 1
        disc = money(o.get("discount")) if o["_has_discount"] else None
        if o["_has_discount"]:
            s["discount"] += disc or ZERO
        elif att["method"] == "code" and rules["discount"]:
            kind, val = rules["discount"]
            s["discount"] += (sale * val / (HUNDRED - val)) if kind == "percent" and val < HUNDRED else (val if kind == "fixed" else ZERO)
            s["discount_est"] = True
        elif att["method"] == "code":
            s["discount_missing"] = True
        if rules["holdback"] is not None and as_of < o["date"] + dt.timedelta(days=rules["holdback"]):
            s["holdback"] += 1
        if o["_cust"] is None:
            s["cust_unknown"] += 1
        elif w_from <= first_paid.get(o["_cust"], o["date"]) <= w_to:
            s["new"].add(o["_cust"])
        else:
            s["repeat"].add(o["_cust"])
    if any(s["discount_est"] for s in stats.values()):
        missing.append("Discount Amount column; the discount given was estimated from programme section 4")
    if any(s["discount_missing"] for s in stats.values()):
        partial.append("the discount given is unknown for some code orders (no Discount Amount column and no "
                       "customer discount in programme section 4)")

    # --- publications, approvals, reach
    platforms = prog["_platforms"]
    pub_ids = {}
    posts_no_date = 0
    for p in camp_pubs:
        d = parse_date(p["posted_at"])
        if d is None:
            posts_no_date += 1
        elif not (w_from <= d <= w_to):
            continue
        if p["creator_ref"] in stats:
            stats[p["creator_ref"]]["posts"].append(p)
            pub_ids[p["publication_id"]] = p["creator_ref"]
    if posts_no_date:
        cannot.append("the window for {} publications with no readable posted_at (counted as in the window)".format(posts_no_date))
    adir = ws / "campaigns" / slug / "approvals"
    if adir.is_dir():
        for f in adir.glob("*.md"):
            parts = f.stem.split("--")
            if len(parts) == 3 and parts[0] == slug and parts[1] in stats:
                stats[parts[1]]["approvals"] += 1
        used.append("campaigns/{}/approvals/ (file names counted)".format(slug))
    reach_unknown = []
    for row in reach_rows:
        src = row["source"].strip().lower()
        if src not in REACH_SOURCES:
            raise BadInput("campaigns/{}/reach.csv source '{}' on {}; use screenshot, public_counter, platform_export "
                           "or estimate.".format(slug, row["source"], row["publication_id"]))
        for col in ("views", "reach", "likes"):
            if row[col] and not row[col].isdigit():
                raise BadInput("campaigns/{}/reach.csv {} must be a whole number on {}.".format(slug, col, row["publication_id"]))
        ref = pub_ids.get(row["publication_id"])
        if ref is None or ref != row["creator_ref"]:
            reach_unknown.append(row["publication_id"])
            continue
        stats[ref]["reach"].append(row)
    if reach_unknown:
        cannot.append("reach rows for publications not in this campaign's window or with a different creator_ref ({}); "
                      "left out".format(", ".join(reach_unknown)))

    # --- per creator figures
    margin = rules["margin"]
    out_rows = []
    for ref, s in stats.items():
        r = s["r"]
        model = r["_model"]
        net = s["gross"] - s["refunds"]
        notes = []
        commission = (net * r["_rate"] / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) if model in COMMISSION_MODELS else ZERO
        labels, cost_missing = ["Measured"], []
        c = costs.get(ref)
        src_label = COST_SOURCES.get((c["source"] or "owner").lower(), "User-provided") if c else ""
        # schemas.md section 12, programme cost: commission due, flat fees paid, gifted units at the costs.csv unit
        # cost, the discount given, and any rail or app fee recorded in costs.csv. A fee is counted only as paid.
        fee = ZERO
        if c and c["fee_paid"]:
            fee = money(c["fee_paid"])
            labels.append(src_label)
        elif model in FEE_MODELS:
            fee = None
            cost_missing.append("fee")
            if r["flat_fee"]:
                notes.append("fee paid not in costs.csv (the roster's flat_fee is {} per deliverable set; not counted)".format(r["flat_fee"]))
        gift = None
        if c and c["gift_units"] == "0":
            gift = ZERO
            labels.append(src_label)
        elif c and c["gift_units"] and c["gift_unit_cost"]:
            gift = Decimal(c["gift_units"]) * money(c["gift_unit_cost"])
            labels.append(src_label)
        else:
            cost_missing.append("gift")
        other = money(c["rail_app_fee"]) if c and c["rail_app_fee"] else ZERO
        if c and c["rail_app_fee"]:
            labels.append(src_label)
        discount = s["discount"].quantize(CENT, rounding=ROUND_HALF_UP)
        if s["discount_est"]:
            labels.append("Estimated")
        if s["discount_missing"]:
            cost_missing.append("discount")
        total = commission + (fee or ZERO) + (gift or ZERO) + other + discount
        new_n = len(s["new"])
        repeat_n = len(s["repeat"] - s["new"])
        cpo = ratio(total, Decimal(s["tracked"])) if s["tracked"] else None
        cpnc = ratio(total, Decimal(new_n)) if new_n else None
        spc = ratio(net, total) if total > ZERO else None
        contrib = [None, None]
        pays = ""
        if margin:
            creator_cost = commission + (fee or ZERO) + (gift or ZERO) + other
            # Cost of goods at the margin band: on list price (net sales plus discount given) by default, or on
            # net sales when section 1 says the band is on net revenue (schemas.md section 12).
            goods_base = net if rules["margin_basis"] == "net revenue" else net + discount
            contrib = [(net - goods_base * (HUNDRED - m) / HUNDRED - creator_cost).quantize(CENT, rounding=ROUND_HALF_UP)
                       for m in margin]
            if total == ZERO and s["tracked"] == 0:
                pays = "no_activity"
            elif contrib[0] > ZERO:
                pays = "both"
            elif contrib[1] > ZERO:
                pays = "high_only"
            else:
                pays = "neither"
        vs_target = ""
        if target is not None and cpo is not None:
            vs_target = "at_or_below" if cpo <= target else "above"
        read = "none" if s["tracked"] == 0 else ("thin" if s["tracked"] < a.min_orders else "ok")

        live = removed = edited = 0
        disc_counts = {"yes": 0, "partial": 0, "no": 0, "": 0}
        rights = {"active": 0, "expired": 0, "unknown": 0}
        for p in s["posts"]:
            checks = [p["check_day30"], p["check_day7"], p["check_day1"]]
            last = next((x for x in checks if x in ("live", "removed", "edited")), "")
            live += last in ("live", "edited")
            removed += last == "removed"
            edited += "edited" in checks
            ds = p["disclosure_seen"] if p["disclosure_seen"] in ("yes", "partial", "no") else ""
            disc_counts[ds] += 1
            ru = parse_date(p["rights_until"])
            rights["unknown" if ru is None else ("active" if ru >= as_of else "expired")] += 1
            rule = organic_rule(p["platform"], platforms)
            if rule.startswith("no"):
                notes.append("{} posted on {}, which programme section 3 rules out for organic creator posts".format(
                    p["publication_id"], p["platform"]))
            elif not rule or rule.startswith("unknown"):
                notes.append("{} posted on {}, which programme section 3 leaves unknown".format(p["publication_id"], p["platform"]))
        checked = disc_counts["yes"] + disc_counts["partial"] + disc_counts["no"]
        if s["zero_basis"]:
            notes.append("{} tracked order{} refunded to nothing, counted with a zero basis".format(
                s["zero_basis"], "" if s["zero_basis"] == 1 else "s"))
        if not r["code"]:
            notes.append("no code on the roster")
        if not s["posts"]:
            notes.append("no post recorded in the window")
        if r["status"] != "active":
            notes.append("roster status {}: its code and link do not attribute".format(r["status"] or "empty"))
        if not r["agreement_date"]:
            notes.append("agreement_date empty: orders not checked against it")
        for other_slug in sorted(other_campaigns.get(ref, ())):
            notes.append("also in campaign {}".format(other_slug))
        views = [int(x["views"]) for x in s["reach"] if x["views"]]
        reach = [int(x["reach"]) for x in s["reach"] if x["reach"]]
        likes = [int(x["likes"]) for x in s["reach"] if x["likes"]]
        rlabel = weakest([REACH_SOURCES[x["source"].strip().lower()] for x in s["reach"]])
        s.update({"net": net, "commission": commission, "fee": fee, "gift": gift, "other": other, "discount_q": discount,
                  "total": total, "cpo": cpo, "cpnc": cpnc, "spc": spc, "contrib": contrib, "pays": pays,
                  "cost_label": weakest(labels), "cost_missing": cost_missing, "new_n": new_n, "repeat_n": repeat_n,
                  "read": read, "vs_target": vs_target, "live": live, "removed": removed, "edited": edited,
                  "disc": disc_counts, "disc_pct": pct(disc_counts["yes"], checked), "rights": rights,
                  "notes": notes, "views": sum(views) if views else None, "reach_sum": sum(reach) if reach else None,
                  "likes": sum(likes) if likes else None, "rlabel": rlabel})
        if cost_missing:
            partial.append("{}: cost leaves out {} (add it to campaigns/{}/costs.csv)".format(ref, " and ".join(cost_missing), slug))
        out_rows.append(s)

    gap = [m for m in link_check_months if m in uncoded_months]
    if gap:
        partial.append("an active creator holds a tracked link but exports/link-attribution file is missing for {}, where "
                       "some orders carry no active creator's code, so link-only orders there are not counted".format(", ".join(gap)))
    elif link_check_months:
        fine.append("no link file for {}, but every order there carries an active creator's code, so no link could have "
                    "attributed one".format(", ".join(link_check_months)))
    unassessed = [s["r"]["creator_ref"] for s in out_rows if s["excluded"].get("no_agreement_date")]
    if unassessed:
        partial.append("orders for {} were not assessed because the roster has no agreement_date for them; fill it with "
                       "creator-roster".format(", ".join(unassessed)))

    # --- ranking: the declared metric; creators with no value for it are ranked after the rest, never dropped
    metric = a.rank_by
    mname, direction = RANK_METRICS[metric]
    value_of = {"cost_per_tracked_order": lambda s: s["cpo"], "cost_per_new_customer": lambda s: s["cpnc"],
                "tracked_orders": lambda s: Decimal(s["tracked"]), "net_sales": lambda s: s["net"],
                "commission_return_on_sales": lambda s: s["spc"],
                "new_customers": lambda s: Decimal(s["new_n"])}[metric]

    def key(s):
        v = value_of(s)
        primary = (1, ZERO) if v is None else (0, v if direction == "lower" else -v)
        return (primary, -s["tracked"], s["total"], s["r"]["creator_ref"])
    for i, s in enumerate(sorted(out_rows, key=key), start=1):
        s["rank"] = i
        if value_of(s) is None:
            s["notes"].insert(0, "no value for the ranking metric: ranked after the creators who have one, by programme cost")

    # --- totals
    T = {"tracked": sum(s["tracked"] for s in out_rows), "code": sum(s["code"] for s in out_rows),
         "link": sum(s["link"] for s in out_rows), "gross": sum((s["gross"] for s in out_rows), ZERO),
         "refunds": sum((s["refunds"] for s in out_rows), ZERO), "net": sum((s["net"] for s in out_rows), ZERO),
         "commission": sum((s["commission"] for s in out_rows), ZERO), "fee": sum((s["fee"] or ZERO for s in out_rows), ZERO),
         "gift": sum((s["gift"] or ZERO for s in out_rows), ZERO), "other": sum((s["other"] for s in out_rows), ZERO),
         "discount_q": sum((s["discount_q"] for s in out_rows), ZERO), "total": sum((s["total"] for s in out_rows), ZERO),
         "holdback": sum(s["holdback"] for s in out_rows), "cust_unknown": sum(s["cust_unknown"] for s in out_rows)}
    new_all = set().union(*[s["new"] for s in out_rows])
    T["new_n"] = len(new_all)
    T["repeat_n"] = len(set().union(*[s["repeat"] for s in out_rows]) - new_all)
    T["cpo"] = ratio(T["total"], Decimal(T["tracked"])) if T["tracked"] else None
    T["cpnc"] = ratio(T["total"], Decimal(T["new_n"])) if T["new_n"] else None
    T["spc"] = ratio(T["net"], T["total"]) if T["total"] > ZERO else None
    T["contrib"] = [sum((s["contrib"][i] for s in out_rows), ZERO) if margin else None for i in (0, 1)]
    T["excluded"] = OrderedDict()
    for s in out_rows:
        for k, n in s["excluded"].items():
            T["excluded"][k] = T["excluded"].get(k, 0) + n
    for f in ("live", "removed", "edited"):
        T[f] = sum(s[f] for s in out_rows)
    T["posts"] = sum(len(s["posts"]) for s in out_rows)
    T["disc"] = {k: sum(s["disc"][k] for s in out_rows) for k in ("yes", "partial", "no", "")}
    T["disc_pct"] = pct(T["disc"]["yes"], T["disc"]["yes"] + T["disc"]["partial"] + T["disc"]["no"])
    T["rights"] = {k: sum(s["rights"][k] for s in out_rows) for k in ("active", "expired", "unknown")}
    T["approvals"] = sum(s["approvals"] for s in out_rows)
    T["cost_label"] = weakest([s["cost_label"] for s in out_rows])
    T["cost_missing"] = sorted({m for s in out_rows for m in s["cost_missing"]})
    T["pays"] = ""
    if margin:
        T["pays"] = "both" if T["contrib"][0] > ZERO else ("high_only" if T["contrib"][1] > ZERO else "neither")
    T["read"] = "none" if T["tracked"] == 0 else ("thin" if T["tracked"] < a.min_orders else "ok")
    T["vs_target"] = "" if target is None or T["cpo"] is None else ("at_or_below" if T["cpo"] <= target else "above")
    vs = [s["views"] for s in out_rows if s["views"] is not None]
    rs = [s["reach_sum"] for s in out_rows if s["reach_sum"] is not None]
    ls = [s["likes"] for s in out_rows if s["likes"] is not None]
    T.update({"views": sum(vs) if vs else None, "reach_sum": sum(rs) if rs else None, "likes": sum(ls) if ls else None,
              "rlabel": weakest([s["rlabel"] for s in out_rows]), "reported": sum(len(s["reach"]) for s in out_rows)})

    # --- platforms
    plat = OrderedDict()
    for s in out_rows:
        on = sorted({p["platform"] for p in s["posts"]})
        for p in s["posts"]:
            q = plat.setdefault(p["platform"], {"posts": 0, "live": 0, "removed": 0, "yes": 0, "checked": 0, "orders": 0})
            q["posts"] += 1
            checks = [p["check_day30"], p["check_day7"], p["check_day1"]]
            last = next((x for x in checks if x in ("live", "removed", "edited")), "")
            q["live"] += last in ("live", "edited")
            q["removed"] += last == "removed"
            q["yes"] += p["disclosure_seen"] == "yes"
            q["checked"] += p["disclosure_seen"] in ("yes", "partial", "no")
        if not s["tracked"]:
            continue
        bucket = on[0] if len(on) == 1 else ("several platforms" if on else "no post recorded")
        q = plat.setdefault(bucket, {"posts": 0, "live": 0, "removed": 0, "yes": 0, "checked": 0, "orders": 0})
        q["orders"] += s["tracked"]

    # --- coverage
    if not any(e["missing"] or e["fallbacks"] for e in exports):
        fine.append("every column the computation reads was in the orders export{}".format("s" if len(exports) > 1 else ""))
    fine.append("every creator in the campaign is in the roster")
    if not code_conflicts:
        fine.append("no order carried codes of two active creators")
    if links and not link_notes["conflict"]:
        fine.append("no order was linked to two creators")
    if store["orders"]:
        fine.append("the attributed total was checked against the store's paid orders in the same export: {} of {} are "
                    "creator-tracked (no count independent of the export was available)".format(T["tracked"], store["paid"]))
    cannot.append("sales a post caused without the code or a recorded link (branded search, direct visits, word of mouth)")
    cannot.append("orders shipped to a creator's own address (the roster holds no addresses)")
    if code_conflicts:
        cannot.append("{} orders carrying codes of two active creators, left unattributed: {}".format(
            len(code_conflicts), ", ".join(code_conflicts)))
    if link_notes["conflict"]:
        cannot.append("{} orders the link file gives to two creators, left to codes only".format(len(link_notes["conflict"])))
    if link_notes["not_active"]:
        cannot.append("link rows naming a creator who is not active: {}".format(", ".join(link_notes["not_active"])))
    unmatched_links = [k for k in links if k not in all_orders]
    if unmatched_links:
        cannot.append("{} link row{} an order not in the exports".format(
            len(unmatched_links), " names" if len(unmatched_links) == 1 else "s name"))

    status = "partial" if partial else "complete"
    ctx = {"slug": slug, "from": w_from, "to": w_to, "as_of": as_of, "rows": out_rows, "T": T, "rules": rules,
           "metric": metric, "mname": mname, "direction": direction, "min_orders": a.min_orders, "target": target,
           "store": store, "unattributed": unattributed, "outside": outside, "overridden": overridden,
           "not_activated": not_activated, "plat": plat, "platforms": platforms, "link_state": link_state,
           "partial": partial, "used": used, "missing": missing, "cannot": cannot, "fine": fine, "status": status,
           "earliest": earliest, "metric_source": a.metric_source, "thin_source": a.thin_source, "promos": promos}
    ctx["prior"] = read_prior(ws, a.prior, out_rows) if a.prior else None

    written = write_performance(ws, ctx)
    drafts = [] if a.no_drafts else write_drafts(ws, ctx)
    print_summary(ctx, written, drafts)
    return 2 if partial else 0


# ------------------------------------------------------------------------------------------------
# Outputs

def row_values(ctx, s, total=False):
    T = ctx["T"]
    r = None if total else s["r"]
    s = T if total else s
    exc = s["excluded"]
    vals = OrderedDict([
        ("campaign_slug", ctx["slug"]), ("window_from", ctx["from"].isoformat()), ("window_to", ctx["to"].isoformat()),
        ("as_of", ctx["as_of"].isoformat()), ("creator_ref", "TOTAL" if total else r["creator_ref"]),
        ("display_name", "all ranked creators" if total else r["display_name"]),
        ("primary_platform", "" if total else r["primary_platform"]), ("tier", "" if total else r["tier"]),
        ("compensation_model", "" if total else r["_model"]),
        ("commission_rate_pct", "" if total or r["_rate"] is None else format(r["_rate"].normalize(), "f")),
        ("pipeline_stage", "" if total else s["stage"]), ("roster_status", "" if total else r["status"]),
        ("tracked_orders", s["tracked"]), ("orders_by_code", s["code"]), ("orders_by_link", s["link"]),
        ("gross_sales", fmt(s["gross"])), ("refunds", fmt(s["refunds"])), ("net_sales", fmt(s["net"])),
        ("new_customers", s["new_n"]), ("repeat_customers", s["repeat_n"]), ("orders_customer_unknown", s["cust_unknown"]),
        ("orders_in_holdback", "" if ctx["rules"]["holdback"] is None else s["holdback"]),
        ("excluded_orders", sum(exc.values())), ("excluded_detail", ";".join("{}:{}".format(k, n) for k, n in exc.items())),
        ("cost_commission", fmt(s["commission"])), ("cost_fee", fmt(s["fee"])),
        ("cost_gift", fmt(s["gift"]) if total or s["gift"] is not None else ""), ("cost_rail_app_fee", fmt(s["other"])),
        ("cost_discount", fmt(s["discount_q"])), ("cost_total", fmt(s["total"])), ("cost_label", s["cost_label"]),
        ("cost_missing", ";".join(s["cost_missing"])), ("cost_per_tracked_order", fmt(s["cpo"])),
        ("cost_per_new_customer", fmt(s["cpnc"])), ("commission_return_on_sales", fmt(s["spc"])),
        ("contribution_low_margin", fmt(s["contrib"][0])), ("contribution_high_margin", fmt(s["contrib"][1])),
        ("pays_back", s["pays"]), ("cpo_vs_target", s["vs_target"]),
        ("posts", s["posts"] if total else len(s["posts"])), ("posts_live_at_last_check", s["live"]),
        ("posts_removed", s["removed"]), ("posts_edited", s["edited"]), ("disclosure_yes", s["disc"]["yes"]),
        ("disclosure_partial", s["disc"]["partial"]), ("disclosure_no", s["disc"]["no"]),
        ("disclosure_not_checked", s["disc"][""]),
        ("disclosure_yes_pct", "" if s["disc_pct"] is None else str(s["disc_pct"])),
        ("rights_active", s["rights"]["active"]), ("rights_expired", s["rights"]["expired"]),
        ("rights_unknown", s["rights"]["unknown"]), ("approval_attempts", s["approvals"]),
        ("rank_metric", ctx["metric"]), ("rank", "" if total else s["rank"]), ("read", s["read"]),
        ("notes", "" if total else ";".join(s["notes"])),
        ("reported_posts", s["reported"] if total else len(s["reach"])),
        ("views_reported", "" if s["views"] is None else s["views"]),
        ("reach_reported", "" if s["reach_sum"] is None else s["reach_sum"]),
        ("likes_reported", "" if s["likes"] is None else s["likes"]), ("reported_label", s["rlabel"]),
    ])
    return vals


def write_performance(ws, ctx):
    d = ws / "campaigns" / ctx["slug"]
    d.mkdir(parents=True, exist_ok=True)
    path = d / "performance.csv"
    kept = None
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            first = next(csv.DictReader(f), None)
        old = (first or {}).get("as_of", "")
        if old and old != ctx["as_of"].isoformat():
            dest = d / "performance-{}.csv".format(old)
            n = 2
            while dest.exists():
                dest = d / "performance-{}-{}.csv".format(old, n)
                n += 1
            path.rename(dest)
            kept = dest
    rows = sorted(ctx["rows"], key=lambda s: s["rank"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(PERF_HEADER)
        for s in rows:
            w.writerow(list(row_values(ctx, s).values()))
        w.writerow(list(row_values(ctx, None, total=True).values()))
    return {"path": path, "rows": len(rows) + 1, "kept": kept}


def read_prior(ws, prior, out_rows):
    p = pathlib.Path(prior)
    p = p if p.is_absolute() else ws / prior
    if not p.exists():
        raise BadInput("--prior {} does not exist.".format(prior))
    prev = {r["creator_ref"]: r for r in ATTR.read_exact(p, PERF_HEADER, prior)}
    return {"path": p, "rows": prev}


def label_cost(v, label):
    return "{} ({})".format(v, label) if v and label else (v or "")


def md_table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def signals(ctx, s):
    out = []
    if s["read"] == "none":
        out.append("no tracked orders")
    elif s["read"] == "thin":
        out.append("thin read: {} tracked orders, under the {} the read needs".format(s["tracked"], ctx["min_orders"]))
    else:
        out.append("read ok: {} tracked orders".format(s["tracked"]))
    if s["vs_target"]:
        out.append("cost per order {} the plan target".format("at or below" if s["vs_target"] == "at_or_below" else "above"))
    pays = {"both": "pays back at both ends of the margin band (Estimated)",
            "neither": "does not pay back at either end of the margin band (Estimated)",
            "high_only": "pays back only at the higher margin (Estimated)",
            "no_activity": "nothing spent and nothing sold"}.get(s["pays"])
    if pays:
        out.append(pays)
    if s["fee"]:
        out.append("fee paid {}".format(fmt(s["fee"])))
    checked = s["disc"]["yes"] + s["disc"]["partial"] + s["disc"]["no"]
    if s["posts"]:
        out.append("disclosure yes on {} of {} checked posts".format(s["disc"]["yes"], checked))
    if s["removed"]:
        out.append("{} post{} removed".format(s["removed"], "" if s["removed"] == 1 else "s"))
    if s["rights"]["expired"]:
        out.append("reuse rights expired on {}".format(s["rights"]["expired"]))
    if s["cost_missing"]:
        out.append("cost leaves out {}".format(" and ".join(s["cost_missing"])))
    out += [n for n in s["notes"] if "programme section 3" in n or n.startswith("no code") or n.startswith("no post")]
    return "; ".join(out)


def tables(ctx):
    T, cur, rows = ctx["T"], ctx["rules"]["currency"], sorted(ctx["rows"], key=lambda s: s["rank"])
    hb = ctx["rules"]["holdback"]
    t = {}
    exc = ", ".join("{} {}".format(REASONS[k], n) for k, n in T["excluded"].items()) or "none"
    totals = [
        ["Ranked creators (activated in the campaign)", len(rows), "Measured (pipeline and publications log)"],
        ["Creators with at least one tracked order", sum(1 for s in rows if s["tracked"]), "Measured"],
        ["Tracked orders", T["tracked"], "Measured"],
        ["of which by code / by recorded link", "{} / {}".format(T["code"], T["link"]), "Measured"],
        ["Paid store orders in the window, from every source", ctx["store"]["paid"], "Measured"],
        ["Net sales on tracked orders ({})".format(cur), fmt(T["net"]), "Measured"],
        ["Refunds on tracked orders ({})".format(cur), fmt(T["refunds"]), "Measured"],
        ["New / repeat customers / orders with no customer identifier", "{} / {} / {}".format(T["new_n"], T["repeat_n"], T["cust_unknown"]), "Measured"],
        ["Tracked orders still inside the {}-day holdback".format(hb) if hb is not None else "Tracked orders inside the holdback",
         T["holdback"] if hb is not None else "holdback not set", "Measured"],
        ["Excluded orders carrying a ranked creator's code or link", exc, "Measured"],
        ["Programme cost ({})".format(cur), fmt(T["total"]), T["cost_label"] + (" (leaves out {})".format(", ".join(T["cost_missing"])) if T["cost_missing"] else "")],
        ["Cost per tracked order ({})".format(cur), fmt(T["cpo"]) or "no orders", T["cost_label"]],
        ["Cost per new customer ({})".format(cur), fmt(T["cpnc"]) or "no new customers", T["cost_label"]],
        ["Commission return on sales (commission basis per unit of programme cost)", fmt(T["spc"]) or "no cost", T["cost_label"]],
        ["Contribution after programme cost, low and high margin ({})".format(cur),
         "{} / {}".format(fmt(T["contrib"][0]), fmt(T["contrib"][1])) if ctx["rules"]["margin"] else "margin band not set",
         "Estimated (programme section 1 margin band, read on {})".format(ctx["rules"]["margin_basis"])],
        ["Posts in the window / live at last check / removed", "{} / {} / {}".format(T["posts"], T["live"], T["removed"]), "Measured (publications log)"],
        ["Disclosure seen in full, share of checked posts", "{} percent".format(T["disc_pct"]) if T["disc_pct"] is not None else "no post checked", "Measured (publications log)"],
        ["Posts with active / expired / unknown reuse rights", "{} / {} / {}".format(T["rights"]["active"], T["rights"]["expired"], T["rights"]["unknown"]), "Measured (publications log)"],
    ]
    t["TOTALS"] = md_table(["Measure", "Value", "Label"], totals)

    head = ["Rank", "Creator", "Platform, tier, deal", "Tracked orders (Measured)", "By code / link", "Net sales ({}, Measured)".format(cur),
            "New / repeat customers (Measured)", "Cost per tracked order ({})".format(cur), "Cost per new customer ({})".format(cur), "Read"]
    body = []
    for s in rows:
        r = s["r"]
        body.append([s["rank"], "{} ({})".format(r["display_name"], r["creator_ref"]),
                     "{}, {}, {}".format(r["primary_platform"], r["tier"] or "tier unknown", r["_model"]), s["tracked"],
                     "{} / {}".format(s["code"], s["link"]), fmt(s["net"]), "{} / {}".format(s["new_n"], s["repeat_n"]),
                     label_cost(fmt(s["cpo"]), s["cost_label"]) or "no orders", label_cost(fmt(s["cpnc"]), s["cost_label"]) or "no new customers",
                     s["read"]])
    t["RANKING"] = ("Ranking metric: {} ({} is better; from {}). Every creator activated in the campaign is listed; a creator "
                    "with no value for the metric is ranked after the rest, by programme cost. A read under {} tracked "
                    "orders is marked thin (from {}).\n\n".format(ctx["mname"], ctx["direction"], ctx["metric_source"],
                                                               ctx["min_orders"], ctx["thin_source"])
                    + md_table(head, body))

    head = ["Creator", "Commission (Measured)", "Fee paid", "Gift product", "Rail or app fee", "Discount given", "Programme cost",
            "Cost label", "Left out", "Commission return on sales", "Contribution, low / high margin (Estimated)"]
    body = []
    for s in rows + [None]:
        x = ctx["T"] if s is None else s
        body.append(["all ranked creators" if s is None else s["r"]["creator_ref"], fmt(x["commission"]),
                     fmt(x["fee"]) if x["fee"] is not None else "unknown",
                     fmt(x["gift"]) if x["gift"] is not None else "unknown", fmt(x["other"]), fmt(x["discount_q"]),
                     fmt(x["total"]), x["cost_label"], ", ".join(x["cost_missing"]) or "nothing", fmt(x["spc"]) or "no cost",
                     "{} / {}".format(fmt(x["contrib"][0]), fmt(x["contrib"][1])) if ctx["rules"]["margin"] else "margin band not set"])
    t["COSTS"] = ("Amounts in {}. Programme cost is the pack's shared definition (schemas.md section 12): commission due on "
                  "tracked orders, at the creator's rate on the commission basis and including orders still inside the "
                  "holdback; flat fees paid; gifted units at their unit cost; the customer discount given; and any rail or "
                  "app fee. Fees, gifts and rail or app fees come from campaigns/{}/costs.csv, User-provided unless marked "
                  "estimate. The payable commission is commission-statement's.\n\n".format(cur, ctx["slug"])
                  + md_table(head, body))

    head = ["Creator", "Posts", "Live at last check", "Removed", "Edited", "Disclosure yes / partial / no / not checked",
            "Disclosure yes, share of checked", "Rights active / expired / unknown", "Approval attempts"]
    body = []
    for s in rows + [None]:
        x = ctx["T"] if s is None else s
        n = x["posts"] if s is None else len(x["posts"])
        body.append(["all ranked creators" if s is None else s["r"]["creator_ref"], n, x["live"], x["removed"], x["edited"],
                     "{} / {} / {} / {}".format(x["disc"]["yes"], x["disc"]["partial"], x["disc"]["no"], x["disc"][""]),
                     "{} percent".format(x["disc_pct"]) if x["disc_pct"] is not None else "none checked",
                     "{} / {} / {}".format(x["rights"]["active"], x["rights"]["expired"], x["rights"]["unknown"]), x["approvals"]])
    t["POSTS"] = "All Measured, from the publications log as checked on the platform.\n\n" + md_table(head, body)

    body = []
    for name, q in ctx["plat"].items():
        rule = organic_rule(name, ctx["platforms"]) if name not in ("several platforms", "no post recorded") else ""
        body.append([name, rule or ("" if name in ("several platforms", "no post recorded") else "not in the table"), q["posts"], q["live"],
                     q["removed"], "{} of {}".format(q["yes"], q["checked"]), q["orders"]])
    t["PLATFORMS"] = ("Tracked orders are placed on a platform only when every post the creator made in the window is on it.\n\n"
                      + md_table(["Platform", "Programme section 3, organic creator posts", "Posts", "Live at last check",
                                  "Removed", "Disclosure yes", "Tracked orders (Measured)"], body))

    body = [[s["r"]["creator_ref"], len(s["reach"]), s["views"] if s["views"] is not None else "",
             s["reach_sum"] if s["reach_sum"] is not None else "", s["likes"] if s["likes"] is not None else "", s["rlabel"],
             ", ".join(sorted({x["source"] for x in s["reach"]})), ", ".join(sorted({x["observed_at"] for x in s["reach"]}))]
            for s in rows if s["reach"]]
    t["REACH"] = ("These figures are reported apart and never enter the ranking. Screenshots and public counters are "
                  "User-provided; an estimate is Estimated.\n\n" + md_table(
                      ["Creator", "Posts with figures", "Views", "Reach", "Likes", "Label", "Source", "Observed"], body)
                  if body else "No reach figures were supplied (campaigns/{}/reach.csv is absent or empty). Nothing is "
                               "inferred in their place.".format(ctx["slug"]))

    lines = ["- Sales a post caused without the creator's code or a recorded link (branded search, direct visits, word of "
             "mouth) are real and are not counted here. If the store runs a post-purchase \"how did you hear about us\" "
             "survey, its export is where they show; this report does not read it.",
             "- Link attribution: {}.".format(ctx["link_state"]),
             "- A code shared beyond the creator's audience (for example on a coupon site) still attributes to the creator; the "
             "export cannot tell the two apart.",
             "- Tracked orders were {} of {} paid store orders in the window (Measured); the rest carried no ranked creator's "
             "code or link.".format(ctx["T"]["tracked"], ctx["store"]["paid"])]
    if ctx["earliest"]:
        lines.append("- New and repeat customers are judged against orders in the exports back to {}; a customer whose "
                     "earlier orders are older than that counts as new.".format(ctx["earliest"]))
    if ctx["unattributed"]:
        lines.append("- Codes on orders in the window that belong to no active creator: " + ", ".join(
            "{} ({} order{}, {} {}{})".format(c, u["orders"], "" if u["orders"] == 1 else "s", fmt(u["sales"]), cur,
                                            ", owner " + u["owner"] if u["owner"] else "") for c, u in ctx["unattributed"].items()) + ".")
    if ctx["promos"]:
        lines.append("- The store's own promotion codes (programme section 5), not creators' codes: " + ", ".join(
            "{} ({} order{})".format(c, u["orders"], "" if u["orders"] == 1 else "s") for c, u in ctx["promos"].items()) + ".")
    if ctx["outside"]:
        lines.append("- Orders attributed to active creators outside this campaign: " + ", ".join(
            "{} ({})".format(k, n) for k, n in ctx["outside"].items()) + ".")
    if ctx["overridden"]:
        lines.append("- Orders where the code and the link file named different creators (the code won): " + ", ".join(ctx["overridden"]) + ".")
    if ctx["not_activated"]:
        lines.append("- Creators in the campaign pipeline who never reached agreement, not ranked: " + ", ".join(
            "{} ({})".format(k, v) for k, v in ctx["not_activated"].items()) + ".")
    t["UNSEEN"] = "\n".join(lines)

    body = [["{} ({})".format(s["r"]["display_name"], s["r"]["creator_ref"]), signals(ctx, s), "[write]", "[write]", "[write]", ""]
            for s in rows]
    t["DECISIONS"] = ("Signals are the script's; the proposed decision, its reason and the alternative are proposals for the "
                      "owner, drawn from the skill's decision guide. The owner's column stays empty until the owner decides.\n\n"
                      + md_table(["Creator", "Signals (from the script)", "Proposed decision", "Reason", "Alternative",
                                  "Owner's decision"], body))

    pr = ctx.get("prior")
    if pr:
        body = []
        for s in rows:
            p = pr["rows"].get(s["r"]["creator_ref"])
            if p is None:
                body.append([s["r"]["creator_ref"], "not in the prior report", s["tracked"], "", "", fmt(s["net"]), "", "", fmt(s["cpo"])])
                continue
            po, ps = int(p["tracked_orders"] or 0), money(p["net_sales"]) or ZERO
            body.append([s["r"]["creator_ref"], p["as_of"], p["tracked_orders"], s["tracked"], s["tracked"] - po, p["net_sales"],
                         fmt(s["net"]), fmt(s["net"] - ps), "{} then, {} now".format(p["cost_per_tracked_order"] or "no orders", fmt(s["cpo"]) or "no orders")])
        prior_as_of = next(iter(pr["rows"].values()), {}).get("as_of", "an unknown date")
        t["PRIOR"] = ("Compared with the run as of {} ({}; Measured on both sides; windows may differ).\n\n".format(
            prior_as_of, pr["path"].name)
                      + md_table(["Creator", "Prior as of", "Tracked orders then", "now", "change", "Net sales then", "now",
                                  "change", "Cost per tracked order"], body))
    else:
        t["PRIOR"] = "No prior report was given (--prior), so nothing is compared."
    t["COVERAGE"] = coverage_text(ctx)
    return t


def coverage_text(ctx):
    parts = ["Coverage ({}).".format(ctx["status"])]
    if ctx["partial"]:
        parts.append("Partial because: " + "; ".join(ctx["partial"]) + ".")
    parts.append("Inputs used: " + "; ".join(ctx["used"]) + ".")
    parts.append("Inputs missing: " + ("; ".join(ctx["missing"]) if ctx["missing"] else "none") + ".")
    parts.append("Could not judge: " + "; ".join(ctx["cannot"]) + ".")
    parts.append("Checked and fine: " + ("; ".join(ctx["fine"]) if ctx["fine"] else "nothing beyond the above") + ".")
    return "\n\n".join(parts)


def write_if_draft(path, text):
    if path.exists() and DRAFT_MARKER not in path.read_text(encoding="utf-8"):
        return "kept"
    state = "replaced" if path.exists() else "written"
    path.write_text(text, encoding="utf-8")
    return state


def write_drafts(ws, ctx):
    out = []
    tpl_r, tpl_n = SKILL / "assets" / "report-template.md", SKILL / "assets" / "creator-results-note.md"
    for p in (tpl_r, tpl_n):
        if not p.exists():
            raise BadInput("the skill's {} is missing; reinstall the performance-report skill.".format(p.relative_to(SKILL)))
    t = tables(ctx)
    status_word = ctx["status"]
    title = "# Performance report: {}, {} to {} ({})".format(ctx["slug"], ctx["from"], ctx["to"], status_word)
    status_line = ("Status: partial. " + "; ".join(ctx["partial"]) + ".") if ctx["partial"] else \
        "Status: complete. Every input the computation needs was present; what the report cannot see is listed below."
    text = tpl_r.read_text(encoding="utf-8")
    fills = {"MARKER": DRAFT_MARKER, "TITLE": title, "STATUS": status_line, "AS_OF": ctx["as_of"].isoformat(), "FROM": ctx["from"].isoformat(),
             "TO": ctx["to"].isoformat(), "CURRENCY": ctx["rules"]["currency"], "SLUG": ctx["slug"]}
    fills.update(t)
    for k, v in fills.items():
        text = text.replace("{{" + k + "}}", v)
    d = ws / "campaigns" / ctx["slug"]
    rp = d / "report-{}.md".format(ctx["as_of"].isoformat())
    out.append((rp, write_if_draft(rp, text)))

    nd = d / "results-notes"
    cur = ctx["rules"]["currency"]
    for s in sorted(ctx["rows"], key=lambda s: s["rank"]):
        if not s["posts"] and not s["tracked"]:
            out.append((None, "no note for {}: no post and no order in the window".format(s["r"]["creator_ref"])))
            continue
        r = s["r"]
        nums = [["Orders placed with your code", s["code"]], ["Orders through your tracked link", s["link"]],
                ["Sales from those orders, after discounts and refunds ({})".format(cur), fmt(s["net"])],
                ["New customers among them", s["new_n"]]]
        posts = [[p["posted_at"][:10], p["platform"], p["format"], {"yes": "seen in full", "partial": "partly seen",
                  "no": "not seen"}.get(p["disclosure_seen"], "not checked"),
                  next((x for x in [p["check_day30"], p["check_day7"], p["check_day1"]] if x in ("live", "removed", "edited")),
                       "not checked")] for p in s["posts"]]
        reach = ""
        if s["reach"]:
            reach = ("The figures you sent us, which we keep as you reported them: {} views, {} reach, {} likes across {} "
                     "post{}.".format(s["views"] if s["views"] is not None else "no", s["reach_sum"] if s["reach_sum"] is not None else "no",
                                      s["likes"] if s["likes"] is not None else "no", len(s["reach"]), "" if len(s["reach"]) == 1 else "s"))
        hold = ""
        if s["holdback"]:
            hold = ("{} of these orders {} still inside the store's {}-day refund window, so the figures may still move."
                    .format(s["holdback"], "is" if s["holdback"] == 1 else "are", ctx["rules"]["holdback"]))
        nt = tpl_n.read_text(encoding="utf-8")
        nf = {"MARKER": DRAFT_MARKER, "CAMPAIGN": ctx["slug"], "FROM": ctx["from"].isoformat(), "TO": ctx["to"].isoformat(),
              "AS_OF": ctx["as_of"].isoformat(), "DISPLAY_NAME": r["display_name"],
              "NUMBERS": md_table(["What we counted (Measured, from the store's orders)", "Figure"], nums),
              "POSTS": md_table(["Posted", "Platform", "Format", "Disclosure as we checked it", "Last check"], posts) if posts else "No post recorded in this window.",
              "REACH": reach, "HOLDBACK": hold}
        for k, v in nf.items():
            nt = nt.replace("{{" + k + "}}", v)
        nd.mkdir(parents=True, exist_ok=True)
        np_ = nd / "{}-{}.md".format(r["creator_ref"], ctx["as_of"].isoformat())
        out.append((np_, write_if_draft(np_, nt)))
    return out


def print_summary(ctx, written, drafts):
    T, cur = ctx["T"], ctx["rules"]["currency"]
    print("performance-report: campaign {}, window {} to {}, as of {}".format(ctx["slug"], ctx["from"], ctx["to"], ctx["as_of"]))
    print("status: {}".format(ctx["status"] if not ctx["partial"] else "partial: " + "; ".join(ctx["partial"])))
    print("ranking metric: {}, {} is better (from {}); thin read under {} tracked orders (from {})".format(
        ctx["mname"], ctx["direction"], ctx["metric_source"], ctx["min_orders"], ctx["thin_source"]))
    if ctx["target"] is not None:
        print("plan target cost per tracked order: {} {} (User-provided)".format(fmt(ctx["target"]), cur))
    print("")
    print("Creators, every activated one ranked. Orders, sales and customers Measured; cost carries its own label.")
    head = "{:>4}  {:<9} {:<22} {:>6} {:>9} {:>10} {:>9} {:>11} {:<14} {:>9} {:<5} {:>5} {:>5}".format(
        "rank", "creator", "name", "orders", "code/link", "net sales", "new/rep", "cost total", "cost label", "cost/ord", "read", "posts", "disc%")
    print(head)
    for s in sorted(ctx["rows"], key=lambda s: s["rank"]):
        print("{:>4}  {:<9} {:<22} {:>6} {:>9} {:>10} {:>9} {:>11} {:<14} {:>9} {:<5} {:>5} {:>5}".format(
            s["rank"], s["r"]["creator_ref"], s["r"]["display_name"][:22], s["tracked"], "{}/{}".format(s["code"], s["link"]),
            fmt(s["net"]), "{}/{}".format(s["new_n"], s["repeat_n"]), fmt(s["total"]), s["cost_label"] or "-",
            fmt(s["cpo"]) or "none", s["read"], len(s["posts"]), "" if s["disc_pct"] is None else str(s["disc_pct"])))
    print("{:>4}  {:<9} {:<22} {:>6} {:>9} {:>10} {:>9} {:>11} {:<14} {:>9} {:<5} {:>5} {:>5}".format(
        "", "TOTAL", "all ranked creators", T["tracked"], "{}/{}".format(T["code"], T["link"]), fmt(T["net"]),
        "{}/{}".format(T["new_n"], T["repeat_n"]), fmt(T["total"]), T["cost_label"], fmt(T["cpo"]) or "none", T["read"],
        T["posts"], "" if T["disc_pct"] is None else str(T["disc_pct"])))
    print("")
    print("store context (Measured): {} paid store orders in the window, {} of them creator-tracked".format(ctx["store"]["paid"], T["tracked"]))
    if ctx["rules"]["margin"]:
        print("contribution after programme cost (Estimated, margin band {}-{} percent on {}): {} to {} {}".format(
            ctx["rules"]["margin"][0], ctx["rules"]["margin"][1], ctx["rules"]["margin_basis"], fmt(T["contrib"][0]),
            fmt(T["contrib"][1]), cur))
    if T["reported"]:
        print("reported reach, not ranked ({}): {} views, {} reach, {} likes over {} posts".format(
            T["rlabel"], T["views"] if T["views"] is not None else "no", T["reach_sum"] if T["reach_sum"] is not None else "no",
            T["likes"] if T["likes"] is not None else "no", T["reported"]))
    for code, u in ctx["unattributed"].items():
        print("unattributed code {}: {} order(s), {} {}{}".format(code, u["orders"], fmt(u["sales"]), cur,
                                                             "; owner " + u["owner"] if u["owner"] else ""))
    for code, u in ctx["promos"].items():
        print("store promotion code {} (programme section 5): {} order(s)".format(code, u["orders"]))
    for ref, n in ctx["outside"].items():
        print("orders for {} (active, not in this campaign): {}".format(ref, n))
    for x in ctx["overridden"]:
        print("code and link disagreed, code won: {}".format(x))
    print("")
    print(coverage_text(ctx).replace("\n\n", "\n"))
    print("")
    print("wrote {} ({} rows: {} creators and TOTAL)".format(written["path"], written["rows"], written["rows"] - 1))
    if written["kept"]:
        print("kept the earlier run's file as {}".format(written["kept"]))
    for path, state in drafts:
        print("{}: {}".format(state, path) if path else state)
        if state == "kept":
            print("  (prose already written there; the draft marker was removed, so it was not overwritten)")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Compute per-creator and campaign performance for one campaign of the consumer-brand creator programme "
                    "and write campaigns/<slug>/performance.csv, plus report and results-note drafts.",
        epilog="Exit 0 complete; 1 bad input (the message says what to fix); 2 partial (the output says what was skipped). "
               "No network. Paths in --export and --prior are relative to the workspace.")
    ap.add_argument("workspace", help="the programme workspace folder")
    ap.add_argument("--campaign", required=True, help="the campaign slug, for example 2026-12-holiday-tote")
    ap.add_argument("--from", dest="date_from", help="first order date counted, YYYY-MM-DD (default: the campaign's first post)")
    ap.add_argument("--to", dest="date_to", help="last order date counted, YYYY-MM-DD (default: --as-of)")
    ap.add_argument("--as-of", dest="as_of", help="the date the report is true on, YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--export", action="append", help="an orders export to read instead of every orders CSV in exports/; repeatable")
    ap.add_argument("--rank-by", dest="rank_by", choices=list(RANK_METRICS), help="the ranking metric for this run only "
                    "(default: programme section 5); use it when the campaign plan or the owner declares another")
    ap.add_argument("--rank-by-source", dest="rank_by_source", default="the person running the report",
                    help="who declared the --rank-by metric, for example 'the campaign plan' or 'the owner'")
    ap.add_argument("--min-orders", dest="min_orders", type=int, default=None,
                    help="tracked orders below which a read is marked thin, for this run only (default: programme section 5)")
    ap.add_argument("--target-cpo", dest="target_cpo", help="the plan's target cost per tracked order, store currency")
    ap.add_argument("--prior", help="an earlier performance.csv to compare with; campaigns/<slug>/performance.csv is the last run, "
                    "read before this run keeps it under its as-of date")
    ap.add_argument("--no-drafts", dest="no_drafts", action="store_true", help="write performance.csv only, no report or notes drafts")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except BadInput as e:
        print("performance-report could not run: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
