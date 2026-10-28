#!/usr/bin/env python3
"""Check a creator's caption, and optionally a transcript, against the programme file.

Part of the content-approval skill. Run with python3 -I. Reads, never writes:
  <workspace>/program/program.md   sections 3, 7, 8 and 9
  <workspace>/data/creators.csv    the creator's code and tracked link
  ../references/approval-checklist.md section 5 (caption window, spoken window, cue words)

Programme sections 7 and 8 are read only in the shapes program-setup writes:
  Approved:  - <product>: "<verbatim wording>" [owner]
  Forbidden: phrases in straight double quotes
  Section 8: one indented line per platform under the wording field,
             - <platform>: "<wording>" <placement> [owner]
Any other shape is reported, never read loosely. The spoken form is the
placement text's "spoken: <phrase>", ending at ";" or the mark.

File arguments given as relative paths are looked for in the workspace
first, then in the current folder.

Each output line starts with a checklist line id from approval-checklist.md
section 1, then one of: ok, FINDING, SKIPPED (a check this script runs but
could not, for want of input), REVIEWER (never checkable by a script), INFO.

Exit 0: no FINDING and no SKIPPED. Exit 2: at least one FINDING or SKIPPED,
each printed. Exit 1: bad input or a usage error, with one sentence saying
what to fix.
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "references"))
from brand_context import brand_name, claim_cues, value as context_value

SKILL_DIR = Path(__file__).resolve().parent.parent
CHECKLIST = SKILL_DIR / "references" / "approval-checklist.md"

# Source: the pack's references/schemas.md section 4 (data/creators.csv header, in order).
CREATORS_HEADER = [
    "creator_ref", "display_name", "primary_platform", "primary_handle", "profile_url",
    "other_platforms", "tier", "followers_primary", "followers_as_of", "engagement_rate_pct",
    "engagement_as_of", "niche_tags", "audience_fit_score", "brand_safety_flag", "contact_path",
    "contact_email", "status", "compensation_model", "commission_rate_pct", "flat_fee", "code",
    "affiliate_link", "rail", "agreement_date", "agreement_file", "usage_rights_until",
    "exclusivity_until", "first_campaign", "last_activity", "notes",
]
# Source: schemas.md section 4, allowed values of primary_platform.
PLATFORMS = ["instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast",
             "newsletter", "bluesky", "threads", "other"]
# Source: schemas.md section 6, allowed values of format.
FORMATS = ["video", "reel", "story", "post", "thread", "newsletter", "podcast", "live", "other"]
# Source: schemas.md section 2 (identifier shapes).
REF_RE = re.compile(r"^c-[a-z0-9]{6}$")
SLUG_RE = re.compile(r"^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
# Source: program-template.md, first section (the four source marks).
MARK_RE = re.compile(r"\[(owner|observed|default|open)\]")
# Source: program-template.md v0.1.2, sections 8 and 9: the field labels this script reads.
# The template says the value follows the label and the label text is never edited.
LABEL_WORDING = ("Required disclosure wording and placement, per platform (text at the start of the caption, "
                 "spoken aloud and on screen in video, platform paid-partnership tool switched on in addition):")
LABEL_NONCOUNT = ("Words that do not count as disclosure (for example `#sp`, `#collab`, `#ambassador` alone, "
                  "`thanks to`):")
LABEL_REDLINES = "Redlines: topics, words, imagery or associations the brand will not appear beside:"
# The only shapes read from programme sections 7 and 8 (the lead's ruling, 2026-10-20; program-setup
# writes them so). Anything else is reported, never read loosely.
APPROVED_RE = re.compile(r'^- (?P<product>[^"\n]+?):\s*"(?P<wording>[^"\n]+)"\s*\[owner\]\s*$')
PLATFORM_LINE_RE = re.compile(
    r'^[ \t]+- (?P<platform>[^:"\n]+):\s*"(?P<wording>[^"\n]+)"(?P<placement>[^\n]*?)\s*\[owner\]\s*$')
DOUBLE_QUOTED_RE = re.compile(r'"([^"\n]+)"')
# The spoken form in a platform line's placement text, ending at ";" or the mark (the lead's ruling, 2026-10-21).
SPOKEN_RE = re.compile(r"\bspoken:\s*([^;]*)")
QUOTED_RE = re.compile(r'"([^"]+)"|“([^”]+)”|`([^`]+)`')
URL_RE = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s)\]]*)?", re.I)
# A code is upper case letters and digits, 4 to 20 characters (schemas.md section 2).
CODE_NEAR_RE = re.compile(r"\b[Cc][Oo][Dd][Ee]\b[\s:]*[\"'“‘]?([A-Z0-9]{4,20})\b")


class BadInput(Exception):
    pass


class Parser(argparse.ArgumentParser):
    """Usage errors exit 1, not argparse's 2, which the contract keeps for a partial run."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: {message}; see --help.", file=sys.stderr)
        sys.exit(1)


