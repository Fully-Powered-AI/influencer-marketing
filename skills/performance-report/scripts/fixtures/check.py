"""Assertions for run_fixtures.sh. Each command prints what it checked and exits 1 on the first miss."""
import csv
import pathlib
import re
import sys


def rows(path):
    return {r["creator_ref"]: r for r in csv.DictReader(open(path, newline="", encoding="utf-8"))}


def keys(perf, expected):
    got, bad = rows(perf), 0
    for e in csv.DictReader(open(expected, newline="", encoding="utf-8")):
        v = got.get(e["creator_ref"], {}).get(e["column"])
        if v != e["value"]:
            print("  miss: {} {} is {!r}, hand value {!r}".format(e["creator_ref"], e["column"], v, e["value"]))
            bad += 1
    return bad


def value(perf, ref, column, want):
    v = rows(perf).get(ref, {}).get(column)
    if v != want:
        print("  miss: {} {} is {!r}, want {!r}".format(ref, column, v, want))
        return 1
    return 0


def notes(note_dir, creators):
    roster = list(csv.DictReader(open(creators, newline="", encoding="utf-8")))
    bad = 0
    files = sorted(pathlib.Path(note_dir).glob("*.md"))
    if not files:
        print("  miss: no results notes were written")
        return 1
    for f in files:
        own = f.name[:8]
        text = f.read_text(encoding="utf-8")
        for r in roster:
            if r["creator_ref"] == own:
                continue
            for token in (r["creator_ref"], r["display_name"]):
                if token and token in text:
                    print("  miss: {} mentions another creator ({})".format(f.name, token))
                    bad += 1
    return bad


def nopii(folder):
    bad = 0
    for f in pathlib.Path(folder).rglob("*"):
        if f.is_file() and f.suffix in (".md", ".csv") and f.name not in ("costs.csv", "reach.csv", "plan.md"):
            text = f.read_text(encoding="utf-8")
            if re.search(r"[\w.+-]+@[\w-]+\.\w+", text) or "Ignore all previous" in text:
                print("  miss: {} carries an email address or input text".format(f))
                bad += 1
    return bad


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    n = {"keys": keys, "value": value, "notes": notes, "nopii": nopii}[cmd](*args)
    sys.exit(1 if n else 0)
