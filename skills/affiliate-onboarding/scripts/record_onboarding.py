#!/usr/bin/env python3
"""Record a creator's tested code and link, on any rail, and mark the creator active.

Run after the code exists on the rail and a person has tried it at checkout:

    python3 -I scripts/record_onboarding.py WORKSPACE --creator c-7k2m9q --code SAMPLE15 \
        --link https://... --tested checkout --discount-seen "15 percent" \
        --checked-by "programme lead" [--combines no] [--campaign 2026-11-launch]

On the manual rail the link is built from programme section 5 (omit --link); on the app rail
--link built does the same where the app lets the brand set the address; on Collabs the link
is the one Collabs gives.

Writes data/creators.csv (code, affiliate_link, rail, status active, last_activity, notes),
data/pipeline.csv (agreed to onboarded, when that row exists) and the code plan under codes/.
No network. Exit 0 done, 1 bad input (one sentence says what to fix).
"""
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboarding_lib as lib  # noqa: E402


def parse_args(argv):
    p = lib.Parser.make(description="Record a creator's tested code and link and mark the creator active. No network.")
    p.add_argument("workspace")
    p.add_argument("--creator", help="creator_ref, c- and six characters")
    p.add_argument("--code", help="the code as the rail or the plan holds it")
    p.add_argument("--link", help="the rail's link (collabs, app), or 'built' for the section 5 link (app); omit on manual")
    p.add_argument("--tested", help="'checkout' (code entered, stopped before paying) or 'order:<order name>' as the orders export's Name column shows it, for example order:#1043 (a bare number gets its #)")
    p.add_argument("--tested-on", help="the date the test ran, YYYY-MM-DD (default the --date of this record); it dates the 'test order' note")
    p.add_argument("--discount-seen", help="the discount checkout showed, for example '15 percent' or 'USD 10'")
    p.add_argument("--checked-by", help="the role that ran the test, from programme section 10")
    p.add_argument("--combines", choices=("yes", "no", "not-tested"), default="not-tested",
                   help="did the code combine with another active discount at checkout")
    p.add_argument("--minted-by", choices=("api", "admin_ui"), help="manual rail: how the planned code was created")
    p.add_argument("--minted-at", help="manual rail: when it was created, YYYY-MM-DDTHH:MMZ, if known")
    p.add_argument("--campaign", help="campaign_slug, when the pipeline has none or more than one")
    p.add_argument("--date", help="today's date for the records, YYYY-MM-DD (default today, UTC)")
    return p.parse_args(argv)


def need(value, flag, why):
    if not value:
        raise lib.InputError(f"{flag} is missing; {why}")
    return value


def seen_discount(text, currency):
    t = text.strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|pct\b)?", t, re.I)
    if not m:
        raise lib.InputError(f"--discount-seen '{text}' has no number in it; write what checkout showed, for example '15 percent'.")
    pct = re.search(r"%|percent|pct", t, re.I)
    return ("percentage" if pct else "fixed_amount"), Decimal(m.group(1))


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    ws = Path(args.workspace)
    if not ws.is_dir():
        print(f"Stopped: the workspace {ws} is not a folder.", file=sys.stderr)
        return 1
    try:
        return run(args, ws)
    except lib.InputError as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1


