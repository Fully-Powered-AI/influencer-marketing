#!/usr/bin/env python3
"""Compute the creator commission statement for one period of the consumer-brand creator programme.

Reads, inside the workspace only:
  program/program.md                 sections 1, 4, 5, 6 and 10 (rates and rules, found by heading number)
  data/creators.csv                  the roster: codes, status, deal, rate, flat fee, rail, agreement date
  data/publications.csv              fee milestones for flat and hybrid deals, disclosure as posted
  codes/code-plan-*.csv              optional: further minted codes per creator
  exports/*.csv                      Shopify orders exports (or the files named with --export)
  exports/link-attribution-<period>.csv   optional: orders a person attributed to a creator's tracked link
  payouts/<earlier period>/statement.csv  the latest earlier statement, for amounts carried forward
Writes payouts/<period>/statement.csv, payout-list.csv and statement.md, and nothing else.

Exit 0: a final or preview statement with every needed input read.
Exit 2: partial; the first line of statement.md and the coverage line say what was missing.
Exit 1: bad input; one sentence on stderr says what to fix. Nothing is written.
No network. Python 3 standard library only. Run with: python3 -I commission_statement.py ...
"""
import argparse
import csv
import datetime as dt
import re
import sys
from collections import OrderedDict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

# ---------------------------------------------------------------------------------------------
# Shapes. Source: the pack's references/schemas.md, written 2026-10-20 (sections 4, 6, 9, 10, 11).
# The runtime copy ships with creator-roster; if the two differ, that copy rules and this list is
# updated to match.
CREATORS_HEADER = (
    "creator_ref,display_name,primary_platform,primary_handle,profile_url,other_platforms,tier,"
    "followers_primary,followers_as_of,engagement_rate_pct,engagement_as_of,niche_tags,"
    "audience_fit_score,brand_safety_flag,contact_path,contact_email,status,compensation_model,"
    "commission_rate_pct,flat_fee,code,affiliate_link,rail,agreement_date,agreement_file,"
    "usage_rights_until,exclusivity_until,first_campaign,last_activity,notes").split(",")
PUBLICATIONS_HEADER = (
    "publication_id,campaign_slug,creator_ref,platform,post_url,posted_at,format,disclosure_seen,"
    "disclosure_form,code_in_post,link_in_post,approval_id,check_day1,check_day7,check_day30,"
    "rights_until,notes").split(",")
CODE_PLAN_HEADER = (
    "creator_ref,code,discount_type,discount_value,applies_to,starts_at,ends_at,usage_limit,"
    "once_per_customer,status,minted_at,minted_by,notes").split(",")
LINK_HEADER = ["order_name", "creator_ref", "source", "exported_at"]
STATEMENT_HEADER = (
    "period,creator_ref,display_name,rail,orders_attributed,orders_excluded,gross_sales,refunds,"
    "commission_basis,commission_rate_pct,commission_due,flat_fee_due,total_due,holdback_until,"
    "status,notes").split(",")
# Payout list: schemas.md section 11 (the shape this skill proposed, adopted 2026-10-20).
PAYOUT_HEADER = ["period", "creator_ref", "display_name", "rail", "amount", "currency",
                 "statement_status", "notes"]

# Orders export columns, matched case-insensitively. Source: schemas.md section 10 (first choice,
# fallback); the names are those Shopify lists in references/shopify-affiliate-rails.md section 6
# (read 2026-10-20). The orders export carries no link columns; links come from the link file.
ORDER_COLUMNS = OrderedDict([
    ("order", (["name"], ["id"])),
    ("date", (["created at"], ["paid at"])),
    ("status", (["financial status"], [])),
    ("code", (["discount code"], [])),
    ("subtotal", (["subtotal"], ["total"])),
    ("total", (["total"], [])),
    ("refund", (["refunded amount"], [])),
    ("email", (["email"], [])),
    ("cancelled", (["canceled at", "cancelled at"], [])),
])
OPTIONAL_COLUMNS = {"total", "cancelled"}
COLUMN_LABEL = {"order": "Name", "date": "Created at", "status": "Financial Status",
                "code": "Discount Code", "subtotal": "Subtotal", "total": "Total",
                "refund": "Refunded Amount", "email": "Email", "cancelled": "Canceled at"}
# Build default: a CSV is taken for an orders export when it has an order identifier column and at
# least SIGNATURE_MIN of these known columns (so an export missing one column is still recognised).
SIGNATURE = {"created at", "paid at", "financial status", "discount code", "subtotal", "total",
             "refunded amount", "email", "fulfillment status", "lineitem name"}
SIGNATURE_MIN = 2

# Financial Status values (shopify-affiliate-rails.md section 6 lists paid, authorized, refunded and
# so on). Commission counts paid orders; a partly refunded paid order counts on its reduced basis
# (schemas.md section 10 and the skill brief). Every other value, or none, earns no commission.
STATUS_PAID = "paid"
STATUS_PART_REFUNDED = "partially_refunded"
STATUS_REFUNDED = "refunded"

# schemas.md section 10: only a code belonging to an active creator attributes.
ACTIVE = "active"
# Build default: code-plan rows in these states count as a creator's code alongside the roster's.
LIVE_CODE_STATES = {"minted", "active"}
RAILS = ("collabs", "app", "manual", "none")
SELF_PAYING_RAILS = {"collabs", "app"}   # the rail computes and pays its own commission
COMMISSION_MODELS = {"cpa", "hybrid"}
FEE_MODELS = {"flat", "hybrid"}
MODELS = {"cpa", "flat", "hybrid", "gift", "none"}
LINK_SOURCES = {"collabs", "app", "api", "manual"}   # schemas.md section 10

# schemas.md section 6: publication-tracking records a reached fee milestone as the notes entry
# "YYYY-MM-DD fee milestone reached by <role>: finance to pay". Its writer puts the owner's own text after
# the colon for a second deliverable set, so the date, the phrase and "by <role>" are matched and the text
# after the colon is not. Each entry dated inside the period makes one roster flat_fee due.
MILESTONE_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2}) fee milestone reached by ([^:;]+?)\s*(?::.*)?$", re.I)
# schemas.md section 4: a duplicate retired by a merge stays "ended" with a "merged into c-xxxxxx" note.
MERGED_RE = re.compile(r"merged into (c-[a-z0-9]{6})")
# schemas.md sections 4 and 12: affiliate-onboarding records the brand's own test order in the creator's roster
# notes as its own dated entry, "YYYY-MM-DD test order <Name>" with the export's "#" (for example
# "2026-07-02 test order #1001"); an undated legacy entry "test order #1001" is read the same way. That order
# earns nothing and is listed under exclusions.
TEST_ORDER_RE = re.compile(r"\btest order (#?[A-Za-z0-9][A-Za-z0-9\-]*)", re.I)
# schemas.md section 12: the self-referral rule is off only when the value after the template text is exactly
# one of these, matched as the whole value and never as a word inside a sentence ("earns no commission" keeps
# it on). performance-report's compute_performance.py holds the same list; change both together.
SELFREF_OFF = {"off", "no", "none", "not applied", "does not apply", "disabled"}
# schemas.md section 12: an attribution line reading "as written" (or "as above") says nothing and counts as missing.
SAYS_NOTHING = {"as written", "as above"}
# Markers this script writes into statement notes, read back next period for carried amounts.
CARRY_RE = re.compile(r"carried forward (\d+\.\d{2})")
FINAL_MARK = "final statement"

CENT = Decimal("0.01")
ZERO = Decimal("0")
PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
MARK_RE = re.compile(r"\[[^\]]*\]")
# Template 0.1.2 rule: an indented line under a field is the owner's detail only when it carries a source mark;
# an unmarked indented line (for example "Write the minimum as ...") is template text and is ignored.
SOURCE_MARK_RE = re.compile(r"\[(owner|observed|default)\]", re.I)

