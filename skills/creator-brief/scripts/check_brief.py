#!/usr/bin/env python3
"""Check a configured creator brief against the roster and the programme file.

    python3 -I check_brief.py <workspace> <brief.md> [<brief.md> ...] [--cohort] [--today YYYY-MM-DD]

The script reads; it never writes, sends or fetches anything. Standard library only.

Exit codes:
  0  every check passed: the brief is ready for the programme lead's read before sending
  1  bad input: a file, a programme section, a roster header, a brief heading or a template
     placeholder is missing or malformed; the message says what to fix; that brief was not judged
  2  not ready to send: a content mismatch (a claim, the code, the link, the disclosure, the pay,
     the rights) or a gap marked [MISSING: ...]; every finding is printed
With several briefs the exit code is the worst one: 1 before 2 before 0.
"""

import argparse
import csv
import datetime
import glob
import io
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "references"))
from brand_context import audience_rule, unrestricted

# ---------------------------------------------------------------------------
# Constants. Each names where it comes from.
# ---------------------------------------------------------------------------

# Brief headings, in order. Source: assets/brief-template.md in this skill.
BRIEF_SECTIONS = [
    "Why we are doing this",
    "Your creative freedom",
    "What we need from you",
    "What you can say",
    "What you never say or show",
    "Your code and link",
    "Disclosure",
    "Platform and audience rules",
    "Approval",
    "Pay",
    "Using your content",
    "Contact",
]
# The last heading, the programme lead's notes. Source: assets/brief-template.md.
LEAD_SECTION_PREFIX = "For the programme lead"
# The one fixed sentence allowed under "What you can say". Source: assets/brief-template.md.
CAN_SAY_INTRO = ("Statements about the product stay in these exact words. "
                 "Everything around them is yours.")
# Sections a cohort's briefs must share word for word. Source: SKILL.md step 7 (build choice).
COHORT_SHARED = [
    "Why we are doing this",
    "Your creative freedom",
    "What we need from you",
    "What you can say",
    "What you never say or show",
    "Disclosure",
    "Platform and audience rules",
    "Approval",
]
# Sections the forbidden-phrase search skips: one holds only checked approved lines, the
# other lists the forbidden phrases on purpose. Source: SKILL.md step 8 (build choice).
FORBIDDEN_SEARCH_SKIPS = {"What you can say", "What you never say or show"}

# Roster header, in order. Source: pack references/schemas.md section 4.
CREATORS_HEADER = [
    "creator_ref", "display_name", "primary_platform", "primary_handle", "profile_url",
    "other_platforms", "tier", "followers_primary", "followers_as_of", "engagement_rate_pct",
    "engagement_as_of", "niche_tags", "audience_fit_score", "brand_safety_flag", "contact_path",
    "contact_email", "status", "compensation_model", "commission_rate_pct", "flat_fee", "code",
    "affiliate_link", "rail", "agreement_date", "agreement_file", "usage_rights_until",
    "exclusivity_until", "first_campaign", "last_activity", "notes",
]
# Code plan header, in order. Source: pack references/schemas.md section 9.
CODE_PLAN_HEADER = [
    "creator_ref", "code", "discount_type", "discount_value", "applies_to", "starts_at",
    "ends_at", "usage_limit", "once_per_customer", "status", "minted_at", "minted_by", "notes",
]
# Platform values. Source: pack references/schemas.md section 4, primary_platform.
PLATFORMS = {"instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast",
             "newsletter", "bluesky", "threads", "other"}
# Roster statuses under which terms are agreed in writing. Source: schemas.md section 4.
AGREED_STATUSES = {"agreed", "active"}
# Code-plan statuses under which a code exists in the store. Source: schemas.md section 9.
LIVE_CODE_STATUSES = {"minted", "active"}
# Talking-point ceiling when programme section 9 states none. Source: programme template
# section 9, creative-freedom default ("up to three talking points").
DEFAULT_MAX_POINTS = 3
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
# Source marks on programme lines. Source: programme template, opening paragraph.
SOURCE_MARKS = re.compile(r"\[(?:owner|observed|default|open)\]", re.IGNORECASE)
# Shapes. Source: pack references/schemas.md section 2.
CREATOR_REF = re.compile(r"^c-[a-z0-9]{6}$")
CAMPAIGN_SLUG = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Programme lines found by their fixed template text, with the brief section that must carry
# the number. Source: programme template 0.1.2, sections 8 and 11 (lines added in 0.1.2).
TERM_LINES = [
    (11, "brand approval turnaround on submitted content", "Approval",
     "the approval turnaround"),
    (11, "minimum time a post stays live", "What we need from you", "the minimum days live"),
    (8, "time a creator has to correct a live post", "Disclosure", "the correction time"),
]
# Pay terms the brief states, found by their template text. Source: programme template 0.1.2,
# sections 5 and 6; the minimum is written "minimum <amount>" or "no minimum" (program-setup's
# writing rule, template 0.1.2 section 6).
HOLDBACK_LABEL = "holdback before a sale counts as commissionable"
PAYOUT_LABEL = "payout schedule"
MINIMUM_RE = re.compile(r"\bminimum\s+(?:[A-Za-z]{3}\s+)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)",
                        re.IGNORECASE)
