#!/usr/bin/env python3
"""Check a partnership-agreement terms sheet against the roster and the programme file.

  python3 -I check_terms.py <workspace> <terms.md>
  python3 -I check_terms.py <workspace> --show <creator_ref>

The first form checks a drafted sheet. The second prints the roster row and every programme
value a sheet copies, so the values are copied rather than recalled; it exits 1 when the row is
closed (stop S2) and 2 when the row has no complete agreed deal (stop S3). Nothing is written.

Exit 0: every section present and filled, figures match the roster, rules match the programme.
Exit 1: something must be fixed; each problem is printed as FAIL with what to do.
Exit 2: nothing to fix, but the sheet is unfinished: TBD values remain, or a comparison could
        not run because the programme leaves the value blank. Each is printed.
"""

import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the skill folder free of caches
sys.path.insert(0, str(Path(__file__).resolve().parent))
from terms_lib import (  # noqa: E402
    CREATOR_REF, FORMATS, HEADING, MODELS, PLATFORMS, InputError, Programme, is_noneish,
    Parser, contains_run, norm, read_roster, read_text, roster_row, same_amount, same_text, same_window,
    to_decimal, window_months_from_posting,
)

# The sheet's sections and the lines each must keep. Source: assets/terms-sheet-template.md and
# references/terms-checklist.md (the IDs there are these section numbers). The fixture runner
# checks the template against this list, so a change here needs the same change there.
SECTIONS = [
    (1, "Parties", ["Brand legal entity", "Brand signs as", "Creator ref", "Creator display name",
                    "Creator legal name and notice address", "Acting for the creator", "Sends the terms"]),
    (2, "Term and renewal", ["Campaign", "Start", "End", "Renewal"]),
    (3, "Deliverables and dates", ["Brief", "Platform conditions from programme section 3",
                                   "Minimum time live, days"]),
    (4, "Compensation", ["Model", "Commission rate, percent of the basis", "Commission basis",
                         "Customer discount on the creator's code",
                         "Flat fee per deliverable set, store currency", "Flat fee paid",
                         "Owner approval for a flat or hybrid deal", "Product supplied",
                         "Store currency", "Holdback, days", "Self-referral", "Minimum payout",
                         "Statement and payout cadence", "Payout rail",
                         "Dispute window for a statement, days"]),
    (5, "Code, link and attribution", ["Code", "Link", "Who owns the code", "Attribution",
                                       "Click window", "Code use"]),
    (6, "Usage rights", ["Ownership", "Owned channels the brand may reuse content on", "Window",
                         "Paid reuse", "Paid reuse platforms", "Edits the brand may make", "Credit"]),
    (7, "Exclusivity", ["Category", "Period", "Payment for exclusivity"]),
    (8, "Disclosure", ["Wording", "Placement", "Video and audio", "Platform tool",
                       "Words that do not count", "Free product", "Brand's check", "Why"]),
    (9, "Product claims", ["Rule", "Approved statements", "Forbidden", "Compatibility statements",
                           "Own experience", "Why"]),
    (10, "Approval, correction and takedown", ["Draft before posting", "Review",
                                               "Brand's turnaround, days", "Creative voice",
                                               "Correction", "Correction time, days", "Takedown",
                                               "Takedown time, days", "Who asks"]),
    (11, "Creator eligibility and audience rules", ["Creator's age", "Audience", "Age setting",
                                              "Evidence the brand requires"]),
    (12, "Independent contractor and tax", ["Status", "Taxes", "Tax forms"]),
    (13, "Confidentiality", ["Confidential", "Never restricted", "Period"]),
    (14, "Termination", ["Notice without cause, days", "Without cause", "For cause", "On termination",
                         "Survives"]),
    (15, "Governing law and disputes", ["Governing law", "Disputes"]),
    (16, "Departures and counsel note", ["Departures from the programme file",
                                         "Clauses outside the template",
                                         "Counsel review of this template", "Sheet may go to the creator",
                                         "Questions for counsel",
                                         "Counsel note"]),
    (17, "Coverage", []),
]
CHECKED = range(1, 17)        # section 17 is written after the check
# Sheet lines that copy a day count from the programme file: (sheet section, sheet label,
# programme section, pattern for the programme line's label). Template 0.1.2 of program-setup.
DAY_COUNTS = [
    (3, "Minimum time live, days", 11, r"^minimum time a post stays live"),
    (4, "Dispute window for a statement, days", 11, r"^dispute window on a commission statement"),
    (10, "Brand's turnaround, days", 11, r"^brand approval turnaround"),
    (10, "Correction time, days", 8, r"^time a creator has to correct"),
    (10, "Takedown time, days", 11, r"^time allowed to take down"),
    (14, "Notice without cause, days", 11, r"^notice period for ending without cause"),
]
NO_TBD = (8, 9)               # disclosure and claims must be complete before anything else
PLACEHOLDER = re.compile(r"<(?!https?:)[^<>\n]{1,120}>")
TBD = re.compile(r"\bTBD\b")
FIELD = re.compile(r"^- ([^:]+):\s*(.*)$")
CHILD = re.compile(r"^\s+- (.*)$")
RULE_CELL = re.compile(r"^:?-{3,}:?$")
# Words that make a usage window unbounded (references/red-flags.md, RF1).
UNBOUNDED = re.compile(r"perpetu|unlimited|forever|indefinite|no end|irrevocab", re.I)
# Words that make the term renew by itself (references/red-flags.md, RF4).
AUTO_RENEW = re.compile(r"auto|automatic|evergreen|rolls? over", re.I)
# Words that mean exclusivity is not separately paid for (references/red-flags.md, RF2).
UNPAID = re.compile(r"includ|commission only|no (?:additional|extra|separate)|free of charge|\bnil\b|\bzero\b|without (?:payment|charge)", re.I)
# Roster states in which no terms are drafted (schemas section 4).
CLOSED_STATUS = ("declined", "ended", "excluded")


