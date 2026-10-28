#!/usr/bin/env python3
"""Offer arithmetic for creator-outreach.

Reads programme sections 1 and 4 of <workspace>/program/program.md and prints, for one
tracked order at the average order value: the customer discount, the commission, the
contribution after commission at the low and high end of the gross margin band, and the
highest commission rate before an order loses money. With --flat it prints the tracked
orders needed to recover the fee, for a flat deal and for a hybrid deal. With --tier it
compares the fee with the owner's anchor range for that tier. With --creator it lists the
creator's past results from payouts/*/statement.csv. Every figure carries its label.

Run: python3 -I offer_calc.py <workspace> [--flat FEE] [--commission PCT] [--discount PCT]
                               [--tier TIER] [--creator REF] [--as-of YYYY-MM-DD]

Exit 0 on success; 1 when a programme value or an argument is missing or unreadable (the
message names it); 2 on a partial run (something was skipped; the first line says what).
Standard library only; no network.

How the figures are built: the pack's per-order definition, references/schemas.md section 12
(Shared definitions), 2026-10-20, which campaign-plan and the reports use as well.
- Average order value as programme section 1 states it, before discounts.
- Revenue per order = average order value x (1 - customer discount). A fixed-amount discount
  is subtracted instead, capped at the order value (the build's extension of section 12,
  which writes the discount as a share).
- Cost of goods per order = average order value x (1 - gross margin), the margin read on list
  price; when the indented line under the section 1 margin band says net revenue, cost of
  goods = revenue per order x (1 - gross margin).
- Commission per order = rate x revenue per order. When programme section 4 names the
  subtotal before discounts as the basis, commission = rate x average order value (section
  12's commission-basis entry: as programme section 4 states it).
- Contribution per order = revenue - cost of goods - commission. A flat fee breaks even at
  fee / contribution, rounded up to whole orders; a flat-only deal has no commission.
The build's choices: money is rounded half up to cents for display only; every comparison uses the exact
  figure. The highest commission rate is rounded down to one decimal so the stated rate
  never loses money. Break-even order counts are rounded up to whole orders.
"""

import argparse
import glob
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import programme as pg  # noqa: E402  (shared reader in this folder)

HUNDRED = Decimal(100)
CENT = Decimal('0.01')
TENTH = Decimal('0.1')
TIERS = ('nano', 'micro', 'mid', 'macro')  # schemas.md section 4, tier column
CURRENCY_RE = re.compile(r'\b[A-Z]{3}\b')


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error; the pack reserves 2 for a partial run."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f'{self.prog}: {message}', file=sys.stderr)
        sys.exit(1)


def fail(message):
    raise pg.ProgrammeError(message)


def money(cur, value):
    return f'{cur} {value.quantize(CENT, ROUND_HALF_UP):,.2f}'


def plain(value):
    return f'{value.quantize(CENT, ROUND_HALF_UP):.2f}'


def pct(value):
    return format(value.normalize(), 'f')


def decimal_arg(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f'{text!r} is not a number')
    if value < 0:
        raise argparse.ArgumentTypeError('must not be negative')
    return value


def iso_date(text):
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f'{text!r} is not a date in YYYY-MM-DD form')


# ---- reading the programme -------------------------------------------------------------

def one_number(entry, section, what, example):
    nums = pg.numbers(entry['value'])
    if len(nums) != 1:
        fail(f'Programme section {section}, {what}, should carry one number (found '
             f'{len(nums)}); write it as {example}.')
    return nums[0]


def read_aov(entry):
    value = one_number(entry, 1, 'average order value', "'42.00 USD, measured 2026-09-30'")
    if value <= 0:
        fail('Programme section 1, average order value, must be above zero.')
    found = pg.DATE_RE.search(entry['value'])
    return value, (found.group(0) if found else None)


def read_margin(entry):
    nums = pg.numbers(entry['value'])
    if len(nums) not in (1, 2):
        fail('Programme section 1, gross margin band, should be one percent or a range of '
             f'two (found {len(nums)} numbers); write it as \'55 to 65 percent\'.')
    if all(n <= 1 for n in nums):
        fail('Programme section 1, gross margin band, looks like a fraction; write percent, '
             'for example 55 to 65.')
    if any(n <= 0 or n >= 100 for n in nums):
        fail('Programme section 1, gross margin band, must lie between 0 and 100 percent.')
    return min(nums), max(nums)


