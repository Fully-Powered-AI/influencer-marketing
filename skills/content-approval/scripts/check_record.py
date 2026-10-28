#!/usr/bin/env python3
"""Approval records: the next approval_id, and a check that a record is complete and consistent.

Part of the content-approval skill. Run with python3 -I.

  check_record.py <workspace> next-id --campaign SLUG --creator REF
      Prints the next approval_id for this creator in this campaign, the previous
      one (or none) and the path to write. Reads campaigns/<slug>/approvals/.

  check_record.py <workspace> check <record.md>
      Checks the record against ../references/approval-checklist.md: the twelve
      lines in order, allowed states and fixes, the claims line against the
      product statements, a feedback item for every failed line and none for
      any other, the owner questions, the conditions at posting, the coverage
      line, "partial" in the title when a line is not checked, the attempt
      chain, and the verdict computed from the checklist by the table in
      section 3 of that file. Writes nothing. A relative record path is looked
      for in the workspace first, then in the current folder.

Exit 0: next-id printed, or the record is consistent. Exit 2: the record has
problems, each printed. Exit 1: bad input or a usage error, with one sentence
saying what to fix.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CHECKLIST = SKILL_DIR / "references" / "approval-checklist.md"

# Source: the pack's references/schemas.md section 2 (identifier shapes).
SLUG = r"\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*"
REF = r"c-[a-z0-9]{6}"
ID_RE = re.compile(rf"^({SLUG})--({REF})--([1-9]\d*)$")
# Source: schemas.md sections 4 and 6 (platform and format values).
PLATFORMS = {"instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast",
             "newsletter", "bluesky", "threads", "other"}
FORMATS = {"video", "reel", "story", "post", "thread", "newsletter", "podcast", "live", "other"}
# Source: approval-checklist.md section 4 (states and fixes) and section 2 (classes).
STATES = {"pass", "fail", "ask", "not checked", "n/a", "at posting"}
FIXES = {"text", "resubmit", "stop"}
CLASSES = {"approved", "reword", "forbidden", "ask"}
EMPTY_FIX = {"", "-", "none"}
VERDICTS = {"approve", "approve-with-changes", "stop"}
STOP_REASONS = {"rule-broken", "on-hold", "resubmit", "none"}
OCCASIONS = {"before publication", "before a payment milestone"}
# The order of approval-checklist.md section 3; the script refuses to run if that table changes.
VERDICT_ORDER = [("stop", "rule-broken"), ("stop", "on-hold"), ("stop", "resubmit"),
                 ("approve-with-changes", "none"), ("approve", "none")]
REQUIRED_FIELDS = ["approval_id", "campaign", "creator_ref", "platform", "format", "product", "attempt",
                   "previous", "occasion", "reviewed_at", "reviewer_role", "programme_file",
                   "caption_check", "verdict", "stop_reason"]
COVERAGE_LABELS = ["Inputs used:", "Inputs missing:", "Could not judge:", "Fine:"]
TAG_RE = re.compile(r"^\s*(?:\d+\.|-)\s*\(([a-z][a-z-]*)\)")


class BadInput(Exception):
    pass


class Parser(argparse.ArgumentParser):
    """Usage errors exit 1, not argparse's 2, which the contract keeps for a partial run."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: {message}; see --help.", file=sys.stderr)
        sys.exit(1)


def resolve(ws, arg):
    """A relative file argument is looked for in the workspace first, then in the current folder."""
    path = Path(arg)
    if path.is_absolute():
        return path
    return ws / path if (ws / path).exists() else path


def sections(text, level="## "):
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith(level):
            cur = line[len(level):].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def table(lines):
    rows, seen_header = [], False
    for line in lines:
        if not line.startswith("|"):
            if seen_header and rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not seen_header:
            seen_header = True
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def load_reference():
    if not CHECKLIST.exists():
        raise BadInput(f"{CHECKLIST} is missing; reinstall the content-approval skill folder.")
    text = CHECKLIST.read_text(encoding="utf-8")
    secs = {k.split(".")[0]: v for k, v in sections(text).items()}
    lines = []
    for cells in table(secs.get("1", [])):
        if len(cells) >= 6 and re.fullmatch(r"[a-z][a-z-]*", cells[1]):
            lines.append({"id": cells[1], "fail_is": cells[4], "at_posting": cells[5] == "yes"})
    order = [(c[2], c[3]) for c in table(secs.get("3", [])) if len(c) >= 4]
    if len(lines) != 12:
        raise BadInput("approval-checklist.md section 1 does not list twelve lines; restore the table.")
    if order != VERDICT_ORDER:
        raise BadInput("approval-checklist.md section 3 no longer matches this script's verdict order; "
                       "update VERDICT_ORDER and compute() together with the table.")
    return lines


