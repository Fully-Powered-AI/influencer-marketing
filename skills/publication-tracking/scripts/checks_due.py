#!/usr/bin/env python3
"""Record live creator posts in data/publications.csv and list what is due.

Part of the publication-tracking skill (consumer-brand creator programme, pack version 0.1.0, 2026-10-20).
Standard library only; no network. Run with python3 -I.

Three modes, the workspace path always first:

  checks_due.py WORKSPACE [--as-of YYYY-MM-DD]
      The due list: day 1, 7 and 30 checks due or overdue, open live-check issues and fix requests,
      removed or edited posts not yet dealt with, flat and hybrid deals with no fee milestone noted,
      live-check lines not recorded, rights windows ending soon.

  checks_due.py WORKSPACE add --campaign SLUG --creator REF --platform P --url URL --posted-at TIME
                 --format F --approval ID|none --role ROLE [live-check options] [--on DATE] [--note TEXT]
      Appends one row with a new publication_id, rights_until copied from the roster, and the live check
      as the person reported it; moves the pipeline row for the campaign and creator to stage live.

  checks_due.py WORKSPACE record PUBLICATION_ID --role ROLE [options] [--on DATE]
      Records a day 1, 7 or 30 check, a re-run of the live check, a fix request, an owner's waiver,
      a removal review, a fee milestone, a rights window re-copied from the roster, a late approval link
      or a note. Every record is a dated entry appended to the row's notes; nothing earlier is removed.

Exit codes
  0  done. For the due list: nothing overdue, nothing to act on, every live-check line recorded.
  1  bad input: a missing file or programme section, a header that differs from the schema, a value
     outside the allowed set. One sentence says what to fix. Nothing is written.
  2  due list only: something needs a person (overdue, act now, not checked), or the run was partial
     because a row could not be read. The first line says which.

Where the numbers live: CHECK_DAYS, GRACE_DAYS and RIGHTS_WARNING_DAYS below. Change them here only.
"""
import argparse
import csv
import os
import re
import secrets
import shlex
import sys
import tempfile
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "references"))
from brand_context import audience_rule, unrestricted, section_lines

# ---------------------------------------------------------------------------------------------
# Numbers. Each names its origin.
# The check cadence, in days after posting. Set by the pack's design brief (2026-10-20). No rule
# fixes a monitoring frequency: the pack's references/platform-and-compliance-notes.md section 1
# records that the FTC FAQ specifies none.
CHECK_DAYS = (1, 7, 30)
# Days after a check's due date before it counts as overdue. Build default (2026-10-20), owner to confirm.
GRACE_DAYS = {1: 1, 7: 2, 30: 3}
# A rights window ending within this many days of the as-of date is listed. From the pack's design
# brief (2026-10-20); content-reuse uses the same window for "expiring".
RIGHTS_WARNING_DAYS = 30

# ---------------------------------------------------------------------------------------------
# Shapes, from the pack's references/schemas.md sections 2, 4, 5 and 6 (2026-10-20).
PUB_HEADER = ["publication_id", "campaign_slug", "creator_ref", "platform", "post_url", "posted_at",
              "format", "disclosure_seen", "disclosure_form", "code_in_post", "link_in_post",
              "approval_id", "check_day1", "check_day7", "check_day30", "rights_until", "notes"]
ROSTER_HEADER = ["creator_ref", "display_name", "primary_platform", "primary_handle", "profile_url",
                 "other_platforms", "tier", "followers_primary", "followers_as_of", "engagement_rate_pct",
                 "engagement_as_of", "niche_tags", "audience_fit_score", "brand_safety_flag",
                 "contact_path", "contact_email", "status", "compensation_model", "commission_rate_pct",
                 "flat_fee", "code", "affiliate_link", "rail", "agreement_date", "agreement_file",
                 "usage_rights_until", "exclusivity_until", "first_campaign", "last_activity", "notes"]
PIPELINE_HEADER = ["campaign_slug", "creator_ref", "stage", "stage_date", "next_action",
                   "next_action_date", "owner_role", "last_message_date", "offer_summary", "notes"]
PLATFORMS = ["instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast", "newsletter",
             "bluesky", "threads", "other"]
FORMATS = ["video", "reel", "story", "post", "thread", "newsletter", "podcast", "live", "other"]
DISCLOSURE_SEEN = ["yes", "no", "partial"]
FORMS = ["caption", "spoken", "on_screen", "platform_tool"]
CHECK_VALUES = ["live", "removed", "edited", "not_checked"]
AGE_VALUES = ["confirmed", "not-set", "not-offered", "not-required", "unchecked"]
MATCH_VALUES = {"yes": "match", "no": "differs", "unchecked": "unchecked"}
ISSUES = ["disclosure", "code", "link", "age", "content", "approval", "platform"]
LIVE_ISSUES = ["disclosure", "code", "link", "age", "content"]
FEE_MODELS = ("flat", "hybrid")

# The floor a "yes" disclosure must meet, by format. Source: the pack's
# references/platform-and-compliance-notes.md section 1 (FTC "Disclosures 101", read 2026-10-20):
# video disclosures belong in the video, audible and on screen; on stories and images the disclosure is
# superimposed. Podcast audio-only is the build's reading of "the audible portion". Programme section 8
# may require more (for example the platform tool); that part is the person's judgment, not checked here.
REQUIRED_ALL = {"video": {"spoken", "on_screen"}, "reel": {"spoken", "on_screen"},
                "live": {"spoken", "on_screen"}, "story": {"on_screen"}, "podcast": {"spoken"}}
REQUIRED_ANY = {"post": {"caption", "on_screen"}, "thread": {"caption"}, "newsletter": {"caption"},
                "other": set(FORMS)}

# Which row of the programme's section 3 table governs each roster platform value. bluesky and threads
# have no row in the template's table, so they read as "not in section 3".
SECTION3_ROW = {"instagram": "instagram", "tiktok": "tiktok", "youtube": "youtube", "x": "x",
                "onlyfans": "onlyfans", "reddit": "reddit", "podcast": "podcasts and newsletters",
                "newsletter": "podcasts and newsletters", "other": "other"}

# creator-roster's script, as the sibling skill folder of this one's real location (symlinks resolved).
ROSTER_SCRIPT = Path(__file__).resolve().parents[2] / "creator-roster" / "scripts" / "roster.py"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:\d{2})$")
REF_RE = re.compile(r"^c-[a-z0-9]{6}$")
PUB_RE = re.compile(r"^p-[a-z0-9]{6}$")
SLUG_RE = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
APPROVAL_RE = re.compile(r"^(\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*)--(c-[a-z0-9]{6})--([1-9][0-9]*)$")


