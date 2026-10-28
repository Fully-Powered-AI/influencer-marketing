"""Read the programme file by its fixed headings and field labels.

Shared by init_workspace.py and compare_models.py. Standard library only.
The headings and field labels are read at run time from the template,
../assets/program-template.md, so a template change reaches every check
without editing this file.

Line rules, from the template's own instructions (assets/program-template.md,
first section): a field is a bullet whose template text ends with a colon;
the value is written after that colon; the source mark is the last thing on
the line; extra detail goes on indented lines under the field, each with
its own mark. Indented lines that are in the template itself are guidance,
not values, and are skipped.

Shapes other skills' checkers parse (lead's fix round, 2026-10-20), checked
here so a programme that passes is one they can read:
- section 3: a `with conditions` cell states them after a colon;
- section 7 Approved: `- <product>: "<verbatim wording>" [owner]`;
- section 7 Forbidden: exact phrases in double quotes after the template
  text, the reason unquoted;
- section 8 wording: one indented line per platform, the platform written
  as a roster value, `- <platform>: "<wording>" <placement> [mark]`, one
  quoted wording per line (a spoken form goes, unquoted, in the placement);
  every roster platform whose section 3 organic column is yes or with
  conditions has its line; a spoken form is written in the placement as
  `spoken: <phrase>`. Quotes are straight double quotes throughout.

Rulings (programme rules, schemas.md section 12, 2026-10-20): every line
in sections 7 and 8 carries [owner], even a pack proposal the owner accepted;
no value is "as written", "as above" or a bare "default"; the section 5
attribution value is the full sentence.
"""
import re
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "program-template.md"

# The four source marks the template defines (assets/program-template.md, line 5).
MARK_RE = re.compile(r"\[(owner|observed|default|open)\]")
OPEN_RE = re.compile(r"\[open\]")
HEADING_RE = re.compile(r"^## (\d+)\. (.+?)\s*$")
LEVEL2_RE = re.compile(r"^## ")
SUBHEADING_RE = re.compile(r"^### (.+?)\s*$")
LOG_ENTRY_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}, \S")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Allowed values for the organic and paid columns of section 3 (template, section 3).
PLATFORM_VALUES = ("yes", "no", "unknown")
WITH_CONDITIONS_RE = re.compile(r"^with conditions:\s*(\S.*)$", re.IGNORECASE)

# Section 7 Approved line: a product, a colon, then the cleared wording in double quotes.
APPROVED_RE = re.compile(r'^(?P<product>[^:"]+):\s*"(?P<wording>[^"]+)"')
# The line a programme with nothing cleared carries in section 7's opening part.
NO_CLAIM_PREFIX = "No claim is cleared yet"
# Section 8: the wording field, and the shape of each per-platform line under it.
WORDING_LABEL_START = "Required disclosure wording and placement"
PLATFORM_LINE_RE = re.compile(r'^- (?P<label>[^:"`]+):\s*"(?P<wording>[^"]+)"(?P<rest>[^"]*)$')
CURLY_QUOTES = ("\u201c", "\u201d")
# Roster platform values: references/schemas.md section 4, `primary_platform` (2026-10-20);
# run_fixtures.sh compares this list with that file when the pack is present.
ROSTER_PLATFORMS = ("instagram", "tiktok", "youtube", "x", "onlyfans", "reddit",
                    "podcast", "newsletter", "bluesky", "threads", "other")
# Section 3 rows whose label is not itself a roster value (template section 3 rows).
ROW_PLATFORMS = {
    "onlyfans (creator-owned pages)": ("onlyfans",),
    "podcasts and newsletters": ("podcast", "newsletter"),
    "grindr and scruff (brand advertising only)": (),
}

STATUSES = ("settled", "open", "unfilled", "unmarked", "invalid")

# Values a reader cannot apply: the line must carry the sentence itself
# (programme rules; schemas.md section 12, attribution model line).
PLACEHOLDERS = {"as written", "as above", "as stated", "as proposed", "see above", "same", "default", "the default"}
# Sections whose lines take [owner] only (programme rules).
OWNER_ONLY_SECTIONS = (7, 8)
THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def norm(text):
    """Collapse runs of whitespace so a label matches however it was wrapped."""
    return " ".join(text.split())