def read_currency(entry):
    found = CURRENCY_RE.search(entry['value'])
    if not found:
        fail('Programme section 1, store currency, should be a three-letter code such as USD.')
    return found.group(0)


def read_rate(entry, section, what):
    if entry['value'].lower().startswith('none'):
        return Decimal(0)
    value = one_number(entry, section, what, "'15 percent'")
    if value >= 100:
        fail(f'Programme section {section}, {what}, must be below 100 percent.')
    return value


def read_discount(entry):
    text = entry['value']
    lower = text.lower()
    if lower.startswith('none'):
        return 'percent', Decimal(0)
    value = one_number(entry, 4, 'customer-facing discount', "'15 percent' or '5.00 USD'")
    if '%' in text or 'percent' in lower or 'pct' in lower:
        if value >= 100:
            fail('Programme section 4, customer-facing discount, must be below 100 percent.')
        return 'percent', value
    if CURRENCY_RE.search(text) or 'fixed' in lower or 'dollar' in lower:
        return 'fixed', value
    fail('Programme section 4, customer-facing discount, does not say whether it is a '
         "percent or a fixed amount; write '15 percent' or '5.00 USD'.")


def read_basis(entry):
    lower = entry['value'].lower()
    if 'after discount' in lower:
        return 'after'
    if 'before discount' in lower:
        return 'before'
    fail('Programme section 4, commission basis, is neither the subtotal after discounts nor '
         'before discounts; this script computes only those two. Ask the owner which applies.')


def read_copy_line(entry):
    """Numbers per label in the section 4 break-even line, or None if it has no labels."""
    lower = entry['value'].lower()
    keys = [('aov', 'average order value'), ('margin', 'margin'),
            ('discount', 'discount'), ('commission', 'commission')]
    spots = sorted((lower.find(word), key, len(word)) for key, word in keys if word in lower)
    if not spots:
        return None
    parts = {}
    for i, (start, key, length) in enumerate(spots):
        end = spots[i + 1][0] if i + 1 < len(spots) else len(lower)
        segment = entry['value'][start + length:end]
        nums = pg.numbers(segment)
        if not nums and 'none' in segment.lower():
            nums = [Decimal(0)]
        parts[key] = nums
    return parts


def check_copy(parts, aov, margin, discount, rate):
    """Refuse a break-even line that disagrees with the lines it copies."""
    expected = {
        'aov': ([aov], 'section 1 average order value'),
        'margin': (sorted({margin[0], margin[1]}), 'section 1 gross margin band'),
        'discount': ([discount[1]], 'section 4 customer-facing discount'),
        'commission': ([rate], 'section 4 commission rate'),
    }
    for key, nums in parts.items():
        want, where = expected[key]
        got = sorted(set(nums)) if key == 'margin' else nums
        if got != want:
            shown = ' to '.join(pct(n) for n in nums) or 'nothing'
            fail(f"Programme section 4's break-even line gives {shown} where the {where} "
                 f"gives {' to '.join(pct(n) for n in want)}; correct the one that is wrong.")


def read_anchor(entry, tier):
    """(low, high) for a tier from the section 4 anchors line, or None if not stated."""
    lower = entry['value'].lower()
    spots = []
    for name in TIERS:
        hit = re.search(rf'\b{name}\b', lower)
        if hit:
            spots.append((hit.start(), name))
    spots.sort()
    for i, (start, name) in enumerate(spots):
        if name != tier:
            continue
        end = spots[i + 1][0] if i + 1 < len(spots) else len(lower)
        nums = pg.numbers(entry['value'][start + len(name):end])
        if len(nums) == 1:
            return nums[0], nums[0]
        if len(nums) == 2:
            return min(nums), max(nums)
        return None
    return None


# ---- arithmetic -----------------------------------------------------------------------