class BadInput(Exception):
    pass


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error; the contract keeps 2 for 'needs a person' or partial, so 1."""
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"error: {message}. Nothing was written.", file=sys.stderr)
        sys.exit(1)


def fail(msg):
    raise BadInput(msg)


# --------------------------------------------------------------------------------------------- dates
def parse_date(s, what):
    s = (s or "").strip()
    if not DATE_RE.match(s):
        fail(f"{what} must be a date written YYYY-MM-DD; got '{s}'.")
    try:
        return date.fromisoformat(s)
    except ValueError:
        fail(f"{what} is not a real calendar date: '{s}'.")


def parse_time(s, what):
    s = (s or "").strip()
    m = TIME_RE.match(s)
    if not m:
        fail(f"{what} must be a time with its zone, for example 2026-11-03T18:30Z or "
             f"2026-11-03T10:30-08:00; got '{s}'. If only the date is known, ask the creator or read the post's own timestamp.")
    d, hh, mm, ss, zone = m.groups()
    try:
        offset = timezone.utc if zone == "Z" else timezone(
            (1 if zone[0] == "+" else -1) * timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6])))
        dt = datetime.fromisoformat(f"{d}T{hh}:{mm}:{ss or '00'}").replace(tzinfo=offset)
    except ValueError:
        fail(f"{what} is not a real time: '{s}'.")
    return dt.astimezone(timezone.utc)


def fmt_time(dt):
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def today_utc():
    return datetime.now(timezone.utc).date()


# --------------------------------------------------------------------------------------------- files
def check_header(got, want, path):
    if got == want:
        return
    missing = [c for c in want if c not in got]
    extra = [c for c in got if c not in want]
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if extra:
            parts.append("unexpected " + ", ".join(extra))
        fail(f"{path} header differs from the schema ({'; '.join(parts)}); fix the header row "
             f"(creator-roster check names the shape) and run again.")
    fail(f"{path} has the right columns in the wrong order; the order is: {', '.join(want)}.")


def read_csv(path, header, label, strict):
    """Read a whole CSV. strict: any malformed row stops the run (used before a write)."""
    if not path.exists():
        fail(f"{label} not found at {path}; {'run program-setup to create the workspace files' if label != 'data/pipeline.csv' else 'it is optional'}.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            got = [c.strip() for c in next(reader)]
        except StopIteration:
            fail(f"{path} is empty; it needs at least the header row from the schema.")
        check_header(got, header, path)
        rows, bad = [], []
        for lineno, rec in enumerate(reader, start=2):
            if not any(c.strip() for c in rec):
                continue
            if len(rec) != len(header):
                if strict:
                    fail(f"{path} line {lineno} has {len(rec)} cells, not {len(header)}; fix that line "
                         f"(an unquoted comma is the usual cause) before recording anything.")
                bad.append((lineno, f"{len(rec)} cells, not {len(header)}"))
                continue
            rows.append(dict(zip(header, rec)))
    return rows, bad


def write_csv(path, header, rows):
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in header})
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------------------------- programme
def read_programme(ws):
    p = ws / "program" / "program.md"
    if not p.exists():
        fail(f"no programme file at {p}; run program-setup first.")
    return p.read_text(encoding="utf-8")


def section(text, n):
    m = re.search(rf"^##\s+{n}\.[^\n]*\n(.*?)(?=^##\s+\d+\.|\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def table_rows(body):
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [re.sub(r"\[[^\]]*\]", "", c).strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def platform_rules(text):
    body = section(text, 3)
    if body is None:
        fail("the programme file has no section 3 (Platforms); run program-setup to restore the heading "
             "'## 3. Platforms' and its table.")
    rules = {}
    for cells in table_rows(body):
        if len(cells) >= 2 and cells[0]:
            rules[cells[0].lower()] = cells[1]
    return rules


def platform_rule(rules, platform):
    key = SECTION3_ROW.get(platform)
    if key is None:
        return ("unset", f"{platform} has no row in programme section 3")
    for name, value in rules.items():
        if name == key or name.startswith(key + " ") or name.startswith(key + "("):
            v = value.strip()
            lv = v.lower()
            if lv == "yes":
                return ("allowed", v)
            if lv == "no":
                return ("barred", v)
            if lv.startswith("with conditions"):
                return ("conditional", v)
            return ("unset", f"section 3 gives organic creator posts on {platform} as '{v or 'blank'}'")
    return ("unset", f"{platform} has no row in programme section 3")


FIX_WINDOW_LINE = "Time a creator has to correct a live post after being asked, in days:"   # section 8
MIN_LIVE_LINE = "Minimum time a post stays live, in days:"                                  # section 11


def programme_line(text, n, prefix):
    """The value written after a template line, marks removed: None if the line is absent, '' if it is
    blank or only [open]."""
    body = section(text, n) or ""
    for line in body.splitlines():
        t = line.strip().lstrip("-").strip()
        if t.startswith(prefix):
            value = t[len(prefix):]
            return "" if "[open]" in value else re.sub(r"\[[^\]]*\]", "", value).strip()
    return None


def programme_days(text, n, prefix):
    """A whole number of days from a programme line: (days or None, what the line says)."""
    v = programme_line(text, n, prefix)
    if not v:
        return None, "absent" if v is None else "blank or [open]"
    m = re.match(r"^(\d+)(?:\s*days?)?$", v)
    if not m:
        return None, f"unreadable ('{v}')"
    return int(m.group(1)), f"{m.group(1)} days"


def programme_roles(text):
    body = section(text, 10)
    if body is None:
        fail("the programme file has no section 10 (Roles and approvals); run program-setup to restore it.")
    roles = [c[0].lower() for c in table_rows(body) if c and c[0]]
    if not roles:
        fail("programme section 10 lists no roles; run program-setup to fill the roles table.")
    return roles


def add_months(d, months):
    """The same day of the month, months later; the month's last day when that day does not exist.
    Build rule (2026-10-20) for 'rights from posting: <n> months'; the agreement's wording governs."""
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(d.day, last))


def rights_from_posting(rr):
    """Months from the roster note 'rights from posting: <n> months' (schemas.md section 4), latest wins."""
    if rr is None:
        return None
    found = re.findall(r"rights from posting:\s*(\d+)\s*months?\b", rr["notes"], re.I)
    return int(found[-1]) if found else None


def roster_rights_for(rr, posted_d):
    """(rights_until for a post, how it was set). schemas.md section 4: when the roster carries
    'rights from posting: <n> months', every post is dated from its own posting date plus the window,
    whatever the roster's date says (the roster carries the latest of them); otherwise the roster's
    date is copied; otherwise ('', reason)."""
    given = rr["usage_rights_until"].strip()
    months = rights_from_posting(rr)
    if months is not None:
        d = add_months(posted_d, months)
        return d.isoformat(), (f"posted {posted_d.isoformat()} + {months} months, from the roster note "
                               f"'rights from posting: {months} months' (same day of the month, or its last day)")
    if given:
        return given, "copied from the roster"
    if rr["agreement_file"].strip():
        return "", "none on the roster with an agreement on file (none granted)"
    return "", "none on the roster (unknown)"


def roster_update_line(ws, rr, value, posted_d, pid, role):
    """For a from-posting window: the roster's date carries the latest post's date, so the update is
    printed only when this post's date is later than the roster's current one."""
    months = rights_from_posting(rr)
    if months is None or not value:
        return None
    cur = rr["usage_rights_until"].strip()
    if cur and DATE_RE.match(cur) and cur >= value:
        return (f"Roster: usage_rights_until {cur} is already the latest from-posting date "
                f"(this post's {value} is not later); no roster update.")
    return ("Roster: the roster carries the latest from-posting date"
            + (f" ({cur} now)" if cur else " (empty now)")
            + "; the programme lead sets it with "
            + roster_update_command(ws, rr, value, posted_d, pid, months, role))


def roster_update_command(ws, rr, value, posted_d, pid, months, role):
    """The creator-roster update line, runnable from any folder, dated with the posting date."""
    note = f"rights from posting: {months} months, from {pid} posted {posted_d.isoformat()}"
    if not ROSTER_SCRIPT.is_file():
        return (f"creator-roster (its script is not installed beside this skill): set usage_rights_until={value} "
                f"for {rr['creator_ref']}, dated {posted_d.isoformat()}, note \"{note}\"")
    return (f"python3 -I {shlex.quote(str(ROSTER_SCRIPT))} {shlex.quote(str(Path(ws).resolve()))} update "
            f"{rr['creator_ref']} usage_rights_until={value} --note {shlex.quote(note)} "
            f"--role {shlex.quote(role)} --date {posted_d.isoformat()}")


def merged_into(rr):
    """The kept creator_ref when this roster row is a duplicate retired by a merge, else None."""
    if rr is None or rr["status"] != "ended":
        return None
    m = re.search(r"merged into (c-[a-z0-9]{6})", rr["notes"])
    return m.group(1) if m else None


def check_role(role, roles):
    r = " ".join((role or "").lower().split())
    if r not in roles:
        fail(f"--role '{role}' is not a role in programme section 10 ({', '.join(roles)}); "
             f"give the role, never a person's name.")
    return r


# --------------------------------------------------------------------------------------------- notes
def clean_text(s):
    return re.sub(r"\s+", " ", (s or "").replace(";", ",")).strip()