NO_MINIMUM_RE = re.compile(r"\bno minimum\b", re.IGNORECASE)
# The spoken form of a disclosure, in section 8's placement text: "spoken: <phrase>", ending at
# ";" or the mark. Source: the lead's ruling of 2026-10-21 (integration review F4).
SPOKEN_RE = re.compile(r"\bspoken:\s*([^;]+)", re.IGNORECASE)
# The fixed words for a right the agreement did not grant. Source: assets/brief-template.md;
# the rule that an empty date beside an agreement means none: schemas.md section 4.
NONE_PHRASES = {"usage_rights_until": "reuse: none", "exclusivity_until": "exclusivity: none"}
# Publications header, in order. Source: pack references/schemas.md section 6.
PUBLICATIONS_HEADER = [
    "publication_id", "campaign_slug", "creator_ref", "platform", "post_url", "posted_at",
    "format", "disclosure_seen", "disclosure_form", "code_in_post", "link_in_post",
    "approval_id", "check_day1", "check_day7", "check_day30", "rights_until", "notes",
]
# A usage window that runs from the posting date: the dated roster note
# "YYYY-MM-DD ... rights from posting: <n> months", matched by its phrase after the date, and the
# brief's duration wording for it. Source: schemas.md section 4 and the lead's ruling of
# 2026-10-21 (integration review 4b, N2).
FROM_POSTING_RE = re.compile(r"rights from posting:\s*(\d+)\s*months?", re.IGNORECASE)
FROM_POSTING_WORDING = "reuse: {n} months from the day you post"
# Roster notes that change what may be sent. Source: schemas.md section 4, rules for the roster.
DO_NOT_CONTACT = "do not contact"
MERGED_INTO = re.compile(r"merged into (c-[a-z0-9]{6})")
# Markers this skill writes. Source: SKILL.md steps 5 and 6.
MISSING_MARK = "[MISSING:"
PENDING_MARK = "to be cleared by the owner"
# A dollar sign before a digit: hosts rewrite it (pack contract section 6).
DOLLAR_DIGIT = re.compile(r"\$(?=\s?\d)")
# The only shapes read from programme sections 7 and 8, and from the brief's claim lines.
# Source: program-setup's writing rules as the lead ruled them on 2026-10-21, matched to
# content-approval's check_caption.py so a programme file that passes here also passes there.
APPROVED_RE = re.compile(r'^- (?P<product>[^"\n]+?):\s*"(?P<wording>[^"\n]+)"\s*\[owner\]\s*$')
UNCLEARED_RE = re.compile(r'^- (?P<product>[^"\n]+?):\s*"(?P<wording>[^"\n]+)"\s*'
                          r'(?P<mark>\[(?:observed|default|open)\])?\s*$')
BRIEF_CLAIM_RE = re.compile(r'^- (?P<product>[^"\n]+?):\s*"(?P<wording>[^"\n]+)"\s*$')
PLATFORM_LINE_RE = re.compile(
    r'^[ \t]+- (?P<platform>[^:"\n]+):\s*"(?P<wording>[^"\n]+)"(?P<placement>[^\n]*?)\s*\[owner\]\s*$')
DOUBLE_QUOTED = re.compile(r'"([^"\n]+)"')
OTHER_QUOTES = re.compile("[“”‘’`]")
# The section 8 field the platform lines sit under. Source: programme template 0.1.2, section 8.
LABEL_WORDING = ("Required disclosure wording and placement, per platform (text at the start of the "
                 "caption, spoken aloud and on screen in video, platform paid-partnership tool "
                 "switched on in addition):")
NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?!\w)")
URL = re.compile(r"https?://\S+")


class Bad(Exception):
    """Bad input: the brief cannot be judged until the named thing is fixed (exit 1)."""


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def unify(text):
    """Lower-case, straight quotes, no emphasis marks, single spaces."""
    t = (text.replace("’", "'").replace("‘", "'")
         .replace("“", '"').replace("”", '"'))
    t = t.replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", t).strip().lower()


def needle(text):
    """A phrase as it is searched for: unified, without wrapping quotes or end punctuation."""
    t = unify(text).strip('"').strip()
    return re.sub(r"[.;:,!]+$", "", t).strip()


def numbers(text):
    """Numbers written in prose, ignoring dates, links and codes."""
    t = URL.sub(" ", text)
    t = ISO_DATE.sub(" ", t)
    return [float(n.replace(",", "")) for n in NUMBER.findall(t)]


def has_number(text, value):
    try:
        v = float(value)
    except ValueError:
        return False
    return any(abs(v - n) < 1e-9 for n in numbers(text))


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def read_text(path, what, fix):
    if not os.path.isfile(path):
        raise Bad(f"{what} was not found at {path}; {fix}")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise Bad(f"{what} at {path} could not be read as UTF-8 text ({exc}); save it as UTF-8.")


def read_csv(path, header, what):
    text = read_text(path, what, "check the workspace path.")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise Bad(f"{what} at {path} is empty; it needs the header row from schemas.md.")
    head = [c.strip() for c in rows[0]]
    if head != header:
        missing = [c for c in header if c not in head]
        extra = [c for c in head if c not in header]
        detail = (f"missing {', '.join(missing) or 'none'}; extra {', '.join(extra) or 'none'}"
                  if missing or extra else "the columns are out of order")
        raise Bad(f"{what} at {path} has a header that differs from schemas.md ({detail}); "
                  "fix the header, or run creator-roster's validate.")
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        r = r + [""] * (len(header) - len(r))
        out.append({k: v.strip() for k, v in zip(header, r)})
    return out


# ---------------------------------------------------------------------------
# The programme file
# ---------------------------------------------------------------------------

def programme_sections(text):
    sections, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.\s", line)
        if m:
            current = int(m.group(1))
            sections[current] = []
            continue
        if line.startswith("## "):
            current = None
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def need(sections, n, why):
    if n not in sections:
        raise Bad(f"program/program.md has no section {n}, which this check needs for {why}; "
                  "restore the heading from the programme template and fill it with the owner "
                  "(program-setup).")
    return sections[n]


def subsection(lines, word):
    """Lines under the first ### heading containing word; None if there is no such heading."""
    found, inside, out = False, False, []
    for line in lines:
        if line.startswith("### "):
            inside = word in line.lower()
            found = found or inside
            continue
        if inside:
            out.append(line)
    return out if found else None


def bullet_body(line):
    m = re.match(r"^\s*[-*]\s+(\S.*)$", line)
    return m.group(1) if m else None