class Report:
    """Collects messages by kind; a message already recorded is not repeated."""

    def __init__(self):
        self.fails, self.tbds, self.skips, self.notes = [], [], [], []

    @staticmethod
    def _add(bucket, msg):
        if msg not in bucket:
            bucket.append(msg)

    def fail(self, msg):
        self._add(self.fails, msg)

    def tbd(self, msg):
        self._add(self.tbds, msg)

    def skip(self, msg):
        self._add(self.skips, msg)

    def note(self, msg):
        self._add(self.notes, msg)


def parse_sheet(text):
    head, sections, duplicates, current, in_table, header = [], {}, [], None, False, None
    for number, raw in enumerate(text.splitlines(), 1):
        m = HEADING.match(raw)
        if m:
            n = int(m.group(1))
            if n in sections:
                duplicates.append(n)
            current = {"title": m.group(2), "fields": [], "rows": [], "lines": []}
            sections[n] = current
            in_table = False
            continue
        if current is None:
            head.append((number, raw))
            continue
        current["lines"].append((number, raw))
        line = raw.rstrip()
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not in_table:
                in_table, header = True, cells
                continue
            if all(RULE_CELL.match(c) for c in cells if c):
                continue
            target = current["fields"][-1]["rows"] if current["fields"] else current["rows"]
            target.append({"line": number, "cells": cells, "header": header})
            continue
        in_table = False
        fm = FIELD.match(line)
        if fm:
            current["fields"].append({"label": fm.group(1).strip(), "value": fm.group(2).strip(),
                                      "children": [], "rows": [], "line": number})
            continue
        cm = CHILD.match(line)
        if cm and current["fields"]:
            current["fields"][-1]["children"].append((number, cm.group(1).strip()))
    return head, sections, duplicates


def find(fields, label):
    want = label.lower()
    for f in fields:
        if f["label"].lower() == want:
            return f
    for f in fields:
        if f["label"].lower().startswith(want + " "):
            return f
    return None


def filled(field):
    return bool(field["value"] or field["children"] or field["rows"])


def field_text(field):
    parts = [field["value"]] + [c for _, c in field["children"]]
    for row in field["rows"]:
        parts.extend(row["cells"])
    return " ".join(p for p in parts if p)


def is_tbd(text):
    return bool(TBD.search(text or ""))


def unset(text):
    """TBD or still a template placeholder: not a value to compare (placeholders already fail)."""
    return is_tbd(text) or bool(PLACEHOLDER.search(text or ""))


def check_structure(head, sections, duplicates, rep):
    for n in duplicates:
        rep.fail(f"section {n} appears more than once; keep one copy.")
    for n, title, labels in SECTIONS:
        if n not in sections:
            rep.fail(f"section {n}. {title} is missing; copy it from assets/terms-sheet-template.md.")
            continue
        sec = sections[n]
        if norm(sec["title"]) != norm(title):
            rep.note(f"section {n} is titled '{sec['title']}', the template says '{title}'.")
        for label in labels:
            if not find(sec["fields"], label):
                rep.fail(f"section {n}: the line '{label}' is missing; every term stays in the sheet, filled or TBD.")
    for number, raw in head + [x for n in CHECKED if n in sections for x in sections[n]["lines"]]:
        m = PLACEHOLDER.search(raw)
        if m:
            rep.fail(f"line {number}: {m.group(0)} is still a template placeholder; fill it from its source or write TBD and who decides.")
    for n in CHECKED:
        if n not in sections:
            continue
        for f in sections[n]["fields"]:
            if not filled(f):
                rep.fail(f"section {n}, '{f['label']}': empty; fill it or write TBD and who decides.")


