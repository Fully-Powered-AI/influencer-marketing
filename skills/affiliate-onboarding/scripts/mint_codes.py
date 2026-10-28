#!/usr/bin/env python3
"""Plan each agreed creator's discount code on the manual rail, and optionally create them.

Without --live this script reads the workspace, writes the code plan and one Admin API
request body per code, and does nothing else: no network, no store change.

    python3 -I scripts/mint_codes.py WORKSPACE --starts 2026-11-01 --ends 2026-12-31 \
        --once-per-customer yes --usage-limit none

With --live it reads a plan already written, prints exactly what it would create, and stops.
With --live --yes, run by a person from their own terminal, it asks them to type the store
domain and the number of codes, then calls the Shopify Admin GraphQL API once per code with
the token in the environment variable SHOPIFY_ADMIN_TOKEN, and records each answer in the plan.

    SHOPIFY_ADMIN_TOKEN=... python3 -I scripts/mint_codes.py WORKSPACE --live --yes

Exit 0: everything asked for was done. 1: bad input (one sentence says what to fix).
2: partial: something was skipped, collided or failed, and the output says what.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboarding_lib as lib  # noqa: E402

TOKEN_ENV = "SHOPIFY_ADMIN_TOKEN"

# Admin GraphQL API facts, from the pack's references/shopify-affiliate-rails.md sections 4
# to 4.3 (sources read 2026-10-20), summarised in this skill's references/rails.md section 4.
API_VERSION = "2026-10"                    # "Latest stable", released 2026-10-01
API_VERSION_UNTIL = "2027-10-16T15:00Z"    # accessible until then, per Shopify's versioning page
REQUIRED_SCOPE = "write_discounts"
MUTATION = (
    "mutation CreateCreatorCode($input: DiscountCodeBasicInput!) {\n"
    "  discountCodeBasicCreate(basicCodeDiscount: $input) {\n"
    "    codeDiscountNode {\n"
    "      id\n"
    "      codeDiscount {\n"
    "        ... on DiscountCodeBasic {\n"
    "          title\n"
    "          codes(first: 10) { nodes { code } }\n"
    "          startsAt\n"
    "          endsAt\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "    userErrors { field message code }\n"
    "  }\n"
    "}\n"
)
# Endpoint on the store's .myshopify.com address and the access-token header: shopify
# reference section 4.1. The reference's own advice stands: try the first live run on a
# development store.
ENDPOINT = "https://{store}/admin/api/{version}/graphql.json"
TOKEN_HEADER = "X-Shopify-Access-Token"
# A code that already exists: shopify reference section 4.3. Shopify documents the error
# codes but not which one a duplicate returns, so a row becomes `collision` on either a
# matching code or matching words; any other userError leaves it `planned` with the message.
TAKEN_CODES = ("TAKEN", "DUPLICATE")
TAKEN_WORDS = ("taken", "already", "unique")


def parse_args(argv):
    p = lib.Parser.make(
        description="Plan creator discount codes on the manual rail (no network), or create a written plan in the store with --live.",
        epilog=f"The live branch reads the Admin API token from the environment variable {TOKEN_ENV}, never from a file or an argument; it needs the {REQUIRED_SCOPE} scope.")
    p.add_argument("workspace", help="the client's workspace folder")
    p.add_argument("--starts", help="first day the codes work, YYYY-MM-DD or YYYY-MM-DDTHH:MMZ (UTC)")
    p.add_argument("--ends", help="last day the codes work, YYYY-MM-DD or YYYY-MM-DDTHH:MMZ (UTC), or 'none'; "
                   "when left out, programme section 4's 'Codes after a campaign window' line decides")
    p.add_argument("--once-per-customer", choices=("yes", "no"), help="may a customer use a creator's code only once")
    p.add_argument("--usage-limit", help="total uses allowed per code, a whole number, or 'none'")
    p.add_argument("--code", action="append", default=[], metavar="c-xxxxxx=CODE",
                   help="set one creator's code by hand instead of the scheme (repeatable)")
    p.add_argument("--creator", action="append", default=[], metavar="c-xxxxxx",
                   help="plan only these creators (repeatable); default every agreed creator without a code")
    p.add_argument("--date", help="the plan date for the file name, YYYY-MM-DD (default today, UTC)")
    p.add_argument("--live", action="store_true", help="read a written plan and create its planned codes in the store")
    p.add_argument("--plan", help="with --live: the plan file (default codes/code-plan-<date>.csv)")
    p.add_argument("--yes", action="store_true", help="with --live: go ahead after the typed confirmation")
    return p.parse_args(argv)


def utc_time(value, end):
    """'2026-11-01' -> ('2026-11-01T00:00Z', '2026-11-01T00:00:00Z'); an end date runs to 23:59."""
    if lib.DATE_RE.match(value):
        hm = "23:59" if end else "00:00"
        sec = "59" if end else "00"
        return f"{value}T{hm}Z", f"{value}T{hm}:{sec}Z"
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$", value):
        return value, value[:-1] + ":00Z"
    raise lib.InputError(f"'{value}' is not a date (YYYY-MM-DD) or a UTC time (YYYY-MM-DDTHH:MMZ).")


def payload(row, starts_api, ends_api, combines):
    """The full request body for one code: the mutation and its variables (shopify reference 4 to 4.2)."""
    if row["discount_type"] == "percentage":
        value = {"percentage": float(round(lib.Decimal(row["discount_value"]) / 100, 4))}
    else:
        # 4.2: discountAmount with amount and appliesOnEachItem; false splits the amount across
        # the order's items, which is "off their order" as the kit says.
        value = {"discountAmount": {"amount": row["discount_value"], "appliesOnEachItem": False}}
    inp = {
        "title": f"Creator code {row['creator_ref']} {row['code']}",
        "code": row["code"],
        "startsAt": starts_api,
    }
    if ends_api:
        inp["endsAt"] = ends_api
    inp["context"] = {"all": "ALL"}
    inp["customerGets"] = {"value": value, "items": {"all": True}}
    if combines is not None:
        inp["combinesWith"] = dict(combines)
    inp["appliesOncePerCustomer"] = row["once_per_customer"] == "yes"
    if row["usage_limit"]:
        inp["usageLimit"] = int(row["usage_limit"])
    return {"query": MUTATION, "variables": {"input": inp}}


def payload_path(ws, plan_date, row):
    return ws / "codes" / f"payloads-{plan_date}" / f"{row['creator_ref']}-{row['code']}.json"


def coverage(used, missing, not_judged):
    print("Coverage. Inputs used: " + "; ".join(used) + ".")
    print("Inputs missing: " + ("; ".join(missing) if missing else "none") + ".")
    print("Not judged by this script: " + "; ".join(not_judged) + ".")


def plan(args, ws, prog):
    rail = prog.rail()
    if rail != "manual":
        raise lib.InputError(f"Programme section 6 names the rail '{rail}'; that rail makes each creator's code itself, so record the code it gives with scripts/record_onboarding.py instead.")
    scheme = prog.code_scheme()
    dtype, dval = prog.discount()
    try:
        link_tpl = prog.link_scheme()
        link_note = ""
    except lib.InputError as e:
        link_tpl, link_note = None, str(e)
    for flag, val in (("--starts", args.starts),
                      ("--once-per-customer", args.once_per_customer), ("--usage-limit", args.usage_limit)):
        if val is None:
            raise lib.InputError(f"{flag} is missing; the window and the limits are the programme lead's to give, once, for this batch of codes.")
    after = prog.after_window()
    ends_arg, ends_note = args.ends, ""
    if after == "stay":
        if ends_arg not in (None, "none"):
            raise lib.InputError(f"Programme section 4 says codes stay active after a campaign window, but --ends {ends_arg} gives an end date; leave --ends out, or the owner changes section 4 first.")
        ends_arg, ends_note = "none", "no end date: programme section 4, codes stay active after the window"
    elif after == "end":
        if ends_arg in (None, "none"):
            raise lib.InputError("Programme section 4 says codes end with the campaign window; give --ends with the window's last day (campaigns/<campaign_slug>/plan.md).")
        ends_note = "end date is the campaign window's last day: programme section 4, given by the programme lead"
    elif ends_arg is None:
        raise lib.InputError("--ends is missing, and programme section 4 has no ruling on codes after a campaign window; give --ends DATE or --ends none (User-provided), or settle the line through program-setup.")
    elif ends_arg == "none":
        ends_note = "no end date (User-provided)"
    starts_csv, starts_api = utc_time(args.starts, end=False)
    ends_csv, ends_api = ("", None) if ends_arg == "none" else utc_time(ends_arg, end=True)
    combines, combine_text = prog.combines_with()
    if ends_api and ends_csv < starts_csv:
        raise lib.InputError(f"--ends {args.ends} is before --starts {args.starts}.")
    if args.usage_limit == "none":
        usage = ""
    elif args.usage_limit.isdigit() and int(args.usage_limit) > 0:
        usage = args.usage_limit
    else:
        raise lib.InputError(f"--usage-limit must be a whole number above 0 or 'none'; got '{args.usage_limit}'.")
    overrides = {}
    for item in args.code:
        ref, _, code = item.partition("=")
        lib.check_code_shape(code)
        overrides[ref] = code
    plan_date = lib.today(args.date)

    roster_path, roster = lib.load_roster(ws)
    _, pipeline = lib.load_pipeline(ws)
    plans = lib.load_plans(ws)
    used = lib.codes_in_use(roster, plans, prog.store_codes())
    out_path = ws / "codes" / f"code-plan-{plan_date}.csv"
    existing = plans.get(out_path, [])

    candidates = [r for r in roster if r["status"] == "agreed" and not r["code"].strip()]
    if args.creator:
        unknown = [c for c in args.creator if c not in {r["creator_ref"] for r in roster}]
        if unknown:
            raise lib.InputError(f"--creator {unknown[0]} is not in data/creators.csv.")
        for r in roster:
            if r["creator_ref"] in args.creator and r not in candidates:
                print(f"  Not a candidate: {r['creator_ref']} is at status {r['status']}" + (f" with code {r['code']}" if r["code"].strip() else "") + "; only agreed creators without a code are planned.")
        candidates = [r for r in candidates if r["creator_ref"] in args.creator]
    for ref in overrides:
        if ref not in {r["creator_ref"] for r in candidates}:
            raise lib.InputError(f"--code {ref}=... names a creator who is not an agreed creator without a code.")

    new_rows, skipped, collided, already, payloads = [], [], [], [], []
    run_codes = {}
    for c in candidates:
        ref = c["creator_ref"]
        prior = [(p, r) for p, rows in plans.items() for r in rows if r["creator_ref"] == ref]
        live_prior = [(p, r) for p, r in prior if r["status"] in ("planned", "minted", "active")]
        if live_prior:
            p, r = live_prior[0]
            already.append(f"{ref} already has {r['code']} ({r['status']}) in codes/{p.name}")
            continue
        try:
            if not c["agreement_date"].strip():
                raise lib.SkipCreator("the roster has no agreement_date: terms are agreed in writing before a code exists (partnership-agreement, then creator-roster)")
            ruling = prog.platform_ok(c)
            code = overrides.get(ref) or lib.build_code(scheme, c, dtype, dval)
        except lib.SkipCreator as e:
            skipped.append(f"{ref}: {e}")
            continue
        if any(r["status"] == "collision" and r["code"].upper() == code.upper() for _, r in prior):
            skipped.append(f"{ref}: {code} is already recorded as a collision; set a different code with --code {ref}=CODE")
            continue
        notes = []
        if ref in overrides:
            notes.append("code set by hand with --code, not by the scheme (User-provided)")
        notes.append("start and limits User-provided")
        if not usage:
            notes.append("no total use limit (User-provided)")
        if ends_note:
            notes.append(ends_note)
        if combines is not None:
            notes.append("combinesWith from programme section 4 (" + combine_text.replace(";", ",") + "): "
                         + ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in combines.items()) + ", checked on the test order")
        elif combine_text:
            notes.append(f"combinesWith not sent: programme section 4 ({combine_text.replace(';', ',')}) does not settle Shopify's order, product and shipping classes, so set Combinations in the admin and check it on the test order")
        else:
            notes.append("combinesWith not sent: programme section 4 has no combining ruling, so Shopify's default (combines with nothing) applies until the owner rules")
        if ruling == "conditions":
            notes.append(f"platform {c['primary_platform']} allowed with conditions, programme section 3")
        if link_tpl:
            campaign, why = lib.campaign_for(ref, pipeline)
            try:
                notes.append("link " + lib.build_link(link_tpl, c, code, campaign))
            except lib.SkipCreator as e:
                notes.append(f"link not built yet ({e}{', ' + why if why else ''})")
        row = {
            "creator_ref": ref, "code": code, "discount_type": dtype,
            "discount_value": lib.fmt_number(dval) if dtype == "percentage" else str(dval),
            "applies_to": "all", "starts_at": starts_csv, "ends_at": ends_csv, "usage_limit": usage,
            "once_per_customer": args.once_per_customer, "status": "planned",
            "minted_at": "", "minted_by": "", "notes": "",
        }
        hit = lib.collision_with(code, ref, used)
        if hit is None and code.upper() in run_codes:
            hit = ("this run", run_codes[code.upper()], "planned")
        if hit:
            where, other, status = hit
            row["status"] = "collision"
            notes.append(f"collides with {other} ({status}) in {where}")
            collided.append(f"{ref}: {code} is already used by {other} ({status}) in {where}; set a different code with --code {ref}=CODE")
        else:
            payloads.append((row, payload(row, starts_api, ends_api, combines)))
        run_codes[code.upper()] = ref
        # One dated entry (schemas: every notes entry starts with its date); parts joined by commas.
        row["notes"] = f"{plan_date} planned by affiliate-onboarding: " + ", ".join(n.replace(";", ",") for n in notes)
        new_rows.append(row)

    if new_rows:
        lib.write_csv(out_path, lib.PLAN_HEADER, existing + new_rows)
        for row, body in payloads:
            pp = payload_path(ws, plan_date, row)
            pp.parent.mkdir(parents=True, exist_ok=True)
            pp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    print(f"Read {len(roster)} roster row(s) ({len(candidates)} agreed without a code) and {sum(len(r) for r in plans.values())} row(s) in {len(plans)} code plan(s).")
    print(f"Wrote codes/{out_path.name}: {len(existing)} rows kept, {len(new_rows)} added, 0 changed." if new_rows
          else "Wrote nothing: no row to add.")
    planned = [r for r in new_rows if r["status"] == "planned"]
    for r in planned:
        print(f"  planned {r['creator_ref']} {r['code']} {r['discount_type']} {r['discount_value']} from {r['starts_at']} to {r['ends_at'] or 'no end'}")
    if payloads:
        print(f"Wrote {len(payloads)} request bodies under codes/payloads-{plan_date}/. Nothing was sent; no store was touched.")
    for label, items in (("Collision", collided), ("Skipped", skipped), ("Not planned again", already)):
        for i in items:
            print(f"  {label}: {i}")
    if not candidates:
        print("Looked at the roster and found no creator at status agreed without a code; nothing to plan.")
    if link_note:
        print(f"  Links not built: {link_note}")
    partial = bool(collided or skipped)
    if partial:
        print("PARTIAL: some creators have no code to mint yet; the lines above say why and what unblocks each.")
    coverage(
        ["program/program.md sections 3, 4, 5 and 6", "data/creators.csv",
         "data/pipeline.csv" if pipeline is not None else "no data/pipeline.csv",
         f"{len(plans)} code plan(s) under codes/", "window and limits from the command line (User-provided)"],
        [] if pipeline is not None else ["data/pipeline.csv (links needing {campaign} are not built)"],
        ["codes that exist in the store but not in this workspace (the live call or the admin refuses those)",
         "whether the discount suits the margin (program-setup and creator-outreach own that)"])
    return 2 if partial else 0


def live(args, ws, prog, transport, confirm, env):
    rail = prog.rail()
    if rail != "manual":
        raise lib.InputError(f"Programme section 6 names the rail '{rail}'; the live branch is for the manual rail only.")
    store = prog.store_domain()
    plan_date = lib.today(args.date)
    path = Path(args.plan) if args.plan else ws / "codes" / f"code-plan-{plan_date}.csv"
    if not path.is_absolute() and args.plan:
        path = ws / args.plan
    if not path.exists():
        raise lib.InputError(f"No code plan at {path}; run this script without --live first, or name the plan with --plan.")
    m = re.search(r"code-plan-(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not m:
        raise lib.InputError(f"{path.name} is not named code-plan-YYYY-MM-DD.csv.")
    pdate = m.group(1)
    rows = lib.read_csv(path, lib.PLAN_HEADER, "The code plan")
    todo, missing = [], []
    for r in rows:
        if r["status"] != "planned":
            continue
        pp = payload_path(ws, pdate, r)
        if not pp.exists():
            missing.append(f"{r['creator_ref']} {r['code']}: no request body at {pp.relative_to(ws)} (the file was moved or never written; re-plan it)")
            continue
        body = json.loads(pp.read_text(encoding="utf-8"))
        if body.get("variables", {}).get("input", {}).get("code") != r["code"]:
            missing.append(f"{r['creator_ref']} {r['code']}: the request body's code differs from the plan row; re-plan it")
            continue
        todo.append((r, body))
    if lib.now_utc() > API_VERSION_UNTIL:
        raise lib.InputError(f"API version {API_VERSION} was supported until {API_VERSION_UNTIL}; update API_VERSION in scripts/mint_codes.py from a current reading of Shopify's versioning page, and the references with it.")
    print(f"Live plan for store {store}, Admin GraphQL API {API_VERSION}, scope {REQUIRED_SCOPE}, token from the environment variable {TOKEN_ENV}.")
    print(f"Endpoint (shopify reference 4.1; first live run on a development store): {ENDPOINT.format(store=store, version=API_VERSION)}")
    print(f"This would create {len(todo)} discount code(s) in the live store {store}:")
    for r, body in todo:
        inp = body["variables"]["input"]
        off = f"{r['discount_value']} percent" if r["discount_type"] == "percentage" else f"{prog.currency() or 'USD'} {r['discount_value']}"
        cw = inp.get("combinesWith")
        cw_text = ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in cw.items()) if cw else "not sent (combines with nothing)"
        print(f"  {r['code']} for {r['creator_ref']}: {off} off, from {inp['startsAt']} to {inp.get('endsAt', 'no end')}, once per customer {r['once_per_customer']}, total uses {r['usage_limit'] or 'no limit'}, combines: {cw_text}")
    for i in missing:
        print(f"  Not sendable: {i}")
    if not todo:
        print("Nothing planned to create." + (" PARTIAL: see the lines above." if missing else ""))
        return 2 if missing else 0
    if not args.yes:
        print(f"Nothing created. To create these {len(todo)} code(s), the token custodian runs this again with --live --yes from their own terminal.")
        return 0
    token = (env if env is not None else os.environ).get(TOKEN_ENV, "").strip()
    if not token:
        raise lib.InputError(f"No Admin API token in the environment variable {TOKEN_ENV}; the token custodian (programme section 6) sets it in their own terminal, or creates the codes in the Shopify admin from the plan instead.")
    expected = f"{store} {len(todo)}"
    if confirm is None:
        if not sys.stdin.isatty():
            raise lib.InputError("The live branch runs only from a person's own terminal, where they type the confirmation; it will not run from an agent or a pipe.")
        typed = input(f"Type the store domain and the number of codes to create them ({expected}): ")
    else:
        typed = confirm(expected)
    if lib.norm(typed or "") != expected:
        raise lib.InputError(f"The confirmation '{typed}' does not match '{expected}'; nothing was created.")
    send = transport or http_transport
    done, collided, failed, stopped = 0, 0, [], None
    for r, body in todo:
        try:
            status, resp = send(store, API_VERSION, token, body)
        except TransportLost as e:
            r["notes"] = lib.append_note(r["notes"], f"{lib.today(args.date)} outcome unknown: request sent, no answer ({e}), check the admin for {r['code']} before re-running")
            stopped = f"no answer from the store for {r['code']} ({e})"
            lib.write_csv(path, lib.PLAN_HEADER, rows)
            break
        result = read_answer(status, resp)
        stamp = lib.today(args.date)
        if result[0] == "minted":
            r["status"], r["minted_at"], r["minted_by"] = "minted", lib.now_utc(), "api"
            r["notes"] = lib.append_note(r["notes"], f"{stamp} created through the Admin API, node {result[1]}")
            done += 1
        elif result[0] == "taken":
            if "outcome unknown" in r["notes"]:
                r["notes"] = lib.append_note(r["notes"], f"{stamp} store says {r['code']} exists, probably from the earlier unanswered request, check the admin and record it with record_onboarding.py --minted-by api")
                failed.append(f"{r['code']}: exists in the store, probably ours from the earlier unanswered request")
            else:
                r["status"] = "collision"
                r["notes"] = lib.append_note(r["notes"], f"{stamp} store refused: {result[1]}")
                collided += 1
        elif result[0] == "error":
            r["notes"] = lib.append_note(r["notes"], f"{stamp} store refused: {result[1]}")
            failed.append(f"{r['code']}: {result[1]}")
        else:
            r["notes"] = lib.append_note(r["notes"], f"{stamp} not created: {result[1]}")
            stopped = result[1]
            lib.write_csv(path, lib.PLAN_HEADER, rows)
            break
        lib.write_csv(path, lib.PLAN_HEADER, rows)
    print(f"Created {done} of {len(todo)}; collisions {collided}; refused {len(failed)}.")
    for f in failed:
        print(f"  Refused: {f}")
    if stopped:
        print(f"  Stopped early: {stopped}. Rows not reached stay planned; nothing was retried.")
    print(f"Updated codes/{path.name} in place ({len(rows)} rows read, 0 added, {done + collided + len(failed) + (1 if stopped else 0)} changed).")
    partial = done < len(todo) or bool(missing)
    if partial:
        print("PARTIAL: not every planned code was created; the plan rows say why.")
    coverage([f"codes/{path.name}", f"request bodies under codes/payloads-{pdate}/", "programme section 6 store domain"],
             [], ["whether each created code works at checkout: the test order checks that (assets/test-order-check.md)"])
    return 2 if partial else 0


class TransportLost(Exception):
    """The request may have reached the store but no answer came back."""


def http_transport(store, version, token, body):
    """One POST to the Admin GraphQL API. Imported and called only in the --live --yes branch."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(
        ENDPOINT.format(store=store, version=version), data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", TOKEN_HEADER: token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {}
        return e.code, data
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TransportLost(type(e).__name__)