def run(args, ws):
    date = lib.today(args.date)
    prog = lib.Programme.load(ws)
    rail = prog.rail()
    ref = need(args.creator, "--creator", "name the creator by creator_ref.")
    code = need(args.code, "--code", "give the code exactly as the rail or the plan holds it.").strip()
    lib.check_code_shape(code)
    tested = need(args.tested, "--tested", "the code is tried at checkout before the creator hears about it (assets/test-order-check.md); record 'checkout' or 'order:<order name>'.")
    if tested != "checkout" and not re.match(r"^order:\S+$", tested):
        raise lib.InputError(f"--tested '{tested}' must be 'checkout' or 'order:<order name>', with no spaces in the name.")
    tested_on = args.tested_on or date
    if not lib.DATE_RE.match(tested_on) or tested_on > date:
        raise lib.InputError(f"--tested-on '{tested_on}' must be a date, YYYY-MM-DD, no later than {date}.")
    test_order = None
    if tested.startswith("order:"):
        test_order = tested[6:]
        if test_order.isdigit():
            test_order = "#" + test_order   # the orders export's Name column carries the #
    seen = need(args.discount_seen, "--discount-seen", "write the discount checkout showed, so it can be checked against programme section 4.")
    role = need(args.checked_by, "--checked-by", "name the role that ran the test (programme section 10); roles, never names.").strip().lower()
    roles = prog.roles()
    if role not in roles:
        raise lib.InputError(f"--checked-by '{args.checked_by}' is not a role in programme section 10 ({', '.join(roles) or 'none listed'}); roles, never names.")

    dtype, dval = prog.discount()
    stype, sval = seen_discount(seen, prog.currency())
    if (stype, sval) != (dtype, Decimal(dval)):
        raise lib.InputError(f"Checkout showed {seen} but programme section 4 sets {lib.render_discount(dtype, dval, prog.currency())}; fix the discount on the rail (or the programme file, with the owner) and test again.")

    combine_rule, combine_text = prog.combining()
    if combine_rule == "no" and args.combines == "yes":
        raise lib.InputError(f"The code combined with another discount at checkout, but programme section 4 says '{combine_text}'; set the discount's Combinations to match and test again.")

    roster_path, roster = lib.load_roster(ws)
    creator = lib.find_creator(roster, ref)
    if creator["status"] != "agreed":
        raise lib.InputError(f"{ref} is at status '{creator['status']}' on the roster; onboarding starts at 'agreed' (creator-outreach and partnership-agreement come first).")
    if creator["code"].strip():
        raise lib.InputError(f"{ref} already has the code {creator['code']} on the roster; one active code per creator unless the programme says otherwise.")
    if not creator["agreement_date"].strip():
        raise lib.InputError(f"{ref} has no agreement_date on the roster; terms are agreed in writing before a code goes live (partnership-agreement, then creator-roster).")
    try:
        prog.platform_ok(creator)
    except lib.SkipCreator as e:
        raise lib.InputError(str(e))

    plans = lib.load_plans(ws)
    used = lib.codes_in_use(roster, plans, prog.store_codes())
    hit = lib.collision_with(code, ref, used)
    if hit:
        where, other, status = hit
        raise lib.InputError(f"{code} is already used by {other} ({status}) in {where}; the programme cannot give one code to two creators, so settle which code this creator gets.")

    pp, pipeline = lib.load_pipeline(ws)
    campaign = args.campaign
    if not campaign:
        campaign, _ = lib.campaign_for(ref, pipeline)

    # The link.
    if rail == "manual" or (rail == "app" and args.link == "built"):
        if args.link not in (None, "built"):
            raise lib.InputError("On the manual rail the link is built from programme section 5, so leave out --link.")
        try:
            link = lib.build_link(prog.link_scheme(), creator, code, campaign)
        except lib.SkipCreator as e:
            raise lib.InputError(f"The section 5 link cannot be built for {ref}: {e}.")
    else:
        link = need(args.link, "--link", f"on the {rail} rail the link is the one the rail gives; copy it from there.")
        if link == "built":
            raise lib.InputError("On Collabs the link must be the one Collabs gives; a brand-built link would not credit the creator there.")
        if not link.startswith("https://"):
            raise lib.InputError(f"--link '{link}' is not an https:// address.")

    # The code plan row.
    plan_changed, plan_added, plan_file = 0, 0, None
    if rail == "manual":
        mine = [(p, r) for p, rows in plans.items() for r in rows
                if r["creator_ref"] == ref and r["code"].upper() == code.upper()]
        usable = [(p, r) for p, r in mine if r["status"] in ("planned", "minted")]
        if not usable:
            raise lib.InputError(f"No planned or minted {code} for {ref} under codes/; plan it with scripts/mint_codes.py first, or check the code.")
        plan_file, row = usable[0]
        if row["status"] == "planned":
            if not args.minted_by:
                raise lib.InputError(f"{code} is still 'planned' in codes/{plan_file.name}; say how it was created with --minted-by admin_ui (or api).")
            row["minted_by"] = args.minted_by
            row["minted_at"] = args.minted_at or ""
        row["status"] = "active"
        row["notes"] = lib.append_note(row["notes"], f"{date} tested ({tested}) by {role}, active")
        if test_order:
            row["notes"] = lib.append_note(row["notes"], f"{tested_on} test order {test_order}")
        lib.write_csv(plan_file, lib.PLAN_HEADER, plans[plan_file])
        plan_changed = 1
    else:
        plan_file = ws / "codes" / f"code-plan-{date}.csv"
        rows = plans.get(plan_file, [])
        rows.append({
            "creator_ref": ref, "code": code, "discount_type": dtype,
            "discount_value": lib.fmt_number(dval) if dtype == "percentage" else str(dval),
            "applies_to": "", "starts_at": "", "ends_at": "", "usage_limit": "", "once_per_customer": "",
            "status": "active", "minted_at": "", "minted_by": rail,
            "notes": f"{date} code made by the {rail} rail, discount as checkout showed it, window and limits as set on the rail, tested ({tested}) by {role}"
                     + (f";{tested_on} test order {test_order}" if test_order else ""),
        })
        lib.write_csv(plan_file, lib.PLAN_HEADER, rows)
        plan_added = 1

    # The roster row.
    creator["code"], creator["affiliate_link"], creator["rail"] = code, link, rail
    creator["status"], creator["last_activity"] = "active", date
    note = f"{date} onboarded on the {rail} rail with {code}, tested ({tested}) by {role}, combines with other discounts: {args.combines}"
    if campaign and not creator["first_campaign"].strip():
        creator["first_campaign"] = campaign
    creator["notes"] = lib.append_note(creator["notes"], note)
    if test_order:
        # The fixed entry schemas.md section 4 names, dated like every notes entry:
        # 'YYYY-MM-DD test order <Name>', with the test date. commission-statement and
        # performance-report match the phrase after the date and exclude the order.
        creator["notes"] = lib.append_note(creator["notes"], f"{tested_on} test order {test_order}")
    lib.write_csv(roster_path, lib.ROSTER_HEADER, roster)

    # The pipeline row.
    pipe_msg = "no data/pipeline.csv; nothing changed there"
    if pipeline is not None:
        targets = [r for r in pipeline if r["creator_ref"] == ref and r["stage"] == "agreed"
                   and (campaign is None or r["campaign_slug"] == campaign)]
        if len(targets) == 1:
            r = targets[0]
            r.update({"stage": "onboarded", "stage_date": date,
                      "next_action": "send the welcome kit and the brief to the creator", "next_action_date": date})
            role_note = ""
            if "programme lead" in roles:
                r["owner_role"] = "programme lead"
            else:
                role_note = f"; owner_role kept as '{r['owner_role']}' because programme section 10 has no 'programme lead' role"
            r["notes"] = lib.append_note(r["notes"], f"{date} onboarded with {code}")
            lib.write_csv(pp, lib.PIPELINE_HEADER, pipeline)
            pipe_msg = f"data/pipeline.csv: {len(pipeline)} rows read, 0 added, 1 changed ({r['campaign_slug']} to onboarded{role_note})"
        else:
            pipe_msg = (f"data/pipeline.csv: {len(pipeline)} rows read, 0 changed; "
                        + ("no row at stage agreed for this creator" if not targets else "several rows at stage agreed; give --campaign"))

    print(f"data/creators.csv: {len(roster)} rows read, 0 added, 1 changed ({ref} to active, code {code}, rail {rail}).")
    print(pipe_msg + ".")
    print(f"codes/{plan_file.name}: {plan_added} added, {plan_changed} changed.")
    print("Kit values (copy exactly into the welcome kit; scripts/check_kit.py checks them):")
    print(f"  code: {code}")
    print(f"  link: {link}")
    print(f"  customer discount: {lib.render_discount(dtype, dval, prog.currency())}")
    commission = lib.render_commission(creator, prog.commission_basis())
    print(f"  commission: {commission or 'none on sales (compensation_model ' + creator['compensation_model'] + ')'}")
    try:
        print(f"  holdback: {prog.holdback_days()} days")
    except lib.InputError as e:
        print(f"  holdback: missing ({e})")
    print(f"  payout schedule: {prog.field('payout_schedule') or 'missing: programme section 6 has no payout schedule; the kit waits for it'}")
    print(f"  combines with other discounts: {args.combines} at the test; programme section 4: {combine_text or 'no ruling yet'}")
    try:
        print(f"  attribution: {prog.attribution_line(rail, prog.app_name())}")
    except lib.InputError as e:
        print(f"  attribution: missing ({e})")
    if test_order:
        print(f"  test order: {test_order} (roster note '{tested_on} test order {test_order}'; commission-statement and performance-report exclude it)")
    print("Run creator-roster export-xlsx so the workbook shows this change.")
    print("Coverage. Inputs used: program/program.md sections 3, 4, 5, 6 and 10; data/creators.csv; "
          + ("data/pipeline.csv; " if pipeline is not None else "") + f"{len(plans)} code plan(s); the test result from the command line (User-provided).")
    print("Not judged by this script: whether the rail will credit and pay the creator as it says (references/rails.md); codes in the store outside this workspace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