def entry(on, token, args, role, text=None):
    s = f"{on.isoformat()} {token}"
    if args:
        s += " " + " ".join(args)
    s += f" by {role}"
    t = clean_text(text)
    if t:
        s += f": {t}"
    return s


def append_note(row, e):
    cur = (row.get("notes") or "").strip().rstrip(";")
    row["notes"] = f"{cur};{e}" if cur else e


def parse_notes(cell):
    out = []
    for i, raw in enumerate((cell or "").split(";")):
        raw = raw.strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2}) ([a-z][a-z0-9-]*)(.*)$", raw)
        if not m:
            continue
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        rest, text = m.group(3).strip(), ""
        if ": " in rest:
            rest, text = rest.split(": ", 1)
        role = ""
        bm = re.search(r"(?:^|\s)by (.+)$", rest)
        if bm:
            role = bm.group(1).strip()
            rest = rest[:bm.start()].strip()
        args = rest.split() if rest else []
        kv = dict(a.split("=", 1) for a in args if "=" in a)
        out.append({"date": d, "token": m.group(2), "args": [a for a in args if "=" not in a],
                    "kv": kv, "role": role, "text": text, "i": i})
    out.sort(key=lambda e: (e["date"], e["i"]))
    return out


def latest(entries, token, pred=None):
    found = None
    for e in entries:
        if e["token"] == token and (pred is None or pred(e)):
            found = e
    return found


def lc_value(entries, key):
    """The latest recorded value of one live-check line; a line not looked at is 'unchecked'."""
    v = "unchecked"
    for e in entries:
        if e["token"] == "live-check" and e["kv"].get(key, "unchecked") != "unchecked":
            v = e["kv"][key]
    return v


# --------------------------------------------------------------------------------------------- comparisons
def norm_link(s):
    s = (s or "").strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I):
        s = "https://" + s
    p = urllib.parse.urlsplit(s)
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return (host, p.path.rstrip("/"), p.query)


def norm_post_url(s):
    # The query is kept: some platforms identify the post in it (a video id after watch?v=).
    return norm_link(s)


def code_result(in_post, absent, given):
    if not given:
        return "none-issued"
    if in_post:
        return "match" if in_post.strip() == given.strip() else "differs"
    return "absent" if absent else "unchecked"


def link_result(in_post, absent, given):
    if not given:
        return "none-issued"
    if in_post:
        return "match" if norm_link(in_post) == norm_link(given) else "differs"
    return "absent" if absent else "unchecked"


def issued(entries, rr, key):
    """The code or link issued for this post: as copied into the 'added' entry, else the roster's now."""
    added = latest(entries, "added")
    if added is not None and f"issued-{key}" in added["kv"]:
        return added["kv"][f"issued-{key}"]
    if rr is None:
        return None
    return rr["code"] if key == "code" else rr["affiliate_link"]


def issue_states(row, rr, entries, age_rule=None):
    """State of each live-check issue: ok, open, unchecked or n/a, with a detail line.

    Code and link use the result recorded at the live check (compared then with what was issued for
    this post), so a later change to the roster does not re-judge an old post."""
    st = {}
    ds = row["disclosure_seen"]
    if ds == "yes":
        st["disclosure"] = ("ok", "")
    elif ds in ("no", "partial"):
        forms = row["disclosure_form"] or "none"
        st["disclosure"] = ("open", f"disclosure {ds} (forms seen: {forms})")
    else:
        st["disclosure"] = ("unchecked", "disclosure")
    for issue, col, cmp in (("code", "code_in_post", code_result), ("link", "link_in_post", link_result)):
        given = issued(entries, rr, issue)
        res = "none-issued" if given == "" else lc_value(entries, issue)
        if res == "unchecked" and row[col]:
            res = cmp(row[col], False, given) if given is not None else "unchecked"
        if res == "none-issued":
            st[issue] = ("n/a", "")
        elif res == "match":
            st[issue] = ("ok", "")
        elif res == "differs":
            st[issue] = ("open", f"{issue} in post '{row[col]}' differs from the one issued '{given or 'unknown'}'")
        elif res == "absent":
            st[issue] = ("open", f"the issued {issue} '{given or 'unknown'}' is not in the post")
        else:
            st[issue] = ("unchecked", issue)
    age = lc_value(entries, "age")
    if age_rule is None:
        st["age"] = ("unchecked", "programme section 9 audience rule is missing, open or duplicated")
    elif unrestricted(age_rule):
        st["age"] = ("n/a", "programme section 9: " + age_rule)
    elif age == "confirmed":
        st["age"] = ("ok", "")
    elif age in ("not-set", "not-required", "not-offered"):
        st["age"] = ("open", "audience evidence does not meet programme section 9: " + age_rule)
    else:
        st["age"] = ("unchecked", "age setting")
    content = lc_value(entries, "approval")
    if not row["approval_id"]:
        st["content"] = ("n/a", "")  # nothing to compare against; the approval issue covers it
    elif content == "match":
        st["content"] = ("ok", "")
    elif content == "differs":
        st["content"] = ("open", f"the live post differs from approval {row['approval_id'] or '(none)'}")
    else:
        st["content"] = ("unchecked", "match to approval")
    return st


ACT_ROUTE = {
    "disclosure": "draft the fix ask from assets/fix-request-template.md, give it to the programme lead to send, then record --fix-requested disclosure (the due date comes from programme section 8)",
    "code": "draft the fix ask from assets/fix-request-template.md, then record --fix-requested code (due date from programme section 8)",
    "link": "draft the fix ask from assets/fix-request-template.md, then record --fix-requested link (due date from programme section 8)",
    "age": "the programme lead decides (on some platforms the setting cannot be added after posting, references/live-check.md); a fix ask, if any, is recorded with --fix-requested age --due DATE",
    "content": "send the live version to content-approval as a new attempt and tell the programme lead",
    "approval": "send the live post to content-approval for a review after the fact and tell the programme lead",
    "platform": "refer to the programme lead and the owner; only the owner can waive it",
}


# --------------------------------------------------------------------------------------------- evaluation
def reached_pairs(pubs):
    """(campaign_slug, creator_ref) pairs where some post carries a fee milestone reached."""
    return {(r["campaign_slug"], r["creator_ref"]) for r in pubs
            if latest(parse_notes(r["notes"]), "fee", lambda e: e["args"][:2] == ["milestone", "reached"])}