# Programme file lines, found by section number and the start of the line. The full template label
# (template 0.1.2, 2026-10-20; the labels read here are unchanged since 0.1.0, and "Partial refunds" and
# "Store promotion codes" are new in 0.1.2) is tried first; otherwise the value is the text after the line's last
# colon, so a label reworded by program-setup still reads.
PROGRAMME_FIELDS = OrderedDict([
    ("currency", (1, "Store currency", "Store currency:")),
    ("model", (4, "Default model for new creators",
               "Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per "
               "deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for "
               "this programme:")),
    ("rate", (4, "Commission rate for",
              "Commission rate for `cpa` and `hybrid`, percent of the commission basis:")),
    ("basis", (4, "Commission basis",
               "Commission basis: `subtotal after discounts, before shipping and tax` [default] or another:")),
    ("partial_refunds", (4, "Partial refunds",
                         "Partial refunds: subtract the full refunded amount from the basis [default], or in "
                         "proportion to the refunded share of the order:")),
    ("attribution", (5, "Attribution model",
                     "Attribution model, declared once: a matching code wins; a tracked link without a "
                     "code is second; nothing else is attributed [default]. Changes here change every report:")),
    ("holdback", (5, "Holdback before a sale",
                  "Holdback before a sale counts as commissionable, in days (refund window) [default 30]:")),
    ("selfref", (5, "Self-referral rule",
                 "Self-referral rule: an order placed by the creator, or shipped to the creator's own "
                 "address, does not earn commission [default]:")),
    ("promo", (5, "Store promotion codes",
               "Store promotion codes that are not creators' codes (so the unattributed list shows only unknown "
               "codes), one per indented line:")),
    ("rail", (6, "Rail chosen",
              "Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or "
              "admin UI codes plus the pack's statement script and a payout list), `none` yet:")),
    ("payout", (6, "Payout schedule",
                "Payout schedule (for example monthly, after the holdback) and minimum payout amount:")),
    ("approver", (6, "Who approves a statement",
                  "Who approves a statement before anything is paid (role), and who pays (role):")),
])

# Exclusion reasons, in the order they are tested. Each order gets the first that applies.
REASONS = OrderedDict([
    ("test_order", "the onboarding test order (named in the roster notes)"),
    ("before_agreement", "dated before the creator's agreement_date"),
    ("status_unknown", "financial status unknown"),
    ("cancelled", "cancelled"),
    ("refunded", "fully refunded"),
    ("not_paid", "financial status not paid"),
    ("self_referral", "self-referral (order email is the creator's)"),
])


class BadInput(Exception):
    pass


def money(text):
    """Parse a money cell. Returns None when unreadable; never turns a bad cell into zero."""
    if text is None:
        return None
    s = re.sub(r"[^0-9.\-]", "", text.strip())
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def fmt(d):
    return "{:.2f}".format(d.quantize(CENT, rounding=ROUND_HALF_UP))


def fmt_rate(d):
    if d is None:
        return ""
    s = format(d.normalize(), "f")
    return s


def parse_iso(text):
    m = DATE_RE.match((text or "").strip())
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def norm_name(name):
    return name.strip().lstrip("#").strip().lower()


def norm_status(s):
    return re.sub(r"[\s\-]+", "_", (s or "").strip().lower())


def split_codes(cell):
    # schemas.md section 10: until a real export settles it, several codes in one cell are split on commas.
    return [c.strip().upper() for c in (cell or "").split(",") if c.strip()]


# ---------------------------------------------------------------------------------------------
# Reading

def read_exact_csv(path, header, what):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        got = next(reader, None)
        if got is None:
            raise BadInput("{} is empty; it needs its header row from schemas.md.".format(what))
        got = [h.strip() for h in got]
        if got != header:
            missing = [h for h in header if h not in got]
            extra = [h for h in got if h not in header]
            if missing or extra:
                raise BadInput("{} header differs from schemas.md: missing {}, extra {}.".format(
                    what, missing or "none", extra or "none"))
            raise BadInput("{} has the right columns in the wrong order; restore the schemas.md order.".format(what))
        rows = []
        for n, row in enumerate(reader, start=2):
            if not any(c.strip() for c in row):
                continue
            if len(row) != len(header):
                raise BadInput("{} line {} has {} cells where the header has {}.".format(
                    what, n, len(row), len(header)))
            rows.append(dict(zip(header, [c.strip() for c in row])))
    return rows


def read_programme(ws):
    path = ws / "program" / "program.md"
    if not path.exists():
        raise BadInput("program/program.md is not in the workspace; run program-setup first.")
    sections = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m:
            current = int(m.group(1))
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    for n in (4, 5, 6):
        if n not in sections:
            raise BadInput("program/program.md has no section {} heading; restore the template headings.".format(n))
    values, found = {}, {}
    for key, (sec, start, label) in PROGRAMME_FIELDS.items():
        values[key] = None
        lines = sections.get(sec, [])
        for i, line in enumerate(lines):
            s = line.strip()
            if not s.startswith("- ") or line[:1].isspace():
                continue
            body = s[2:].strip()
            if not body.lower().startswith(start.lower()):
                continue
            # Indented lines under a field carry extra detail, each with its own source mark (template 0.1.1 on);
            # an indented line without [owner], [observed] or [default] is template text and is skipped.
            extra = []
            for nxt in lines[i + 1:]:
                if not nxt.strip() or not nxt[:1].isspace():
                    break
                if SOURCE_MARK_RE.search(nxt) and "[open]" not in nxt.lower():
                    t = MARK_RE.sub("", nxt).replace("`", "").strip()
                    t = t[2:].strip() if t.startswith("- ") else t
                    if t:
                        extra.append(t)
            found[key] = extra
            if body.startswith(label):
                raw = body[len(label):]
            else:
                raw = body.rsplit(":", 1)[1] if ":" in body else ""
            raw = raw.strip()
            if not raw or "[open]" in raw.lower():
                break
            cleaned = MARK_RE.sub("", raw).replace("`", "").strip()
            if key == "attribution" and cleaned.lower().rstrip(".").strip() in SAYS_NOTHING:
                break
            values[key] = {"raw": raw, "value": cleaned if cleaned else "default", "line": body}
            break
    values["_sections"] = sections
    values["_found"] = found
    return values


def need(prog, key):
    sec, start, _ = PROGRAMME_FIELDS[key]
    v = prog.get(key)
    if v is None:
        raise BadInput("program/program.md section {} has no value for the line starting '{}' (a blank value, "
                       "[open] or 'as written' counts as missing); fill it with program-setup.".format(sec, start))
    return v


