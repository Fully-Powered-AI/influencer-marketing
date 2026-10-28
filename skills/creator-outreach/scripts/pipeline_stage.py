#!/usr/bin/env python3
"""Record an outreach stage in data/pipeline.csv, or show a campaign's outreach rows.

  python3 -I pipeline_stage.py <workspace> set --campaign SLUG --creator REF [--creator REF]
          --stage STAGE --owner-role ROLE [--date YYYY-MM-DD] [--offer TEXT] [--platform P]
          [--note TEXT] [--message-date D] [--approved-by ROLE --approved-on D]
          [--approval-id ID] [--due D] [--next-action TEXT --next-date D]
  python3 -I pipeline_stage.py <workspace> show --campaign SLUG [--as-of D]

`set` checks, before it writes anything: the role against programme section 10, the
campaign plan exists, the creator is on the roster, not excluded and not marked do not
contact, the platform the deal
is for against programme section 3, the move from the row's current stage, the follow-up
count, the dates, for a flat or hybrid agreement the approval named in programme
section 4, and for `approved` or a return to `content_due` the content-approval record and
its verdict. Then it writes one row per creator per campaign (schemas.md section 5), sets
the next action and its date, appends a dated note, moves the roster row's `last_activity`
forward to the stage date (the one roster cell it writes), and prints the dated creator-roster
commands for every other roster change. Several --creator values are checked together; if one fails, nothing is
written. The stage is a person's report of what happened; the script never sends anything.

Exit 0 on success; 1 on bad input or a refused move (the message says what to fix);
2 on a partial run (`set` skipped a creator already at the stage). Standard library only.
"""

import argparse
import csv
import io
import os
import re
import shlex
import sys
from datetime import datetime, timedelta, timezone

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import programme as pg  # noqa: E402  (shared reader in this folder)

# Stages this script records (schemas.md section 5, 2026-10-20): the outreach stages, and
# the delivery stages the programme lead records through this script after the brief is
# sent and after content-approval has written its record.
OUTREACH_STAGES = ('identified', 'first_touch', 'followed_up', 'replied', 'negotiating',
                   'agreed', 'declined', 'no_response')
DELIVERY_STAGES = ('briefed', 'content_due', 'content_submitted', 'approved')
# Stages another script writes; this one never moves a row into or out of them, except the
# move from onboarded to briefed.
OTHER_STAGES = {'onboarded': "affiliate-onboarding's recording script",
                'live': "publication-tracking's script", 'closed': 'a later step, not this script'}
STAGE_ORDER = OUTREACH_STAGES + ('onboarded',) + DELIVERY_STAGES + ('live', 'closed')
# content-approval verdicts (its approval-record template) that allow each move.
APPROVAL_VERDICTS = {'approved': ('approve', 'approve-with-changes'), 'content_due': ('stop',)}
VERDICT_RE = re.compile(r'^-\s*verdict:\s*([a-z-]+)', re.MULTILINE | re.IGNORECASE)

# Which current stage each new stage may follow; None means no row yet (build's choice).
ALLOWED_FROM = {
    'identified': {None},
    'first_touch': {None, 'identified'},
    'followed_up': {'first_touch', 'followed_up'},
    'replied': {'first_touch', 'followed_up', 'replied', 'no_response', 'declined'},
    'negotiating': {'replied', 'negotiating'},
    'agreed': {'replied', 'negotiating'},
    'declined': {'first_touch', 'followed_up', 'replied', 'negotiating'},
    'no_response': {'first_touch', 'followed_up'},
    'briefed': {'onboarded'},
    'content_due': {'briefed', 'content_submitted'},
    'content_submitted': {'content_due'},
    'approved': {'content_submitted'},
}

# The cadence. Three follow-ups, then no_response: the pack brief for creator-outreach,
# 2026-10-20. The spacing in calendar days is the build's choice, informed by the library's
# outreach-manager cadence; change it here and nowhere else.
MAX_FOLLOW_UPS = 3
FOLLOW_UP_AFTER_DAYS = (4, 5, 7)  # first touch to follow-up 1, 1 to 2, 2 to 3
NO_RESPONSE_AFTER_DAYS = 7        # follow-up 3 to recording no_response
REPLY_WITHIN_DAYS = 2             # a reply is answered within (build's choice)
NEGOTIATION_CHECK_DAYS = 5        # an open negotiation is looked at again after (build's choice)

