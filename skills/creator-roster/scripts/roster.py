#!/usr/bin/env python3
"""Keep the creator programme's register valid, and move it to and from the workbook.

Usage:  python3 -I roster.py <workspace> <command> [options]
        python3 -I roster.py <workspace> <command> --help

Commands: check, find, add, update, merge, report, export-xlsx, import-xlsx, schema.

Exit codes (references/schemas.md section 5): 0 done; 1 bad input or a schema break,
nothing written, the message says what to fix; 2 partial or warnings, the output
says what was skipped or what needs a person.

The headers and allowed values of the three CSVs are read at every run from
../references/schemas.md, the runtime copy of the pack's schemas: that copy is
the law. Windows, ages and value meanings are read from
../references/roster-rules.md. Value shapes (dates, numbers, identifiers) are in
SHAPE below, from schemas.md sections 2 to 6. Standard library only; no network.
"""

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import random
import re
import secrets
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCHEMA_FILE = os.path.join(SKILL_DIR, "references", "schemas.md")
RULES_FILE = os.path.join(SKILL_DIR, "references", "roster-rules.md")

TABLES = ("creators", "pipeline", "publications")
CSV_PATH = {"creators": "data/creators.csv", "pipeline": "data/pipeline.csv",
            "publications": "data/publications.csv"}          # schemas.md section 1
SCHEMA_SECTION = {"creators": 4, "pipeline": 5, "publications": 6}
LONGLIST_SECTION = 7
SHORTLIST_SECTION = 8
PROGRAM_FILE = "program/program.md"
ROLES_SECTION = 10                                            # program template section 10
WORKBOOK_DEFAULT = "data/creator-programme.xlsx"              # schemas.md section 1.1

OK, BAD, PARTIAL = 0, 1, 2

# Value shapes by column. Identifier shapes: schemas.md section 2. The others:
# the "allowed values" of sections 4 to 6. Enumerations are not listed here;
# they are read from schemas.md at every run.
SHAPE = {
    "creator_ref": "ref", "publication_id": "pubid", "campaign_slug": "slug",
    "first_campaign": "slug", "approval_id": "approval", "code": "code",
    "profile_url": "url", "affiliate_link": "url", "post_url": "url",
    "followers_primary": "int", "audience_fit_score": "int",
    "engagement_rate_pct": "decimal", "commission_rate_pct": "decimal", "flat_fee": "decimal",
    "followers_as_of": "date", "engagement_as_of": "date", "agreement_date": "date",
    "usage_rights_until": "date", "exclusivity_until": "date", "last_activity": "date",
    "stage_date": "date", "next_action_date": "date", "last_message_date": "date",
    "rights_until": "date", "posted_at": "utctime", "contact_email": "email",
    "other_platforms": "platformlist", "niche_tags": "taglist", "notes": "notes",
    "agreement_file": "agreementpath", "primary_handle": "handle",
}
# Dates that record something already observed or done, so a date after the
# run date is probably a typing slip (a warning, never a break).
PAST_DATES = ("followers_as_of", "engagement_as_of", "agreement_date", "last_activity",
              "stage_date", "last_message_date", "posted_at")
KEY = {"creators": ("creator_ref",), "pipeline": ("campaign_slug", "creator_ref"),
       "publications": ("publication_id",)}
REQUIRED = {"creators": ("creator_ref",), "pipeline": ("campaign_slug", "creator_ref"),
            "publications": ("publication_id", "creator_ref")}

SLUG = r"\d{4}-(?:0[1-9]|1[0-2])-[a-z0-9]+(?:-[a-z0-9]+)*"
REF = r"c-[a-z0-9]{6}"
PATTERN = {
    "ref": re.compile(REF + r"\Z"),
    "pubid": re.compile(r"p-[a-z0-9]{6}\Z"),
    "slug": re.compile(SLUG + r"\Z"),
    "code": re.compile(r"[A-Z0-9]{4,20}\Z"),
    "approval": re.compile(SLUG + "--" + REF + r"--[1-9][0-9]*\Z"),
    "int": re.compile(r"[0-9]+\Z"),
    "decimal": re.compile(r"[0-9]+(?:\.[0-9]+)?\Z"),
    "url": re.compile(r"https?://\S+\Z"),
    "email": re.compile(r"[^@\s;,]+@[^@\s;,]+\.[^@\s;,]+\Z"),
    "date": re.compile(r"\d{4}-\d{2}-\d{2}\Z"),
    "utctime": re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\Z"),
    "platformitem": re.compile(r"([a-z]+):(@\S+)\Z"),
}
SHAPE_WORDS = {
    "ref": "a creator_ref such as c-7k2m9q", "pubid": "a publication_id such as p-3x9k2a",
    "slug": "a campaign slug such as 2026-12-holiday-tote",
    "code": "upper-case letters and digits only, 4 to 20 characters",
    "approval": "<campaign_slug>--<creator_ref>--<n>", "int": "a whole number",
    "decimal": "a plain decimal with no symbol, such as 34.00 or 15",
    "url": "a URL starting http:// or https://", "email": "an email address",
    "date": "a date written YYYY-MM-DD", "utctime": "a UTC time written YYYY-MM-DDTHH:MMZ",
    "platformlist": "a ';' list of platform:@handle", "taglist": "a ';' list of lower-case tags",
    "notes": "dated entries separated by ';'", "agreementpath": "a path under agreements/",
    "handle": "a handle with a leading @",
}
HASHLIKE = re.compile(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32})(?![0-9a-fA-F])")
EMAIL_IN_TEXT = re.compile(r"[^@\s;,()<>]+@[^@\s;,()<>]+\.[A-Za-z]{2,}")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
PLACEHOLDERS = {"n/a", "#n/a", "null", "nan", "-", "--", "–", "—"}  # schemas.md section 3
MERGED = re.compile(r"merged into (" + REF + r")")
# The fixed notes entries other skills read (schemas.md section 4).
DO_NOT_CONTACT = re.compile(r"\bdo not contact\b", re.I)
RIGHTS_FROM_POSTING = re.compile(r"\brights from posting:\s*([0-9]+)\s+months?\b", re.I)
RIGHTS_FROM_POSTING_LOOSE = re.compile(r"\brights from posting\b", re.I)
ANY_REF = re.compile(r"(?<![a-z0-9-])" + REF + r"(?![a-z0-9])")
REF_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"   # schemas.md section 2
EXCEL_CELL_LIMIT = 32767   # the most characters Excel keeps in one cell


class Stop(Exception):
    """Bad input. The message says what to fix; nothing is written; exit 1."""


# ---------------------------------------------------------------- small helpers

def today_utc():
    return dt.datetime.now(dt.timezone.utc).date()


def parse_date_arg(text, flag):
    if text is None:
        return today_utc()
    try:
        if not PATTERN["date"].match(text):
            raise ValueError
        return dt.date.fromisoformat(text)
    except ValueError:
        raise Stop(f"{flag} '{text}' is not a date written YYYY-MM-DD.")


def as_date(value):
    """The date part of a date or UTC-time cell, or None."""
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def plural(n, word, many=None):
    return f"{n} {word if n == 1 else (many or word + 's')}"


def split_list(value):
    return [] if value == "" else value.split(";")


def note_safe(text):
    """Notes are a ';' list of dated entries, so an entry cannot hold ';' or a line break."""
    return re.sub(r"\s+", " ", text.replace(";", ",")).strip()


def workspace_of(args):
    ws = os.path.abspath(args.workspace)
    if not os.path.isdir(ws):
        raise Stop(f"the workspace folder '{args.workspace}' does not exist. Give the folder that holds program/ and data/.")
    return ws


def inside(ws, path):
    real_ws = os.path.realpath(ws)
    real = os.path.realpath(path)
    return real == real_ws or real.startswith(real_ws + os.sep)


def resolve_out(ws, given, default):
    path = given or default
    path = path if os.path.isabs(path) else os.path.join(ws, path)
    if not inside(ws, path):
        raise Stop(f"'{given}' is outside the workspace. This skill writes only inside {ws}.")
    return path


def resolve_in(ws, given):
    for path in (given, os.path.join(ws, given)):
        if os.path.isfile(path):
            return path
    raise Stop(f"'{given}' was not found, either as given or inside the workspace.")


def make_rng(seed):
    return random.Random(seed) if seed is not None else secrets.SystemRandom()


def col_letters(index):
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


# ---------------------------------------------------------------- the schema

def parse_allowed(text):
    """Read one 'allowed values' cell of schemas.md into a column spec."""
    tokens = [t for t in re.findall(r"`([^`]*)`", text) if t != ";"]
    bare = re.sub(r"`[^`]*`", " ", re.sub(r"\([^)]*\)", " ", text))
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", bare)]
    spec = {"enum": None, "multi": False, "same_as_platform": False, "range": None}
    if "as in the roster" in text:
        spec["same_as_platform"] = True
    elif tokens and all(w in ("and", "or") for w in words):
        spec["enum"] = tokens
    elif tokens and "list" in words and set(words) <= {"list", "of", "and", "or"}:
        spec["enum"], spec["multi"] = tokens, True
    m = re.search(r"integer\s+(\d+)\s+to\s+(\d+)", text)
    if m:
        spec["range"] = (int(m.group(1)), int(m.group(2)))
    return spec


def parse_band(text):
    """'under 10,000', '10,000 to 49,999', '500,000 and up' -> (low, high), high excluded, None for no top.

    Read as written in schemas.md section 4: "under" excludes its figure, "a to b"
    includes both, "and up" includes its figure."""
    nums = []
    for number, unit in re.findall(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kKmM]?)\b", text):
        nums.append(int(float(number.replace(",", "")) * {"": 1, "k": 1000, "m": 1000000}[unit.lower()]))
    t = text.lower().strip()
    if t.startswith("under") and len(nums) == 1:
        return (0, nums[0])
    if " to " in t and len(nums) == 2:
        return (nums[0], nums[1] + 1)
    if ("and up" in t or "and over" in t) and len(nums) == 1:
        return (nums[0], None)
    return None


def bands_meet(bands):
    """True when the bands start at 0, follow on without gap or overlap, and only the last is open."""
    ordered = sorted(bands, key=lambda b: b[1])
    if not ordered or ordered[0][1] != 0:
        return False
    for (_, _, high), (_, low, _) in zip(ordered, ordered[1:]):
        if high is None or high != low:
            return False
    return True


