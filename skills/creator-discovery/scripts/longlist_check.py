#!/usr/bin/env python3
"""Check a creator-discovery longlist before it goes to creator-vetting.

Usage:
  python3 -I scripts/longlist_check.py <workspace> <longlist.csv> [--sort]

What it checks:
  - the header is exactly the longlist header (pack schemas.md section 7);
  - the file is named data/longlist-YYYY-MM-DD.csv inside the workspace;
  - duplicates on platform plus normalised handle, and on normalised
    profile_url (reported, never deleted);
  - rows without profile_url, rows whose followers_source is `estimate`,
    values outside the allowed lists, ragged rows;
  - the notes evidence the skill requires (references/search-recipes.md
    section 9): `talks:` or `mentions` with a URL on `yes` rows,
    `contact:` on email, form and agent rows, `export:` on export rows;
  - the light screen: a row on a platform that programme section 3 marks
    `no` for organic creator posts carries a `screen:` note, and a platform
    with no decision is flagged; `unknown` marked [owner] or [default] is a
    ruling, listed and not flagged;
  - creators already on the roster (data/creators.csv), followed through
    `merged into` notes to the surviving record, with a `screen:` note
    required when that record is `excluded` or carries `do not contact`;
  - the order: creators who already talk about the category first, then
    unknown, then no, then screened rows (`--sort` rewrites the file in
    that order, changing no value).

Exit codes: 0 clean; 1 bad input (one sentence says what to fix);
2 rows flagged, duplicates found, the order is wrong, or a check was skipped.
The script reads files only in the workspace and this skill's folder, and
never calls the network.
"""

import argparse
import csv
import datetime
import re
import sys
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlsplit

# Pack references/schemas.md section 7, 2026-10-20.
HEADER = [
    "display_name", "platform", "handle", "profile_url", "followers",
    "followers_source", "niche_tags", "found_via",
    "already_talks_about_category", "contact_path", "notes",
]
# Pack schemas.md section 4 (primary_platform values), used by the roster too.
PLATFORMS = {
    "instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast",
    "newsletter", "bluesky", "threads", "other",
}
# Pack schemas.md section 7.
FOLLOWERS_SOURCES = {"profile", "search_result", "media_kit", "estimate"}
TALK_VALUES = {"yes", "no", "unknown"}
# Pack schemas.md section 4 (contact_path values).
CONTACT_PATHS = {"email", "dm", "agent", "form", "unknown"}
CONTACT_NEEDS_SOURCE = {"email", "form", "agent"}
# Programme template section 3: the row that rules each longlist platform.
# bluesky and threads have no row of their own, so the owner's `other` row rules them.
PROGRAMME_ROW = {
    "instagram": "instagram", "tiktok": "tiktok", "youtube": "youtube",
    "x": "x", "onlyfans": "onlyfans", "reddit": "reddit",
    "podcast": "podcasts and newsletters",
    "newsletter": "podcasts and newsletters",
    "bluesky": "other", "threads": "other", "other": "other",
}
# Pack schemas.md section 4: the roster columns this check reads.
ROSTER_NEEDS = [
    "creator_ref", "primary_platform", "primary_handle", "profile_url",
    "other_platforms", "status", "notes",
]
# Pack schemas.md sections 2 and 4: a duplicate retired by a merge keeps status
# `ended` with the note `merged into c-xxxxxx`; such a row is never counted, so a
# match follows it to the record that survived. `do not contact` is a fixed note.
MERGED = re.compile(r"merged into (c-[a-z0-9]{6})")
MERGED_STATUS = "ended"
DO_NOT_CONTACT = "do not contact"
# Programme template: [owner] and [default] mark a decision, [open] marks none.
MARK = re.compile(r"\[([a-z]+)\]")
RULED_MARKS = {"owner", "default"}
# Discovery order from the skill's brief: category talk first, screened rows last.
TALK_GROUP = {"yes": 0, "unknown": 1, "": 1, "no": 2}
SCREENED_GROUP = 3
# Pack schemas.md section 1: data/longlist-YYYY-MM-DD.csv.
FILE_NAME = re.compile(r"^longlist-(\d{4}-\d{2}-\d{2})\.csv$")
# references/search-recipes.md: every recipe is a heading of this shape.
RECIPE_HEADING = re.compile(r"^### `([a-z0-9-]+)`")
RECIPES_FILE = Path(__file__).resolve().parent.parent / "references" / "search-recipes.md"
# URL normalisation: these host prefixes and aliases point at the same profile.
HOST_PREFIXES = ("www.", "m.", "mobile.")
HOST_ALIASES = {"twitter.com": "x.com"}


