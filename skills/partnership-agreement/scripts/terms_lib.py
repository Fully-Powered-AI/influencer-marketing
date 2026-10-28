"""Shared readers for the partnership-agreement scripts. Python 3 standard library only.

Reads the programme file by its fixed numbered headings and the roster CSV with the header
from the pack's schemas. The roster header below is copied from schemas section 4; the runtime
copy in creator-roster's references/schemas.md is the law, so if it changes there, change it here.
"""

import argparse
import csv
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

# schemas section 4, data/creators.csv, in order.
ROSTER_HEADER = [
    "creator_ref", "display_name", "primary_platform", "primary_handle", "profile_url",
    "other_platforms", "tier", "followers_primary", "followers_as_of", "engagement_rate_pct",
    "engagement_as_of", "niche_tags", "audience_fit_score", "brand_safety_flag", "contact_path",
    "contact_email", "status", "compensation_model", "commission_rate_pct", "flat_fee", "code",
    "affiliate_link", "rail", "agreement_date", "agreement_file", "usage_rights_until",
    "exclusivity_until", "first_campaign", "last_activity", "notes",
]
# schemas section 4, primary_platform values.
PLATFORMS = ("instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast",
             "newsletter", "bluesky", "threads", "other")
# schemas section 4, compensation_model values.
MODELS = ("cpa", "flat", "hybrid", "gift", "none")
# schemas section 6, publications format values.
FORMATS = ("video", "reel", "story", "post", "thread", "newsletter", "podcast", "live", "other")
# schemas section 2, creator_ref shape.
CREATOR_REF = re.compile(r"^c-[a-z0-9]{6}$")

# Programme-template labels (program-template.md 0.1.2, 2026-10-20) that contain a colon of their
# own. A filled line is '<label>: <value>', so for these the value starts after the whole label;
# any other line splits at its first colon. The fixture runner compares this list with the
# programme template when the pack is present.
TEMPLATE_LABELS = [
    'Products, one per line: name, category, materials or ingredients, variants, sizes, list price, and owner-cleared attributes. Unlisted product statements require review',
    'Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme',
    'Commission basis: `subtotal after discounts, before shipping and tax` [default] or another',
    "Flat-fee anchors by tier, store currency, for the owner's reference only (ranges, not offers): nano / micro / mid / macro",
    'Gifting: which products, how many units a year, and whether a post is expected',
    'Break-even check inputs the `creator-outreach` skill uses: average order value, gross margin band, customer discount, commission rate (copied from above so a script can read one section)',
    'Codes after a campaign window: `end` with the window, or `stay active` [default stay active]',
    'Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to the refunded share of the order',
    'Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values)',
    'Landing pages: which page each product campaign sends to',
    'Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report',
    "Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]",
    "What is Measured, what is Estimated: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]",
    "Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet",
    'Prerequisites verified on the store, each with the date and the role that checked: Shopify Payments active, country supported, Collabs or app installed, discount-creation access, API access scope and token custodian role',
    "How a creator joins: application page URL (Collabs or app), or the pack's onboarding path",
    "Content suitability policy: permitted themes and presentation for the category and markets (the owner decides; the pack has no category default)",
    'Audience age: applicable audience restrictions and required evidence, or none with a reason',
    'Redlines: topics, words, imagery or associations the brand will not appear beside',
    'Creative freedom: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]',
    'Competitor conflicts: which categories count as competitors for exclusivity purposes',
    'Default exclusivity: none [default], or the category and period',
    'Counsel review rule: no agreement is sent to a creator before counsel has reviewed the template once, and any non-template clause goes back to counsel [default]',
]

HEADING = re.compile(r"^##\s+(\d+)\.\s*(.*?)\s*$")
SUBHEADING = re.compile(r"^###\s+(.*?)\s*$")
# Source marks used in the programme file (program-template.md, opening paragraph).
MARK = re.compile(r"\[(?:owner|observed|default|open)\]", re.I)
TABLE_RULE = re.compile(r"^:?-{3,}:?$")
PLATFORM_VALUE = re.compile(r"^(yes|no|with conditions|unknown)\b")


class InputError(Exception):
    """Bad input. The message is one plain sentence saying what to fix."""


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error; this pack keeps 2 for a partial run, so a usage error exits 1."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: {message}; run with --help for the arguments.\n")


def read_text(path):
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InputError(f"{path} was not found; check the path and run again.")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder; give the path to the file.")
    except UnicodeDecodeError:
        raise InputError(f"{path} could not be read as UTF-8; export it as plain text or Markdown and run again.")


def norm(text):
    """Lower case, letters and digits only, single spaces: for comparing wording, not meaning."""
    text = MARK.sub(" ", text or "")
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def same_text(a, b):
    """Equal after normalisation: case, punctuation and source marks ignored, every word kept."""
    na, nb = norm(a), norm(b)
    return bool(na) and na == nb