def programme_rules(prog, need_rate, need_model):
    """Turn the programme lines this run needs into rules. Raises BadInput naming the section."""
    rules = {}
    hb = need(prog, "holdback")
    m = re.search(r"\d+", hb["value"])
    if not m and hb["value"] == "default":
        m = re.search(r"\[default (\d+)\]", hb["line"])
        rules["holdback"] = int(m.group(1)) if m else None
    else:
        rules["holdback"] = int(m.group(0)) if m else None
    if rules["holdback"] is None:
        raise BadInput("program/program.md section 5 holdback '{}' has no number of days.".format(hb["raw"]))

    at = need(prog, "attribution")["value"].lower()
    if re.search(r"\bcodes? only\b|\bonly (discount )?codes?\b", at):
        rules["links"] = False
    elif ("link" in at and "code" in at) or at == "default":
        rules["links"] = True
    else:
        raise BadInput("program/program.md section 5 declares an attribution model this script does not "
                       "apply ('{}'); it applies 'code first, then tracked link' or 'codes only'.".format(at))

    sr = need(prog, "selfref")["value"].lower()
    rules["selfref"] = sr.strip().rstrip(".").strip() not in SELFREF_OFF

    basis = need(prog, "basis")["value"].lower()
    if "subtotal" in basis or basis == "default":
        rules["basis"] = "subtotal"
    elif "total" in basis:
        rules["basis"] = "total"
    else:
        raise BadInput("program/program.md section 4 commission basis '{}' is not one this script "
                       "computes (subtotal after discounts, or total).".format(basis))

    rail = need(prog, "rail")["value"].lower()
    found = [(rail.find(r), r) for r in RAILS if re.search(r"\b" + r + r"\b", rail)]
    if not found:
        raise BadInput("program/program.md section 6 rail '{}' names none of collabs, app, manual, none.".format(rail))
    rules["rail"] = sorted(found)[0][1]

    po = need(prog, "payout")
    pv = " ".join([po["value"]] + prog["_found"].get("payout", [])).lower()
    m = re.search(r"minimum\D{0,24}?(\d+(?:\.\d+)?)", pv)
    if m:
        rules["minimum"] = Decimal(m.group(1))
    elif re.search(r"\bno minimum\b", pv):
        rules["minimum"] = ZERO
    else:
        nums = re.findall(r"\d+(?:\.\d+)?", pv)
        if "minimum" in po["line"].lower().split(":")[0] and len(nums) == 1:
            rules["minimum"] = Decimal(nums[0])
        else:
            raise BadInput("program/program.md section 6 payout line '{}' does not state the minimum payout; "
                           "write it as 'minimum <amount>' or 'no minimum'.".format(po["raw"]))

    rules["rate"] = None
    rv = prog.get("rate")
    if rv is not None:
        m = re.search(r"\d+(?:\.\d+)?", rv["value"])
        if m:
            rules["rate"] = Decimal(m.group(0))
    if need_rate and rules["rate"] is None:
        raise BadInput("program/program.md section 4 has no commission rate, and a creator on a cpa or "
                       "hybrid deal has none on the roster; fill section 4 or the roster's commission_rate_pct.")
    rules["model"] = None
    mv = prog.get("model")
    if mv is not None:
        mm = re.search(r"\b(cpa|flat|hybrid|gift|none)\b", mv["value"].lower())
        rules["model"] = mm.group(1) if mm else None
    if need_model and rules["model"] is None:
        raise BadInput("program/program.md section 4 has no default model, and an active creator has no "
                       "compensation_model on the roster; fill one of them.")

    cur = prog.get("currency")
    m = re.search(r"\b[A-Z]{3}\b", cur["raw"]) if cur else None
    rules["currency"] = m.group(0) if m else ""

    ap = prog.get("approver")
    if ap is not None:
        rules["approver"] = ap["raw"]
        rules["approver_source"] = "programme section 6"
    else:
        approves, pays = None, None
        for line in prog["_sections"].get(10, []):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0] and not set(cells[0]) <= set("-: "):
                if "statement" in cells[2].lower() and approves is None:
                    approves = cells[0]
                if re.search(r"\bpays\b", cells[1].lower()) and pays is None:
                    pays = cells[0]
        rules["approver"] = "{} approves; {} pays".format(approves or "not named", pays or "not named")
        rules["approver_source"] = "programme section 10 (section 6 line is blank)"
    # Partial refunds (template 0.1.2, section 4). schemas.md section 12: the refunded amount is subtracted
    # in full unless section 4 says in proportion, so an absent or blank line means "in full".
    pr = prog.get("partial_refunds")
    if "partial_refunds" not in prog["_found"]:
        rules["refund_rule"], rules["refund_note"] = "full", "in full (no Partial refunds line in section 4; the shared default)"
    elif pr is None:
        rules["refund_rule"], rules["refund_note"] = "full", "in full (section 4 line blank; the shared default)"
    elif "proportion" in pr["value"].lower():
        rules["refund_rule"], rules["refund_note"] = "proportion", "in proportion to the refunded share of the order total"
    elif re.search(r"\b(full|subtract|default)\b", pr["value"].lower()):
        rules["refund_rule"], rules["refund_note"] = "full", "in full"
    else:
        raise BadInput("program/program.md section 4 'Partial refunds' says '{}'; this script applies 'in full' or "
                       "'in proportion'.".format(pr["raw"]))

    # Store promotion codes (template 0.1.2, section 5): codes on the line itself or on its indented lines.
    promo = set()
    pv5 = prog.get("promo")
    texts = ([pv5["value"]] if pv5 and pv5["value"] != "default" else []) + prog["_found"].get("promo", [])
    for t in texts:
        # "WELCOME10: newsletter first-order offer [owner]" names the code WELCOME10; the words after the colon
        # describe it. A line may also list several codes separated by commas.
        for item in t.split(":", 1)[0].split(","):
            words = item.split()
            c = words[0].strip().upper() if words else ""
            if c and c != "NONE":
                promo.add(c)
    rules["promo"] = promo
    rules["promo_note"] = ("{} listed in section 5".format(len(promo)) if "promo" in prog["_found"]
                           else "no Store promotion codes line in section 5")
    rules["raw"] = {k: (prog[k]["raw"] if prog.get(k) else "") for k in PROGRAMME_FIELDS}
    return rules


def looks_like_orders(header_lower):
    has_id = "name" in header_lower or "id" in header_lower
    return has_id and len(SIGNATURE & set(header_lower)) >= SIGNATURE_MIN


def read_orders_export(path, basis_kind):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None) or []
        lower = [h.strip().lower() for h in header]
        index = {}
        for i, h in enumerate(lower):
            index.setdefault(h, i)
        cols, missing, fallbacks = {}, [], []
        for key, (first, fallback) in ORDER_COLUMNS.items():
            if key == "subtotal" and basis_kind == "total":
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
        orders = OrderedDict()
        rows = 0
        no_id = 0
        for row in reader:
            if not any(c.strip() for c in row):
                continue
            rows += 1
            ident = row[cols["order"]].strip() if "order" in cols and cols["order"] < len(row) else ""
            if not ident:
                no_id += 1
                continue
            key_name = norm_name(ident)
            if key_name in orders:
                # schemas.md section 10: order-level cells come from the first row of each order; later rows of
                # the same order are line items and are not read for order-level values.
                orders[key_name]["rows"] += 1
                continue
            o = orders[key_name] = {"name": ident, "rows": 1, "file": path.name}
            for key, i in cols.items():
                if key == "order" or i >= len(row):
                    continue
                v = row[i].strip()
                if v:
                    o[key] = v
    return {"path": path, "header": header, "cols": cols, "missing": missing,
            "fallbacks": fallbacks, "orders": orders, "rows": rows, "no_id": no_id}


# ---------------------------------------------------------------------------------------------
# Computing

def classify(o, creator, rules, as_of, test_orders):
    """Return (state, reason, subtotal, refund); state is excluded, unassessed, pending or cleared."""
    if norm_name(o["name"]) in test_orders:
        return "excluded", "test_order", None, None
    agreement = parse_iso(creator["agreement_date"])
    if agreement is None:
        return "unassessed", "no agreement_date on the roster, so the start of eligibility is unknown", None, None
    if o["date_parsed"] < agreement:
        return "excluded", "before_agreement", None, None
    status = norm_status(o.get("status"))
    if not status:
        return "excluded", "status_unknown", None, None
    if o.get("cancelled"):
        return "excluded", "cancelled", None, None
    if status == STATUS_REFUNDED:
        return "excluded", "refunded", None, None
    if status not in (STATUS_PAID, STATUS_PART_REFUNDED):
        return "excluded", "not_paid", None, None
    email = creator["contact_email"].strip().lower()
    if rules["selfref"] and email and o.get("email", "").strip().lower() == email:
        return "excluded", "self_referral", None, None
    sub = money(o.get("subtotal"))
    if sub is None:
        return "unassessed", "the basis amount is unreadable", None, None
    if "refund" in o:
        refund = money(o["refund"])
        if refund is None:
            return "unassessed", "the refunded amount is unreadable", None, None
    elif status == STATUS_PART_REFUNDED:
        return "unassessed", "partly refunded and the export does not say by how much", None, None
    else:
        refund = ZERO
    # schemas.md section 12 and programme section 4: the refund comes off the basis in full, or in
    # proportion to the refunded share of the order total; never below zero.
    refund = max(refund, ZERO)
    if refund > ZERO and rules["refund_rule"] == "proportion":
        total = money(o.get("total"))
        if total is None or total <= ZERO:
            return "unassessed", "the in-proportion refund rule needs the order Total, which is missing or unreadable", None, None
        refund = (sub * refund / total).quantize(CENT, rounding=ROUND_HALF_UP)
    refund = min(refund, sub)
    cleared_on = o["date_parsed"] + dt.timedelta(days=rules["holdback"])
    if as_of < cleared_on:
        return "pending", cleared_on.isoformat(), sub, refund
    return "cleared", "", sub, refund


