#!/usr/bin/env bash
# Fixtures for content-approval: check_caption.py and check_record.py.
# Green cases, must-attend cases (exit 2 with a named finding) and must-fail cases (exit 1).
# Runs from any folder; exits non-zero on any miss.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(dirname "$HERE")"
SKILL="$(dirname "$SCRIPTS")"
WS="$HERE/ws"
IN="$HERE/inputs"
CAMP=2026-12-fixture-launch
APP="$WS/campaigns/$CAMP/approvals"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
misses=0

run() { # name, wanted exit code, text the output must contain, then the command
  local name="${1}" want="${2}" text="${3}"; shift 3
  local out got
  out="$("$@" 2>&1)"; got=$?
  if [ "$got" != "$want" ]; then
    echo "MISS $name: exit $got, wanted $want"; printf '%s\n' "$out" | tail -4; misses=$((misses + 1)); return
  fi
  if [ -n "$text" ] && ! printf '%s\n' "$out" | grep -qF -- "$text"; then
    echo "MISS $name: output lacks: $text"; misses=$((misses + 1)); return
  fi
  echo "ok   $name (exit $got)"
}

cc() { python3 -I "$SCRIPTS/check_caption.py" "$@"; }
cr() { python3 -I "$SCRIPTS/check_record.py" "$@"; }
in_dir() { local d="${1}"; shift; (cd "$d" && "$@"); }

# check_caption.py
run "caption: clean post is all clear" 0 "all clear" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format post --product "Canvas Tote (fixture)" "$IN/clean-caption.txt"
run "caption: forbidden phrase is a stop" 2 'forbidden phrase "prevents all damage"' \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format post "$IN/forbidden-caption.txt"
run "caption: forbidden compatibility line found" 2 'forbidden phrase "works with every appliance"' \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format post "$IN/forbidden-caption.txt"
run "caption: buried disclosure is outside instagram's window" 2 "outside the window of 125" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format post "$IN/buried-caption.txt"
run "caption: late spoken disclosure" 2 "say it earlier" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format reel --transcript "$IN/late-transcript.txt" "$IN/clean-caption.txt"
run "caption: reel without a transcript is skipped, not passed" 2 "needs a transcript and none was given" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format reel "$IN/clean-caption.txt"
run "caption: platform barred in section 3" 2 "says organic creator posts: no; this is a stop" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform tiktok "$IN/clean-caption.txt"
run "caption: approved for another product" 2 "is not approved for Desk Tray (fixture)" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --product "Desk Tray (fixture)" "$IN/clean-caption.txt"
run "caption: the platform line's spoken form passes the transcript" 2 'spoken "this video is sponsored by Cedar Lane" at transcript char 0' \
  cc "$WS" --campaign $CAMP --creator c-fx0003 --platform youtube --format video --transcript "$IN/spoken-form-transcript.txt" "$IN/clean-caption.txt"
run "caption: without a spoken form, other spoken words do not pass" 2 "section 8 gives no 'spoken:' form for instagram" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format reel --transcript "$IN/spoken-form-transcript.txt" "$IN/clean-caption.txt"
run "caption: a workspace-relative caption path is found from another folder" 2 'forbidden phrase "prevents all damage"' \
  in_dir "$TMP" cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format post exports/$CAMP--c-fx0001--1-caption.txt
run "caption: the SKILL.md command works as printed, from the skill folder" 2 'forbidden phrase "prevents all damage"' \
  in_dir "$SKILL" python3 -I scripts/check_caption.py "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --format post exports/$CAMP--c-fx0001--1-caption.txt
run "caption: a usage error exits 1, not 2" 1 "see --help" \
  cc "$WS" --campaign $CAMP --creator c-fx0001 --platform instagram --no-such-flag "$IN/clean-caption.txt"
run "caption: unknown creator is bad input" 1 "is not in data/creators.csv" \
  cc "$WS" --campaign $CAMP --creator c-zz9999 --platform instagram "$IN/clean-caption.txt"

cp -R "$WS" "$TMP/no8"
python3 -I -c 'import re,sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(re.sub(r"(?ms)^## 8\..*?(?=^## 9\.)", "", s))' "$TMP/no8/program/program.md"
run "caption: programme without section 8 is bad input" 1 "has no section 8" \
  cc "$TMP/no8" --campaign $CAMP --creator c-fx0001 --platform instagram "$IN/clean-caption.txt"