class InputError(Exception):
    """Bad input: the message is the one sentence the person reads."""


def table_cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def classify_rule(cell, last_cell=""):
    """Turn an organic-creator-posts cell into yes, no, conditions, ruled-unknown or undecided.

    `unknown` is a ruling when the owner marked it: the mark on the cell itself,
    or else the row's mark, which template 0.1.2 puts at the end of the last cell.
    """
    value = re.sub(r"\[[^\]]*\]", "", cell).strip().lower()
    if not value:
        return "undecided"
    if value.startswith("with conditions"):
        return "conditions"
    first = re.split(r"[\s,;:.()]+", value)[0]
    if first in ("yes", "no"):
        return first
    if first == "unknown":
        marks = MARK.findall(cell.lower()) or MARK.findall(last_cell.lower())
        if marks and marks[-1] in RULED_MARKS:
            return "ruled-unknown"
    return "undecided"


def read_platform_rules(program_path):
    lines = program_path.read_text(encoding="utf-8-sig").splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r"^##\s+3\.", l)), None)
    if start is None:
        raise InputError(
            f"Programme section 3 (Platforms) was not found in {program_path}; "
            "restore the heading '## 3. Platforms' from the programme template.")
    end = next((j for j in range(start + 1, len(lines))
                if re.match(r"^##\s+\d+\.", lines[j])), len(lines))
    table = [l for l in lines[start + 1:end] if l.strip().startswith("|")]
    if len(table) < 2:
        raise InputError(
            "Programme section 3 has no platform table; run program-setup to fill it.")
    head = [c.lower() for c in table_cells(table[0])]
    try:
        pcol = head.index("platform")
        ocol = next(i for i, c in enumerate(head) if "organic" in c)
    except (ValueError, StopIteration):
        raise InputError(
            "Programme section 3's table has no 'platform' or 'organic creator posts' "
            "column; restore the columns from the programme template.")
    rules = {}
    for row in table[1:]:
        cells = table_cells(row)
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if len(cells) <= max(pcol, ocol):
            continue
        label = re.sub(r"\(.*?\)", "", cells[pcol]).strip().lower()
        rules[label] = (classify_rule(cells[ocol], cells[-1]), cells[ocol])
    return rules


def read_recipe_ids():
    if not RECIPES_FILE.exists():
        return None
    ids = set()
    for line in RECIPES_FILE.read_text(encoding="utf-8").splitlines():
        m = RECIPE_HEADING.match(line)
        if m:
            ids.add(m.group(1))
    return ids or None


def norm_handle(handle):
    h = " ".join(handle.strip().lower().split())
    h = h.lstrip("@")
    for prefix in ("/u/", "u/"):
        if h.startswith(prefix):
            h = h[len(prefix):]
    return h


def norm_url(url):
    """Lowercased host and path, no scheme, query, fragment or trailing slash.

    Profile handles in URLs are case-insensitive on the platforms the pack
    lists; a false match is only ever reported, never merged.
    """
    u = url.strip()
    if not u:
        return ""
    parts = urlsplit(u if "://" in u else "https://" + u)
    host = parts.netloc.lower()
    for prefix in HOST_PREFIXES:
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    host = HOST_ALIASES.get(host, host)
    return host + parts.path.rstrip("/").lower()


def is_web_address(url):
    parts = urlsplit(url.strip())
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def note_entries(notes):
    return [e.strip() for e in notes.split(";") if e.strip()]


def has_entry(entries, prefix, need_url=False):
    for e in entries:
        if e.lower().startswith(prefix) and (not need_url or "http" in e.lower()):
            return True
    return False


def has_evidence(entries):
    return has_entry(entries, "talks:", True) or has_entry(entries, "mentions ", True)