def month_bounds(period):
    m = PERIOD_RE.match(period)
    y, mo = int(m.group(1)), int(m.group(2))
    start = dt.date(y, mo, 1)
    end = dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.timedelta(days=1)
    return start, end


def previous_month(period):
    y, mo = int(period[:4]), int(period[5:])
    return "{:04d}-{:02d}".format(y - (mo == 1), 12 if mo == 1 else mo - 1)


def parse_model(prog):
    v = prog.get("model")
    m = re.search(r"\b(cpa|flat|hybrid|gift|none)\b", v["value"].lower()) if v else None
    return m.group(1) if m else None


def load_roster(ws, used):
    path = ws / "data" / "creators.csv"
    if not path.exists():
        raise BadInput("data/creators.csv is not in the workspace; set the roster up with creator-roster.")
    creators = OrderedDict()
    for r in read_exact_csv(path, CREATORS_HEADER, "data/creators.csv"):
        ref = r["creator_ref"]
        if not ref:
            raise BadInput("data/creators.csv has a row with no creator_ref; fix it with creator-roster.")
        if ref in creators:
            raise BadInput("data/creators.csv lists {} twice; merge the rows with creator-roster.".format(ref))
        model = r["compensation_model"].lower()
        if model and model not in MODELS:
            raise BadInput("data/creators.csv {} has compensation_model '{}'; allowed: {}.".format(
                ref, model, ", ".join(sorted(MODELS))))
        for col in ("commission_rate_pct", "flat_fee"):
            if r[col] and not re.fullmatch(r"\d+(\.\d+)?", r[col]):
                raise BadInput("data/creators.csv {} has {} '{}', which is not a plain number.".format(ref, col, r[col]))
        creators[ref] = r
    used.append("data/creators.csv ({} rows)".format(len(creators)))
    return creators


def merged_into(r):
    m = MERGED_RE.search(r["notes"]) if r["status"] != ACTIVE else None
    return m.group(1) if m else None


def owner_text(ref, creators):
    r = creators[ref]
    target = merged_into(r)
    return "{} ({}, merged into {})".format(ref, r["status"], target) if target else \
        "{} (status {})".format(ref, r["status"] or "empty")


def resolve_deals(creators, prog):
    default_model = parse_model(prog)
    need_model = any(r["status"] == ACTIVE and not r["compensation_model"] for r in creators.values())
    need_rate = any(r["status"] == ACTIVE and not r["commission_rate_pct"]
                    and (r["compensation_model"].lower() or default_model) in COMMISSION_MODELS
                    for r in creators.values())
    rules = programme_rules(prog, need_rate, need_model)
    for r in creators.values():
        r["_model"] = r["compensation_model"].lower() or rules["model"] or ""
        r["_rate"] = Decimal(r["commission_rate_pct"]) if r["commission_rate_pct"] else rules["rate"]
        r["_rate_source"] = "roster" if r["commission_rate_pct"] else "programme section 4"
        if r["_rate"] is not None and not ZERO <= r["_rate"] <= Decimal(100):
            raise BadInput("{} has a commission rate of {} percent; a rate is between 0 and 100.".format(
                r["creator_ref"], fmt_rate(r["_rate"])))
        rail = r["rail"].lower()
        r["_rail"] = rail if rail in RAILS else rules["rail"]
    return rules


def load_codes(ws, creators, used):
    owner = {}
    for r in creators.values():
        c = r["code"].strip().upper()
        if not c:
            continue
        prev = owner.get(c)
        if prev and prev[0] != r["creator_ref"]:
            if r["status"] == ACTIVE and creators[prev[0]]["status"] == ACTIVE:
                raise BadInput("code {} belongs to two active creators ({} and {}); fix it with creator-roster.".format(
                    c, prev[0], r["creator_ref"]))
            if r["status"] != ACTIVE:
                continue
        owner[c] = (r["creator_ref"], "roster")
    plans = sorted((ws / "codes").glob("code-plan-*.csv")) if (ws / "codes").is_dir() else []
    for p in plans:
        for row in read_exact_csv(p, CODE_PLAN_HEADER, "codes/" + p.name):
            c = row["code"].strip().upper()
            if not c or row["status"].lower() not in LIVE_CODE_STATES or row["creator_ref"] not in creators:
                continue
            if c in owner and owner[c][0] != row["creator_ref"]:
                raise BadInput("code {} is the roster's code for {} and a code-plan code for {} in codes/{}.".format(
                    c, owner[c][0], row["creator_ref"], p.name))
            owner.setdefault(c, (row["creator_ref"], "codes/" + p.name))
    if plans:
        used.append("codes/ ({} code plan file{})".format(len(plans), "" if len(plans) == 1 else "s"))
    return owner


def load_exports(ws, args, rules, used, gaps_export, fine, could_not_judge):
    if args.export:
        files = []
        for e in args.export:
            p = Path(e)
            if not p.exists() and (ws / e).exists():
                p = ws / e
            if not p.exists():
                raise BadInput("--export {} does not exist.".format(e))
            files.append(p)
    else:
        if not (ws / "exports").is_dir():
            raise BadInput("exports/ is not in the workspace; save the Shopify orders export there.")
        files = sorted(p for p in (ws / "exports").glob("*.csv") if not p.name.startswith("link-attribution-"))
    exports, skipped = [], []
    for p in files:
        with p.open(newline="", encoding="utf-8-sig") as f:
            head = next(csv.reader(f), None) or []
        if not looks_like_orders([h.strip().lower() for h in head]):
            if args.export:
                raise BadInput("{} does not look like a Shopify orders export (no Name or Id column beside the "
                               "usual order columns).".format(p.name))
            skipped.append(p.name)
            continue
        exports.append(read_orders_export(p, rules["basis"]))
    if not exports:
        raise BadInput("no Shopify orders export found in exports/; export the orders for {} from the Shopify admin "
                       "and save the CSV there.".format(args.period))
    all_orders, duplicates = OrderedDict(), 0
    for e in exports:
        name = rel(ws, e["path"])
        for k in e["missing"]:
            if k == "email" and not rules["selfref"]:
                continue
            gaps_export.append("{} has no {} column".format(name, COLUMN_LABEL[k]))
        for k, alt in e["fallbacks"]:
            gaps_export.append("{} has no {} column; used {} instead{}".format(
                name, COLUMN_LABEL[k], alt.title(),
                ", which includes shipping and tax and so overstates the basis" if k == "subtotal" else ""))
        if e["no_id"]:
            gaps_export.append("{}: {} rows without an order identifier were not read".format(name, e["no_id"]))
        used.append("{} ({} rows, {} orders)".format(name, e["rows"], len(e["orders"])))
        for key, o in e["orders"].items():
            if key in all_orders:
                duplicates += 1
                continue
            all_orders[key] = o
    if all(("order", "id") in e["fallbacks"] for e in exports) and rules["links"]:
        gaps_export.append("the exports carry Id but not Name, and the link file joins on Name")
    if not any("cancelled" in e["cols"] for e in exports):
        could_not_judge.append("cancellations beyond the financial status (no Canceled at column)")
    if skipped:
        fine.append("skipped as not orders exports: {}".format(", ".join(skipped)))
    if duplicates:
        fine.append("orders found in more than one export and counted once: {}".format(duplicates))
    return all_orders