# Roster status that follows a pipeline stage (build's choice). The roster is changed by
# creator-roster's update command, never by this script; it moves only from these statuses.
# The roster's `agreed` means agreed in writing, so the outreach `agreed` stage (agreed in
# principle) moves the pipeline only and prints the deal fields; status=agreed waits for
# partnership-agreement's hand-off with the agreement date (pack lead's ruling on review 4-F9).
STAGE_TO_STATUS = {'first_touch': 'contacted', 'negotiating': 'negotiating',
                   'declined': 'declined', 'no_response': 'prospect'}
STATUS_MAY_MOVE = {'prospect', 'contacted', 'negotiating', 'declined', 'ended'}

# A roster note with this phrase stops outreach for good (build's choice; creator-roster
# writes the note when a creator asks not to be contacted).
DO_NOT_CONTACT = 'do not contact'

MERGED_RE = re.compile(r'\bmerged into c-[a-z0-9]{6}\b')  # schemas.md section 4, roster rules

SLUG_RE = re.compile(r'^\d{4}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$')
REF_RE = re.compile(r'^c-[a-z0-9]{6}$')
OFFER_RE = re.compile(r'^(cpa|flat|hybrid|gift)\b')
FOLLOW_UP_NOTE_RE = re.compile(r'\bfollowed_up (\d+)\b')
PLATFORMS = ('instagram', 'tiktok', 'youtube', 'x', 'onlyfans', 'reddit', 'podcast',
             'newsletter', 'bluesky', 'threads', 'other')  # schemas.md section 4
ROSTER_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'creator-roster', 'scripts', 'roster.py')


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error; the pack reserves 2 for a partial run."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f'{self.prog}: {message}', file=sys.stderr)
        sys.exit(1)


def fail(message):
    raise pg.ProgrammeError(message)


def iso(text, what):
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        fail(f'{what} {text!r} is not a date in YYYY-MM-DD form.')


def clean_note(text):
    return ' '.join((text or '').replace(';', ',').split())


def follow_ups(notes):
    found = [int(n) for n in FOLLOW_UP_NOTE_RE.findall(notes or '')]
    return max(found) if found else 0


def next_step(stage, day, n, slug, ref, current=None, due=None):
    """(next_action, next_action_date, working) for a stage reached on day."""
    def plus(days, rule):
        return (day + timedelta(days=days)).isoformat(), (
            f'{(day + timedelta(days=days)).isoformat()} = stage_date {day.isoformat()} + '
            f'{days} calendar days ({rule} in scripts/pipeline_stage.py)')
    if stage == 'identified':
        return (f'send the first touch in campaigns/{slug}/outreach/{ref}.md from the brand '
                "account, then record first_touch"), day.isoformat(), 'the same day'
    if stage == 'first_touch':
        date, why = plus(FOLLOW_UP_AFTER_DAYS[0], 'FOLLOW_UP_AFTER_DAYS[0]')
        return 'if no reply, send follow-up 1 from the outreach file, then record followed_up', date, why
    if stage == 'followed_up' and n < MAX_FOLLOW_UPS:
        date, why = plus(FOLLOW_UP_AFTER_DAYS[n], f'FOLLOW_UP_AFTER_DAYS[{n}]')
        return (f'if no reply, send follow-up {n + 1} from the outreach file, then record '
                'followed_up'), date, why
    if stage == 'followed_up':
        date, why = plus(NO_RESPONSE_AFTER_DAYS, 'NO_RESPONSE_AFTER_DAYS')
        return 'if no reply, record no_response, then approach again next campaign', date, why
    if stage == 'replied':
        date, why = plus(REPLY_WITHIN_DAYS, 'REPLY_WITHIN_DAYS')
        return 'answer the reply with creator-outreach (paste their message)', date, why
    if stage == 'negotiating':
        date, why = plus(NEGOTIATION_CHECK_DAYS, 'NEGOTIATION_CHECK_DAYS')
        return ('settle terms or record declined, and a flat or hybrid deal needs the approval in '
                'programme section 4'), date, why
    if stage == 'agreed':
        return 'run partnership-agreement for the agreed terms', day.isoformat(), 'the same day'
    due_date, due_why = (due, 'the due date given with --due') if due else ('', 'no date: no --due given')
    if stage == 'briefed':
        return ('agree the content due date with the creator, then record content_due with --due',
                day.isoformat(), 'the same day')
    if stage == 'content_due' and current == 'content_submitted':
        return ("send content-approval's feedback to the creator, then record content_submitted "
                'when the revision arrives'), due_date, due_why
    if stage == 'content_due':
        return ('when the creator submits, record content_submitted, then run content-approval',
                due_date, due_why)
    if stage == 'content_submitted':
        return 'run content-approval on the submission', day.isoformat(), 'the same day'
    if stage == 'approved':
        return ('the creator posts the approved version; publication-tracking records the live '
                'post'), due_date, due_why
    if stage == 'declined':
        return 'none for this campaign', '', 'no date'
    return 'none this campaign, approach again next campaign', '', 'no date'