def contains_run(haystack, needle):
    """True when the needle's normalised words appear in the haystack as a whole run of words."""
    n = norm(needle)
    return bool(n) and f" {n} " in f" {norm(haystack)} "


def amount_and_unit(text):
    """(number, 'percent' or 'amount') for a discount such as '15 percent' or 'USD 5 off'."""
    number = to_decimal(text)
    unit = "percent" if re.search(r"%|\bpercent\b|\bper cent\b", text or "", re.I) else "amount"
    return number, unit


def same_amount(a, b):
    """Same number and same unit: '15 percent' equals '15%', never '5 percent' or 'USD 15'."""
    na, ua = amount_and_unit(a)
    nb, ub = amount_and_unit(b)
    return na is not None and na == nb and ua == ub


WINDOW = re.compile(r"(\d+(?:\.\d+)?)\s*(day|week|month|year)s?\b(?:\s+(?:from|after)\s+(?:the\s+)?(\w+))?", re.I)
# Words for the posting date as a window's start. A duration stated with no start runs from
# posting (schemas section 4, ruling of 2026-10-21), so no start reads as posting too.
POSTING = {"", "posting", "post", "posts", "publication", "publishing"}


def window_parts(text):
    """(length, unit, start) for a usage window such as '6 months from posting' or '6 months,
    organic reuse only'; start is 'posting' when the window has none. None when there is no length."""
    m = WINDOW.search(text or "")
    if not m:
        return None
    start = (m.group(3) or "").lower()
    return to_decimal(m.group(1)), m.group(2).lower(), "posting" if start in POSTING else start


def same_window(a, b):
    """Same length, unit and start: '6 months, organic reuse only' equals '6 months from posting;
    paid reuse not included', never 'months from posting', '2 months' or '6 months from the end date'."""
    pa, pb = window_parts(a), window_parts(b)
    return pa is not None and pa == pb


def window_months_from_posting(text):
    """Whole months for a window that runs from posting (a year is twelve), else None. Days and
    weeks are not turned into months; the hand-off asks the owner how such a window is dated."""
    parts = window_parts(text)
    if parts is None or parts[2] != "posting":
        return None
    length, unit, _ = parts
    months = length * 12 if unit == "year" else length if unit == "month" else None
    if months is None or months != months.to_integral_value():
        return None
    return str(int(months))


def to_decimal(text):
    """A plain number from a cell or a value, or None. '15', '15.0', '15 percent', '250.00'."""
    if text is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not m:
        return None
    try:
        return Decimal(m.group(0))
    except InvalidOperation:
        return None


def is_noneish(text):
    """True for an empty value, none, n/a, no or zero (with or without a trailing reason)."""
    t = norm(text)
    return t in ("", "na", "0", "0 00", "no") or t.startswith(("none", "n a", "no "))


def split_sections(text):
    """Map section number to {'title', 'lines': [(line_number, text)]}; also return duplicates."""
    sections, duplicates, current = {}, [], None
    for number, line in enumerate(text.splitlines(), 1):
        m = HEADING.match(line)
        if m:
            n = int(m.group(1))
            if n in sections:
                duplicates.append(n)
            current = {"title": m.group(2), "lines": [], "line": number}
            sections[n] = current
            continue
        if current is not None:
            current["lines"].append((number, line))
    return sections, duplicates