def evaluate(row, rr, rule, as_of, reached=frozenset(), min_live=None, age_rule=None):
    """Everything the due list says about one row, as of a date."""
    out = {"overdue": [], "act": [], "unchecked": [], "coming": [], "ended": False,
           "rights_unknown": False, "rights_none": False, "waived": 0, "skip": None, "removed": False}
    for col, allowed in (("format", FORMATS), ("check_day1", CHECK_VALUES + [""]),
                         ("check_day7", CHECK_VALUES + [""]), ("check_day30", CHECK_VALUES + [""]),
                         ("disclosure_seen", DISCLOSURE_SEEN + [""])):
        if row[col] not in allowed:
            out["skip"] = f"{col} is '{row[col]}', not one of {', '.join(a for a in allowed if a)}"
            return out
    try:
        posted = parse_time(row["posted_at"], "posted_at").date()
        rights = parse_date(row["rights_until"], "rights_until") if row["rights_until"].strip() else None
    except BadInput as e:
        out["skip"] = str(e)
        return out
    if posted > as_of:
        out["skip"] = f"posted {posted.isoformat()}, after the as-of date"
        return out
    entries = parse_notes(row["notes"])

    # The day 1, 7 and 30 checks.
    state = None
    for n in CHECK_DAYS:
        v = row[f"check_day{n}"] or "not_checked"
        due = posted + timedelta(days=n)
        if v in ("live", "edited", "removed"):
            state = v
            ce = latest(entries, "check", lambda e: e["kv"].get(f"day{n}") == v)
            seen_on = ce["date"] if ce else due
            if v == "edited" and not latest(entries, "live-check", lambda e: e["date"] >= seen_on):
                out["act"].append(f"edited at the day {n} check on {seen_on.isoformat()}: re-run the live "
                                  f"check on the post as it now stands and record it")
            if v == "removed" and not latest(entries, "removal-reviewed", lambda e: e["date"] >= seen_on):
                lived = (seen_on - posted).days
                if min_live is None:
                    term = "programme section 11 sets no minimum time live"
                else:
                    term = (f"programme section 11 sets a minimum of {days_word(min_live)} live: seen removed "
                            f"{days_word(lived)} after posting, {'inside' if lived < min_live else 'past'} it "
                            f"(it may have come down earlier)")
                out["act"].append(f"removed at the day {n} check on {seen_on.isoformat()}; {term}: read the "
                                  f"campaign plan and the agreement, then record --removal-reviewed")
            continue
        if state == "removed":
            continue
        g = GRACE_DAYS[n]
        end = due + timedelta(days=g)
        working = f"(posted {posted.isoformat()} + {days_word(n)})"
        if as_of < due:
            continue
        if as_of <= end:
            out["act"].append(f"day {n} check due {due.isoformat()} {working}: open the post and record it; "
                              f"overdue after {end.isoformat()} (+{days_word(g)})")
        else:
            out["overdue"].append(f"day {n} check due {due.isoformat()} {working}, window closed "
                                  f"{end.isoformat()} (+{days_word(g)}), not recorded")
    out["removed"] = state == "removed"

    # Live-check issues, the approval link and the platform ruling. Not listed once the post is removed:
    # the removal review covers it.
    if not out["removed"]:
        st = issue_states(row, rr, entries, age_rule)
        if not row["approval_id"]:
            st["approval"] = ("open", "no approval on record")
        else:
            link_e = latest(entries, "approval") or latest(entries, "added")
            if link_e is not None and link_e["kv"].get("verdict") == "stop":
                st["approval"] = ("open", f"published under {row['approval_id']}, whose verdict is stop")
        kind, detail = rule
        if kind == "barred":
            st["platform"] = ("open", f"programme section 3 says organic creator posts on {row['platform']}: no")
        elif kind == "unset":
            st["platform"] = ("unchecked", f"platform ruling ({detail})")
        unchecked = []
        for issue in ISSUES:
            s, d = st.get(issue, ("ok", ""))
            if s == "unchecked":
                unchecked.append(d)
                continue
            if s != "open":
                continue
            if latest(entries, "waived", lambda e: e["args"][:1] == [issue]):
                out["waived"] += 1
                continue
            conf = latest(entries, "fix-confirmed", lambda e: e["args"][:1] == [issue])
            req = latest(entries, "fix-requested", lambda e: e["args"][:1] == [issue]
                         and (conf is None or e["date"] >= conf["date"]))
            if req:
                try:
                    fdue = parse_date(req["kv"].get("due", ""), "fix due date")
                except BadInput:
                    out["act"].append(f"{d}; the fix request of {req['date'].isoformat()} has no readable due date: record it again")
                    continue
                line = (f"{d}; fix asked {req['date'].isoformat()}, due {fdue.isoformat()}")
                if as_of > fdue:
                    out["overdue"].append(line + ", not confirmed by a re-check")
                else:
                    out["coming"].append(line + ", awaiting the creator")
            elif issue in ("disclosure", "code", "link", "age"):
                out["act"].append(f"{d}, no fix asked: {ACT_ROUTE[issue]}")
            else:
                out["act"].append(f"{d}: {ACT_ROUTE[issue]}")
        if unchecked:
            out["unchecked"].append("not recorded: " + ", ".join(unchecked))

    # Flat and hybrid deals: the publication receipt is the fee milestone.
    if rr is not None and rr["compensation_model"] in FEE_MODELS:
        fm = latest(entries, "fee", lambda e: e["args"][:1] == ["milestone"])
        if fm is None:
            out["act"].append(f"{rr['compensation_model']} deal, fee milestone not recorded: the programme lead "
                              f"confirms the receipt, then record --fee-milestone reached if this post completes "
                              f"the deliverable set, part if it is one post of several, or held with --note")
        elif fm["args"][1:2] == ["held"]:
            out["coming"].append(f"fee milestone held on {fm['date'].isoformat()}: {fm['text'] or 'no reason given'}")
        elif fm["args"][1:2] == ["part"] and (row["campaign_slug"], row["creator_ref"]) not in reached:
            out["coming"].append(f"fee milestone part on {fm['date'].isoformat()}; no post of this campaign "
                                 f"carries reached yet: record it on the post that completes the set")

    # Rights windows.
    roster_rights = rr["usage_rights_until"].strip() if rr is not None else ""
    from_posting = rights_from_posting(rr)
    settled = latest(entries, "rights-not-covered", lambda e: e["kv"].get("roster") == roster_rights)
    # Under a from-posting window each post keeps its own date and the roster carries the latest, so a
    # later roster date says nothing about this post.
    prompt_roster = bool(roster_rights) and settled is None and from_posting is None
    if rights is None:
        # schemas.md section 4: an empty rights date with an agreement on file means none was granted,
        # unless the roster carries 'rights from posting: <n> months'.
        if rr is not None and not roster_rights and from_posting is None and rr["agreement_file"].strip():
            out["rights_none"] = True
        else:
            out["rights_unknown"] = True
        if from_posting is not None:
            out["coming"].append(f"rights window not on the row; the roster says rights run {from_posting} months "
                                 f"from posting: record --rights-from-roster to date it from this post")
        elif prompt_roster:
            out["coming"].append(f"rights window not on the row; the roster now says {roster_rights}: if the "
                                 f"agreement covers this post, record --rights-from-roster; if not, "
                                 f"--rights-not-covered --note")
    else:
        days = (rights - as_of).days
        if days < 0:
            out["ended"] = True
            if prompt_roster and DATE_RE.match(roster_rights) and roster_rights > rights.isoformat():
                out["coming"].append(f"rights ended {rights.isoformat()} (rights_until on the row); the roster now "
                                     f"says {roster_rights}: if the extension covers this post, record "
                                     f"--rights-from-roster; if not, --rights-not-covered --note")
        elif days <= RIGHTS_WARNING_DAYS:
            line = (f"rights end {rights.isoformat()} (rights_until on the row), in {days_word(days)}: "
                    f"content-reuse to plan, partnership-agreement to extend")
            if prompt_roster and DATE_RE.match(roster_rights) and roster_rights > rights.isoformat():
                line += (f"; the roster now says {roster_rights}: if the extension covers this post, "
                         f"record --rights-from-roster; if not, --rights-not-covered --note")
            out["coming"].append(line)
    return out


def days_word(n):
    return f"{n} day" if n == 1 else f"{n} days"


def next_pipeline_action(pubs, campaign, creator):
    """The earliest thing a person still owes the live posts of one campaign and creator:
    a removal not yet reviewed, or the next check not yet recorded. (action, date) or ('', '')."""
    todo = []
    for r in pubs:
        if r["campaign_slug"] != campaign or r["creator_ref"] != creator:
            continue
        try:
            posted = parse_time(r["posted_at"], "posted_at").date()
        except BadInput:
            continue
        entries = parse_notes(r["notes"])
        state = None
        for n in CHECK_DAYS:
            v = r.get(f"check_day{n}") or "not_checked"
            if v in ("live", "edited", "removed"):
                state = v
                if v == "removed":
                    ce = latest(entries, "check", lambda e: e["kv"].get(f"day{n}") == v)
                    seen = ce["date"] if ce else posted + timedelta(days=n)
                    if not latest(entries, "removal-reviewed", lambda e: e["date"] >= seen):
                        todo.append((seen, f"removal review of {r['publication_id']}"))
                continue
            if state == "removed":
                continue
            todo.append((posted + timedelta(days=n), f"day {n} check of {r['publication_id']}"))
            break
    if not todo:
        return "", ""
    when, what = min(todo)
    return what, when.isoformat()