def check_approval(ws, slug, ref, approval_id, stage):
    """The approval_id behind approved or a return to content_due, after checking its record."""
    if not approval_id:
        fail(f'{stage} here follows content-approval; give --approval-id, the record '
             f'campaigns/{slug}/approvals/<approval_id>.md it wrote.')
    if not re.match(rf'^{re.escape(slug)}--{re.escape(ref)}--[1-9][0-9]*$', approval_id):
        fail(f"--approval-id '{approval_id}' is not {slug}--{ref}--<n> (schemas.md section 2).")
    path = os.path.join(ws, 'campaigns', slug, 'approvals', approval_id + '.md')
    if not os.path.isfile(path):
        fail(f'campaigns/{slug}/approvals/{approval_id}.md was not found; run content-approval first.')
    with open(path, encoding='utf-8') as fh:
        found = VERDICT_RE.search(fh.read())
    verdict = found.group(1).lower() if found else 'unreadable'
    if verdict not in APPROVAL_VERDICTS[stage]:
        fail(f"The verdict in {approval_id} is {verdict}; {stage} needs "
             f"{' or '.join(APPROVAL_VERDICTS[stage])}.")
    return approval_id


def roster_command(ws, ref, fields, note, role, day):
    """The creator-roster update line for a roster change, dated with the stage date."""
    if not os.path.isfile(ROSTER_SCRIPT):
        return (f'not run here; with creator-roster set {" ".join(fields)} for {ref}, dated {day} '
                '(its script is not installed beside this skill).')
    return (f'python3 -I {shlex.quote(ROSTER_SCRIPT)} {shlex.quote(ws)} update {ref} '
            f'{" ".join(shlex.quote(f) for f in fields)} --note {shlex.quote(note)} '
            f'--role {shlex.quote(role)} --date {day}')


def roster_fields(offer):
    """Roster compensation fields from an agreed offer_summary."""
    model = OFFER_RE.match(offer).group(1)
    rate = re.match(r'^(?:cpa|hybrid)\s+(\d+(?:\.\d+)?)\s*pct', offer)
    fee = re.search(r'\bfee\s+(\d+(?:\.\d+)?)', offer)
    fields = [f'compensation_model={model}']
    fields.append(f'commission_rate_pct={rate.group(1) if rate else ""}')
    fields.append(f'flat_fee={fee.group(1) if fee else ""}')
    return fields


def read_rows(path, header, what):
    rows = pg.read_csv(path, header, what)
    with open(path, 'rb') as fh:
        ending = '\r\n' if b'\r\n' in fh.read() else '\n'
    return rows, ending


def write_rows(path, header, rows, ending):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator=ending)
    writer.writerow(header)
    for row in rows:
        writer.writerow([row[c] for c in header])
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(buffer.getvalue())
    os.replace(tmp, path)


