"""Read the programme file, program/program.md, by its fixed numbered headings.

Shared by plan_budget.py and check_plan.py in this skill (each script adds this folder
to its import path, so the pair works under `python3 -I`). Sections are found by number
(programme template 0.1.2, 2026-10-20); a field is found by the label text the template
writes before its colon. A field that is blank or marked [open] is missing.

Source marks (template introduction): [owner] the owner said it, [observed] read from the
store or a public page on a date, [default] a pack default the owner accepted, [open]
undecided. A value marked [observed] is labelled Measured; anything else the owner set is
labelled User-provided.
"""
import re
from pathlib import Path

HEADING = re.compile(r"^##\s+(\d+)\.\s")
MARK = re.compile(r"\[(owner|observed|default|open)\]", re.I)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")

# field key: (section number, label pattern up to and including the label's colon).
# Label wording is the programme template's, version 0.1.2 of 2026-10-20.
FIELDS = {
    "aov": (1, r"average order value[^:]*:"),
    "margin": (1, r"gross margin band[^:]*:"),
    "currency": (1, r"store currency[^:]*:"),
    "commission_rate": (4, r"commission rate for[^:]*:"),
    "commission_basis": (4, r"commission basis\s*:"),
    "discount": (4, r"customer-facing discount[^:]*:"),
    "combine": (4, r"whether creator codes combine with other discounts[^:]*:"),
    "codes_after": (4, r"codes after a campaign window[^:]*:"),
    "thin": (5, r"tracked orders below which a creator's read is called thin[^:]*:"),
    "ranking": (5, r"ranking metric for performance reports[^:]*:"),
    "fee_rule": (4, r"when a flat or hybrid deal is allowed[^:]*:"),
    "attribution": (5, r"attribution model, declared once\s*:"),
    "holdback": (5, r"holdback before a sale[^:]*:"),
    "rights_window": (11, r"default usage-rights window[^:]*:"),
}

# Text the template leaves inside a value position; only what follows it is the owner's answer.
TEMPLATE_TAILS = {
    "commission_basis": "or another:",
    "codes_after": "[default stay active]:",
    "attribution": "changes here change every report:",
}

# Words that point at text instead of being the value. A field holding one of these is
# missing: the pack's ruling of 2026-10-21 (schemas.md section 12, attribution model line)
# says a value is the full sentence the owner accepted or changed, never "as written".
PLACEHOLDER_VALUES = {"as written", "as above", "default", "the default", "same", "same as above",
                      "see above", "as is", "as stated", "unchanged"}

LABELS = {
    "aov": "average order value",
    "margin": "gross margin band",
    "currency": "store currency",
    "commission_rate": "commission rate",
    "commission_basis": "commission basis",
    "discount": "customer-facing discount",
    "combine": "whether creator codes combine with other discounts",
    "codes_after": "codes after a campaign window",
    "thin": "tracked orders below which a creator's read is called thin",
    "ranking": "ranking metric for performance reports",
    "fee_rule": "when a flat or hybrid deal is allowed, and who approves one",
    "attribution": "attribution model",
    "holdback": "holdback before a sale counts as commissionable",
    "rights_window": "default usage-rights window",
}


class ProgrammeError(Exception):
    """A programme problem the person must fix; the message is the sentence they read."""


def load(workspace):
    path = Path(workspace) / "program" / "program.md"
    if not path.is_file():
        raise ProgrammeError(f"{path} was not found; run program-setup to create the programme file, then re-run.")
    sections, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = HEADING.match(line)
        if m:
            current = int(m.group(1))
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    if not sections:
        raise ProgrammeError(f"{path} has no numbered sections; it does not follow the programme template.")
    return sections