def count_tbds(sections, rep):
    per = {}
    for n in CHECKED:
        if n not in sections:
            continue
        sec = sections[n]
        items = []
        for f in sec["fields"]:
            if is_tbd(f["value"]):
                items.append((f["line"], f["label"], f["value"]))
            for number, child in f["children"]:
                if is_tbd(child):
                    items.append((number, f["label"], child))
            for row in f["rows"]:
                if any(is_tbd(c) for c in row["cells"]):
                    items.append((row["line"], f["label"], " | ".join(row["cells"])))
        for row in sec["rows"]:
            if any(is_tbd(c) for c in row["cells"]):
                items.append((row["line"], "table", " | ".join(row["cells"])))
        for number, label, text in items:
            if n in NO_TBD:
                rep.fail(f"section {n}, '{label}' (line {number}) is TBD; disclosure and claims are copied from programme sections 8 and 7 and cannot wait.")
            else:
                rep.tbd(f"section {n}, '{label}' (line {number}): {text}")
        if items:
            per[n] = len(items)
    return per


def departure_listed(sections, programme_section):
    sec = sections.get(16)
    if not sec:
        return False
    field = find(sec["fields"], "Departures from the programme file")
    if field is None or PLACEHOLDER.search(field_text(field)):
        return False
    return bool(re.search(rf"programme section {programme_section}\b", field_text(field), re.I))


def compare(rep, sections, n, what, found, prog_value, sheet_field, equal):
    """Compare one sheet value with the programme's value for it."""
    if sheet_field is None:
        return
    sheet_value = field_text(sheet_field)
    if PLACEHOLDER.search(sheet_value):
        return
    if is_tbd(sheet_value):
        if prog_value:
            rep.note(f"{what}: the sheet says TBD; programme section {n} has '{prog_value}'.")
        return
    if not found:
        rep.skip(f"{what}: no matching line in programme section {n}; not compared.")
        return
    if not prog_value:
        if departure_listed(sections, n):
            rep.note(f"{what}: programme section {n} is blank; the sheet's value is listed in section 16 for the owner.")
        else:
            rep.fail(f"{what}: programme section {n} is blank but the sheet says '{sheet_value}'; write TBD (owner), or list it in section 16 as a departure naming programme section {n}.")
        return
    if equal(sheet_value, prog_value):
        return
    if departure_listed(sections, n):
        rep.note(f"{what}: differs from programme section {n} ('{prog_value}'); listed in section 16 for the owner.")
    else:
        rep.fail(f"{what}: the sheet says '{sheet_value}', programme section {n} says '{prog_value}'; copy the programme's value, or list the difference in section 16 naming programme section {n}.")


def same_number(a, b):
    return to_decimal(a) is not None and to_decimal(a) == to_decimal(b)


def check_compensation(rep, sections, row):
    sec = sections.get(4)
    if not sec:
        return None
    get = lambda label: find(sec["fields"], label)
    model_f = get("Model")
    model = norm(model_f["value"]).split(" ")[0] if model_f and model_f["value"] else ""
    roster_model = row["compensation_model"].lower()
    if model_f and not unset(model_f["value"]):
        if model not in MODELS:
            rep.fail(f"section 4, Model: '{model_f['value']}' is not one of {', '.join(MODELS)}.")
        elif not roster_model:
            rep.fail("section 4, Model: the roster row has no compensation_model; record the agreed deal with creator-roster's update command first.")
        elif model != roster_model:
            rep.fail(f"section 4, Model: the sheet says {model}, the roster says {roster_model}; fix whichever is wrong. The roster is what commission-statement pays from.")
        if model == "none":
            rep.fail("section 4, Model: none means there is no deal to write terms for.")
    use = model if model in MODELS else roster_model
    pairs = [("Commission rate, percent of the basis", "commission_rate_pct", ("cpa", "hybrid")),
             ("Flat fee per deliverable set, store currency", "flat_fee", ("flat", "hybrid"))]
    for label, column, models in pairs:
        f = get(label)
        if not f or not f["value"] or unset(f["value"]):
            if f and unset(f["value"]) and row[column]:
                rep.note(f"section 4, {label}: TBD; the roster has {row[column]}.")
            continue
        sheet, roster = f["value"], row[column]
        if use in models:
            if not roster:
                rep.fail(f"section 4, {label}: the roster's {column} is empty; record it with creator-roster's update command, or write TBD.")
            elif not same_number(sheet, roster):
                rep.fail(f"section 4, {label}: the sheet says {sheet}, the roster says {roster}; fix whichever is wrong.")
        elif not is_noneish(sheet):
            rep.fail(f"section 4, {label}: a {use} deal carries none here, but the sheet says {sheet}.")
        elif roster and not is_noneish(roster):
            rep.fail(f"section 4, {label}: the roster's {column} is {roster} on a {use} deal; correct the roster or the model.")
    paid_when = get("Flat fee paid")
    if paid_when and paid_when["value"] and use in ("flat", "hybrid") and is_noneish(paid_when["value"]):
        rep.fail("section 4, Flat fee paid: a flat or hybrid deal says when the fee is paid, for example after the brand records the post as live.")
    approval = get("Owner approval for a flat or hybrid deal")
    if approval and approval["value"] and use in ("flat", "hybrid"):
        value = approval["value"]
        if is_noneish(value):
            rep.fail("section 4, Owner approval: a flat or hybrid deal needs the owner's approval (programme section 4); write TBD (owner) until it is given, then the date.")
        elif not unset(value) and not re.search(r"\d{4}-\d{2}-\d{2}", value):
            rep.fail("section 4, Owner approval: name the role and the date of the approval, for example 'owner, 2026-10-20'.")
    return use