def norm(text):
    text = unicodedata.normalize("NFKC", text)
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(a, b)
    return text


def read(path, what, normalise=True):
    try:
        text = Path(path).read_text(encoding="utf-8")
        return norm(text) if normalise else text
    except FileNotFoundError:
        raise BadInput(f"{what} not found at {path} (a relative path is looked for in the workspace, "
                       "then in the current folder); check the path.")
    except UnicodeDecodeError:
        raise BadInput(f"{what} at {path} is not UTF-8 text; save it as UTF-8 and rerun.")


def resolve(ws, arg):
    """A relative file argument is looked for in the workspace first, then in the current folder."""
    path = Path(arg)
    if path.is_absolute():
        return path
    return ws / path if (ws / path).exists() else path


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^## (\d+)\. ", line)
        if m:
            cur = int(m.group(1))
            out[cur] = []
        elif line.startswith("## "):
            cur = None
        elif cur is not None:
            out[cur].append(line)
    return out


def subsections(lines):
    parts, cur = {}, None
    for line in lines:
        m = re.match(r"^### (.+?)\s*$", line)
        if m:
            cur = m.group(1)
            parts[cur] = []
        elif cur is not None:
            parts[cur].append(line)
    return parts


def bullets(lines):
    """Top-level bullets with their indented detail lines (template line rules)."""
    out, cur = [], None
    for line in lines:
        if line.startswith("- "):
            cur = (line[2:].rstrip(), [])
            out.append(cur)
        elif cur is not None and line[:1] in (" ", "\t") and line.strip():
            cur[1].append(line.strip().lstrip("-* ").strip())
        else:
            cur = None
    return out


def after_label(text):
    """The value part of a field line: text after the first colon outside brackets."""
    depth = 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return text[:i], text[i + 1:]
    return "", text


def quoted(text):
    return [next(g for g in m if g).strip() for m in QUOTED_RE.findall(text) if any(m)]


def is_open(text):
    return "[open]" in text


def phrase_rx(phrase, keep_hash=True):
    p = norm(phrase).lower()
    if not keep_hash:
        p = p.replace("#", " ")
    tokens = re.findall(r"[#@%]?\w+", p)
    if not tokens:
        return None
    body = r"[\W_]+".join(re.escape(t) for t in tokens)
    return re.compile(r"(?<![\w#@])" + body + r"(?!\w)", re.I)


def first_hit(rx, text):
    m = rx.search(text) if rx else None
    return m.start() if m else None


def sentence_at(text, pos, width=110):
    start = max(text.rfind(c, 0, pos) for c in ".!?\n") + 1
    ends = [i for i in (text.find(c, pos) for c in ".!?\n") if i >= 0]
    end = min(ends) + 1 if ends else len(text)
    s = " ".join(text[start:end].split())
    return s if len(s) <= width else s[: width - 3] + "..."