def set_pipeline_next(pipeline, pubs, campaign, creator):
    """Point a live pipeline row's next_action at what is owed next; 1 if the row changed, else 0."""
    prow = next((p for p in pipeline if p["campaign_slug"] == campaign and p["creator_ref"] == creator), None)
    if prow is None or prow["stage"] != "live":
        return 0
    what, when = next_pipeline_action(pubs, campaign, creator)
    if (prow["next_action"], prow["next_action_date"]) == (what, when):
        return 0
    prow["next_action"], prow["next_action_date"] = what, when
    return 1


def label(row):
    return f"{row['publication_id']} ({row['campaign_slug']}, {row['creator_ref']}, {row['platform']} {row['format']})"


def print_row_report(row, ev):
    for key, title in (("overdue", "OVERDUE"), ("act", "ACT NOW"), ("unchecked", "NOT CHECKED"),
                       ("coming", "COMING UP")):
        for line in ev[key]:
            print(f"  {title}: {line}")
    if not any(ev[k] for k in ("overdue", "act", "unchecked", "coming")):
        print("  nothing due for this post yet")


# --------------------------------------------------------------------------------------------- live-check input
def live_check_args(p):
    p.add_argument("--disclosure-seen", choices=DISCLOSURE_SEEN)
    p.add_argument("--disclosure-form", help="; list of caption, spoken, on_screen, platform_tool")
    p.add_argument("--code-in-post", help="the code exactly as it appears in the post")
    p.add_argument("--no-code-in-post", action="store_true", help="looked: no code in the post")
    p.add_argument("--link-in-post", help="the link exactly as it appears (caption, bio, sticker or description)")
    p.add_argument("--no-link-in-post", action="store_true", help="looked: no link anywhere the post points to")
    p.add_argument("--age-setting", choices=AGE_VALUES)
    p.add_argument("--matches-approval", choices=list(MATCH_VALUES))


def live_check_given(a):
    return any([a.disclosure_seen, a.disclosure_form, a.code_in_post, a.no_code_in_post, a.link_in_post,
                a.no_link_in_post, a.age_setting, a.matches_approval])


def parse_forms(s):
    if s is None:
        return None
    forms = [f.strip() for f in s.split(";") if f.strip()]
    bad = [f for f in forms if f not in FORMS]
    if bad:
        fail(f"--disclosure-form has {', '.join(bad)}; allowed: {', '.join(FORMS)}, separated by ';'.")
    return [f for f in FORMS if f in forms]


def apply_live_check(row, rr, a, fmt, on, role):
    """Validate the reported live check, update the row's columns, return the live-check note entry."""
    if a.code_in_post and a.no_code_in_post:
        fail("give --code-in-post or --no-code-in-post, not both.")
    if a.link_in_post and a.no_link_in_post:
        fail("give --link-in-post or --no-link-in-post, not both.")
    forms = parse_forms(a.disclosure_form)
    if forms is not None and not a.disclosure_seen:
        fail("--disclosure-form needs --disclosure-seen as well.")
    if a.disclosure_seen:
        if a.disclosure_seen == "no" and forms:
            fail("--disclosure-seen no means no adequate disclosure was seen, so --disclosure-form must be empty; "
                 "use partial if some form was there.")
        if a.disclosure_seen in ("yes", "partial") and not forms:
            fail(f"--disclosure-seen {a.disclosure_seen} needs --disclosure-form naming where it was seen.")
        if a.disclosure_seen == "yes":
            need = REQUIRED_ALL.get(fmt)
            if need and not need.issubset(forms):
                fail(f"a {fmt} counts as disclosed only with {' and '.join(sorted(need))} "
                     f"(references/live-check.md, line 3); record partial, or add the forms that were seen.")
            anyof = REQUIRED_ANY.get(fmt)
            if anyof and not anyof.intersection(forms):
                fail(f"a {fmt} counts as disclosed only with one of {', '.join(sorted(anyof))}; "
                     f"record partial, or add the form that was seen.")
        row["disclosure_seen"] = a.disclosure_seen
        row["disclosure_form"] = ";".join(forms or [])
    kv = []
    if a.disclosure_seen:
        kv.append(f"disclosure={a.disclosure_seen}")
        kv.append("forms=" + ("+".join(forms) if forms else "none"))
    entries = parse_notes(row["notes"])
    if a.code_in_post or a.no_code_in_post:
        row["code_in_post"] = (a.code_in_post or "").strip()
        kv.append("code=" + code_result(row["code_in_post"], a.no_code_in_post, issued(entries, rr, "code")))
    if a.link_in_post or a.no_link_in_post:
        row["link_in_post"] = (a.link_in_post or "").strip()
        kv.append("link=" + link_result(row["link_in_post"], a.no_link_in_post, issued(entries, rr, "link")))
    if a.age_setting:
        kv.append(f"age={a.age_setting}")
    if a.matches_approval:
        kv.append(f"approval={MATCH_VALUES[a.matches_approval]}")
    return entry(on, "live-check", kv, role)


def approval_verdict(path):
    """The verdict line of a content-approval record; 'unknown' when the line cannot be read."""
    m = re.search(r"^-\s*verdict:\s*([a-z-]+)", path.read_text(encoding="utf-8"), re.M | re.I)
    v = m.group(1).lower() if m else "unknown"
    return v if v in ("approve", "approve-with-changes", "stop") else "unknown"


def check_approval(ws, approval, campaign, creator):
    m = APPROVAL_RE.match(approval)
    if not m:
        fail(f"--approval '{approval}' is not an approval_id (<campaign_slug>--<creator_ref>--<n>); "
             f"give the id from campaigns/{campaign}/approvals/, or 'none' if the post went live without one.")
    if m.group(1) != campaign or m.group(2) != creator:
        fail(f"--approval '{approval}' belongs to campaign {m.group(1)} and creator {m.group(2)}, "
             f"not {campaign} and {creator}.")
    folder = ws / "campaigns" / campaign / "approvals"
    if not (folder / f"{approval}.md").exists():
        fail(f"no approval record at {folder / (approval + '.md')}; check the id, or give 'none' if there was no approval.")
    later = sorted(int(p.stem.rsplit("--", 1)[1]) for p in folder.glob(f"{campaign}--{creator}--*.md")
                   if p.stem.rsplit("--", 1)[1].isdigit())
    n = int(m.group(3))
    verdict = approval_verdict(folder / f"{approval}.md")
    warns = []
    if later and later[-1] > n:
        warns.append(f"a later approval attempt exists ({campaign}--{creator}--{later[-1]}); confirm the post "
                     f"went live under attempt {n}")
    if verdict == "stop":
        warns.append(f"the verdict of {approval} is stop: this version was not approved for posting")
    elif verdict == "unknown":
        warns.append(f"no readable verdict line in {approval}.md; read the record")
    return verdict, warns


# --------------------------------------------------------------------------------------------- commands
def paths(ws):
    return (ws / "data" / "publications.csv", ws / "data" / "creators.csv", ws / "data" / "pipeline.csv")


def workbook_reminder():
    print("Workbook: if data/creator-programme.xlsx was edited since the last import, run creator-roster "
          "import-xlsx before this script; after this write, run creator-roster export-xlsx.")


