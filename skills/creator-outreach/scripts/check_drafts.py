#!/usr/bin/env python3
"""Check the message drafts in creator-outreach files before a person sends them.

  python3 -I check_drafts.py <workspace> <file> [<file> ...]

A draft is every block that starts with a heading of the form
  ### Draft: <touch> | channel: <dm|email|agent|form> [| case: <case>] [| send on: <date>]
where <touch> is first_touch, follow_up_1, follow_up_2, follow_up_3 or reply. The block runs
to the next heading. Files are read relative to the workspace unless absolute. Other
headings, the internal sections and quoted creator replies are not checked.

Fails a block for: a word count outside its band, an emoji or emoticon, an exclamation
mark, a dollar sign before a digit, more links than its touch allows, a hype phrase, a
stock opener in a first touch, a Subject line missing from an email or present in a DM.
Warns for a sentence with a product-claim word that does not contain an approved claim
from programme section 7 word for word, and lists bracketed placeholders still to fill.

Exit 0 when every block passes (warnings may remain; a person clears each); 1 when any
block fails or an input is unreadable (the message says what to fix); 2 when a block could
not be checked or no draft block was found. Standard library only.
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "references"))
from brand_context import claim_cues

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import programme as pg  # noqa: E402  (shared reader in this folder)

# Word bands per touch. first_touch 60 to 120: the pack brief for creator-outreach,
# 2026-10-20. The rest: the build's choice, each follow-up shorter than the first touch.
BANDS = {'first_touch': (60, 120), 'follow_up_1': (20, 80), 'follow_up_2': (20, 80),
         'follow_up_3': (15, 60), 'reply': (15, 150)}
# Links allowed per touch: none in a first touch, one after (build's choice, informed by
# the library's outreach-manager copy rules).
MAX_LINKS = {'first_touch': 0, 'follow_up_1': 1, 'follow_up_2': 1, 'follow_up_3': 1, 'reply': 1}
CHANNELS = ('dm', 'email', 'agent', 'form')
NEEDS_SUBJECT = ('email', 'agent')

# Build's choice, 2026-10-20: phrases that read as hype or as a template.
HYPE = ('amazing', 'incredible', 'awesome', 'game-changer', 'game changer', 'revolutionary',
        'best-in-class', 'world-class', 'obsessed', 'huge fan', 'biggest fan',
        'love your content', 'love your vibe', 'perfect fit', 'perfect match', 'dream collab',
        'exclusive opportunity', 'once-in-a-lifetime', 'once in a lifetime', "don't miss",
        'limited time', 'act now', '#1', 'number one', 'skyrocket', 'insane', 'mind-blowing',
        'next level', 'next-level', 'unbeatable', 'killer')
STOCK_OPENERS = ('hope this finds you', 'hope you are well', "hope you're well", 'my name is',
                 'i wanted to reach out', 'reaching out because', 'i came across your',
                 'i stumbled', 'quick question for you')
# Review cues only; the owner may replace them in programme section 7.
CLAIM_WORDS = ('safe', 'safer', 'compatible', 'compatibility', 'prevent', 'prevents', 'protect', 'protects', 'treat', 'treats', 'cure', 'cures', 'organic', 'natural', 'non-toxic', 'waterproof', 'hypoallergenic', 'clinically', 'certified', 'guaranteed', 'sustainable', 'biodegradable', 'recycled')

HEAD_RE = re.compile(r'^###\s+Draft:\s*(.+)$')
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.\-]*")
URL_RE = re.compile(r'https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|net|org|io|co|shop|store|ly|me|ai)\b',
                    re.IGNORECASE)
DOLLAR_RE = re.compile(r'\$\s*\d')
EMOTICON_RE = re.compile(r'(?:^|\s)[:;=][\-\']?[)(DPp](?=\s|$)')
PLACEHOLDER_RE = re.compile(r'\[[^\]\n]+\]')
EMOJI_RANGES = ((0x1F000, 0x1FFFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0x2300, 0x23FF),
                (0xFE0F, 0xFE0F), (0x200D, 0x200D))


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error; the pack reserves 2 for a partial run."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f'{self.prog}: {message}', file=sys.stderr)
        sys.exit(1)


def has_phrase(text, phrase):
    return re.search(r'(?<![\w#])' + re.escape(phrase) + r'(?![\w])', text) is not None


def approved_claims(sections):
    """Approved claim wording from programme section 7, lower case, spaces normalised."""
    claims, inside = [], False
    for line in sections.get(7, []):
        if line.startswith('### '):
            inside = line.lower().startswith('### approved')
            continue
        if inside and line.startswith('- '):
            text = pg.MARK_RE.sub('', line[2:])
            quoted = re.findall(r'["“]([^"”]+)["”]', text)
            for claim in (quoted or [re.sub(r'\([^)]*\)\s*$', '', text)]):
                claim = ' '.join(claim.lower().split()).strip(' .:')
                if claim:
                    claims.append(claim)
    return claims


def blocks(text):
    """(heading text, body lines) for every Draft block in a file."""
    out, current = [], None
    for line in text.splitlines():
        match = HEAD_RE.match(line)
        if match:
            current = (match.group(1), [])
            out.append(current)
            continue
        if line.startswith('#'):
            current = None
            continue
        if current is not None and not line.strip().startswith('<!--'):
            current[1].append(line)
    return out


def check_block(head, lines, claims, cues=CLAIM_WORDS):
    """(touch, channel, status, problems, warnings, placeholders); status pass, fail or skip."""
    parts = [p.strip() for p in head.split('|')]
    touch = parts[0].lower()
    fields = {}
    for p in parts[1:]:
        if ':' in p:
            key, value = p.split(':', 1)
            fields[key.strip().lower()] = value.strip().lower()
    channel = fields.get('channel', '')
    if touch not in BANDS:
        return touch, channel, 'skip', [f"touch '{touch}' is not one of {', '.join(BANDS)}"], [], []
    if channel not in CHANNELS:
        return touch, channel, 'skip', [f"channel '{channel or 'missing'}' is not one of "
                                        f"{', '.join(CHANNELS)}"], [], []
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    subject = None
    if lines and lines[0].lower().startswith('subject:'):
        subject, lines = lines[0][len('subject:'):].strip(), lines[1:]
    body = '\n'.join(lines).strip()
    whole = ((subject or '') + '\n' + body).strip()
    lower = whole.lower()
    problems, warnings = [], []
    if not body:
        return touch, channel, 'fail', ['the block has no message text'], [], []
    words = len(WORD_RE.findall(body))
    low, high = BANDS[touch]
    if not low <= words <= high:
        side = 'below' if words < low else 'above'
        problems.append(f'{words} words, {side} the {low} to {high} band for {touch}')
    if any(lo <= ord(ch) <= hi for ch in whole for lo, hi in EMOJI_RANGES) or EMOTICON_RE.search(whole):
        problems.append('an emoji or emoticon; remove it')
    if '!' in whole or '¡' in whole:
        problems.append('an exclamation mark; use a full stop')
    if DOLLAR_RE.search(whole):
        problems.append("a dollar sign before a digit; write 'USD 15' instead")
    links = URL_RE.findall(body)
    if len(links) > MAX_LINKS[touch]:
        problems.append(f'{len(links)} link(s); {touch} allows {MAX_LINKS[touch]}')
    hype = [p for p in HYPE if has_phrase(lower, p)]
    if hype:
        problems.append('hype phrase(s): ' + ', '.join(hype) + '; say the specific thing instead')
    if touch == 'first_touch':
        stock = [p for p in STOCK_OPENERS if p in lower]
        if stock:
            problems.append('stock opener(s): ' + ', '.join(stock) + '; open on what they made')
    if channel in NEEDS_SUBJECT and touch == 'first_touch' and not subject:
        problems.append(f'no Subject: line; a first touch by {channel} needs one')
    if channel == 'dm' and subject is not None:
        problems.append('a Subject: line in a DM; remove it')
    for sentence in re.split(r'(?<=[.?])\s+|\n+', body):
        s_lower = ' '.join(sentence.lower().split())
        hits = [w for w in cues if has_phrase(s_lower, w)]
        if hits and not any(c in s_lower for c in claims):
            warnings.append(f"claim word(s) {', '.join(hits)} in: \"{sentence.strip()}\"; a product "
                            'statement must be programme section 7 Approved wording, word for word')
    placeholders = PLACEHOLDER_RE.findall(whole)
    return touch, channel, ('fail' if problems else 'pass'), problems, warnings, placeholders


def main():
    parser = Parser(description='Check creator-outreach message drafts before sending.')
    parser.add_argument('workspace', help='the workspace folder (holds program/program.md)')
    parser.add_argument('files', nargs='+', help='outreach files, relative to the workspace')
    args = parser.parse_args()
    try:
        sections = pg.read_sections(args.workspace)
        claims = approved_claims(sections)
        cues = claim_cues(sections.get(7, []), CLAIM_WORDS)
    except (pg.ProgrammeError, ValueError) as err:
        print(f'check_drafts: {err}', file=sys.stderr)
        return 1
    totals = {'pass': 0, 'fail': 0, 'skip': 0}
    warn_count, fill_count = 0, 0
    for name in args.files:
        path = name if os.path.isabs(name) else os.path.join(args.workspace, name)
        if not os.path.isfile(path):
            print(f'check_drafts: {name} was not found in the workspace.', file=sys.stderr)
            return 1
        with open(path, encoding='utf-8') as fh:
            found = blocks(fh.read())
        print(f'## {name}')
        if not found:
            print('  no "### Draft:" blocks found; nothing was checked in this file')
            totals['skip'] += 1
            continue
        for head, lines in found:
            touch, channel, status, problems, warnings, holes = check_block(head, lines, claims, cues)
            totals[status] += 1
            label = {'pass': 'PASS', 'fail': 'FAIL', 'skip': 'NOT CHECKED'}[status]
            print(f'  {label} {touch} ({channel or "no channel"}): {head}')
            for p in problems:
                print(f'    - {p}')
            for w in warnings:
                print(f'    - WARN {w}')
            if holes:
                print('    - to fill before sending: ' + ', '.join(holes))
            warn_count += len(warnings)
            fill_count += len(holes)
    checked = totals['pass'] + totals['fail']
    print(f"Result: {checked} block(s) checked, {totals['pass']} passed, {totals['fail']} failed, "
          f"{totals['skip']} not checked; {warn_count} claim warning(s) for a person to clear; "
          f'{fill_count} placeholder(s) to fill. Approved claims read from programme section 7: '
          f'{len(claims)}.')
    if totals['fail']:
        return 1
    if totals['skip'] or checked == 0:
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