def check_platforms(rep, sections, prog):
    sec = sections.get(3)
    if not sec:
        return
    rows = sec["rows"]
    if not rows:
        rep.fail("section 3: the deliverables table has no rows; add one per deliverable, with TBD in cells not yet agreed.")
    conditions = find(sec["fields"], "Platform conditions from programme section 3")
    needs_conditions = []
    for row in rows:
        cells = row["cells"] + [""] * 7
        platform, fmt = cells[1].strip().lower(), cells[2].strip().lower()
        if fmt and not unset(fmt) and fmt not in FORMATS:
            rep.fail(f"section 3, line {row['line']}: format '{cells[2]}' is not one of {', '.join(FORMATS)}.")
        if not platform or unset(platform):
            continue
        if platform not in PLATFORMS:
            rep.fail(f"section 3, line {row['line']}: platform '{cells[1]}' is not one of {', '.join(PLATFORMS)}.")
            continue
        hit = prog.platform(platform)
        if hit is None:
            rep.skip(f"section 3, {platform}: programme section 3 has no row for it and no 'other' row; not compared.")
            continue
        label, organic, _paid, note = hit
        if note:
            rep.note(f"section 3: {note}.")
        if organic == "no":
            rep.fail(f"section 3, {platform}: programme section 3 says creator posts there are 'no' ({label}); take the deliverable out, or the owner changes section 3 first.")
        elif organic in ("", "unknown"):
            rep.skip(f"section 3, {platform}: programme section 3 has '{organic or 'blank'}' for creator posts; the owner decides before this deliverable is offered.")
        elif organic == "with conditions":
            needs_conditions.append(platform)
    if needs_conditions and conditions and is_noneish(field_text(conditions)):
        rep.fail(f"section 3: programme section 3 sets conditions for {', '.join(needs_conditions)}; copy them into 'Platform conditions from programme section 3'.")


def check_usage_and_exclusivity(rep, sections, prog):
    sec6, sec7 = sections.get(6), sections.get(7)
    if sec6:
        window = find(sec6["fields"], "Window")
        if window and UNBOUNDED.search(field_text(window)):
            rep.fail(f"section 6, Window: '{field_text(window)}' has no end; the roster and content-reuse need an end date or a period with an end.")
        paid = find(sec6["fields"], "Paid reuse")
        platforms = find(sec6["fields"], "Paid reuse platforms")
        paid_value = norm(paid["value"]).split(" ")[0] if paid and paid["value"] else ""
        if paid and not unset(paid["value"]) and paid_value not in ("yes", "no"):
            rep.fail(f"section 6, Paid reuse: write yes or no (or TBD), not '{paid['value']}'.")
        if paid_value == "no" and platforms and not is_noneish(field_text(platforms)):
            rep.fail("section 6: paid reuse is no but paid reuse platforms are listed; make them agree.")
        if paid_value == "yes" and platforms and not unset(field_text(platforms)):
            names = [p.strip().lower() for p in re.split(r"[;,]", field_text(platforms)) if p.strip()]
            if not names or all(is_noneish(p) for p in names):
                rep.fail("section 6: paid reuse is yes but no platform is named.")
            for p in names:
                if p not in PLATFORMS:
                    rep.fail(f"section 6, Paid reuse platforms: '{p}' is not one of {', '.join(PLATFORMS)}.")
                    continue
                hit = prog.platform(p)
                if hit is None:
                    rep.skip(f"section 6, {p}: no row in programme section 3; not compared.")
                    continue
                _label, _organic, paid_col, _note = hit
                if paid_col == "no":
                    rep.fail(f"section 6, {p}: programme section 3 says paid use by the brand there is 'no'.")
                elif paid_col in ("", "unknown"):
                    rep.skip(f"section 6, {p}: programme section 3 has '{paid_col or 'blank'}' for paid use; the owner decides first.")
        if window:
            found, value = prog.field(11, r"usage.rights|reus")
            compare(rep, sections, 11, "section 6, Window", found, value, window, same_window)
    if sec7:
        category = find(sec7["fields"], "Category")
        payment = find(sec7["fields"], "Payment for exclusivity")
        if category and category["value"] and not unset(category["value"]) and not is_noneish(category["value"]):
            pay = payment["value"] if payment else ""
            if not unset(pay) and (is_noneish(pay) or UNPAID.search(pay)):
                rep.fail("section 7: exclusivity is set but nothing is paid for it; state the payment, or set the category to none.")
        if category:
            found, value = prog.field(11, r"exclusivity")
            compare(rep, sections, 11, "section 7, Category", found, value, category,
                    lambda a, b: (is_noneish(a) and is_noneish(b)) or (not is_noneish(a) and same_text(a, b)))