def row_group(row):
    entries = note_entries(row.get("notes", ""))
    if has_entry(entries, "screen:"):
        return SCREENED_GROUP
    return TALK_GROUP.get(row.get("already_talks_about_category", "").strip().lower(), 1)


def read_longlist(path):
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                raise InputError(f"{path.name} is empty; start it from assets/longlist-template.csv.")
            header = [h.strip() for h in header]
            if header != HEADER:
                missing = [h for h in HEADER if h not in header]
                extra = [h for h in header if h not in HEADER]
                detail = []
                if missing:
                    detail.append("missing: " + ", ".join(missing))
                if extra:
                    detail.append("not in the shape: " + ", ".join(extra))
                if not detail:
                    detail.append("the columns are out of order")
                raise InputError(
                    f"The header of {path.name} does not match the longlist shape "
                    f"({'; '.join(detail)}); copy the header from assets/longlist-template.csv.")
            rows = []
            for cells in reader:
                if not any(c.strip() for c in cells):
                    continue
                rows.append((reader.line_num, cells))
            return rows
    except UnicodeDecodeError:
        raise InputError(f"{path.name} could not be read as UTF-8; re-save it from the spreadsheet in the CSV UTF-8 format, then rerun.")


def write_longlist(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(HEADER)
        for cells in rows:
            writer.writerow(cells)


def read_roster(workspace):
    """Return (index, status, message). status is ran, absent or skipped."""
    path = workspace / "data" / "creators.csv"
    if not path.exists():
        return None, "absent", ("no roster yet at data/creators.csv, so no roster match was run "
                                "(normal before the first creator is added)")
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = [h.strip() for h in (reader.fieldnames or [])]
            missing = [c for c in ROSTER_NEEDS if c not in fields]
            if missing:
                return None, "skipped", ("roster match skipped: data/creators.csv lacks "
                                         + ", ".join(missing) + "; run creator-roster check")
            by_ref, by_handle, by_url = {}, defaultdict(list), defaultdict(list)
            for r in reader:
                r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
                ref = r["creator_ref"]
                if not ref:
                    continue
                by_ref[ref] = (r["status"].lower(), r["notes"])
                if r["primary_handle"]:
                    by_handle[(r["primary_platform"].lower(), norm_handle(r["primary_handle"]))].append(ref)
                for item in r["other_platforms"].split(";"):
                    if ":" in item:
                        plat, handle = item.split(":", 1)
                        by_handle[(plat.strip().lower(), norm_handle(handle))].append(ref)
                if r["profile_url"]:
                    by_url[norm_url(r["profile_url"])].append(ref)
    except UnicodeDecodeError:
        return None, "skipped", "roster match skipped: data/creators.csv is not UTF-8 text"
    message = "roster match run against data/creators.csv"
    book = workspace / "data" / "creator-programme.xlsx"
    if book.exists() and book.stat().st_mtime > path.stat().st_mtime:
        message += ("; the workbook data/creator-programme.xlsx is newer than the CSV: if it was "
                    "edited, run creator-roster import-xlsx first, then run this check again")
    return {"by_ref": by_ref, "by_handle": by_handle, "by_url": by_url}, "ran", message


def resolve_merges(roster, ref):
    """Follow `merged into` notes from ref to the surviving record.

    Returns (surviving_ref, status, notes, retired_refs, problem); problem is a
    phrase when the chain ends at a ref the roster lacks or loops.
    """
    chain = [ref]
    while True:
        status, notes = roster["by_ref"][chain[-1]]
        m = MERGED.search(notes) if status == MERGED_STATUS else None
        if not m:
            return chain[-1], status, notes, chain[:-1], None
        nxt = m.group(1)
        if nxt in chain:
            return chain[-1], status, notes, chain[:-1], "the merge notes loop (" + " -> ".join(chain + [nxt]) + ")"
        if nxt not in roster["by_ref"]:
            return nxt, "", "", chain, f"merged into {nxt}, which is not on the roster"
        chain.append(nxt)


def percent(part, whole):
    if not whole:
        return "0"
    value = Decimal(part) * 100 / Decimal(whole)
    return str(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def resolve_longlist(workspace, given):
    p = Path(given)
    if not p.is_absolute() and not p.exists():
        p = workspace / given
    if not p.exists():
        raise InputError(f"The longlist {given} was not found in the workspace's data/ folder.")
    m = FILE_NAME.match(p.name)
    if not m:
        raise InputError(f"{p.name} is not named longlist-YYYY-MM-DD.csv; rename it to the date the list was made.")
    try:
        datetime.date.fromisoformat(m.group(1))
    except ValueError:
        raise InputError(f"{p.name} carries an impossible date; rename it with the real date.")
    if p.resolve().parent != (workspace / "data").resolve():
        raise InputError(f"{p.name} is not in {workspace / 'data'}; the longlist belongs in the workspace's data/ folder.")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check a creator-discovery longlist (pack schemas.md section 7) before vetting.")
    ap.add_argument("workspace", help="the workspace folder (holds program/ and data/)")
    ap.add_argument("longlist", help="data/longlist-YYYY-MM-DD.csv, relative to the workspace or absolute")
    ap.add_argument("--sort", action="store_true",
                    help="rewrite the file in discovery order (category talk first, screened rows last); no value changes")
    args = ap.parse_args(argv)

    workspace = Path(args.workspace)
    if not workspace.is_dir():
        raise InputError(f"The workspace {workspace} is not a folder; give the workspace path first.")
    program = workspace / "program" / "program.md"
    if not program.exists():
        raise InputError(f"There is no programme file at {program}; run program-setup first.")
    rules = read_platform_rules(program)
    path = resolve_longlist(workspace, args.longlist)
    rows = read_longlist(path)

    out = [f"longlist_check: {path}"]
    if args.sort:
        order = sorted(range(len(rows)), key=lambda i: (row_group(dict(zip(HEADER, rows[i][1]))), i))
        moved = sum(1 for pos, i in enumerate(order) if pos != i)
        if moved:
            write_longlist(path, [rows[i][1] for i in order])
            rows = read_longlist(path)
        out.append(f"sort: read {len(rows)} rows, added 0, changed {moved} (position only, no value changed)")

    recipe_ids = read_recipe_ids()
    roster, roster_status, roster_message = read_roster(workspace)

    flags = defaultdict(list)          # line -> problems
    skipped = []
    if recipe_ids is None:
        skipped.append("found_via check skipped: references/search-recipes.md is missing or lists no recipes")
    if roster_status == "skipped":
        skipped.append(roster_message)

    by_platform = Counter()
    talk = Counter()
    sources = Counter()
    screened = 0
    conditions = Counter()
    ruled_unknown = defaultdict(list)
    by_handle = defaultdict(list)
    by_url = defaultdict(list)
    roster_hits = []
    yes_rows = []
    groups = []

    for line, cells in rows:
        if len(cells) != len(HEADER):
            flags[line].append(
                f"has {len(cells)} cells where the header has {len(HEADER)}; "
                "a comma inside a cell needs the cell in double quotes")
            groups.append(1)
            continue
        row = {k: v.strip() for k, v in zip(HEADER, cells)}
        entries = note_entries(row["notes"])
        platform = row["platform"].lower()
        handle = row["handle"]
        talk_value = row["already_talks_about_category"].lower()
        groups.append(row_group(row))
        is_screened = has_entry(entries, "screen:")
        screened += is_screened

        by_platform[platform or "(empty)"] += 1
        talk[talk_value or "unknown"] += 1
        sources[row["followers_source"] or "(empty)"] += 1

        if platform not in PLATFORMS:
            flags[line].append(f"platform '{row['platform']}' is not one of: {', '.join(sorted(PLATFORMS))}")
        if not handle:
            flags[line].append("no handle; for a podcast or newsletter use the show or publication name")
        if not row["profile_url"]:
            flags[line].append("no profile_url")
        elif not is_web_address(row["profile_url"]):
            flags[line].append("profile_url is not a web address starting http:// or https://")
        if row["followers"] and not row["followers"].isdigit():
            flags[line].append(f"followers '{row['followers']}' is not digits only (write 12400, not 12.4k or 12,400)")
        if row["followers_source"] and row["followers_source"] not in FOLLOWERS_SOURCES:
            flags[line].append(f"followers_source '{row['followers_source']}' is not one of: {', '.join(sorted(FOLLOWERS_SOURCES))}")
        if row["followers"] and not row["followers_source"]:
            flags[line].append("followers given without followers_source")
        if row["followers_source"] == "estimate":
            flags[line].append("followers_source is estimate: replace it with a count read from the profile, or leave both cells empty")
        tags = row["niche_tags"]
        if tags and any((not t) or t != t.strip() or t != t.lower() for t in tags.split(";")):
            flags[line].append("niche_tags must be lowercase, separated by ';' with no spaces around it")
        if recipe_ids is not None and row["found_via"] not in recipe_ids:
            flags[line].append(f"found_via '{row['found_via']}' is not a recipe id in references/search-recipes.md")
        if talk_value and talk_value not in TALK_VALUES:
            flags[line].append(f"already_talks_about_category '{row['already_talks_about_category']}' is not yes, no or unknown")
        if talk_value == "yes":
            yes_rows.append(f"line {line}: {platform}:{handle} ({row['found_via']})")
            if not has_evidence(entries):
                flags[line].append("already talks about the category is yes but notes carry no 'talks:' or 'mentions' entry with a URL")
        contact = row["contact_path"].lower()
        if contact and contact not in CONTACT_PATHS:
            flags[line].append(f"contact_path '{row['contact_path']}' is not one of: {', '.join(sorted(CONTACT_PATHS))}")
        if contact in CONTACT_NEEDS_SOURCE and not has_entry(entries, "contact:", True):
            flags[line].append(f"contact_path is {contact} but notes carry no 'contact:' entry with the public page where it is shown")
        if row["found_via"] == "export" and not any(e.lower().startswith("export:") and "exports/" in e for e in entries):
            flags[line].append("found_via is export but notes carry no 'export: exports/<file> row <n> map ...' entry")

        if platform in PROGRAMME_ROW:
            label = PROGRAMME_ROW[platform]
            rule, raw = rules.get(label, ("missing", ""))
            if rule == "missing":
                flags[line].append(f"programme section 3 has no row '{label}' to rule platform {platform}")
            elif rule == "undecided":
                flags[line].append(f"programme section 3 has no decision for organic creator posts on '{label}' (cell: '{raw}')")
            elif rule == "no" and not is_screened:
                flags[line].append(f"programme section 3 says no to organic creator posts on '{label}'; add a 'screen:' note")
            elif rule == "conditions":
                conditions[label] += 1
            elif rule == "ruled-unknown":
                ruled_unknown[label].append(str(line))

        if handle and platform:
            by_handle[(platform, norm_handle(handle))].append(line)
        if row["profile_url"]:
            by_url[norm_url(row["profile_url"])].append(line)

        if roster is not None:
            refs = []
            if handle:
                refs += roster["by_handle"].get((platform, norm_handle(handle)), [])
            if row["profile_url"]:
                refs += roster["by_url"].get(norm_url(row["profile_url"]), [])
            survivors = set()
            # A direct match on a live record is reported before a match through a retired one.
            resolved = sorted(((ref,) + resolve_merges(roster, ref) for ref in dict.fromkeys(refs)),
                              key=lambda t: (t[5] is not None, len(t[4])))
            for ref, kept, status, notes, retired, problem in resolved:
                if kept in survivors:
                    continue
                survivors.add(kept)
                who = f"line {line}: {platform}:{handle}"
                if problem:
                    roster_hits.append(f"{who} matches {ref}, {problem}; run creator-roster check")
                    flags[line].append(f"matches {ref}, {problem}; run creator-roster check before relying on this row")
                    continue
                dnc = DO_NOT_CONTACT in notes.lower()
                tail = f"status {status or '(empty)'}" + (f", notes carry '{DO_NOT_CONTACT}'" if dnc else "")
                if retired:
                    steps = ", ".join(f"{a} merged into {b}" for a, b in zip(retired, retired[1:] + [kept]))
                    roster_hits.append(f"{who} matches {retired[0]}, a record retired by merge ({steps}); "
                                       f"the surviving record is {kept}, {tail}")
                else:
                    roster_hits.append(f"{who} is {kept} on the roster, {tail}")
                if status == "excluded" and not is_screened:
                    flags[line].append(f"matches {kept}, excluded on the roster; add a 'screen:' note")
                if dnc and not is_screened:
                    flags[line].append(f"matches {kept}, whose roster notes carry '{DO_NOT_CONTACT}'; add a 'screen:' note")

    dup_groups = []
    for (plat, h), lines in sorted(by_handle.items()):
        if len(lines) > 1:
            dup_groups.append(f"platform {plat}, handle {h}: lines {', '.join(map(str, lines))}")
    for u, lines in sorted(by_url.items()):
        if len(lines) > 1:
            dup_groups.append(f"profile_url {u}: lines {', '.join(map(str, lines))}")

    in_order = all(a <= b for a, b in zip(groups, groups[1:]))

    n = len(rows)
    out.append(f"rows read: {n}")
    if n == 0:
        out.append("the file has a header and no rows: nothing was recorded")
    out.append("per platform: " + (", ".join(f"{k} {v}" for k, v in sorted(by_platform.items())) or "none"))
    out.append(
        f"already talks about the category: yes {talk['yes']} of {n} ({percent(talk['yes'], n)} percent), "
        f"no {talk['no']}, unknown {talk['unknown']} (counted from this file)")
    out.append("followers_source: " + (", ".join(f"{k} {v}" for k, v in sorted(sources.items())) or "none"))
    out.append(f"screened rows (notes carry 'screen:'): {screened}")
    if conditions:
        out.append("rows on platforms allowed with conditions in programme section 3: "
                   + ", ".join(f"{k} {v}" for k, v in sorted(conditions.items())))
    if ruled_unknown:
        out.append("rows on platforms the owner ruled unknown in programme section 3 (a ruling, not a gap; "
                   "creator-vetting holds them at negotiate): "
                   + "; ".join(f"{k} lines {', '.join(v)}" for k, v in sorted(ruled_unknown.items())))
    out.append("order: " + ("discovery order (category talk first, screened rows last)" if in_order
                            else "NOT in discovery order; run again with --sort"))
    if yes_rows:
        out.append("already talk about the category:")
        out.extend("  " + r for r in yes_rows)
    out.append("roster: " + roster_message)
    out.extend("  " + h for h in roster_hits)
    if dup_groups:
        out.append(f"DUPLICATES ({len(dup_groups)} groups; nothing deleted):")
        out.extend("  " + d for d in dup_groups)
    if flags:
        out.append(f"FLAGGED ROWS ({len(flags)}):")
        for line in sorted(flags):
            for problem in flags[line]:
                out.append(f"  line {line}: {problem}")
    for s in skipped:
        out.append("SKIPPED: " + s)

    ran = ["header", "file name", "allowed values", "duplicates", "notes evidence",
           "platform screen against programme section 3"]
    if recipe_ids is not None:
        ran.append("found_via recipe ids")
    if roster_status == "ran":
        ran.append("roster match")
    out.append(
        "coverage: checked " + ", ".join(ran)
        + ("; not run: " + "; ".join(skipped) if skipped else "")
        + "; not checkable by this script: programme section 9 redlines and content suitability, whether an "
          "evidence URL shows what its note says, whether a contact path is really public, "
          "whether two different handles are the same person")

    problems = bool(flags) or bool(dup_groups) or not in_order or bool(skipped)
    if problems:
        words, parts = [], []
        if skipped:
            words.append("PARTIAL")
            parts.append(f"{len(skipped)} checks skipped")
        if flags or dup_groups or not in_order:
            words.append("FLAGGED")
        if flags:
            parts.append(f"{len(flags)} flagged rows")
        if dup_groups:
            parts.append(f"{len(dup_groups)} duplicate groups")
        if not in_order:
            parts.append("not in discovery order")
        out.append("RESULT: " + ", ".join(words) + " (" + ", ".join(parts) + ")")
    else:
        out.append("RESULT: CLEAN")
    print("\n".join(out))
    return 2 if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InputError as e:
        print(f"longlist_check: {e}")
        sys.exit(1)