def read_claims(sec7):
    """Approved and Forbidden, in the one shape each; anything else is a finding, not read."""
    approved_lines = subsection(sec7, "approved")
    forbidden_lines = subsection(sec7, "forbidden")
    if approved_lines is None or forbidden_lines is None:
        raise Bad("programme section 7 needs both an 'Approved claims' and a 'Forbidden claims' "
                  "subheading (### ...) as in the programme template.")
    approved, not_cleared, findings = {}, {}, []
    for line in approved_lines:
        if not line.startswith("- "):
            continue  # indented detail lines and prose are not claims
        text = line.rstrip()
        m = APPROVED_RE.match(text)
        if m:
            approved[(needle(m.group("product")), needle(m.group("wording")))] = text
            continue
        if "[owner]" in text:
            findings.append(f"programme section 7, Approved: '{text[:90]}' is not in the shape - "
                            "<product>: \"<verbatim wording>\" [owner] (straight double quotes, one "
                            "wording), so it is not read as approved; program-setup rewrites it")
            continue
        u = UNCLEARED_RE.match(text)
        if u:
            not_cleared[(needle(u.group("product")), needle(u.group("wording")))] = (
                u.group("mark") or "no mark")
    products = {p for p, _ in approved}
    phrases, described = [], 0
    current, detail = None, False
    for line in forbidden_lines:
        if line.startswith("- "):
            current, detail = line[2:], False
        elif current is not None and line[:1] in (" ", "\t") and line.strip():
            detail = True
        else:
            current = None
            continue
        text = line.strip()
        if "[open]" in text.lower():
            continue
        found = DOUBLE_QUOTED.findall(text)
        if OTHER_QUOTES.search(text):
            findings.append(f"programme section 7, Forbidden: '{text[:90]}' quotes with typographic "
                            "quotes or backticks; only phrases in straight double quotes are read")
        if not found:
            body = SOURCE_MARKS.sub("", text.split(":", 1)[-1]).strip()
            if not detail and ":" in text and body:
                described += 1
            continue
        named = {p for p in products if p and p in unify(text)}
        for phrase in found:
            phrases.append(phrase)
            for (p, w) in approved:
                if w == needle(phrase) and (not named or p in named):
                    raise Bad(f"programme section 7 lists \"{phrase}\" both as Approved for {p} "
                              "and as Forbidden; the owner settles which, with program-setup.")
    return approved, not_cleared, phrases, described, findings


