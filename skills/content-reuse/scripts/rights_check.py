#!/usr/bin/env python3
"""Build the creator-content reuse inventory for one campaign, and check a reuse plan against it.

Usage (run with python3 -I):
  rights_check.py <workspace> --campaign <slug> --as-of YYYY-MM-DD
                  [--asset p-xxxxxx ...] [--check-plan campaigns/<slug>/reuse/plan-YYYY-MM-DD.md]

Reads, never writes: program/program.md (sections 3, 7, 10, 12), data/publications.csv,
data/creators.csv, the agreement file each roster row names, and the approval records under
campaigns/<slug>/approvals/. Writes one file: campaigns/<slug>/reuse/inventory.csv.
No network. Standard library only.

Exit codes: 0 done; 1 bad input (one sentence says what to fix);
2 a requested asset cannot be reused, or the plan has rows that fail the check.
The column meanings, status values and hold codes are in references/inventory-codes.md.
"""
import argparse
import csv
import datetime as dt
import pathlib
import re
import sys

# Days before the rights end at which an asset is marked "expiring". Source: the pack's
# publication-tracking skill warns 30 days before a rights window closes; this window is kept
# equal so the two lists agree. Change it here and nowhere else.
EXPIRING_DAYS = 30

# The brand's owned channels, as the pack's content-reuse brief names them (2026-10-20):
# product pages, email, the brand's own social accounts, retail partner decks.
OWNED_CHANNELS = ["product-page", "email", "brand-social", "retail-deck"]

# Words that map a usage-rights line in an agreement file to an owned channel. Build's choice;
# a stated channel list narrows the suggestions, an absent one leaves all four with a note.
CHANNEL_WORDS = [
    ("product-page", r"\b(product page|product pages|website|web site|site|online store|landing page)"),
    ("email", r"\b(e-?mail|newsletter)"),
    ("brand-social", r"\b(social|instagram|facebook|youtube|tiktok)"),
    ("retail-deck", r"\b(retail|wholesale|deck|sales material)"),
]

# Exact headers from the pack's references/schemas.md, sections 4 and 6.
CREATORS_HEADER = [
    "creator_ref", "display_name", "primary_platform", "primary_handle", "profile_url",
    "other_platforms", "tier", "followers_primary", "followers_as_of", "engagement_rate_pct",
    "engagement_as_of", "niche_tags", "audience_fit_score", "brand_safety_flag", "contact_path",
    "contact_email", "status", "compensation_model", "commission_rate_pct", "flat_fee", "code",
    "affiliate_link", "rail", "agreement_date", "agreement_file", "usage_rights_until",
    "exclusivity_until", "first_campaign", "last_activity", "notes",
]
PUBLICATIONS_HEADER = [
    "publication_id", "campaign_slug", "creator_ref", "platform", "post_url", "posted_at", "format",
    "disclosure_seen", "disclosure_form", "code_in_post", "link_in_post", "approval_id",
    "check_day1", "check_day7", "check_day30", "rights_until", "notes",
]
# This skill's own file; the brief's eight columns plus rights_status, checked_as_of, holds, notes.
INVENTORY_HEADER = [
    "publication_id", "creator_ref", "format", "platform", "rights_until", "rights_status",
    "checked_as_of", "paid_reuse", "approved_claims_present", "suggested_uses", "holds", "notes",
]
# Cut types defined in references/reuse-formats.md, section 2.
CUTS = ["full", "trim", "crop", "still", "quote", "other"]
PLAN_COLUMNS = [
    "publication_id", "channel", "placement", "start", "end", "removed_on", "approval_id", "cut",
    "credit and disclosure", "code shown", "owner_role",
]

SLUG_RE = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
PUB_RE = re.compile(r"^p-[a-z0-9]{6}$")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
TAG_RE = re.compile(r"\[(?:owner|observed|default|open)\]", re.I)


class BadInput(Exception):
    """One plain sentence saying what to fix; the script exits 1."""


def iso(value, where):
    """Parse YYYY-MM-DD (a trailing time is ignored). Empty gives None; anything else is bad input."""
    value = (value or "").strip()
    if not value:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:T\d{2}:\d{2}(?::\d{2})?Z?)?$", value)
    if not m:
        raise BadInput(f"{where}: '{value}' is not a date in the form YYYY-MM-DD; correct it and run again.")
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        raise BadInput(f"{where}: '{value}' is not a real calendar date; correct it and run again.")