def cmd_set(args):
    ws = args.workspace
    today = datetime.now(timezone.utc).date()
    sections = pg.read_sections(ws)
    roles = pg.roles(sections)
    role = args.owner_role.strip().lower()
    if role not in roles:
        fail(f"Owner role '{args.owner_role}' is not in programme section 10 "
             f"(roles there: {', '.join(roles)}).")
    if not SLUG_RE.match(args.campaign):
        fail(f"Campaign slug '{args.campaign}' should be lowercase kebab starting YYYY-MM-.")
    if not os.path.isfile(os.path.join(ws, 'campaigns', args.campaign, 'plan.md')):
        fail(f'campaigns/{args.campaign}/plan.md was not found; run campaign-plan or name an '
             'existing campaign.')
    stage = args.stage
    day = iso(args.date, '--date') if args.date else today
    if day > today:
        fail(f'--date {day.isoformat()} is after today ({today.isoformat()}, UTC); record a stage '
             'only once it has happened.')
    creators_path = os.path.join(ws, 'data', 'creators.csv')
    creators, creators_ending = read_rows(creators_path, pg.CREATORS_HEADER, 'data/creators.csv')
    pipeline_path = os.path.join(ws, 'data', 'pipeline.csv')
    rows, ending = read_rows(pipeline_path, pg.PIPELINE_HEADER, 'data/pipeline.csv')
    roster = {r['creator_ref']: r for r in creators}

    offer = (args.offer or '').strip()
    if offer and not OFFER_RE.match(offer):
        fail("--offer should start with cpa, flat, hybrid or gift; paste the offer_summary line "
             'that offer_calc.py printed.')
    approval_text = ''
    if stage == 'agreed':
        if not offer:
            fail('--offer is required at agreed: the agreed terms as an offer_summary line.')
        if OFFER_RE.match(offer).group(1) in ('flat', 'hybrid'):
            entry = pg.classify(4, sections).get('approval')
            if pg.is_missing(entry):
                fail('Programme section 4 does not say who approves a flat or hybrid deal; the '
                     'owner sets that before one is agreed.')
            if not args.approved_by or not args.approved_on:
                fail('A flat or hybrid agreement needs --approved-by ROLE and --approved-on DATE, '
                     'the approval programme section 4 requires.')
            approver = args.approved_by.strip().lower()
            if approver not in roles:
                fail(f"--approved-by '{args.approved_by}' is not a role in programme section 10.")
            if approver not in entry['value'].lower():
                fail(f"Programme section 4 does not name '{approver}' as the approver of flat or "
                     f"hybrid deals; it says: \"{entry['value']}\".")
            approved_on = iso(args.approved_on, '--approved-on')
            if approved_on > day:
                fail('--approved-on is after the date the agreement is recorded.')
            approval_text = f'{OFFER_RE.match(offer).group(1)} approved by {approver} on {approved_on}'
    if args.next_date and not args.next_action:
        fail('--next-date needs --next-action with it.')
    next_date_override = iso(args.next_date, '--next-date').isoformat() if args.next_date else None
    due = iso(args.due, '--due').isoformat() if args.due else None
    if due and stage not in ('content_due', 'approved'):
        fail('--due belongs with content_due or approved: the date the content or the post is due.')
    if args.approval_id and len(args.creator) > 1:
        fail('--approval-id names one creator; record one creator at a time.')
    message_day = iso(args.message_date, '--message-date').isoformat() if args.message_date else None

    plans, warnings, skipped = [], [], []
    for ref in args.creator:
        if not REF_RE.match(ref):
            fail(f"'{ref}' is not a creator_ref (c- and six lowercase letters or digits).")
        person = roster.get(ref)
        if person is None:
            fail(f'{ref} is not in data/creators.csv; add the creator with creator-roster first.')
        merged = MERGED_RE.search(person['notes'])
        if person['status'] == 'ended' and merged:
            fail(f'{ref} was {merged.group(0)}; record the stage for that ref instead.')
        current_row = next((r for r in rows if r['campaign_slug'] == args.campaign
                            and r['creator_ref'] == ref), None)
        current = current_row['stage'] if current_row else None
        if current in ('live', 'closed'):
            fail(f'{ref} is at {current} in {args.campaign}, which {OTHER_STAGES[current]} writes '
                 'and whose next_action it owns; this script changes neither the stage nor the '
                 'next action of that row.')
        if current == stage == 'identified':
            skipped.append(f'{ref} is already identified in {args.campaign}; nothing changed')
            continue
        if current not in ALLOWED_FROM[stage]:
            fail(f"{ref} is at {current or 'no row'} in {args.campaign}; {stage} cannot follow it "
                 f"(it may follow: {', '.join(s or 'no row' for s in sorted(ALLOWED_FROM[stage], key=str))}).")
        if current_row and day < iso(current_row['stage_date'], 'stage_date in data/pipeline.csv'):
            fail(f"--date {day.isoformat()} is before {ref}'s current stage date "
                 f"{current_row['stage_date']}.")
        approval_id = None
        if stage == 'approved' or (stage == 'content_due' and current == 'content_submitted'):
            approval_id = check_approval(ws, args.campaign, ref, args.approval_id, stage)
        if stage in ('content_due', 'approved') and not due:
            warnings.append(f'{ref}: no --due date given, so next_action_date is empty; add it '
                            'when the date is known.')
        platform = None
        if stage in ('identified', 'first_touch'):
            if person['status'] == 'excluded' or person['brand_safety_flag'] == 'exclude':
                fail(f'{ref} is excluded on the roster (status {person["status"]}, brand safety '
                     f'{person["brand_safety_flag"] or "empty"}); no outreach.')
            if DO_NOT_CONTACT in person['notes'].lower():
                fail(f"{ref}'s roster notes say '{DO_NOT_CONTACT}'; no outreach.")
            if person['brand_safety_flag'] == 'review':
                if stage == 'first_touch':
                    fail(f'{ref} has brand_safety_flag review; settle it with creator-roster before '
                         'the first touch is sent.')
                warnings.append(f'{ref} has brand_safety_flag review: settle it before sending.')
            platform = (args.platform or person['primary_platform']).strip().lower()
            if platform not in PLATFORMS:
                fail(f"Platform '{platform}' is not a roster platform value.")
            on_roster = {person['primary_platform']} | {
                p.split(':', 1)[0] for p in person['other_platforms'].split(';') if p}
            if platform not in on_roster:
                fail(f'{ref} has no {platform} account on the roster; add it with creator-roster '
                     'or choose a platform they are on.')
            row_name, rule, raw = pg.platform_rule(sections, platform)
            if rule == 'no':
                fail(f'Programme section 3 says no organic creator posts on {row_name}; the deal '
                     'cannot ask for one there. Choose another platform with --platform.')
            if rule == 'unknown':
                fail(f'Programme section 3 has no ruling on organic creator posts for '
                     f'{row_name or platform}; the owner rules on it before outreach for that platform.')
            if rule == 'with conditions':
                warnings.append(f'{ref}: section 3 allows {row_name} posts with conditions, quoted: '
                                f'"{raw}". The drafts must state them.')
        if stage == 'first_touch' and not offer and not (current_row and current_row['offer_summary']):
            fail('--offer is required at first_touch: paste the offer_summary line offer_calc.py printed.')
        n = follow_ups(current_row['notes']) if current_row else 0
        if stage == 'followed_up':
            if n >= MAX_FOLLOW_UPS:
                fail(f'{ref} already has {n} follow-ups recorded; record replied or no_response.')
            n += 1
        if stage == 'no_response' and n < MAX_FOLLOW_UPS and not args.note:
            fail(f'{ref} has {n} of {MAX_FOLLOW_UPS} follow-ups recorded; to stop early, give '
                 '--note with the reason.')
        plans.append((ref, person, current_row, current, platform, n, approval_id))

    others = {}
    for r in rows:
        if r['campaign_slug'] != args.campaign:
            others.setdefault(r['creator_ref'], []).append(r)

    read_count, added, changed = len(rows), 0, 0
    report, activity_changed = [], []
    for ref, person, current_row, current, platform, n, approval_id in plans:
        action, action_date, working = next_step(stage, day, n, args.campaign, ref, current, due)
        if args.next_action:
            action = clean_note(args.next_action)
            action_date = next_date_override or ''
            working = 'given with --next-date' if action_date else 'no date given'
        entry = f'{day.isoformat()} {stage}'
        if stage == 'followed_up':
            entry += f' {n}'
        if platform:
            entry += f' for {platform}'
        under = f'under {approval_id}' if approval_id else ''
        extras = [x for x in (approval_text, under, clean_note(args.note)) if x]
        if extras:
            entry += ': ' + ', '.join(extras)
        entry += f' ({role})'
        if current_row is None:
            current_row = {c: '' for c in pg.PIPELINE_HEADER}
            current_row.update(campaign_slug=args.campaign, creator_ref=ref)
            rows.append(current_row)
            added += 1
        else:
            changed += 1
        current_row['stage'] = stage
        current_row['stage_date'] = day.isoformat()
        current_row['next_action'] = action
        current_row['next_action_date'] = action_date
        current_row['owner_role'] = role
        if stage in ('first_touch', 'followed_up', 'replied', 'content_submitted'):
            current_row['last_message_date'] = message_day or day.isoformat()
        elif message_day:
            current_row['last_message_date'] = message_day
        if offer:
            current_row['offer_summary'] = offer
        current_row['notes'] = ';'.join(x for x in (current_row['notes'], entry) if x)

        lines = [f'{ref} ({person["display_name"]}): {current or "no row"} -> {stage} on '
                 f'{day.isoformat()}; next: {action}; next_action_date {working}.']
        for r in others.get(ref, []):
            lines.append(f'  other campaign: {r["campaign_slug"]} at {r["stage"]} since '
                         f'{r["stage_date"]}; offer {r["offer_summary"] or "not recorded"}.')
        status = STAGE_TO_STATUS.get(stage)
        if status and person['status'] in STATUS_MAY_MOVE and person['status'] != status:
            lines.append('  roster: ' + roster_command(
                ws, ref, [f'status={status}'], f'{args.campaign} {stage}', role, day.isoformat()))
        elif status and person['status'] != status:
            lines.append(f'  roster: status stays {person["status"]} (a partner already); no update.')
        if stage == 'agreed':
            lines.append('  roster, now (the deal fields partnership-agreement reads; status stays '
                         f'{person["status"]} until the terms are in writing): ' + roster_command(
                             ws, ref, roster_fields(offer),
                             f'{args.campaign} deal agreed in principle, terms not yet in writing',
                             role, day.isoformat()))
            lines.append("  roster, later, at partnership-agreement's hand-off once the terms are "
                         'agreed in writing (put that date in both places): ' + roster_command(
                             ws, ref, ['status=agreed', 'agreement_date=YYYY-MM-DD'],
                             f'{args.campaign} terms agreed in writing', role, 'YYYY-MM-DD'))
        old_activity = person['last_activity']
        if not old_activity or old_activity < day.isoformat():
            person['last_activity'] = day.isoformat()
            activity_changed.append(ref)
            lines.append(f'  roster: last_activity {old_activity or "(empty)"} -> {day.isoformat()}, '
                         'written by this script (the stage date; it only moves forward).')
        report.append('\n'.join(lines))

    if plans:
        write_rows(pipeline_path, pg.PIPELINE_HEADER, rows, ending)
    print(f'data/pipeline.csv: read {read_count} rows, added {added}, changed {changed}.')
    if activity_changed:
        write_rows(creators_path, pg.CREATORS_HEADER, creators, creators_ending)
    print(f'data/creators.csv: read {len(creators)} rows, added 0, changed {len(activity_changed)} '
          '(last_activity only; every other roster field moves through creator-roster). If the '
          'workbook is in use, run creator-roster export-xlsx afterwards.')
    for block in report:
        print(block)
    if stage == 'identified' and plans:
        sender = pg.classify(10, sections).get('sending')
        if pg.is_missing(sender):
            print('Sends from: programme section 10 names no sending account per outreach channel; '
                  'ask the person once, and the drafts sign with the role meanwhile.')
        else:
            print(f'Sends from (programme section 10, quoted): "{sender["value"]}". Label: '
                  f'{pg.label_for(sender, 10)}.')
    for w in warnings:
        print(f'WARNING: {w}')
    for s in skipped:
        print(f'SKIPPED: {s}')
    if os.path.isfile(ROSTER_SCRIPT):
        print(f'Then validate: python3 -I {shlex.quote(ROSTER_SCRIPT)} {shlex.quote(ws)} check')
    else:
        print('creator-roster is not installed beside this skill, so the roster status was not '
              'updated and the files were not validated; say so in the coverage line.')
    if skipped:
        print('Partial: ' + '; '.join(skipped) + '.')
        return 2
    return 0