def read_schema():
    try:
        with open(SCHEMA_FILE, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        raise Stop("references/schemas.md is missing from the skill folder. Reinstall creator-roster; it carries the runtime copy of the schemas.")
    sections, current = {}, None
    for line in text.splitlines():
        m = re.match(r"##\s+(\d+)\.\s", line)
        if m:
            current = int(m.group(1))
            sections[current] = []
        elif line.startswith("## "):
            current = None
        elif current is not None:
            sections[current].append(line)
    schema = {"cols": {}, "header": {}, "verdicts": [], "tier_bands": None}
    for table, number in SCHEMA_SECTION.items():
        cols = {}
        for line in sections.get(number, []):
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            names = re.findall(r"`([^`]+)`", cells[0])
            if not names or len(cells) < 2:
                continue
            spec = parse_allowed(cells[-1])
            for name in names:
                if name in cols:
                    raise Stop(f"references/schemas.md section {number} lists column {name} twice.")
                cols[name] = dict(spec)
            if names == ["tier"]:
                bands = []
                for token, band in re.findall(r"`([a-z]+)`\s*\(([^)]*)\)", cells[-1]):
                    parsed = parse_band(band)
                    if parsed is None:
                        bands = None
                        break
                    bands.append((token, parsed[0], parsed[1]))
                schema["tier_bands"] = bands if bands and bands_meet(bands) else None
        if not cols:
            raise Stop(f"references/schemas.md section {number} has no column table the script can read.")
        schema["cols"][table] = cols
        schema["header"][table] = list(cols)
    platforms = schema["cols"]["creators"].get("primary_platform", {}).get("enum")
    if not platforms:
        raise Stop("references/schemas.md section 4 gives no allowed values for primary_platform.")
    for table in TABLES:
        for spec in schema["cols"][table].values():
            if spec["same_as_platform"]:
                spec["enum"] = list(platforms)
    m = re.search(r"`verdict`\s*\(([^)]*)\)", "\n".join(sections.get(SHORTLIST_SECTION, [])))
    if not m:
        raise Stop("references/schemas.md section 8 gives no allowed values for verdict.")
    schema["verdicts"] = re.findall(r"`([^`]+)`", m.group(1))
    labels = {}
    section7 = " ".join(sections.get(LONGLIST_SECTION, []))
    for names, label in re.findall(r"((?:`[a-z_]+`(?:,\s*|\s+and\s+)?)+)\s+(?:is|are)\s+(Measured|User-provided|Estimated)", section7):
        for name in re.findall(r"`([a-z_]+)`", names):
            labels[name] = label
    schema["followers_labels"] = labels
    section8 = " ".join(sections.get(SHORTLIST_SECTION, []))
    schema["total_optional_verdicts"] = tuple(re.findall(r"`([a-z_]+)` row may carry an empty `total`", section8))
    schema["platforms"] = list(platforms)
    return schema


def enum_of(schema, table, column):
    return schema["cols"][table].get(column, {}).get("enum") or []


def tier_for(followers, bands):
    for name, low, high in bands or []:
        if followers >= low and (high is None or followers < high):
            return name
    return None


# ---------------------------------------------------------------- rules and roles

RULE_LISTS = {
    "rights_ending_within_days": ("days", None), "exclusivity_ending_within_days": ("days", None),
    "stale_after_days": ("days", None), "default_add_verdicts": ("verdict", None),
    "new_creator_status": ("creators", "status"), "excluded_verdict": ("verdict", None),
    "excluded_status": ("creators", "status"), "excluded_flag": ("creators", "brand_safety_flag"),
    "merged_status": ("creators", "status"), "stale_skips_statuses": ("creators", "status"),
    "needs_agreement_date": ("creators", "status"), "code_expected_status": ("creators", "status"),
    "rate_models": ("creators", "compensation_model"), "fee_models": ("creators", "compensation_model"),
    "pipeline_done_stages": ("pipeline", "stage"), "stages_graded_elsewhere": ("pipeline", "stage"),
}


def read_rules(schema):
    try:
        with open(RULES_FILE, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        raise Stop("references/roster-rules.md is missing from the skill folder. Reinstall creator-roster.")
    m = re.search(r"```settings\n(.*?)```", text, re.S)
    if not m:
        raise Stop("references/roster-rules.md has no settings block the script can read.")
    rules = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        rules[key.strip()] = [v.strip() for v in value.split(",") if v.strip()]
    for key, (kind, column) in RULE_LISTS.items():
        values = rules.get(key)
        if not values:
            raise Stop(f"references/roster-rules.md has no value for {key}.")
        if kind == "days":
            if not all(v.isdigit() for v in values):
                raise Stop(f"references/roster-rules.md: {key} must be whole numbers of days.")
            rules[key] = sorted(int(v) for v in values)
            continue
        allowed = schema["verdicts"] if kind == "verdict" else enum_of(schema, kind, column)
        for v in values:
            if v not in allowed:
                raise Stop(f"references/roster-rules.md: {key} names '{v}', which references/schemas.md does not allow ({', '.join(allowed)}).")
    return rules


def read_roles(ws):
    path = os.path.join(ws, PROGRAM_FILE)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    roles, in_section = [], False
    for line in lines:
        m = re.match(r"##\s+(\d+)\.", line)
        if m:
            in_section = int(m.group(1)) == ROLES_SECTION
            continue
        if in_section and line.strip().startswith("|"):
            first = re.sub(r"[*`]", "", line.strip().strip("|").split("|")[0]).strip()
            if first and not re.fullmatch(r":?-{3,}:?", first) and first.lower() != "role":
                roles.append(first.lower())
    return roles


def require_role(ws, role):
    roles = read_roles(ws)
    if roles is None:
        raise Stop(f"{PROGRAM_FILE} was not found. Run program-setup first: every note names a role from its section {ROLES_SECTION}.")
    if not roles:
        raise Stop(f"{PROGRAM_FILE} section {ROLES_SECTION} lists no roles. Fill it with program-setup.")
    if not role:
        raise Stop(f"say who is making the change with --role, one of: {', '.join(roles)}. A role, never a name.")
    if role.strip().lower() not in roles:
        raise Stop(f"'{role}' is not a role in {PROGRAM_FILE} section {ROLES_SECTION} ({', '.join(roles)}). Use one of those; never a person's name.")
    return role.strip().lower()


# ---------------------------------------------------------------- problems

class Problems:
    def __init__(self):
        self.items = []
        self.not_checked = []

    def brk(self, where, msg, structural=False):
        self.items.append(("BREAK", where, msg, structural))

    def warn(self, where, msg):
        self.items.append(("WARN", where, msg, False))

    @property
    def breaks(self):
        return [i for i in self.items if i[0] == "BREAK"]

    @property
    def warnings(self):
        return [i for i in self.items if i[0] == "WARN"]

    @property
    def structural(self):
        return [i for i in self.items if i[3]]

    def lines(self):
        return [f"  {level} {where}: {msg}" for level, where, msg, _ in self.items]


# ---------------------------------------------------------------- CSV files

class Table:
    def __init__(self, name, path, header, rows, lines, bom, newline):
        self.name, self.path, self.header = name, path, header
        self.rows, self.lines, self.bom, self.newline = rows, lines, bom, newline
        self.header_ok = True
        self.read_count = len(rows)

    def copy(self):
        t = Table(self.name, self.path, list(self.header), [dict(r) for r in self.rows],
                  list(self.lines), self.bom, self.newline)
        t.header_ok, t.read_count = self.header_ok, self.read_count
        return t


def where_of(table, index, row):
    key = ", ".join(row.get(k, "") for k in KEY[table.name]) if row else ""
    line = table.lines[index] if index < len(table.lines) else "new"
    return f"{CSV_PATH[table.name]} line {line}" + (f" ({key})" if key.strip(", ") else "")


def load_tables(ws, schema, problems):
    tables = {}
    for name in TABLES:
        path = os.path.join(ws, CSV_PATH[name])
        rel = CSV_PATH[name]
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except FileNotFoundError:
            problems.brk(rel, "the file is missing. Run program-setup's init_workspace to create the header-only files.", True)
            continue
        bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.brk(rel, "the file is in another text encoding. Re-save it in the CSV UTF-8 format and run again.", True)
            continue
        newline = "\r\n" if "\r\n" in text else "\n"
        reader = csv.reader(io.StringIO(text, newline=""))
        header, rows, lines = None, [], []
        try:
            for cells in reader:
                if header is None:
                    header = cells
                    continue
                if not cells or (len(cells) == 1 and cells[0] == ""):
                    continue
                if len(cells) != len(header):
                    problems.brk(f"{rel} line {reader.line_num}",
                                 f"the row has {len(cells)} cells; the header has {len(header)}. A comma inside a value needs the value in double quotes.", True)
                    continue
                rows.append(dict(zip(header, cells)))
                lines.append(reader.line_num)
        except csv.Error as exc:
            problems.brk(rel, f"the file is not readable CSV ({exc}).", True)
            continue
        if header is None:
            problems.brk(rel, "the file is empty; it needs at least the header row.", True)
            continue
        t = Table(name, path, header, rows, lines, bom, newline)
        expected = schema["header"][name]
        if header != expected:
            t.header_ok = False
            missing = [c for c in expected if c not in header]
            extra = [c for c in header if c not in expected]
            parts = []
            if missing:
                parts.append("missing column " + ", ".join(missing))
            if extra:
                parts.append("extra column " + ", ".join(extra))
            if not parts:
                parts.append("the columns are out of order")
            problems.brk(f"{rel} header", "; ".join(parts) + f". The header must be exactly, in order: {','.join(expected)}", True)
        tables[name] = t
    return tables


def render_table(t):
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator=t.newline)
    writer.writerow(t.header)
    for row in t.rows:
        writer.writerow([row[c] for c in t.header])
    data = buf.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if t.bom else data


def commit(tables):
    """Write every table to a temporary file first, then move each into place."""
    staged = []
    try:
        for t in tables:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(t.path), prefix=".roster-", suffix=".tmp")
            with os.fdopen(fd, "wb") as fh:
                fh.write(render_table(t))
            staged.append((tmp, t.path))
        for tmp, path in staged:
            os.replace(tmp, path)
    except OSError as exc:
        for tmp, _ in staged:
            if os.path.exists(tmp):
                os.remove(tmp)
        raise Stop(f"could not write the files ({exc}).")


def counts_line(t, added, changed):
    return f"{CSV_PATH[t.name]}: read {t.read_count}, added {added}, changed {changed}"


# ---------------------------------------------------------------- merged records and identity

def merged_into(row, merged_status):
    if row.get("status") != merged_status:
        return None
    found = MERGED.findall(row.get("notes", ""))
    return found[-1] if found else None


def no_contact(row):
    return bool(DO_NOT_CONTACT.search(row.get("notes", "")))


def months_from_posting(row):
    """The n of the last 'rights from posting: <n> months' entry, or None."""
    found = RIGHTS_FROM_POSTING.findall(row.get("notes", ""))
    return int(found[-1]) if found else None


def note_dates(row):
    return [d for d in (as_date(m) for m in re.findall(r"(?:^|;)\s*(\d{4}-\d{2}-\d{2})", row.get("notes", ""))) if d]


def kept_ref(ref, by_ref, merged_status):
    seen = set()
    while ref in by_ref and ref not in seen:
        seen.add(ref)
        target = merged_into(by_ref[ref], merged_status)
        if not target:
            return ref
        ref = target
    return ref


def norm_handle(handle):
    h = handle.strip().lower().rstrip("/")
    return h[1:] if h.startswith("@") else h


def norm_url(url):
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^(?:www\.|m\.)", "", u)
    return re.split(r"[?#]", u)[0].rstrip("/")


def identity_keys(row):
    keys = []
    if row.get("primary_platform") and norm_handle(row.get("primary_handle", "")):
        keys.append(("handle", row["primary_platform"].strip().lower(), norm_handle(row["primary_handle"])))
    for item in split_list(row.get("other_platforms", "")):
        platform, _, handle = item.partition(":")
        if platform and norm_handle(handle):
            keys.append(("handle", platform.strip().lower(), norm_handle(handle)))
    if row.get("profile_url") and norm_url(row["profile_url"]):
        keys.append(("url", norm_url(row["profile_url"])))
    return keys


def describe_key(key):
    return f"{key[1]} @{key[2]}" if key[0] == "handle" else f"profile URL {key[1]}"


class Identity:
    """Normalised platform and handle, and profile URL, to the record that holds them."""

    def __init__(self, rows, merged_status, skip_ref=None):
        by_ref = {r["creator_ref"]: r for r in rows}
        self.index = {}
        for row in rows:
            if row["creator_ref"] == skip_ref:
                continue
            target = kept_ref(row["creator_ref"], by_ref, merged_status)
            if target == skip_ref:
                continue
            for key in identity_keys(row):
                self.index.setdefault(key, set()).add(target)

    def add(self, row, ref):
        for key in identity_keys(row):
            self.index.setdefault(key, set()).add(ref)

    def match(self, row):
        found = {}
        for key in identity_keys(row):
            for ref in self.index.get(key, ()):
                found.setdefault(ref, []).append(describe_key(key))
        return found


# ---------------------------------------------------------------- validation