def field(sections, key):
    """Return (value, marks) for a field, or (None, marks) when blank, [open] or a placeholder.

    The value is what follows the template's text on the field's own line, plus any
    indented lines under it that carry a source mark ([owner], [observed], [default]).
    Unmarked indented lines are the template's own instructions and are ignored (the pack
    rule of 2026-10-21, template 0.1.2). A field line is a top-level bullet only. Where the
    template writes text in the value position (TEMPLATE_TAILS), the value is only what
    follows that text: for the attribution model, the full sentence after "Changes here
    change every report:", so the pre-filled default before it is never taken as an answer.
    """
    num, pattern = FIELDS[key]
    rx = re.compile(r"^[-*]\s*" + pattern, re.I)
    lines = sections.get(num, [])
    for i, line in enumerate(lines):
        m = rx.match(line)
        if not m:
            continue
        extra = []
        for sub in lines[i + 1:]:
            if not sub.strip() or not sub[:1].isspace():
                break
            sub_marks = {x.lower() for x in MARK.findall(sub)}
            if sub_marks & {"owner", "observed", "default"}:
                extra.append((strip_marks(sub.strip().lstrip("-* ")), sub_marks))
        rest = line[m.end():]
        tail = TEMPLATE_TAILS.get(key)
        if tail and tail in rest.lower():
            idx = rest.lower().index(tail)
            rest = rest[idx + len(tail):]
        marks = {x.lower() for x in MARK.findall(rest)}
        value = strip_marks(rest)
        if "open" in marks:
            return None, marks
        parts = [value] if value else []
        for text, sub_marks in extra:
            if text:
                parts.append(text)
                marks |= sub_marks
        if not parts or parts[0].lower().strip(" .") in PLACEHOLDER_VALUES:
            return None, marks
        return "; ".join(parts), marks
    return None, set()


def strip_marks(text):
    return MARK.sub("", text).replace("`", "").strip(" \t.;")


def require(sections, key):
    value, marks = field(sections, key)
    if value is None:
        num = FIELDS[key][0]
        raise ProgrammeError(
            f"Programme section {num}: '{LABELS[key]}' is blank, [open] or a placeholder such as 'as written'; write the value itself with program-setup and re-run.")
    return value, marks


def label_for(marks):
    return "Measured" if "observed" in marks else "User-provided"


def numbers(text):
    text = ISO_DATE.sub(" ", text)
    text = THOUSANDS.sub("", text)
    return NUMBER.findall(text)


def section_text(sections, num):
    return "\n".join(sections.get(num, []))


# Platform table, programme section 3. Row labels are the template's.
def _row_keys(label):
    low = label.lower().strip()
    if low.startswith("podcasts and newsletters"):
        return ["podcast", "newsletter"]
    if low.startswith("grindr and scruff"):
        return ["grindr", "scruff"]
    return [re.split(r"[\s(]", low, maxsplit=1)[0]]


def _status(cell):
    c = strip_marks(cell).lower()
    if not c:
        return "unknown"
    if c.startswith("with conditions"):
        return "with conditions"
    if re.match(r"yes\b", c):
        return "yes"
    if re.match(r"no\b", c):
        return "no"
    return "unknown"


def platform_table(sections):
    """Map platform key -> dict(status, text, row) from section 3's organic column.

    Returns (table, filled) where filled is False when no row has a ruling.
    """
    table, filled = {}, False
    for line in sections.get(3, []):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() == "platform" or set(cells[0]) <= set("-: "):
            continue
        status = _status(cells[1])
        if strip_marks(cells[1]):
            filled = True
        for key in _row_keys(cells[0]):
            table[key] = {"status": status, "text": strip_marks(cells[1]), "row": cells[0]}
    return table, filled


def platform_ruling(table, platform):
    """Return (status, text, via) for a creator platform; via names the row used."""
    p = platform.lower().strip()
    if p in table:
        r = table[p]
        return r["status"], r["text"], r["row"]
    if "other" in table:
        r = table["other"]
        return r["status"], r["text"], r["row"] + " (no row of its own)"
    return "unknown", "", "no row"


def eligible(status):
    return status in ("yes", "with conditions")
