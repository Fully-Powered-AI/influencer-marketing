#!/usr/bin/env python3
"""Check a written campaign plan before it goes to the owner.

Usage:
  python3 -I scripts/check_plan.py WORKSPACE --campaign SLUG

Checks campaigns/SLUG/plan.md against the plan template (assets/plan-template.md), the
programme file and budget.csv:
  1. the slug's form (schemas.md section 2) and the title line with its status
  2. the ten numbered headings, in order
  3. the six KPI rows, and the attribution and ranking-metric lines copied word for word from
     programme section 5
  4. the creator mix: tiers, compensation, whole-number counts, every platform cleared for
     organic creator posts in programme section 3, an owner-approval entry on every fee row
     and every mid or macro row, and the same rows and counts as budget.csv's base case
  5. both generated blocks present and unedited (their hashes), and budget.csv unchanged
     since the block was written
  6. a partial block means a partial title; an approved title has no pending approval
  7. checklist ids M1 to M10 and risk ids R1 to R9 present, none left as a placeholder
  8. the coverage section's three lines, and no dollar sign before a digit

Exit 0: every check ran and passed. Exit 1: a finding (each printed with what to fix) or bad
input. Exit 2: no findings, but a check was skipped because an input was missing; the output
says which. Never touches the network and never writes.
"""
import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # leave no __pycache__ inside the installed skill
sys.path.insert(0, str(Path(__file__).resolve().parent))
import programme as pg  # noqa: E402

SLUG = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])-[a-z0-9]+(?:-[a-z0-9]+)*$")
TITLE = re.compile(r"^# Campaign plan: (?P<slug>\S+) \((?P<status>draft|partial|approved \d{4}-\d{2}-\d{2})\)\s*$")
HEADINGS = ["## 1. Objective", "## 2. KPIs and attribution", "## 3. Creator mix", "## 4. Budget",
            "## 5. Timeline", "## 6. Measurement setup before launch", "## 7. Risks and contingencies",
            "## 8. Approvals and open items", "## 9. Revisions", "## 10. Coverage"]
KPIS = ["tracked orders", "new customers", "cost per tracked order", "commission return on sales",
        "posts live with disclosure", "assets with reuse rights"]
TIERS = ["nano", "micro", "mid", "macro"]
COMPENSATION = ["cpa", "hybrid", "flat", "gift"]
MARKERS = {
    "budget": ("<!-- plan_budget:budget:begin -->", "<!-- plan_budget:budget:end -->"),
    "dates": ("<!-- plan_budget:dates:begin -->", "<!-- plan_budget:dates:end -->"),
}
DOLLAR = re.compile(r"\$[0-9]")
PLACEHOLDER = re.compile(r"<[^<>\n]*>")


def verbatim(text):
    """The text as written, less source marks, bold markers, edge punctuation and line wrapping."""
    t = pg.strip_marks(text).replace("**", "")
    return re.sub(r"\s+", " ", t).strip(" .;:")


def norm(text):
    t = pg.strip_marks(text).replace("*", "").lower()
    return re.sub(r"\s+", " ", t).strip(" .;:")


def sections_of(lines):
    found, idx = {}, []
    for i, line in enumerate(lines):
        if line.strip() in HEADINGS:
            idx.append((line.strip(), i))
    for k, (h, i) in enumerate(idx):
        end = idx[k + 1][1] if k + 1 < len(idx) else len(lines)
        found[h] = lines[i + 1:end]
    return found, [h for h, _ in idx]


def table_rows(lines, first_header):
    rows, header, started = [], None, False
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            if started:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            if cells and cells[0].lower() == first_header:
                header, started = [c.lower() for c in cells], True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(header, cells)))
    return header, rows


def block(text, name):
    begin, end = MARKERS[name]
    i, j = text.find(begin), text.find(end)
    if i < 0 or j < 0 or j < i:
        return None
    return text[i + len(begin):j].strip("\n")