def check_cell(schema, table, column, value, where, problems):
    spec = schema["cols"][table].get(column, {})
    shape = SHAPE.get(column)
    if value == "":
        if column in REQUIRED[table]:
            problems.brk(where, f"{column} is empty; every row needs it.")
        return
    if CONTROL.search(value):
        problems.brk(where, f"{column} holds a control character, which the workbook cannot carry. Retype the value.")
    if len(value) > EXCEL_CELL_LIMIT:
        problems.warn(where, f"{column} is longer than Excel keeps in one cell ({EXCEL_CELL_LIMIT} characters).")
    if shape not in ("url",) and HASHLIKE.search(value):
        problems.brk(where, f"{column} holds what looks like a hashed identifier. A hashed customer email is for repeat-purchase counting inside the report scripts and never enters the roster; remove it.")
    if column != "contact_email" and shape != "url" and EMAIL_IN_TEXT.search(value):
        problems.warn(where, f"{column} holds an email address. The roster keeps a creator's address only in contact_email, and only when it is public or the creator gave it.")
    enum = spec.get("enum")
    if enum:
        items = split_list(value) if spec.get("multi") else [value]
        if spec.get("multi") and any(i != i.strip() or i == "" for i in items):
            problems.brk(where, f"{column}: list items are separated by ';' with no spaces and no empty items.")
            return
        bad = [i for i in items if i not in enum]
        if bad:
            problems.brk(where, f"{column}: '{';'.join(bad)}' is not one of: {', '.join(enum)}.")
        return
    if value.strip().lower() in PLACEHOLDERS:
        problems.brk(where, f"{column} says '{value}'. Leave the cell empty for unknown; never N/A, null or a dash.")
        return
    if shape in ("date", "utctime"):
        ok = bool(PATTERN[shape].match(value))
        if ok:
            try:
                if shape == "date":
                    dt.date.fromisoformat(value)
                else:
                    dt.datetime.strptime(value, "%Y-%m-%dT%H:%MZ")
            except ValueError:
                ok = False
        if not ok:
            problems.brk(where, f"{column}: '{value}' is not {SHAPE_WORDS[shape]}.")
    elif shape in ("int", "decimal", "ref", "pubid", "slug", "code", "approval", "url", "email"):
        if not PATTERN[shape].match(value):
            problems.brk(where, f"{column}: '{value}' is not {SHAPE_WORDS[shape]}.")
        elif shape == "int" and spec.get("range"):
            low, high = spec["range"]
            if not low <= int(value) <= high:
                problems.brk(where, f"{column}: {value} is outside {low} to {high}.")
    elif shape in ("platformlist", "taglist"):
        items = split_list(value)
        if any(i != i.strip() or i == "" for i in items):
            problems.brk(where, f"{column}: list items are separated by ';' with no spaces and no empty items.")
        elif shape == "taglist" and any(i != i.lower() for i in items):
            problems.brk(where, f"{column}: tags are lower case.")
        elif shape == "platformlist":
            for item in items:
                m = PATTERN["platformitem"].match(item)
                if not m or m.group(1) not in schema["platforms"]:
                    problems.brk(where, f"{column}: '{item}' is not platform:@handle with a platform from: {', '.join(schema['platforms'])}.")
    elif shape == "agreementpath":
        if not value.startswith("agreements/") or ".." in value.split("/"):
            problems.brk(where, f"{column}: '{value}' is not a path under agreements/.")
    elif shape == "handle" and not value.startswith("@"):
        problems.warn(where, f"{column}: '{value}' has no leading @ (schemas.md section 4 keeps handles with @).")
    elif shape == "notes":
        for entry in split_list(value):
            if entry.strip() and not re.match(r"\d{4}-\d{2}-\d{2}\b", entry.strip()):
                problems.warn(where, f"notes entry '{entry.strip()[:40]}' does not start with its date. Each entry starts YYYY-MM-DD and the role.")
                break


def validate(ws, schema, rules, tables, roles, as_of, problems):
    """Every cell, then the rules across rows and files. Adds to problems."""
    merged_status = rules["merged_status"][0]
    for name in TABLES:
        t = tables.get(name)
        if t is None or not t.header_ok:
            continue
        for i, row in enumerate(t.rows):
            where = where_of(t, i, row)
            for column in t.header:
                check_cell(schema, name, column, row[column], where, problems)
            for column in PAST_DATES:
                d = as_date(row.get(column, ""))
                if d and d > as_of:
                    problems.warn(where, f"{column} {row[column]} is after the run date {as_of}; check for a typing slip.")
    creators = tables.get("creators")
    if creators is None or not creators.header_ok:
        problems.not_checked.append("rules across files (data/creators.csv could not be read)")
        return
    by_ref, codes = {}, {}
    for i, row in enumerate(creators.rows):
        ref = row["creator_ref"]
        if ref in by_ref:
            problems.brk(where_of(creators, i, row), f"creator_ref {ref} appears twice. A ref names one creator for life; one of these rows was keyed by hand.", True)
        by_ref.setdefault(ref, row)
        if row["code"]:
            codes.setdefault(row["code"].upper(), []).append(ref)
    for code, refs in codes.items():
        if len(refs) > 1:
            problems.brk(CSV_PATH["creators"], f"code {code} belongs to {', '.join(refs)}. A code attributes sales to one creator only.")
    for name in ("pipeline", "publications"):
        t = tables.get(name)
        if t is None or not t.header_ok:
            continue
        for i, row in enumerate(t.rows):
            ref = row["creator_ref"]
            if ref and ref not in by_ref:
                problems.brk(where_of(t, i, row), f"creator_ref {ref} is not in data/creators.csv. Add the creator first, or correct the ref.")
            elif ref and merged_into(by_ref[ref], merged_status):
                problems.warn(where_of(t, i, row), f"{ref} was merged into {kept_ref(ref, by_ref, merged_status)}; this row should name the kept ref.")
    publications = tables.get("publications")
    if publications is not None and publications.header_ok:
        seen = set()
        for i, row in enumerate(publications.rows):
            if row["publication_id"] in seen:
                problems.brk(where_of(publications, i, row), f"publication_id {row['publication_id']} appears twice.", True)
            seen.add(row["publication_id"])
    # identity: possible duplicates among records not already merged
    owners = {}
    for row in creators.rows:
        if merged_into(row, merged_status):
            continue
        for key in identity_keys(row):
            owners.setdefault(key, set()).add(row["creator_ref"])
    for key, refs in owners.items():
        if len(refs) > 1:
            problems.warn(CSV_PATH["creators"], f"{' and '.join(sorted(refs))} share {describe_key(key)}. If they are one creator, merge them (merge keeps the older ref).")
    # field combinations inside a creator row
    bands = schema["tier_bands"]
    if not bands:
        problems.not_checked.append("tier against followers (schemas.md tier bands could not be read)")
    pipeline_dates, posted, post_rights = {}, {}, {}
    if tables.get("pipeline") is not None and tables["pipeline"].header_ok:
        for prow in tables["pipeline"].rows:
            for column in ("stage_date", "last_message_date"):
                d = as_date(prow[column])
                if d:
                    pipeline_dates.setdefault(prow["creator_ref"], []).append(d)
    if tables.get("publications") is not None and tables["publications"].header_ok:
        for prow in tables["publications"].rows:
            d = as_date(prow["posted_at"])
            if d:
                posted.setdefault(prow["creator_ref"], []).append(d)
            r = as_date(prow["rights_until"])
            if r:
                post_rights.setdefault(prow["creator_ref"], []).append(r)
    for i, row in enumerate(creators.rows):
        if merged_into(row, merged_status):
            continue
        where = where_of(creators, i, row)
        for column in ("status", "primary_platform", "primary_handle"):
            if not row[column]:
                problems.warn(where, f"{column} is empty, so this creator cannot be matched or counted properly.")
        if bands and PATTERN["int"].match(row["followers_primary"] or "x") and row["tier"]:
            expected = tier_for(int(row["followers_primary"]), bands)
            if expected and expected != row["tier"]:
                problems.warn(where, f"tier is {row['tier']} but {row['followers_primary']} followers is {expected} by the bands in schemas.md section 4.")
        model = row["compensation_model"]
        if model in rules["rate_models"] and not row["commission_rate_pct"]:
            problems.warn(where, f"compensation_model {model} needs commission_rate_pct.")
        if model in rules["fee_models"] and not row["flat_fee"]:
            problems.warn(where, f"compensation_model {model} needs flat_fee.")
        if model and model not in rules["rate_models"] and row["commission_rate_pct"]:
            problems.warn(where, f"commission_rate_pct is set but compensation_model is {model}.")
        if model and model not in rules["fee_models"] and row["flat_fee"]:
            problems.warn(where, f"flat_fee is set but compensation_model is {model}.")
        if row["status"] in rules["needs_agreement_date"] and not row["agreement_date"]:
            problems.warn(where, f"status is {row['status']} but agreement_date is empty. The status moves to agreed only at partnership-agreement's hand-off, together with agreement_date (terms agreed in writing have a date).")
        if row["code"] and not row["rail"]:
            problems.warn(where, "code is set but rail is empty; say where the code and payout live.")
        if row["followers_primary"] and not row["followers_as_of"]:
            problems.warn(where, "followers_primary has no followers_as_of date.")
        if row["engagement_rate_pct"] and not row["engagement_as_of"]:
            problems.warn(where, "engagement_rate_pct has no engagement_as_of date.")
        if row["agreement_file"] and not os.path.isfile(os.path.join(ws, row["agreement_file"])):
            problems.warn(where, f"agreement_file {row['agreement_file']} does not exist in the workspace.")
        # schemas.md section 4 ruling: last_activity equals the creator's latest activity, so a
        # dated note or pipeline row later than it is a warning.
        last = as_date(row["last_activity"])
        dated = note_dates(row) + pipeline_dates.get(row["creator_ref"], [])
        if last and dated and max(dated) > last:
            problems.warn(where, f"last_activity {row['last_activity']} is older than this creator's latest dated note or pipeline row ({max(dated)}); last_activity should equal the latest activity. Record it with update --note and --date {max(dated)}.")
        if RIGHTS_FROM_POSTING_LOOSE.search(row["notes"]) and not RIGHTS_FROM_POSTING.search(row["notes"]):
            problems.warn(where, "a notes entry mentions rights from posting but is not written 'rights from posting: <n> months', so other skills cannot read it.")
        months = months_from_posting(row)
        if months is not None and not row["usage_rights_until"] and posted.get(row["creator_ref"]):
            problems.warn(where, f"rights run {months} months from posting and a post was recorded on {min(posted[row['creator_ref']])}, but usage_rights_until is empty. Record the date publication-tracking computed with update.")
        latest_post_right = max(post_rights.get(row["creator_ref"], []), default=None)
        if months is not None and as_date(row["usage_rights_until"]) and latest_post_right and as_date(row["usage_rights_until"]) < latest_post_right:
            problems.warn(where, f"rights run from posting and the latest post's rights_until is {latest_post_right}, later than usage_rights_until {row['usage_rights_until']}. The roster carries the latest of them (schemas.md section 4); record it with update.")
    pipeline = tables.get("pipeline")
    if pipeline is not None and pipeline.header_ok:
        if roles is None:
            problems.not_checked.append(f"owner_role against the roles ({PROGRAM_FILE} not found)")
        open_rows = {}
        for i, row in enumerate(pipeline.rows):
            if roles is not None and row["owner_role"] and row["owner_role"].strip().lower() not in roles:
                problems.warn(where_of(pipeline, i, row), f"owner_role '{row['owner_role']}' is not a role in {PROGRAM_FILE} section {ROLES_SECTION} ({', '.join(roles)}).")
            if row["stage"] not in rules["pipeline_done_stages"]:
                open_rows.setdefault((row["campaign_slug"], row["creator_ref"]), []).append(i)
                if row["creator_ref"] in by_ref and no_contact(by_ref[row["creator_ref"]]):
                    problems.warn(where_of(pipeline, i, row), f"{row['creator_ref']} carries 'do not contact' in notes but this row is open at stage {row['stage']}. Close it ({rules['pipeline_done_stages'][0]}) with a note; no outreach is drafted for them.")
        for (slug, ref), idx in open_rows.items():
            if len(idx) > 1:
                problems.warn(CSV_PATH["pipeline"], f"{ref} has {len(idx)} open rows in {slug}. Keep one; move the other's stage to {rules['pipeline_done_stages'][0]} with a note.")


def latest_activity(tables):
    """creator_ref -> the latest dated note, pipeline or publication date recorded for them."""
    latest = {}
    creators = tables.get("creators")
    if creators is not None and creators.header_ok:
        for row in creators.rows:
            dates = note_dates(row)
            if dates:
                latest[row["creator_ref"]] = max(dates)
    for name, columns in (("pipeline", ("stage_date", "last_message_date")), ("publications", ("posted_at",))):
        t = tables.get(name)
        if t is None or not t.header_ok:
            continue
        for row in t.rows:
            for column in columns:
                d = as_date(row.get(column, ""))
                if d and (row["creator_ref"] not in latest or d > latest[row["creator_ref"]]):
                    latest[row["creator_ref"]] = d
    return latest


def all_refs(tables):
    refs = set()
    for t in tables.values():
        for row in t.rows:
            for value in row.values():
                refs.update(ANY_REF.findall(value))
    return refs


def new_ref(taken, rng):
    while True:
        ref = "c-" + "".join(rng.choice(REF_ALPHABET) for _ in range(6))
        if ref not in taken:
            taken.add(ref)
            return ref