def next_id(ws, slug, ref):
    if not re.fullmatch(SLUG, slug):
        raise BadInput(f"'{slug}' is not a campaign_slug (YYYY-MM-name).")
    if not re.fullmatch(REF, ref):
        raise BadInput(f"'{ref}' is not a creator_ref (c- and six letters or digits); never use a handle.")
    camp = ws / "campaigns" / slug
    if not camp.is_dir():
        raise BadInput(f"campaigns/{slug} does not exist in the workspace; check the slug.")
    folder = camp / "approvals"
    attempts = []
    if folder.is_dir():
        for f in folder.glob(f"{slug}--{ref}--*.md"):
            m = ID_RE.match(f.stem)
            if m:
                attempts.append(int(m.group(3)))
    n = max(attempts) + 1 if attempts else 1
    new = f"{slug}--{ref}--{n}"
    print(f"approval_id: {new}")
    print(f"previous: {f'{slug}--{ref}--{n - 1}' if attempts else 'none'}")
    print(f"path: campaigns/{slug}/approvals/{new}.md")
    print(f"attempts on disk: {len(attempts)}")
    return 0


def compute(rows, statements):
    """The verdict table of approval-checklist.md section 3, first matching row wins."""
    judged = [r for r in rows if r["id"] != "creative-freedom"]
    fails = [r for r in judged if r["state"] == "fail"]
    if any(s["class"] == "forbidden" for s in statements) or any(r["fix"] == "stop" for r in fails):
        return VERDICT_ORDER[0]
    if any(r["state"] in ("ask", "not checked") for r in judged):
        return VERDICT_ORDER[1]
    if any(r["fix"] == "resubmit" for r in fails):
        return VERDICT_ORDER[2]
    if any(r["fix"] == "text" for r in fails):
        return VERDICT_ORDER[3]
    return VERDICT_ORDER[4]


def tags(lines):
    return [m.group(1) for m in (TAG_RE.match(l) for l in lines) if m]