QUOTED = re.compile(r"[\"\u201c]([^\"\u201d]+)[\"\u201d]")


def disclosure_entries(prog):
    """Programme section 8's required wording as (label words, full text, quoted wording) per
    platform entry: from the marked lines under the field (program-setup's form), or from the
    field's own line split at ';' when the owner wrote it on one line."""
    found, own = prog.field(8, r"^required disclosure")
    if not found:
        return None
    lines = prog.field_details(8, r"^required disclosure")
    if not lines and own:
        lines = [part.strip() for part in own.split(";") if part.strip()]
    entries = []
    for line in lines:
        label, sep, rest = line.partition(":")
        if sep and len(label.split()) <= 6 and not re.search(r"[\"\u201c\u201d]", label):
            words, text = set(norm(label).split()), rest.strip()
        else:
            words, text = set(), line.strip()
        quoted = QUOTED.search(text)
        entries.append((words, text, quoted.group(1) if quoted else ""))
    return entries


def entry_for(entries, platform):
    names = {platform, platform + "s"}
    for words, text, quoted in entries:
        if words & names:
            return text, quoted
    return None


def check_disclosure(rep, sections, prog):
    """The sheet's wording is, whole, a wording programme section 8 gives, and it carries the
    wording for every platform the sheet's deliverables use."""
    sec = sections.get(8)
    if not sec:
        return
    entries = disclosure_entries(prog)
    if entries is None:
        rep.skip("section 8: programme section 8 has no required-disclosure line; wording not compared.")
        return
    if not entries:
        rep.fail("programme section 8 has no disclosure wording; the owner fills it through program-setup before any terms are drafted.")
        return
    wording = find(sec["fields"], "Wording")
    if not wording or unset(field_text(wording)):
        return
    pieces = ([wording["value"]] if wording["value"] else []) + [c for _, c in wording["children"]]
    allowed = [x for _, text, quoted in entries for x in (text, quoted) if x]
    for piece in pieces:
        label, sep, rest = piece.partition(":")
        bare = rest if sep and norm(label) in {p for p in PLATFORMS} | {p + "s" for p in PLATFORMS} else piece
        if not any(same_text(bare, a) for a in allowed):
            rep.fail(f"section 8, Wording: '{piece}' is not, whole, a wording in programme section 8; copy the quoted wording for the platform, or its whole line, exactly.")
    platforms = {row["cells"][1].strip().lower() for row in sections.get(3, {}).get("rows", [])
                 if len(row["cells"]) > 1 and row["cells"][1].strip().lower() in PLATFORMS}
    text = " ".join(pieces)
    for platform in sorted(platforms):
        hit = entry_for(entries, platform)
        if hit is None:
            if len(entries) > 1 or entries[0][0]:
                rep.skip(f"section 8: programme section 8 has no wording line for {platform}; not compared.")
            continue
        full, quoted = hit
        if not (contains_run(text, quoted) if quoted else contains_run(text, full)):
            rep.fail(f"section 8, Wording: the sheet has a {platform} deliverable but not programme section 8's {platform} wording ('{quoted or full}').")


def check_claims(rep, sections, prog):
    sec = sections.get(9)
    if not sec:
        return
    field = find(sec["fields"], "Approved statements")
    if not field:
        return
    approved = prog.approved_statements()
    targets = set()
    for body, part in approved:
        targets.update({norm(body), norm(part)})
    rows = field["rows"]
    if not rows:
        if field["value"] and norm(field["value"]).startswith("none"):
            rep.note("section 9: no approved statements; the creator may make no product claim until the owner clears one.")
        elif field["value"]:
            rep.fail("section 9, Approved statements: put the statements in the table, one per row, exactly as in programme section 7.")
        return
    for row in rows:
        statement = row["cells"][0].strip().strip('"“”') if row["cells"] else ""
        if not statement or unset(statement):
            continue
        if norm(statement).startswith("none"):
            rep.note("section 9: no approved statements; the creator may make no product claim until the owner clears one.")
            continue
        if not approved:
            rep.fail(f"section 9, line {row['line']}: programme section 7 lists no approved statements, so '{statement}' cannot be one.")
        elif norm(statement) not in targets:
            rep.fail(f"section 9, line {row['line']}: '{statement}' is not, word for word, a statement under Approved in programme section 7; copy one from there or take it out. Approved lines: "
                     + "; ".join(b for b, _ in approved))