def load_links(ws, period, rules, creators, used, could_not_judge, p_end):
    info = {"map": {}, "rows": 0, "not_active": [], "conflict": [], "bad_source": 0, "present": False}
    path = ws / "exports" / "link-attribution-{}.csv".format(period)
    if not rules["links"]:
        info["state"] = "not used: programme section 5 attributes codes only"
        return info
    if not path.exists():
        info["state"] = "absent: exports/{} not found, so only codes attribute".format(path.name)
        return info
    rows = read_exact_csv(path, LINK_HEADER, "exports/" + path.name)
    by_order = OrderedDict()
    for lr in rows:
        by_order.setdefault(norm_name(lr["order_name"]), []).append(lr)
    for k, group in by_order.items():
        refs = sorted({lr["creator_ref"] for lr in group})
        if len(refs) > 1:
            info["conflict"].append("{} ({})".format(group[0]["order_name"], ", ".join(refs)))
            continue
        lr = group[0]
        c = creators.get(lr["creator_ref"])
        if c is None or c["status"] != ACTIVE:
            info["not_active"].append("{} ({})".format(lr["order_name"], lr["creator_ref"]))
            continue
        info["map"][k] = lr
    info["bad_source"] = sum(1 for lr in rows if lr["source"].lower() not in LINK_SOURCES)
    exported = sorted({lr["exported_at"][:10] for lr in rows if parse_iso(lr["exported_at"])})
    info["rows"], info["present"] = len(rows), True
    info["state"] = "exports/{} ({} rows{})".format(path.name, len(rows), ", exported " + ", ".join(exported) if exported else "")
    used.append(info["state"])
    if exported and parse_iso(exported[-1]) <= p_end:
        could_not_judge.append("link attribution for orders after {}: the link file was exported before the period "
                               "ended".format(exported[-1]))
    elif not exported:
        could_not_judge.append("whether the link file covers the whole period (no exported_at dates)")
    return info


def attribute(in_period, code_owner, creators, links, rules, as_of, test_orders):
    per = OrderedDict()
    res = {"per": per, "unattributed": OrderedDict(), "promo": OrderedDict(), "conflicts": [], "no_code": [],
           "stray_only": [], "overridden": [], "link_used": 0}

    def active_owner(c):
        own = code_owner.get(c)
        return own[0] if own and creators[own[0]]["status"] == ACTIVE else None

    for o in sorted(in_period, key=lambda x: (x["date_parsed"], x["name"])):
        codes = split_codes(o.get("code"))
        owners = sorted({active_owner(c) for c in codes if active_owner(c)})
        stray = [c for c in codes if not active_owner(c)]
        link = links.get(norm_name(o["name"]))
        ref, via = None, None
        if len(owners) > 1:
            res["conflicts"].append("{} ({})".format(o["name"], ", ".join(owners)))
        elif owners:
            ref, via = owners[0], "code"
            if link and link["creator_ref"] != ref:
                res["overridden"].append("{} (code {}, link {})".format(o["name"], ref, link["creator_ref"]))
        elif link:
            ref, via = link["creator_ref"], "link"
            res["link_used"] += 1
        for c in stray:
            own = code_owner.get(c)
            target = res["promo"] if (c in rules["promo"] and not own) else res["unattributed"]
            info = target.setdefault(c, {"orders": 0, "subtotal": ZERO, "owner": "", "attributed": 0})
            info["orders"] += 1
            info["subtotal"] += money(o.get("subtotal")) or ZERO
            if own:
                info["owner"] = owner_text(own[0], creators)
            if ref:
                info["attributed"] += 1
        if ref is None:
            if len(owners) <= 1:
                (res["stray_only"] if codes else res["no_code"]).append(o["name"])
            continue
        b = bucket(per, ref)
        b["orders"].append(o)
        if via == "link":
            b["via_link"] += 1
        elif link and link["creator_ref"] != ref:
            b["code_beat_link"] += 1
        state, reason, sub, refund = classify(o, creators[ref], rules, as_of, test_orders)
        if state == "excluded":
            b["excluded"].setdefault(reason, []).append(o)
        elif state == "unassessed":
            b["unassessed"].append((o, reason))
        elif state == "pending":
            b["pending"].append((o, reason, sub, refund))
        else:
            b["cleared"].append((o, sub, refund))
    return res


def bucket(per, ref):
    if ref not in per:
        per[ref] = {"orders": [], "excluded": OrderedDict(), "pending": [], "cleared": [], "unassessed": [],
                    "via_link": 0, "code_beat_link": 0}
    return per[ref]


def load_publications(ws, p_start, p_end, used):
    path = ws / "data" / "publications.csv"
    if not path.exists():
        return None, {}, {}, {}
    rows = read_exact_csv(path, PUBLICATIONS_HEADER, "data/publications.csv")
    milestones, posted, flags = {}, {}, {}
    for pr in rows:
        ref = pr["creator_ref"]
        for entry in pr["notes"].split(";"):
            m = MILESTONE_RE.match(entry)
            if m:
                d = parse_iso(m.group(1))
                if d and p_start <= d <= p_end:
                    milestones.setdefault(ref, []).append(pr["publication_id"])
                break
        d = parse_iso(pr["posted_at"])
        if d and p_start <= d <= p_end:
            posted.setdefault(ref, []).append(pr["publication_id"])
            seen = pr["disclosure_seen"].lower()
            if seen in ("no", "partial"):
                flags.setdefault(ref, []).append("{} disclosure_seen {}".format(pr["publication_id"], seen))
    used.append("data/publications.csv ({} rows)".format(len(rows)))
    return rows, milestones, posted, flags


def load_carried(ws, period, used, could_not_judge, person):
    """Amounts carried below the minimum, per creator, from that creator's latest final statement row.

    Earlier statements are read newest first. A creator's preview or partial row is walked past, so a
    statement that never reached final does not lose an amount carried into it; a final row ends the walk;
    a statement with no row for the creator ends it too (nothing was carried into that month)."""
    carried, note = {}, "none (no earlier statement in payouts/)"
    pay = ws / "payouts"
    if not pay.is_dir():
        return carried, note
    dirs = [p for p in pay.iterdir() if p.is_dir() and PERIOD_RE.match(p.name) and (p / "statement.csv").exists()]
    later = sorted(p.name for p in dirs if p.name > period)
    if later:
        person.append("a later statement exists ({}); amounts carried past this period may already sit there, so "
                      "check them before approving a rerun".format(", ".join(later)))
    earlier = sorted((p for p in dirs if p.name < period), key=lambda p: p.name, reverse=True)
    if not earlier:
        return carried, note
    stmts = [(p.name, read_exact_csv(p / "statement.csv", STATEMENT_HEADER, "payouts/{}/statement.csv".format(p.name)))
             for p in earlier]
    refs = []
    for _, rows in stmts:
        for r in rows:
            if r["creator_ref"] not in refs:
                refs.append(r["creator_ref"])
    walked_past, read_from = set(), set()
    for ref in refs:
        for name, rows in stmts:
            row = next((r for r in rows if r["creator_ref"] == ref), None)
            if row is None:
                break
            if FINAL_MARK not in row["notes"]:
                walked_past.add(name)
                continue
            m = CARRY_RE.search(row["notes"])
            if m and row["status"] in ("draft", "approved"):
                carried[ref] = (Decimal(m.group(1)), name)
                read_from.add(name)
            elif m and row["status"] == "disputed":
                could_not_judge.append("the amount carried for {} in {} (that row is disputed)".format(ref, name))
            break
    for name in sorted(walked_past):
        could_not_judge.append("amounts carried from before {0}: rows of {0}'s statement are not final, so the latest "
                               "final row of each creator was read".format(name))
    note = "earlier statements {} ({} carried amount{}{})".format(
        ", ".join("payouts/{}/statement.csv".format(n) for n, _ in reversed(stmts)), len(carried),
        "" if len(carried) == 1 else "s", ", read from " + ", ".join(sorted(read_from)) if read_from else "")
    used.append(note)
    if stmts[0][0] != previous_month(period):
        could_not_judge.append("anything carried from the months between {} and {} (no statement found for them)".format(
            stmts[0][0], period))
    return carried, note


def rel(ws, p):
    try:
        return str(p.resolve().relative_to(ws.resolve()))
    except ValueError:
        return p.name