def per_order(aov, discount, rate, basis, margin, margin_on='list'):
    kind, amount = discount
    disc = aov * amount / HUNDRED if kind == 'percent' else min(amount, aov)
    paid = aov - disc
    cogs = (aov if margin_on == 'list' else paid) * (HUNDRED - margin) / HUNDRED
    gross = paid - cogs
    base = paid if basis == 'after' else aov
    commission = base * rate / HUNDRED
    contribution = gross - commission
    ceiling = (gross / base * HUNDRED) if (base > 0 and gross > 0) else Decimal(0)
    return {'disc': disc, 'paid': paid, 'cogs': cogs, 'gross': gross,
            'commission': commission, 'contribution': contribution, 'ceiling': ceiling}


def orders_to_recover(fee, contribution):
    if contribution <= 0:
        return 'never: each order loses money'
    exact = fee / contribution
    whole = exact.to_integral_value(rounding=ROUND_CEILING)
    return f'{whole} ({plain(exact)})'


def offer_summary(model, rate, discount, fee=None):
    kind, amount = discount
    code = (f'code {pct(amount)} pct off' if kind == 'percent' else f'code {plain(amount)} off')
    if model == 'cpa':
        return f'cpa {pct(rate)} pct, {code}, no fee'
    if model == 'flat':
        return f'flat, {code}, fee {plain(fee)}'
    return f'hybrid {pct(rate)} pct, {code}, fee {plain(fee)}'


# ---- past results ---------------------------------------------------------------------

def history(workspace, ref, cur):
    lines, partial = [], []
    creators = pg.read_csv(os.path.join(workspace, 'data', 'creators.csv'),
                           pg.CREATORS_HEADER, 'data/creators.csv')
    row = next((r for r in creators if r['creator_ref'] == ref), None)
    if row is None:
        fail(f'{ref} is not in data/creators.csv; add the creator with creator-roster first.')
    lines.append(f'## Past results for {ref}')
    lines.append('')
    fields = ['status', 'compensation_model', 'commission_rate_pct', 'flat_fee', 'code',
              'rail', 'agreement_date', 'usage_rights_until', 'exclusivity_until',
              'last_activity']
    shown = '; '.join(f'{f} {row[f] or "(empty)"}' for f in fields)
    lines.append(f'Roster row (data/creators.csv, as recorded): {shown}.')
    lines.append('')
    files = sorted(glob.glob(os.path.join(workspace, 'payouts', '*', 'statement.csv')))
    found = []
    for path in files:
        rel = os.path.relpath(path, workspace)
        try:
            rows = pg.read_csv(path, pg.STATEMENT_HEADER, rel)
        except pg.ProgrammeError as err:
            partial.append(f'{rel} skipped: {err}')
            continue
        found.extend((rel, r) for r in rows if r['creator_ref'] == ref)
    if not found:
        lines.append(f'No statement rows for {ref}: looked in {len(files)} statement file(s) '
                     'under payouts/ and found none. There are no measured results to quote.')
        lines.append('')
        return lines, partial
    cols = [('orders_attributed', 'int'), ('orders_excluded', 'int'), ('gross_sales', 'money'),
            ('refunds', 'money'), ('commission_due', 'money'), ('flat_fee_due', 'money'),
            ('total_due', 'money')]
    heads = [c.replace('_', ' ') + ('' if kind == 'int' else f' ({cur})') for c, kind in cols]
    lines.append('| period | ' + ' | '.join(heads) + ' | status |')
    lines.append('|' + '---|' * (len(cols) + 2))
    totals = {c: Decimal(0) for c, _ in cols}
    gaps = {c: 0 for c, _ in cols}
    for rel, r in sorted(found, key=lambda item: item[1]['period']):
        cells = []
        for col, _ in cols:
            raw = r[col].strip()
            try:
                totals[col] += Decimal(raw)
                cells.append(raw)
            except InvalidOperation:
                gaps[col] += 1
                cells.append('unknown')
        lines.append(f"| {r['period']} | " + ' | '.join(cells) + f" | {r['status'] or 'unknown'} |")
    total_cells = []
    for col, kind in cols:
        value = str(int(totals[col])) if kind == 'int' else plain(totals[col])
        if gaps[col]:
            value = f'incomplete: {value} from {len(found) - gaps[col]} of {len(found)} rows'
        total_cells.append(value)
    lines.append('| total | ' + ' | '.join(total_cells) + ' | |')
    lines.append('')
    statuses = sorted({r['status'] or 'unknown' for _, r in found})
    lines.append('Measured: rows from ' + ', '.join(sorted({rel for rel, _ in found})) +
                 ', computed by commission-statement from the store orders export. Status as '
                 f"recorded ({', '.join(statuses)}); a draft row is not yet approved by the owner.")
    lines.append('')
    return lines, partial