def platform_row(sec3, platform):
    header, rows = None, []
    for line in sec3:
        t = re.match(r"^\s*\|(.+)\|\s*$", line)
        if not t:
            continue
        cells = [c.strip() for c in t.group(1).split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        rows.append(cells)
    if header is None:
        raise Bad("programme section 3 has no platform table; restore it from the programme "
                  "template and fill it with the owner.")
    organic = next((i for i, h in enumerate(header) if "organic" in h), None)
    if organic is None:
        raise Bad("programme section 3's table has no 'organic creator posts' column.")

    def label(cells):
        return SOURCE_MARKS.sub("", cells[0]).strip().lower()

    def matches(lab):
        first = re.split(r"[\s(]", lab)[0]
        if lab == platform or first == platform:
            return True
        return platform in ("podcast", "newsletter") and lab.startswith("podcasts")

    row = next((r for r in rows if matches(label(r))), None)
    if row is None:
        row = next((r for r in rows if label(r) == "other"), None)
    if row is None:
        raise Bad(f"programme section 3 has no row for {platform} and no 'other' row.")
    lab = label(row)
    raw = SOURCE_MARKS.sub("", row[organic] if organic < len(row) else "").strip()
    low = raw.lower()
    if not low:
        raise Bad(f"programme section 3, row '{lab}', has no value for organic creator posts; "
                  "the owner rules on it with program-setup.")
    if re.match(r"^no\b", low):
        return lab, "no", ""
    if low.startswith("yes"):
        return lab, "yes", ""
    if low.startswith("unknown"):
        return lab, "unknown", ""
    if low.startswith("with conditions"):
        cond = raw[len("with conditions"):].strip(" :;,-()–—")
        if not cond:
            raise Bad(f"programme section 3, row '{lab}', says 'with conditions' without stating "
                      "them; the owner states them with program-setup.")
        return lab, "with conditions", cond
    raise Bad(f"programme section 3, row '{lab}', reads '{raw}', which is not yes, no, "
              "with conditions or unknown.")


def disclosure_wording(sec8, platform):
    """The platform's indented line under the required-disclosure field, in the one shape
    - <platform>: "<wording>" <placement> [owner]. The first quoted string is the wording and a
    second is placement. The key is the roster value; 'all' or a section 3 row label is not read."""
    findings, notes, found = [], [], []
    in_field = seen_field = other_shape = False
    for line in sec8:
        if line.startswith("- "):
            in_field = " ".join(line[2:].split()).startswith(LABEL_WORDING)
            seen_field = seen_field or in_field
            if in_field and DOUBLE_QUOTED.search(" ".join(line[2:].split())[len(LABEL_WORDING):]):
                notes.append("section 8: wording on the field line itself is not read; it goes on "
                             "the indented platform lines")
            continue
        if not in_field:
            continue
        if not line.strip() or line[:1] not in (" ", "\t"):
            in_field = False
            continue
        m = PLATFORM_LINE_RE.match(line.rstrip())
        key = (m.group("platform") if m else line.strip().lstrip("-* ").split(":", 1)[0]).strip()
        if not m:
            if key == platform:
                other_shape = True
                findings.append(f"programme section 8: '{line.strip()[:90]}' is not in the shape - "
                                "<platform>: \"<wording>\" <placement> [owner], so it is not read")
            else:
                notes.append(f"section 8 line not in the shape, not read: {line.strip()[:70]}")
        elif key not in PLATFORMS:
            notes.append(f"section 8 line for '{key}' is not read: lines are keyed by the roster's "
                         "platform value, and 'all' counts for no platform")
        elif key == platform:
            found.append(m)
    if not seen_field:
        raise Bad("programme section 8 has no 'Required disclosure wording and placement, per "
                  "platform' line in the template's words; restore it with program-setup.")
    if not found:
        extra = "; a line for it exists but in another shape" if other_shape else ""
        raise Bad(f"programme section 8 has no disclosure line for {platform} in the shape "
                  f"- {platform}: \"<wording>\" <placement> [owner] under the required-disclosure "
                  f"field{extra}; the owner adds it with program-setup.")
    if len(found) > 1:
        findings.append(f"programme section 8 has {len(found)} lines for {platform}; one line per "
                        "platform, so the owner removes the extra")
    placement = found[0].group("placement").strip()
    if DOUBLE_QUOTED.search(placement):
        notes.append(f"section 8, {platform}: a second quoted string is placement, not wording")
    return found[0].group("wording"), placement, findings, notes


def max_points(sec9):
    m = re.search(r"up to (\w+) talking points?", unify(" ".join(sec9)))
    if m:
        w = m.group(1)
        if w.isdigit():
            return int(w), "programme section 9"
        if w in NUMBER_WORDS:
            return NUMBER_WORDS[w], "programme section 9"
    return DEFAULT_MAX_POINTS, "the programme template's default (section 9 states no number)"


def labelled_value(lines, label):
    """The value written after a template line's text, or None when the line is absent."""
    for line in lines:
        body = bullet_body(line)
        if body and body.lower().startswith(label) and ":" in body:
            return SOURCE_MARKS.sub("", body.split(":", 1)[1]).strip()
    return None


def section4_discount(sec4):
    for line in sec4:
        m = re.match(r"^\s*[-*]\s+customer-facing discount[^:]*:(.*)$", line, re.IGNORECASE)
        if m:
            value = SOURCE_MARKS.sub("", m.group(1)).strip()
            return value or None
    return None


# ---------------------------------------------------------------------------
# The brief
# ---------------------------------------------------------------------------

def parse_brief(path):
    text = read_text(path, "The brief", "check the path.")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("Status:"):
        raise Bad("the brief's first line must be its status line, starting 'Status:' "
                  "(the template starts 'Status: unchecked').")
    for i, line in enumerate(lines, 1):
        for mark in ("{{", "<!--"):
            if mark in line:
                raise Bad(f"line {i} of the brief still carries template guidance ({mark}); "
                          "fill it from its source or write [MISSING: <what> - <who supplies it>].")
    headers, sections, title = {}, [], None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            sections.append({"title": line[3:].strip(), "start": i, "body": []})
            continue
        if sections:
            sections[-1]["body"].append(line)
            continue
        if line.startswith("# ") and title is None:
            title = i
            continue
        m = re.match(r"^(Campaign|Creator|Platform|Brief date):\s*(\S.*)$", line)
        if m:
            headers[m.group(1)] = m.group(2).strip()
    if title is None:
        raise Bad("the brief has no title line starting '# ' before its first section.")
    titles = [s["title"] for s in sections]
    lead_ok = bool(titles) and titles[-1].startswith(LEAD_SECTION_PREFIX)
    if titles[:-1] != BRIEF_SECTIONS or not lead_ok:
        missing = [t for t in BRIEF_SECTIONS if t not in titles]
        extra = [t for t in titles if t not in BRIEF_SECTIONS
                 and not t.startswith(LEAD_SECTION_PREFIX)]
        parts = []
        if missing:
            parts.append("missing: " + "; ".join(missing))
        if extra:
            parts.append("not in the template: " + "; ".join(extra))
        if not lead_ok:
            parts.append(f"the last section must be '## {LEAD_SECTION_PREFIX} ...'")
        if not parts:
            parts.append("the sections are out of order")
        raise Bad("the brief's sections do not match assets/brief-template.md ("
                  + "; ".join(parts) + ").")
    for key in ("Campaign", "Creator", "Platform", "Brief date"):
        if key not in headers:
            raise Bad(f"the brief has no '{key}:' line under its title.")
    if not CREATOR_REF.match(headers["Creator"]):
        raise Bad(f"'Creator: {headers['Creator']}' is not a creator_ref (c- and six letters "
                  "or digits).")
    if not CAMPAIGN_SLUG.match(headers["Campaign"]):
        raise Bad(f"'Campaign: {headers['Campaign']}' is not a campaign slug (YYYY-MM-...).")
    platform = headers["Platform"].lower()
    if platform not in PLATFORMS:
        raise Bad(f"'Platform: {headers['Platform']}' is not one of the roster's platform values.")
    try:
        datetime.date.fromisoformat(headers["Brief date"])
    except ValueError:
        raise Bad(f"'Brief date: {headers['Brief date']}' is not an ISO date.")
    by_title = {}
    for s in sections:
        s["text"] = "\n".join(s["body"])
        by_title[s["title"]] = s
        if s["title"] in BRIEF_SECTIONS and not s["text"].strip():
            raise Bad(f"the section '{s['title']}' is empty.")
    lead = sections[-1]
    if not any(re.match(r"^\s*(?:[-*]\s+)?Coverage:", l) for l in lead["body"]):
        raise Bad("the programme lead's notes have no 'Coverage:' line.")
    return {
        "path": path, "lines": lines, "headers": headers, "platform": platform,
        "sections": by_title, "lead": lead, "title_line": title,
        "creator_text": "\n".join(lines[1:lead["start"]]),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.rows, self.problems, self.gaps = [], 0, 0

    def ok(self, msg):
        self.rows.append(("PASS", msg))

    def fail(self, msg):
        self.rows.append(("FAIL", msg))
        self.problems += 1

    def gap(self, msg):
        self.rows.append(("GAP", msg))
        self.gaps += 1

    def unchecked(self, msg):
        self.rows.append(("NOT CHECKED", msg))

    def note(self, msg):
        self.rows.append(("NOTE", msg))

    def status_line(self, today):
        if self.problems or self.gaps:
            parts = []
            if self.problems:
                parts.append(plural(self.problems, "problem"))
            if self.gaps:
                parts.append(plural(self.gaps, "gap"))
            prefix = "PARTIAL, " if self.gaps else ""
            return (f"Status: {prefix}NOT READY TO SEND: {', '.join(parts)} "
                    f"(check_brief.py, {today})")
        return f"Status: READY TO SEND after the programme lead's read (check_brief.py, {today})"


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def check_one(workspace, brief_path, prog, roster, today):
    rep = Report()
    b = parse_brief(brief_path)
    h, platform, sec = b["headers"], b["platform"], b["sections"]
    ref, slug = h["Creator"], h["Campaign"]

    # Where the brief sits.
    rel = os.path.relpath(os.path.abspath(brief_path), os.path.abspath(workspace))
    parts = rel.split(os.sep)
    if len(parts) == 4 and parts[0] == "campaigns" and parts[2] == "briefs":
        if parts[1] != slug or parts[3] != ref + ".md":
            raise Bad(f"the brief is saved as {rel} but says Campaign: {slug} and Creator: {ref}; "
                      f"save it as campaigns/{slug}/briefs/{ref}.md.")
        rep.ok(f"saved at {rel}")
    else:
        rep.note(f"not saved at campaigns/{slug}/briefs/{ref}.md (found at {rel}); save it there "
                 "before sending")
    if os.path.isfile(os.path.join(workspace, "campaigns", slug, "plan.md")):
        rep.unchecked("the why, the deliverables and the dates against campaigns/"
                      f"{slug}/plan.md: the programme lead reads them against the plan")
    else:
        rep.note(f"campaigns/{slug}/plan.md was not found; the why, deliverables and dates "
                 "must be marked User-provided in the programme lead's notes")

    # The roster row.
    row = next((r for r in roster if r["creator_ref"] == ref), None)
    if row is None:
        raise Bad(f"data/creators.csv has no row for {ref}; add the creator with creator-roster "
                  "first, or correct the Creator: line.")
    merged = MERGED_INTO.search(row["notes"])
    if row["status"] == "ended" and merged:
        raise Bad(f"{ref} was merged into {merged.group(1)} (roster notes); brief the surviving "
                  f"row: Creator: {merged.group(1)}.")
    if DO_NOT_CONTACT in row["notes"].lower():
        rep.fail(f"the roster notes for {ref} say do not contact; no brief goes to them")
    if row["brand_safety_flag"] == "exclude":
        rep.fail(f"the roster marks {ref} brand_safety_flag exclude; no brief goes to an "
                 "excluded creator")
    elif row["brand_safety_flag"] == "review":
        rep.note(f"the roster marks {ref} brand_safety_flag review; the owner decides before "
                 "this is sent")
    agreed = row["status"] in AGREED_STATUSES
    if agreed:
        rep.ok(f"roster status {row['status']}")
    else:
        rep.gap(f"terms are not agreed yet (roster status: {row['status'] or 'empty'}); pay "
                "and rights stay [MISSING: ...] until partnership-agreement and signature")

    # Platform: the creator's, and allowed by programme section 3.
    own = {row["primary_platform"]} | {p.split(":", 1)[0] for p in
                                        row["other_platforms"].split(";") if p}
    if platform in own:
        rep.ok(f"{platform} is one of {ref}'s platforms in the roster")
    else:
        rep.fail(f"{platform} is not among {ref}'s platforms in the roster "
                 f"({', '.join(sorted(p for p in own if p)) or 'none'})")
    sec3 = need(prog, 3, "the platform rule")
    row_label, allowed, conditions = platform_row(sec3, platform)
    rules_text = unify(sec["Platform and audience rules"]["text"])
    if allowed == "no":
        rep.fail(f"programme section 3 says no organic creator posts on {row_label}; this "
                 "brief cannot go out for that platform")
    elif allowed == "unknown":
        rep.gap(f"programme section 3 says 'unknown' for creator posts on {row_label}; the "
                "owner rules before a brief goes out")
    elif allowed == "with conditions":
        if needle(conditions) in rules_text:
            rep.ok(f"section 3 conditions for {row_label} stated verbatim")
        else:
            rep.fail(f"'Platform and audience rules' does not state programme section 3's "
                     f"conditions for {row_label} word for word: \"{conditions}\"")
    else:
        rep.ok(f"programme section 3 allows creator posts on {row_label}")
    age_rule = audience_rule(need(prog, 9, "audience rules"))
    if age_rule is None:
        rep.gap("programme section 9 needs a settled Audience age rule, including none with a reason")
    elif unrestricted(age_rule):
        rep.ok("programme section 9 requires no audience age restriction")
        if re.search(r"\badults?[- ]only\b|audience must be adults|audience.*18\+", rules_text):
            rep.fail("brief adds an audience age restriction absent from programme section 9")
    else:
        ages = re.findall(r"\b(?:1[3-9]|[2-9][0-9])\b", age_rule)
        matches = all(re.search(r"\b" + age + r"\b", rules_text) for age in ages) if ages else needle(age_rule) in rules_text
        if matches:
            rep.ok("the configured audience-age requirement is stated")
            rep.unchecked("evidence and platform settings against programme section 9: " + age_rule)
        else:
            rep.fail("'Platform and audience rules' omits the configured audience restriction: " + age_rule)

    # Disclosure: programme section 8 wording for this platform.
    if allowed == "no":
        rep.unchecked("disclosure wording: the platform is not allowed, so it was not looked up")
    else:
        sec8 = need(prog, 8, "the disclosure wording")
        disc = unify(sec["Disclosure"]["text"])
        w, placement, s8_findings, s8_notes = disclosure_wording(sec8, platform)
        for finding in s8_findings:
            rep.fail(finding)
        for note in s8_notes:
            rep.note(note)
        # The written wording must stand as a quoted string, so the spoken line (which may
        # contain the same words, unquoted) cannot stand in for it.
        written = {needle(q) for q in DOUBLE_QUOTED.findall(disc)}
        if needle(w) in written:
            rep.ok(f"disclosure wording \"{w}\" present, quoted")
        else:
            rep.fail(f"the disclosure wording \"{w}\" from programme section 8 for "
                     f"{platform} is not in 'Disclosure' as a quoted string")
        spoken = SPOKEN_RE.search(placement)
        if spoken:
            phrase = spoken.group(1).strip().rstrip(".,").strip()
            if needle(phrase) in disc:
                rep.ok(f"spoken disclosure \"{phrase}\" present")
            else:
                rep.fail(f"the spoken disclosure from programme section 8 for {platform}, "
                         f"\"{phrase}\", is not in 'Disclosure'")
        else:
            rep.note(f"programme section 8 gives no spoken form for {platform} (spoken: ...)")

    # Claims: every line under "What you can say" is an Approved [owner] line for that product.
    sec7 = need(prog, 7, "the approved and forbidden claims")
    approved, not_cleared, forbidden, described, s7_findings = read_claims(sec7)
    for finding in s7_findings:
        rep.fail(finding)
    limit, limit_src = max_points(need(prog, 9, "the talking-point limit"))
    points = 0
    can_start = sec["What you can say"]["start"]
    for offset, line in enumerate(sec["What you can say"]["body"], 1):
        n = can_start + offset + 1
        if not line.strip() or needle(line) == needle(CAN_SAY_INTRO):
            continue
        cm = BRIEF_CLAIM_RE.match(line.rstrip())
        if cm is None:
            rep.fail(f"line {n}, under 'What you can say', is not a claim line in the shape - "
                     "<product>: \"<wording>\" (straight double quotes); only claim lines and the "
                     "template's opening sentence go there")
            continue
        points += 1
        product, wording = cm.group("product").strip(), cm.group("wording")
        key = (needle(product), needle(wording))
        if key in approved:
            rep.ok(f"line {n}: approved for {product}")
        elif key in not_cleared:
            rep.fail(f"line {n}: \"{wording}\" is in section 7 for {product} but marked "
                     f"{not_cleared[key]}, not [owner]; the owner has not cleared it")
        elif any(w == key[1] for _, w in approved):
            rep.fail(f"line {n}: \"{wording}\" is approved for another product, not for "
                     f"{product or 'an unnamed product'}; claims never move between formulas")
        else:
            rep.fail(f"line {n}: \"{wording}\" is not an Approved [owner] line for "
                     f"{product or 'an unnamed product'} in programme section 7; take it out, or "
                     "list it in the notes as to be cleared by the owner")
    if points == 0:
        rep.fail("'What you can say' has no approved claim line")
    if points > limit:
        rep.fail(f"'What you can say' has {points} points; the limit is {limit} ({limit_src})")
    elif points:
        rep.ok(f"{points} of at most {limit} talking points ({limit_src})")
    if not_cleared:
        n = len(not_cleared)
        rep.note(f"{plural(n, 'line')} under section 7 Approved {'is' if n == 1 else 'are'} not "
                 "marked [owner], so not treated as cleared")

    # Forbidden phrases, outside the two claim sections.
    searched = unify("\n".join(s["text"] for t, s in sec.items()
                               if t in BRIEF_SECTIONS and t not in FORBIDDEN_SEARCH_SKIPS)
                     + "\n" + "\n".join(b["lines"][b["title_line"]:min(
                         s["start"] for s in sec.values())]))
    hits = [p for p in forbidden if needle(p) and needle(p) in searched]
    for p in hits:
        rep.fail(f"the forbidden phrase \"{p}\" from programme section 7 appears in the brief")
    if forbidden and not hits:
        rep.ok(f"none of {plural(len(forbidden), 'quoted forbidden phrase')} appears")
    if described:
        rep.unchecked(f"{plural(described, 'Forbidden line')} in section 7 "
                      f"{'describes' if described == 1 else 'describe'} a kind of claim without a "
                      "quoted phrase; no string can find those, so the programme lead reads for them")

    # Code, link and discount.
    cta = sec["Your code and link"]["text"]
    code, link = row["code"], row["affiliate_link"]
    if code:
        if re.search(r"(?<![A-Z0-9])" + re.escape(code) + r"(?![A-Z0-9])", cta):
            rep.ok(f"code {code} matches the roster")
        else:
            rep.fail(f"the code {code} from the roster is not in 'Your code and link'")
    elif MISSING_MARK.lower() in cta.lower():
        rep.note(f"the roster has no code for {ref} yet; the brief marks it missing "
                 "(affiliate-onboarding issues it)")
    else:
        rep.fail(f"the roster has no code for {ref}, yet 'Your code and link' states one without "
                 "a [MISSING: ...] marker")
    if link:
        if link in cta:
            rep.ok("tracked link matches the roster")
        else:
            rep.fail(f"the tracked link from the roster is not in 'Your code and link': {link}")
    elif MISSING_MARK.lower() in cta.lower():
        rep.note(f"the roster has no tracked link for {ref} yet; the brief marks it missing")
    else:
        rep.fail(f"the roster has no tracked link for {ref}, yet 'Your code and link' states one "
                 "without a [MISSING: ...] marker")
    whole = "\n".join(b["lines"])
    for other in roster:
        if other["creator_ref"] == ref:
            continue
        m_other = MERGED_INTO.search(other["notes"])
        if other["status"] == "ended" and m_other and m_other.group(1) == ref:
            continue
        oc, ol = other["code"], other["affiliate_link"]
        if oc and re.search(r"(?<![A-Z0-9])" + re.escape(oc) + r"(?![A-Z0-9])", whole):
            rep.fail(f"the brief carries {other['creator_ref']}'s code {oc}")
        if ol and ol in whole and not (link and ol in link):
            rep.fail(f"the brief carries {other['creator_ref']}'s tracked link")
    discount, discount_src = None, ""
    if code:
        for plan_path in sorted(glob.glob(os.path.join(workspace, "codes", "code-plan-*.csv"))):
            for r in read_csv(plan_path, CODE_PLAN_HEADER, "The code plan"):
                if (r["creator_ref"] == ref and r["code"] == code
                        and r["status"] in LIVE_CODE_STATUSES and r["discount_value"]):
                    discount = r["discount_value"]
                    discount_src = os.path.relpath(plan_path, workspace)
    if discount is None:
        value = section4_discount(need(prog, 4, "the customer discount"))
        if value is None:
            raise Bad("programme section 4 has no customer-facing discount and no code plan "
                      "row gives one; the owner sets it with program-setup.")
        found = numbers(value)
        if found:
            discount, discount_src = f"{found[0]:g}", "programme section 4"
        else:
            rep.unchecked(f"the discount: programme section 4 reads '{value}', with no number "
                          "to compare")
    if discount is not None:
        if has_number(cta, discount):
            rep.ok(f"discount {discount} matches {discount_src}")
        elif not code and MISSING_MARK.lower() in cta.lower():
            rep.note(f"discount {discount} ({discount_src}) not yet stated beside the missing code")
        else:
            rep.fail(f"'Your code and link' does not state the discount {discount} from "
                     f"{discount_src}")

    # Pay, as agreed in the roster.
    pay = sec["Pay"]["text"]
    pay_missing = MISSING_MARK.lower() in pay.lower()
    model = row["compensation_model"]
    if not agreed:
        if not pay_missing:
            rep.fail("'Pay' states terms before they are agreed; write [MISSING: pay as agreed - "
                     "from the signed agreement]")
    elif not model:
        if not pay_missing:
            rep.fail(f"the roster has no compensation_model for {ref}, yet 'Pay' carries no "
                     "[MISSING: ...] marker")
    else:
        if model in ("cpa", "hybrid"):
            rate = row["commission_rate_pct"]
            if not rate:
                if not pay_missing:
                    rep.fail(f"the roster has no commission rate for {ref}, yet 'Pay' carries no "
                             "[MISSING: ...] marker")
            elif has_number(pay, rate):
                rep.ok(f"commission rate {rate} percent matches the roster")
            else:
                rep.fail(f"'Pay' does not state the roster's commission rate, {rate} percent")
        if model in ("flat", "hybrid"):
            fee = row["flat_fee"]
            if not fee:
                if not pay_missing:
                    rep.fail(f"the roster has no flat fee for {ref}, yet 'Pay' carries no "
                             "[MISSING: ...] marker")
            elif has_number(pay, fee):
                rep.ok(f"flat fee {fee} matches the roster")
            else:
                rep.fail(f"'Pay' does not state the roster's flat fee, {fee}")
        if model in ("gift", "none"):
            rep.unchecked(f"pay: the roster model is {model}; there is no rate or fee to compare")
        if model in ("cpa", "hybrid"):
            hold = labelled_value(need(prog, 5, "the holdback"), HOLDBACK_LABEL)
            hold_n = numbers(hold) if hold else []
            if not hold_n:
                rep.unchecked("the holdback in 'Pay': programme section 5 gives no number yet")
            elif has_number(pay, hold_n[0]):
                rep.ok(f"holdback, {hold_n[0]:g} days, matches programme section 5")
            else:
                rep.fail(f"'Pay' does not state the holdback from programme section 5, "
                         f"{hold_n[0]:g} days")
            payout = labelled_value(need(prog, 6, "the minimum payout"), PAYOUT_LABEL)
            if not payout:
                rep.unchecked("the minimum payout in 'Pay': programme section 6 gives no value yet")
            elif NO_MINIMUM_RE.search(payout):
                if "no minimum" in unify(pay):
                    rep.ok("no minimum payout, as programme section 6 says")
                else:
                    rep.fail("'Pay' does not say 'no minimum', as programme section 6 does")
            elif MINIMUM_RE.search(payout):
                amount = MINIMUM_RE.search(payout).group(1).replace(",", "")
                if has_number(pay, amount):
                    rep.ok(f"minimum payout {amount} matches programme section 6")
                else:
                    rep.fail(f"'Pay' does not state the minimum payout from programme section 6, "
                             f"{amount}")
            else:
                rep.fail(f"programme section 6 writes the payout line as '{payout[:60]}', without "
                         "'minimum <amount>' or 'no minimum'; program-setup rewrites it")
            rep.unchecked("the commission basis and the payout schedule wording in 'Pay' against "
                          "programme sections 4 and 6: the programme lead reads them")

    # Using your content: rights and exclusivity from the agreement.
    use = sec["Using your content"]["text"]
    use_missing = MISSING_MARK.lower() in use.lower()
    if not agreed or not row["agreement_file"]:
        if not use_missing:
            rep.fail("'Using your content' states rights, but the roster names no agreed "
                     "agreement; write [MISSING: usage rights and exclusivity - from the signed "
                     "agreement]")
    else:
        if not os.path.isfile(os.path.join(workspace, row["agreement_file"])):
            rep.note(f"the roster's agreement_file {row['agreement_file']} was not found")
        from_posting = None
        for entry in row["notes"].split(";"):
            m_fp = FROM_POSTING_RE.search(entry)
            if m_fp:
                from_posting = int(m_fp.group(1))  # the latest dated entry wins
        for col, what in (("usage_rights_until", "usage-rights end date"),
                          ("exclusivity_until", "exclusivity end date")):
            if col == "usage_rights_until" and from_posting is not None:
                wording = FROM_POSTING_WORDING.format(n=from_posting)
                pub_path = os.path.join(workspace, "data", "publications.csv")
                pub_dates = []
                if os.path.isfile(pub_path):
                    pub_dates = [r["rights_until"] for r in
                                 read_csv(pub_path, PUBLICATIONS_HEADER, "The publications file")
                                 if r["creator_ref"] == ref and r["campaign_slug"] == slug
                                 and r["rights_until"]]
                hit = next((d for d in pub_dates if d in use), None)
                if wording in unify(use):
                    rep.ok(f"usage window runs from posting ({from_posting} months, roster note "
                           "rights from posting), stated as a duration from the day they post")
                elif hit:
                    rep.ok(f"usage window runs from posting; the brief states the live post's "
                           f"computed date {hit} (data/publications.csv)")
                else:
                    dates = ", ".join(pub_dates) or "none recorded yet"
                    rep.fail(f"the roster notes say rights from posting: {from_posting} months, so "
                             "'Using your content' must say \"Reuse: "
                             f"{from_posting} months from the day you post, ...\" or, once the post "
                             f"is live, its rights_until in data/publications.csv ({dates})")
                continue
            if row[col]:
                if row[col] in use:
                    rep.ok(f"{what} {row[col]} matches the roster")
                else:
                    rep.fail(f"'Using your content' does not state the roster's {what}, "
                             f"{row[col]}")
            elif NONE_PHRASES[col] in unify(use):
                rep.ok(f"no {what} on the roster beside an agreement: none granted, and the "
                       "brief says so")
            else:
                rep.fail(f"the roster has no {what} beside agreement {row['agreement_file']}, "
                         "which means none was granted (schemas.md section 4); 'Using your "
                         f"content' must say \"{NONE_PHRASES[col].capitalize()} in your "
                         "agreement.\"")
        rep.unchecked("the channels and paid-reuse terms against the agreement file: the "
                      "programme lead reads them")

    # Terms the programme fixes for every creator: sections 8 and 11.
    for sec_no, label, title, what in TERM_LINES:
        value = labelled_value(need(prog, sec_no, what), label)
        found = numbers(value) if value else []
        if value is None:
            rep.unchecked(f"{what}: programme section {sec_no} has no '{label}' line "
                          "(template 0.1.2 adds it)")
        elif not found:
            rep.unchecked(f"{what}: programme section {sec_no} gives no number yet")
        elif has_number(sec[title]["text"], found[0]):
            rep.ok(f"{what}, {found[0]:g} days, matches programme section {sec_no}")
        else:
            rep.fail(f"'{title}' does not state {what} from programme section {sec_no}, "
                     f"{found[0]:g} days")

    # Deliverables carry dates.
    if ISO_DATE.search(sec["What we need from you"]["text"]):
        rep.ok("deliverables carry dates")
    else:
        rep.fail("'What we need from you' has no date (YYYY-MM-DD)")

    # Gaps, pending points, dollars.
    for i, line in enumerate(b["lines"][1:b["lead"]["start"]], 2):
        if MISSING_MARK.lower() in line.lower():
            rep.gap(f"line {i}: {line.strip()}")
        if PENDING_MARK in line.lower():
            rep.fail(f"line {i}: a point waiting for the owner is in the creator's text; move it "
                     "to the programme lead's notes")
    pending = []
    for line in b["lead"]["body"]:
        if PENDING_MARK not in line.lower():
            continue
        m = re.match(r"^\s*(?:[-*]\s+)?to be cleared by the owner:\s*(.*)$", line, re.IGNORECASE)
        if m and needle(m.group(1)) in ("", "none"):
            continue
        pending.append(line)
    if pending:
        n = len(pending)
        rep.note(f"{plural(n, 'point')} in the programme lead's notes {'waits' if n == 1 else 'wait'} "
                 "for the owner and stays out of the creator's text")
    for i, line in enumerate(b["lines"], 1):
        if DOLLAR_DIGIT.search(line):
            rep.fail(f"line {i} has a dollar sign before a digit; write USD and the amount")

    # The status line may not claim more than the checks found.
    if b["lines"][0].startswith("Status: READY") and (rep.problems or rep.gaps):
        rep.fail("the first line says ready, but the checks above did not pass")
    return rep, b


def main(argv):
    ap = argparse.ArgumentParser(
        description="Check a creator brief against the roster and the programme file. "
                    "Reads only; writes, sends and fetches nothing.")
    ap.add_argument("workspace", help="the workspace folder (holds program/ and data/)")
    ap.add_argument("briefs", nargs="+", help="one or more briefs, campaigns/<slug>/briefs/<ref>.md")
    ap.add_argument("--cohort", action="store_true",
                    help="also check that the briefs share their common sections word for word")
    ap.add_argument("--today", help="date for the status line, YYYY-MM-DD (default: today, UTC)")
    args = ap.parse_args(argv)

    today = args.today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    ws = args.workspace
    try:
        if args.today:
            datetime.date.fromisoformat(args.today)
        prog_text = read_text(os.path.join(ws, "program", "program.md"), "The programme file",
                              "run program-setup with the owner first.")
        prog = programme_sections(prog_text)
        roster = read_csv(os.path.join(ws, "data", "creators.csv"), CREATORS_HEADER,
                          "The roster")
    except (Bad, ValueError) as exc:
        print(f"COULD NOT RUN: {exc}")
        return 1
    print(f"read: program/program.md (sections {', '.join(str(n) for n in sorted(prog))}); "
          f"data/creators.csv ({plural(len(roster), 'row')})")

    worst, parsed = 0, []
    for brief in args.briefs:
        path = brief if os.path.isfile(brief) else os.path.join(ws, brief)
        print(f"\n== {brief}")
        try:
            rep, b = check_one(ws, path, prog, roster, today)
        except Bad as exc:
            print(f"COULD NOT CHECK: {exc}")
            print("Result: bad input (exit 1); nothing in this brief was judged.")
            worst = 1
            continue
        for kind, msg in rep.rows:
            print(f"{kind:<12} {msg}")
        first, last = b["title_line"] + 1, b["lead"]["start"]
        print(f"Send lines {first} to {last}: from the title to the line before the programme "
              "lead's notes.")
        print("First line should read:")
        print(rep.status_line(today))
        code = 2 if (rep.problems or rep.gaps) else 0
        print(f"Result: {'not ready' if code else 'ready'} (exit {code})")
        if code and worst == 0:
            worst = 2
        parsed.append(b)

    if args.cohort:
        print("\n== cohort")
        if len(parsed) < 2:
            print("COULD NOT CHECK: a cohort check needs at least two briefs that parsed.")
            return 1
        drift = 0
        for title in COHORT_SHARED:
            texts = {unify(b["sections"][title]["text"]) for b in parsed}
            if len(texts) > 1:
                drift += 1
                print(f"FAIL         cohort briefs differ in '{title}'")
        if drift:
            print(f"Result: cohort not consistent, {plural(drift, 'section')} differ (exit 2)")
            if worst == 0:
                worst = 2
        else:
            print(f"PASS         {len(parsed)} briefs share every common section")
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
