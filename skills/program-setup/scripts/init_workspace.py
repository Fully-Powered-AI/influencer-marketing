#!/usr/bin/env python3
"""Create the creator-programme workspace, or check its programme file.

Create (default): makes the folders of the workspace, writes header-only
data/creators.csv, data/pipeline.csv and data/publications.csv, and copies
the programme template to program/program.md. Nothing that exists is
overwritten; an existing CSV whose header differs stops the run before
anything is written.

Check (--check): reads program/program.md, confirms the twelve numbered
headings are present and in order, and counts per section the items that
are settled, open, unfilled, unmarked or invalid. Exits 2 while any
section in --require (default 4,5,6,7,8) has an item that is not settled.

Exit codes: 0 done; 1 bad input (one sentence says what to fix);
2 the programme file is not ready for the required sections.

Run with: python3 -I init_workspace.py <workspace> [--check] [--require 4,5,6,7,8]
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

# python3 -I leaves the script's own folder off the import path; add it
# so the sibling module below is found. Only this skill's folder is added.
sys.dont_write_bytecode = True  # keep the skill folder free of cache files
sys.path.insert(0, str(Path(__file__).resolve().parent))
import programme_file as pf  # noqa: E402

# Folder layout: references/schemas.md section 1 (build-time source, 2026-10-20).
# Dated files (longlists, shortlists, code plans, statements) and the
# workbook data/creator-programme.xlsx are made by the skills that own them.
FOLDERS = ("program", "data", "campaigns", "codes", "payouts", "exports", "agreements")

# Exact headers: references/schemas.md sections 4, 5 and 6 (2026-10-20).
# scripts/fixtures/run_fixtures.sh compares these with that file when the
# pack is present, so a schema change cannot drift past this script.
HEADERS = {
    "data/creators.csv": [
        "creator_ref", "display_name", "primary_platform", "primary_handle",
        "profile_url", "other_platforms", "tier", "followers_primary",
        "followers_as_of", "engagement_rate_pct", "engagement_as_of",
        "niche_tags", "audience_fit_score", "brand_safety_flag",
        "contact_path", "contact_email", "status", "compensation_model",
        "commission_rate_pct", "flat_fee", "code", "affiliate_link", "rail",
        "agreement_date", "agreement_file", "usage_rights_until",
        "exclusivity_until", "first_campaign", "last_activity", "notes",
    ],
    "data/pipeline.csv": [
        "campaign_slug", "creator_ref", "stage", "stage_date", "next_action",
        "next_action_date", "owner_role", "last_message_date",
        "offer_summary", "notes",
    ],
    "data/publications.csv": [
        "publication_id", "campaign_slug", "creator_ref", "platform",
        "post_url", "posted_at", "format", "disclosure_seen",
        "disclosure_form", "code_in_post", "link_in_post", "approval_id",
        "check_day1", "check_day7", "check_day30", "rights_until", "notes",
    ],
}

# Sections the downstream money and content skills read (build brief for
# program-setup; programme rules): compensation, tracking, the rail,
# claims, disclosure.
DEFAULT_REQUIRE = "4,5,6,7,8"


def fail(message):
    print(message)
    sys.exit(1)


def read_csv(path):
    """Header and data-row count of an existing CSV, or a problem sentence."""
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeDecodeError) as error:
        return None, 0, f"{path.name} could not be read ({error})"
    if not rows:
        return None, 0, f"{path.name} exists but is empty; add the header row or remove the file"
    return rows[0], len(rows) - 1, None


def header_problem(name, found, expected):
    missing = [c for c in expected if c not in found]
    extra = [c for c in found if c not in expected]
    if not missing and not extra and found != expected:
        return f"{name}: the columns are right but out of order; expected {','.join(expected)}"
    parts = []
    if missing:
        parts.append("missing " + ", ".join(missing))
    if extra:
        parts.append("extra " + ", ".join(extra))
    return f"{name}: header differs from schemas.md ({'; '.join(parts)})" if parts else None


def create(workspace):
    template = pf.TEMPLATE_PATH
    if not template.is_file():
        fail(f"The programme template is missing at {template}; reinstall the program-setup skill folder.")

    # Read every existing CSV first, so a bad header stops the run before any write.
    existing, problems = {}, []
    for name, expected in HEADERS.items():
        path = workspace / name
        if path.exists():
            header, count, problem = read_csv(path)
            problem = problem or header_problem(name, header, expected)
            if problem:
                problems.append(problem)
            else:
                existing[name] = count
    if problems:
        for problem in problems:
            print(problem)
        fail("Nothing was written. Fix the file(s) above with the creator-roster skill, or move them aside, then run again.")

    for folder in FOLDERS:
        path = workspace / folder
        state = "kept" if path.is_dir() else "created"
        path.mkdir(exist_ok=True)
        print(f"{state}: {folder}/")

    program = workspace / "program" / "program.md"
    if program.exists():
        print("kept: program/program.md (never overwritten)")
    else:
        shutil.copyfile(template, program)
        print("created: program/program.md from assets/program-template.md")

    for name, expected in HEADERS.items():
        path = workspace / name
        if name in existing:
            print(f"kept: {name} (header matches; {existing[name]} rows read, 0 added, 0 changed)")
            continue
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle, lineterminator="\n").writerow(expected)
        print(f"created: {name} (file was absent; 0 rows read, header written, 0 rows added)")

    print("Workspace ready. Next: fill program/program.md with the owner, then run this script with --check.")
    return 0


def parse_require(text):
    if text.strip().lower() == "all":
        return list(range(1, 13))
    try:
        nums = sorted({int(part) for part in text.split(",") if part.strip()})
    except ValueError:
        fail(f"--require takes 'all' or section numbers separated by commas, for example 4,5,6,7,8; got '{text}'.")
    if not nums or any(n < 1 or n > 12 for n in nums):
        fail(f"--require takes section numbers from 1 to 12; got '{text}'.")
    return nums


def check(workspace, require):
    program = workspace / "program" / "program.md"
    if not program.is_file():
        fail(f"No programme file at {program}; run this script without --check to create the workspace first.")
    try:
        template_text = pf.TEMPLATE_PATH.read_text(encoding="utf-8")
        program_text = program.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(f"Could not read the programme file or the template ({error}).")

    sections, items, problems = pf.analyse(program_text, template_text)
    if problems:
        for problem in problems:
            print(problem)
        fail("The programme file's headings do not match the template; restore them (headings are fixed), then run --check again.")

    by_section = {}
    for entry in items:
        by_section.setdefault(entry["section"], []).append(entry)

    print(f"Programme file check: {program}")
    for sec in sections:
        found = by_section.get(sec["num"], [])
        counts = {s: sum(1 for e in found if e["status"] == s) for s in pf.STATUSES}
        flag = " (required)" if sec["num"] in require else ""
        print(f"  {sec['num']:>2}. {sec['title']}{flag}: {len(found)} items, "
              + ", ".join(f"{counts[s]} {s}" for s in pf.STATUSES))

    blocking = [e for e in items if e["section"] in require and e["status"] != "settled"]
    other = [e for e in items if e["section"] not in require and e["status"] != "settled"]
    if blocking:
        print("Not settled in the required sections:")
        for e in blocking:
            print(f"  section {e['section']}: {e['status']}: {e['label']}" + (f" ({e['detail']})" if e["detail"] else ""))
    if other:
        elsewhere = ",".join(str(n) for n in sorted({e["section"] for e in other}))
        print(f"Not settled elsewhere: {len(other)} items in sections {elsewhere} "
              f"(run --check --require {elsewhere} to list them).")

    req = ",".join(str(n) for n in require)
    if blocking:
        open_sections = sorted({e["section"] for e in blocking})
        print(f"Result: partial. Sections {', '.join(str(n) for n in open_sections)} of the required {req} have "
              f"{len(blocking)} items not settled; skills that read them will stop and ask.")
        return 2
    print(f"Result: required sections {req} are settled.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Create the creator-programme workspace, or check program/program.md with --check.")
    parser.add_argument("workspace", help="path to the workspace folder (it must exist)")
    parser.add_argument("--check", action="store_true",
                        help="check program/program.md instead of creating the workspace")
    parser.add_argument("--require", default=DEFAULT_REQUIRE,
                        help="sections that must be settled for --check to exit 0: 'all', or numbers such as "
                             "4,5,6,7,8 (the default); creator-discovery needs 1,2,3,9")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        fail(f"The workspace folder {workspace} does not exist; create it or pass an existing folder.")
    if args.check:
        return check(workspace, parse_require(args.require))
    return create(workspace)


if __name__ == "__main__":
    sys.exit(main())