# ---- main -----------------------------------------------------------------------------

def build(args):
    ws = args.workspace
    sections = pg.read_sections(ws)
    s1, s4 = pg.classify(1, sections), pg.classify(4, sections)
    aov_e = pg.require(s1, 'aov', 1)
    margin_e = pg.require(s1, 'margin', 1)
    cur_e = pg.require(s1, 'currency', 1)
    rate_e = pg.require(s4, 'commission_rate', 4)
    disc_e = pg.require(s4, 'discount', 4)
    basis_e = pg.require(s4, 'basis', 4)

    aov, aov_date = read_aov(aov_e)
    low, high = read_margin(margin_e)
    cur = read_currency(cur_e)
    prog_rate = read_rate(rate_e, 4, 'commission rate')
    prog_disc = read_discount(disc_e)
    basis = read_basis(basis_e)
    margin_on, margin_label, _ = pg.margin_basis(sections)

    notes, missing, partial = [], [], []
    copy_e = s4.get('breakeven')
    if pg.is_missing(copy_e):
        notes.append("Section 4's break-even line is empty; the values were read from their "
                     'own lines in sections 1 and 4.')
    else:
        parts = read_copy_line(copy_e)
        if parts is None:
            notes.append("Section 4's break-even line has no labels this script can read, so "
                         'it was not checked against sections 1 and 4.')
        else:
            check_copy(parts, aov, (low, high), prog_disc, prog_rate)
            notes.append("Section 4's break-even line agrees with the lines it copies.")

    rate = args.commission if args.commission is not None else prog_rate
    discount = ('percent', args.discount) if args.discount is not None else prog_disc
    if rate >= HUNDRED or (discount[0] == 'percent' and discount[1] >= HUNDRED):
        fail('An override must be below 100 percent.')

    model_e = s4.get('default_model')
    model = None
    if not pg.is_missing(model_e):
        hit = re.search(r'\b(cpa|flat|hybrid|gift)\b', model_e['value'].lower())
        model = hit.group(1) if hit else None
    if model is None:
        missing.append('section 4 default model')

    out = []
    out.append('# Offer arithmetic')
    out.append('')
    out.append(f'Computed by scripts/offer_calc.py from program/program.md in the workspace, '
               f'as of {args.as_of.isoformat()}. Paste this block as it stands; do not retype '
               'its figures.')
    out.append('')
    out.append('## Inputs')
    out.append('')
    out.append('| input | value | label |')
    out.append('|---|---|---|')
    out.append(f'| store currency | {cur} | {pg.label_for(cur_e, 1)} |')
    dated = f', measured {aov_date}' if aov_date else ', measurement date not stated'
    if not aov_date:
        missing.append('section 1 date the average order value was measured')
    out.append(f'| average order value | {money(cur, aov)}{dated} | {pg.label_for(aov_e, 1)} |')
    band = f'{pct(low)} percent' if low == high else f'{pct(low)} to {pct(high)} percent'
    out.append(f'| gross margin band | {band} | {pg.label_for(margin_e, 1)} |')
    if args.discount is not None:
        prog_shown = (f'{pct(prog_disc[1])} percent' if prog_disc[0] == 'percent'
                      else money(cur, prog_disc[1]))
        out.append(f'| customer discount | {pct(discount[1])} percent | User-provided '
                   f'(--discount override; programme section 4 says {prog_shown}) |')
    else:
        shown = (f'{pct(discount[1])} percent' if discount[0] == 'percent'
                 else f'{money(cur, discount[1])} fixed')
        out.append(f'| customer discount | {shown} | {pg.label_for(disc_e, 4)} |')
    if args.commission is not None:
        out.append(f'| commission rate | {pct(rate)} percent | User-provided (--commission '
                   f'override; programme section 4 says {pct(prog_rate)} percent) |')
    else:
        out.append(f'| commission rate | {pct(rate)} percent | {pg.label_for(rate_e, 4)} |')
    out.append(f'| gross margin read on | '
               f"{'list price' if margin_on == 'list' else 'net revenue (after the customer discount)'} | "
               f'{margin_label} |')
    basis_text = 'subtotal after discounts' if basis == 'after' else 'subtotal before discounts'
    out.append(f'| commission basis | {basis_text}, before shipping and tax | '
               f'{pg.label_for(basis_e, 4)} |')
    out.append(f'| default model | {model or "not stated"} | '
               f'{pg.label_for(model_e, 4) if model else "missing"} |')
    out.append('')

    margins = [low] if low == high else [low, high]
    figs = [per_order(aov, discount, rate, basis, m, margin_on) for m in margins]
    lo = figs[0]
    head = ' | '.join(f'at {pct(m)} percent margin' for m in margins)
    rule = '|---|' + '---|' * len(margins)
    out.append('## One tracked order at the average order value')
    out.append('')
    out.append('Every row is Estimated: computed from the inputs above for one order at the '
               'average order value.')
    out.append('')
    out.append(f'| figure | {head} |')
    out.append(rule)
    rows = [
        ('order subtotal before the discount', lambda f: money(cur, aov)),
        ('customer discount', lambda f: money(cur, f['disc'])),
        ('revenue per order: the subtotal the customer pays, before shipping and tax',
         lambda f: money(cur, f['paid'])),
        ('cost of goods', lambda f: money(cur, f['cogs'])),
        ('gross profit before commission', lambda f: money(cur, f['gross'])),
        (f'commission to the creator at {pct(rate)} percent', lambda f: money(cur, f['commission'])),
        ('contribution per order after commission', lambda f: money(cur, f['contribution'])),
        ('highest commission rate before an order loses money (rounded down)',
         lambda f: f"{pct(f['ceiling'].quantize(TENTH, ROUND_DOWN))} percent"),
    ]
    for name, cell in rows:
        out.append(f'| {name} | ' + ' | '.join(cell(f) for f in figs) + ' |')
    out.append('')

    warnings = []
    if lo['gross'] <= 0:
        warnings.append(f'At {pct(low)} percent margin the customer discount alone uses up the '
                        'gross profit: every creator order loses money before any commission.')
    elif lo['contribution'] <= 0:
        warnings.append(f'At {pct(low)} percent margin an order at {pct(rate)} percent commission '
                        'loses money: the rate is above the highest rate shown for that margin.')
    if args.commission is not None and args.commission != prog_rate:
        warnings.append('The commission rate tested differs from programme section 4; a rate '
                        'other than the programme\'s is the owner\'s decision (sections 4 and 10).')
    if args.discount is not None and discount != prog_disc:
        warnings.append('The discount tested differs from programme section 4; the discount '
                        'on a code is set in the programme, not in a negotiation.')

    summaries = [('default per-sale deal', offer_summary('cpa', rate, discount))]
    if args.flat is not None:
        if args.flat <= 0:
            fail('--flat must be above zero.')
        fee = args.flat
        out.append(f'## Flat fee of {money(cur, fee)}')
        out.append('')
        out.append('Tracked orders needed for the contribution to cover the fee. Estimated: '
                   'computed from the table above; whole orders rounded up, the exact quotient '
                   'in brackets.')
        out.append('')
        out.append(f'| deal | {head} |')
        out.append(rule)
        out.append('| flat: the fee, no commission | ' +
                   ' | '.join(orders_to_recover(fee, f['gross']) for f in figs) + ' |')
        if rate > 0:
            out.append(f'| hybrid: the fee plus {pct(rate)} percent commission | ' +
                       ' | '.join(orders_to_recover(fee, f['contribution']) for f in figs) + ' |')
        out.append('')
        summaries.append(('flat deal', offer_summary('flat', rate, discount, fee)))
        if rate > 0:
            summaries.append(('hybrid deal', offer_summary('hybrid', rate, discount, fee)))
        approval_e = s4.get('approval')
        if pg.is_missing(approval_e):
            partial.append('approval rule not shown: programme section 4 does not say when a flat '
                           'or hybrid deal is allowed or who approves one; no fee can be offered '
                           'until the owner sets it')
        else:
            out.append(f'Programme section 4 on flat and hybrid deals, quoted: '
                       f'"{approval_e["value"]}". Label: {pg.label_for(approval_e, 4)}.')
            out.append('')

    if args.tier:
        anchors_e = s4.get('anchors')
        anchor = None if pg.is_missing(anchors_e) else read_anchor(anchors_e, args.tier)
        if anchor is None:
            partial.append(f'tier comparison skipped: programme section 4 states no flat-fee '
                           f'anchor for {args.tier}')
        else:
            a_low, a_high = anchor
            shown = (money(cur, a_low) if a_low == a_high
                     else f'{money(cur, a_low)} to {money(cur, a_high)}')
            out.append(f'## Tier anchor for {args.tier}')
            out.append('')
            line = (f"Programme section 4 anchor for {args.tier}: {shown}, the owner's reference "
                    f'range, not an offer. Label: {pg.label_for(anchors_e, 4)}.')
            if args.flat is not None:
                place = ('inside' if a_low <= args.flat <= a_high
                         else 'below' if args.flat < a_low else 'above')
                line += f' The fee tested, {money(cur, args.flat)}, is {place} this range.'
            out.append(line)
            out.append('')

    if args.creator:
        lines, skipped = history(ws, args.creator, cur)
        out.extend(lines)
        partial.extend(skipped)

    out.append('## Lines for data/pipeline.csv')
    out.append('')
    for name, text in summaries:
        out.append(f'- offer_summary, {name}: {text}')
    out.append('')

    if warnings:
        out.append('## Warnings')
        out.append('')
        out.extend(f'- {w}' for w in warnings)
        out.append('')

    out.append('## Not in these figures')
    out.append('')
    out.append('Shipping, payment processing, rail and app fees, refunds, the holdback and the '
               'cost of any gifted product. If the margin band does not already allow for them, '
               'the contribution is lower than shown. The arithmetic is the pack\'s per-order '
               'definition (schemas.md section 12): the average order value is before discounts; '
               'if the owner measured it after discounts, the discount is counted twice and the '
               'contribution shown is low.')
    out.append('')
    for n in notes:
        out.append(n)
    out.append('')
    used = ['section 1 average order value, gross margin band and the line under it, store currency',
            'section 4 commission rate, customer-facing discount, commission basis']
    if args.flat is not None:
        used.append('section 4 flat and hybrid approval line')
    if args.tier:
        used.append('section 4 flat-fee anchors')
    if args.creator:
        used.append('data/creators.csv and payouts/*/statement.csv')
    overrides = [n for n, v in (('--commission', args.commission), ('--discount', args.discount),
                                ('--flat', args.flat)) if v is not None]
    if overrides:
        used.append('command-line ' + ', '.join(overrides))
    gaps = missing + partial
    out.append('Coverage: inputs used: ' + '; '.join(used) + '. Inputs missing: ' +
               ('; '.join(gaps) if gaps else 'none') + '. Not judged: whether creator orders '
               'match the average order value, how many orders this creator will drive, refunds, '
               'and the costs listed above.')

    if partial:
        out.insert(0, 'Partial: ' + '; '.join(partial) + '.')
        out.insert(1, '')
    return out, (2 if partial else 0)