def check_programme_values(rep, sections, prog, model):
    sec4, sec15 = sections.get(4), sections.get(15)
    gift = model == "gift"
    if sec4:
        f = find(sec4["fields"], "Store currency")
        found, value = prog.field(1, r"^store currency")
        compare(rep, sections, 1, "section 4, Store currency", found, value, f, same_text)
        if gift:
            rep.note("section 4: a gift deal; commission basis, discount and holdback are not compared.")
        else:
            f = find(sec4["fields"], "Commission basis")
            found, value = prog.field(4, r"^commission basis")
            compare(rep, sections, 4, "section 4, Commission basis", found, value, f, same_text)
            f = find(sec4["fields"], "Customer discount on the creator's code")
            found, value = prog.field(4, r"^customer.facing discount|^customer discount")
            compare(rep, sections, 4, "section 4, Customer discount", found, value, f, same_amount)
            f = find(sec4["fields"], "Holdback, days")
            found, value = prog.field(5, r"^holdback")
            compare(rep, sections, 5, "section 4, Holdback", found, value, f, same_number)
    if sec15:
        f = find(sec15["fields"], "Governing law")
        found, value = prog.field(11, r"governing")
        compare(rep, sections, 11, "section 15, Governing law", found, value, f, same_text)
    # Day counts the programme sets (template 0.1.2: section 8 correction time, section 11 the rest).
    for sheet_n, label, prog_n, pattern in DAY_COUNTS:
        sec = sections.get(sheet_n)
        if sec:
            found, value = prog.field(prog_n, pattern)
            compare(rep, sections, prog_n, f"section {sheet_n}, {label}", found, value, find(sec["fields"], label), same_number)
    sec16 = sections.get(16)
    if sec16:
        f = find(sec16["fields"], "Sheet may go to the creator")
        found, value = prog.field(11, r"^whether the terms sheet")
        compare(rep, sections, 11, "section 16, Sheet may go to the creator", found, value, f, same_text)
        check_counsel_record(rep, sections, prog, find(sec16["fields"], "Counsel review of this template"))


def check_counsel_record(rep, sections, prog, field):
    """The sheet repeats programme section 11's counsel review record, or says none is recorded."""
    if field is None or not field["value"] or PLACEHOLDER.search(field["value"]):
        return
    value = field_text(field)
    found, record = prog.field(11, r"^counsel review record")
    says_none = norm(value).startswith("not recorded")
    if not found:
        rep.skip("section 16, Counsel review: programme section 11 has no counsel review record line; not compared.")
    elif not record:
        if not says_none:
            rep.fail(f"section 16, Counsel review: programme section 11 records no counsel review, but the sheet says '{value}'; write 'not recorded: these terms may not go to a creator yet'.")
    elif says_none:
        rep.fail(f"section 16, Counsel review: programme section 11 records '{record}'; copy that record.")
    elif not same_text(value, record):
        rep.fail(f"section 16, Counsel review: the sheet says '{value}', programme section 11 records '{record}'; copy the record exactly.")


def check_term(rep, sections):
    sec = sections.get(2)
    if sec:
        renewal = find(sec["fields"], "Renewal")
        if renewal and AUTO_RENEW.search(field_text(renewal)):
            rep.fail("section 2, Renewal: the term may not renew by itself; a further term is a new terms sheet.")


def run_check(workspace, sheet_arg, signed=None):
    ws = Path(workspace)
    if not ws.is_dir():
        raise InputError(f"{ws} is not a folder; give the workspace path first.")
    sheet_path = Path(sheet_arg)
    if not sheet_path.is_absolute() and not sheet_path.exists():
        sheet_path = ws / sheet_arg
    text = read_text(sheet_path)
    prog = Programme(ws)
    rows = read_roster(ws)
    rep = Report()
    head, sections, duplicates = parse_sheet(text)
    status = next((raw.split(":", 1)[1].strip() for _, raw in head if raw.lower().startswith("status:")), "")
    if not status:
        rep.note("no Status line at the top; the template's first lines say 'Status: draft'.")
    check_structure(head, sections, duplicates, rep)
    per = count_tbds(sections, rep)
    row, model = None, ""
    ref_field = find(sections.get(1, {}).get("fields", []), "Creator ref")
    ref = ref_field["value"].strip() if ref_field else ""
    if not ref or unset(ref) or ref.startswith("<"):
        rep.fail("section 1, Creator ref: fill it with the creator's roster ref; nothing can be compared without it.")
    elif not CREATOR_REF.match(ref):
        rep.fail(f"section 1, Creator ref: '{ref}' is not a roster ref (c- and six lower-case letters or digits).")
    else:
        try:
            row = roster_row(rows, ref)
        except InputError as err:
            rep.fail(f"section 1, Creator ref: {err}")
    if row:
        if row["status"] in CLOSED_STATUS or row["brand_safety_flag"] == "exclude":
            rep.fail(f"the roster has {ref} as status '{row['status']}', brand safety '{row['brand_safety_flag'] or 'none'}'; no terms are drafted for this creator unless the owner reopens the row with creator-roster.")
        elif row["brand_safety_flag"] == "review":
            rep.note(f"the roster flags {ref} for brand-safety review; the owner clears it before terms go out.")
        model = check_compensation(rep, sections, row) or ""
        name = find(sections.get(1, {}).get("fields", []), "Creator display name")
        if name and name["value"] and row["display_name"] and not same_text(name["value"], row["display_name"]):
            rep.fail(f"section 1, Creator display name: the sheet says '{name['value']}', the roster says '{row['display_name']}'.")
    check_term(rep, sections)
    check_platforms(rep, sections, prog)
    check_usage_and_exclusivity(rep, sections, prog)
    check_disclosure(rep, sections, prog)
    check_claims(rep, sections, prog)
    check_programme_values(rep, sections, prog, model)

    print(f"check_terms: {sheet_path}")
    print(f"against: {ws / 'data' / 'creators.csv'} and {prog.path}")
    deliverables = len(sections.get(3, {}).get("rows", []))
    fields = sum(len(sections[n]["fields"]) for n in sections)
    print(f"read: {len(sections)} sections, {fields} lines, {deliverables} deliverable rows; status '{status or 'none'}'; roster row {'found' if row else 'not used'}")
    for label, items in (("FAIL", rep.fails), ("TBD", rep.tbds), ("NOT COMPARED", rep.skips), ("NOTE", rep.notes)):
        for item in items:
            print(f"{label:<13}{item}")
    total = sum(per.values())
    if per:
        print("TBD by section: " + ", ".join(f"{n}: {c}" for n, c in sorted(per.items())) + f" (total {total})")
    else:
        print("TBD by section: none")
    if rep.fails:
        code, word = 1, "FAIL"
    elif rep.tbds or rep.skips:
        code, word = 2, "INCOMPLETE"
    else:
        code, word = 0, "PASS"
    if row and code != 1:
        print_handoff(ws, sheet_path, sections, ref, signed)
    print(f"RESULT: {word} (exit {code}): {len(rep.fails)} to fix, {total} TBD, {len(rep.skips)} not compared. Section 17 is not checked.")
    return code