def split_sections(text):
    """Split a programme file into numbered sections.

    Returns (sections, problems). Each section is a dict with num, title,
    start (1-based line number of the heading) and lines (the body).
    Any level-2 heading that is not '## N. Title' is a problem.
    """
    sections, problems = [], []
    current = None
    for i, line in enumerate(text.splitlines(), start=1):
        match = HEADING_RE.match(line)
        if match:
            current = {"num": int(match.group(1)), "title": match.group(2),
                       "start": i, "lines": []}
            sections.append(current)
        elif LEVEL2_RE.match(line):
            problems.append(f"line {i}: '{line.strip()}' is not a numbered section heading")
        elif current is not None:
            current["lines"].append(line)
    return sections, problems


def check_headings(program_sections, template_sections):
    """Compare headings with the template: same numbers, same titles, same order."""
    problems = []
    expected = [(s["num"], s["title"]) for s in template_sections]
    found = [(s["num"], s["title"]) for s in program_sections]
    found_nums = [n for n, _ in found]
    for num, title in expected:
        if num not in found_nums:
            problems.append(f"heading '## {num}. {title}' is missing")
    for num in sorted(set(found_nums)):
        if found_nums.count(num) > 1:
            problems.append(f"heading number {num} appears {found_nums.count(num)} times")
    titles = dict(expected)
    for num, title in found:
        if num not in titles:
            problems.append(f"heading '## {num}. {title}' is not in the template")
        elif title != titles[num]:
            problems.append(f"heading {num} reads '{title}'; the template has '{titles[num]}'")
    if not problems and found_nums != sorted(found_nums):
        problems.append("headings are out of order: " + ", ".join(str(n) for n in found_nums))
    return problems


def bullets(lines):
    """Top-level bullets with their indented continuation lines.

    Returns a list of (first_line_text, [continuation lines]). Lines that are
    neither bullets nor indented under a bullet (prose, tables, blanks) end
    the current bullet.
    """
    out, current = [], None
    for line in lines:
        if line.startswith("- "):
            current = (line[2:].rstrip(), [])
            out.append(current)
        elif current is not None and line[:1] in (" ", "\t") and line.strip():
            current[1].append(line.strip())
        else:
            current = None
    return out


def template_labels(lines):
    """Field labels, fixed lines and guidance lines from a template section body.

    A field is a bullet whose text, after removing a trailing [open], ends
    with a colon. Any other bullet is fixed text and is not an item. An
    indented line under a template field is guidance for that field.
    """
    labels, fixed, guidance = [], set(), {}
    for text, cont in bullets(lines):
        stripped = OPEN_RE.sub("", text).rstrip()
        if stripped.endswith(":"):
            labels.append(norm(stripped))
            guidance[norm(stripped)] = {norm(c) for c in cont}
        else:
            fixed.add(norm(text))
    return labels, fixed, guidance


def value_status(parts, owner_only=False):
    """Status of a value made of one or more non-empty text parts."""
    parts = [p for p in parts if p.strip()]
    if not parts:
        return "unfilled", "no value after the colon"
    if any(OPEN_RE.search(p) for p in parts):
        return "open", "marked [open]"
    for p in parts:
        bare = norm(MARK_RE.sub(" ", p)).strip(" .:;-").lower()
        if bare in PLACEHOLDERS:
            return "invalid", f"'{bare}' is not a value; write the sentence or figure itself"
    unmarked = [p for p in parts if not MARK_RE.search(p)]
    if unmarked:
        return "unmarked", "no source mark on: " + short(unmarked[0])
    if owner_only:
        not_owner = [p for p in parts if "[owner]" not in p]
        if not_owner:
            return "invalid", ("sections 7 and 8 take [owner] only, even for a proposal the owner accepted; "
                               "fix: " + short(not_owner[0], 50))
    return "settled", ""


def short(text, width=70):
    text = norm(text)
    return text if len(text) <= width else text[: width - 3] + "..."


def item(section, label, status, detail=""):
    return {"section": section, "label": short(label), "status": status, "detail": detail}