def cmd_list(ws, a):
    as_of = parse_date(a.as_of, "--as-of") if a.as_of else today_utc()
    text = read_programme(ws)
    rules = platform_rules(text)
    pub_p, ros_p, _ = paths(ws)
    pubs, bad = read_csv(pub_p, PUB_HEADER, "data/publications.csv", strict=False)
    roster, rbad = read_csv(ros_p, ROSTER_HEADER, "data/creators.csv", strict=False)
    by_ref = {r["creator_ref"]: r for r in roster}
    merged = sum(1 for r in roster if merged_into(r))
    done_sets = reached_pairs(pubs)
    min_live, min_live_says = programme_days(text, 11, MIN_LIVE_LINE)
    sections = {"overdue": [], "act": [], "unchecked": [], "coming": []}
    skipped = [f"line {ln}: {why}" for ln, why in bad]
    ended, unknown, none_granted, waived, quiet, future = [], [], [], 0, 0, 0
    for row in pubs:
        rr = by_ref.get(row["creator_ref"])
        kept = merged_into(rr)
        if kept:
            rr = None   # a merged duplicate is inactive and never counted (schemas.md section 4)
        ev = evaluate(row, rr, platform_rule(rules, row["platform"]), as_of, done_sets, min_live, audience_rule(section_lines(text, 9)))
        if ev["skip"]:
            if "after the as-of date" in ev["skip"]:
                future += 1
            else:
                skipped.append(f"{row['publication_id'] or '(no id)'}: {ev['skip']}")
            continue
        if kept:
            ev["unchecked"].append(f"creator {row['creator_ref']} was merged into {kept}: correct the row's "
                                   f"creator_ref in the workbook with a dated note; the deal and the roster's "
                                   f"rights window not judged")
        elif rr is None:
            ev["unchecked"].append(f"creator {row['creator_ref']} not in data/creators.csv: the deal (fee "
                                   f"milestone) and the roster's rights window not judged")
        for k in sections:
            sections[k] += [f"{label(row)}: {line}" for line in ev[k]]
        if ev["ended"]:
            ended.append(row["publication_id"])
        if ev["rights_unknown"]:
            unknown.append(row["publication_id"])
        if ev["rights_none"]:
            none_granted.append(row["publication_id"])
        waived += ev["waived"]
        if not any(ev[k] for k in sections):
            quiet += 1
    attention = sections["overdue"] or sections["act"] or sections["unchecked"]
    partial = bool(skipped)
    first = "partial: " if partial else ""
    print(f"{first}publication-tracking due list as of {as_of.isoformat()} "
          f"(dates are User-provided, from the workspace; due dates and day counts computed by this script in UTC calendar days)")
    counts = (f"{len(sections['overdue'])} overdue, {len(sections['act'])} to act on, "
              f"{len(sections['unchecked'])} with lines not checked, {len(sections['coming'])} coming up")
    if attention or partial:
        print(f"Result: needs attention (exit 2): {counts}")
    elif sections["coming"]:
        print(f"Result: nothing overdue (exit 0): {counts}")
    else:
        print("Result: nothing needs attention (exit 0)")
    for key, title in (("overdue", "OVERDUE"), ("act", "ACT NOW"), ("unchecked", "NOT CHECKED"),
                       ("coming", "COMING UP")):
        if sections[key]:
            print(f"\n{title}")
            for line in sections[key]:
                print(f"- {line}")
    print()
    print(f"Coverage: read {len(pubs)} publication rows and {len(roster) - merged} roster rows"
          + (f" ({merged} merged duplicate{'' if merged == 1 else 's'} not counted)" if merged else "")
          + f", programme sections 3 and 11 (minimum time live: {min_live_says}). "
          f"Rows skipped (could not be read): {len(skipped)}" + (f" [{'; '.join(skipped)}]" if skipped else "")
          + (f". Roster lines skipped: {len(rbad)}" if rbad else "")
          + f". Posted after the as-of date, not judged: {future}"
          + f". Rows with nothing due: {quiet}. Waived issues: {waived}"
          + f". Rights already ended: {len(ended)}" + (f" [{', '.join(ended)}]" if ended else "")
          + f". Rights window unknown: {len(unknown)}" + (f" [{', '.join(unknown)}]" if unknown else "")
          + f". No reuse rights granted: {len(none_granted)}" + (f" [{', '.join(none_granted)}]" if none_granted else "")
          + ". Not judged by this script: whether the disclosure wording and placement meet programme "
            "section 8, whether the post matches its approval, the audience setting; those are the "
            "person's live-check report.")
    return 2 if (attention or partial) else 0


def cmd_add(ws, a):
    text = read_programme(ws)
    rules = platform_rules(text)
    role = check_role(a.role, programme_roles(text))
    on = parse_date(a.on, "--on") if a.on else today_utc()
    pub_p, ros_p, pipe_p = paths(ws)
    pubs, _ = read_csv(pub_p, PUB_HEADER, "data/publications.csv", strict=True)
    roster, _ = read_csv(ros_p, ROSTER_HEADER, "data/creators.csv", strict=True)
    pipeline = read_csv(pipe_p, PIPELINE_HEADER, "data/pipeline.csv", strict=True)[0] if pipe_p.exists() else None
    if not SLUG_RE.match(a.campaign):
        fail(f"--campaign '{a.campaign}' is not a campaign_slug (YYYY-MM- then lowercase words with hyphens).")
    if not (ws / "campaigns" / a.campaign).is_dir():
        fail(f"no campaign folder campaigns/{a.campaign}/; check the slug, or run campaign-plan first.")
    if not REF_RE.match(a.creator):
        fail(f"--creator '{a.creator}' is not a creator_ref (c- and six lowercase letters or digits); "
             f"never a handle.")
    rr = next((r for r in roster if r["creator_ref"] == a.creator), None)
    if rr is None:
        fail(f"creator {a.creator} is not in data/creators.csv; add them with creator-roster first.")
    if merged_into(rr):
        fail(f"creator {a.creator} was merged into {merged_into(rr)}; record the post under {merged_into(rr)}.")
    if a.platform not in PLATFORMS:
        fail(f"--platform '{a.platform}' is not one of {', '.join(PLATFORMS)}.")
    if a.format not in FORMATS:
        fail(f"--format '{a.format}' is not one of {', '.join(FORMATS)}.")
    if not re.match(r"^https?://\S+$", a.url.strip()):
        fail(f"--url '{a.url}' must be the post's full web address, starting http:// or https://.")
    key = norm_post_url(a.url)
    dup = next((r for r in pubs if r["post_url"] and norm_post_url(r["post_url"]) == key), None)
    if dup:
        fail(f"this post is already recorded as {dup['publication_id']}; use record {dup['publication_id']} instead.")
    posted = parse_time(a.posted_at, "--posted-at")
    if posted.date() > on:
        fail(f"--posted-at {fmt_time(posted)} is after the observation date {on.isoformat()}.")
    warnings = []
    if a.approval.strip().lower() == "none":
        approval = ""
    else:
        approval = a.approval.strip()
        verdict, w = check_approval(ws, approval, a.campaign, a.creator)
        warnings += w
    if rr["usage_rights_until"].strip():
        parse_date(rr["usage_rights_until"], f"the roster's usage_rights_until for {a.creator}")
    rights, rights_how = roster_rights_for(rr, posted.date())
    existing = {r["publication_id"] for r in pubs}
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    pid = "p-" + "".join(secrets.choice(alphabet) for _ in range(6))
    while pid in existing:
        pid = "p-" + "".join(secrets.choice(alphabet) for _ in range(6))
    row = {k: "" for k in PUB_HEADER}
    row.update({"publication_id": pid, "campaign_slug": a.campaign, "creator_ref": a.creator,
                "platform": a.platform, "post_url": a.url.strip(), "posted_at": fmt_time(posted),
                "format": a.format, "approval_id": approval, "check_day1": "not_checked",
                "check_day7": "not_checked", "check_day30": "not_checked", "rights_until": rights})
    given = [f"issued-code={rr['code'].strip()}"] if rr["code"].strip() else []
    given += [f"issued-link={rr['affiliate_link'].strip()}"] if rr["affiliate_link"].strip() else []
    given += [f"verdict={verdict}"] if approval else []
    append_note(row, entry(on, "added", given, role, "approval none on record" if not approval else ""))
    if live_check_given(a):
        append_note(row, apply_live_check(row, rr, a, a.format, on, role))
    if a.note:
        append_note(row, entry(on, "note", [], role, a.note))
    if rr["status"] != "active":
        warnings.append(f"the roster status for {a.creator} is '{rr['status']}', not active")
    platforms = {rr["primary_platform"]} | {p.split(":", 1)[0] for p in rr["other_platforms"].split(";") if p}
    if a.platform not in platforms:
        warnings.append(f"{a.platform} is not among the creator's platforms in the roster")
    kind, detail = platform_rule(rules, a.platform)
    if kind == "conditional":
        warnings.append(f"programme section 3 allows organic creator posts on {a.platform} {detail}: "
                        f"confirm the post meets the conditions")
    pipe_changed = 0
    if pipeline is not None:
        prow = next((p for p in pipeline if p["campaign_slug"] == a.campaign and p["creator_ref"] == a.creator), None)
        if prow is None:
            warnings.append(f"no pipeline row for {a.campaign} and {a.creator}; pipeline not moved")
        elif prow["stage"] == "closed":
            warnings.append("the pipeline row is closed; left as it is")
        else:
            if prow["stage"] != "approved" and prow["stage"] != "live":
                warnings.append(f"the pipeline stage was '{prow['stage']}', not approved, when the post went live")
            if prow["stage"] != "live":
                prow["stage"] = "live"
                prow["stage_date"] = posted.date().isoformat()
            if "programme lead" in programme_roles(text):
                prow["owner_role"] = "programme lead"
            append_note(prow, entry(on, "live", [pid], role))
            pipe_changed = 1
    else:
        warnings.append("data/pipeline.csv not found; pipeline not moved")
    pubs.append(row)
    if pipe_changed:
        set_pipeline_next(pipeline, pubs, a.campaign, a.creator)
    write_csv(pub_p, PUB_HEADER, pubs)
    if pipe_changed:
        write_csv(pipe_p, PIPELINE_HEADER, pipeline)
    print(f"publication_id={pid}")
    print(f"data/publications.csv: read {len(pubs) - 1} rows, added 1, changed 0. rights_until: "
          f"{rights or 'empty'} ({rights_how}).")
    line = roster_update_line(ws, rr, rights, posted.date(), pid, role)
    if line:
        print(line)
    print(f"data/pipeline.csv: " + (f"read {len(pipeline)} rows, added 0, changed {pipe_changed}." if pipeline is not None else "not present."))
    if pipe_changed:
        what, when = next_pipeline_action(pubs, a.campaign, a.creator)
        print("Pipeline next action: " + (f"{what} on {when}" if what else "none"))
    for w in warnings:
        print(f"Warning: {w}.")
    print(f"As of {on.isoformat()}, for {label(row)}:")
    print_row_report(row, evaluate(row, rr, (kind, detail), on, reached_pairs(pubs),
                                   programme_days(text, 11, MIN_LIVE_LINE)[0], audience_rule(section_lines(text, 9))))
    workbook_reminder()
    return 0


