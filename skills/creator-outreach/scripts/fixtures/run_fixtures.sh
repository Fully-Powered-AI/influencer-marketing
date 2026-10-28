#!/usr/bin/env bash
# Runs every creator-outreach fixture: green cases, must-fail cases and partial cases for
# offer_calc.py, check_drafts.py and pipeline_stage.py. Exits non-zero on any miss.
# Written 2026-10-20. The fixture workspaces hold invented values only.
# Pipeline cases run on a temporary copy, so the fixtures are never changed.

set -u
HERE="$(cd "$(dirname "${0}")" && pwd)"
SCRIPTS="$(dirname "$HERE")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
MISSES=0
RUNS=0

expect() {  # expect <exit code> <description> <command...>
  local want="${1}" what="${2}"
  shift 2
  RUNS=$((RUNS + 1))
  "$@" >"$TMP/out" 2>"$TMP/err"
  local got=$?
  if [ "$got" -ne "$want" ]; then
    echo "MISS: $what (exit $got, wanted $want)"
    sed 's/^/    /' "$TMP/out" "$TMP/err" | head -20
    MISSES=$((MISSES + 1))
  else
    echo "ok:   $what (exit $got)"
  fi
}

contains() {  # contains <file out|err> <text> <description>
  RUNS=$((RUNS + 1))
  if grep -qF -- "${2}" "$TMP/${1}"; then
    echo "ok:   ${3}"
  else
    echo "MISS: ${3} (no \"${2}\" in ${1})"
    MISSES=$((MISSES + 1))
  fi
}

same() {  # same <expected file> <actual file> <description>
  RUNS=$((RUNS + 1))
  if diff -u "${1}" "${2}" >"$TMP/diff"; then
    echo "ok:   ${3}"
  else
    echo "MISS: ${3}"
    sed 's/^/    /' "$TMP/diff" | head -30
    MISSES=$((MISSES + 1))
  fi
}

PY="python3 -I"
OFFER="$SCRIPTS/offer_calc.py"
CHECK="$SCRIPTS/check_drafts.py"
PIPE="$SCRIPTS/pipeline_stage.py"
GREEN="$HERE/ws-green"
EXP="$HERE/expected"

echo "== offer_calc.py"
expect 0 "green: default programme" $PY "$OFFER" "$GREEN" --as-of 2026-10-20
cp "$TMP/out" "$TMP/offer-default.md"
same "$EXP/offer-default.md" "$TMP/offer-default.md" "green: default figures match the hand-checked block"
expect 0 "green: --flat 300 --tier micro" $PY "$OFFER" "$GREEN" --flat 300 --tier micro --as-of 2026-10-20
cp "$TMP/out" "$TMP/offer-flat.md"
same "$EXP/offer-flat-micro.md" "$TMP/offer-flat.md" "green: flat and hybrid break-even match the hand-checked block"
expect 0 "green: --creator c-eeeee5 past results" $PY "$OFFER" "$GREEN" --creator c-eeeee5 --as-of 2026-10-20
contains out "| total | 21 | 1 | 749.70 | 35.70 | 107.11 | 0.00 | 107.11 | |" "green: statement totals summed by the script"
expect 2 "partial: --tier macro has no anchor" $PY "$OFFER" "$GREEN" --flat 300 --tier macro --as-of 2026-10-20
contains out "Partial: tier comparison skipped" "partial: the first line says partial"
cp -R "$GREEN" "$TMP/ws-bad-statement"
mkdir -p "$TMP/ws-bad-statement/payouts/2026-09"
printf 'period,creator_ref,orders\n2026-09,c-eeeee5,4\n' >"$TMP/ws-bad-statement/payouts/2026-09/statement.csv"
expect 2 "partial: a statement with a broken header is skipped, not counted" $PY "$OFFER" "$TMP/ws-bad-statement" --creator c-eeeee5 --as-of 2026-10-20
contains out "payouts/2026-09/statement.csv skipped" "partial: the skipped file is named"
expect 0 "green: margin on net revenue, as section 1's indented line says" $PY "$OFFER" "$HERE/ws-net-margin" --flat 300 --as-of 2026-10-20
cp "$TMP/out" "$TMP/offer-net.md"
same "$EXP/offer-net-margin.md" "$TMP/offer-net.md" "green: net-margin figures match the hand-checked block"
expect 1 "must-fail: margin band blank, only the template's unmarked instruction under it" $PY "$OFFER" "$HERE/ws-margin-instruction-only" --as-of 2026-10-20
contains err "Programme section 1, gross margin band, is empty" "must-fail: the instruction is not read as the owner's value"
expect 0 "green: an unmarked answer under the margin band is template text" $PY "$OFFER" "$HERE/ws-margin-answer-unmarked" --as-of 2026-10-20
contains out "| gross margin read on | list price | pack default (schemas.md section 12)" "green: the margin stays on list price"
expect 1 "must-fail: no margin band" $PY "$OFFER" "$HERE/ws-no-margin" --as-of 2026-10-20
contains err "Programme section 1, gross margin band, is empty" "must-fail: names section 1 and the margin band"
expect 1 "must-fail: break-even line disagrees with its source" $PY "$OFFER" "$HERE/ws-copy-mismatch" --as-of 2026-10-20
contains err "break-even line gives 20" "must-fail: names both values"
expect 1 "must-fail: no programme file" $PY "$OFFER" "$TMP/no-such-workspace"
expect 1 "must-fail: unknown argument exits 1, not 2" $PY "$OFFER" "$GREEN" --bogus
expect 1 "must-fail: unknown creator" $PY "$OFFER" "$GREEN" --creator c-zzzzzz