def print_handoff(ws, sheet_path, sections, ref, signed):
    """The creator-roster command the programme lead runs once the terms are agreed in writing
    (schemas section 4). Nothing is run here."""
    try:
        rel = sheet_path.resolve().relative_to(ws.resolve()).as_posix()
    except ValueError:
        rel = sheet_path.as_posix()
    fields = [f"status=agreed", f"agreement_date={signed or 'YYYY-MM-DD'}", f"agreement_file={rel}"]
    sec7 = sections.get(7, {}).get("fields", [])
    category, period = find(sec7, "Category"), find(sec7, "Period")
    if category and not is_noneish(category["value"]) and period:
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", period["value"])
        fields.append(f"exclusivity_until={dates[-1] if dates else 'YYYY-MM-DD'}")
    window = find(sections.get(6, {}).get("fields", []), "Window")
    window_text = field_text(window) if window else ""
    months = window_months_from_posting(window_text)
    note = "terms agreed in writing"
    after = []
    if months:
        note = f"rights from posting: {months} months"
        after.append("usage_rights_until stays empty: the window runs from posting; publication-tracking computes the date when the post is recorded.")
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", window_text.strip()):
        fields.append(f"usage_rights_until={window_text.strip()}")
    elif window_text and not is_tbd(window_text):
        after.append(f"usage_rights_until is not set by this command: the window '{window_text}' has no fixed end and is not a whole number of months from posting; ask the owner how it is dated.")
    script = Path(__file__).resolve().parents[2] / "creator-roster" / "scripts" / "roster.py"
    script_text = str(script) if script.is_file() else "CREATOR-ROSTER-FOLDER/scripts/roster.py"
    date_flag = f" --date {signed}" if signed else " --date YYYY-MM-DD"
    print("After the terms are agreed in writing, the programme lead runs (nothing is run here):")
    print(f'  python3 -I {script_text} {ws} update {ref} {" ".join(fields)} --note "{note}" --role "programme lead"{date_flag}')
    for line in after:
        print(f"  {line}")
    if not signed:
        print("  YYYY-MM-DD is the date the terms were agreed in writing; run this check again with --signed and that date to fill it.")