cp -R "$WS" "$TMP/header"
python3 -I -c 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("creator_ref,display_name", "creator_ref,name", 1))' "$TMP/header/data/creators.csv"
run "caption: roster header break is bad input" 1 "header differs from schemas.md section 4" \
  cc "$TMP/header" --campaign $CAMP --creator c-fx0001 --platform instagram "$IN/clean-caption.txt"

# Strict shapes: only the lines program-setup writes are read (SKILL.md, Limits).
cp -R "$WS" "$TMP/loose7"
python3 -I -c 'import sys; p=sys.argv[1]; s=open(p).read(); a="- Desk Tray (fixture): \"Washes off with water\" [owner]\n"; open(p,"w").write(s.replace(a, a + "- \"Hypoallergenic\" (Canvas Tote (fixture)) [owner]\n", 1))' "$TMP/loose7/program/program.md"
run "caption: an Approved line in another shape is reported, not read" 2 "section 7 Approved line not in the shape" \
  cc "$TMP/loose7" --campaign $CAMP --creator c-fx0001 --platform instagram --format post "$IN/clean-caption.txt"

cp -R "$WS" "$TMP/all8"
python3 -I -c 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("  - instagram: ", "  - all: ", 1))' "$TMP/all8/program/program.md"
run "caption: an 'all' line does not stand in for the platform's line" 1 "has no line for instagram" \
  cc "$TMP/all8" --campaign $CAMP --creator c-fx0001 --platform instagram "$IN/clean-caption.txt"

# check_record.py
run "record: stop for a forbidden claim is consistent" 0 "computed verdict: stop, stop_reason: rule-broken" \
  cr "$WS" check "$APP/$CAMP--c-fx0001--1.md"
run "record: re-review with a text change is consistent" 0 "computed verdict: approve-with-changes" \
  cr "$WS" check "$APP/$CAMP--c-fx0001--2.md"
run "record: forbidden claim softened to changes fails" 2 "a stop is a stop" \
  cr "$WS" check "$APP/$CAMP--c-fx0002--1.md"
run "record: change asked of a line that passed fails" 2 "asks for a change to a line that did not fail" \
  cr "$WS" check "$APP/$CAMP--c-fx0002--1.md"
run "record: unwatched video approved fails" 2 "the title line must say 'partial'" \
  cr "$WS" check "$APP/$CAMP--c-fx0003--1.md"
run "record: unwatched video gives on-hold" 2 "the checklist gives verdict 'stop', stop_reason 'on-hold'" \
  cr "$WS" check "$APP/$CAMP--c-fx0003--1.md"
run "record: re-review with no earlier attempt on disk fails" 2 "is not on disk" \
  cr "$WS" check "$APP/$CAMP--c-fx0003--3.md"
run "record: a workspace-relative record path is found from another folder" 0 "computed verdict: stop, stop_reason: rule-broken" \
  in_dir "$TMP" cr "$WS" check campaigns/$CAMP/approvals/$CAMP--c-fx0001--1.md
run "record: the SKILL.md command works as printed, from the skill folder" 0 "computed verdict: approve-with-changes" \
  in_dir "$SKILL" python3 -I scripts/check_record.py "$WS" check campaigns/$CAMP/approvals/$CAMP--c-fx0001--2.md
run "record: a usage error exits 1, not 2" 1 "see --help" \
  cr "$WS" check
run "record: next-id counts the attempts" 0 "approval_id: $CAMP--c-fx0001--3" \
  cr "$WS" next-id --campaign $CAMP --creator c-fx0001
run "record: next-id refuses an unknown campaign" 1 "does not exist in the workspace" \
  cr "$WS" next-id --campaign 2026-12-no-such-campaign --creator c-fx0001

# The thresholds live in references/approval-checklist.md section 5, never in SKILL.md.
if grep -nwE '50|100|125|150|280' "$SKILL/SKILL.md" >/dev/null; then
  echo "MISS SKILL.md states a threshold that belongs in references/approval-checklist.md"; misses=$((misses + 1))
else
  echo "ok   SKILL.md carries no threshold"
fi

echo "fixtures: $misses miss(es)"
[ "$misses" -eq 0 ]