def cmd_show(args):
    ws = args.workspace
    as_of = iso(args.as_of, '--as-of') if args.as_of else datetime.now(timezone.utc).date()
    rows, _ = read_rows(os.path.join(ws, 'data', 'pipeline.csv'), pg.PIPELINE_HEADER,
                        'data/pipeline.csv')
    mine = [r for r in rows if r['campaign_slug'] == args.campaign]
    print(f'# Outreach rows for {args.campaign}, as of {as_of.isoformat()}')
    print('')
    if not mine:
        print(f'No rows for {args.campaign} in data/pipeline.csv ({len(rows)} rows read).')
        return 0
    counts = {}
    for r in mine:
        counts[r['stage']] = counts.get(r['stage'], 0) + 1
    order = list(STAGE_ORDER)
    print('Counted by the script: ' + '; '.join(
        f'{s} {counts[s]}' for s in sorted(counts, key=lambda s: order.index(s) if s in order else 99))
        + f'; total {len(mine)}.')
    print('')
    print('| creator_ref | stage | stage_date | follow-ups | next_action | next_action_date | owner_role | due |')
    print('|---|---|---|---|---|---|---|---|')
    for r in sorted(mine, key=lambda r: (r['next_action_date'] or '9999', r['creator_ref'])):
        due = ''
        if r['next_action_date']:
            due = 'due' if iso(r['next_action_date'], 'next_action_date') <= as_of else ''
        print(f"| {r['creator_ref']} | {r['stage']} | {r['stage_date']} | {follow_ups(r['notes'])} | "
              f"{r['next_action']} | {r['next_action_date']} | {r['owner_role']} | {due} |")
    return 0