def coverage(tables, roles, extra_not_checked, not_judged):
    read = ", ".join(f"{CSV_PATH[n]} ({plural(tables[n].read_count, 'row')})" for n in TABLES if n in tables)
    missing = [CSV_PATH[n] for n in TABLES if n not in tables]
    used = read + (f", {PROGRAM_FILE} section {ROLES_SECTION} ({len(roles)} roles)" if roles is not None else "")
    lines = [f"COVERAGE. Inputs used: {used}, references/schemas.md, references/roster-rules.md."]
    lines.append("Inputs missing: " + (", ".join(missing + ([PROGRAM_FILE] if roles is None else [])) or "none") + ".")
    lines.append("Not checked: " + ("; ".join(extra_not_checked) + "; " if extra_not_checked else "") + not_judged + ".")
    return lines


NOT_JUDGED = ("whether a handle or URL belongs to the creator, whether a contact email is public or was given by the creator, "
              "whether agreement dates and terms match what was signed, and the files under codes/, payouts/ and campaigns/")


def load_all(args):
    ws = workspace_of(args)
    schema = read_schema()
    rules = read_rules(schema)
    return ws, schema, rules


# ---------------------------------------------------------------- commands: schema, check

def cmd_schema(args):
    ws, schema, rules = load_all(args)
    out = []
    for name in TABLES:
        out.append(f"{name} ({CSV_PATH[name]}, schemas.md section {SCHEMA_SECTION[name]}): {len(schema['header'][name])} columns")
        for column in schema["header"][name]:
            spec = schema["cols"][name][column]
            text = f"  {column}"
            if spec["enum"]:
                text += (": list of " if spec["multi"] else ": one of ") + ", ".join(spec["enum"])
            elif SHAPE.get(column) in SHAPE_WORDS:
                text += ": " + SHAPE_WORDS[SHAPE[column]]
            if spec["range"]:
                text += f", {spec['range'][0]} to {spec['range'][1]}"
            if column == "tier" and schema["tier_bands"]:
                text += " (bands: " + "; ".join((f"{n} {lo} and up" if hi is None else f"{n} {lo} to under {hi}") for n, lo, hi in schema["tier_bands"]) + ")"
            out.append(text)
    out.append(f"shortlist verdicts (schemas.md section {SHORTLIST_SECTION}): {', '.join(schema['verdicts'])}")
    out.append(f"shortlist verdicts that may carry an empty total (schemas.md section {SHORTLIST_SECTION}): " + (", ".join(schema["total_optional_verdicts"]) or "none"))
    out.append(f"followers_source labels (schemas.md section {LONGLIST_SECTION}): " + (", ".join(f"{k} {v}" for k, v in schema["followers_labels"].items()) or "none found"))
    return OK, "the schema as this script reads it from references/schemas.md.", out


def cmd_check(args):
    ws, schema, rules = load_all(args)
    as_of = parse_date_arg(args.as_of, "--as-of")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    roles = read_roles(ws)
    validate(ws, schema, rules, tables, roles, as_of, problems)
    workbook_state(ws, schema, tables, problems)
    nb, nw = len(problems.breaks), len(problems.warnings)
    tally = f"{plural(nb, 'break')}, {plural(nw, 'warning')}"
    out = [f"Checked as of {as_of}: {tally}."] + problems.lines()
    if problems.not_checked:
        out.append("Could not check: " + "; ".join(problems.not_checked) + ".")
    out += coverage(tables, roles, problems.not_checked, NOT_JUDGED)
    if nb:
        return BAD, f"breaks. {tally}. Fix the breaks before any skill writes to these files.", out
    if nw or problems.not_checked:
        label = "partial" if problems.not_checked else "warnings"
        return PARTIAL, f"{label}. {tally}" + (", and some rules could not be checked." if problems.not_checked else "."), out
    return OK, f"clean. {tally}.", out


def workbook_state(ws, schema, tables, problems):
    path = os.path.join(ws, WORKBOOK_DEFAULT)
    if not os.path.isfile(path) or any(not tables.get(n) or not tables[n].header_ok for n in TABLES):
        return
    try:
        wb = read_workbook(path, schema)
    except Stop as exc:
        problems.warn(WORKBOOK_DEFAULT, f"the workbook could not be read ({exc}).")
        return
    wb_fp, csv_fp = fingerprint_wb(wb), fingerprint_tables(tables)
    if wb_fp == csv_fp:
        return
    if wb["stamp"] and wb_fp == wb["stamp"]:
        problems.warn(WORKBOOK_DEFAULT, "the workbook is older than the CSVs. Run export-xlsx before anyone edits it.")
    else:
        problems.warn(WORKBOOK_DEFAULT, "the workbook has edits that are not in the CSVs. Run import-xlsx before any other skill writes.")


# ---------------------------------------------------------------- command: add