def read_csv(path, header, label):
    if not path.is_file():
        raise BadInput(f"{label} not found at {path}; create it with the skill that owns it before running content-reuse.")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            got = next(reader)
        except StopIteration:
            raise BadInput(f"{label} is empty; it needs at least its header row.")
        got = [g.strip().lstrip("﻿") for g in got]
        if got != header:
            missing = [h for h in header if h not in got]
            extra = [g for g in got if g not in header]
            if missing or extra:
                parts = []
                if missing:
                    parts.append("missing " + ", ".join(missing))
                if extra:
                    parts.append("extra " + ", ".join(extra))
                raise BadInput(f"{label} header does not match the pack schema ({'; '.join(parts)}); fix the header and run again.")
            raise BadInput(f"{label} has the right columns in the wrong order; restore the schema order and run again.")
        rows = []
        for n, raw in enumerate(reader, start=2):
            if not any(c.strip() for c in raw):
                continue
            if len(raw) != len(header):
                raise BadInput(f"{label} line {n} has {len(raw)} cells, expected {len(header)}; fix that row and run again.")
            rows.append(dict(zip(header, [c.strip() for c in raw])))
        return rows


def sections_of(text):
    """Split the programme file by its fixed '## N.' headings."""
    out, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m:
            current = int(m.group(1))
            out[current] = []
            continue
        if current is not None:
            out[current].append(line)
    return out


def cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_separator(cs):
    filled = [c for c in cs if c]
    return bool(filled) and all(re.fullmatch(r":?-{2,}:?", c) for c in filled)


def platform_key(name):
    name = re.sub(r"\(.*?\)", "", name.lower()).strip()
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def paid_value(raw):
    v = TAG_RE.sub("", raw).strip().lower()
    if not v:
        return ""
    if v.startswith("with conditions"):
        return "with-conditions"
    if v.startswith("yes"):
        return "yes"
    if v.startswith("no"):
        return "no"
    return "unknown"


def parse_platforms(lines):
    rows = [l for l in lines if l.strip().startswith("|")]
    if not rows:
        raise BadInput("Programme section 3 (Platforms) has no platform table; fill it with program-setup.")
    header = [h.lower() for h in cells(rows[0])]
    idx = next((i for i, h in enumerate(header) if "paid" in h), None)
    if idx is None:
        raise BadInput("Programme section 3 (Platforms) has no 'paid by the brand' column; restore the template table.")
    table, filled = {}, 0
    for r in rows[1:]:
        cs = cells(r)
        if is_separator(cs) or len(cs) <= idx or not cs[0]:
            continue
        val = paid_value(cs[idx])
        if val:
            filled += 1
        table[platform_key(cs[0])] = val or "unknown"
    if not filled:
        raise BadInput("Programme section 3 (Platforms): the 'paid by the brand' column is empty for every platform; fill it with program-setup.")
    return table


def claim_core(text):
    quoted = re.findall(r"[\"“”]([^\"“”]{3,})[\"“”]", text)
    if quoted:
        return max(quoted, key=len)
    return re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()


def norm(text):
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


# program-setup's settled state for "nothing cleared yet": this marked line above the Approved
# heading, with Approved empty (program-setup, programme_file.py NO_CLAIM_PREFIX).
NO_CLAIM_PREFIX = "no claim is cleared yet"
OWNER_TAG = re.compile(r"\[owner\]", re.I)


def parse_approved_claims(lines):
    """Return (claims, none_cleared). Only lines marked [owner] count, as program-setup writes them."""
    claims, none_cleared, heading = [], False, None
    for line in lines:
        s = line.strip()
        if s.startswith("###"):
            heading = "approved" if "approved" in s.lower() else "other"
            continue
        m = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", s)
        if not m:
            continue
        body = TAG_RE.sub("", m.group(1)).strip()
        if heading is None and body.lower().startswith(NO_CLAIM_PREFIX) and OWNER_TAG.search(m.group(1)):
            none_cleared = True
        elif heading == "approved" and body and OWNER_TAG.search(m.group(1)):
            core = norm(claim_core(body))
            if core:
                claims.append(core)
    if claims and none_cleared:
        raise BadInput("Programme section 7 lists approved claims and also says no claim is cleared yet; "
                       "the owner settles which is true with program-setup.")
    if not claims and not none_cleared:
        raise BadInput("Programme section 7 lists no approved claim marked [owner] and does not record that no claim "
                       "is cleared yet; the owner settles section 7 with program-setup before content is reused.")
    return claims, none_cleared


def product_statement_count(text):
    """Rows in the approval record's "Product statements" table that quote a statement; None if no such table."""
    inside, header_seen, count = False, False, 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            if inside:
                break
            inside = "product statement" in s.lower()
            continue
        if not inside or not s.startswith("|"):
            continue
        cs = cells(s)
        if not header_seen:
            header_seen = True
            continue
        if is_separator(cs) or len(cs) < 2:
            continue
        quoted = cs[1].strip().strip('"\u201c\u201d').strip()
        if quoted and not quoted.startswith("<") and quoted.lower() not in ("none", "n/a"):
            count += 1
    return count if header_seen else None


def parse_roles(lines):
    roles = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cs = cells(line)
        if is_separator(cs) or not cs[0] or cs[0].lower() == "role":
            continue
        roles.append(TAG_RE.sub("", cs[0]).strip().lower())
    return [r for r in roles if r]