def analyse_bullets(num, lines, labels, fixed, guidance=None, values=None, rules=None):
    """Items for the bullets of one section (or subsection).

    values, when a dict is passed, receives each field's detail lines with
    template guidance removed, keyed by label, for the shape checks. rules
    maps a label to a function of (value, detail) returning a problem or None.
    """
    guidance = guidance or {}
    rules = rules or {}
    owner_only = num in OWNER_ONLY_SECTIONS
    items, used = [], set()
    entries = bullets(lines)
    matched = {}
    for index, (text, cont) in enumerate(entries):
        ntext = norm(text)
        best = None
        for label in labels:
            if ntext.startswith(label) and (best is None or len(label) > len(best)):
                best = label
        if best is not None:
            matched.setdefault(best, []).append(index)
            used.add(index)
        elif ntext in fixed:
            used.add(index)
    for label in labels:
        hits = matched.get(label, [])
        if not hits:
            items.append(item(num, label, "unfilled", "line missing; copy it from the template"))
            continue
        text, cont = entries[hits[0]]
        cont = [c for c in cont if norm(c) not in guidance.get(label, set())]
        if values is not None:
            values[label] = cont
        rest = norm(text)[len(label):].strip()
        status, detail = value_status([rest] + cont, owner_only)
        if status == "settled" and label in rules:
            problem = rules[label](rest, cont)
            if problem:
                status, detail = "invalid", problem
        items.append(item(num, label, status, detail))
        for extra in hits[1:]:
            items.append(item(num, label, "invalid",
                              "line appears more than once; scripts read the first"))
    for index, (text, cont) in enumerate(entries):
        if index in used:
            continue
        status, detail = value_status([text] + cont, owner_only)
        items.append(item(num, text, status, detail))
    return items


def table_rows(lines):
    """Data rows of every markdown table in the lines, as lists of cells."""
    rows, in_table = [], False
    for raw in lines:
        if raw.startswith("|"):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if not in_table:
                in_table = True
                continue  # header row
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue  # separator row
            rows.append(cells)
        else:
            in_table = False
    return rows


def platform_cell_ok(cell):
    value = cell.strip().strip("`").strip()
    if value.lower() in PLATFORM_VALUES:
        return True
    match = WITH_CONDITIONS_RE.match(value)
    return bool(match and match.group(1))


def analyse_table(num, program_lines, template_lines, platform_rules):
    items = []
    template_keys = [norm(r[0]).lower() for r in table_rows(template_lines)]
    rows = table_rows(program_lines)
    seen = set()
    for cells in rows:
        key = norm(cells[0]).lower()
        seen.add(key)
        row_text = " | ".join(cells)
        if OPEN_RE.search(row_text):
            items.append(item(num, cells[0], "open", "row marked [open]"))
            continue
        if platform_rules:
            if len(cells) != 5:
                items.append(item(num, cells[0], "invalid", f"row has {len(cells)} cells; the table has 5"))
                continue
            if not cells[1] or not cells[2] or not cells[3]:
                items.append(item(num, cells[0], "unfilled", "organic, paid or labelling cell is empty"))
                continue
            bad = [c for c in (cells[1], cells[2]) if not platform_cell_ok(c)]
            if bad:
                items.append(item(num, cells[0], "invalid",
                                  "use yes, no, unknown or 'with conditions' and state them; found: " + short(bad[0], 40)))
                continue
        if not MARK_RE.search(row_text):
            items.append(item(num, cells[0], "unmarked", "no source mark in the row"))
            continue
        items.append(item(num, cells[0], "settled"))
    for key in template_keys:
        if key not in seen:
            items.append(item(num, key, "unfilled", "row missing; copy it from the template"))
    return items


def subsections(lines):
    """Split a section body at its ### headings: [(title or None, lines)]."""
    parts = [(None, [])]
    for line in lines:
        match = SUBHEADING_RE.match(line)
        if match:
            parts.append((match.group(1), []))
        else:
            parts[-1][1].append(line)
    return parts


