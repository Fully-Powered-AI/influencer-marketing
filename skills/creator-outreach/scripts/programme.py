"""Shared reader for the workspace files used by the creator-outreach scripts.

Reads `program/program.md` by its fixed section numbers and the CSV headers from the
pack's schemas. Standard library only. Imported by offer_calc.py and pipeline_stage.py,
which add this folder to the end of sys.path so that `python3 -I` still works.

Sources:
- Section numbers and line prompts: skills/program-setup/assets/program-template.md,
  template versions 0.1.0 to 0.1.2, 2026-10-20. Lines are found by key phrases, so wording that
  program-setup refines inside a section still parses as long as the phrase stays.
- The margin-basis line and the per-order definitions: references/schemas.md of the pack,
  section 12 (Shared definitions), 2026-10-20.
- Source marks [owner], [observed], [default], [open]: the same template, opening lines.
- CSV headers: references/schemas.md of the pack (runtime copy in creator-roster),
  sections 4, 5 and 11, 2026-10-20.
"""

import csv
import os
import re
from decimal import Decimal, InvalidOperation


class ProgrammeError(Exception):
    """A value a script needs is missing or unreadable. The message says what to fix."""


SECTION_RE = re.compile(r'^##\s+(\d+)\.\s')
MARK_RE = re.compile(r'\[(owner|observed|default|open)\]', re.IGNORECASE)
DATE_RE = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
NUM_RE = re.compile(r'(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?')
EMPTY_WORDS = {'', 'tbd', 'to be decided', '?', '-', 'n/a', 'unknown', 'not yet decided'}

# The template's prompt text for lines whose prompt has more than one colon, so the
# value is everything after the prompt (template versions 0.1.0 to 0.1.2).
PROMPTS = {
    'default_model': 'Default model for new creators: `cpa` (commission on tracked sales), '
                     '`flat` (fee per deliverable), `hybrid` (small fee plus commission), '
                     '`gift` (product only). Default for this programme:',
    'basis': 'Commission basis: `subtotal after discounts, before shipping and tax` '
             '[default] or another:',
    'anchors': "Flat-fee anchors by tier, store currency, for the owner's reference only "
               '(ranges, not offers): nano / micro / mid / macro:',
    'breakeven': 'Break-even check inputs the `creator-outreach` skill uses: average order '
                 'value, gross margin band, customer discount, commission rate (copied from '
                 'above so a script can read one section):',
}
LAST_COLON_KEYS = set(PROMPTS)

# Key phrases, checked in this order; the first match claims the line.
SECTION_KEYS = {
    1: [('aov', ('average order value',)),
        ('margin', ('margin',)),
        ('currency', ('store currency',))],
    10: [('sending', ('sending account',))],
    4: [('breakeven', ('break-even', 'break even')),
        ('commission_rate', ('commission rate',)),
        ('basis', ('commission basis',)),
        ('discount', ('customer-facing discount', 'customer discount', 'discount carried')),
        ('anchors', ('anchor',)),
        ('approval', ('approve',)),
        ('default_model', ('default model',))],
}

KEY_NAMES = {
    'aov': 'average order value', 'margin': 'gross margin band', 'currency': 'store currency',
    'breakeven': 'break-even check inputs', 'commission_rate': 'commission rate',
    'basis': 'commission basis', 'discount': 'customer-facing discount',
    'anchors': 'flat-fee anchors by tier', 'approval': 'who approves a flat or hybrid deal',
    'default_model': 'default model for new creators',
    'sending': 'sending account per outreach channel',
}

# Template 0.1.2 instruction text on the indented line under the margin band; what follows
# it is the owner's answer (list price or net revenue).
MARGIN_BASIS_PROMPT = 'State whether the band is on list price or on net revenue'
# Indented template instructions that are never a value.
DETAIL_PROMPTS = (MARGIN_BASIS_PROMPT,)

CREATORS_HEADER = [
    'creator_ref', 'display_name', 'primary_platform', 'primary_handle', 'profile_url',
    'other_platforms', 'tier', 'followers_primary', 'followers_as_of', 'engagement_rate_pct',
    'engagement_as_of', 'niche_tags', 'audience_fit_score', 'brand_safety_flag',
    'contact_path', 'contact_email', 'status', 'compensation_model', 'commission_rate_pct',
    'flat_fee', 'code', 'affiliate_link', 'rail', 'agreement_date', 'agreement_file',
    'usage_rights_until', 'exclusivity_until', 'first_campaign', 'last_activity', 'notes',
]
PIPELINE_HEADER = [
    'campaign_slug', 'creator_ref', 'stage', 'stage_date', 'next_action', 'next_action_date',
    'owner_role', 'last_message_date', 'offer_summary', 'notes',
]
STATEMENT_HEADER = [
    'period', 'creator_ref', 'display_name', 'rail', 'orders_attributed', 'orders_excluded',
    'gross_sales', 'refunds', 'commission_basis', 'commission_rate_pct', 'commission_due',
    'flat_fee_due', 'total_due', 'holdback_until', 'status', 'notes',
]