def run(args):
    ws = Path(args.workspace)
    if not ws.is_dir():
        raise BadInput("the workspace '{}' is not a folder.".format(args.workspace))
    if not PERIOD_RE.match(args.period):
        raise BadInput("--period must be YYYY-MM, for example 2026-09.")
    as_of = parse_iso(args.as_of)
    if as_of is None or len(args.as_of.strip()) != 10:
        raise BadInput("--as-of must be a date, YYYY-MM-DD.")
    today = dt.datetime.now(dt.timezone.utc).date()   # the pack's scripts judge "today" in UTC
    if as_of > today:
        raise BadInput("--as-of {} is after today; a statement is computed as of a day that has happened.".format(
            as_of.isoformat()))
    p_start, p_end = month_bounds(args.period)
    if as_of < p_start:
        raise BadInput("--as-of {} is before the period {} begins.".format(as_of.isoformat(), args.period))

    used, fine, could_not_judge, gaps_export = [], [], [], []
    creators = load_roster(ws, used)
    rules = resolve_deals(creators, read_programme(ws))
    used.append("program/program.md sections 1, 4, 5, 6")
    code_owner = load_codes(ws, creators, used)
    all_orders = load_exports(ws, args, rules, used, gaps_export, fine, could_not_judge)

    unreadable, in_period, dates = 0, [], []
    for o in all_orders.values():
        d = parse_iso(o.get("date"))
        if d is None:
            unreadable += 1
            continue
        o["date_parsed"] = d
        dates.append(d)
        if p_start <= d <= p_end:
            in_period.append(o)
    if unreadable:
        gaps_export.append("{} orders had no readable order date, so whether they fall in the period is unknown".format(unreadable))

    links = load_links(ws, args.period, rules, creators, used, could_not_judge, p_end)
    test_orders = {}
    for r in creators.values():
        for name in TEST_ORDER_RE.findall(r["notes"]):
            test_orders[norm_name(name)] = r["creator_ref"]
    if test_orders:
        fine.append("onboarding test orders named in the roster notes: {}".format(len(test_orders)))
    res = attribute(in_period, code_owner, creators, links["map"], rules, as_of, test_orders)
    per = res["per"]
    in_names = {norm_name(o["name"]) for o in in_period}
    link_outside = sorted(lr["order_name"] for k, lr in links["map"].items() if k in all_orders and k not in in_names)
    link_missing = sorted(lr["order_name"] for k, lr in links["map"].items() if k not in all_orders)

    pubs, milestones, posted, disclosure = load_publications(ws, p_start, p_end, used)
    person = []   # lines for "Needs a person" that belong to no statement row
    creator_gaps = {}
    for r in creators.values():
        if r["status"] == ACTIVE and r["_model"] in FEE_MODELS and pubs is None:
            bucket(per, r["creator_ref"])
            creator_gaps.setdefault(r["creator_ref"], []).append("flat fee not assessed: data/publications.csv is missing")
    # A missing link file is a gap only when a tracked link was issued and some order dated in the period carries
    # no active creator's code, so that a link could have attributed it (code wins otherwise). With no such order
    # (an empty month, or every order carrying a creator code) the file could change nothing.
    link_candidates = len(res["no_code"]) + len(res["stray_only"])
    if rules["links"] and not links["present"] and link_candidates:
        for r in creators.values():
            if r["status"] == ACTIVE and r["affiliate_link"].strip():
                bucket(per, r["creator_ref"])
                creator_gaps.setdefault(r["creator_ref"], []).append(
                    "a tracked link was issued and exports/link-attribution-{}.csv is missing, so link-only orders are "
                    "not counted".format(args.period))
    for ref, ids in sorted(milestones.items()):
        if ref not in creators:
            person.append("{}: fee milestone on {} for a creator not on the roster".format(ref, ",".join(ids)))
        elif merged_into(creators[ref]):
            person.append("{}: fee milestone on {}, but the row is {}; a person records it on the kept row".format(
                ref, ",".join(ids), owner_text(ref, creators)))
            milestones[ref] = []
        elif creators[ref]["_model"] in FEE_MODELS:
            bucket(per, ref)
        else:
            person.append("{}: fee milestone recorded on {} but the deal is {}, so no fee is computed".format(
                ref, ",".join(ids), creators[ref]["_model"] or "unset"))
    for ref, items in sorted(disclosure.items()):
        if ref not in per:
            person.append("{}: {} (no statement row this period)".format(ref, "; ".join(items)))
    carried, carry_note = load_carried(ws, args.period, used, could_not_judge, person)
    for ref in list(carried):
        if ref in creators and merged_into(creators[ref]):
            person.append("{}: {} carried from {}, but the row is {}; a person moves it to the kept row".format(
                ref, fmt(carried[ref][0]), carried[ref][1], owner_text(ref, creators)))
            del carried[ref]
        elif ref in creators:
            bucket(per, ref)

    holdback_until = p_end + dt.timedelta(days=rules["holdback"])
    final = as_of >= holdback_until
    rows, payout, detail = [], [], []
    for ref in sorted(per):
        detail.append(creator_row(ref, per[ref], creators[ref], rules, args.period, as_of, final, holdback_until,
                                  gaps_export, creator_gaps.get(ref, []), milestones.get(ref, []),
                                  posted.get(ref, []), pubs is not None, disclosure.get(ref, []),
                                  carried.get(ref, (ZERO, ""))))
    for d in detail:
        rows.append(d["row"])
        if d["payout"]:
            payout.append(d["payout"])
    partial = bool(gaps_export) or any(d["gaps"] for d in detail)
    if partial:
        outcome = "partial" + ("" if final else " (preview)")
    else:
        outcome = "final" if final else "preview"

    if rules["selfref"]:
        no_email = sorted(d["ref"] for d in detail if d["b"]["orders"] and not creators[d["ref"]]["contact_email"])
        if no_email:
            could_not_judge.append("self-referral by email for {} (no contact_email on the roster)".format(", ".join(no_email)))
        could_not_judge.append("self-referral by shipping address (the roster holds no addresses)")
    else:
        could_not_judge.append("self-referral (programme section 5 does not apply the rule)")
    if not gaps_export:
        fine.append("every export column the statement needs was present")

    out_dir = ws / "payouts" / args.period
    stmt_path = out_dir / "statement.csv"
    earlier_rows = 0
    if stmt_path.exists():
        existing = read_exact_csv(stmt_path, STATEMENT_HEADER, "payouts/{}/statement.csv".format(args.period))
        locked = [r for r in existing if r["status"] != "draft"]
        if locked:
            raise BadInput("payouts/{}/statement.csv has rows a person has marked {} ({}); a rerun would overwrite "
                           "them. Move that folder aside under a dated name and rerun, or keep the statement as it "
                           "stands.".format(args.period, ", ".join(sorted({r["status"] for r in locked})),
                                            ", ".join(r["creator_ref"] for r in locked)))
        earlier_rows = len(existing)

    ctx = {"args": args, "as_of": as_of, "outcome": outcome, "final": final, "partial": partial, "rules": rules,
           "detail": detail, "per": per, "creators": creators, "holdback_until": holdback_until,
           "in_period": in_period, "all_orders": all_orders, "dates": dates, "res": res, "links": links,
           "link_outside": link_outside, "link_missing": link_missing, "gaps_export": gaps_export,
           "could_not_judge": could_not_judge, "used": used, "fine": fine, "payout": payout,
           "carry_note": carry_note, "person": person}
    md = render_md(ctx)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(stmt_path, STATEMENT_HEADER, rows)
    write_csv(out_dir / "payout-list.csv", PAYOUT_HEADER, payout)
    (out_dir / "statement.md").write_text(md, encoding="utf-8")

    print("Commission statement {} as of {}: {}".format(args.period, as_of.isoformat(), outcome))
    for d in detail:
        print("  {} ({}): basis {}, commission {}, flat fee {}, carried in {}, total {}; payout list: {}".format(
            d["ref"], d["rail"], fmt(d["basis"]), fmt(d["commission"]), fmt(d["fee"]), fmt(d["carry"]),
            fmt(d["total"]), payout_word(d, final, bool(gaps_export), rules)))
    print("  orders dated in the period: {}; unattributed codes: {}; payout list rows: {}".format(
        len(in_period), len(res["unattributed"]), len(payout)))
    replaced = "; replaced an earlier draft of {} rows".format(earlier_rows) if stmt_path.exists() and earlier_rows else ""
    print("Wrote payouts/{0}/statement.csv ({1} rows{2}), payouts/{0}/payout-list.csv ({3} rows), "
          "payouts/{0}/statement.md".format(args.period, len(rows), replaced, len(payout)))
    print(md.rstrip().splitlines()[-1])
    return 2 if partial else 0