def tokens_of(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def platform_matches(key, platform):
    toks = tokens_of(key)
    aliases = {"x": {"x", "twitter"}}.get(platform, {platform})
    return any(a in toks or a + "s" in toks for a in aliases)


def load_settings():
    if not CHECKLIST.exists():
        raise BadInput(f"{CHECKLIST} is missing; reinstall the content-approval skill folder.")
    text = read(CHECKLIST, "the approval checklist")
    sec = sections(text).get(5)
    if not sec:
        raise BadInput("references/approval-checklist.md has no section 5 (settings); reinstall the skill folder.")
    window, origin, spoken, formats, cues = {}, {}, None, None, []
    for line in sec:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or re.fullmatch(r":?-{3,}:?", cells[0]):
            continue
        key, value = cells[0], cells[1]
        if key in PLATFORMS and value.isdigit():
            window[key] = int(value)
            origin[key] = cells[2]
        elif key == "spoken window" and value.isdigit():
            spoken = int(value)
        elif key == "formats that need a transcript":
            formats = [v.strip() for v in value.split(";") if v.strip()]
        elif re.fullmatch(r"[a-z-]+", key) and ";" in value:
            cues.append((key, [v.strip() for v in value.split(";") if v.strip()]))
    missing = [p for p in PLATFORMS if p not in window]
    if missing or spoken is None or formats is None or not cues:
        raise BadInput("references/approval-checklist.md section 5 is incomplete (caption window for "
                       f"{', '.join(missing) or 'all platforms'}, spoken window, formats or cue words); "
                       "restore the table rows.")
    return window, origin, spoken, formats, cues


def load_programme(ws):
    path = ws / "program" / "program.md"
    if not path.exists():
        raise BadInput(f"{path} not found; run program-setup with the owner first.")
    secs = sections(read(path, "the programme file", normalise=False))
    for n in (3, 7, 8, 9):
        if n not in secs:
            raise BadInput(f"program/program.md has no section {n}; restore the heading from the template.")
    return secs


def section3_row(lines, platform):
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("platform",) or re.fullmatch(r":?-{3,}:?", cells[0]):
            continue
        if platform_matches(cells[0], platform) or (platform == "other" and cells[0].lower() == "other"):
            return cells
    return None


def approved_claims(lines):
    """Approved lines in the one shape: - <product>: "<verbatim wording>" [owner]."""
    parts = subsections(lines)
    body = next((b for t, b in parts.items() if t.startswith("Approved")), None)
    if body is None:
        raise BadInput("program/program.md section 7 has no '### Approved claims' heading; restore it from the template.")
    claims, notes = [], []
    for line in body:
        if not line.startswith("- "):
            continue  # indented detail lines and prose are not claims
        text = line.rstrip()
        m = APPROVED_RE.match(text)
        if m:
            claims.append((m.group("wording"), m.group("product").strip()))
        elif is_open(text):
            notes.append(("INFO", f"section 7 Approved line marked [open], not approved: {text[2:][:80]}"))
        elif "[owner]" not in text:
            notes.append(("INFO", f"section 7 Approved line without [owner], not approved: {text[2:][:80]}"))
        else:
            notes.append(("FINDING", f"section 7 Approved line not in the shape - <product>: \"<verbatim wording>\" "
                          f"[owner], so not read as approved: {text[2:][:80]}; ask program-setup to rewrite it"))
    return claims, notes


def forbidden_phrases(lines):
    """Phrases in straight double quotes on Forbidden lines and their indented detail lines."""
    parts = subsections(lines)
    body = next((b for t, b in parts.items() if t.startswith("Forbidden")), None)
    if body is None:
        raise BadInput("program/program.md section 7 has no '### Forbidden claims' heading; restore it from the template.")
    out, described = [], 0
    for text, detail in bullets(body):
        if is_open(text):
            continue
        label, value = after_label(text)
        # Template labels carry no quotes, so every double-quoted string on the line is a phrase.
        found = DOUBLE_QUOTED_RE.findall(text) + [q for d in detail if not is_open(d) for q in DOUBLE_QUOTED_RE.findall(d)]
        out += [(phrase, (label or text).strip()) for phrase in found]
        if not found and label and MARK_RE.sub("", value).strip():
            described += 1
    return out, described


def open_contradictions(lines):
    intro = []
    for line in lines:
        if line.startswith("### "):
            break
        intro.append(line)
    return [MARK_RE.sub("", t).strip() for t, _ in bullets(intro) if is_open(t)]


def field(lines, label):
    """Value and detail lines of a field, found by its template label."""
    short_label = re.split(r" \(|:", label, maxsplit=1)[0]
    for text, detail in bullets(lines):
        flat = " ".join(text.split())
        if flat.startswith(label):
            return flat[len(label):], detail
        if flat.startswith(short_label):
            return after_label(flat)[1], detail
    return None, []


def disclosure_wordings(lines, platform):
    """The platform's line under the wording field: - <platform>: "<wording>" <placement> [owner].

    Returns (wording, placement, spoken form or None, notes); wording is None when the platform has
    no line in that shape.
    """
    notes, found, in_field = [], [], False
    for line in lines:
        if line.startswith("- "):
            in_field = " ".join(line[2:].split()).startswith(LABEL_WORDING)
            if in_field and DOUBLE_QUOTED_RE.search(line[2 + len(LABEL_WORDING):]):
                notes.append(("INFO", "section 8: wording on the field line itself is not read; "
                              "the wording goes on the indented platform lines"))
            continue
        if not in_field:
            continue
        if not line.strip() or line[:1] not in (" ", "\t"):
            in_field = False  # a blank or unindented line ends the field (template line rules)
            continue
        m = PLATFORM_LINE_RE.match(line.rstrip())
        key = m.group("platform").strip() if m else line.strip().lstrip("- ").split(":", 1)[0].strip()
        if not m:
            status = "FINDING" if key == platform else "INFO"
            notes.append((status, f"section 8 line not in the shape - <platform>: \"<wording>\" <placement> "
                          f"[owner], so not read: {line.strip()[:80]}"))
        elif key not in PLATFORMS:
            notes.append(("INFO", f"section 8 line for '{key}' is not read: the platform is written as a roster "
                          f"value ({', '.join(PLATFORMS)})"))
        elif key == platform:
            found.append(m)
    if not found:
        return None, None, None, notes
    if len(found) > 1:
        notes.append(("FINDING", f"section 8 has {len(found)} lines for {platform}; only the first is read"))
    m = found[0]
    placement = m.group("placement").strip()
    if DOUBLE_QUOTED_RE.search(placement):
        notes.append(("INFO", f"section 8, {platform}: a second quoted string is read as placement, not as "
                      "accepted wording; one wording per platform line"))
    sm = SPOKEN_RE.search(placement)
    spoken = sm.group(1).strip() if sm and sm.group(1).strip() else None
    return m.group("wording"), placement, spoken, notes


def noncounting(lines):
    value, detail = field(lines, LABEL_NONCOUNT)
    if value is None:
        return []
    words = [] if is_open(value) else quoted(value)
    return words + [q for d in detail if not is_open(d) for q in quoted(d)]


def redline_words(lines):
    value, detail = field(lines, LABEL_REDLINES)
    if value is None:
        return []
    words = [] if is_open(value) else quoted(value)
    return words + [q for d in detail if not is_open(d) for q in quoted(d)]


def roster_row(ws, ref):
    path = ws / "data" / "creators.csv"
    if not path.exists():
        raise BadInput(f"{path} not found; set up the roster with creator-roster first.")
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        if header != CREATORS_HEADER:
            miss = [c for c in CREATORS_HEADER if c not in header]
            extra = [c for c in header if c not in CREATORS_HEADER]
            raise BadInput("data/creators.csv header differs from schemas.md section 4"
                           + (f"; missing: {', '.join(miss)}" if miss else "")
                           + (f"; extra: {', '.join(extra)}" if extra else "")
                           + ("; columns out of order" if not miss and not extra else "")
                           + "; fix it with creator-roster.")
        rows = [dict(zip(header, r)) for r in reader]
    match = [r for r in rows if r["creator_ref"] == ref]
    if not match:
        raise BadInput(f"creator_ref {ref} is not in data/creators.csv; add the creator with creator-roster first.")
    return match[0], len(rows), path


def bare_url(url):
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/")


def main(argv=None):
    ap = Parser(
        description="Check a creator caption (and transcript) against programme sections 3, 7, 8 and 9 "
                    "and the roster's code and link. Writes nothing.")
    ap.add_argument("workspace", help="the client's workspace folder")
    ap.add_argument("--campaign", required=True, help="campaign_slug, for example 2026-12-holiday-tote")
    ap.add_argument("--creator", required=True, help="creator_ref, for example c-7k2m9q")
    ap.add_argument("--platform", required=True, choices=PLATFORMS)
    ap.add_argument("caption", help="UTF-8 text file holding the caption exactly as submitted; a relative path "
                    "is looked for in the workspace first, then in the current folder")
    ap.add_argument("--transcript", help="UTF-8 text file holding the spoken words, for video or audio; "
                    "resolved like the caption")
    ap.add_argument("--format", choices=FORMATS, help="the deliverable format; decides whether a transcript is expected")
    ap.add_argument("--brand-name", help="explicit brand name for transcript timing; otherwise programme section 1 Brand name")
    ap.add_argument("--product", help="the product as named in programme section 7; flags statements approved only for another product")
    a = ap.parse_args(argv)

    out, counts = [], {"FINDING": 0, "SKIPPED": 0}

    def say(line_id, status, msg):
        if status in counts:
            counts[status] += 1
        out.append(f"{line_id:<21} {status:<8} {msg}")

    try:
        ws = Path(a.workspace)
        if not ws.is_dir():
            raise BadInput(f"workspace {ws} is not a folder; pass the workspace path first.")
        if not SLUG_RE.match(a.campaign):
            raise BadInput(f"campaign '{a.campaign}' is not a campaign_slug (YYYY-MM-name); check the slug.")
        if not REF_RE.match(a.creator):
            raise BadInput(f"creator '{a.creator}' is not a creator_ref (c- and six letters or digits); use the roster's ref, never a handle.")
        if not (ws / "campaigns" / a.campaign).is_dir():
            raise BadInput(f"campaigns/{a.campaign} does not exist in the workspace; check the slug or run campaign-plan.")
        window, window_origin, spoken_window, transcript_formats, cues = load_settings()
        secs = load_programme(ws)
        try:
            brand = brand_name(secs.get(1, []), a.brand_name)
        except ValueError as error:
            raise BadInput(str(error))
        if context_value(secs[7], ("Claim review cues:",)) is not None:
            cues = [("configured-product-claim", claim_cues(secs[7], ()))]
        caption_raw = read(resolve(ws, a.caption), "the caption file")
        caption = caption_raw.lstrip()
        transcript = read(resolve(ws, a.transcript), "the transcript file") if a.transcript else None
        row, nrows, roster_path = roster_row(ws, a.creator)
        claims, claim_notes = approved_claims(secs[7])
        forbidden, described = forbidden_phrases(secs[7])
        cell = section3_row(secs[3], a.platform)
        organic = MARK_RE.sub("", cell[1]).strip().strip("`").lower() if cell and len(cell) > 1 else ""
        barred = re.match(r"^no\b", organic) is not None
        wording, placement, spoken_form, s8_notes = disclosure_wordings(secs[8], a.platform)
        wordings = [wording] if wording else []
        if not wordings and not barred:
            raise BadInput(f"program/program.md section 8 has no line for {a.platform} under the disclosure wording "
                           f"field in the shape - {a.platform}: \"<wording>\" <placement> [owner]; ask the owner "
                           "to fill it with program-setup.")
    except (BadInput, ValueError) as e:
        print(f"check_caption.py: {e}", file=sys.stderr)
        return 1

    out.append(f"check_caption.py  campaign {a.campaign}  creator {a.creator}  platform {a.platform}"
               f"  format {a.format or 'not given'}  product {a.product or 'not given'}")
    out.append(f"read: program/program.md sections 1, 3, 7, 8, 9; data/creators.csv ({nrows} rows read); "
               "references/approval-checklist.md section 5; nothing written")
    xlsx = ws / "data" / "creator-programme.xlsx"
    if xlsx.exists():
        say("code-link", "INFO", "this check reads data/creators.csv, not the workbook; if the workbook was "
            "edited since the last import, run creator-roster import-xlsx first (creator-roster check says "
            "whether it was)")

    # Platform (section 3)
    if cell is None:
        say("platform", "FINDING", f"programme section 3 has no row for {a.platform}; the owner rules before this runs (ask)")
    elif not organic:
        say("platform", "FINDING", f"section 3 row '{cell[0]}' has no decision for organic creator posts; the owner rules (ask)")
    elif barred:
        say("platform", "FINDING", f"section 3 row '{cell[0]}' says organic creator posts: no; this is a stop")
    elif organic.startswith("unknown"):
        say("platform", "FINDING", f"section 3 row '{cell[0]}' says unknown; the owner rules (ask)")
    else:
        say("platform", "ok", f"section 3 row '{cell[0]}', organic creator posts: {organic}")
        if organic.startswith("with conditions"):
            say("platform", "REVIEWER", "check each condition written in that row against the submission")

    # Claims (section 7)
    for wording, product in claims:
        rx = phrase_rx(wording)
        for where, text in (("caption", caption), ("transcript", transcript)):
            pos = first_hit(rx, text) if text else None
            if pos is None:
                continue
            label = f"\"{wording}\" (approved for {product or 'a product section 7 does not name'})"
            if a.product and product and phrase_rx(product).search(a.product) is None \
                    and phrase_rx(a.product).search(product) is None:
                say("claims", "FINDING", f"{where} char {pos}: {label} is not approved for {a.product}")
            else:
                say("claims", "ok", f"{where} char {pos}: approved statement {label}")
    for phrase, reason in forbidden:
        rx = phrase_rx(phrase)
        for where, text in (("caption", caption), ("transcript", transcript)):
            pos = first_hit(rx, text) if text else None
            if pos is not None:
                say("claims", "FINDING", f"{where} char {pos}: forbidden phrase \"{phrase}\" "
                    f"(section 7: {reason[:80]}); this is a stop")
    approved_spans = []
    for wording, _ in claims:
        rx = phrase_rx(wording)
        for where, text in (("caption", caption), ("transcript", transcript)):
            if text and rx:
                approved_spans += [(where, m.start(), m.end()) for m in rx.finditer(text)]
    for category, words in cues:
        for w in words:
            rx = phrase_rx(w)
            for where, text in (("caption", caption), ("transcript", transcript)):
                if not text or not rx:
                    continue
                for m in rx.finditer(text):
                    if any(s[0] == where and s[1] <= m.start() and m.end() <= s[2] for s in approved_spans):
                        continue
                    line_id = "no-fabrication" if category == "results-and-relationship" else "claims"
                    say(line_id, "FINDING", f"{where} char {m.start()}: cue '{w}' ({category}) in: "
                        f"\"{sentence_at(text, m.start())}\"; the reviewer classes this sentence")
    for status, msg in claim_notes:
        say("claims", status, msg)
    if described:
        say("claims", "INFO", f"{described} section 7 Forbidden line(s) quote no phrase; the reviewer reads them")
    for line in open_contradictions(secs[7]):
        short = line if len(line) <= 90 else line[:87].rsplit(" ", 1)[0] + "..."
        say("claims", "INFO", f"section 7 contradiction still open: {short}; no claim it touches can pass")
    if not claims:
        say("claims", "INFO", "section 7 Approved has no owner-cleared line; every product statement is 'ask'")
    say("claims", "REVIEWER", "list every product statement, including paraphrases the script cannot match, "
        "and class each (approval-checklist.md section 2)")

    # Disclosure wording and placement (section 8)
    if barred:
        say("disclosure-wording", "SKIPPED", "not checked: the platform is barred in section 3")
    else:
        for status, msg in s8_notes:
            say("disclosure-wording", status, msg)
        if placement:
            say("disclosure-placement", "REVIEWER", f"section 8 placement for {a.platform}: {placement[:90]}")
        hits = sorted((m.start(), m.end(), w) for w in wordings for m in [phrase_rx(w).search(caption)] if m)
        bad = sorted((p, w) for w in noncounting(secs[8]) for p in [first_hit(phrase_rx(w), caption)] if p is not None)
        n = window[a.platform]
        if hits:
            pos, end, w = hits[0]
            say("disclosure-wording", "ok", f"caption: \"{w}\" found (section 8 wording for {a.platform})")
            where = (f"first disclosure \"{w}\" runs from caption char {pos} to {end} (Measured: counted by this "
                     f"script); window for {a.platform}: {n} (approval-checklist.md section 5, {window_origin[a.platform]})")
            if end <= n:
                say("disclosure-placement", "ok", f"{where}; inside the window")
            else:
                say("disclosure-placement", "FINDING", f"{where}; outside the window of {n}: move it to the start")
        else:
            say("disclosure-wording", "FINDING", f"caption does not carry the section 8 wording for "
                f"{a.platform}: \"{wordings[0]}\"")
            say("disclosure-placement", "SKIPPED", "not checked: no accepted disclosure in the caption to place")
        for pos, w in bad:
            status = "INFO" if hits else "FINDING"
            say("disclosure-wording", status, f"caption char {pos}: \"{w}\" is wording section 8 says does not count"
                + ("; it does not replace the accepted wording" if hits else " and it stands alone"))
    say("disclosure-placement", "REVIEWER", "confirm in the screenshots that nothing (a fold, a sticker, a "
        "hashtag pile) hides the disclosure")

    # Spoken disclosure (section 8)
    needs_transcript = a.format in transcript_formats if a.format else False
    if transcript is not None and not barred:
        accepted = wordings + ([spoken_form] if spoken_form else [])
        spoken = [(p, w) for w in accepted for p in [first_hit(phrase_rx(w, keep_hash=False), transcript)] if p is not None]
        mentions = [p for p in (first_hit(phrase_rx(brand), transcript),
                                first_hit(phrase_rx(row["code"]), transcript) if row["code"] else None) if p is not None]
        if not spoken:
            say("disclosure-video", "FINDING", "transcript carries neither the section 8 wording "
                + " nor the spoken form ".join(f"\"{w}\"" for w in accepted)
                + ("" if spoken_form else f" (section 8 gives no 'spoken:' form for {a.platform})"))
        else:
            pos, w = min(spoken)
            first = min(mentions) if mentions else None
            if first is None:
                say("disclosure-video", "ok", f"spoken \"{w}\" at transcript char {pos}; no brand or code mention found to time it against")
            elif pos <= first + spoken_window:
                say("disclosure-video", "ok", f"spoken \"{w}\" at transcript char {pos}, first brand or code mention "
                    f"at {first} (Measured: counted by this script), within the spoken window of {spoken_window}")
            else:
                say("disclosure-video", "FINDING", f"spoken \"{w}\" at transcript char {pos}, more than {spoken_window} "
                    f"characters after the first brand or code mention at {first}: say it earlier")
    elif needs_transcript and not barred:
        say("disclosure-video", "SKIPPED", f"not checked: format {a.format} needs a transcript and none was given")
    elif not a.format and not barred:
        say("disclosure-video", "INFO", "format not given; spoken disclosure checked only when a transcript is passed")
    say("disclosure-video", "REVIEWER", "on-screen disclosure needs the video or screenshots")
    say("disclosure-tool", "REVIEWER", "the platform's paid-partnership tool is set when posting; usually 'at posting'")
    say("age", "REVIEWER", "who appears and who is addressed, and the age setting, are the reviewer's")

    # Code and link (roster)
    code, link = row["code"].strip(), row["affiliate_link"].strip()
    combined = caption + ("\n" + transcript if transcript else "")
    if not code:
        say("code-link", "FINDING", f"the roster has no code for {a.creator}; run affiliate-onboarding first")
    else:
        m = phrase_rx(code).search(combined)
        if m:
            seen = combined[m.start():m.end()]
            say("code-link", "ok" if seen == code else "INFO",
                f"code {code} found" + ("" if seen == code else f", typed as '{seen}'"))
        else:
            say("code-link", "FINDING", f"code {code} (roster) not found in the caption or transcript")
        for cm in CODE_NEAR_RE.finditer(combined):
            if cm.group(1).upper() != code.upper():
                say("code-link", "FINDING", f"'code {cm.group(1)}' appears; the roster's code is {code}")
    if not link:
        say("code-link", "FINDING", f"the roster has no affiliate_link for {a.creator}; run affiliate-onboarding first")
    else:
        target = bare_url(link)
        host = target.split("/")[0]
        urls = [bare_url(u).rstrip(".,;:!?") for u in URL_RE.findall(caption)]
        if target in urls:
            say("code-link", "ok", "tracked link found as issued")
        else:
            wrong = [u for u in urls if u.split("/")[0] == host]
            if wrong:
                say("code-link", "FINDING", f"a link to {host} appears but not the tracked one: {wrong[0]}")
            else:
                say("code-link", "FINDING", "tracked link not in the caption; if the brief puts it elsewhere "
                    "(bio, sticker, description, show notes), the reviewer checks it there")

    # Redlines (section 9)
    words = redline_words(secs[9])
    if not words:
        say("redlines", "INFO", "section 9 lists no quoted redline words; the reviewer reads the redlines line")
    for w in words:
        for where, text in (("caption", caption), ("transcript", transcript)):
            pos = first_hit(phrase_rx(w), text) if text else None
            if pos is not None:
                say("redlines", "FINDING", f"{where} char {pos}: redline word \"{w}\" (section 9)")
    say("redlines", "REVIEWER", "images, sound, setting and content suitability against section 9")

    brief = ws / "campaigns" / a.campaign / "briefs" / f"{a.creator}.md"
    if brief.exists():
        say("brief", "REVIEWER", f"compare the deliverable with {brief.relative_to(ws)}")
    else:
        say("brief", "SKIPPED", f"no brief at campaigns/{a.campaign}/briefs/{a.creator}.md; line 'brief' cannot be checked")

    print("\n".join(out))
    total = counts["FINDING"] + counts["SKIPPED"]
    print(f"result: {counts['FINDING']} finding(s), {counts['SKIPPED']} skipped; "
          + ("all clear" if total == 0 else "the reviewer reads each line above") + f"; exit {2 if total else 0}")
    return 2 if total else 0


if __name__ == "__main__":
    sys.exit(main())
