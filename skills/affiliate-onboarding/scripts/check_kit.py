#!/usr/bin/env python3
"""Check a drafted welcome kit against the roster and the programme file before it is sent.

    python3 -I scripts/check_kit.py WORKSPACE campaigns/<campaign_slug>/welcome/<creator_ref>.md

Passes only when: no template slot or rail label is left; the creator's own code and link
appear and no other creator's code does; the customer discount, holdback, commission,
payout schedule and the rail's attribution sentence appear exactly as the programme file,
the roster and references/rails.md give them; a section 10 role
is named as the contact; no product-claim term and no approved claim line appears (claims
belong in the brief); no dollar sign sits before a digit. It judges nothing else: the
disclosure paragraph's wording is the content reviewer's to judge.

No network. Exit 0 pass, 1 fail or bad input; every failure is printed with its line.
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "references"))
from brand_context import claim_cues

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboarding_lib as lib  # noqa: E402

# Review cues only, not legal findings; the owner may replace them in section 7.
CLAIM_TERMS = ('safe', 'safer', 'compatible', 'compatibility', 'prevent', 'prevents', 'protect', 'protects', 'treat', 'treats', 'cure', 'cures', 'organic', 'natural', 'non-toxic', 'waterproof', 'hypoallergenic', 'clinically', 'certified', 'guaranteed', 'sustainable', 'biodegradable', 'recycled')
RAIL_LABELS = ("[collabs]", "[app]", "[manual]")


def main(argv=None):
    p = lib.Parser.make(description="Check a drafted welcome kit before the programme lead sends it. No network.")
    p.add_argument("workspace")
    p.add_argument("kit", help="campaigns/<campaign_slug>/welcome/<creator_ref>.md, relative to the workspace or absolute")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    ws = Path(args.workspace)
    try:
        return run(ws, args.kit)
    except (lib.InputError, ValueError) as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1


def run(ws, kit_arg):
    kit = Path(kit_arg)
    if not kit.is_absolute():
        kit = ws / kit
    m = re.search(r"campaigns/([^/]+)/welcome/(c-[a-z0-9]{6})\.md$", kit.as_posix())
    if not m:
        raise lib.InputError(f"{kit_arg} is not at campaigns/<campaign_slug>/welcome/<creator_ref>.md; save the kit there.")
    campaign, ref = m.group(1), m.group(2)
    if not kit.exists():
        raise lib.InputError(f"No kit at {kit}.")
    text = kit.read_text(encoding="utf-8")
    lines = text.splitlines()
    prog = lib.Programme.load(ws)
    cues = claim_cues(prog.sections.get(7, []), CLAIM_TERMS)
    _, roster = lib.load_roster(ws)
    creator = lib.find_creator(roster, ref)
    if creator["status"] != "active" or not creator["code"].strip() or not creator["affiliate_link"].strip():
        raise lib.InputError(f"{ref} is not yet active with a code and a link on the roster; run scripts/record_onboarding.py after the test, then draft the kit.")

    fails, notes = [], []

    def where(pattern, flags=0):
        return [i for i, line in enumerate(lines, 1) if re.search(pattern, line, flags)]

    for i in where(r"\{\{[^}]*\}\}"):
        fails.append(f"line {i}: a template slot is still unfilled")
    for i, line in enumerate(lines, 1):
        if line.strip().lower().startswith(RAIL_LABELS):
            fails.append(f"line {i}: a rail label is left; keep only the paragraph for this creator's rail, without its label")
    for i in where(r"\$[0-9]"):
        fails.append(f"line {i}: a dollar sign before a digit; write USD and the amount")

    code, link = creator["code"].strip(), creator["affiliate_link"].strip()
    if code not in text:
        fails.append(f"the creator's code {code} does not appear")
    if link not in text:
        fails.append("the creator's link does not appear exactly as the roster holds it")
    others = {r["code"].strip().upper() for r in roster if r["creator_ref"] != ref and r["code"].strip()}
    others |= {c.upper() for c in prog.store_codes()}
    for plan_rows in lib.load_plans(ws).values():
        others |= {r["code"].strip().upper() for r in plan_rows if r["creator_ref"] != ref and r["code"].strip()}
    for i, line in enumerate(lines, 1):
        for tok in re.findall(r"\b[A-Z0-9]{4,20}\b", line):
            if tok in others:
                fails.append(f"line {i}: {tok} is another creator's code, or one of the store's own promotion codes")

    currency = prog.currency()
    dtype, dval = prog.discount()
    want = lib.render_discount(dtype, dval, currency)
    # Each value is looked for on the template line that carries it, so a figure elsewhere in
    # the kit (the commission, a Collabs fact) cannot stand in for it.
    if not any("audience gets" in line and want in line for line in lines):
        fails.append(f"the 'What your audience gets' line does not give the customer discount as '{want}' (programme section 4)")
    try:
        hb = f"{prog.holdback_days()} days"
        if not any("commissionable" in line and hb in line for line in lines):
            fails.append(f"the line on when a sale becomes commissionable does not give the holdback as '{hb}' (programme section 5)")
    except lib.InputError as e:
        fails.append(str(e))
    commission = lib.render_commission(creator, prog.commission_basis())
    if commission and commission not in text:
        fails.append(f"the commission '{commission}' (roster and programme section 4) does not appear in that form")
    schedule = prog.field("payout_schedule")
    if not schedule:
        fails.append("programme section 6 has no payout schedule and minimum payout; the kit cannot be finished until the owner sets them")
    elif lib.norm(schedule.replace("`", "")) not in lib.norm(text):
        fails.append("the payout schedule and minimum payout are not copied word for word from programme section 6")
    try:
        attribution = prog.attribution_line(creator["rail"], prog.app_name())
        if lib.norm(attribution) not in lib.norm(text):
            fails.append(f"the attribution sentence is not the one for the {creator['rail']} rail, word for word (programme section 5 and references/rails.md section 1): '{attribution}'")
    except lib.InputError as e:
        fails.append(str(e))
    roles = prog.roles()
    if not any(re.search(r"\b" + re.escape(r) + r"\b", text, re.I) for r in roles):
        fails.append("no role from programme section 10 is named as the contact")
    if creator["rail"] == "collabs" and "Collabs" not in text:
        fails.append("the creator is on Collabs but the kit's payout paragraph does not say so")
    if creator["rail"] != "collabs" and "Collabs" in text:
        fails.append(f"the creator is on the {creator['rail']} rail but the kit mentions Collabs")

    for i, line in enumerate(lines, 1):
        low = line.lower()
        for term in cues:
            if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low):
                fails.append(f"line {i}: '{term}' reads as a product claim; claims belong in the brief, from programme section 7")
                break
    for claim in prog.approved_claims():
        if len(claim) > 8 and lib.norm(claim).lower() in lib.norm(text).lower():
            fails.append(f"an approved claim is quoted ('{claim[:40]}'); claims belong in the brief, not the kit")

    brief = ws / "campaigns" / campaign / "briefs" / f"{ref}.md"
    if not brief.exists():
        notes.append(f"campaigns/{campaign}/briefs/{ref}.md does not exist yet: the kit points to a brief that creator-brief has not written")

    print(f"Checked {kit.relative_to(ws) if kit.is_relative_to(ws) else kit} ({len(lines)} lines) for {ref} on the {creator['rail']} rail.")
    for f in fails:
        print(f"  FAIL {f}")
    for n in notes:
        print(f"  NOTE {n}")
    print("Not judged: the disclosure paragraph's wording and placement (content-approval and the content reviewer judge those), and anything the creator is told outside this file.")
    if fails:
        print(f"Result: FAIL, {len(fails)} problem(s). Fix the kit and run this again before it is sent.")
        return 1
    print("Result: PASS" + (" with notes" if notes else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