def creator_row(ref, b, c, rules, period, as_of, final, holdback_until, gaps_export, base_gaps, fee_ids,
                posted_ids, have_pubs, flags, carry):
    gross = sum((s for _, s, _ in b["cleared"]), ZERO)
    refunds = sum((r for _, _, r in b["cleared"]), ZERO)
    basis = gross - refunds
    model = c["_model"]
    rate = (c["_rate"] or ZERO) if model in COMMISSION_MODELS else ZERO
    commission = (basis * rate / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    gaps = list(base_gaps) + ["{} not assessed: {}".format(o["name"], why) for o, why in b["unassessed"]]
    fee = ZERO
    notes = []
    if fee_ids and model in FEE_MODELS:
        if c["flat_fee"]:
            fee = Decimal(c["flat_fee"]) * len(fee_ids)
        else:
            gaps.append("fee milestone recorded on {} but the roster has no flat_fee".format(",".join(fee_ids)))
    carry_amt, carry_from = carry
    total = commission + fee + carry_amt
    rail = c["_rail"]
    payout_amount = fee + carry_amt if rail in SELF_PAYING_RAILS else total
    pending_basis = sum((s - r for _, _, s, r in b["pending"]), ZERO)
    excluded_n = sum(len(v) for v in b["excluded"].values())

    if gaps_export or gaps:
        notes.append("{} partial statement".format(as_of.isoformat()))
    elif final:
        notes.append("{} {}".format(as_of.isoformat(), FINAL_MARK))
    else:
        notes.append("{} preview, holdback open until {}".format(as_of.isoformat(), holdback_until.isoformat()))
    if model in COMMISSION_MODELS:
        notes.append("rate from {}".format(c["_rate_source"]))
    elif model:
        notes.append("{} deal: no commission".format(model))
    if b["excluded"]:
        notes.append("excluded: " + ", ".join("{} {}".format(REASONS[k], len(v)) for k, v in b["excluded"].items()))
    if b["pending"]:
        notes.append("pending inside the holdback: {} orders, basis {}".format(len(b["pending"]), fmt(pending_basis)))
    if b["via_link"]:
        notes.append("attributed by tracked link: {}".format(b["via_link"]))
    if b["code_beat_link"]:
        notes.append("orders with another creator's link where the code won: {}".format(b["code_beat_link"]))
    if fee:
        notes.append("fee milestones: {} ({})".format(len(fee_ids), ",".join(fee_ids)))
    elif model in FEE_MODELS and posted_ids and have_pubs and not fee_ids:
        notes.append("posted in the period ({}) but no fee milestone recorded".format(",".join(posted_ids)))
    if carry_amt:
        notes.append("carried in {} from {}".format(fmt(carry_amt), carry_from))
    if rail in SELF_PAYING_RAILS:
        notes.append("rail {}: reconciliation, the rail pays its own commission".format(rail))
    elif rail == "none":
        notes.append("no payout rail chosen in programme section 6")
    notes.extend(flags)
    notes.extend(gaps)

    on_list = False
    if final and not gaps_export and not gaps and payout_amount > ZERO:
        if payout_amount >= rules["minimum"]:
            on_list = True
        else:
            notes.append("below minimum {}: carried forward {}".format(fmt(rules["minimum"]), fmt(payout_amount)))
    row = OrderedDict([
        ("period", period), ("creator_ref", ref), ("display_name", c["display_name"]), ("rail", rail),
        ("orders_attributed", str(len(b["orders"]))), ("orders_excluded", str(excluded_n)),
        ("gross_sales", fmt(gross)), ("refunds", fmt(refunds)), ("commission_basis", fmt(basis)),
        ("commission_rate_pct", fmt_rate(rate)), ("commission_due", fmt(commission)),
        ("flat_fee_due", fmt(fee)), ("total_due", fmt(total)), ("holdback_until", holdback_until.isoformat()),
        ("status", "draft"), ("notes", ";".join(notes))])
    pay = None
    if on_list:
        pnotes = ["owner approval required before payment"]
        if rail in SELF_PAYING_RAILS:
            pnotes.append("flat fee and carried amount only, the rail pays the commission")
        if rail == "none":
            pnotes.append("no rail chosen in programme section 6")
        pay = OrderedDict([
            ("period", period), ("creator_ref", ref), ("display_name", c["display_name"]), ("rail", rail),
            ("amount", fmt(payout_amount)), ("currency", rules["currency"]), ("statement_status", "draft"),
            ("notes", ";".join(pnotes))])
    return {"ref": ref, "c": c, "b": b, "basis": basis, "rate": rate, "commission": commission, "fee": fee,
            "carry": carry_amt, "total": total, "pending_basis": pending_basis, "rail": rail, "on_list": on_list,
            "gaps": gaps, "model": model, "payout_amount": payout_amount, "excluded_n": excluded_n,
            "flags": flags, "row": row, "payout": pay}


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([r[h] for h in header])


def payout_word(d, final, export_gap, rules):
    if d["on_list"]:
        return "yes, " + fmt(d["payout_amount"])
    if d["gaps"] or export_gap:
        return "no (partial)"
    if not final:
        return "no (preview)"
    if d["payout_amount"] <= ZERO:
        return "no (the rail pays)" if d["rail"] in SELF_PAYING_RAILS and d["commission"] > ZERO else "no (nothing due)"
    if d["payout_amount"] < rules["minimum"]:
        return "no (below minimum, carried)"
    return "no"


def render_md(x):
    args, rules, detail, res, links = x["args"], x["rules"], x["detail"], x["res"], x["links"]
    cur = (" " + rules["currency"]) if rules["currency"] else ""
    p_start, p_end = month_bounds(args.period)
    L = ["# Commission statement {}, as of {}: {}".format(args.period, x["as_of"].isoformat(), x["outcome"]), ""]
    if x["partial"]:
        L.append("Outcome: partial. Something this statement needs was missing (listed under Missing in the coverage "
                 "line). No payout list row is written for anything it touched. Fix it and rerun.")
    elif x["final"]:
        L.append("Outcome: final. The holdback for {} closed on {}, so every order dated in the period has cleared "
                 "or been excluded by rule.".format(args.period, x["holdback_until"].isoformat()))
    else:
        L.append("Outcome: preview, not payable. The holdback for {0} stays open until {1}; orders inside it are listed "
                 "as pending and the payout list is empty. Rerun on or after {1} for the payable statement.".format(
                     args.period, x["holdback_until"].isoformat()))
    L += ["",
          "Every row is `draft`. Approval and payment: {} ({}). Default rail: {} (programme section 6); each creator's "
          "rail is in the table. For a creator on `collabs` or `app` the rail computes and pays its own commission, "
          "and this statement is the reconciliation of it. For `manual`, the payout list is what finance pays once "
          "the owner has approved.".format(rules["approver"], rules["approver_source"], rules["rail"]),
          "",
          "Rules applied, from the programme file: holdback {} days; attribution {}; self-referral rule {}; basis {}; "
          "partial refunds come off the basis {}; store promotion codes: {}; minimum payout {}{}; default commission "
          "rate {}. The basis is the order's {} as exported, so every discount on the order, code or automatic, is "
          "already taken off before the rate applies. Tracked orders and the basis follow the pack's shared "
          "definitions (schemas section 12).".format(
              rules["holdback"], "code first, then tracked link" if rules["links"] else "codes only",
              "applied" if rules["selfref"] else "not applied",
              "subtotal after discounts, before shipping and tax" if rules["basis"] == "subtotal" else "order total",
              rules["refund_note"], rules["promo_note"],
              fmt(rules["minimum"]), cur, (fmt_rate(rules["rate"]) + " percent") if rules["rate"] is not None else "not set",
              "Subtotal" if rules["basis"] == "subtotal" else "Total"),
          "",
          "Labels: order counts, sales, refunds and basis are Measured (the Shopify orders export{}). Rates, flat fees "
          "and the minimum payout are User-provided (roster, programme sections 4 and 6). Commission, fees and totals "
          "are the script's arithmetic on those two. Nothing here is Estimated.".format(
              ", and the link file for link-attributed orders" if res["link_used"] else ""),
          "", "## Per creator", ""]
    if detail:
        L.append("| creator | rail | attributed | excluded | pending | basis | rate | commission | flat fee | carried in | total due | payout list |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for d in detail:
            L.append("| {} {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                d["ref"], d["c"]["display_name"], d["rail"], len(d["b"]["orders"]), d["excluded_n"],
                len(d["b"]["pending"]), fmt(d["basis"]), fmt_rate(d["rate"]), fmt(d["commission"]), fmt(d["fee"]),
                fmt(d["carry"]), fmt(d["total"]), payout_word(d, x["final"], bool(x["gaps_export"]), rules)))
        L += ["", "{}: {}{}. On the payout list: {}{}.".format(
            "Total due across the statement" if x["final"] else "Total so far (preview, not payable)",
            fmt(sum((d["total"] for d in detail), ZERO)), cur,
            fmt(sum((Decimal(p["amount"]) for p in x["payout"]), ZERO)), cur)]
    else:
        L.append("No creator has an attributed order, a fee milestone or a carried amount in {}.".format(args.period))
    quiet = sorted(r["creator_ref"] for r in x["creators"].values() if r["status"] == ACTIVE and r["creator_ref"] not in x["per"])
    if quiet:
        L += ["", "Active creators with nothing attributed in the period: {}.".format(", ".join(quiet))]

    L += ["", "## Exclusions by rule", ""]
    counts = OrderedDict((k, [0, ZERO]) for k in REASONS)
    for d in detail:
        for k, v in d["b"]["excluded"].items():
            counts[k][0] += len(v)
            counts[k][1] += sum((money(o.get("subtotal")) or ZERO for o in v), ZERO)
    if any(n for n, _ in counts.values()):
        L += ["| reason | orders | subtotal not commissioned |", "|---|---|---|"]
        L += ["| {} | {} | {} |".format(REASONS[k], n, fmt(a)) for k, (n, a) in counts.items() if n]
    else:
        L.append("None.")

    L += ["", "## Pending inside the holdback", ""]
    pend = [(d["ref"], o, why, s - r) for d in detail for (o, why, s, r) in d["b"]["pending"]]
    if pend:
        L += ["Orders inside the holdback: {}, basis {}{}, not yet commissionable. Each clears on the date shown unless "
              "it is refunded first.".format(len(pend), fmt(sum((p[3] for p in pend), ZERO)), cur), "",
              "| creator | order | basis | clears on |", "|---|---|---|---|"]
        L += ["| {} | {} | {} | {} |".format(ref, o["name"], fmt(bs), why) for ref, o, why, bs in pend]
    else:
        L.append("None." + (" The holdback has closed." if x["final"] else ""))

    L += ["", "## Needs a person", ""]
    items = []
    for d in detail:
        items += ["- {}: {}.".format(d["ref"], g) for g in d["gaps"]]
        items += ["- {}: {}; the owner decides before approving.".format(d["ref"], f) for f in d["flags"]]
        if x["final"] and not x["gaps_export"] and not d["gaps"] and ZERO < d["payout_amount"] < rules["minimum"]:
            items.append("- {}: {}{} is below the minimum payout of {}; carried forward to the next statement.".format(
                d["ref"], fmt(d["payout_amount"]), cur, fmt(rules["minimum"])))
    items += ["- {}.".format(p) for p in x["person"]]
    items += ["- {}: carried a creator code and another creator's link; the code won (programme section 5).".format(o)
              for o in res["overridden"]]
    items += ["- {}: carries the codes of two active creators; not attributed until a person decides.".format(o)
              for o in res["conflicts"]]
    items += ["- {}: two creators in the link file; not attributed by link.".format(o) for o in links["conflict"]]
    L += items or ["Nothing."]

    L += ["", "## Unattributed codes", ""]
    if res["unattributed"]:
        L += ["Codes on orders dated in the period that belong to no active creator. The script attributes none of "
              "them; a person decides what each one is.", "",
              "| code | orders | subtotal | known owner | orders attributed to a creator another way |", "|---|---|---|---|---|"]
        L += ["| {} | {} | {} | {} | {} |".format(c, i["orders"], fmt(i["subtotal"]),
                                                  i["owner"] or "none on the roster or code plans", i["attributed"])
              for c, i in res["unattributed"].items()]
    else:
        L.append("None.")
    if res["promo"]:
        L += ["", "Store promotion codes from programme section 5, not creators' and not listed above: {}.".format(
            "; ".join("{} on {} orders, subtotal {} ({} of them attributed to a creator another way)".format(
                c, i["orders"], fmt(i["subtotal"]), i["attributed"]) for c, i in res["promo"].items()))]

    L += ["", "## Link attribution", "", "Link file: {}.".format(links["state"])]
    if links["present"]:
        L.append("Orders attributed by link: {}. Rows whose order is in no export: {}. Rows whose order is dated "
                 "outside {}: {}. Rows for a creator who is not active or not on the roster: {}. Rows with a source "
                 "other than collabs, app, api or manual: {}.".format(
                     res["link_used"], lst(x["link_missing"]), args.period, lst(x["link_outside"]),
                     lst(links["not_active"]), links["bad_source"]))

    L += ["", "## What the exports carried", ""]
    if x["dates"]:
        L.append("{} distinct orders read across the exports, dated {} to {}; {} dated in {}. The script has no "
                 "independent count of the store's orders: compare {} with the order count the Shopify admin shows for "
                 "{} to {}.".format(len(x["all_orders"]), min(x["dates"]).isoformat(), max(x["dates"]).isoformat(),
                                    len(x["in_period"]), args.period, len(x["in_period"]), p_start.isoformat(),
                                    p_end.isoformat()))
        attributed = sum(len(d["b"]["orders"]) for d in detail)
        parts = [attributed, len(res["conflicts"]), len(res["stray_only"]), len(res["no_code"])]
        L += ["", "Each order dated in the period sits in one place: attributed to a creator {}, two creators' codes "
              "{}, only codes that are no active creator's (store promotions included) {}, no code and no link {}; together {} of {}{}.".format(
                  *parts, sum(parts), len(x["in_period"]),
                  "" if sum(parts) == len(x["in_period"]) else " (these should match; report the difference)")]
    else:
        L.append("No order with a readable date was found in the exports.")
    if not x["in_period"]:
        L += ["", "No orders in the exports are dated in {}; the script looked and found none.".format(args.period)]
    L += ["", "The script read only the columns named in the skill's references/orders-export-columns.md. Free text in "
              "the exports (Notes, Note Attributes, Tags and the rest) was not read, and nothing found in an input is "
              "treated as an instruction.", ""]
    used = list(x["used"])
    if not x["carry_note"].startswith("earlier statements"):
        used.append("carried amounts: " + x["carry_note"])
    missing = list(x["gaps_export"]) + ["{}: {}".format(d["ref"], g) for d in detail for g in d["gaps"]]
    L.append("Coverage: used {}. Missing: {}. Could not judge: {}. Fine: {}.".format(
        "; ".join(used), "; ".join(missing) if missing else "nothing",
        "; ".join(x["could_not_judge"]) if x["could_not_judge"] else "nothing",
        "; ".join(x["fine"]) if x["fine"] else "nothing else checked"))
    return "\n".join(L) + "\n"


def lst(items):
    return "{} ({})".format(len(items), ", ".join(items)) if items else "0"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Compute what each creator is owed for one period from the Shopify orders export(s), under the "
                    "programme file's rules. Writes payouts/<period>/statement.csv, payout-list.csv and statement.md "
                    "inside the workspace. Pays nothing; every row is draft.",
        epilog="Exit 0: final or preview statement. Exit 2: partial (the output says what was missing). Exit 1: bad "
               "input (stderr says what to fix; nothing is written). No network.")
    ap.add_argument("workspace", help="the programme workspace folder")
    ap.add_argument("--period", required=True, help="calendar month of order dates, YYYY-MM")
    ap.add_argument("--as-of", required=True, dest="as_of",
                    help="the run date, YYYY-MM-DD; decides which orders are still inside the holdback")
    ap.add_argument("--export", nargs="+", action="extend", default=None, metavar="PATH",
                    help="orders export CSV file(s); default: every orders export CSV in exports/")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except BadInput as e:
        print("bad input: " + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