# Words that place a line of section 3's "brand's own channels" list under a channel code,
# checked in this order (a social account named "page" must not read as a product page).
BRAND_CHANNEL_WORDS = [
    ("retail-deck", r"\b(retail|wholesale|stockist|partner deck|deck)"),
    ("email", r"\b(e-?mail|newsletter|mailing list|klaviyo)"),
    ("brand-social", r"(\b(social|instagram|facebook|youtube|tiktok|threads|bluesky|reddit|twitter|x)\b|@)"),
    ("product-page", r"\b(product pages?|site|website|web site|online store|store|landing pages?|pages?)\b"),
]


def parse_brand_channels(lines, roles):
    """Section 3's "The brand's own channels" line and the indented lines under it.

    Returns [(channel code or None, the line's text, publishing role or None)]."""
    texts, inside = [], False
    for line in lines:
        if re.match(r"^\s*[-*+]\s+the brand.s own channels\b", line, re.I):
            inside = True
            rest = TAG_RE.sub("", line.split(":", 1)[1] if ":" in line else "").strip()
            if rest:
                texts.append(rest)
            continue
        if not inside:
            continue
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            text = TAG_RE.sub("", re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line)).strip()
            if text:
                texts.append(text)
            continue
        inside = False
    by_length = sorted(roles, key=len, reverse=True)
    entries = []
    for text in texts:
        low = text.lower()
        code = next((c for c, pattern in BRAND_CHANNEL_WORDS if re.search(pattern, low)), None)
        role = next((r for r in by_length if re.search(r"\b" + re.escape(r) + r"\b", low)), None)
        entries.append((code, text, role))
    return entries


def section7_changes(lines):
    """Dates in the decisions log whose last field names section 7."""
    dates = []
    for line in lines:
        s = re.sub(r"^[-*+]\s+", "", line.strip())
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s*,", s)
        if not m:
            continue
        last = s.split(",")[-1]
        if "7" in re.findall(r"\d+", last):
            d = iso(m.group(1), "Programme section 12 (Decisions log)")
            dates.append(d)
    return sorted(dates)


def parse_verdict(text):
    for line in text.splitlines():
        low = line.lower().replace("*", "").replace("_", " ")
        if "verdict" not in low:
            continue
        rest = re.sub(r"^[^a-z]*", "", low.split("verdict", 1)[1])
        if "approve" in rest and "stop" in rest:
            continue  # an unfilled list of options, not a verdict
        if rest.startswith(("stop", "no-go", "no go")):
            return "stop"
        if rest.startswith(("approve", "go")):
            return "approve"
    return "unread"


def read_approval(ws, slug, approval_id):
    """Return (verdict, date or None, text). verdict is approve, stop, unread or missing."""
    if not approval_id:
        return "missing", None, ""
    path = ws / "campaigns" / slug / "approvals" / f"{approval_id}.md"
    if not path.is_file():
        return "missing", None, ""
    text = path.read_text(encoding="utf-8", errors="replace")
    verdict = parse_verdict(text)
    scrubbed = text.replace(approval_id, " ").replace(slug, " ")
    # content-approval's record carries "reviewed_at: YYYY-MM-DDTHH:MMZ"; other dated lines are
    # a fallback, then the first date in the file.
    date = None
    for pattern in (r"reviewed_at", r"\b(date|reviewed|approved on)\b"):
        for line in scrubbed.splitlines():
            if re.search(pattern, line, re.I):
                m = DATE_RE.search(line)
                if m:
                    date = iso(m.group(1), f"{path.name}")
                    break
        if date is not None:
            break
    if date is None:
        m = DATE_RE.search(scrubbed)
        if m:
            date = iso(m.group(1), f"{path.name}")
    return verdict, date, text


PAID_PHRASE = re.compile(r"paid[\s_-]+(?:re-?)?(?:use|usage)\b", re.I)


def granted_list(rest):
    """For a terms line's value: None if unfilled (a <placeholder>) or empty, [] if 'none', else the text."""
    rest = re.sub(r"^[\s:|\-\u2013\u2014=*]+", "", rest.lower())
    if not rest.strip() or "<" in rest:
        return None
    if re.match(r"none\b", rest):
        return []
    return rest