echo "== check_drafts.py"
expect 0 "green: outreach file and replies file pass" $PY "$CHECK" "$GREEN" \
  campaigns/2026-09-launch-tote/outreach/c-aaaaa1.md campaigns/2026-09-launch-tote/outreach/replies.md
contains out "8 block(s) checked, 8 passed, 0 failed" "green: every block counted"
# The pack bars a dollar sign before a digit, emoji and exclamation marks from every file,
# so the planted ones are added here, at run time.
EMOJI="$(printf '\360\237\230\200')"
BANG="$(printf '\041')"
sed -e 's/DOLLARSIGN/$/g' -e "s/EMOJISIGN/${EMOJI}/g" -e "s/BANGSIGN/${BANG}/g" \
  "$HERE/drafts/must-fail.md" >"$TMP/must-fail.md"
expect 1 "must-fail: rule-breaking drafts" $PY "$CHECK" "$GREEN" "$TMP/must-fail.md"
contains out "below the 60 to 120 band" "must-fail: word count"
contains out "an emoji or emoticon" "must-fail: emoji"
contains out "an exclamation mark" "must-fail: exclamation mark"
contains out "1 link(s); first_touch allows 0" "must-fail: link in a first touch"
contains out "hype phrase(s): amazing, perfect fit" "must-fail: hype"
contains out "stock opener(s): hope this finds you" "must-fail: stock opener"
contains out "a dollar sign before a digit" "must-fail: dollar before a digit"
contains out "WARN claim word(s) safe, certified" "must-fail: unapproved claim warned"
contains out "a Subject: line in a DM" "must-fail: subject in a DM"
expect 2 "not checked: an unknown touch is reported, not passed" $PY "$CHECK" "$GREEN" "$HERE/drafts/not-checked.md"
expect 1 "must-fail: missing file" $PY "$CHECK" "$GREEN" campaigns/none.md