def run_show(workspace, ref):
    ws = Path(workspace)
    if not ws.is_dir():
        raise InputError(f"{ws} is not a folder; give the workspace path first.")
    if not CREATOR_REF.match(ref):
        raise InputError(f"'{ref}' is not a roster ref (c- and six lower-case letters or digits).")
    prog = Programme(ws)
    row = roster_row(read_roster(ws), ref)
    print(f"Roster row {ref} (data/creators.csv):")
    for col in ("display_name", "primary_platform", "primary_handle", "other_platforms", "status",
                "compensation_model", "commission_rate_pct", "flat_fee", "code", "affiliate_link",
                "rail", "agreement_date", "agreement_file", "usage_rights_until", "exclusivity_until"):
        print(f"  {col}: {row[col] or '(empty)'}")
    stop = 0
    if row["status"] in CLOSED_STATUS or row["brand_safety_flag"] == "exclude":
        print(f"STOP S2: the roster has {ref} as status '{row['status']}', brand safety '{row['brand_safety_flag'] or 'none'}'; no terms are drafted or reviewed unless the owner reopens the row with creator-roster.")
        stop = 1
    model = row["compensation_model"].lower()
    needs = {"cpa": ["commission_rate_pct"], "hybrid": ["commission_rate_pct", "flat_fee"], "flat": ["flat_fee"], "gift": []}
    if model not in needs or any(not row[c] for c in needs[model]):
        print(f"STOP S3 for draft mode: the roster row has no complete agreed deal (model '{model or 'empty'}'); record it with creator-roster's update command first. Review mode can continue.")
        stop = stop or 2
    print("Programme values the terms sheet copies (blank: the sheet says TBD and the owner decides):")
    asks = [(1, "store currency", r"^store currency"),
            (4, "commission rate (default)", r"^commission rate"),
            (4, "commission basis", r"^commission basis"),
            (4, "customer discount", r"^customer.facing discount|^customer discount"),
            (4, "who approves flat or hybrid", r"flat or hybrid"),
            (5, "attribution model", r"attribution model"),
            (5, "click window", r"cookie|click window"),
            (5, "holdback, days", r"^holdback"),
            (5, "self-referral rule", r"self.referral"),
            (6, "payout rail", r"rail chosen"),
            (6, "payout schedule and minimum payout", r"payout schedule"),
            (6, "who approves and who pays", r"approves a statement"),
            (8, "who checks a live post", r"who checks"),
            (9, "audience age evidence", r"audience age"),
            (9, "competitor categories", r"competitor"),
            (9, "redlines", r"redlines"),
            (11, "governing law", r"governing"),
            (11, "template location and counsel review", r"template"),
            (11, "default usage-rights window and paid reuse", r"usage.rights|reus"),
            (11, "default exclusivity", r"exclusivity"),
            (11, "counsel review record", r"^counsel review record"),
            (11, "whether the terms sheet may go to creators", r"^whether the terms sheet"),
            (11, "dispute window on a statement, days", r"^dispute window on a commission statement"),
            (11, "minimum time a post stays live, days", r"^minimum time a post stays live"),
            (11, "brand approval turnaround, days", r"^brand approval turnaround"),
            (8, "time to correct a live post, days", r"^time a creator has to correct"),
            (11, "time to take down a post after notice, days", r"^time allowed to take down"),
            (11, "notice period without cause, days", r"^notice period for ending without cause")]
    for n, what, pattern in asks:
        found, value = prog.field(n, pattern)
        shown = value if value else ("(blank)" if found else "(no such line)")
        print(f"  section {n}, {what}: {shown}")
    entries = disclosure_entries(prog)
    print("  section 8, required disclosure wording, per entry (quoted wording first):" + ("" if entries else " (blank)"))
    for words, text, quoted in entries or []:
        print(f"    {' '.join(sorted(words)) or 'all platforms'}: {quoted or '(no quoted wording)'} | {text}")
    print("  section 3, platforms (organic creator posts / paid by the brand):")
    for label, organic, paid, _cells in prog.platform_table():
        print(f"    {label}: {organic or 'blank'} / {paid or 'blank'}")
    approved = prog.approved_statements()
    print("  section 7, approved statements:" + ("" if approved else " none"))
    for body, _part in approved:
        print(f"    - {body}")
    forbidden = [l.strip()[2:] for l in prog.subsection(7, "Forbidden") if l.strip().startswith("- ")]
    print("  section 7, forbidden:" + ("" if forbidden else " none"))
    for item in forbidden:
        print(f"    - {item}")
    return stop


def main(argv=None):
    parser = Parser(
        description="Check a terms sheet against the roster and programme file, or show the values a sheet copies.",
        epilog="Exit 0 pass, 1 something to fix, 2 unfinished (TBD values or comparisons not run). With --show: 0 printed, 1 the creator's row is closed (stop S2), 2 the row has no complete agreed deal (stop S3 for draft mode). Nothing is written.")
    parser.add_argument("workspace", help="the programme workspace folder")
    parser.add_argument("terms", nargs="?", help="the terms sheet, for example agreements/c-7k2m9q-2026-10-20.md")
    parser.add_argument("--show", metavar="CREATOR_REF", help="print the roster row and programme values for this creator instead of checking a sheet")
    parser.add_argument("--signed", metavar="YYYY-MM-DD", help="the date the terms were agreed in writing, to fill the printed creator-roster command")
    args = parser.parse_args(argv)
    try:
        if args.show:
            return run_show(args.workspace, args.show)
        if not args.terms:
            raise InputError("give the terms sheet to check, or --show and a creator ref.")
        if args.signed and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.signed):
            raise InputError(f"--signed '{args.signed}' is not a date; write YYYY-MM-DD.")
        return run_check(args.workspace, args.terms, args.signed)
    except InputError as err:
        print(f"check_terms: {err}")
        print("RESULT: FAIL (exit 1): bad input.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
