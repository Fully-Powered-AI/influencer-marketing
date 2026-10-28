#!/usr/bin/env python3
"""Fixture cases for check_terms.py and scan_incoming.py, plus drift checks between the scripts,
the template and the references. Each case copies the fixture workspace to a temporary folder,
applies its edits, runs one script, and compares the exit code and the output with what the case
expects. Prints one line per case and exits 1 if any case misses."""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
SCRIPTS = SKILL / "scripts"
WS = HERE / "ws"
GREEN = "agreements/c-7k2m9q-2026-10-20.md"
PROGRAMME = "program/program.md"

# (name, script, args, edits {relative file: [(old, new), ...] or None to delete}, exit, must contain, must not contain)
CASES = [
    ("green sheet passes", "check_terms.py", [GREEN], {}, 0, ["RESULT: PASS"], []),
    ("TBD values leave it incomplete", "check_terms.py", [GREEN], {GREEN: [
        ("Dispute window for a statement, days: 30", "Dispute window for a statement, days: TBD (owner)"),
        ("Disputes: fixture dispute process (counsel, 2026-10-20)", "Disputes: TBD (counsel)")]},
     2, ["RESULT: INCOMPLETE", "total 2"], ["FAIL "]),
    ("a programme day count copied into the sheet passes; a different one must be listed", "check_terms.py", [GREEN], {GREEN: [
        ("- Takedown time, days: 1", "- Takedown time, days: 3")]}, 1, ["programme section 11 says '1'"], []),
    ("a TBD day count with the programme's value set is incomplete and shows the value", "check_terms.py", [GREEN], {GREEN: [
        ("- Correction time, days: 2", "- Correction time, days: TBD (owner)")]}, 2, ["programme section 8 has '2'", "RESULT: INCOMPLETE"], ["FAIL "]),
    ("a counsel review the programme does not record fails", "check_terms.py", [GREEN], {PROGRAMME: [
        ("reviewed by counsel 2026-10-20, version 0.1.1 [owner]", "")]}, 1, ["records no counsel review"], []),
    ("'not recorded' when the programme has no counsel record passes that line", "check_terms.py", [GREEN], {PROGRAMME: [
        ("reviewed by counsel 2026-10-20, version 0.1.1 [owner]", "")], GREEN: [
        ("- Counsel review of this template: reviewed by counsel 2026-10-20, version 0.1.1", "- Counsel review of this template: not recorded: these terms may not go to a creator yet")]},
     0, ["RESULT: PASS"], []),
    ("a missing section fails", "check_terms.py", [GREEN], {GREEN: [
        ("## 13. Confidentiality\n", "## 99. Removed\n")]}, 1, ["section 13. Confidentiality is missing"], []),
    ("a rate that differs from the roster fails", "check_terms.py", [GREEN], {GREEN: [
        ("Commission rate, percent of the basis: 15", "Commission rate, percent of the basis: 20")]}, 1, ["the roster says 15"], []),
    ("TBD disclosure fails", "check_terms.py", [GREEN], {GREEN: [
        ('- Wording: "Ad: paid partnership with Cedar Lane"', "- Wording: TBD (owner)")]}, 1, ["disclosure and claims are copied"], []),
    ("disclosure wording not from the programme fails", "check_terms.py", [GREEN], {GREEN: [
        ('- Wording: "Ad: paid partnership with Cedar Lane"', "- Wording: #sponsored at the end")]}, 1, ["is not, whole, a wording in programme section 8"], []),
    ("a shortened disclosure wording fails", "check_terms.py", [GREEN], {GREEN: [
        ('- Wording: "Ad: paid partnership with Cedar Lane"', '- Wording: "Ad"')]}, 1, ["is not, whole, a wording in programme section 8", "not programme section 8's instagram wording"], []),
    ("another platform's wording, when the deliverables are on instagram, fails", "check_terms.py", [GREEN], {GREEN: [
        ('- Wording: "Ad: paid partnership with Cedar Lane"', '- Wording: "This is a paid partnership with Cedar Lane"')]}, 1, ["not programme section 8's instagram wording"], []),
    ("a customer discount of 5 percent against 15 percent fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Customer discount on the creator's code: 15 percent", "- Customer discount on the creator's code: 5 percent")]}, 1, ["programme section 4 says '15 percent'"], []),
    ("a fixed-amount discount against a percentage fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Customer discount on the creator's code: 15 percent", "- Customer discount on the creator's code: USD 15 off")]}, 1, ["programme section 4 says '15 percent'"], []),
    ("15% is the same discount as 15 percent", "check_terms.py", [GREEN], {GREEN: [
        ("- Customer discount on the creator's code: 15 percent", "- Customer discount on the creator's code: 15%")]}, 0, ["RESULT: PASS"], []),
    ("a window with no number fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Window: 6 months from posting", "- Window: months from posting")]}, 1, ["programme section 11 says '6 months from posting"], []),
    ("a shorter window fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Window: 6 months from posting", "- Window: 2 months from posting")]}, 1, ["programme section 11 says '6 months from posting"], []),
    ("part of the governing law fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Governing law: Fixture Jurisdiction A", "- Governing law: Jurisdiction")]}, 1, ["programme section 11 says 'Fixture Jurisdiction A'"], []),
    ("part of the commission basis fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Commission basis: subtotal after discounts, before shipping and tax", "- Commission basis: subtotal")]}, 1, ["programme section 4 says 'subtotal after discounts"], []),
    ("--show leaves the template's unmarked guidance out of values", "check_terms.py", ["--show", "c-7k2m9q"], {}, 0,
     ["payout schedule and minimum payout: monthly, after the holdback; minimum payout 25.00", "instagram: Ad: paid partnership with Cedar Lane"], ["Write the minimum as"]),
    ("a marked detail line stands in for a blank field line", "check_terms.py", ["--show", "c-7k2m9q"], {PROGRAMME: [
        ("minimum payout amount: monthly, after the holdback; minimum payout 25.00 [owner]", "minimum payout amount:\n  - monthly, minimum 40.00 [owner]")]}, 0,
     ["payout schedule and minimum payout: monthly, minimum 40.00"], ["Write the minimum as"]),
    ("without --signed the command carries YYYY-MM-DD, never a shell-unsafe placeholder", "check_terms.py", [GREEN], {}, 0,
     ["agreement_date=YYYY-MM-DD", "--date YYYY-MM-DD"], ["<date"]),
    ("the roster command is printed, with the rights-from-posting note", "check_terms.py", [GREEN, "--signed", "2026-11-03"], {}, 0,
     ["update c-7k2m9q status=agreed agreement_date=2026-11-03 agreement_file=agreements/c-7k2m9q-2026-10-20.md --note \"rights from posting: 6 months\" --role \"programme lead\" --date 2026-11-03",
      "usage_rights_until stays empty"], ["exclusivity_until="]),
    ("a fixed end date and paid exclusivity go into the roster command", "check_terms.py", [GREEN, "--signed", "2026-11-03"], {GREEN: [
        ("- Window: 6 months from posting", "- Window: 2027-05-31"),
        ("- Category: none", "- Category: home-goods products"),
        ("- Period: n/a", "- Period: 2026-11-01 to 2027-01-31"),
        ("- Payment for exclusivity: n/a", "- Payment for exclusivity: 100.00"),
        ("- Departures from the programme file: none", "- Departures from the programme file: programme section 11: fixed window end and category exclusivity; owner approval: TBD")]}, 2,
     ["exclusivity_until=2027-01-31", "usage_rights_until=2027-05-31", '--note "terms agreed in writing"'], []),
    ("a duration with no start runs from posting: the command carries the note", "check_terms.py", [GREEN, "--signed", "2026-11-03"], {
        PROGRAMME: [("6 months from posting; paid reuse not included [owner]", "6 months, organic reuse only [owner]")],
        GREEN: [("- Window: 6 months from posting", "- Window: 6 months, organic reuse only")]}, 0,
     ['--note "rights from posting: 6 months"', "usage_rights_until stays empty", "--date 2026-11-03", "RESULT: PASS"], ["usage_rights_until=", "ask the owner"]),
    ("'6 months from posting' in the sheet matches a duration-only programme window", "check_terms.py", [GREEN], {
        PROGRAMME: [("6 months from posting; paid reuse not included [owner]", "6 months, organic reuse only [owner]")]}, 0, ["RESULT: PASS"], []),
    ("a window in years from posting is noted in months", "check_terms.py", [GREEN, "--signed", "2026-11-03"], {
        PROGRAMME: [("6 months from posting; paid reuse not included [owner]", "1 year, organic reuse only [owner]")],
        GREEN: [("- Window: 6 months from posting", "- Window: 1 year")]}, 0, ['--note "rights from posting: 12 months"'], ["usage_rights_until="]),
    ("a window from another start is not noted as from posting", "check_terms.py", [GREEN, "--signed", "2026-11-03"], {GREEN: [
        ("- Window: 6 months from posting", "- Window: 6 months from the end date"),
        ("- Departures from the programme file: none", "- Departures from the programme file: programme section 11: window runs from the end date; owner approval: TBD")]}, 2,
     ["ask the owner how it is dated", '--note "terms agreed in writing"'], ["rights from posting"]),
    ("an unknown flag is a usage error and exits 1", "check_terms.py", [GREEN, "--no-such-flag"], {}, 1, ["run with --help"], []),
    ("an unknown flag on the scanner exits 1", "scan_incoming.py", ["exports/incoming-clean.txt", "--creator", "c-7k2m9q", "--no-such-flag"], {}, 1, ["run with --help"], []),
    ("a statement not cleared in section 7 fails", "check_terms.py", [GREEN], {GREEN: [
        ("| Fixture approved statement one | Product A |", "| Latex safe | Product A |")]}, 1, ["is not, word for word"], []),
    ("a platform the programme rules out fails", "check_terms.py", [GREEN], {GREEN: [
        ("| 2 | instagram | story |", "| 2 | tiktok | video |")]}, 1, ["creator posts there are 'no'"], []),
    ("exclusivity without payment fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Category: none", "- Category: home-goods products"),
        ("- Period: n/a", "- Period: 2026-11-01 to 2027-01-31"),
        ("- Payment for exclusivity: n/a", "- Payment for exclusivity: included in the commission")]}, 1, ["nothing is paid for it"], []),
    ("a window with no end fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Window: 6 months from posting", "- Window: in perpetuity")]}, 1, ["has no end"], []),
    ("automatic renewal fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Renewal: none; continuing after the end date takes a new terms sheet", "- Renewal: renews automatically each quarter")]}, 1, ["may not renew by itself"], []),
    ("an unlisted departure from the programme fails", "check_terms.py", [GREEN], {GREEN: [
        ("- Holdback, days: 30", "- Holdback, days: 14")]}, 1, ["programme section 5 says '30'"], []),
    ("a listed departure waits for the owner", "check_terms.py", [GREEN], {GREEN: [
        ("- Holdback, days: 30", "- Holdback, days: 14"),
        ("- Departures from the programme file: none", "- Departures from the programme file: programme section 5: holdback 14 days instead of 30; owner approval: TBD")]},
     2, ["listed in section 16", "RESULT: INCOMPLETE"], ["FAIL "]),
    ("an excluded creator fails", "check_terms.py", [GREEN], {GREEN: [
        ("Creator ref: c-7k2m9q", "Creator ref: c-x9clos"),
        ("Creator display name: Sample Creator A", "Creator display name: Sample Creator C")]}, 1, ["no terms are drafted for this creator"], []),
    ("a hybrid deal without the owner's approval fails", "check_terms.py", [GREEN], {GREEN: [
        ("Creator ref: c-7k2m9q", "Creator ref: c-h4brid"),
        ("Creator display name: Sample Creator A", "Creator display name: Sample Creator B"),
        ("- Model: cpa", "- Model: hybrid"),
        ("Commission rate, percent of the basis: 15", "Commission rate, percent of the basis: 10"),
        ("Flat fee per deliverable set, store currency: none", "Flat fee per deliverable set, store currency: 150.00"),
        ("- Flat fee paid: n/a", "- Flat fee paid: after the brand records the reel as live")]}, 1, ["needs the owner's approval"], []),
    ("blank programme disclosure fails", "check_terms.py", [GREEN], {PROGRAMME: [
        ('  - instagram: "Ad: paid partnership with Cedar Lane" at the start of the caption, paid-partnership tool on [owner]\n', ""),
        ('  - x: "Ad: paid partnership with Cedar Lane" at the start of the post, Paid Partnership label on [owner]\n', ""),
        ('  - youtube: "This is a paid partnership with Cedar Lane" said aloud in the first 30 seconds and shown on screen; paid promotion box ticked [owner]\n', ""),
        ('  - podcast: "This episode is sponsored by Cedar Lane" read aloud before the mention [owner]\n', ""),
        ("`thanks to`): #sp, #collab, #ambassador, thanks to, gifted on its own [owner]", "`thanks to`):"),
        ("runs the check): programme lead, on day 1 [owner]", "runs the check):")]}, 1, ["programme section 8 has no disclosure wording"], []),
    ("the template keeps every section and line the script requires", "check_terms.py", ["SKILL:assets/terms-sheet-template.md"], {}, 1,
     ["still a template placeholder"], ["is missing"]),
    ("a missing roster is bad input", "check_terms.py", [GREEN], {"data/creators.csv": None}, 1, ["No roster at"], []),
    ("--show for a creator not on the roster is bad input", "check_terms.py", ["--show", "c-zzzzzz"], {}, 1, ["is not in data/creators.csv"], []),
    ("--show for an excluded creator is stop S2", "check_terms.py", ["--show", "c-x9clos"], {}, 1, ["STOP S2"], []),
    ("--show for a row with no agreed deal is stop S3", "check_terms.py", ["--show", "c-7k2m9q"], {"data/creators.csv": [
        ("negotiating,cpa,15,", "negotiating,,,")]}, 2, ["STOP S3"], ["STOP S2"]),
    ("--show prints the values a sheet copies", "check_terms.py", ["--show", "c-7k2m9q"], {}, 0, ["section 5, holdback, days: 30", "Fixture approved statement one"], ["STOP"]),
    ("a hybrid fee with no payment timing fails", "check_terms.py", [GREEN], {GREEN: [
        ("Creator ref: c-7k2m9q", "Creator ref: c-h4brid"),
        ("Creator display name: Sample Creator A", "Creator display name: Sample Creator B"),
        ("- Model: cpa", "- Model: hybrid"),
        ("Commission rate, percent of the basis: 15", "Commission rate, percent of the basis: 10"),
        ("Flat fee per deliverable set, store currency: none", "Flat fee per deliverable set, store currency: 150.00"),
        ("- Owner approval for a flat or hybrid deal: n/a", "- Owner approval for a flat or hybrid deal: owner, 2026-10-20")]}, 1, ["says when the fee is paid"], []),
    ("a hybrid deal with timing and approval passes", "check_terms.py", [GREEN], {GREEN: [
        ("Creator ref: c-7k2m9q", "Creator ref: c-h4brid"),
        ("Creator display name: Sample Creator A", "Creator display name: Sample Creator B"),
        ("- Model: cpa", "- Model: hybrid"),
        ("Commission rate, percent of the basis: 15", "Commission rate, percent of the basis: 10"),
        ("Flat fee per deliverable set, store currency: none", "Flat fee per deliverable set, store currency: 150.00"),
        ("- Flat fee paid: n/a", "- Flat fee paid: after the brand records the reel as live"),
        ("- Owner approval for a flat or hybrid deal: n/a", "- Owner approval for a flat or hybrid deal: owner, 2026-10-20")]}, 0, ["RESULT: PASS"], []),
    ("a flagged paper is flagged", "scan_incoming.py", ["exports/incoming-flagged.txt", "--creator", "c-7k2m9q"], {}, 2,
     ["FLAG  RF1 ", "FLAG  RF2 ", "FLAG  RF3 ", "FLAG  RF4 ", "FLAG  RF6 ", "ABSENT RF7", "ABSENT RF8", "FLAG  RF9 ", "FLAG  RF11 ",
      "ABSENT RF12", "FLAG  RF13 ", "FLAG  RF16 ", "FLAG  RF17 "], []),
    ("a clean paper flags nothing", "scan_incoming.py", ["exports/incoming-clean.txt", "--creator", "c-7k2m9q"], {}, 0, ["NOTHING FLAGGED"], ["FLAG ", "ABSENT"]),
    ("a creator not on the roster is bad input", "scan_incoming.py", ["exports/incoming-clean.txt", "--creator", "c-zzzzzz"], {}, 1, ["is not in data/creators.csv"], []),
    ("an empty paper is bad input", "scan_incoming.py", ["exports/incoming-clean.txt", "--creator", "c-7k2m9q"],
     {"exports/incoming-clean.txt": [("__ALL__", "")]}, 1, ["has no text"], []),
]