def parse_agreement(text, platform_keys):
    """Return (paid_reuse, owned channels, paid platforms, conflict flag).

    Reads the lines of the pack's terms sheet (partnership-agreement, section 6): "Owned channels
    the brand may reuse content on:", "Paid reuse:", "Paid reuse platforms:". For the two lists,
    None means not stated (or left as a placeholder) and [] means none granted."""
    values = set()
    for line in text.splitlines():
        for m in PAID_PHRASE.finditer(line):
            before = line[: m.start()].lower().replace("*", "").strip()
            after = line[m.end():].lower().replace("*", "").replace("_", " ")
            after = re.sub(r"\(?\s*yes\s*(?:or|/|\|)\s*no\s*\)?", " ", after)
            after = re.sub(r"^[\s:|\-–—=)]+", "", after)
            w = re.match(r"[a-z]+", after)
            word = w.group(0) if w else ""
            if word in ("yes", "granted", "included", "allowed", "permitted"):
                values.add("yes")
            elif word in ("no", "none", "excluded", "not"):
                values.add("no")
            elif re.search(r"\b(no|not)$", before):
                values.add("no")
    channels, platforms = None, None
    for line in text.splitlines():
        m = re.search(r"\bpaid[\s_-]+(?:re-?)?use[\s_-]+platforms?\b", line, re.I)
        if m:
            got = granted_list(line[m.end():])
            if got is not None:
                platforms = platforms or []
                if got:
                    for key in platform_keys:
                        if re.search(r"\b" + re.escape(key.split("-")[0]) + r"\b", got) and key not in platforms:
                            platforms.append(key)
            continue
        m = re.search(r"\b(?:owned[\s_-]+channels?|(?:reuse|usage)[\s_-]+(?:channels?|rights))\b", line, re.I)
        if not m:
            continue
        rest = line[m.end():]
        rest = re.sub(r"^[^:|]*?(?:content on|reuse on)\b", "", rest, flags=re.I)
        got = granted_list(rest)
        if got is None:
            continue
        channels = channels or []
        for code, pattern in CHANNEL_WORDS:
            if got and re.search(pattern, got) and code not in channels:
                channels.append(code)
    conflict = len(values) > 1
    paid = values.pop() if len(values) == 1 else "unknown"
    if channels is not None:
        channels = [c for c in OWNED_CHANNELS if c in channels]
    return paid, channels, platforms, conflict