def analyse_claims(num, program_lines, template_lines):
    """Section 7: the intro, Approved (owner's wording only) and Forbidden."""
    items, problems = [], []
    prog = subsections(program_lines)
    tmpl = subsections(template_lines)

    def find(parts, prefix):
        for title, body in parts:
            if title is not None and title.startswith(prefix):
                return body
        return None

    labels, fixed, guidance = template_labels(tmpl[0][1])
    items += analyse_bullets(num, prog[0][1], labels, fixed, guidance)
    intro_entries = bullets(prog[0][1])
    no_claim = [t for t, c in intro_entries if norm(t).startswith(NO_CLAIM_PREFIX)]

    approved = find(prog, "Approved")
    forbidden = find(prog, "Forbidden")
    if approved is None:
        problems.append("section 7 has no '### Approved claims' heading")
    if forbidden is None:
        problems.append("section 7 has no '### Forbidden claims' heading")
    if problems:
        return items, problems

    entries = bullets(approved)
    if not entries and not no_claim:
        items.append(item(num, "Approved claims", "unfilled",
                          f"none recorded; write the cleared wording, or '- {NO_CLAIM_PREFIX}...' "
                          "with [owner] above the Approved heading"))
    if entries and no_claim:
        items.append(item(num, "Approved claims", "invalid",
                          f"Approved has lines but the opening part still says '{NO_CLAIM_PREFIX}'"))
    for text, cont in entries:
        parts = [text] + cont
        joined = " ".join(parts)
        if OPEN_RE.search(joined):
            items.append(item(num, "Approved: " + text, "open", "marked [open]"))
        elif "[owner]" in joined:
            status, detail = value_status(parts)
            if status == "unmarked":
                items.append(item(num, "Approved: " + text, "unmarked", detail))
            elif (not APPROVED_RE.match(MARK_RE.sub("", text).strip()) or text.count('"') != 2
                  or any(q in text for q in CURLY_QUOTES)):
                items.append(item(num, "Approved: " + text, "invalid",
                                  'write it as - <product>: "<verbatim wording>" [owner], one wording per line'))
            else:
                items.append(item(num, "Approved: " + text, "settled"))
        elif MARK_RE.search(joined):
            items.append(item(num, "Approved: " + text, "invalid",
                              "an approved claim carries [owner] only; a page read or a default is not clearance"))
        else:
            items.append(item(num, "Approved: " + text, "unmarked", "no source mark"))

    flabels, ffixed, fguidance = template_labels(find(tmpl, "Forbidden") or [])
    items += analyse_bullets(num, forbidden, flabels, ffixed, fguidance)
    for text, cont in bullets(forbidden):
        for part in [text] + cont:
            if part.count('"') % 2 or any(q in part for q in CURLY_QUOTES):
                items.append(item(num, "Forbidden: " + text, "invalid",
                                  "use balanced straight double quotes; every quoted string here is read as a forbidden phrase"))
    return items, problems


def analyse_log(num, lines):
    items = []
    entries = bullets(lines)
    for text, _ in entries:
        if LOG_ENTRY_RE.match("- " + text):
            items.append(item(num, text, "settled"))
        else:
            items.append(item(num, text, "invalid", "entry must start 'YYYY-MM-DD, role, '"))
    if not entries:
        items.append(item(num, "Decisions log", "unfilled", "no dated entry yet"))
    return items


def _discount_rule(value, detail):
    text = " ".join([value] + detail)
    lower = text.lower()
    if lower.startswith("none") or re.search(r"%|\bpercent\b|\bpct\b|\bfixed\b|\b[A-Z]{3}\b", MARK_RE.sub(" ", text)):
        return None
    return "say 'percent' or 'fixed' (or the currency): '15 percent' or 'fixed 5.00 USD'"


def _minimum_rule(value, detail):
    text = " ".join([value] + detail).lower()
    if re.search(r"\bno minimum\b|\bminimum \d", THOUSANDS_RE.sub("", text)):
        return None
    return "write the minimum as 'minimum <amount>' or 'no minimum'"


def _attribution_rule(value, detail):
    text = " ".join([value] + detail).lower()
    if re.search(r"\bcodes? only\b|\bonly (discount )?codes?\b", text):
        return None
    if "code" in text and "link" in text and text.find("code") < text.find("link"):
        return None
    return ("write the model as a sentence naming code first, then tracked link, or codes only; "
            "the report scripts apply only those two")


# (section, start of the template label) -> rule; the readers' accepted forms
# (offer_calc.py, commission_statement.py, attribution.py, 2026-10-20).
FIELD_RULES = {
    (4, "Customer-facing discount"): _discount_rule,
    (5, "Attribution model"): _attribution_rule,
    (6, "Payout schedule"): _minimum_rule,
}


def rules_for(num, labels):
    out = {}
    for (sec, start), rule in FIELD_RULES.items():
        if sec == num:
            for label in labels:
                if label.startswith(start):
                    out[label] = rule
    return out


def analyse(program_text, template_text):
    """Return (sections, items, problems). Problems are structural (exit 1)."""
    tsections, tproblems = split_sections(template_text)
    if tproblems or not tsections:
        return [], [], ["the template itself could not be read: " + "; ".join(tproblems or ["no headings"])]
    psections, problems = split_sections(program_text)
    problems += check_headings(psections, tsections)
    if problems:
        return psections, [], problems
    tby = {s["num"]: s for s in tsections}
    items = []
    for sec in psections:
        num, body, tbody = sec["num"], sec["lines"], tby[sec["num"]]["lines"]
        if num == 12:
            items += analyse_log(num, body)
        elif num == 7:
            found, sub_problems = analyse_claims(num, body, tbody)
            items += found
            problems += sub_problems
        else:
            labels, fixed, guidance = template_labels(tbody)
            values = {}
            items += analyse_bullets(num, body, labels, fixed, guidance, values, rules_for(num, labels))
            if table_rows(tbody) or table_rows(body):
                items += analyse_table(num, body, tbody, platform_rules=(num == 3))
            if num == 8:
                rows = [r for s3 in psections if s3["num"] == 3 for r in table_rows(s3["lines"])]
                items += check_platform_lines(num, labels, values, rows)
    return psections, items, problems


