#!/usr/bin/env python3
"""Fixture cases for score_creators.py. Each case runs on a fresh copy of fixtures/workspace.
Prints one line per case and exits 1 if any case misses its expected exit code or output."""
import csv
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "score_creators.py"
CASES = HERE / "cases"
AS_OF = ["--as-of", "2026-10-20"]
LONGLIST = "data/longlist-2026-10-15.csv"
misses = []


def fresh(tmp):
    ws = pathlib.Path(tmp) / "ws"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(HERE / "workspace", ws)
    return ws


def run(ws, *args):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(ws), *args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def shortlist(ws):
    path = ws / "data" / "shortlist-2026-10-20.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as f:
        return {r["handle"]: r for r in csv.DictReader(f)}


def case(name, ok, detail=""):
    print(("pass  " if ok else "MISS  ") + name + ("" if ok else f"  ({detail})"))
    if not ok:
        misses.append(name)


with tempfile.TemporaryDirectory() as tmp:
    green = [LONGLIST, str(CASES / "green-scores.csv"), "--posts", str(CASES / "posts-2026-10-19.csv"), *AS_OF]

    # green: three creators, mixed verdicts, output equal to the expected file
    ws = fresh(tmp)
    code, out, err = run(ws, *green)
    got = (ws / "data" / "shortlist-2026-10-20.csv").read_text(encoding="utf-8") if code == 0 else ""
    want = (CASES / "expected-green-shortlist.csv").read_text(encoding="utf-8")
    case("green: exit 0", code == 0, f"exit {code}: {err.strip()}")
    case("green: shortlist equals the expected file", got == want, "diff the files")
    case("green: first line says complete", out.splitlines()[0].endswith("complete") if out else False, out[:80])
    case("green: coverage line printed", "Coverage. Used:" in out, "no coverage line")
    rows = shortlist(ws) or {}
    case("green: verdicts engage, negotiate, exclude",
         [rows.get(h, {}).get("verdict") for h in ("@fixture_creator_a", "@fixture_creator_b", "@fixture_creator_c")]
         == ["engage", "negotiate", "exclude"], str({h: r.get("verdict") for h, r in rows.items()}))
    case("green: creator_ref filled from the roster", rows.get("@fixture_creator_c", {}).get("creator_ref") == "c-7k2m9q",
         "creator_ref not filled")
    case("green: tier and engagement_rate_pct columns filled",
         [(rows.get(h, {}).get("tier"), rows.get(h, {}).get("engagement_rate_pct"))
          for h in ("@fixture_creator_a", "@fixture_creator_b", "@fixture_creator_c")]
         == [("micro", "2.71"), ("mid", "4.84"), ("nano", "3.04")], "tier or rate columns wrong")
    case("green: tier kept out of reasons", rows and not any("tier " in r["reasons"] for r in rows.values()), "tier in reasons")
    case("green: brand_safety_flag none, none, exclude",
         [rows.get(h, {}).get("brand_safety_flag") for h in ("@fixture_creator_a", "@fixture_creator_b", "@fixture_creator_c")]
         == ["none", "none", "exclude"], "flag column wrong")
    case("green: engagement Measured with the read date", rows and all("Measured, counts read 2026-10-19" in r["reasons"]
         for r in rows.values()), "label")

    # the same date again: refused without --replace, set aside with it
    code, out, err = run(ws, *green)
    case("existing shortlist: exit 1 without --replace", code == 1 and "--replace" in err, f"exit {code}")
    code, out, err = run(ws, *green, "--replace")
    aside = list((ws / "data").glob("shortlist-2026-10-20.replaced-*.csv"))
    case("existing shortlist: --replace sets the old file aside", code == 0 and len(aside) == 1, f"exit {code}, {len(aside)} aside")

    # rates run: numbers only, nothing written
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, "--rates-only", "--posts", str(CASES / "posts-2026-10-19.csv"), *AS_OF)
    case("rates run: exit 0 and the computed median", code == 0 and "2.71 pct of followers" in out, f"exit {code}")
    case("rates run: writes nothing", shortlist(ws) is None, "a shortlist was written")

    # must-fail: a score out of range
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, str(CASES / "fail-score-out-of-range.csv"), *AS_OF)
    case("score out of range: exit 1 naming the line", code == 1 and "authenticity is 6" in err, f"exit {code}: {err.strip()}")
    case("score out of range: nothing written", shortlist(ws) is None, "a shortlist was written")

    # must-fail: a missing column
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, str(CASES / "fail-missing-column.csv"), *AS_OF)
    case("missing column: exit 1 naming it", code == 1 and "missing contactability" in err, f"exit {code}: {err.strip()}")

    # must-fail: a scored line without evidence
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, str(CASES / "fail-evidence-missing.csv"), *AS_OF)
    case("evidence missing: exit 1", code == 1 and "no entry for brand_safety" in err, f"exit {code}: {err.strip()}")

    # must-fail: programme section 9 not decided
    ws = fresh(tmp)
    prog = ws / "program" / "program.md"
    text = prog.read_text(encoding="utf-8")
    prog.write_text(text.replace("fixture wording [owner]\n- Brand voice", "fixture wording [open]\n- Brand voice"), encoding="utf-8")
    code, out, err = run(ws, *green)
    case("section 9 undecided: exit 1 naming section 9", code == 1 and "section 9 'redlines'" in err, f"exit {code}: {err.strip()}")

    # partial: no posts file, every creator low confidence, engage held at negotiate
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, str(CASES / "green-scores.csv"), *AS_OF)
    rows = shortlist(ws) or {}
    case("no posts: exit 2 and first line partial", code == 2 and out.splitlines()[0].startswith("Vetting run 2026-10-20: partial"),
         f"exit {code}")
    case("no posts: all low confidence", rows and all(r["confidence"] == "low" for r in rows.values()), "confidence not low")
    case("no posts: engage held at negotiate", rows.get("@fixture_creator_a", {}).get("verdict") == "negotiate", "verdict")
    case("no posts: engagement_rate_pct empty, tier still filled",
         rows and all(r["engagement_rate_pct"] == "" and r["tier"] for r in rows.values()), "columns")

    # partial: a line left empty is not judged; that creator is skipped and the run is partial
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, str(CASES / "partial-unjudged.csv"), "--posts", str(CASES / "posts-2026-10-19.csv"), *AS_OF)
    rows = shortlist(ws) or {}
    c = rows.get("@fixture_creator_c", {})
    case("unjudged line: exit 2, skip, total empty", code == 2 and c.get("verdict") == "skip" and c.get("total") == ""
         and "not judged: contactability" in c.get("reasons", ""), f"exit {code}, {c.get('verdict')}")

    # roster says excluded: the verdict is exclude whatever the total
    ws = fresh(tmp)
    shutil.copy(CASES / "roster-excluded.csv", ws / "data" / "creators.csv")
    code, out, err = run(ws, *green)
    a = (shortlist(ws) or {}).get("@fixture_creator_a", {})
    case("roster excluded: exclude kept", code == 0 and a.get("verdict") == "exclude" and a.get("creator_ref") == "c-a1b2c3",
         f"exit {code}, {a.get('verdict')}")

    # a merged-away roster row is skipped; the surviving row's ref is used (schemas.md section 4)
    ws = fresh(tmp)
    shutil.copy(CASES / "roster-merged.csv", ws / "data" / "creators.csv")
    code, out, err = run(ws, *green)
    c = (shortlist(ws) or {}).get("@fixture_creator_c", {})
    case("merged roster row: never matched, survivor used", code == 0 and c.get("creator_ref") == "c-b2c3d4"
         and "c-7k2m9q" not in out and "1 roster row(s) merged into another were skipped" in out,
         f"exit {code}, ref {c.get('creator_ref')}")

    # brand_safety_flag review: an open owner question holds engage at negotiate; a 3 flags review
    ws = fresh(tmp)
    code, out, err = run(ws, LONGLIST, str(CASES / "review-flag-scores.csv"), "--posts", str(CASES / "posts-2026-10-19.csv"), *AS_OF)
    rows = shortlist(ws) or {}
    a, b = rows.get("@fixture_creator_a", {}), rows.get("@fixture_creator_b", {})
    case("owner question: review and held at negotiate", a.get("brand_safety_flag") == "review" and a.get("verdict") == "negotiate"
         and "open for the owner" in a.get("reasons", ""), f"{a.get('brand_safety_flag')}, {a.get('verdict')}")
    case("brand_safety 3: review", b.get("brand_safety_flag") == "review" and b.get("verdict") == "negotiate", f"{b.get('brand_safety_flag')}")

    # a posts file whose name states no read date: engagement User-provided, with a warning
    ws = fresh(tmp)
    undated = pathlib.Path(tmp) / "recent-posts.csv"
    shutil.copy(CASES / "posts-2026-10-19.csv", undated)
    code, out, err = run(ws, LONGLIST, str(CASES / "green-scores.csv"), "--posts", str(undated), *AS_OF)
    a = (shortlist(ws) or {}).get("@fixture_creator_a", {})
    case("undated posts file: User-provided and warned", code == 0 and "User-provided, read date not stated" in a.get("reasons", "")
         and "carries no read date" in out, f"exit {code}")

    # programme section 3 says no for the platform: skip
    ws = fresh(tmp)
    shutil.copy(CASES / "platform-no" / "longlist-2026-10-15.csv", ws / "data" / "longlist-2026-10-15.csv")
    code, out, err = run(ws, LONGLIST, str(CASES / "platform-no" / "scores.csv"), *AS_OF)
    d = (shortlist(ws) or {}).get("@fixture_creator_d", {})
    case("platform ruled no: skip", d.get("verdict") == "skip" and "section 3 says no" in d.get("reasons", ""),
         f"exit {code}, {d.get('verdict')}")

print(f"{len(misses)} miss(es)")
sys.exit(1 if misses else 0)