def read_answer(status, resp):
    """('minted', id) | ('taken', msg) | ('error', msg) | ('stop', msg)."""
    if status == 429:
        return "stop", "the store throttled the request (HTTP 429); wait and run --live again"
    if status in (401, 403):
        return "stop", f"the store refused the token (HTTP {status}); the token custodian checks it and its {REQUIRED_SCOPE} scope"
    if status != 200:
        return "stop", f"HTTP {status} from the store"
    if resp.get("errors"):
        text = json.dumps(resp["errors"])[:300]
        return "stop", ("throttled: " if "THROTTLED" in text else "API error: ") + text
    node = (((resp.get("data") or {}).get("discountCodeBasicCreate")) or {})
    errs = node.get("userErrors") or []
    if errs:
        msg = "; ".join(f"{','.join(e.get('field') or [])}: {e.get('message', '')}" + (f" ({e['code']})" if e.get("code") else "") for e in errs)
        if any((e.get("code") or "") in TAKEN_CODES for e in errs) or any(w in msg.lower() for w in TAKEN_WORDS):
            return "taken", msg
        return "error", msg
    cdn = node.get("codeDiscountNode") or {}
    if cdn.get("id"):
        return "minted", cdn["id"]
    return "stop", "an answer with neither a created discount nor an error"


def main(argv=None, transport=None, confirm=None, env=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    ws = Path(args.workspace)
    if not ws.is_dir():
        print(f"Stopped: the workspace {ws} is not a folder.", file=sys.stderr)
        return 1
    try:
        prog = lib.Programme.load(ws)
        if args.live:
            return live(args, ws, prog, transport, confirm, env)
        return plan(args, ws, prog)
    except lib.InputError as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