def check(ws, slug):
    findings, skipped, ran = [], [], []
    camp = ws / "campaigns" / slug
    plan = camp / "plan.md"
    if not SLUG.match(slug):
        findings.append(f"'{slug}' is not a campaign slug: YYYY-MM- then lowercase words joined by hyphens (schemas.md section 2).")
    if not plan.is_file():
        raise FileNotFoundError(f"{plan} was not found; write the plan from assets/plan-template.md first.")
    text = plan.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 1. title
    m = TITLE.match(lines[0]) if lines else None
    status = None
    if not m:
        findings.append("The first line must read '# Campaign plan: <slug> (draft)', '(partial)' or '(approved YYYY-MM-DD)'.")
    else:
        status = m.group("status")
        if m.group("slug") != slug:
            findings.append(f"The title names '{m.group('slug')}' but the folder is '{slug}'.")
    ran.append("title and slug")

    # 2. headings
    secs, order = sections_of(lines)
    missing = [h for h in HEADINGS if h not in secs]
    if missing:
        findings.append("Missing heading(s): " + "; ".join(missing) + ". Keep the template's numbered headings.")
    elif order != HEADINGS:
        findings.append("The numbered headings are out of order; keep the template's order.")
    ran.append("headings")

    try:
        sections = pg.load(ws)
    except pg.ProgrammeError as e:
        sections = None
        skipped.append(f"programme checks ({e})")

    # 3. KPIs and attribution
    kpi = "\n".join(secs.get("## 2. KPIs and attribution", [])).lower()
    for k in KPIS:
        if k not in kpi:
            findings.append(f"Section 2 lacks the KPI '{k}'; keep the template's six KPI rows.")
    att_line = next((l for l in secs.get("## 2. KPIs and attribution", []) if norm(l).startswith("attribution model")), None)
    if att_line is None:
        findings.append("Section 2 lacks the 'Attribution model:' line.")
    elif sections is not None:
        value, _ = pg.field(sections, "attribution")
        if value is None:
            findings.append("Programme section 5: the attribution model is blank, [open] or a placeholder such as 'as written'; its value is the full sentence the owner accepted or changed (schemas.md section 12). Have program-setup write it, then copy it into the plan.")
        else:
            planned = verbatim(att_line.split(":", 1)[1] if ":" in att_line else "")
            if planned != verbatim(value):
                findings.append("Section 2's attribution line differs from programme section 5; copy the sentence verbatim: \"" + value + "\".")
            else:
                ran.append("attribution copy")
    rank_line = next((l for l in secs.get("## 2. KPIs and attribution", []) if norm(l).startswith("ranking metric")), None)
    if rank_line is None:
        findings.append("Section 2 lacks the 'Ranking metric:' line.")
    elif sections is not None:
        value, _ = pg.field(sections, "ranking")
        if value is None:
            skipped.append("ranking-metric copy (programme section 5 ranking metric is blank or [open])")
        elif norm(rank_line.split(":", 1)[1] if ":" in rank_line else "") != norm(value):
            findings.append("Section 2's ranking-metric line differs from programme section 5; copy it word for word: \"" + value + "\".")
        else:
            ran.append("ranking-metric copy")
    ran.append("KPI rows")

    # 4. creator mix
    header, mix = table_rows(secs.get("## 3. Creator mix", []), "tier")
    need = ["tier", "compensation", "creators", "platforms", "from the shortlist", "owner approval"]
    if header is None or any(c not in header for c in need):
        findings.append("Section 3 needs the mix table with columns: " + ", ".join(need) + ".")
        mix = []
    table, filled = (pg.platform_table(sections) if sections is not None else ({}, False))
    if sections is not None and not filled:
        skipped.append("platform rule (programme section 3 has no rulings)")
    pending = False
    for r in mix:
        tier, comp = r.get("tier", "").lower(), r.get("compensation", "").lower()
        where = f"Section 3 row '{r.get('tier', '')} {r.get('compensation', '')}'"
        if PLACEHOLDER.search(" ".join(r.values())):
            findings.append(f"{where} still holds a template placeholder.")
            continue
        if tier not in TIERS:
            findings.append(f"{where}: tier must be nano, micro, mid or macro.")
        if comp not in COMPENSATION:
            findings.append(f"{where}: compensation must be cpa, hybrid, flat or gift.")
        if not r.get("creators", "").isdigit():
            findings.append(f"{where}: creators must be a whole number.")
        plats = [x.strip().lower() for x in r.get("platforms", "").split(";") if x.strip()]
        if not plats:
            findings.append(f"{where}: name at least one platform.")
        if filled:
            for plat in plats:
                st, txt, via = pg.platform_ruling(table, plat)
                if not pg.eligible(st):
                    findings.append(f"{where}: programme section 3 rules '{st}' for organic creator posts on {plat} (row: {via}); take it out of the plan or have the owner change section 3.")
        approval = r.get("owner approval", "").strip().lower()
        if (comp in ("hybrid", "flat") or tier in ("mid", "macro")) and approval in ("", "not needed", "none", "n/a"):
            findings.append(f"{where}: a fee deal or a mid or macro creator needs the owner's approval entry (pending, or approved with its date); programme section 4 sets who approves.")
        if "pending" in approval:
            pending = True
    if filled and mix:
        ran.append("platform rule")
    ran.append("creator mix")

    budget_csv = camp / "budget.csv"
    if budget_csv.is_file() and mix:
        with budget_csv.open(newline="", encoding="utf-8") as fh:
            base = {(r["tier"], r["compensation"]): r["creators"] for r in csv.DictReader(fh)
                    if r.get("scenario") == "base" and r.get("tier") != "total"}
        planned = {(r.get("tier", "").lower(), r.get("compensation", "").lower()): r.get("creators", "") for r in mix}
        if planned != base:
            findings.append("Section 3's rows and counts differ from budget.csv's base case; change the assumptions or the mix so they agree, then re-run plan_budget.py.")
        else:
            ran.append("mix against budget.csv")
    elif not budget_csv.is_file():
        skipped.append("mix against budget.csv (no budget.csv; run plan_budget.py)")

    # 5. generated blocks
    partial_block = False
    for name in ("budget", "dates"):
        body = block(text, name)
        if body is None:
            findings.append(f"The {name} block markers are missing; copy them from assets/plan-template.md and re-run plan_budget.py.")
            continue
        if not body.strip():
            findings.append(f"The {name} block is empty; run plan_budget.py.")
            continue
        blines = body.splitlines()
        last = blines[-1] if blines else ""
        mm = re.match(r"^block sha256: ([0-9a-f]{16})$", last)
        inner = "\n".join(blines[:-1])
        if not mm or hashlib.sha256(inner.encode("utf-8")).hexdigest()[:16] != mm.group(1):
            findings.append(f"The {name} block was edited by hand; change the inputs and re-run plan_budget.py instead.")
            continue
        if "Status: partial" in inner or "Not computed:" in inner or "not computed:" in inner:
            partial_block = True
        if name == "budget":
            cm = re.search(r"^budget\.csv sha256: ([0-9a-f]{16})$", inner, re.M)
            if budget_csv.is_file() and cm:
                if hashlib.sha256(budget_csv.read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:16] != cm.group(1):
                    findings.append("budget.csv has changed since the budget block was written; re-run plan_budget.py.")
    ran.append("generated blocks")

    # 6. status consistency
    if status:
        if partial_block and status != "partial":
            findings.append("A generated block says partial or not computed, so the title's status must be (partial).")
        if status.startswith("approved") and pending:
            findings.append("The title says approved but a mix row's owner approval is still pending.")
    ran.append("status")

    # 7. checklist and risks
    m6 = "\n".join(secs.get("## 6. Measurement setup before launch", []))
    for i in range(1, 11):
        if not re.search(rf"\bM{i}\b", m6):
            findings.append(f"Section 6 lacks checklist item M{i}; keep all ten.")
    _, risks = table_rows(secs.get("## 7. Risks and contingencies", []), "id")
    ids = {r.get("id", "").upper(): r for r in risks}
    for i in range(1, 10):
        r = ids.get(f"R{i}")
        if r is None:
            findings.append(f"Section 7 lacks risk R{i}; keep all nine (say 'not applicable' and why if one does not apply).")
        elif PLACEHOLDER.search(" ".join(r.values())):
            findings.append(f"Section 7 risk R{i} still holds a template placeholder; write this campaign's response.")
    ran.append("checklist and risks")

    # 8. coverage and dollar rule
    cov = "\n".join(secs.get("## 10. Coverage", [])).lower()
    for label in ("inputs used:", "inputs missing:", "could not judge:"):
        if label not in cov:
            findings.append(f"Section 10 lacks the '{label}' line.")
    current = None
    for n, line in enumerate(lines, 1):
        if line.strip() in HEADINGS:
            current = line.strip()
        if DOLLAR.search(line):
            findings.append(f"Line {n} has a dollar sign before a digit; write the currency code, for example USD 15.")
        reported = current in ("## 3. Creator mix", "## 7. Risks and contingencies") and line.lstrip().startswith("|")
        if line.strip() and PLACEHOLDER.search(line) and not line.lstrip().startswith("<!--") and not reported:
            findings.append(f"Line {n} still holds a template placeholder: {line.strip()[:80]}")
    ran.append("coverage and text")
    return findings, skipped, ran


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Exit 0 pass, 1 findings or bad input, 2 a check skipped. Reads only.")
    ap.add_argument("workspace", help="the workspace folder")
    ap.add_argument("--campaign", required=True, help="campaign slug")
    a = ap.parse_args(argv)
    ws = Path(a.workspace)
    if not ws.is_dir():
        print(f"check_plan: {ws} is not a folder; give the workspace path first.", file=sys.stderr)
        return 1
    try:
        findings, skipped, ran = check(ws, a.campaign)
    except FileNotFoundError as e:
        print(f"check_plan: {e}", file=sys.stderr)
        return 1
    for f in findings:
        print(f"finding: {f}")
    for s in skipped:
        print(f"skipped: {s}")
    print(f"Coverage: checks run: {', '.join(ran)}. Skipped: {'; '.join(skipped) or 'none'}. "
          "Not checked: whether the mix argument, risks and checklist roles are sensible (that is the owner's review).")
    if findings:
        print(f"Result: {len(findings)} finding(s); fix each and re-run.")
        return 1
    if skipped:
        print("Result: no findings, but partial: a check was skipped.")
        return 2
    print("Result: pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