def build_inventory(ws, slug, as_of, program):
    publications = read_csv(ws / "data" / "publications.csv", PUBLICATIONS_HEADER, "data/publications.csv")
    creators = read_csv(ws / "data" / "creators.csv", CREATORS_HEADER, "data/creators.csv")
    roster = {c["creator_ref"]: c for c in creators}
    pubs = [p for p in publications if p["campaign_slug"] == slug]
    if not pubs:
        raise BadInput(f"data/publications.csv has no row for campaign {slug}; record live posts with publication-tracking first.")
    platforms = parse_platforms(program.get(3, []))
    roles = parse_roles(program.get(10, []))
    brand = parse_brand_channels(program.get(3, []), roles)
    brand_codes = {code for code, _, _ in brand if code}
    if not brand_codes:
        raise BadInput("Programme section 3: the brand's own channels line lists no channel this skill can read "
                       "(site pages, email list, social accounts, retail partners); fill it with program-setup, "
                       "one indented line per channel with the role that publishes on it.")
    claims, none_cleared = parse_approved_claims(program.get(7, []))
    changes = section7_changes(program.get(12, []))
    stats = {"agreements_expected": 0, "agreements_read": 0, "approvals_expected": 0, "approvals_read": 0}
    rows = []
    for p in pubs:
        where = f"data/publications.csv ({p['publication_id']})"
        ref = p["creator_ref"]
        creator = roster.get(ref)
        notes, holds = [], []
        posted = iso(p["posted_at"], where + " posted_at")
        pub_ru = iso(p["rights_until"], where + " rights_until")
        ros_ru = iso(creator["usage_rights_until"], f"data/creators.csv ({ref}) usage_rights_until") if creator else None
        # schemas.md section 4: "rights from posting: <n> months" on the roster means the window runs
        # from each post's own date; publication-tracking computes the post's rights_until, so the
        # publication row is read and the roster date is not applied to it.
        from_posting = re.search(r"rights from posting:\s*(\d+)\s*months?", creator["notes"], re.I) if creator else None
        if from_posting:
            rights_until = pub_ru
            notes.append(f"rights-from-posting:{from_posting.group(1)}-months")
        elif pub_ru and ros_ru:
            rights_until = min(pub_ru, ros_ru)
            if pub_ru != ros_ru:
                notes.append(f"rights-mismatch:publication={pub_ru}+roster={ros_ru}+used-earlier")
        else:
            rights_until = pub_ru or ros_ru
            if ros_ru and not pub_ru:
                notes.append("rights-from-roster")
        # Rights status: unknown unless a written agreement and a rights date both exist.
        # schemas.md section 4: a merged duplicate (status ended, note "merged into c-...") is
        # inactive and never counted; an empty usage_rights_until with an agreement file on the
        # roster means no rights were granted, which is not the same as unknown.
        merged = re.search(r"merged into (c-[a-z0-9]{6})", creator["notes"], re.I) if creator else None
        if creator is None:
            status = "unknown"
            notes.append("not-in-roster")
        elif merged and creator["status"] == "ended":
            status = "unknown"
            notes.append(f"creator-merged-into:{merged.group(1)}")
        elif not creator["agreement_date"]:
            status = "unknown"
            notes.append("no-written-agreement")
        elif from_posting and pub_ru is None:
            status = "unknown"
            notes.append("rights-from-posting-undated" if posted else "rights-from-posting-not-yet-live")
        elif ros_ru is None and creator["agreement_file"] and not from_posting:
            status = "not-granted"
            notes.append("no-rights-granted")
        elif rights_until is None:
            status = "unknown"
            notes.append("no-rights-date")
        elif rights_until < as_of:
            status = "expired"
        elif (rights_until - as_of).days <= EXPIRING_DAYS:
            status = "expiring"
            notes.append(f"days-left:{(rights_until - as_of).days}")
        else:
            status = "active"
        # Paid reuse and channel scope come from the agreement file the roster names.
        paid, channels, paid_platforms = "unknown", None, None
        if creator and creator["agreement_file"]:
            stats["agreements_expected"] += 1
            apath = ws / creator["agreement_file"]
            if apath.is_file():
                stats["agreements_read"] += 1
                paid, channels, paid_platforms, conflict = parse_agreement(
                    apath.read_text(encoding="utf-8", errors="replace"), list(platforms))
                if conflict:
                    notes.append("paid-reuse-conflict")
                if paid == "unknown" and not conflict:
                    notes.append("paid-reuse-not-stated")
            else:
                notes.append("agreement-file-missing")
        elif creator:
            notes.append("no-agreement-file")
        if channels is None:
            notes.append("channels-not-stated")
        elif channels:
            notes.append("channels-from-agreement:" + "+".join(channels))
        else:
            notes.append("channels-none-granted")
        # Holds: reasons outside the rights window that stop reuse until a person clears them.
        stats["approvals_expected"] += 1
        verdict, approved_on, approval_text = read_approval(ws, slug, p["approval_id"])
        if verdict == "missing":
            holds.append("no-approval")
        else:
            stats["approvals_read"] += 1
            if verdict == "stop":
                holds.append("approval-stop")
            elif verdict == "unread":
                holds.append("approval-unread")
        seen = p["disclosure_seen"]
        if seen == "no":
            holds.append("disclosure-missing")
        elif seen == "partial":
            holds.append("disclosure-partial")
        elif seen != "yes":
            holds.append("disclosure-unchecked")
        checks = [p["check_day1"], p["check_day7"], p["check_day30"]]
        if "removed" in checks:
            holds.append("post-removed")
        if "edited" in checks:
            notes.append("post-edited:reuse-the-approved-version")
        if creator:
            if creator["brand_safety_flag"] == "exclude":
                holds.append("brand-safety-exclude")
            elif creator["brand_safety_flag"] == "review":
                holds.append("brand-safety-review")
            if creator["status"] == "excluded":
                holds.append("creator-excluded")
        forms = [f for f in p["disclosure_form"].split(";") if f]
        travels = [f for f in forms if f in ("on_screen", "spoken")]
        notes.append("disclosure-in-asset:" + "+".join(travels) if travels else "disclosure-not-in-asset")
        if p["code_in_post"]:
            notes.append(f"code-in-asset:{p['code_in_post']}")
        # Claims: which approved statements the approval record carries, and whether section 7
        # changed after the asset was approved.
        if verdict == "missing":
            present = ""
        elif none_cleared:
            # No claim is cleared, so an asset may be reused only if its approval quotes no product statement.
            present = "none"
            n_statements = product_statement_count(approval_text)
            if n_statements is None:
                holds.append("product-statements-unread")
            elif n_statements:
                holds.append("product-statement-without-cleared-claim")
        else:
            body = norm(approval_text)
            found = [f"A{i}" for i, c in enumerate(claims, start=1) if c and c in body]
            present = ";".join(found) if found else "none"
        basis = approved_on or posted
        if basis is None:
            notes.append("approval-date-unknown")
        later = [d for d in changes if basis and d > basis]
        if later:
            notes.append(f"reapproval-needed-after:{later[-1]}")
        # Paid only where the agreement granted it AND programme section 3 allows paid for the platform.
        paid_keys = []
        if paid == "yes":
            allowed = [k for k, v in platforms.items() if v in ("yes", "with-conditions")]
            if paid_platforms is None:
                paid_keys = allowed
                notes.append("paid-platforms-not-stated")
            else:
                paid_keys = [k for k in allowed if k in paid_platforms]
                refused_by_table = [k for k in paid_platforms if k not in allowed]
                if refused_by_table:
                    notes.append("paid-platform-not-allowed-by-section-3:" + "+".join(refused_by_table))
        owned = list(OWNED_CHANNELS if channels is None else channels)
        absent = [c for c in owned if c not in brand_codes]
        if absent:
            notes.append("brand-has-no:" + "+".join(absent))
        uses = [c for c in owned if c in brand_codes]
        for key in paid_keys:
            uses.append(("paid:" if platforms[key] == "yes" else "paid-with-conditions:") + key)
        if status in ("active", "expiring") and not holds and not uses:
            holds.append("no-channel-granted")
        suggested = ";".join(uses) if status in ("active", "expiring") and not holds else "none"
        rows.append({
            "publication_id": p["publication_id"], "creator_ref": ref, "format": p["format"],
            "platform": p["platform"], "rights_until": rights_until.isoformat() if rights_until else "",
            "rights_status": status, "checked_as_of": as_of.isoformat(), "paid_reuse": paid,
            "approved_claims_present": present, "suggested_uses": suggested,
            "holds": ";".join(holds) if holds else "none", "notes": ";".join(notes),
            "_approval_id": p["approval_id"],
        })
    stats["none_cleared"] = none_cleared
    stats["merged"] = sum(1 for c in creators if c["status"] == "ended" and re.search(r"merged into c-", c["notes"], re.I))
    stats["brand"] = brand
    return rows, stats, len(publications), len(creators) - stats["merged"]