def run_case(case, tmp):
    name, script, args, edits, want_exit, must, must_not = case
    ws = tmp / "ws"
    shutil.copytree(WS, ws)
    for rel, changes in edits.items():
        target = ws / rel
        if changes is None:
            target.unlink()
            continue
        text = target.read_text(encoding="utf-8")
        for old, new in changes:
            if old == "__ALL__":
                text = new
                continue
            if old not in text:
                return False, f"edit not applied, '{old[:50]}' not in {rel}"
            text = text.replace(old, new)
        target.write_text(text, encoding="utf-8")
    argv = [str(SKILL / a[6:]) if a.startswith("SKILL:") else a for a in args]
    proc = subprocess.run([sys.executable, "-I", "-B", str(SCRIPTS / script), str(ws)] + argv,
                          capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    problems = []
    if proc.returncode != want_exit:
        problems.append(f"exit {proc.returncode}, wanted {want_exit}")
    problems += [f"missing '{m}'" for m in must if m not in out]
    problems += [f"unexpected '{m}'" for m in must_not if m in out]
    return not problems, "; ".join(problems) or "ok", out


def drift_checks():
    results = []
    scan = (SCRIPTS / "scan_incoming.py").read_text()
    flags = (SKILL / "references" / "red-flags.md").read_text()
    in_script = set(re.findall(r"\b(RF\d+)\b", scan))
    in_ref = set(re.findall(r"^\| (RF\d+) \|", flags, re.M))
    results.append(("every scanner flag has a row in red-flags.md, and every row a check", in_script == in_ref,
                    f"script only: {sorted(in_script - in_ref)}; reference only: {sorted(in_ref - in_script)}"))
    checklist = (SKILL / "references" / "terms-checklist.md").read_text()
    template = (SKILL / "assets" / "terms-sheet-template.md").read_text()
    t_ids = [int(x) for x in re.findall(r"^\| T(\d+) \|", checklist, re.M)]
    sections = [int(x) for x in re.findall(r"^## (\d+)\. ", template, re.M)]
    results.append(("checklist IDs T1 to T16 match the template's sections 1 to 16", t_ids == list(range(1, 17)) and sections == list(range(1, 18)),
                    f"checklist {t_ids}; template {sections}"))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SCRIPTS))
    from terms_lib import TEMPLATE_LABELS
    pack_template = SKILL.parent / "program-setup" / "assets" / "program-template.md"
    if pack_template.is_file():
        found = []
        for line in pack_template.read_text().splitlines():
            if line.startswith("- ") and line.rstrip().endswith(":"):
                label = line[2:].rstrip()[:-1]
                if ":" in label:
                    found.append(" ".join(label.split()))
        results.append(("terms_lib's programme labels match program-setup's template", found == TEMPLATE_LABELS,
                        f"template only: {[l for l in found if l not in TEMPLATE_LABELS][:3]}; script only: {[l for l in TEMPLATE_LABELS if l not in found][:3]}"))
    else:
        results.append(("terms_lib's programme labels match program-setup's template (skipped: template not beside this skill)", True, "skipped"))
    return results


def main():
    misses = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_case(case, Path(tmp))
        ok, detail = result[0], result[1]
        print(f"{'ok  ' if ok else 'MISS'} {case[0]}" + ("" if ok else f": {detail}"))
        if not ok:
            misses += 1
            if len(result) > 2:
                print("      output: " + result[2].strip().replace("\n", "\n      "))
    for name, ok, detail in drift_checks():
        print(f"{'ok  ' if ok else 'MISS'} {name}" + ("" if ok else f": {detail}"))
        misses += 0 if ok else 1
    print(f"{len(CASES) + 3 - misses} of {len(CASES) + 3} passed")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