def programme_path(workspace):
    return os.path.join(workspace, 'program', 'program.md')


def read_sections(workspace):
    """Return {section number: [lines]} for the programme file."""
    path = programme_path(workspace)
    if not os.path.isfile(path):
        raise ProgrammeError('program/program.md was not found in the workspace; '
                             'run program-setup first.')
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    sections, current = {}, None
    for line in lines:
        match = SECTION_RE.match(line)
        if match:
            current = int(match.group(1))
            sections[current] = []
            continue
        if line.startswith('## '):
            current = None
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def bullet_items(section_lines):
    """(top-level '- ' bullet, [its indented detail lines]) pairs.

    Template 0.1.1 puts the value after the template's text and extra detail on indented
    lines with their own marks, so detail is kept apart and used only when the main line
    carries no value, and then only detail lines that carry a mark and are not the
    template's own indented instructions. An unmarked indented line is template text and is
    never read as a value. Detail is not joined onto a main line that has a value, so a
    number in the detail (a measuring window, say) cannot pass for the field's figure.
    """
    items = []
    for line in section_lines:
        if line.startswith('- '):
            items.append((line[2:].strip(), []))
        elif items and line[:1] in (' ', '\t') and line.strip():
            items[-1][1].append(line.strip().lstrip('-').strip())
    return items


def split_item(text, key=None):
    """Split a bullet into (label, value)."""
    prompt = PROMPTS.get(key)
    if prompt and text.startswith(prompt):
        return prompt, text[len(prompt):].strip()
    if text.rstrip().endswith(':'):
        return text, ''
    sep = text.rfind(': ') if key in LAST_COLON_KEYS else text.find(': ')
    if sep == -1:
        return text, ''
    return text[:sep], text[sep + 2:].strip()


def classify(section_number, sections):
    """Return {key: {'value', 'marks', 'raw'}} for the known lines of one section."""
    found = {}
    for item, detail in bullet_items(sections.get(section_number, [])):
        rough_label = item.split(': ', 1)[0].lower()
        for key, phrases in SECTION_KEYS.get(section_number, []):
            if not any(p in rough_label for p in phrases):
                continue
            if key in found:
                raise ProgrammeError(f'Programme section {section_number} states the '
                                     f'{KEY_NAMES[key]} on two lines; keep one.')
            _, value = split_item(item, key)
            marked = [d for d in detail if MARK_RE.search(d) and not d.startswith(DETAIL_PROMPTS)]
            if not MARK_RE.sub('', value).strip() and marked:
                value = ' '.join(marked)
            marks = [m.lower() for m in MARK_RE.findall(value)]
            clean = MARK_RE.sub('', value).replace('`', '').strip().rstrip('.').strip()
            found[key] = {'value': clean, 'marks': marks, 'raw': value}
            break
    return found


def margin_basis(sections):
    """('list' or 'net', label, raw) from the indented line under the section 1 margin band.

    schemas.md section 12: the margin is read on list price unless section 1 says otherwise.
    'net' means on revenue per order, after the customer discount.
    """
    for item, detail in bullet_items(sections.get(1, [])):
        if 'margin' not in item.split(': ', 1)[0].lower():
            continue
        for line in detail:
            if not line.startswith(MARGIN_BASIS_PROMPT):
                continue
            answer = line[len(MARGIN_BASIS_PROMPT):]
            answer = answer.split('otherwise', 1)[-1] if 'otherwise' in answer else answer
            marks = [m.lower() for m in MARK_RE.findall(answer)]
            text = MARK_RE.sub('', answer).replace('`', '').strip(' .:;,').lower()
            # An unmarked indented line is template text, never the owner's answer (the
            # pack lead's parsing rule, 2026-10-20); [open] or a blank answer is missing.
            if not marks or 'open' in marks or not text:
                break
            if 'net' in text:
                return 'net', label_for({'marks': marks}, 1), text
            if 'list' in text:
                return 'list', label_for({'marks': marks}, 1), text
            raise ProgrammeError('Programme section 1, the line under the gross margin band, says '
                                 f'"{text}"; it should say list price or net revenue.')
    return 'list', 'pack default (schemas.md section 12): list price, section 1 does not say otherwise', ''