def main():
    parser = Parser(description='Record or show creator outreach stages in data/pipeline.csv.')
    parser.add_argument('workspace', help='the workspace folder')
    sub = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    s = sub.add_parser('set', help='record the stage a person reports')
    s.add_argument('--campaign', required=True, help='campaign_slug')
    s.add_argument('--creator', required=True, action='append', help='creator_ref (repeatable)')
    s.add_argument('--stage', required=True, choices=OUTREACH_STAGES + DELIVERY_STAGES)
    s.add_argument('--owner-role', required=True, help='the role that acts next (section 10)')
    s.add_argument('--date', help='the day the stage was reached (default today, UTC)')
    s.add_argument('--offer', help='offer_summary line from offer_calc.py')
    s.add_argument('--platform', help='the platform the deal is for (default the primary platform)')
    s.add_argument('--note', help='a short reason or detail, added to notes with the date')
    s.add_argument('--message-date', help='date of the last message either way, if not --date')
    s.add_argument('--approved-by', help='role that approved a flat or hybrid deal')
    s.add_argument('--approved-on', help='date of that approval')
    s.add_argument('--approval-id', help='the content-approval record behind approved, or behind '
                   'a return to content_due')
    s.add_argument('--due', help='for content_due or approved: the date the content or post is due')
    s.add_argument('--next-action', help='replace the computed next action')
    s.add_argument('--next-date', help='date for --next-action')
    sh = sub.add_parser('show', help="list a campaign's rows and what is due")
    sh.add_argument('--campaign', required=True)
    sh.add_argument('--as-of', help='date to judge what is due (default today, UTC)')
    args = parser.parse_args()
    try:
        return cmd_set(args) if args.command == 'set' else cmd_show(args)
    except pg.ProgrammeError as err:
        print(f'pipeline_stage: {err}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