def allowed_platforms(rows):
    """Roster platforms whose section 3 organic column is yes or with conditions."""
    out = []
    for cells in rows:
        if len(cells) < 2:
            continue
        organic = cells[1].strip().strip("`").lower()
        if organic == "yes" or organic.startswith("with conditions"):
            key = norm(cells[0]).lower()
            mapped = ROW_PLATFORMS.get(key, (key,) if key in ROSTER_PLATFORMS else ())
            out += [m for m in mapped if m not in out]
    return out


def check_platform_lines(num, labels, values, rows):
    """Section 8 wording: one indented line per roster platform, in the shape the siblings parse."""
    label = next((l for l in labels if l.startswith(WORDING_LABEL_START)), None)
    if label is None or label not in values:
        return []
    found, seen = [], []
    for line in values[label]:
        if OPEN_RE.search(line):
            continue
        match = PLATFORM_LINE_RE.match(MARK_RE.sub("", line).rstrip())
        if any(q in line for q in CURLY_QUOTES) or not match:
            found.append(item(num, "wording line: " + line, "invalid",
                              'write it as - <platform>: "<wording>" <placement> [owner], one straight-quoted wording'))
            continue
        platform = norm(match.group("label")).lower()
        placement = match.group("rest")
        if "[owner]" not in line:
            found.append(item(num, "wording line: " + line, "invalid",
                              "mark each platform line [owner]; the readers take [owner] only"))
        elif re.search(r"\bspoken\b(?!\s*:)", placement, re.IGNORECASE) or re.search(r"\bspoken:\s*(;|$)", placement, re.IGNORECASE):
            found.append(item(num, "wording line: " + line, "invalid",
                              "write the spoken form as spoken: <phrase>, ending at ; or the mark"))
        if platform not in ROSTER_PLATFORMS:
            found.append(item(num, "wording line: " + line, "invalid",
                              "write the platform as a roster value: " + ", ".join(ROSTER_PLATFORMS)))
        elif platform in seen:
            found.append(item(num, "wording line: " + line, "invalid", f"a second line for {platform}; one per platform"))
        else:
            seen.append(platform)
    for platform in allowed_platforms(rows):
        if platform not in seen:
            found.append(item(num, f"disclosure line for {platform}", "unfilled",
                              f'section 3 allows creator posts there; add - {platform}: "<wording>" <placement> [owner]'))
    return found


def field_value(program_text, section_num, label_start):
    """The value written after a field's label, with its continuation lines.

    label_start is the beginning of the template label, enough to be unique
    in the section. Returns (value_text, status); status is 'missing' when
    the template has no such label or the programme file lacks the line.
    """
    label, guidance = template_label_for(section_num, label_start)
    if label is None:
        return None, "missing"
    sections, _ = split_sections(program_text)
    for sec in sections:
        if sec["num"] != section_num:
            continue
        for text, cont in bullets(sec["lines"]):
            ntext = norm(text)
            if ntext.startswith(label):
                cont = [c for c in cont if norm(c) not in guidance]
                parts = [p for p in [ntext[len(label):].strip()] + cont if p.strip()]
                status, _ = value_status(parts)
                return " ".join(parts), status
    return None, "missing"


def template_label_for(section_num, label_start):
    """The full template label beginning with label_start, and its guidance lines."""
    try:
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError:
        return None, set()
    sections, _ = split_sections(text)
    for sec in sections:
        if sec["num"] == section_num:
            labels, _, guidance = template_labels(sec["lines"])
            for label in labels:
                if label.startswith(norm(label_start)):
                    return label, guidance.get(label, set())
    return None, set()


def numbers_in(value):
    """Numbers in a value, ignoring ISO dates and the source mark."""
    cleaned = THOUSANDS_RE.sub("", DATE_RE.sub(" ", MARK_RE.sub(" ", value)))
    return [n for n in NUMBER_RE.findall(cleaned)]