def is_missing(entry):
    return entry is None or 'open' in entry['marks'] or entry['value'].lower() in EMPTY_WORDS


def require(found, key, section_number):
    entry = found.get(key)
    if entry is None:
        raise ProgrammeError(f'Programme section {section_number} has no line for the '
                             f'{KEY_NAMES[key]}; add it (see the programme template).')
    if is_missing(entry):
        state = 'is marked [open]' if 'open' in entry['marks'] else 'is empty'
        raise ProgrammeError(f'Programme section {section_number}, {KEY_NAMES[key]}, {state}; '
                             'the owner fills it with program-setup before this runs.')
    return entry


def label_for(entry, section_number):
    """Contract label for a value read from the programme, from its source mark."""
    marks = entry['marks']
    if 'observed' in marks:
        return f'Measured (marked [observed] in programme section {section_number})'
    if 'owner' in marks:
        return f'User-provided (the owner, programme section {section_number})'
    if 'default' in marks:
        return f'User-provided (pack default the owner accepted, programme section {section_number})'
    return f'User-provided (no source mark in programme section {section_number})'


def numbers(text):
    """Decimal numbers in text, ignoring ISO dates and thousands separators."""
    out = []
    for raw in NUM_RE.findall(DATE_RE.sub(' ', text)):
        try:
            out.append(Decimal(raw.replace(',', '')))
        except InvalidOperation:
            continue
    return out


def table_rows(section_lines):
    """Rows of the first markdown table in a section, header and separator removed."""
    rows, seen_header = [], False
    for line in section_lines:
        stripped = line.strip()
        if not stripped.startswith('|'):
            if seen_header and rows:
                break
            continue
        cells = [c.strip() for c in stripped.strip('|').split('|')]
        if not seen_header:
            seen_header = True
            continue
        if all(set(c) <= set('-: ') for c in cells):
            continue
        rows.append(cells)
    return rows


def roles(sections):
    """Role names from the section 10 table, lower case."""
    names = [MARK_RE.sub('', r[0]).strip().lower() for r in table_rows(sections.get(10, []))]
    names = [n for n in names if n]
    if not names:
        raise ProgrammeError('Programme section 10 has no roles table; program-setup fills it.')
    return names


PLATFORM_ROW = {
    'instagram': 'instagram', 'tiktok': 'tiktok', 'youtube': 'youtube', 'x': 'x',
    'onlyfans': 'onlyfans', 'reddit': 'reddit', 'podcast': 'podcasts', 'newsletter': 'podcasts',
}


def platform_rule(sections, platform):
    """(row platform cell, organic value, conditions text) for a roster platform value.

    organic value is one of yes, no, with conditions, unknown.
    """
    wanted = PLATFORM_ROW.get(platform, 'other')
    for cells in table_rows(sections.get(3, [])):
        name = cells[0].lower()
        if name == wanted or name.startswith(wanted + ' ') or (wanted == 'podcasts' and 'podcast' in name):
            organic_raw = cells[1] if len(cells) > 1 else ''
            organic = MARK_RE.sub('', organic_raw).replace('`', '').strip().lower()
            if organic.startswith('yes'):
                state = 'yes'
            elif organic.startswith('with conditions'):
                state = 'with conditions'
            elif organic.startswith('no'):
                state = 'no'
            else:
                state = 'unknown'
            return cells[0], state, organic_raw.strip()
    return None, 'unknown', ''


def read_csv(path, header, what):
    """Rows of a CSV whose header must equal the schema header exactly."""
    if not os.path.isfile(path):
        raise ProgrammeError(f'{what} was not found at {path}; program-setup creates it.')
    with open(path, encoding='utf-8', newline='') as fh:
        reader = csv.reader(fh)
        try:
            got = next(reader)
        except StopIteration:
            raise ProgrammeError(f'{what} is empty; it needs the header row from schemas.md.')
        if got != header:
            missing = [c for c in header if c not in got]
            extra = [c for c in got if c not in header]
            detail = []
            if missing:
                detail.append('missing ' + ', '.join(missing))
            if extra:
                detail.append('extra ' + ', '.join(extra))
            if not detail:
                detail.append('columns out of order')
            raise ProgrammeError(f'{what} header differs from schemas.md ({"; ".join(detail)}); '
                                 'run creator-roster check and fix the header.')
        rows = []
        for values in reader:
            if not any(v.strip() for v in values):
                continue
            if len(values) != len(header):
                raise ProgrammeError(f'{what} has a row with {len(values)} cells where the '
                                     f'header has {len(header)}; run creator-roster check.')
            rows.append(dict(zip(header, values)))
    return rows