def check(ws, record_arg, ref_lines):
    record_path = resolve(ws, record_arg)
    problems = []
    p = problems.append
    try:
        text = Path(record_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise BadInput(f"record {record_arg} not found in the workspace or the current folder; check the path.")
    except UnicodeDecodeError:
        raise BadInput(f"record {record_path} is not UTF-8 text.")
    head, body_started, fields = [], False, {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        head.append(line)
        m = re.match(r"^- ([a-z_]+):\s*(.*?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    if "approval_id" not in fields:
        raise BadInput(f"{record_path} has no '- approval_id:' line; is it an approval record?")
    title = next((l for l in head if l.startswith("# ")), "")
    for f in REQUIRED_FIELDS:
        if not fields.get(f):
            p(f"header field '{f}' is missing or empty")

    aid = fields["approval_id"]
    m = ID_RE.match(aid)
    if not m:
        p(f"approval_id '{aid}' is not <campaign_slug>--<creator_ref>--<n> (schemas.md section 2)")
        slug = ref = None
        n = 0
    else:
        slug, ref, n = m.group(1), m.group(2), int(m.group(3))
        expected = (ws / "campaigns" / slug / "approvals" / f"{aid}.md").resolve()
        if Path(record_path).resolve() != expected:
            p(f"the record must live at campaigns/{slug}/approvals/{aid}.md")
        if fields.get("campaign") != slug:
            p("campaign does not match the approval_id")
        if fields.get("creator_ref") != ref:
            p("creator_ref does not match the approval_id")
        if fields.get("attempt") != str(n):
            p(f"attempt must be {n}, the number at the end of the approval_id")
        prev = fields.get("previous", "")
        if n == 1 and prev != "none":
            p("attempt 1 has no previous record; write 'previous: none'")
        if n > 1:
            want = f"{slug}--{ref}--{n - 1}"
            if prev != want:
                p(f"previous must be {want}: a re-review points to the attempt before it")
            elif not (ws / "campaigns" / slug / "approvals" / f"{want}.md").exists():
                p(f"previous record {want}.md is not on disk; a re-review never replaces an earlier attempt")
        roster = ws / "data" / "creators.csv"
        if roster.exists():
            with open(roster, newline="", encoding="utf-8") as fh:
                refs = {r.get("creator_ref") for r in csv.DictReader(fh)}
            if ref not in refs:
                p(f"creator_ref {ref} is not in data/creators.csv")
    if fields.get("platform") and fields["platform"] not in PLATFORMS:
        p(f"platform '{fields['platform']}' is not a roster platform value")
    if fields.get("format") and fields["format"] not in FORMATS:
        p(f"format '{fields['format']}' is not a publications format value")
    if fields.get("occasion") and fields["occasion"] not in OCCASIONS:
        p("occasion must be 'before publication' or 'before a payment milestone'")
    if fields.get("reviewed_at") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z", fields["reviewed_at"]):
        p("reviewed_at must be UTC, YYYY-MM-DDTHH:MMZ")
    if re.search(r"\$[0-9]", text):
        p("a dollar sign stands before a digit; write the currency code instead")

    secs = sections(text)
    for name in ("What was reviewed", "Checklist", "Product statements", "Verdict",
                 "Feedback for the creator", "For the owner and the programme lead",
                 "Conditions at posting", "Coverage"):
        if name not in secs:
            p(f"section '## {name}' is missing")

    reviewed = secs.get("What was reviewed", [])
    if not any(l.startswith(">") for l in reviewed) and not any("exports/" in l for l in reviewed):
        p("'What was reviewed' neither quotes the submission nor names a file under exports/")
    for path in re.findall(r"exports/[^\s,;)`]+", "\n".join(reviewed)):
        if not (ws / path.rstrip(".")).exists():
            p(f"{path} is named in 'What was reviewed' but is not in the workspace")

    rows = []
    for cells in table(secs.get("Checklist", [])):
        cells += [""] * (5 - len(cells))
        rows.append({"id": cells[0], "state": cells[1].lower(), "fix": cells[2].lower(),
                     "evidence": cells[3], "note": cells[4]})
    want_ids = [l["id"] for l in ref_lines]
    if [r["id"] for r in rows] != want_ids:
        p("the checklist must list these lines in this order: " + ", ".join(want_ids))
    defs = {l["id"]: l for l in ref_lines}
    for r in rows:
        d = defs.get(r["id"])
        if d is None:
            continue
        if r["state"] not in STATES:
            p(f"line {r['id']}: state '{r['state']}' is not one of {', '.join(sorted(STATES))}")
            continue
        if r["state"] == "at posting" and not d["at_posting"]:
            p(f"line {r['id']}: 'at posting' is allowed only on lines marked yes in the checklist")
        if r["state"] == "n/a" and not r["note"]:
            p(f"line {r['id']}: n/a needs the reason in the note")
        if r["state"] == "fail":
            if r["fix"] not in FIXES:
                p(f"line {r['id']}: a fail names its fix: text, resubmit or stop")
            elif d["fail_is"] == "stop" and r["fix"] != "stop":
                p(f"line {r['id']}: a fail on this line is a stop; it cannot be softened to '{r['fix']}'")
        elif r["fix"] not in EMPTY_FIX:
            p(f"line {r['id']}: only a failed line carries a fix")
        if r["state"] in ("pass", "fail") and not r["evidence"]:
            p(f"line {r['id']}: {r['state']} needs the evidence and its location")
    by_id = {r["id"]: r for r in rows}
    cf = by_id.get("creative-freedom")
    if cf and cf["state"] != "pass":
        p("line creative-freedom must be pass: correct the feedback before saving the record")

    statements = []
    for cells in table(secs.get("Product statements", [])):
        cells += [""] * (5 - len(cells))
        if not any(cells):
            continue
        statements.append({"text": cells[1], "class": cells[3].lower(), "reason": cells[4]})
    for s in statements:
        if s["class"] not in CLASSES:
            p(f"product statement {s['text'][:40]}: class '{s['class']}' is not approved, reword, forbidden or ask")
        if '"' not in s["text"] and "“" not in s["text"]:
            p(f"product statement {s['text'][:40]}: quote it exactly as submitted")
    claims = by_id.get("claims")
    if claims:
        classes = {s["class"] for s in statements}
        if "forbidden" in classes:
            if not (claims["state"] == "fail" and claims["fix"] == "stop"):
                p("a forbidden product statement makes line claims a fail with fix stop: a stop is a stop")
        elif "ask" in classes:
            if claims["state"] != "ask":
                p("a product statement classed ask makes line claims ask: only the owner rules on it")
        elif "reword" in classes:
            if not (claims["state"] == "fail" and claims["fix"] in ("text", "resubmit")):
                p("a reworded statement makes line claims a fail with fix text or resubmit")
        elif claims["state"] not in ("pass", "n/a"):
            p("with every product statement approved (or none), line claims is pass")

    failed = {r["id"] for r in rows if r["state"] == "fail" and r["id"] != "creative-freedom"}
    feedback = tags(secs.get("Feedback for the creator", []))
    for fid in sorted(failed - set(feedback)):
        p(f"line {fid} failed but the feedback has no change item tagged ({fid})")
    for t in feedback:
        if t not in failed:
            p(f"feedback item ({t}) asks for a change to a line that did not fail; leave the creator's choices alone")
    held = {r["id"] for r in rows if r["state"] in ("ask", "not checked")}
    for hid in sorted(held - set(tags(secs.get("For the owner and the programme lead", [])))):
        p(f"line {hid} is {by_id[hid]['state']} but 'For the owner and the programme lead' has no item ({hid})")
    posting = {r["id"] for r in rows if r["state"] == "at posting"}
    for pid in sorted(posting - set(tags(secs.get("Conditions at posting", [])))):
        p(f"line {pid} is at posting but 'Conditions at posting' has no item ({pid})")

    unseen = [r["id"] for r in rows if r["state"] == "not checked"]
    if unseen and "partial" not in title.lower():
        p("a line is not checked, so the title line must say 'partial'")
    if not unseen and "partial" in title.lower():
        p("the title says 'partial' but every line was checked")
    coverage = "\n".join(secs.get("Coverage", []))
    for label in COVERAGE_LABELS:
        if label not in coverage:
            p(f"coverage line '{label}' is missing")
    cj = re.search(r"Could not judge:(.*)", coverage)
    for uid in unseen:
        if not cj or uid not in cj.group(1):
            p(f"'Could not judge' must name line {uid}")

    verdict, reason = compute(rows, statements) if rows else (None, None)
    if verdict:
        if fields.get("verdict") != verdict or fields.get("stop_reason") != reason:
            p(f"the checklist gives verdict '{verdict}', stop_reason '{reason}'; the header says "
              f"'{fields.get('verdict')}', '{fields.get('stop_reason')}'")
    for pr in problems:
        print(f"PROBLEM  {pr}")
    print(f"record: {record_path}")
    print(f"computed verdict: {verdict}, stop_reason: {reason}")
    print(f"result: {len(problems)} problem(s); exit {2 if problems else 0}")
    return 2 if problems else 0


def main(argv=None):
    ap = Parser(description="Next approval_id, or check an approval record. Writes nothing.")
    ap.add_argument("workspace", help="the client's workspace folder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next-id", help="print the next approval_id for a creator in a campaign")
    n.add_argument("--campaign", required=True)
    n.add_argument("--creator", required=True)
    c = sub.add_parser("check", help="check one approval record")
    c.add_argument("record", help="campaigns/<slug>/approvals/<approval_id>.md; a relative path is looked for "
                   "in the workspace first, then in the current folder")
    a = ap.parse_args(argv)
    try:
        ws = Path(a.workspace)
        if not ws.is_dir():
            raise BadInput(f"workspace {ws} is not a folder; pass the workspace path first.")
        if a.cmd == "next-id":
            return next_id(ws, a.campaign, a.creator)
        return check(ws, a.record, load_reference())
    except BadInput as e:
        print(f"check_record.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