echo "== pipeline_stage.py"
WS="$TMP/ws"
cp -R "$GREEN" "$WS"
SET=($PY "$PIPE" "$WS" set --campaign 2026-09-launch-tote --owner-role "programme lead")
CPA="cpa 15 pct, code 15 pct off, no fee"
expect 0 "green: two creators identified together" "${SET[@]}" --creator c-aaaaa1 --creator c-bbbbb2 --stage identified --date 2026-09-01
contains out "with conditions, quoted" "green: section 3 conditions printed for instagram"
expect 2 "partial: identified again changes nothing" "${SET[@]}" --creator c-aaaaa1 --stage identified --date 2026-09-01
expect 1 "must-fail: first_touch without --offer" "${SET[@]}" --creator c-aaaaa1 --stage first_touch --date 2026-09-02
expect 0 "green: first touch recorded" "${SET[@]}" --creator c-aaaaa1 --stage first_touch --date 2026-09-02 --offer "$CPA"
contains out "next_action_date 2026-09-06 = stage_date 2026-09-02 + 4 calendar days" "green: follow-up date with its working"
contains out "status=contacted --note" "green: the roster status update is printed"
contains out "--date 2026-09-02" "green: the printed roster command carries the stage date (review 4-F10)"
contains out "last_activity 2026-09-01 -> 2026-09-02" "green: last_activity moved forward by the script (review 4-F11)"
expect 0 "green: follow-up 1" "${SET[@]}" --creator c-aaaaa1 --stage followed_up --date 2026-09-06
expect 0 "green: follow-up 2" "${SET[@]}" --creator c-aaaaa1 --stage followed_up --date 2026-09-11
expect 0 "green: follow-up 3" "${SET[@]}" --creator c-aaaaa1 --stage followed_up --date 2026-09-18
expect 1 "must-fail: a fourth follow-up" "${SET[@]}" --creator c-aaaaa1 --stage followed_up --date 2026-09-20
expect 1 "must-fail: a date before the current stage" "${SET[@]}" --creator c-aaaaa1 --stage no_response --date 2026-09-10
expect 0 "green: no_response after three" "${SET[@]}" --creator c-aaaaa1 --stage no_response --date 2026-09-25
expect 0 "green: second creator first touch" "${SET[@]}" --creator c-bbbbb2 --stage first_touch --date 2026-09-02 --offer "$CPA"
expect 1 "must-fail: agreed straight from first_touch" "${SET[@]}" --creator c-bbbbb2 --stage agreed --date 2026-09-03 --offer "$CPA"
expect 0 "green: replied" "${SET[@]}" --creator c-bbbbb2 --stage replied --date 2026-09-04
expect 0 "green: negotiating" "${SET[@]}" --creator c-bbbbb2 --stage negotiating --date 2026-09-05 --note "asks for a fee of 150.00"
HYB="hybrid 10 pct, code 15 pct off, fee 150.00"
expect 1 "must-fail: hybrid agreed without an approval" "${SET[@]}" --creator c-bbbbb2 --stage agreed --date 2026-09-08 --offer "$HYB"
expect 1 "must-fail: approval by a role section 4 does not name" "${SET[@]}" --creator c-bbbbb2 --stage agreed --date 2026-09-08 --offer "$HYB" --approved-by finance --approved-on 2026-09-07
expect 0 "green: hybrid agreed with the owner's approval" "${SET[@]}" --creator c-bbbbb2 --stage agreed --date 2026-09-08 --offer "$HYB" --approved-by owner --approved-on 2026-09-07
contains out "compensation_model=hybrid commission_rate_pct=10 flat_fee=150.00" "green: roster fields for the agreed deal"
contains out "until the terms are in writing" "green: agreed in principle leaves the roster status alone (review 4-F9)"
contains out "status=agreed agreement_date=YYYY-MM-DD" "green: the written-terms update is printed for partnership-agreement's hand-off"
RUNS=$((RUNS + 1))
if grep "roster, now" "$TMP/out" | grep -q "status=agreed"; then echo "MISS: the update to run now sets status=agreed"; MISSES=$((MISSES + 1)); else echo "ok:   the update to run now does not set status=agreed"; fi
expect 1 "must-fail: excluded creator" "${SET[@]}" --creator c-ccccc3 --stage identified --date 2026-09-01
expect 1 "must-fail: a roster row merged into another ref" "${SET[@]}" --creator c-hhhhh8 --stage identified --date 2026-09-01
contains err "merged into c-aaaaa1" "must-fail: the surviving ref is named"
expect 1 "must-fail: a live row's next_action belongs to publication-tracking (review 4-F5)" $PY "$PIPE" "$WS" set --campaign 2026-08-summer-clear --owner-role "programme lead" --creator c-ggggg7 --stage approved --date 2026-09-01 --approval-id 2026-08-summer-clear--c-ggggg7--1 --next-action "chase the creator"
contains err "whose next_action it owns" "must-fail: the owner of the live row is named"
expect 1 "must-fail: a creator marked do not contact" "${SET[@]}" --creator c-fffff6 --stage identified --date 2026-09-01
contains err "do not contact" "must-fail: the roster note is named"
expect 1 "must-fail: platform section 3 rules out" "${SET[@]}" --creator c-ddddd4 --stage identified --date 2026-09-01
expect 0 "green: the same creator on a platform section 3 allows" "${SET[@]}" --creator c-ddddd4 --stage identified --date 2026-09-01 --platform instagram
expect 1 "must-fail: a batch with one bad creator writes nothing" "${SET[@]}" --creator c-eeeee5 --creator c-ccccc3 --stage identified --date 2026-09-03
expect 1 "must-fail: a date in the future" "${SET[@]}" --creator c-eeeee5 --stage identified --date 2099-01-01
expect 1 "must-fail: a role not in section 10" $PY "$PIPE" "$WS" set --campaign 2026-09-launch-tote --owner-role intern --creator c-eeeee5 --stage identified --date 2026-09-03
expect 1 "must-fail: a campaign with no plan" $PY "$PIPE" "$WS" set --campaign 2026-10-no-plan --owner-role "programme lead" --creator c-eeeee5 --stage identified --date 2026-09-03
expect 0 "green: past partner identified, other campaign shown" "${SET[@]}" --creator c-eeeee5 --stage identified --date 2026-09-03
contains out "other campaign: 2026-06-summer-original at closed" "green: the earlier campaign is listed"
contains out "Sends from (programme section 10, quoted)" "green: the sending account is read from section 10"
expect 1 "must-fail: briefed straight from agreed (affiliate-onboarding writes onboarded first)" "${SET[@]}" --creator c-bbbbb2 --stage briefed --date 2026-09-10
expect 0 "green: briefed after onboarded" "${SET[@]}" --creator c-ggggg7 --stage briefed --date 2026-09-10
expect 0 "green: content_due with its due date" "${SET[@]}" --creator c-ggggg7 --stage content_due --date 2026-09-10 --due 2026-09-20
expect 1 "must-fail: approved straight from content_due" "${SET[@]}" --creator c-ggggg7 --stage approved --date 2026-09-12 --approval-id 2026-09-launch-tote--c-ggggg7--2
expect 0 "green: content_submitted" "${SET[@]}" --creator c-ggggg7 --stage content_submitted --date 2026-09-15
expect 1 "must-fail: approved without the approval record" "${SET[@]}" --creator c-ggggg7 --stage approved --date 2026-09-16
expect 1 "must-fail: approved under a record whose verdict is stop" "${SET[@]}" --creator c-ggggg7 --stage approved --date 2026-09-16 --approval-id 2026-09-launch-tote--c-ggggg7--1
contains err "verdict in 2026-09-launch-tote--c-ggggg7--1 is stop" "must-fail: the verdict is named"
expect 1 "must-fail: an approval id for another creator" "${SET[@]}" --creator c-ggggg7 --stage approved --date 2026-09-16 --approval-id 2026-09-launch-tote--c-bbbbb2--1
expect 0 "green: back to content_due after a stop" "${SET[@]}" --creator c-ggggg7 --stage content_due --date 2026-09-16 --approval-id 2026-09-launch-tote--c-ggggg7--1 --due 2026-09-22
expect 0 "green: the revision submitted" "${SET[@]}" --creator c-ggggg7 --stage content_submitted --date 2026-09-18
expect 1 "must-fail: back to content_due under an approve verdict" "${SET[@]}" --creator c-ggggg7 --stage content_due --date 2026-09-19 --approval-id 2026-09-launch-tote--c-ggggg7--2
expect 0 "green: approved under the approve record" "${SET[@]}" --creator c-ggggg7 --stage approved --date 2026-09-19 --approval-id 2026-09-launch-tote--c-ggggg7--2 --due 2026-09-25
expect 1 "must-fail: --due with an outreach stage" "${SET[@]}" --creator c-eeeee5 --stage first_touch --date 2026-09-03 --offer "$CPA" --due 2026-09-30
same "$EXP/pipeline-after.csv" "$WS/data/pipeline.csv" "green: data/pipeline.csv after the sequence"
same "$EXP/creators-after.csv" "$WS/data/creators.csv" "green: data/creators.csv after the sequence (last_activity only)"
expect 0 "green: show what is due" $PY "$PIPE" "$WS" show --campaign 2026-09-launch-tote --as-of 2026-09-30
cp "$TMP/out" "$TMP/show.md"
same "$EXP/show.md" "$TMP/show.md" "green: show output"
# Integration with creator-roster (review 4-F9 to 4-F11), when it is installed beside this
# skill: run every roster command the script prints for now, on a separate copy, through to
# agreed, then creator-roster's own check must be clean. Its note wording is not compared.
ROSTER="$(dirname "$(dirname "$SCRIPTS")")/creator-roster/scripts/roster.py"
if [ -f "$ROSTER" ]; then
  WS2="$TMP/ws-roster"
  cp -R "$GREEN" "$WS2"
  SET2=($PY "$PIPE" "$WS2" set --campaign 2026-09-launch-tote --owner-role "programme lead" --creator c-bbbbb2)
  run_printed() {  # run the roster updates the last set printed for now, never the later hand-off
    grep -E '^  roster(: |, now )' "$TMP/out" | grep 'python3 -I' | sed 's/^.*python3 -I/python3 -I/' >"$TMP/cmds"
    while IFS= read -r cmd; do
      RUNS=$((RUNS + 1))
      if eval "$cmd" >>"$TMP/roster-log" 2>&1; then echo "ok:   printed roster command ran: ${cmd##* update }"
      else echo "MISS: printed roster command failed: $cmd"; MISSES=$((MISSES + 1)); fi
    done <"$TMP/cmds"
  }
  expect 0 "roster: identified" "${SET2[@]}" --stage identified --date 2026-09-01; run_printed
  expect 0 "roster: first touch" "${SET2[@]}" --stage first_touch --date 2026-09-02 --offer "$CPA"; run_printed
  expect 0 "roster: replied" "${SET2[@]}" --stage replied --date 2026-09-04; run_printed
  expect 0 "roster: negotiating" "${SET2[@]}" --stage negotiating --date 2026-09-05; run_printed
  expect 0 "roster: hybrid agreed in principle" "${SET2[@]}" --stage agreed --date 2026-09-08 --offer "$HYB" --approved-by owner --approved-on 2026-09-07; run_printed
  expect 0 "roster: creator-roster check is clean after the printed commands" $PY "$ROSTER" "$WS2" check
  contains out "0 breaks, 0 warnings" "roster: no agreement_date or last_activity warning (review 4-F9, 4-F11)"
  RUNS=$((RUNS + 1))
  if grep -q '^c-bbbbb2,.*,negotiating,hybrid,10,150.00,' "$WS2/data/creators.csv"; then
    echo "ok:   roster: status still negotiating, deal fields recorded for partnership-agreement"
  else echo "MISS: roster: c-bbbbb2 should be negotiating with the hybrid deal fields"; MISSES=$((MISSES + 1)); fi
  RUNS=$((RUNS + 1))
  if grep -q '2026-09-08 programme lead' "$WS2/data/creators.csv"; then echo "ok:   roster: the note is dated with the stage date, not the run date (review 4-F10)"
  else echo "MISS: roster: the note should carry 2026-09-08"; MISSES=$((MISSES + 1)); fi
else
  echo "skip: creator-roster is not installed beside this skill; the roster integration case did not run"
fi
cp -R "$GREEN" "$TMP/ws-bad-header"
sed -i.bak '1s/owner_role/owner/' "$TMP/ws-bad-header/data/pipeline.csv"
expect 1 "must-fail: pipeline header differs from schemas.md" $PY "$PIPE" "$TMP/ws-bad-header" set --campaign 2026-09-launch-tote --owner-role "programme lead" --creator c-aaaaa1 --stage identified --date 2026-09-01
contains err "header differs from schemas.md" "must-fail: the header problem is named"

echo
echo "$RUNS checks, $MISSES missed."
[ "$MISSES" -eq 0 ]