def main():
    parser = Parser(
        description='Offer arithmetic for one tracked order, from programme sections 1 and 4.')
    parser.add_argument('workspace', help='the workspace folder (holds program/program.md)')
    parser.add_argument('--flat', type=decimal_arg, metavar='FEE',
                        help='a proposed flat fee in the store currency; prints the orders '
                             'needed to recover it for a flat and a hybrid deal')
    parser.add_argument('--commission', type=decimal_arg, metavar='PCT',
                        help='test another commission rate, in percent')
    parser.add_argument('--discount', type=decimal_arg, metavar='PCT',
                        help='test another customer discount, in percent')
    parser.add_argument('--tier', choices=TIERS,
                        help="compare the fee with the owner's anchor range for this tier")
    parser.add_argument('--creator', metavar='REF',
                        help="list this creator's roster deal and past statement results")
    parser.add_argument('--as-of', type=iso_date, default=datetime.now(timezone.utc).date(),
                        metavar='YYYY-MM-DD', help='date printed on the block (default today, UTC)')
    args = parser.parse_args()
    try:
        out, code = build(args)
    except pg.ProgrammeError as err:
        print(f'offer_calc: {err}', file=sys.stderr)
        return 1
    print('\n'.join(out))
    return code


if __name__ == '__main__':
    sys.exit(main())