def cmd_record(ws, a):
    text = read_programme(ws)
    rules = platform_rules(text)
    roles = programme_roles(text)
    role = check_role(a.role, roles)
    on = parse_date(a.on, "--on") if a.on else today_utc()
    pub_p, ros_p, pipe_p = paths(ws)
    pubs, _ = read_csv(pub_p, PUB_HEADER, "data/publications.csv", strict=True)
    roster, _ = read_csv(ros_p, ROSTER_HEADER, "data/creators.csv", strict=True)
    pipeline = read_csv(pipe_p, PIPELINE_HEADER, "data/pipeline.csv", strict=True)[0] if pipe_p.exists() else None
    if not PUB_RE.match(a.publication_id):
        fail(f"'{a.publication_id}' is not a publication_id (p- and six lowercase letters or digits).")
    row = next((r for r in pubs if r["publication_id"] == a.publication_id), None)
    if row is None:
        fail(f"{a.publication_id} is not in data/publications.csv; run the due list to see the ids.")
    rr = next((r for r in roster if r["creator_ref"] == row["creator_ref"]), None)
    if rr is None:
        fail(f"creator {row['creator_ref']} of {a.publication_id} is not in data/creators.csv; fix the roster first.")
    if merged_into(rr):
        fail(f"creator {row['creator_ref']} of {a.publication_id} was merged into {merged_into(rr)}; correct the "
             f"row's creator_ref in the workbook with a dated note, import it, then record.")
    posted = parse_time(row["posted_at"], f"posted_at of {a.publication_id}").date()
    if on < posted:
        fail(f"--on {on.isoformat()} is before the post went live ({posted.isoformat()}).")
    done, after_lines = [], []
    for n in CHECK_DAYS:
        v = getattr(a, f"day{n}")
        if v is None:
            continue
        due = posted + timedelta(days=n)
        if on < due:
            fail(f"the day {n} check of {a.publication_id} is not due until {due.isoformat()}; record what you "
                 f"saw with --note, or wait.")
        row[f"check_day{n}"] = v
        append_note(row, entry(on, "check", [f"day{n}={v}"], role))
        done.append(f"day {n} check: {v}")
    if live_check_given(a):
        before = issue_states(row, rr, parse_notes(row["notes"]), audience_rule(section_lines(text, 9)))
        append_note(row, apply_live_check(row, rr, a, row["format"], on, role))
        after = issue_states(row, rr, parse_notes(row["notes"]), audience_rule(section_lines(text, 9)))
        done.append("live check re-run")
        for issue in LIVE_ISSUES:
            if before[issue][0] == "open" and after[issue][0] == "ok":
                append_note(row, entry(on, "fix-confirmed", [issue], role, "re-check of the live post"))
                done.append(f"fix confirmed: {issue}")
    if a.fix_requested:
        window, says = programme_days(text, 8, FIX_WINDOW_LINE)
        if a.due:
            fdue = parse_date(a.due, "--due")
            how = f"due set by {role}"
            if window is not None and fdue != on + timedelta(days=window):
                how += f"; programme section 8 gives {days_word(window)}"
                print(f"Warning: --due {fdue.isoformat()} differs from programme section 8's {days_word(window)} "
                      f"from the request ({(on + timedelta(days=window)).isoformat()}); recorded as given.")
        elif window is not None:
            fdue = on + timedelta(days=window)
            how = f"due from programme section 8, {days_word(window)} after the request"
        else:
            fail(f"programme section 8's line \"{FIX_WINDOW_LINE}\" is {says}; ask the programme lead for the "
                 f"date and give it with --due DATE, or have the owner fill the line through program-setup.")
        if fdue < on:
            fail(f"--due {fdue.isoformat()} is before the request date {on.isoformat()}.")
        txt = how + (f". {a.note}" if a.note else "")
        append_note(row, entry(on, "fix-requested", [a.fix_requested, f"due={fdue.isoformat()}"], role, txt))
        done.append(f"fix requested: {a.fix_requested}, due {fdue.isoformat()} ({how})")
    elif a.due:
        fail("--due goes with --fix-requested.")
    if a.waived:
        if role != "owner":
            fail("only the owner can waive an issue (programme section 10); record it with --role owner.")
        if not a.note:
            fail("--waived needs --note with the owner's reason.")
        append_note(row, entry(on, "waived", [a.waived], role, a.note))
        done.append(f"waived by the owner: {a.waived}")
    if a.removal_reviewed:
        append_note(row, entry(on, "removal-reviewed", [], role, a.removal_reviewed))
        done.append("removal reviewed")
    if a.fee_milestone:
        if rr["compensation_model"] not in FEE_MODELS:
            fail(f"the roster deal for {row['creator_ref']} is '{rr['compensation_model']}'; a fee milestone "
                 f"applies only to flat and hybrid deals.")
        if a.fee_milestone in ("held", "part") and not a.note:
            fail(f"--fee-milestone {a.fee_milestone} needs --note: for held, the reason and the agreement term; "
                 f"for part, which post of the deliverable set this is.")
        reached = lambda r: latest(parse_notes(r["notes"]), "fee",
                                   lambda e: e["args"][:2] == ["milestone", "reached"])
        if a.fee_milestone == "reached":
            if reached(row):
                fail(f"{a.publication_id} already has a fee milestone reached; it is recorded once.")
            other = [r["publication_id"] for r in pubs if r is not row and r["campaign_slug"] == row["campaign_slug"]
                     and r["creator_ref"] == row["creator_ref"] and reached(r)]
            if other and (role != "owner" or not a.note):
                fail(f"{', '.join(other)} already carries this campaign's fee milestone for {row['creator_ref']}; "
                     f"the roster's flat_fee is per deliverable set. A second set is recorded by the owner "
                     f"(--role owner) with --note naming it.")
        txt = a.note if a.note else "finance to pay"
        append_note(row, entry(on, "fee", ["milestone", a.fee_milestone], role, txt))
        done.append(f"fee milestone {a.fee_milestone}")
    if a.rights_from_roster:
        new, how = roster_rights_for(rr, posted)
        if not new:
            fail(f"the roster has no usage_rights_until for {row['creator_ref']} and no 'rights from posting' "
                 f"note; record the agreement there first.")
        parse_date(new, "the roster's usage_rights_until")
        if not a.note:
            fail("--rights-from-roster needs --note naming the agreement or extension that covers this post.")
        if new == row["rights_until"]:
            done.append("rights_until already matches the roster; no change")
        else:
            old = row["rights_until"] or "unknown"
            row["rights_until"] = new
            append_note(row, entry(on, "rights-until", [new, f"from={old}"], role, f"{a.note} ({how})"))
            done.append(f"rights_until {old} -> {new} ({how})")
        roster_line = roster_update_line(ws, rr, new, posted, a.publication_id, role)
        if roster_line:
            after_lines.append(roster_line)
    if a.rights_not_covered:
        cur = rr["usage_rights_until"].strip()
        if not cur:
            fail(f"the roster has no usage_rights_until for {row['creator_ref']}; there is nothing to settle.")
        if not a.note:
            fail("--rights-not-covered needs --note saying why the roster's date does not cover this post.")
        append_note(row, entry(on, "rights-not-covered", [f"roster={cur}"], role, a.note))
        done.append(f"the roster's {cur} recorded as not covering this post")
    if a.approval:
        verdict, w = check_approval(ws, a.approval, row["campaign_slug"], row["creator_ref"])
        old = row["approval_id"]
        if old:
            om, nm = APPROVAL_RE.match(old), APPROVAL_RE.match(a.approval)
            if not om or int(nm.group(3)) <= int(om.group(3)):
                fail(f"{a.publication_id} is already linked to {old}; only a later attempt from a re-review "
                     f"(content-approval) can replace it. A wrong link is corrected in the workbook with a dated note.")
        row["approval_id"] = a.approval
        append_note(row, entry(on, "approval", [a.approval, f"verdict={verdict}"]
                               + ([f"from={old}"] if old else []), role))
        done.append(f"approval linked: {a.approval}" + (f" (replacing {old})" if old else "")
                    + "".join(f"; warning: {x}" for x in w))
    if a.note and not (a.fix_requested or a.waived or a.fee_milestone or a.rights_from_roster or a.rights_not_covered):
        append_note(row, entry(on, "note", [], role, a.note))
        done.append("note added")
    if not done:
        fail("nothing to record: give a check, live-check values, a fix request, a waiver, a removal review, "
             "a fee milestone, --rights-from-roster, --rights-not-covered, --approval or --note.")
    pipe_changed = set_pipeline_next(pipeline, pubs, row["campaign_slug"], row["creator_ref"]) if pipeline else 0
    write_csv(pub_p, PUB_HEADER, pubs)
    if pipe_changed:
        write_csv(pipe_p, PIPELINE_HEADER, pipeline)
    print(f"data/publications.csv: read {len(pubs)} rows, added 0, changed 1 ({a.publication_id}).")
    if pipeline is not None:
        prow = next((x for x in pipeline if x["campaign_slug"] == row["campaign_slug"]
                     and x["creator_ref"] == row["creator_ref"]), None)
        if prow is not None and prow["stage"] == "live":
            what = prow["next_action"]
            tail = f"Next action: {what} on {prow['next_action_date']}" if what else "Next action: none (cleared)"
        else:
            tail = "No live pipeline row for this campaign and creator; left as it is"
        print(f"data/pipeline.csv: read {len(pipeline)} rows, added 0, changed {pipe_changed}. {tail}.")
    for d in done:
        print(f"Recorded: {d}.")
    for line in after_lines:
        print(line)
    print(f"As of {on.isoformat()}, for {label(row)}:")
    print_row_report(row, evaluate(row, rr, platform_rule(rules, row["platform"]), on, reached_pairs(pubs),
                                   programme_days(text, 11, MIN_LIVE_LINE)[0], audience_rule(section_lines(text, 9))))
    workbook_reminder()
    return 0