def write_inventory(ws, slug, rows, as_of):
    path = ws / "campaigns" / slug / "reuse" / "inventory.csv"
    old = []
    if path.is_file():
        old = read_csv(path, INVENTORY_HEADER, f"campaigns/{slug}/reuse/inventory.csv")
    new_ids = {r["publication_id"] for r in rows}
    old_by_id = {r["publication_id"]: r for r in old}
    public = [{k: r[k] for k in INVENTORY_HEADER} for r in rows]
    added = sum(1 for r in public if r["publication_id"] not in old_by_id)
    changed = sum(1 for r in public if r["publication_id"] in old_by_id and old_by_id[r["publication_id"]] != r)
    kept = []
    for r in old:
        if r["publication_id"] not in new_ids:
            r = dict(r)
            r["suggested_uses"] = "none"
            if "orphan" not in r["notes"]:
                r["notes"] = ";".join(x for x in [r["notes"], f"orphan:not-in-publications-as-of-{as_of}"] if x)
            kept.append(r)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=INVENTORY_HEADER, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows + kept:
            w.writerow(r)
    return path, len(old), added, changed, len(kept)


def plan_rows(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    header, rows, found = None, [], False
    for n, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        cs = cells(s)
        if header is None:
            low = [c.lower() for c in cs]
            if "publication_id" in low and "channel" in low and "end" in low:
                header, found = low, True
                missing = [c for c in PLAN_COLUMNS if c not in header]
                if missing:
                    raise BadInput(f"{path.name}: the placements table lacks column(s) {', '.join(missing)}; use assets/reuse-plan-template.md.")
            continue
        if is_separator(cs) or not any(cs):
            continue
        row = dict(zip(header, cs))
        row["_line"] = n
        rows.append(row)
    return rows, found


def take_down_list(ws, slug, inventory, as_of):
    by_id = {r["publication_id"]: r for r in inventory}
    items = []
    folder = ws / "campaigns" / slug / "reuse"
    for plan in sorted(folder.glob("plan-*.md")):
        rows, _ = plan_rows(plan)
        for r in rows:
            if r.get("removed_on"):
                continue
            try:
                end = iso(r.get("end", ""), f"{plan.name} line {r['_line']} end")
            except BadInput:
                continue  # the plan check reports malformed dates
            if end is None:
                continue
            asset = by_id.get(r.get("publication_id", ""))
            ru = iso(asset["rights_until"], "inventory") if asset and asset["rights_until"] else None
            if asset is None or asset["rights_status"] in ("expired", "unknown", "not-granted"):
                why = "rights expired, unknown or not granted: take down now"
            elif ru and end > ru:
                why = f"planned end is after the rights end {ru}: take down by {ru}"
            elif end < as_of:
                why = f"end date {end} has passed: take down now and record removed_on"
            elif (end - as_of).days <= EXPIRING_DAYS:
                why = f"take down by {end}"
            else:
                continue
            items.append(f"{plan.name}: {r.get('publication_id','')} on {r.get('channel','')} ({r.get('placement','')}): {why}")
    return items


def check_plan(ws, slug, path, inventory, roles, brand):
    by_id = {r["publication_id"]: r for r in inventory}
    rows, found = plan_rows(path)
    if not found:
        raise BadInput(f"{path.name} has no placements table with publication_id, channel and end columns; use assets/reuse-plan-template.md.")
    failures = []
    for r in rows:
        where = f"{path.name} line {r['_line']}"
        pid = r.get("publication_id", "")
        asset = by_id.get(pid)
        if asset is None:
            failures.append(f"{where}: {pid or '(blank)'} is not in this campaign's inventory")
            continue
        if asset["suggested_uses"] == "none":
            failures.append(f"{where}: {pid} cannot be reused (rights {status_text(asset)}; holds {asset['holds']})")
            continue
        allowed = asset["suggested_uses"].split(";")
        channel = r.get("channel", "")
        if channel not in allowed:
            failures.append(f"{where}: {pid} channel '{channel}' is not allowed for this asset (allowed: {', '.join(allowed)})")
        try:
            start = iso(r.get("start", ""), f"{where} start")
            end = iso(r.get("end", ""), f"{where} end")
        except BadInput as e:
            failures.append(str(e).replace("; correct it and run again.", ""))
            start = end = None
        if start is None or end is None:
            failures.append(f"{where}: {pid} needs both a start and an end date; every placement comes down by its end date")
        else:
            ru = dt.date.fromisoformat(asset["rights_until"])
            if start > end:
                failures.append(f"{where}: {pid} starts after it ends")
            if end > ru:
                failures.append(f"{where}: {pid} ends after rights end ({end} is after {ru})")
        aid = r.get("approval_id", "")
        if not aid.startswith(f"{slug}--{asset['creator_ref']}--"):
            failures.append(f"{where}: {pid} approval_id '{aid}' is not an approval for {asset['creator_ref']} in {slug}")
        else:
            verdict, approved_on, _ = read_approval(ws, slug, aid)
            if verdict != "approve":
                failures.append(f"{where}: {pid} approval {aid} is {verdict}, not approve")
            need = [n.split(":", 1)[1] for n in asset["notes"].split(";") if n.startswith("reapproval-needed-after:")]
            if need:
                after = dt.date.fromisoformat(need[0])
                if approved_on is None or approved_on < after:
                    failures.append(f"{where}: {pid} section 7 changed on {after}; the row needs an approval dated on or after it (re-run content-approval)")
        cut = r.get("cut", "").lower()
        if cut not in CUTS:
            failures.append(f"{where}: {pid} cut '{r.get('cut','')}' is not one of {', '.join(CUTS)} (references/reuse-formats.md)")
        elif cut == "other" and aid == asset["_approval_id"]:
            failures.append(f"{where}: {pid} a cut of type other needs a new content-approval record, not the original {aid}")
        cd = r.get("credit and disclosure", "")
        if not cd or re.search(r"\[open\]|\btbd\b", cd, re.I):
            failures.append(f"{where}: {pid} credit and disclosure line is empty or open")
        shown = r.get("code shown", "").lower()
        if shown not in ("yes", "no"):
            failures.append(f"{where}: {pid} 'code shown' must be yes or no (the owner decides)")
        role = r.get("owner_role", "").lower()
        if role not in roles:
            failures.append(f"{where}: {pid} owner_role '{r.get('owner_role','')}' is not a role in programme section 10")
        elif channel.startswith("paid"):
            if role != "owner":
                failures.append(f"{where}: {pid} a paid row is the owner's decision; set owner_role to owner")
        elif channel in OWNED_CHANNELS:
            publishers = sorted({rl for code, _, rl in brand if code == channel and rl})
            if not publishers:
                failures.append(f"{where}: {pid} programme section 3 names no publishing role for {channel}; add it to the brand's own channels line")
            elif role not in publishers:
                failures.append(f"{where}: {pid} owner_role '{r.get('owner_role','')}' does not publish on {channel}; programme section 3 names {', '.join(publishers)}")
    return rows, failures


def status_text(r):
    """The rights status, with its reason when it is unknown."""
    if r["rights_status"] == "not-granted":
        return "not-granted (no-rights-granted)"
    if r["rights_status"] != "unknown":
        return r["rights_status"]
    why = [n for n in r["notes"].split(";")
           if n in ("not-in-roster", "no-written-agreement", "no-rights-date", "rights-from-posting-undated",
                    "rights-from-posting-not-yet-live") or n.startswith("creator-merged-into:")]
    return "unknown (" + (why[0] if why else "reason not recorded") + ")"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build campaigns/<slug>/reuse/inventory.csv from publications, the roster, agreements and "
                    "approvals; mark each asset active, expiring, expired, not-granted or unknown as of a date; refuse "
                    "expired, not-granted, unknown or held assets; optionally check a reuse plan against the inventory. No network.")
    ap.add_argument("workspace", help="the workspace folder (program/, data/, campaigns/ ...)")
    ap.add_argument("--campaign", required=True, help="campaign_slug, for example 2026-12-holiday-tote")
    ap.add_argument("--as-of", required=True, help="the date rights are judged on, YYYY-MM-DD")
    ap.add_argument("--asset", action="append", default=[], help="a publication_id the person wants to reuse; repeatable")
    ap.add_argument("--check-plan", help="a plan file to check, relative to the workspace or absolute")
    a = ap.parse_args(argv)
    try:
        ws = pathlib.Path(a.workspace)
        if not ws.is_dir():
            raise BadInput(f"workspace {ws} is not a folder; pass the workspace path first.")
        if not SLUG_RE.match(a.campaign):
            raise BadInput(f"campaign '{a.campaign}' is not a campaign_slug (YYYY-MM-name in lower-case kebab).")
        as_of = iso(a.as_of, "--as-of")
        if as_of is None:
            raise BadInput("--as-of needs a date in the form YYYY-MM-DD.")
        for pid in a.asset:
            if not PUB_RE.match(pid):
                raise BadInput(f"--asset '{pid}' is not a publication_id (p- followed by six lower-case letters or digits).")
        prog_path = ws / "program" / "program.md"
        if not prog_path.is_file():
            raise BadInput("program/program.md not found; run program-setup with the owner first.")
        program = sections_of(prog_path.read_text(encoding="utf-8", errors="replace"))
        rows, stats, n_pub, n_cre = build_inventory(ws, a.campaign, as_of, program)
        by_id = {r["publication_id"]: r for r in rows}
        for pid in a.asset:
            if pid not in by_id:
                raise BadInput(f"--asset {pid} is not a publication of campaign {a.campaign} in data/publications.csv.")
        plan_path = None
        roles = []
        if a.check_plan:
            plan_path = pathlib.Path(a.check_plan)
            if not plan_path.is_absolute():
                plan_path = ws / plan_path
            if not plan_path.is_file():
                raise BadInput(f"plan file {plan_path} not found.")
            roles = parse_roles(program.get(10, []))
            if not roles:
                raise BadInput("Programme section 10 (Roles and approvals) lists no role; the plan check needs it to read owner_role.")
        inv_path, n_old, added, changed, kept = write_inventory(ws, a.campaign, rows, as_of)
        plan_result = check_plan(ws, a.campaign, plan_path, rows, roles, stats["brand"]) if plan_path else None
        takedown = take_down_list(ws, a.campaign, rows, as_of)
    except BadInput as e:
        print(f"content-reuse rights check stopped: {e}")
        return 1

    out = []
    out.append(f"content-reuse rights check, campaign {a.campaign}, as of {as_of} (expiring window: {EXPIRING_DAYS} days)")
    wb = ws / "data" / "creator-programme.xlsx"
    if wb.is_file():
        newest_csv = max((ws / "data" / f).stat().st_mtime for f in ("creators.csv", "publications.csv"))
        if wb.stat().st_mtime > newest_csv:
            out.append("warning: data/creator-programme.xlsx is newer than the CSVs; if it was edited, run creator-roster import-xlsx and run this again")
    out.append(f"read: program/program.md; data/publications.csv ({n_pub} rows, {len(rows)} for this campaign); data/creators.csv ({n_cre} rows counted, {stats['merged']} merged duplicates not counted)")
    if stats["none_cleared"]:
        out.append("claims: programme section 7 records that no claim is cleared yet; approved_claims_present is none for "
                   "every asset, and an asset whose approval record quotes a product statement is held")
    out.append("brand channels (programme section 3): " + "; ".join(
        f"{code or 'unrecognised'} by {role or 'no role named'}" for code, _, role in stats["brand"]))
    out.append(f"read: agreement files {stats['agreements_read']} of {stats['agreements_expected']} named; approval records {stats['approvals_read']} of {stats['approvals_expected']} expected")
    out.append(f"wrote: {inv_path.relative_to(ws)} (read {n_old} rows, added {added}, changed {changed}, kept {kept} no longer in publications)")
    counts = {s: sum(1 for r in rows if r["rights_status"] == s) for s in ("active", "expiring", "expired", "not-granted", "unknown")}
    held = sum(1 for r in rows if r["holds"] != "none")
    usable = sum(1 for r in rows if r["suggested_uses"] != "none")
    out.append("rights: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f"; held {held}; usable for reuse {usable} of {len(rows)}")
    out.append("assets:")
    for r in rows:
        out.append(f"  {r['publication_id']} {r['creator_ref']} {r['platform']} {r['format']}: {status_text(r)}"
                   f" until {r['rights_until'] or ('none granted' if r['rights_status'] == 'not-granted' else 'unknown')}; paid reuse {r['paid_reuse']}; holds {r['holds']};"
                   f" suggested {r['suggested_uses']}")
    refused = []
    for pid in a.asset:
        r = by_id[pid]
        if r["suggested_uses"] == "none":
            refused.append(f"  {pid}: refused (rights {status_text(r)}; holds {r['holds']})")
    if a.asset:
        out.append("requested assets:")
        out.extend(refused or ["  every requested asset may be reused within its suggested uses"])
    out.append("take-down list from plans in this campaign's reuse folder:")
    out.extend(["  " + t for t in takedown] or ["  nothing due within the window"])
    plan_fail = []
    if plan_result is not None:
        prow, plan_fail = plan_result
        out.append(f"plan check: {plan_path.name}, {len(prow)} placement rows, {len(plan_fail)} failing")
        out.extend("  " + f for f in plan_fail)
    status = 2 if (refused or plan_fail) else 0
    if status == 2:
        out.append("result: partial; a requested asset was refused or the plan has failing rows (listed above)")
    else:
        out.append("result: complete")
    print("\n".join(out))
    return status


if __name__ == "__main__":
    sys.exit(main())