def read_plain_csv(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = [(reader.line_num, dict(r)) for r in reader]
            return reader.fieldnames or [], rows
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise Stop(f"could not read {path} as UTF-8 CSV ({exc}).")


def cmd_add(args):
    ws, schema, rules = load_all(args)
    role = require_role(ws, args.role)
    date = parse_date_arg(args.date, "--date")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    roles = read_roles(ws)
    validate(ws, schema, rules, tables, roles, date, problems)
    if problems.breaks:
        first = problems.breaks[0]
        raise Stop(f"the roster has {len(problems.breaks)} breaks; adding on top of a broken file spreads the break. Run check and fix them first. First break: {first[1]}: {first[2]}")
    path = resolve_in(ws, args.from_shortlist)
    header, rows = read_plain_csv(path)
    missing = [c for c in ("platform", "handle", "verdict") if c not in header]
    if missing:
        raise Stop(f"{os.path.basename(path)} has no column {', '.join(missing)}. A shortlist from creator-vetting carries them (schemas.md section {SHORTLIST_SECTION}).")
    selected = [v.strip() for v in (args.verdicts.split(",") if args.verdicts else rules["default_add_verdicts"]) if v.strip()]
    bad = [v for v in selected if v not in schema["verdicts"]]
    if bad:
        raise Stop(f"--verdicts names {', '.join(bad)}; verdicts are {', '.join(schema['verdicts'])}.")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    file_date = m.group(1) if m and as_date(m.group(1)) else ""
    merged_status = rules["merged_status"][0]
    labels = schema["followers_labels"]
    skip_may_lack_total = schema["total_optional_verdicts"]
    read_cols = ("display_name", "profile_url", "followers", "followers_source", "niche_tags", "contact_path",
                 "total", "confidence", "scored_as_of", "creator_ref", "tier", "engagement_rate_pct", "brand_safety_flag")
    absent = [c for c in read_cols if c not in header]
    creators = tables["creators"].copy()
    by_ref = {r["creator_ref"]: r for r in creators.rows}
    ident = Identity(creators.rows, merged_status)
    taken = all_refs(tables)
    rng = make_rng(args.seed)
    added, present, skipped, not_selected, added_refs = [], [], [], {}, set()
    platforms = schema["platforms"]
    for line, r in rows:
        verdict = (r.get("verdict") or "").strip().lower()
        if verdict not in selected:
            not_selected[verdict or "(empty)"] = not_selected.get(verdict or "(empty)", 0) + 1
            continue
        platform = (r.get("platform") or "").strip().lower()
        handle = (r.get("handle") or "").strip()
        if not norm_handle(handle):
            skipped.append(f"line {line}: no handle.")
            continue
        if platform not in platforms:
            skipped.append(f"line {line}: platform '{r.get('platform')}' is not one of {', '.join(platforms)}.")
            continue
        url = re.sub(r"^(?i:https?)://", lambda m: m.group(0).lower(), (r.get("profile_url") or "").strip())
        url = url if PATTERN["url"].match(url) else ""
        named = (r.get("creator_ref") or "").strip()
        label = f"{platform} @{norm_handle(handle)}"
        if named:
            if named in by_ref:
                present.append(f"{label}: already {kept_ref(named, by_ref, merged_status)} (the shortlist names it).")
            else:
                skipped.append(f"line {line}: {label} names creator_ref {named}, which is not in the roster. Check the ref with the person who ran vetting.")
            continue
        probe = {"primary_platform": platform, "primary_handle": handle, "profile_url": url, "other_platforms": ""}
        found = ident.match(probe)
        if len(found) > 1:
            detail = "; ".join(f"{ref} by {', '.join(why)}" for ref, why in sorted(found.items()))
            skipped.append(f"line {line}: {label} matches more than one record ({detail}). Decide whether those records are one creator (merge) before adding.")
            continue
        if found:
            ref, why = next(iter(found.items()))
            extra = ""
            row_now = by_ref.get(ref, {})
            if url and norm_handle(row_now.get("primary_handle", "")) != norm_handle(handle) and "profile URL" in " ".join(why):
                extra = f" The roster's handle is {row_now.get('primary_handle')}; if the handle changed, record it with update."
            earlier = " It was added earlier in this run." if ref in added_refs else ""
            if no_contact(by_ref.get(ref, {})):
                earlier += " Its notes say do not contact."
            shown_ref = "(ref on write)" if args.dry_run and ref in added_refs else ref
            present.append(f"{label}: already {shown_ref} (same {', '.join(why)}). Not added; nothing changed.{earlier}{extra}")
            continue
        row = {c: "" for c in creators.header}
        ref = new_ref(taken, rng)
        scored = (r.get("scored_as_of") or "").strip()
        scored = scored if as_date(scored) and PATTERN["date"].match(scored) else ""
        obs = scored or file_date
        unrecorded, sourced = [], []
        row.update(creator_ref=ref, display_name=(r.get("display_name") or "").strip(), primary_platform=platform,
                   primary_handle="@" + handle.lstrip("@"), profile_url=url, last_activity=date.isoformat())
        if (r.get("profile_url") or "").strip() and not url:
            unrecorded.append("profile_url (not a URL)")
        tags = [t.strip().lower() for t in (r.get("niche_tags") or "").split(";") if t.strip()]
        row["niche_tags"] = ";".join(tags)
        followers = (r.get("followers") or "").replace(",", "").strip()
        source = (r.get("followers_source") or "").strip().lower()
        flabel = labels.get(source)
        if followers:
            # followers_primary is a count "as last observed" (schemas.md section 4), so an
            # Estimated figure (section 7 labels) is noted, never recorded as an observation.
            if not PATTERN["int"].match(followers):
                unrecorded.append("followers (not a whole number)")
            elif not flabel:
                unrecorded.append(f"followers {followers} (followers_source '{source}' has no label in schemas.md section {LONGLIST_SECTION})")
            elif flabel == "Estimated":
                unrecorded.append(f"followers {followers} (Estimated, {source})")
            elif not obs:
                unrecorded.append("followers (no date to record them against)")
            else:
                row["followers_primary"], row["followers_as_of"] = followers, obs
                sourced.append(f"followers {flabel} ({source})")
        tier = (r.get("tier") or "").strip().lower()
        if tier in enum_of(schema, "creators", "tier"):
            row["tier"] = tier
        else:
            if tier:
                unrecorded.append(f"tier '{tier}' (not a tier in schemas.md section 4)")
            if row["followers_primary"]:
                row["tier"] = tier_for(int(row["followers_primary"]), schema["tier_bands"]) or ""
        rate = (r.get("engagement_rate_pct") or "").strip()
        if rate:
            if not PATTERN["decimal"].match(rate):
                unrecorded.append(f"engagement_rate_pct '{rate}' (not a plain decimal)")
            elif not scored:
                unrecorded.append("engagement_rate_pct (no scored_as_of date to record it against)")
            else:
                row["engagement_rate_pct"], row["engagement_as_of"] = rate, scored
        total = (r.get("total") or "").strip()
        low, high = schema["cols"]["creators"]["audience_fit_score"]["range"] or (0, 10 ** 9)
        if PATTERN["int"].match(total or "x") and low <= int(total) <= high:
            row["audience_fit_score"] = total
        elif total:
            unrecorded.append(f"total '{total}' (not a whole number {low} to {high})")
        elif verdict not in skip_may_lack_total:
            unrecorded.append("audience_fit_score (the shortlist total is empty)")
        contact = (r.get("contact_path") or "").strip().lower()
        if contact in enum_of(schema, "creators", "contact_path"):
            row["contact_path"] = contact
        flag = (r.get("brand_safety_flag") or "").strip().lower()
        if flag in enum_of(schema, "creators", "brand_safety_flag"):
            row["brand_safety_flag"] = flag
        elif flag:
            unrecorded.append(f"brand_safety_flag '{flag}' (not one of {', '.join(enum_of(schema, 'creators', 'brand_safety_flag'))})")
        if verdict in rules["excluded_verdict"]:
            row["status"], row["brand_safety_flag"] = rules["excluded_status"][0], rules["excluded_flag"][0]
        else:
            row["status"] = rules["new_creator_status"][0]
        bits = [f"verdict {verdict}"] + ([f"total {total}"] if total else []) + \
               ([f"confidence {r.get('confidence').strip()}"] if (r.get("confidence") or "").strip() else []) + sourced
        note = f"{date} {role}: added from {os.path.basename(path)} ({', '.join(bits)})"
        if unrecorded:
            note += ", not recorded: " + ", ".join(unrecorded)
        row["notes"] = note_safe(note)
        creators.rows.append(row)
        creators.lines.append("new")
        by_ref[ref] = row
        ident.add(row, ref)
        added_refs.add(ref)
        shown = "(ref on write)" if args.dry_run else ref
        added.append(f"{shown}  {label}  {row['display_name'] or '(no display name)'}  (verdict {verdict}, status {row['status']}"
                     + (f", brand_safety_flag {row['brand_safety_flag']}" if row["brand_safety_flag"] else "") + ")"
                     + (f"; not recorded: {', '.join(unrecorded)}" if unrecorded else ""))
    after = dict(tables, creators=creators)
    check_after = Problems()
    validate(ws, schema, rules, after, roles, date, check_after)
    if check_after.breaks:
        first = check_after.breaks[0]
        raise Stop(f"the new rows would break the schema ({first[1]}: {first[2]}). Correct the shortlist and run again.")
    out = [f"{'To add' if args.dry_run else 'Added'} ({len(added)}):"] + [f"  {a}" for a in added]
    out += [f"Already in the roster ({len(present)}):"] + [f"  {p}" for p in present]
    out += [f"Skipped, needs a person ({len(skipped)}):"] + [f"  {s}" for s in skipped]
    if not_selected:
        out.append("Not selected by verdict: " + ", ".join(f"{k} {v}" for k, v in sorted(not_selected.items()))
                   + f" (selected: {', '.join(selected)}; use --verdicts to change).")
    if args.dry_run:
        out.append("Dry run: nothing written. Each creator_ref is drawn when the rows are written, so the real run prints the refs it assigns.")
    elif added:
        commit([creators])
    out.append(counts_line(creators, 0 if args.dry_run else len(added), 0))
    cov = coverage(tables, roles, [], "whether each new creator is who the shortlist says, and anything vetting did not record")
    if absent:
        gap = f"shortlist columns absent ({', '.join(absent)}), so those fields were not recorded."
        cov[1] = "Inputs missing: " + gap if cov[1] == "Inputs missing: none." else cov[1].rstrip(".") + "; " + gap
    out += cov
    code = PARTIAL if skipped else OK
    head = f"{'dry run, ' + str(len(added)) + ' to add' if args.dry_run else str(len(added)) + ' added'}, {len(present)} already present, {len(skipped)} skipped."
    return code, ("partial. " if skipped else "done. ") + head, out


# ---------------------------------------------------------------- command: find

def cmd_find(args):
    ws, schema, rules = load_all(args)
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    structural_or_stop(problems, "search the roster")
    platform = (args.platform or "").strip().lower()
    if platform and platform not in schema["platforms"]:
        raise Stop(f"--platform '{args.platform}' is not one of {', '.join(schema['platforms'])}.")
    url = re.sub(r"^(?i:https?)://", lambda m: m.group(0).lower(), (args.url or "").strip())
    if args.url and not PATTERN["url"].match(url):
        raise Stop(f"--url '{args.url}' is not a URL starting http:// or https://.")
    if not norm_handle(args.handle or "") and not url:
        raise Stop("give --handle (with --platform if you know it), or --url, or both.")
    merged_status = rules["merged_status"][0]
    rows = tables["creators"].rows
    by_ref = {r["creator_ref"]: r for r in rows}
    ident = Identity(rows, merged_status)
    found = {}
    for p in ([platform] if platform else schema["platforms"]):
        probe = {"primary_platform": p if norm_handle(args.handle or "") else "", "primary_handle": args.handle or "",
                 "profile_url": url, "other_platforms": ""}
        for ref, why in ident.match(probe).items():
            found.setdefault(ref, set()).update(why)
    asked = " and ".join(([f"{platform or 'any platform'} @{norm_handle(args.handle)}"] if norm_handle(args.handle or "") else []) + ([f"profile URL {norm_url(url)}"] if url else []))
    out = [f"  {ref}  {by_ref[ref]['display_name'] or '(no display name)'}  status {by_ref[ref]['status'] or '(unknown)'}  (same {', '.join(sorted(why))})"
           + ("  DO NOT CONTACT (see notes)" if no_contact(by_ref[ref]) else "")
           for ref, why in sorted(found.items())]
    out += coverage(tables, read_roles(ws), [], "creators the roster lists under another handle or URL; matching is exact after normalising case, @, www and trailing slashes")
    if not found:
        return OK, f"not in the roster: no record has {asked}.", out
    if len(found) > 1:
        return OK, f"found {len(found)} records for {asked}; they may be one creator (see merge).", out
    return OK, f"found 1 record for {asked}.", out


# ---------------------------------------------------------------- command: update

def structural_or_stop(problems, action):
    if problems.structural:
        first = problems.structural[0]
        raise Stop(f"{first[1]}: {first[2]} Fix this before you {action}.")


def check_note(note):
    if not note or not note.strip():
        raise Stop("give the reason with --note. The note explains the change, with the date and the role.")
    if ";" in note or "\n" in note:
        raise Stop("a note may not contain ';' or a line break, because ';' separates dated entries. Use a comma.")
    return note.strip()


def show(value, column=""):
    """A value as a note shows it. Contact details are never copied into notes."""
    if not value:
        return "(empty)"
    return "(set)" if column == "contact_email" else note_safe(value)


def cmd_update(args):
    ws, schema, rules = load_all(args)
    role = require_role(ws, args.role)
    note = check_note(args.note)
    date = parse_date_arg(args.date, "--date")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    structural_or_stop(problems, "update a record")
    merged_status = rules["merged_status"][0]
    creators = tables["creators"].copy()
    index = next((i for i, r in enumerate(creators.rows) if r["creator_ref"] == args.creator_ref), None)
    if index is None:
        raise Stop(f"{args.creator_ref} is not in data/creators.csv. Refs are assigned by add; check the ref.")
    row = creators.rows[index]
    target = merged_into(row, merged_status)
    if target:
        raise Stop(f"{args.creator_ref} was merged into {target}. Update {target} instead.")
    header = creators.header
    changes, adjusted = [], []
    for item in args.assignments:
        if "=" not in item:
            raise Stop(f"'{item}' is not field=value.")
        field, value = item.split("=", 1)
        field = field.strip()
        if field not in header:
            raise Stop(f"'{field}' is not a column of data/creators.csv. Columns: {', '.join(header)}.")
        if field == "creator_ref":
            raise Stop("creator_ref is stable for life and never changes. If two refs are one creator, use merge.")
        if field == "notes":
            raise Stop("notes are appended with --note, never overwritten.")
        if field == "last_activity":
            raise Stop(f"last_activity is set from --date on every update. To record activity with no other change, run: update {args.creator_ref} --note \"<what happened>\" --date YYYY-MM-DD")
        if field == "primary_handle" and value and not value.startswith("@"):
            value = "@" + value
            adjusted.append(f"primary_handle stored as {value}")
        cell = Problems()
        check_cell(schema, "creators", field, value, f"{args.creator_ref} {field}", cell)
        if cell.breaks:
            raise Stop(cell.breaks[0][2])
        if row[field] != value:
            changes.append((field, row[field], value))
    if not changes and args.assignments:
        return OK, "done. Nothing to change: every value is already as given.", []
    new = dict(row)
    for field, _, value in changes:
        new[field] = value
    fields = {f for f, _, _ in changes}
    if fields & {"primary_platform", "primary_handle", "profile_url", "other_platforms"}:
        others = Identity(creators.rows, merged_status, skip_ref=args.creator_ref)
        clash = others.match(new)
        if clash:
            ref, why = next(iter(clash.items()))
            raise Stop(f"{', '.join(why)} already belongs to {ref}. If they are the same creator, merge them; otherwise check the value.")
    if "code" in fields and new["code"]:
        owner = next((r["creator_ref"] for r in creators.rows if r["code"].upper() == new["code"].upper() and r["creator_ref"] != args.creator_ref), None)
        if owner:
            raise Stop(f"code {new['code']} already belongs to {owner}. A code attributes sales to one creator only.")
    summary = ", ".join(f"{f} {show(o, f)} -> {show(n, f)}" for f, o, n in changes)
    entry = note_safe(f"{date} {role}: {summary} (reason: {note})" if changes else f"{date} {role}: {note}")
    new["notes"] = ";".join([e for e in split_list(row["notes"]) if e] + [entry])
    old_last = as_date(row["last_activity"])
    new["last_activity"] = max(date, old_last).isoformat() if old_last else date.isoformat()
    creators.rows[index] = new
    after = dict(tables, creators=creators)
    remaining = Problems()
    validate(ws, schema, rules, after, read_roles(ws), date, remaining)
    out = [f"{args.creator_ref}: {summary or 'note only'}."] + [f"  ({a})" for a in adjusted] + [f"Note {'to add' if args.dry_run else 'added'}: {entry}"]
    if args.dry_run:
        out.append("Dry run: nothing written.")
    else:
        commit([creators])
    out.append(counts_line(creators, 0, 0 if args.dry_run else 1))
    if remaining.breaks or remaining.warnings:
        out.append(f"The files still have {plural(len(remaining.breaks), 'break')} and {plural(len(remaining.warnings), 'warning')} elsewhere; run check for the list.")
    out += coverage(tables, read_roles(ws), [], "whether the new value is true; the note records who said so")
    what = f"{plural(len(changes), 'field')} {'would change' if args.dry_run else 'changed'}" if changes else ("note would be added" if args.dry_run else "note added")
    return OK, ("dry run. " if args.dry_run else "done. ") + f"{what} on {args.creator_ref}.", out


# ---------------------------------------------------------------- command: merge

def cmd_merge(args):
    ws, schema, rules = load_all(args)
    role = require_role(ws, args.role)
    note = check_note(args.note)
    date = parse_date_arg(args.date, "--date")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    structural_or_stop(problems, "merge records")
    merged_status = rules["merged_status"][0]
    keep_ref, drop_ref = args.keep_ref, args.drop_ref
    if keep_ref == drop_ref:
        raise Stop("the two refs are the same.")
    creators = tables["creators"].copy()
    pos = {r["creator_ref"]: i for i, r in enumerate(creators.rows)}
    for ref in (keep_ref, drop_ref):
        if ref not in pos:
            raise Stop(f"{ref} is not in data/creators.csv.")
        target = merged_into(creators.rows[pos[ref]], merged_status)
        if target:
            raise Stop(f"{ref} was already merged into {target}.")
    if pos[keep_ref] > pos[drop_ref]:
        raise Stop(f"{drop_ref} is the older record (it was added first, line {creators.lines[pos[drop_ref]]}). A merge keeps the older ref. Run: merge {drop_ref} {keep_ref}")
    keep, drop = dict(creators.rows[pos[keep_ref]]), dict(creators.rows[pos[drop_ref]])
    filled, kept, attention, moved = [], [], [], []
    for column in creators.header:
        if column in ("creator_ref", "status", "notes", "last_activity"):
            continue
        a, b = keep[column], drop[column]
        if column in ("other_platforms", "niche_tags"):
            union = [x for x in split_list(a)] + [x for x in split_list(b) if x not in split_list(a)]
            if union != split_list(a):
                keep[column] = ";".join(union)
                filled.append(column)
        elif not a and b:
            keep[column] = b
            filled.append(column)
            if column == "code":
                drop[column] = ""   # a code attributes sales to one record, so it moves rather than copies
                moved.append(f"code {b} moved to {keep_ref}")
        elif a and b and a != b:
            kept.append(f"{column} (kept {note_safe(a)}, the newer record had {note_safe(b)})")
            if column == "code":
                attention.append(f"two codes: {a} stays on {keep_ref}; {b} stays on the merged record {drop_ref}. One active code per creator: decide with affiliate-onboarding which code stays live. Orders on {b} will show as unattributed codes until then.")
    alias = f"{drop['primary_platform']}:@{norm_handle(drop['primary_handle'])}" if drop["primary_platform"] and norm_handle(drop["primary_handle"]) else ""
    if alias and alias not in split_list(keep["other_platforms"]) and \
            (drop["primary_platform"], norm_handle(drop["primary_handle"])) != (keep["primary_platform"], norm_handle(keep["primary_handle"])):
        keep["other_platforms"] = ";".join(split_list(keep["other_platforms"]) + [alias])
        if "other_platforms" not in filled:
            filled.append("other_platforms")
    if not keep["status"] and drop["status"]:
        keep["status"] = drop["status"]
        filled.append("status")
    elif drop["status"] and drop["status"] != keep["status"]:
        attention.append(f"status: {keep_ref} is {keep['status']}, the newer record was {drop['status']}. If {drop['status']} is right, run update {keep_ref} status={drop['status']}.")
    if no_contact(drop) and not no_contact(keep):
        moved.append(f"do not contact carried from {drop_ref}'s notes")
    carried = " (do not contact, carried from the newer record)" if no_contact(drop) and not no_contact(keep) else ""
    keep_note = f"{date} {role}: merged {drop_ref} into this record{carried}" + (f" (filled {', '.join(filled)})" if filled else "") + \
        (f" (kept this record's {', '.join(k.split(' ')[0] for k in kept)})" if kept else "") + f" reason: {note}"
    keep["notes"] = ";".join([e for e in split_list(keep["notes"]) if e] + [note_safe(keep_note)])
    keep["last_activity"] = date.isoformat()
    drop["status"] = merged_status
    drop["notes"] = ";".join([e for e in split_list(drop["notes"]) if e] + [note_safe(f"{date} {role}: merged into {keep_ref} (duplicate record" + (f", {', '.join(moved)}" if moved else "") + f") reason: {note}")])
    drop["last_activity"] = date.isoformat()
    creators.rows[pos[keep_ref]], creators.rows[pos[drop_ref]] = keep, drop
    changed = {"creators": 2}
    out_tables = {"creators": creators}
    for name in ("pipeline", "publications"):
        t = tables[name].copy()
        n = 0
        for row in t.rows:
            if row["creator_ref"] == drop_ref:
                row["creator_ref"] = keep_ref
                row["notes"] = ";".join([e for e in split_list(row["notes"]) if e] + [note_safe(f"{date} {role}: creator_ref {drop_ref} -> {keep_ref} (records merged)")])
                n += 1
        out_tables[name], changed[name] = t, n
    after = dict(tables, **out_tables)
    post = Problems()
    validate(ws, schema, rules, after, read_roles(ws), date, post)
    if post.breaks:
        first = post.breaks[0]
        raise Stop(f"the merge would leave a break ({first[1]}: {first[2]}).")
    for _, where, msg, _ in post.warnings:
        if "open rows" in msg:
            attention.append(f"{where}: {msg}")
    others = []
    skip = {os.path.join(ws, p) for p in CSV_PATH.values()}
    for base, dirs, files in os.walk(ws):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            path = os.path.join(base, f)
            if path in skip or not f.endswith((".md", ".csv", ".txt", ".json")):
                continue
            hit = drop_ref in f
            if not hit:
                try:
                    with open(path, encoding="utf-8", errors="ignore") as fh:
                        hit = drop_ref in fh.read()
                except OSError:
                    continue
            if hit:
                others.append(os.path.relpath(path, ws))
    out = [f"Kept {keep_ref} (the older record); {drop_ref} is now status {merged_status} with a note saying it was merged."]
    out.append("Filled on the kept record from the newer one: " + (", ".join(filled) if filled else "nothing") + ".")
    if moved:
        out.append("Moved, not copied: " + "; ".join(moved) + ".")
    if kept:
        out.append("Kept the older record's value for: " + "; ".join(kept) + ".")
    if attention:
        out.append("Needs a person:")
        out += [f"  {a}" for a in attention]
    if others:
        out.append(f"Files that name {drop_ref} are left as they are, as history (" + ", ".join(sorted(others)[:20]) + (", ..." if len(others) > 20 else "") + ").")
    if args.dry_run:
        out.append("Dry run: nothing written.")
    else:
        commit([out_tables["creators"]] + [out_tables[n] for n in ("pipeline", "publications") if changed[n]])
    for name in TABLES:
        out.append(counts_line(out_tables[name], 0, 0 if args.dry_run else changed[name]))
    out += coverage(tables, read_roles(ws), [], "whether the two records really are one creator; that is the person's evidence")
    code = PARTIAL if attention else OK
    return code, ("partial. " if attention else "done. ") + f"{'would merge' if args.dry_run else 'merged'} {drop_ref} into {keep_ref}" + (f"; {plural(len(attention), 'thing')} need{'s' if len(attention) == 1 else ''} a person." if attention else "."), out


# ---------------------------------------------------------------- command: report

def md_table(header, rows):
    if not rows:
        return []
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return lines


def cmd_report(args):
    ws, schema, rules = load_all(args)
    as_of = parse_date_arg(args.as_of, "--as-of")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    roles = read_roles(ws)
    validate(ws, schema, rules, tables, roles, as_of, problems)
    if problems.breaks:
        raise Stop(f"the files have {len(problems.breaks)} breaks; a report on them could mislead. Run check and fix them first.")
    merged_status = rules["merged_status"][0]
    creators = [r for r in tables["creators"].rows if not merged_into(r, merged_status)]
    merged_count = len(tables["creators"].rows) - len(creators)
    md = [f"# Roster report, as of {as_of}", "",
          "Label: every count is computed by roster.py from rows in the workspace files, which are User-provided records. "
          "Follower figures are as last observed on the dates in the roster.", ""]

    def counts(column, title, order):
        tally = {}
        for r in creators:
            tally[r[column] or "(unknown)"] = tally.get(r[column] or "(unknown)", 0) + 1
        keys = [k for k in order if k in tally] + sorted(k for k in tally if k not in order)
        md.extend([f"## Creators by {title}", ""] + (md_table([title, "creators"], [(k, tally[k]) for k in keys]) or ["No creators in the roster."]) + [""])

    counts("status", "status", enum_of(schema, "creators", "status"))
    counts("tier", "tier", enum_of(schema, "creators", "tier"))
    counts("primary_platform", "platform", schema["platforms"])

    def windows(column, title, days):
        dated = [r for r in creators if as_date(r[column])]
        inner, outer = days[0], days[-1]
        first, second = [], []
        for r in dated:
            left = (as_date(r[column]) - as_of).days
            item = (r["creator_ref"], r["display_name"], r["status"], r[column], left)
            if 0 <= left <= inner:
                first.append(item)
            elif inner < left <= outer:
                second.append(item)
        head = ["creator_ref", "display_name", "status", column, "days left"]
        md.extend([f"## {title} ending within {inner} days", ""] + (md_table(head, sorted(first, key=lambda x: x[4])) or [f"None found among the {plural(len(dated), 'creator')} with {column} set."]) + [""])
        md.extend([f"## {title} ending in {inner + 1} to {outer} days", ""] + (md_table(head, sorted(second, key=lambda x: x[4])) or [f"None found among the {plural(len(dated), 'creator')} with {column} set."]) + [""])
        # schemas.md section 4: an empty date with an agreement file means none was granted;
        # with no agreement file it is unknown.
        bare = [r for r in creators if not r[column] and r["status"] in rules["needs_agreement_date"]]
        from_posting = []
        if column == "usage_rights_until":
            # schemas.md section 4: "rights from posting: <n> months" means the window runs from the post
            from_posting = [f"{r['creator_ref']} ({months_from_posting(r)} months)" for r in bare if months_from_posting(r) is not None]
            bare = [r for r in bare if months_from_posting(r) is None]
        none_granted = [r["creator_ref"] for r in bare if r["agreement_file"]]
        undated = [r["creator_ref"] for r in bare if not r["agreement_file"]]
        statuses = " or ".join(rules["needs_agreement_date"])
        if from_posting:
            md.extend([f"Window from posting, not yet live: {plural(len(from_posting), 'creator')} ({', '.join(from_posting)}); the date is set when the post is recorded.", ""])
        if none_granted:
            md.extend([f"None granted: {plural(len(none_granted), 'creator')} with status {statuses} {'has' if len(none_granted) == 1 else 'have'} an agreement on file and no {column} ({', '.join(none_granted)}).", ""])
        if undated:
            md.extend([f"Unknown, not absent: {plural(len(undated), 'creator')} with status {statuses} {'has' if len(undated) == 1 else 'have'} no {column} and no agreement on file ({', '.join(undated)}).", ""])

    windows("usage_rights_until", "Usage rights", rules["rights_ending_within_days"])
    windows("exclusivity_until", "Exclusivity", rules["exclusivity_ending_within_days"])

    latest = latest_activity(tables)
    stale_days = rules["stale_after_days"][0]
    stale, undated = [], []
    for r in creators:
        if r["status"] in rules["stale_skips_statuses"]:
            continue
        dates = [d for d in (as_date(r["last_activity"]), latest.get(r["creator_ref"])) if d]
        if not dates:
            undated.append(r["creator_ref"])
            continue
        age = (as_of - max(dates)).days
        if age >= stale_days:
            stale.append((r["creator_ref"], r["display_name"], r["status"], max(dates).isoformat(), age))
    md.extend([f"## No activity for {stale_days} days or more", ""] +
              (md_table(["creator_ref", "display_name", "status", "latest activity", "days since"], sorted(stale, key=lambda x: -x[4]))
               or ["None found."]) + [""])
    if undated:
        md.extend([f"No activity date recorded at all: {', '.join(undated)}.", ""])

    dnc = [r["creator_ref"] for r in creators if no_contact(r)]
    md.extend(["## Do not contact", "", (f"{plural(len(dnc), 'creator')} asked not to be approached again: {', '.join(dnc)}. No outreach is drafted for them." if dnc else "None recorded (no notes say do not contact)."), ""])

    status = rules["code_expected_status"][0]
    nocode = [(r["creator_ref"], r["display_name"], r["compensation_model"] or "(unknown)", r["rail"] or "(unknown)")
              for r in creators if r["status"] == status and not r["code"]]
    md.extend([f"## Status {status} with no code", ""] +
              (md_table(["creator_ref", "display_name", "compensation_model", "rail"], nocode) or [f"None found among {plural(sum(1 for r in creators if r['status'] == status), status + ' creator')}."]) + [""])

    overdue, due_elsewhere = [], []
    for r in tables["pipeline"].rows:
        d = as_date(r["next_action_date"])
        if not d or r["stage"] in rules["pipeline_done_stages"]:
            continue
        if r["stage"] in rules["stages_graded_elsewhere"]:
            if d <= as_of:
                due_elsewhere.append((r["campaign_slug"], r["creator_ref"], r["stage"], r["next_action"], r["next_action_date"], r["owner_role"]))
        elif d < as_of:
            overdue.append((r["campaign_slug"], r["creator_ref"], r["stage"], r["next_action"], r["next_action_date"], r["owner_role"], (as_of - d).days))
    md.extend(["## Pipeline actions past their date", ""] +
              (md_table(["campaign_slug", "creator_ref", "stage", "next_action", "next_action_date", "owner_role", "days overdue"], sorted(overdue, key=lambda x: -x[6]))
               or ["None found."]) + [""])
    stages = ", ".join(rules["stages_graded_elsewhere"])
    md.extend([f"## Post checks due (stage {stages})", "",
               f"Listed as due on their date, not graded here: publication-tracking's due list says which to act on now and when one is overdue, after its grace days.", ""] +
              (md_table(["campaign_slug", "creator_ref", "stage", "next_action", "due on", "owner_role"], sorted(due_elsewhere, key=lambda x: x[4]))
               or ["None due."]) + [""])
    no_date = sum(1 for r in tables["pipeline"].rows if not r["next_action_date"] and r["stage"] not in rules["pipeline_done_stages"])
    if no_date:
        md.extend([f"Open pipeline rows with no next_action_date: {no_date} (they cannot be overdue, and nothing reminds anyone).", ""])
    if problems.warnings:
        md.extend([f"Check found {len(problems.warnings)} warnings; run check for the list.", ""])
    md.append(f"Merged records left out of every count: {merged_count}.")
    md.append("")
    md.extend(coverage(tables, roles, problems.not_checked, NOT_JUDGED))
    if args.out:
        path = resolve_out(ws, args.out, None)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md) + "\n")
        md.append(f"Written to {os.path.relpath(path, ws)}.")
    return OK, f"report as of {as_of}: {len(creators)} creators, {len(problems.warnings)} check warnings.", md