def build_parser():
    p = Parser(
        prog="checks_due.py",
        description="Record live creator posts and list what is due (publication-tracking skill).",
        epilog="Exit 0 done; 1 bad input, nothing written; 2 (due list) something needs a person or the run "
               "was partial. Numbers: CHECK_DAYS, GRACE_DAYS, RIGHTS_WARNING_DAYS at the top of this file.")
    p.add_argument("workspace", help="the programme workspace folder")
    p.add_argument("--as-of", help="due-list date, YYYY-MM-DD (default: today, UTC)")
    sub = p.add_subparsers(dest="cmd")
    ad = sub.add_parser("add", help="record a new live post")
    ad.add_argument("--campaign", required=True)
    ad.add_argument("--creator", required=True, help="creator_ref, never a handle")
    ad.add_argument("--platform", required=True, help="as in the roster: " + ", ".join(PLATFORMS))
    ad.add_argument("--url", required=True)
    ad.add_argument("--posted-at", required=True, help="UTC time, for example 2026-11-03T18:30Z, or a time with its offset")
    ad.add_argument("--format", required=True, help=", ".join(FORMATS))
    ad.add_argument("--approval", required=True, help="approval_id, or none if the post went live without one")
    ad.add_argument("--role", required=True, help="a role from programme section 10")
    ad.add_argument("--on", help="date the post was looked at, YYYY-MM-DD (default: today, UTC)")
    ad.add_argument("--note")
    live_check_args(ad)
    rc = sub.add_parser("record", help="record a check, a re-check, a fix request, a waiver, a milestone or a note")
    rc.add_argument("publication_id")
    rc.add_argument("--role", required=True, help="a role from programme section 10")
    rc.add_argument("--on", help="date of what is recorded, YYYY-MM-DD (default: today, UTC)")
    for n in CHECK_DAYS:
        rc.add_argument(f"--day{n}", choices=CHECK_VALUES)
    live_check_args(rc)
    rc.add_argument("--fix-requested", choices=ISSUES)
    rc.add_argument("--due", help="the date the fix was asked for by, YYYY-MM-DD; default: the request date "
                                  "plus programme section 8's correction window")
    rc.add_argument("--waived", choices=ISSUES, help="owner only, with --note")
    rc.add_argument("--removal-reviewed", metavar="TEXT")
    rc.add_argument("--fee-milestone", choices=["reached", "part", "held"],
                    help="flat and hybrid deals: reached (finance to pay), part (one post of a set), held (with --note)")
    rc.add_argument("--rights-from-roster", action="store_true",
                    help="copy the roster's usage_rights_until (or date it from posting) onto this post, with --note")
    rc.add_argument("--rights-not-covered", action="store_true",
                    help="the roster's current date does not cover this post, with --note; stops the prompt "
                         "until the roster date changes")
    rc.add_argument("--approval", help="link an approval_id to a post recorded without one")
    rc.add_argument("--note")
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    ws = Path(a.workspace)
    try:
        if not ws.is_dir():
            fail(f"workspace folder {ws} not found.")
        if a.cmd == "add":
            return cmd_add(ws, a)
        if a.cmd == "record":
            return cmd_record(ws, a)
        return cmd_list(ws, a)
    except BadInput as e:
        print(f"error: {e} Nothing was written.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