class Programme:
    """The programme file, program/program.md, read by its numbered headings."""

    def __init__(self, workspace):
        self.path = Path(workspace) / "program" / "program.md"
        if not self.path.is_file():
            raise InputError(
                f"No programme file at {self.path}; run program-setup with the owner first, "
                "or give the workspace that holds it.")
        self.sections, _ = split_sections(read_text(self.path))

    def has(self, n):
        return n in self.sections

    def lines(self, n):
        return [t for _, t in self.sections.get(n, {}).get("lines", [])]

    def field(self, n, label_pattern):
        """(found, value) for the first top-level '- label: value' line in section n whose label
        matches. The value is the field's own line. An indented line under it is template guidance
        when it carries no source mark and is never read; a marked indented line is the owner's
        detail and stands in for the value only when the field's own line is blank (programme
        template 0.1.2, opening paragraph). A line marked [open] reads as blank (not yet decided)."""
        rx = re.compile(label_pattern, re.I)
        lines = self.lines(n)
        for i, line in enumerate(lines):
            parts = split_line(line)
            if parts is None or not rx.search(parts[0]):
                continue
            own = "" if re.search(r"\[open\]", parts[1], re.I) else clean(parts[1])
            if own:
                return True, own
            return True, "; ".join(self.details(lines[i + 1:]))
        return False, ""

    def field_details(self, n, label_pattern):
        """The marked indented lines under a field, each cleaned, for fields written one item per line."""
        rx = re.compile(label_pattern, re.I)
        lines = self.lines(n)
        for i, line in enumerate(lines):
            parts = split_line(line)
            if parts is not None and rx.search(parts[0]):
                return self.details(lines[i + 1:])
        return []

    @staticmethod
    def details(following):
        out = []
        for nxt in following:
            if not (nxt.startswith(" ") and nxt.strip()):
                break
            text = nxt.strip()
            text = text[2:] if text.startswith("- ") else text
            if MARK.search(text) and not re.search(r"\[open\]", text, re.I):
                out.append(clean(text))
        return out

    def subsection(self, n, title_prefix):
        """Lines under '### <title_prefix>...' inside section n, up to the next '###'."""
        out, inside = [], False
        for line in self.lines(n):
            m = SUBHEADING.match(line)
            if m:
                inside = m.group(1).lower().startswith(title_prefix.lower())
                continue
            if inside:
                out.append(line)
        return out

    def approved_statements(self):
        """Statements under section 7 'Approved claims'. Each entry: (as written, statement part)."""
        out = []
        for line in self.subsection(7, "Approved"):
            s = line.strip()
            if not s.startswith("- "):
                continue
            body = MARK.sub("", s[2:]).strip()
            if not body or re.search(r"\[open\]", s, re.I):
                continue
            quoted = re.search(r"[\"“](.+?)[\"”]", body)
            if quoted:
                part = quoted.group(1)
            else:
                part = re.sub(r"\s*\([^)]*\)\s*$", "", body)
            out.append((body, part))
        return out

    def platform_table(self):
        """Section 3 rows: list of (label, organic, paid), values normalised to yes, no,
        with conditions, unknown or '' (blank)."""
        rows, seen_header = [], False
        for line in self.lines(3):
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(TABLE_RULE.match(c) for c in cells if c):
                continue
            if not seen_header:
                seen_header = True
                continue
            if len(cells) < 3:
                continue
            rows.append((cells[0], platform_value(cells[1]), platform_value(cells[2]), cells))
        return rows

    def platform(self, platform):
        """(row label, organic, paid, note) for a roster platform value, or None if no row."""
        table = self.platform_table()
        p = platform.strip().lower()

        def first(pred):
            for label, organic, paid, _ in table:
                if pred(norm(label)):
                    return label, organic, paid
            return None

        hit = None
        if p in ("podcast", "newsletter"):
            hit = first(lambda lab: "podcast" in lab or "newsletter" in lab)
        elif p == "x":
            hit = first(lambda lab: lab == "x" or lab.startswith("x "))
        elif p in PLATFORMS and p not in ("bluesky", "threads", "other"):
            hit = first(lambda lab: lab.startswith(p))
        if hit:
            return hit + ("",)
        other = first(lambda lab: lab.startswith("other"))
        if other:
            return other + (f"{p} has no row of its own in programme section 3; read from the 'other' row",)
        return None


def split_line(line):
    """(label, value) for a top-level '- label: value' line of the programme file, or None."""
    if not line.startswith("- "):
        return None
    body = line[2:].strip()
    flat = " ".join(body.split())
    for label in TEMPLATE_LABELS:
        if flat.startswith(label + ":"):
            return label, flat[len(label) + 1:].strip()
    if ":" not in body:
        return None
    label, _, value = body.partition(":")
    return label.strip(), value.strip()


def platform_value(cell):
    v = clean(cell).lower()
    m = PLATFORM_VALUE.match(v)
    return m.group(1) if m else ("" if not v else "unknown")


def clean(text):
    text = MARK.sub("", text or "")
    return text.replace("`", "").strip().strip(";").strip()


def read_roster(workspace):
    path = Path(workspace) / "data" / "creators.csv"
    if not path.is_file():
        raise InputError(f"No roster at {path}; set up the workspace with program-setup and add the creator with creator-roster.")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise InputError("data/creators.csv is empty; it needs the header row from the schemas.")
        header = [h.strip() for h in header]
        if header != ROSTER_HEADER:
            missing = [c for c in ROSTER_HEADER if c not in header]
            extra = [c for c in header if c not in ROSTER_HEADER]
            detail = f"missing: {', '.join(missing) or 'none'}; extra: {', '.join(extra) or 'none'}"
            if not missing and not extra:
                detail = "the columns are out of order"
            raise InputError(f"data/creators.csv does not have the schema's header ({detail}); repair it with creator-roster's check before running this.")
        rows = []
        for record in reader:
            if not any(cell.strip() for cell in record):
                continue
            rows.append({k: (record[i].strip() if i < len(record) else "") for i, k in enumerate(header)})
    return rows


def roster_row(rows, ref):
    """The one roster row for ref. Raises InputError when it is missing or duplicated."""
    hits = [r for r in rows if r["creator_ref"] == ref]
    if not hits:
        raise InputError(f"{ref} is not in data/creators.csv; add the creator with creator-roster first.")
    if len(hits) > 1:
        raise InputError(f"{ref} appears {len(hits)} times in data/creators.csv; merge the rows with creator-roster first.")
    return hits[0]