# ---------------------------------------------------------------- the workbook

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
STAMP_NAME = "creator_roster_export_fingerprint"


def xml_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def table_rows(t):
    return [[row[c] for c in t.header] for row in t.rows]


def fingerprint(content):
    """Order-free digest of {name: (header, rows)}: equal content, equal digest."""
    h = hashlib.sha256()
    for name in TABLES:
        header, rows = content[name]
        h.update(json.dumps([name, header, sorted(json.dumps(r, ensure_ascii=False) for r in rows)], ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def fingerprint_tables(tables):
    return fingerprint({n: (tables[n].header, table_rows(tables[n])) for n in TABLES})


def fingerprint_wb(wb):
    return fingerprint({n: (wb["sheets"][n]["header"], [r for _, r in wb["sheets"][n]["rows"]]) for n in TABLES})


def write_workbook(path, tables):
    stamp = fingerprint_tables(tables)
    files = {}
    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1, 2, 3))
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>'
        '</Types>')
    files["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{NS_PKG}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties" Target="docProps/custom.xml"/>'
        '</Relationships>')
    files["docProps/custom.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Properties xmlns="{NS_CUSTOM}" xmlns:vt="{NS_VT}">'
        f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="2" name="{STAMP_NAME}"><vt:lpwstr>{stamp}</vt:lpwstr></property>'
        '</Properties>')
    files["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><bookViews><workbookView/></bookViews><sheets>'
        + "".join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(TABLES, start=1))
        + '</sheets></workbook>')
    files["xl/_rels/workbook.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{NS_PKG}">'
        + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in (1, 2, 3))
        + '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>')
    # Style 1 is the Text number format (49), so Excel keeps typed dates and codes as text; style 2 adds bold for the header.
    files["xl/styles.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<styleSheet xmlns="{NS_MAIN}">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="49" fontId="1" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>')
    for i, name in enumerate(TABLES, start=1):
        t = tables[name]
        parts = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">',
                 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
                 '<sheetFormatPr defaultRowHeight="15"/>',
                 f'<cols><col min="1" max="{len(t.header)}" width="20" style="1" customWidth="1"/></cols><sheetData>']
        for r, values in enumerate([t.header] + table_rows(t), start=1):
            style = 2 if r == 1 else 1
            cells = "".join(f'<c r="{col_letters(c)}{r}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{xml_text(v)}</t></is></c>'
                            for c, v in enumerate(values) if v != "")
            parts.append(f'<row r="{r}">{cells}</row>')
        parts.append("</sheetData></worksheet>")
        files[f"xl/worksheets/sheet{i}.xml"] = "".join(parts)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".roster-", suffix=".xlsx")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("[Content_Types].xml", "_rels/.rels", "docProps/custom.xml", "xl/workbook.xml",
                         "xl/_rels/workbook.xml.rels", "xl/styles.xml", "xl/worksheets/sheet1.xml",
                         "xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, files[name].encode("utf-8"))
        os.replace(tmp, path)
    except OSError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise Stop(f"could not write the workbook ({exc}). If it is open in a spreadsheet app, close it and run again.")


def q(tag, ns=NS_MAIN):
    return f"{{{ns}}}{tag}"


def rich_text(el):
    """Text of an <si> or <is>: its <t>, or the <t> of each run; phonetic runs ignored."""
    parts = []
    for child in el:
        if child.tag == q("t"):
            parts.append(child.text or "")
        elif child.tag == q("r"):
            t = child.find(q("t"))
            parts.append((t.text or "") if t is not None else "")
    return "".join(parts)


def rels_of(z, path):
    try:
        root = ET.fromstring(z.read(path))
    except KeyError:
        return {}
    return {r.get("Id"): (r.get("Type", ""), r.get("Target", "")) for r in root.findall(q("Relationship", NS_PKG))}


def part_path(base, target):
    if target.startswith("/"):
        return target.lstrip("/")
    parts = []
    for p in (base + target).split("/"):
        if p == "..":
            if parts:
                parts.pop()
        elif p and p != ".":
            parts.append(p)
    return "/".join(parts)


def number_text(raw):
    try:
        x = float(raw)
    except ValueError:
        return raw
    if x.is_integer() and abs(x) < 1e15:
        return str(int(x))
    return format(x, ".15g")


def serial_to(raw, shape, date1904):
    """An Excel date serial as ISO text, or None if it is not one."""
    try:
        x = float(raw)
    except ValueError:
        return None
    if not 1 <= x < 2958466:   # Excel's serial range, 1900-01-01 to 9999-12-31
        return None
    base = dt.datetime(1904, 1, 1) if date1904 else dt.datetime(1899, 12, 30)
    moment = base + dt.timedelta(days=x)
    if shape == "date":
        return moment.date().isoformat()
    moment = (moment + dt.timedelta(seconds=30)).replace(second=0, microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%MZ")


def read_workbook(path, schema):
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        raise Stop(f"{os.path.basename(path)} is not an .xlsx workbook this script can open. Save it as Excel Workbook (.xlsx), or export a fresh one.")
    with z:
        try:
            book = ET.fromstring(z.read("xl/workbook.xml"))
        except (KeyError, ET.ParseError):
            raise Stop(f"{os.path.basename(path)} has no readable xl/workbook.xml; it is not an Excel workbook.")
        pr = book.find(q("workbookPr"))
        date1904 = pr is not None and pr.get("date1904") in ("1", "true")
        rels = rels_of(z, "xl/_rels/workbook.xml.rels")
        shared = []
        ss = [t for ty, t in rels.values() if ty.endswith("/sharedStrings")]
        ss_path = part_path("xl/", ss[0]) if ss else "xl/sharedStrings.xml"
        if ss_path in z.namelist():
            shared = [rich_text(si) for si in ET.fromstring(z.read(ss_path)).findall(q("si"))]
        sheets = [(s.get("name"), s.get(q("id", NS_REL))) for s in book.iter(q("sheet"))]
        names = [n for n, _ in sheets]
        missing = [t for t in TABLES if t not in names]
        if missing:
            hints = [f"'{n}'" for n in names if n not in TABLES]
            raise Stop(f"the workbook has no sheet named {', '.join(missing)}. Its sheets are: {', '.join(repr(n) for n in names)}. "
                       f"Sheet names must be exactly creators, pipeline and publications" + (f"; rename {', '.join(hints)} back" if hints else "") + ", then import again.")
        stamp = None
        root_rels = rels_of(z, "_rels/.rels")
        custom = [t for ty, t in root_rels.values() if ty.endswith("/custom-properties")]
        custom_path = part_path("", custom[0]) if custom else "docProps/custom.xml"
        if custom_path in z.namelist():
            for prop in ET.fromstring(z.read(custom_path)).findall(q("property", NS_CUSTOM)):
                if prop.get("name") == STAMP_NAME:
                    value = prop.find(q("lpwstr", NS_VT))
                    stamp = value.text if value is not None else None
        result = {"sheets": {}, "conversions": [], "formulas": [], "extra": [n for n in names if n not in TABLES],
                  "stamp": stamp, "problems": []}
        for name, rid in sheets:
            if name not in TABLES:
                continue
            target = rels.get(rid, ("", ""))[1]
            try:
                root = ET.fromstring(z.read(part_path("xl/", target)))
            except (KeyError, ET.ParseError):
                raise Stop(f"the workbook's sheet {name} could not be read.")
            grid, last_row = {}, 0
            for row_el in root.iter(q("row")):
                r = int(row_el.get("r")) if row_el.get("r") else last_row + 1
                last_row, cursor = r, 0
                for c in row_el.findall(q("c")):
                    ref = c.get("r")
                    col = col_index(re.match(r"[A-Z]+", ref).group(0)) if ref else cursor
                    cursor = col + 1
                    kind = c.get("t", "n")
                    v = c.find(q("v"))
                    raw = (v.text or "") if v is not None else ""
                    if kind == "s":
                        value = shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else ""
                    elif kind == "inlineStr":
                        el = c.find(q("is"))
                        value = rich_text(el) if el is not None else ""
                    elif kind == "b":
                        value = "TRUE" if raw == "1" else "FALSE"
                    else:
                        value = raw
                    grid.setdefault(r, {})[col] = (value, kind, c.find(q("f")) is not None)
            header_cells = grid.get(1, {})
            width = max(header_cells) + 1 if header_cells else 0
            header = [header_cells.get(i, ("", "", False))[0] for i in range(width)]
            while header and header[-1] == "":
                header.pop()
            expected = schema["header"][name]
            if header != expected:
                missing_c = [c for c in expected if c not in header]
                extra_c = [c for c in header if c not in expected]
                detail = "; ".join(([f"missing {', '.join(missing_c)}"] if missing_c else []) + ([f"unexpected {', '.join(repr(c) for c in extra_c)}"] if extra_c else [])) or "the columns are out of order"
                raise Stop(f"sheet {name}, row 1: {detail}. Row 1 must be exactly the header from schemas.md: {','.join(expected)}")
            rows = []
            for r in sorted(k for k in grid if k > 1):
                cells = grid[r]
                beyond = [i for i, (val, _, _) in cells.items() if i >= len(header) and val != ""]
                if beyond:
                    result["problems"].append(f"sheet {name} row {r}: a value in column {col_letters(beyond[0])}, right of the last header column. Move it into a column or clear it.")
                values = []
                for i, column in enumerate(header):
                    val, kind, formula = cells.get(i, ("", "s", False))
                    if formula:
                        result["formulas"].append(f"sheet {name} row {r} {column}: had a formula; its last calculated value was read.")
                    if kind in ("n", "d") and val != "":
                        shape = SHAPE.get(column)
                        if kind == "d":
                            converted = val[:10] if shape == "date" else val
                        elif shape in ("date", "utctime"):
                            converted = serial_to(val, shape, date1904)
                            if converted:
                                result["conversions"].append(f"sheet {name} row {r} {column}: Excel stored {val} (a date serial); read as {converted}.")
                            else:
                                converted = number_text(val)
                        else:
                            converted = number_text(val)
                        val = converted
                    values.append(val)
                if any(values):
                    rows.append((r, values))
            result["sheets"][name] = {"header": header, "rows": rows}
    return result


def cmd_export(args):
    ws, schema, rules = load_all(args)
    out_path = resolve_out(ws, args.out, WORKBOOK_DEFAULT)
    if not out_path.endswith(".xlsx"):
        raise Stop("the workbook path must end in .xlsx.")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    structural_or_stop(problems, "export the workbook")
    validate(ws, schema, rules, tables, read_roles(ws), today_utc(), problems)
    if os.path.exists(out_path) and not args.force:
        try:
            wb = read_workbook(out_path, schema)
        except Stop as exc:
            raise Stop(f"{os.path.relpath(out_path, ws)} exists but could not be read ({exc}). Run with --force to replace it.")
        wb_fp, csv_fp = fingerprint_wb(wb), fingerprint_tables(tables)
        if wb_fp != csv_fp and wb_fp != wb["stamp"]:
            raise Stop(f"{os.path.relpath(out_path, ws)} has edits that are not in the CSVs yet. Run import-xlsx first, or export with --force to discard those edits.")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_workbook(out_path, tables)
    out = [f"Wrote {os.path.relpath(out_path, ws)}: " + ", ".join(f"sheet {n} {plural(len(tables[n].rows), 'row')}" for n in TABLES) + ".",
           "The workbook is a view: edit it, then run import-xlsx. Formatting added in a spreadsheet app is lost at the next export."]
    if problems.breaks:
        out.append(f"{len(problems.breaks)} cells break the schema; fix them in the workbook and import:")
        out += [l for l in problems.lines() if l.strip().startswith("BREAK")]
    out += coverage(tables, read_roles(ws), [], "nothing beyond copying the three files")
    if problems.breaks:
        return PARTIAL, f"partial. Workbook written, but {len(problems.breaks)} cells break the schema.", out
    return OK, "done. Workbook written from the three CSVs.", out


def cmd_import(args):
    ws, schema, rules = load_all(args)
    path = args.path if args.path else os.path.join(ws, WORKBOOK_DEFAULT)
    if not os.path.isfile(path):
        path = resolve_in(ws, args.path or WORKBOOK_DEFAULT)
    role = require_role(ws, args.role) if (args.role or not args.dry_run) else "<role>"
    date = parse_date_arg(args.date, "--date")
    problems = Problems()
    tables = load_tables(ws, schema, problems)
    structural_or_stop(problems, "import the workbook")
    wb = read_workbook(path, schema)
    if wb["problems"]:
        raise Stop(" ".join(wb["problems"]))
    merged_status = rules["merged_status"][0]
    csv_fp, wb_fp = fingerprint_tables(tables), fingerprint_wb(wb)
    notes_out = []
    if wb["extra"]:
        notes_out.append(f"Sheets not read: {', '.join(wb['extra'])}.")
    if wb_fp == csv_fp:
        return OK, "done. No changes: the workbook matches the CSVs.", notes_out + wb["conversions"]
    if wb["stamp"]:
        if wb_fp == wb["stamp"]:
            raise Stop("the workbook has no edits since it was exported, and the CSVs changed since then (a skill wrote to them). Importing would undo those changes. Run export-xlsx to refresh the workbook, then edit it.")
        if csv_fp != wb["stamp"] and not args.accept_workbook:
            raise Stop("both the workbook and the CSVs changed since the last export, so importing could undo a skill's changes. "
                       "Run with --dry-run to see every differing cell. If each workbook value shown is the one to keep, run again with --accept-workbook; "
                       "otherwise export a fresh workbook and redo the edits there.")
    else:
        notes_out.append("The workbook carries no export stamp (it was not made by export-xlsx, or the app that saved it dropped the stamp), so the script could not tell whether the CSVs changed since it was made. Read every change below.")
    rng = make_rng(args.seed)
    taken = all_refs(tables)
    new_tables, changes, added_rows, stops, assigned = {}, [], [], [], []
    for name in TABLES:
        t = tables[name].copy()
        sheet = wb["sheets"][name]
        old_index = {}
        for i, row in enumerate(t.rows):
            key = tuple(row[k] for k in KEY[name])
            old_index.setdefault(key, []).append(i)
        used = {}
        appended = []
        for sheet_row, values in sheet["rows"]:
            new = dict(zip(t.header, values))
            key = tuple(new[k] for k in KEY[name])
            slot = used.get(key, 0)
            if key in old_index and slot < len(old_index[key]):
                used[key] = slot + 1
                i = old_index[key][slot]
                for column in t.header:
                    if t.rows[i][column] != new[column]:
                        if column == "notes":
                            old_entries = [e for e in split_list(t.rows[i][column]) if e]
                            new_entries = [e for e in split_list(new[column]) if e]
                            if new_entries[:len(old_entries)] != old_entries:
                                stops.append(f"sheet {name} row {sheet_row} ({', '.join(key)}): the notes lose or change an earlier entry. Notes are history and are only added to; put the earlier entries back and add a new dated entry instead. If the workbook is older than the CSVs, export a fresh one.")
                                continue
                        changes.append((name, ", ".join(key), column, t.rows[i][column], new[column], i))
                continue
            if name == "creators":
                if not new["creator_ref"]:
                    new["creator_ref"] = new_ref(taken, rng)
                    assigned.append(new["creator_ref"])
                elif new["creator_ref"] in taken:
                    stops.append(f"sheet creators row {sheet_row}: {new['creator_ref']} is already used. Leave creator_ref empty on a new row and the script assigns one.")
            if name == "publications" and not new["publication_id"]:
                stops.append(f"sheet publications row {sheet_row}: no publication_id. Record a new post with publication-tracking (its add mode assigns the id).")
            appended.append((sheet_row, new))
        missing = [", ".join(k) for k, idx in old_index.items() for _ in range(len(idx) - used.get(k, 0))]
        if missing:
            stops.append(f"sheet {name} is missing rows the CSV has: {'; '.join(missing[:10])}{' ...' if len(missing) > 10 else ''}. Nothing is deleted: put the rows back (export a fresh workbook if unsure) and change the status with a note instead. If you changed a key such as creator_ref, change it back; refs never change.")
        new_tables[name] = (t, appended)
    creators_t, creators_new = new_tables["creators"]
    if creators_new:
        ident = Identity(creators_t.rows, merged_status)
        for sheet_row, row in creators_new:
            found = ident.match(row)
            if found:
                ref, why = next(iter(found.items()))
                stops.append(f"sheet creators row {sheet_row}: the new row is the same creator as {ref} ({', '.join(why)}). Remove the new row from the workbook and edit {ref}'s row instead.")
            ident.add(row, row["creator_ref"])
    if stops:
        raise Stop("the workbook cannot be imported as it stands:\n  " + "\n  ".join(stops))
    touched_refs, script_cells = set(), []
    changed_rows = {n: {} for n in TABLES}
    for name, key, column, old, new, i in changes:
        new_tables[name][0].rows[i][column] = new
        changed_rows[name].setdefault(i, []).append((column, old, new))
    for name in TABLES:
        t, appended = new_tables[name]
        for i, cols in changed_rows[name].items():
            row = t.rows[i]
            parts = []
            for column, old, new in cols:
                parts.append(f"{column} {show(old, column)} -> {show(new, column)}" if column == "status" else column)
            if any(c != "notes" for c, _, _ in cols) or len(cols) > 1:
                entry = note_safe(f"{date} {role}: edited in the workbook ({', '.join(p for p in parts if p != 'notes')})")
                row["notes"] = ";".join([e for e in split_list(row["notes"]) if e] + [entry])
                script_cells.append((name, ", ".join(row[k] for k in KEY[name]), "notes", entry))
            touched_refs.add(row["creator_ref"])
        for sheet_row, row in appended:
            entry = note_safe(f"{date} {role}: added in the workbook")
            row["notes"] = ";".join([e for e in split_list(row["notes"]) if e] + [entry])
            script_cells.append((name, ", ".join(row[k] for k in KEY[name]), "notes", entry))
            t.rows.append(row)
            t.lines.append("new")
            touched_refs.add(row["creator_ref"])
    for row in creators_t.rows:
        if row["creator_ref"] in touched_refs and row["last_activity"] != date.isoformat():
            row["last_activity"] = date.isoformat()
            script_cells.append(("creators", row["creator_ref"], "last_activity", date.isoformat()))
    after = {n: new_tables[n][0] for n in TABLES}
    post = Problems()
    validate(ws, schema, rules, after, read_roles(ws), date, post)
    out = list(notes_out)
    out.append(f"Changed cells ({len(changes)}), as file | row key | column | old | new:")
    out += [f"  {CSV_PATH[n]} | {k} | {c} | {o!r} | {v!r}" for n, k, c, o, v, _ in changes]
    news = [(n, r) for n in TABLES for _, r in new_tables[n][1]]
    out.append(f"New rows ({len(news)}):")
    out += [f"  {CSV_PATH[n]} | {', '.join(r[k] for k in KEY[n])}" + (" (creator_ref assigned)" if n == "creators" else "") for n, r in news]
    out.append(f"Cells the script adds ({len(script_cells)}):")
    out += [f"  {CSV_PATH[n]} | {k} | {c} | {v!r}" for n, k, c, v in script_cells]
    if wb["conversions"] or wb["formulas"]:
        out.append("Read with a conversion (check each):")
        out += [f"  {c}" for c in wb["conversions"] + wb["formulas"]]
    if post.breaks:
        out.append(f"The imported values would break the schema in {len(post.breaks)} places; fix them in the workbook and import again:")
        out += [l for l in post.lines() if l.strip().startswith("BREAK")]
        out.append("Nothing was written.")
        return BAD, f"refused. {len(post.breaks)} imported values break the schema.", out
    if post.warnings:
        out.append(f"Warnings after import ({len(post.warnings)}):")
        out += [l for l in post.lines() if l.strip().startswith("WARN")]
    if args.dry_run:
        # a creator_ref is drawn when the rows are written, so the dry run names none
        for i, ref in enumerate(assigned, start=1):
            out = [line.replace(ref, f"(new ref {i}, drawn on write)") for line in out]
        out.append("Dry run: nothing written.")
        return OK, f"dry run. {plural(len(changes), 'changed cell')} and {plural(len(news), 'new row')} would be imported.", out
    to_write = [after[n] for n in TABLES if changed_rows[n] or new_tables[n][1] or (n == "creators" and touched_refs)]
    commit(to_write)
    for n in TABLES:
        out.append(counts_line(after[n], len(new_tables[n][1]), len(changed_rows[n])))
    if not args.no_export:
        write_workbook(os.path.join(ws, WORKBOOK_DEFAULT), after)
        out.append(f"Refreshed {WORKBOOK_DEFAULT} from the CSVs, so it shows the assigned refs and notes. If it was open, close it and reopen it.")
    out += coverage(tables, read_roles(ws), [], "whether each edited value is true; the note records who changed it")
    return OK, f"done. {plural(len(changes), 'changed cell')} and {plural(len(news), 'new row')} imported.", out


# ---------------------------------------------------------------- command line

class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"RESULT: refused. {message}. Run with --help for the options.")
        sys.exit(BAD)


def build_parser():
    p = Parser(prog="roster.py", description=__doc__.split("\n\n")[0],
               epilog="Exit 0 done; 1 bad input or schema break, nothing written; 2 partial or warnings.")
    p.add_argument("workspace", help="the workspace folder (holds program/ and data/)")
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    s = sub.add_parser("check", help="validate the three CSVs: headers, allowed values, dates, refs across files, unique codes")
    s.add_argument("--as-of", help="date the check runs as of, YYYY-MM-DD (default today, UTC)")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("add", help="add creators from a vetting shortlist, assigning each a creator_ref")
    s.add_argument("--from-shortlist", required=True, help="the shortlist CSV, for example data/shortlist-2026-10-19.csv")
    s.add_argument("--verdicts", help="comma list of verdicts to add (default in references/roster-rules.md)")
    s.add_argument("--role", help="the role adding them, from program.md section 10")
    s.add_argument("--date", help="date for the notes, YYYY-MM-DD (default today, UTC)")
    s.add_argument("--seed", type=int, help="fix the random refs, for repeatable test runs only")
    s.add_argument("--dry-run", action="store_true", help="print what would be added; write nothing")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("find", help="is a creator already in the roster? matches handle and profile URL as add does")
    s.add_argument("--handle", help="the handle, with or without @")
    s.add_argument("--platform", help="the platform, if known; without it every platform is searched")
    s.add_argument("--url", help="the profile URL")
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("update", help="change fields on one creator, appending a dated note")
    s.add_argument("creator_ref")
    s.add_argument("assignments", nargs="*", metavar="field=value", help="none or more; an empty value clears the field (the note records the old value); with none, only the note is added")
    s.add_argument("--note", required=True, help="the reason for the change (no ';')")
    s.add_argument("--role", help="the role making the change, from program.md section 10")
    s.add_argument("--date", help="date for the note, YYYY-MM-DD (default today, UTC)")
    s.add_argument("--dry-run", action="store_true", help="print the change; write nothing")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("merge", help="merge a duplicate record into the older one; nothing is deleted")
    s.add_argument("keep_ref", help="the older record, which stays")
    s.add_argument("drop_ref", help="the newer duplicate, which is marked merged")
    s.add_argument("--note", required=True, help="the evidence that they are one creator (no ';')")
    s.add_argument("--role", help="the role making the change, from program.md section 10")
    s.add_argument("--date", help="date for the notes, YYYY-MM-DD (default today, UTC)")
    s.add_argument("--dry-run", action="store_true", help="print the merge; write nothing")
    s.set_defaults(func=cmd_merge)

    s = sub.add_parser("report", help="counts and the lists that need a person")
    s.add_argument("--as-of", help="report date, YYYY-MM-DD (default today, UTC)")
    s.add_argument("--out", help="also write the report as Markdown to this path inside the workspace")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("export-xlsx", help="write the workbook from the three CSVs")
    s.add_argument("--out", help=f"workbook path inside the workspace (default {WORKBOOK_DEFAULT})")
    s.add_argument("--force", action="store_true", help="overwrite a workbook that has edits not yet imported")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("import-xlsx", help="read an edited workbook back into the three CSVs, printing every changed cell")
    s.add_argument("path", nargs="?", help=f"the workbook (default {WORKBOOK_DEFAULT})")
    s.add_argument("--dry-run", action="store_true", help="print every change; write nothing")
    s.add_argument("--role", help="the role whose edits these are, from program.md section 10 (not needed for --dry-run)")
    s.add_argument("--date", help="date for the notes, YYYY-MM-DD (default today, UTC)")
    s.add_argument("--accept-workbook", action="store_true", help="import even though the CSVs also changed since the export")
    s.add_argument("--no-export", action="store_true", help="do not refresh the workbook after importing")
    s.add_argument("--seed", type=int, help="fix the random refs for new rows, for repeatable test runs only")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("schema", help="print the headers and allowed values as read from references/schemas.md")
    s.set_defaults(func=cmd_schema)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        code, result, lines = args.func(args)
    except Stop as exc:
        print(f"RESULT: refused. {exc}")
        print("Nothing was written.")
        return BAD
    print(f"RESULT: {result}")
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
