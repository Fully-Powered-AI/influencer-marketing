"""Fixture cases for affiliate-onboarding's three scripts. Run through run_fixtures.sh.

Each case copies base/ to a fresh temporary workspace, applies its edits, runs its commands
and checks the exit code, the printed lines and the files written. Every case runs with no
network: the dry branches under no_network.py, the live branch through fake_live.py with
canned store answers. Exit 0 when every case passes, 1 on any miss.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
PY = [sys.executable, "-I", "-B"]
MINT = str(SCRIPTS / "mint_codes.py")
RECORD = str(SCRIPTS / "record_onboarding.py")
KIT = str(SCRIPTS / "check_kit.py")
NONET = str(HERE / "no_network.py")
FAKE = str(HERE / "fake_live.py")

PLAN_ARGS = ["--starts", "2026-11-01", "--ends", "2026-12-31", "--once-per-customer", "yes",
             "--usage-limit", "none", "--date", "2026-10-20"]
SCHEME = "`{HANDLE}{DISCOUNT}` [owner]"
RAIL_LINE = "a payout list), `none` yet: `manual` [owner]"
ROSTER_TIKTOK = ("c-fffff6,Sample Creator F,tiktok,@samplef,https://www.tiktok.example.com/@samplef,,micro,30000,2026-10-01,5.0,2026-10-02,home-decor,23,none,dm,,agreed,cpa,15,,,,,2026-10-17,agreements/c-fffff6-2026-10-17.md,,,,2026-10-17,\n"
                 "c-ggggg7,Sample Creator G,instagram,@sampleg,https://www.instagram.example.com/sampleg,,nano,9000,2026-10-01,4.2,2026-10-02,home-decor,20,none,email,,agreed,cpa,15,,,,,,,,,,2026-10-18,\n")
ROSTER_COLLIDE = "c-eeeee5,Sample Creator E,instagram,@old.code,https://www.instagram.example.com/old.code,,nano,7000,2026-10-01,3.3,2026-10-02,home-decor,18,none,dm,,agreed,cpa,15,,,,,2026-10-18,agreements/c-eeeee5-2026-10-18.md,,,,2026-10-18,\n"


def plan(*extra):
    return [NONET, MINT, "{ws}"] + PLAN_ARGS + list(extra)


def plan_no_ends(*extra):
    args = [a for a in PLAN_ARGS if a not in ("--ends", "2026-12-31")]
    return [NONET, MINT, "{ws}"] + args + list(extra)


AFTER_END = "or `stay active` [default stay active]: `end` [owner]"
AFTER_STAY = "or `stay active` [default stay active]: stay active [default]"


def record(*extra):
    return [NONET, RECORD, "{ws}", "--date", "2026-10-20", "--checked-by", "programme lead"] + list(extra)


RECORD_A = ["--creator", "c-aaaaa1", "--code", "SAMPLECREATORA15", "--tested", "checkout",
            "--discount-seen", "15 percent", "--minted-by", "admin_ui", "--combines", "no"]

CASES = [
    {"name": "plan_green", "run": plan(), "exit": 0,
     "out": ["planned c-aaaaa1 SAMPLECREATORA15", "planned c-bbbbb2 SAMPLECREATORB15", "Nothing was sent"],
     "same_file": [("codes/code-plan-2026-10-20.csv", "expected/plan_green/code-plan-2026-10-20.csv"),
                   ("codes/payloads-2026-10-20/c-aaaaa1-SAMPLECREATORA15.json", "expected/plan_green/c-aaaaa1-SAMPLECREATORA15.json")]},
    {"name": "plan_collision_must_fail", "append": [("data/creators.csv", ROSTER_COLLIDE)], "run": plan(), "exit": 2,
     "out": ["Collision: c-eeeee5: OLDCODE15 is already used by c-ddddd4", "PARTIAL"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-eeeee5", {"code": "OLDCODE15", "status": "collision"}),
               ("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned"})],
     "absent": ["codes/payloads-2026-10-20/c-eeeee5-OLDCODE15.json"]},
    {"name": "plan_blank_scheme_ignores_template_detail_must_fail", "edit": [("program/program.md", SCHEME, "")], "run": plan(), "exit": 1,
     "err": ["Programme section 5", "no code scheme"], "absent": ["codes/code-plan-2026-10-20.csv"]},
    {"name": "plan_scheme_in_words_must_fail",
     "edit": [("program/program.md", SCHEME, "the handle then the discount number [owner]")], "run": plan(), "exit": 1,
     "err": ["Programme section 5", "in words"]},
    {"name": "plan_blocked_creators", "append": [("data/creators.csv", ROSTER_TIKTOK)], "run": plan(), "exit": 2,
     "out": ["Skipped: c-fffff6: Programme section 3", "on tiktok are not allowed", "Skipped: c-ggggg7: the roster has no agreement_date"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned"})],
     "no_row": [("codes/code-plan-2026-10-20.csv", "c-fffff6"), ("codes/code-plan-2026-10-20.csv", "c-ggggg7")]},
    {"name": "plan_fixed_amount_payload",
     "edit": [("program/program.md", "fixed amount: 15 percent [owner]", "fixed amount: USD 5 [owner]")], "run": plan(), "exit": 0,
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"discount_type": "fixed_amount", "discount_value": "5.00", "status": "planned"})],
     "json": [("codes/payloads-2026-10-20/c-aaaaa1-SAMPLECREATORA5.json", ["variables", "input", "customerGets", "value", "discountAmount"],
               {"amount": "5.00", "appliesOnEachItem": False})]},
    {"name": "plan_combines_with_from_section4",
     "edit": [("program/program.md", "no: a creator's code does not combine with other codes or automatic discounts [owner]",
               "no other code or order discount; free-shipping offers yes [owner]")], "run": plan(), "exit": 0,
     "json": [("codes/payloads-2026-10-20/c-aaaaa1-SAMPLECREATORA15.json", ["variables", "input", "combinesWith"],
               {"orderDiscounts": False, "productDiscounts": False, "shippingDiscounts": True})]},
    {"name": "plan_combining_unsettled_not_sent",
     "edit": [("program/program.md", "no: a creator's code does not combine with other codes or automatic discounts [owner]",
               "with other codes but not with automatic discounts [owner]")], "run": plan(), "exit": 0,
     "json_absent": [("codes/payloads-2026-10-20/c-aaaaa1-SAMPLECREATORA15.json", ["variables", "input", "combinesWith"])],
     "contains": [("codes/code-plan-2026-10-20.csv", "combinesWith not sent: programme section 4")]},
    {"name": "plan_stay_active_without_ends", "edit": [("program/program.md", AFTER_END, AFTER_STAY)], "run": plan_no_ends(), "exit": 0,
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned", "ends_at": ""})],
     "contains": [("codes/code-plan-2026-10-20.csv", "no end date: programme section 4, codes stay active after the window")]},
    {"name": "plan_end_rule_without_ends_must_fail", "run": plan_no_ends(), "exit": 1,
     "err": ["Programme section 4 says codes end with the campaign window"], "absent": ["codes/code-plan-2026-10-20.csv"]},
    {"name": "plan_stay_active_with_ends_must_fail", "edit": [("program/program.md", AFTER_END, AFTER_STAY)], "run": plan(), "exit": 1,
     "err": ["stay active after a campaign window, but --ends 2026-12-31"]},
    {"name": "plan_store_code_collision_must_fail", "edit": [("program/program.md", "  NEWSLETTER10 [owner]", "  SAMPLECREATORA15 [owner]")],
     "run": plan(), "exit": 2, "out": ["Collision: c-aaaaa1: SAMPLECREATORA15 is already used by the store", "programme section 5 store promotion codes"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "collision"}), ("codes/code-plan-2026-10-20.csv", "c-bbbbb2", {"status": "planned"})]},
    {"name": "plan_wrong_rail_must_fail", "edit": [("program/program.md", RAIL_LINE, "a payout list), `none` yet: `collabs` [owner]")],
     "run": plan(), "exit": 1, "err": ["names the rail 'collabs'", "record_onboarding.py"]},
    {"name": "plan_rerun_does_not_duplicate", "pre": [plan()], "run": plan(), "exit": 0,
     "out": ["Not planned again: c-aaaaa1 already has SAMPLECREATORA15 (planned)"], "rows": [("codes/code-plan-2026-10-20.csv", 2)]},
    {"name": "live_preview_creates_nothing", "pre": [plan()],
     "run": [NONET, MINT, "{ws}", "--live", "--date", "2026-10-20"], "exit": 0,
     "out": ["would create 2 discount code(s) in the live store bb-fixture-store.myshopify.com", "Nothing created"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned", "minted_by": ""})]},
    {"name": "live_without_token_must_fail", "pre": [plan()], "env": {"SHOPIFY_ADMIN_TOKEN": ""},
     "run": [NONET, MINT, "{ws}", "--live", "--yes", "--date", "2026-10-20"], "exit": 1, "err": ["SHOPIFY_ADMIN_TOKEN"]},
    {"name": "live_without_terminal_must_fail", "pre": [plan()], "env": {"SHOPIFY_ADMIN_TOKEN": "fixture-token-not-real"},
     "run": [NONET, MINT, "{ws}", "--live", "--yes", "--date", "2026-10-20"], "exit": 1, "err": ["own terminal"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned"})]},
    {"name": "live_wrong_confirmation_must_fail", "pre": [plan()],
     "run": [FAKE, MINT, "{ws}", "ok,ok", "bb-fixture-store.myshopify.com 3"], "exit": 1,
     "err": ["does not match"], "out": ["received 0 request(s)"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned"})]},
    {"name": "live_answers_recorded", "pre": [plan()],
     "run": [FAKE, MINT, "{ws}", "ok,taken", "expected"], "exit": 2,
     "out": ["Created 1 of 2; collisions 1", "received 2 request(s)", "PARTIAL"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "minted", "minted_by": "api"}),
               ("codes/code-plan-2026-10-20.csv", "c-bbbbb2", {"status": "collision"})]},
    {"name": "live_collision_by_error_code", "pre": [plan()],
     "run": [FAKE, MINT, "{ws}", "taken_code_only,ok", "expected"], "exit": 2,
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "collision"}),
               ("codes/code-plan-2026-10-20.csv", "c-bbbbb2", {"status": "minted"})]},
    {"name": "live_throttle_stops_without_retry", "pre": [plan()],
     "run": [FAKE, MINT, "{ws}", "throttled", "expected"], "exit": 2,
     "out": ["Stopped early: throttled", "received 1 request(s)"],
     "cells": [("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "planned"}),
               ("codes/code-plan-2026-10-20.csv", "c-bbbbb2", {"status": "planned"})]},
    {"name": "record_manual_green", "pre": [plan()], "run": record(*RECORD_A), "exit": 0,
     "dated_notes": ["data/creators.csv", "data/pipeline.csv", "codes/code-plan-2026-10-20.csv"],
     "out": ["c-aaaaa1 to active", "customer discount: 15 percent", "holdback: 30 days"],
     "cells": [("data/creators.csv", "c-aaaaa1", {"status": "active", "code": "SAMPLECREATORA15", "rail": "manual",
                "affiliate_link": "https://www.example.com/?utm_source=instagram&utm_medium=creator&utm_campaign=2026-11-launch&utm_content=c-aaaaa1",
                "last_activity": "2026-10-20", "first_campaign": "2026-11-launch"}),
               ("data/pipeline.csv", "c-aaaaa1", {"stage": "onboarded", "owner_role": "programme lead"}),
               ("codes/code-plan-2026-10-20.csv", "c-aaaaa1", {"status": "active", "minted_by": "admin_ui"})]},
    {"name": "record_collabs_green", "edit": [("program/program.md", RAIL_LINE, "a payout list), `none` yet: `collabs` [owner]")],
     "run": record("--creator", "c-bbbbb2", "--code", "SAMPLEB15", "--link", "https://collabs.example.com/sampleb",
                   "--tested", "order:1043", "--tested-on", "2026-10-19", "--discount-seen", "15%"), "exit": 0,
     "cells": [("data/creators.csv", "c-bbbbb2", {"status": "active", "code": "SAMPLEB15", "rail": "collabs",
                "affiliate_link": "https://collabs.example.com/sampleb"}),
               ("codes/code-plan-2026-10-20.csv", "c-bbbbb2", {"status": "active", "minted_by": "collabs"})],
     "note_entry": [("data/creators.csv", "c-bbbbb2", "2026-10-19 test order #1043"), ("codes/code-plan-2026-10-20.csv", "c-bbbbb2", "2026-10-19 test order #1043")],
     "dated_notes": ["data/creators.csv", "data/pipeline.csv", "codes/code-plan-2026-10-20.csv"],
     "out": ["test order: #1043"]},
    {"name": "record_test_date_after_record_must_fail", "edit": [("program/program.md", RAIL_LINE, "a payout list), `none` yet: `collabs` [owner]")],
     "run": record("--creator", "c-bbbbb2", "--code", "SAMPLEB15", "--link", "https://collabs.example.com/sampleb",
                   "--tested", "order:#1043", "--tested-on", "2026-10-21", "--discount-seen", "15 percent"), "exit": 1,
     "err": ["--tested-on '2026-10-21' must be a date, YYYY-MM-DD, no later than 2026-10-20"],
     "cells": [("data/creators.csv", "c-bbbbb2", {"status": "agreed"})]},
    {"name": "record_owner_role_from_section10",
     "edit": [("program/program.md", "| programme lead | runs discovery", "| creator manager | runs discovery")], "pre": [plan()],
     "run": [NONET, RECORD, "{ws}", "--date", "2026-10-20", "--checked-by", "creator manager"] + RECORD_A,
     "exit": 0, "out": ["owner_role kept as 'programme lead' because programme section 10 has no 'programme lead' role"],
     "cells": [("data/pipeline.csv", "c-aaaaa1", {"stage": "onboarded", "owner_role": "programme lead"})]},
    {"name": "record_without_test_must_fail", "pre": [plan()],
     "run": record("--creator", "c-aaaaa1", "--code", "SAMPLECREATORA15", "--discount-seen", "15 percent", "--minted-by", "admin_ui"),
     "exit": 1, "err": ["--tested is missing"], "cells": [("data/creators.csv", "c-aaaaa1", {"status": "agreed", "code": ""})]},
    {"name": "record_wrong_discount_must_fail", "pre": [plan()],
     "run": record("--creator", "c-aaaaa1", "--code", "SAMPLECREATORA15", "--tested", "checkout", "--discount-seen", "10 percent", "--minted-by", "admin_ui"),
     "exit": 1, "err": ["programme section 4 sets 15 percent"]},
    {"name": "record_combining_against_section4_must_fail", "pre": [plan()],
     "run": record("--creator", "c-aaaaa1", "--code", "SAMPLECREATORA15", "--tested", "checkout", "--discount-seen", "15 percent",
                   "--minted-by", "admin_ui", "--combines", "yes"), "exit": 1,
     "err": ["combined with another discount at checkout, but programme section 4 says"],
     "cells": [("data/creators.csv", "c-aaaaa1", {"status": "agreed"})]},
    {"name": "record_person_not_role_must_fail", "pre": [plan()],
     "run": [NONET, RECORD, "{ws}", "--date", "2026-10-20", "--checked-by", "store manager"] + RECORD_A,
     "exit": 1, "err": ["roles, never names"]},
    {"name": "record_collision_must_fail", "edit": [("program/program.md", RAIL_LINE, "a payout list), `none` yet: `collabs` [owner]")],
     "run": record("--creator", "c-bbbbb2", "--code", "OLDCODE15", "--link", "https://collabs.example.com/sampleb",
                   "--tested", "checkout", "--discount-seen", "15 percent"), "exit": 1,
     "err": ["OLDCODE15 is already used by c-ddddd4"], "cells": [("data/creators.csv", "c-bbbbb2", {"status": "agreed"})]},
    {"name": "kit_green", "pre": [plan(), record(*RECORD_A)],
     "copy": [("kits/c-aaaaa1-good.md", "campaigns/2026-11-launch/welcome/c-aaaaa1.md")],
     "run": [NONET, KIT, "{ws}", "campaigns/2026-11-launch/welcome/c-aaaaa1.md"], "exit": 0,
     "out": ["Result: PASS", "NOTE campaigns/2026-11-launch/briefs/c-aaaaa1.md does not exist yet"]},
    {"name": "kit_faults_must_fail", "pre": [plan(), record(*RECORD_A)],
     "copy": [("kits/c-aaaaa1-bad.md", "campaigns/2026-11-launch/welcome/c-aaaaa1.md")],
     "run": [NONET, KIT, "{ws}", "campaigns/2026-11-launch/welcome/c-aaaaa1.md"], "exit": 1,
     "out": ["OLDCODE15 is another creator's code", "'safe' reads as a product claim", "template slot is still unfilled",
             "a rail label is left", "does not give the customer discount as '15 percent'", "Result: FAIL"]},
    {"name": "kit_attribution_against_section5_must_fail",
     "edit": [("program/program.md", "Changes here change every report: as written [default]",
               "Changes here change every report: a matching code wins; links are not attributed [owner]")],
     "pre": [plan(), record(*RECORD_A)],
     "copy": [("kits/c-aaaaa1-good.md", "campaigns/2026-11-launch/welcome/c-aaaaa1.md")],
     "run": [NONET, KIT, "{ws}", "campaigns/2026-11-launch/welcome/c-aaaaa1.md"], "exit": 1,
     "out": ["the attribution sentence is not the one for the manual rail", "a matching code wins; links are not attributed"]},
    {"name": "kit_before_record_must_fail", "pre": [plan()],
     "copy": [("kits/c-aaaaa1-good.md", "campaigns/2026-11-launch/welcome/c-aaaaa1.md")],
     "run": [NONET, KIT, "{ws}", "campaigns/2026-11-launch/welcome/c-aaaaa1.md"], "exit": 1, "err": ["not yet active"]},
]


def rows_of(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_cmd(cmd, ws, env):
    full = PY + [c.replace("{ws}", str(ws)) for c in cmd]
    e = dict(os.environ)
    e.pop("SHOPIFY_ADMIN_TOKEN", None)
    e.update(env)
    return subprocess.run(full, capture_output=True, text=True, env=e, stdin=subprocess.DEVNULL, timeout=60)


def check(case, tmp):
    ws = tmp / "ws"
    shutil.copytree(HERE / "base", ws)
    problems = []
    for rel, old, new in case.get("edit", []):
        p = ws / rel
        t = p.read_text(encoding="utf-8")
        if old not in t:
            return [f"edit target not found in {rel}: {old[:40]}"]
        p.write_text(t.replace(old, new, 1), encoding="utf-8")
    for rel, text in case.get("append", []):
        with open(ws / rel, "a", encoding="utf-8") as f:
            f.write(text)
    env = case.get("env", {})
    for cmd in case.get("pre", []):
        r = run_cmd(cmd, ws, {})
        if r.returncode != 0:
            return [f"setup command exited {r.returncode}: {(r.stdout + r.stderr).strip()[-300:]}"]
    for src, dst in case.get("copy", []):
        (ws / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / src, ws / dst)
    r = run_cmd(case["run"], ws, env)
    if r.returncode != case["exit"]:
        problems.append(f"exit {r.returncode}, expected {case['exit']}")
    if "network call attempted" in r.stdout + r.stderr:
        problems.append("a network call was attempted")
    for s in case.get("out", []):
        if s not in r.stdout:
            problems.append(f"stdout lacks: {s}")
    for s in case.get("err", []):
        if s not in r.stderr:
            problems.append(f"stderr lacks: {s}")
    for rel, exp in case.get("same_file", []):
        got, want = ws / rel, HERE / exp
        if not got.exists():
            problems.append(f"missing {rel}")
        elif rel.endswith(".json"):
            if json.loads(got.read_text()) != json.loads(want.read_text()):
                problems.append(f"{rel} differs from {exp}")
        elif got.read_text(encoding="utf-8") != want.read_text(encoding="utf-8"):
            problems.append(f"{rel} differs from {exp}")
    for rel, ref, want in case.get("cells", []):
        p = ws / rel
        if not p.exists():
            problems.append(f"missing {rel}")
            continue
        hits = [x for x in rows_of(p) if x.get("creator_ref") == ref]
        if not hits:
            problems.append(f"{rel} has no row for {ref}")
            continue
        for col, val in want.items():
            if hits[-1].get(col) != val:
                problems.append(f"{rel} {ref} {col} = '{hits[-1].get(col)}', expected '{val}'")
    for rel, ref in case.get("no_row", []):
        if (ws / rel).exists() and any(x.get("creator_ref") == ref for x in rows_of(ws / rel)):
            problems.append(f"{rel} has a row for {ref}, expected none")
    for rel, n in case.get("rows", []):
        got = len(rows_of(ws / rel))
        if got != n:
            problems.append(f"{rel} has {got} rows, expected {n}")
    for rel, keys, want in case.get("json", []):
        node = json.loads((ws / rel).read_text()) if (ws / rel).exists() else None
        for k in keys:
            node = node.get(k) if isinstance(node, dict) else None
        if node != want:
            problems.append(f"{rel} {'.'.join(keys)} = {node!r}, expected {want!r}")
    for rel, keys in case.get("json_absent", []):
        node = json.loads((ws / rel).read_text()) if (ws / rel).exists() else {}
        for k in keys[:-1]:
            node = node.get(k, {})
        if keys[-1] in node:
            problems.append(f"{rel} carries {'.'.join(keys)}, expected it absent")
    for rel, ref, entry in case.get("note_entry", []):
        rows = [x for x in rows_of(ws / rel) if x.get("creator_ref") == ref] if (ws / rel).exists() else []
        if not rows or entry not in [e.strip() for e in rows[-1]["notes"].split(";")]:
            problems.append(f"{rel} {ref} notes have no entry exactly '{entry}'")
    for rel in case.get("dated_notes", []):
        for x in rows_of(ws / rel):
            for e in [e.strip() for e in x["notes"].split(";") if e.strip()]:
                if not re.match(r"^\d{4}-\d{2}-\d{2} ", e):
                    problems.append(f"{rel} {x.get('creator_ref')}: notes entry '{e[:50]}' does not start with its date")
    for rel, s in case.get("contains", []):
        if s not in (ws / rel).read_text(encoding="utf-8"):
            problems.append(f"{rel} lacks: {s}")
    for rel in case.get("absent", []):
        if (ws / rel).exists():
            problems.append(f"{rel} exists, expected absent")
    if problems:
        problems.append("output was: " + (r.stdout + r.stderr).strip().replace("\n", " | ")[-600:])
    return problems


def main():
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix="ao-fixture-") as d:
            problems = check(case, Path(d))
        if problems:
            failed += 1
            print(f"FAIL {case['name']}")
            for p in problems:
                print(f"     {p}")
        else:
            print(f"pass {case['name']}")
    print(f"{len(CASES) - failed} of {len(CASES)} cases passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
