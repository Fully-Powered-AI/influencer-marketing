#!/usr/bin/env bash
# Fixture runner for commission_statement.py. Every case runs on a copy of ws-green in a temporary
# folder, so the fixtures themselves are never written to. Exits non-zero if any case misses.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../commission_statement.py"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
misses=0
passes=0

say() { printf '%s\n' "${1}"; }
miss() { say "MISS ${1}"; misses=$((misses + 1)); }
pass() { say "ok   ${1}"; passes=$((passes + 1)); }

fresh() {   # fresh <name>: copy the green workspace to TMP/<name>
  rm -rf "${TMP:?}/${1}"
  cp -R "${HERE}/ws-green" "${TMP}/${1}"
}

runit() {   # runit <workspace> <period> <as-of> [extra args]: sets CODE, OUT, ERR
  local ws="${1}" period="${2}" asof="${3}"
  shift 3
  python3 -I "${SCRIPT}" "${ws}" --period "${period}" --as-of "${asof}" "$@" >"${TMP}/out.txt" 2>"${TMP}/err.txt"
  CODE=$?
  OUT="$(cat "${TMP}/out.txt")"
  ERR="$(cat "${TMP}/err.txt")"
}

expect_code() {   # expect_code <case> <want>
  if [ "${CODE}" -eq "${2}" ]; then pass "${1}: exit ${CODE}"; else miss "${1}: exit ${CODE}, wanted ${2}; ${ERR}"; fi
}

same_files() {   # same_files <case> <expected dir> <payout dir>
  local f
  for f in statement.csv payout-list.csv statement.md; do
    if diff -u "${HERE}/expected/${2}/${f}" "${3}/${f}" >"${TMP}/diff.txt"; then
      pass "${1}: ${f} matches expected/${2}"
    else
      miss "${1}: ${f} differs from expected/${2}"; head -20 "${TMP}/diff.txt"
    fi
  done
}

contains() {   # contains <case> <file> <text>
  if grep -qF -- "${3}" "${2}"; then pass "${1}: has '${3}'"; else miss "${1}: '${3}' not found in ${2##*/}"; fi
}

lacks() {   # lacks <case> <file> <text>
  if grep -qF -- "${3}" "${2}"; then miss "${1}: '${3}' should not appear in ${2##*/}"; else pass "${1}: no '${3}'"; fi
}

lines_are() {   # lines_are <case> <file> <count>
  local n
  n=$(wc -l <"${2}" | tr -d ' ')
  if [ "${n}" -eq "${3}" ]; then pass "${1}: ${2##*/} has ${3} lines"; else miss "${1}: ${2##*/} has ${n} lines, wanted ${3}"; fi
}

# 1 green, preview: the holdback is still open; pending orders listed, payout list empty
fresh ws
runit "${TMP}/ws" 2026-08 2026-09-10
expect_code "preview" 0
same_files "preview" preview "${TMP}/ws/payouts/2026-08"

# 2 green, final on the same workspace: replaces the draft preview; carried amounts read from 2026-07
runit "${TMP}/ws" 2026-08 2026-10-01
expect_code "final" 0
same_files "final" final "${TMP}/ws/payouts/2026-08"
lacks "final, instruction in an export cell ignored" "${TMP}/ws/payouts/2026-08/statement.md" "double"
contains "final, onboarding test order excluded" "${TMP}/ws/payouts/2026-08/statement.md" "| the onboarding test order (named in the roster notes) | 1 | 28.90 |"

# 3 without the link-attribution file while c-ccc333 holds a tracked link: only codes attribute, the run is
#   partial, and that creator stays off the payout list (schemas ruling; performance-report does the same)
fresh nolink
rm "${TMP}/nolink/exports/link-attribution-2026-08.csv"
runit "${TMP}/nolink" 2026-08 2026-10-01
expect_code "no link file, a link issued" 2
same_files "no link file, a link issued" final-no-link "${TMP}/nolink/payouts/2026-08"
lacks "no link file, a link issued" "${TMP}/nolink/payouts/2026-08/payout-list.csv" "c-ccc333"

# 4 must-fail: export without a Financial Status column -> partial, exit 2, no payout rows
fresh nostatus
rm "${TMP}/nostatus/exports/"orders-export-2026-08*.csv
cp "${HERE}/variants/orders-no-financial-status.csv" "${TMP}/nostatus/exports/orders-export-2026-08.csv"
runit "${TMP}/nostatus" 2026-08 2026-10-01
expect_code "no financial status" 2
contains "no financial status" "${TMP}/nostatus/payouts/2026-08/statement.md" "as of 2026-10-01: partial"
contains "no financial status" "${TMP}/nostatus/payouts/2026-08/statement.md" "has no Financial Status column"
lines_are "no financial status" "${TMP}/nostatus/payouts/2026-08/payout-list.csv" 1

# 5 must-fail: a period with no orders -> exit 0, empty statement, coverage says it looked
fresh empty
runit "${TMP}/empty" 2026-06 2026-10-01
expect_code "empty period" 0
lines_are "empty period" "${TMP}/empty/payouts/2026-06/statement.csv" 1
contains "empty period" "${TMP}/empty/payouts/2026-06/statement.md" "the script looked and found none"
contains "empty period" "${TMP}/empty/payouts/2026-06/statement.md" "Coverage: used"

# 6 an active creator with no agreement_date -> that creator not assessed, run partial, others still listed
fresh noagree
cp "${HERE}/variants/creators-with-missing-agreement.csv" "${TMP}/noagree/data/creators.csv"
runit "${TMP}/noagree" 2026-08 2026-10-01
expect_code "missing agreement date" 2
contains "missing agreement date" "${TMP}/noagree/payouts/2026-08/statement.md" "c-ggg777: #1018 not assessed"
lines_are "missing agreement date" "${TMP}/noagree/payouts/2026-08/payout-list.csv" 3
lacks "missing agreement date" "${TMP}/noagree/payouts/2026-08/payout-list.csv" "c-ggg777"

# 7 bad input: the programme leaves the holdback blank -> exit 1 naming section 5, nothing written
fresh noholdback
cp "${HERE}/variants/program-holdback-blank.md" "${TMP}/noholdback/program/program.md"
runit "${TMP}/noholdback" 2026-08 2026-10-01
expect_code "holdback blank" 1
case "${ERR}" in *"section 5"*) pass "holdback blank: names section 5";; *) miss "holdback blank: stderr does not name section 5: ${ERR}";; esac
if [ -e "${TMP}/noholdback/payouts/2026-08" ]; then miss "holdback blank: wrote output"; else pass "holdback blank: nothing written"; fi

# 8 bad input: a person has approved a row -> a rerun refuses to overwrite it
fresh locked
runit "${TMP}/locked" 2026-08 2026-10-01
sed 's/,draft,2026-10-01 final statement;rate from roster;attributed by tracked link/,approved,2026-10-01 final statement;rate from roster;attributed by tracked link/' \
  "${TMP}/locked/payouts/2026-08/statement.csv" >"${TMP}/locked.csv" && mv "${TMP}/locked.csv" "${TMP}/locked/payouts/2026-08/statement.csv"
runit "${TMP}/locked" 2026-08 2026-10-01
expect_code "approved row protected" 1
case "${ERR}" in *"approved"*) pass "approved row protected: says why";; *) miss "approved row protected: ${ERR}";; esac

# 9 bad input: an as-of date in the future, and a named export that is not an orders export
fresh odd
runit "${TMP}/odd" 2026-08 2099-01-01
expect_code "as-of in the future" 1
runit "${TMP}/odd" 2026-08 2026-10-01 --export "${TMP}/odd/exports/instagram-insights-2026-08.csv"
expect_code "named export is not an orders export" 1

# 10 programme section 4 says partial refunds come off in proportion: 80 x 20 / 87 = 18.39 off the basis
fresh prop
cp "${HERE}/variants/program-refund-proportion.md" "${TMP}/prop/program/program.md"
runit "${TMP}/prop" 2026-08 2026-10-01
expect_code "refunds in proportion" 0
contains "refunds in proportion" "${TMP}/prop/payouts/2026-08/statement.csv" "c-aaa111,Creator A (fixture),manual,9,4,255.00,18.39,236.61,20,47.32,0.00,47.32,"
contains "refunds in proportion" "${TMP}/prop/payouts/2026-08/payout-list.csv" "c-aaa111,Creator A (fixture),manual,47.32,USD"

# 11 a fee milestone entry carrying the owner's own text after the colon still makes the fee due
fresh ownernote
sed 's/fee milestone reached by programme lead: finance to pay/fee milestone reached by owner: second deliverable set agreed 2026-08-10/' \
  "${HERE}/ws-green/data/publications.csv" >"${TMP}/ownernote/data/publications.csv"
runit "${TMP}/ownernote" 2026-08 2026-10-01
expect_code "milestone with the owner's text" 0
contains "milestone with the owner's text" "${TMP}/ownernote/payouts/2026-08/statement.csv" "c-ccc333,Creator C (fixture),manual,2,0,190.00,0.00,190.00,10,19.00,150.00,169.00,"

# 12 a "fee milestone part" entry is not a reached milestone: no fee, and the row says none was recorded
fresh part
sed 's/fee milestone reached by programme lead: finance to pay/fee milestone part by programme lead: first post of the set/' \
  "${HERE}/ws-green/data/publications.csv" >"${TMP}/part/data/publications.csv"
runit "${TMP}/part" 2026-08 2026-10-01
expect_code "milestone part only" 0
contains "milestone part only" "${TMP}/part/payouts/2026-08/statement.csv" "10,19.00,0.00,19.00,"
contains "milestone part only" "${TMP}/part/payouts/2026-08/statement.csv" "posted in the period (p-ccc001) but no fee milestone recorded"

# 13 must-fail: the minimum payout left blank under the template's unmarked instruction line ("Write the minimum
#    as minimum <amount> or no minimum"); the instruction is template text, never the owner's value -> exit 1
fresh minblank
cp "${HERE}/variants/program-minimum-blank.md" "${TMP}/minblank/program/program.md"
runit "${TMP}/minblank" 2026-08 2026-10-01
expect_code "minimum blank under the instruction" 1
case "${ERR}" in *"section 6"*"Payout schedule"*) pass "minimum blank: names section 6 and the line";; *) miss "minimum blank: ${ERR}";; esac
if [ -e "${TMP}/minblank/payouts/2026-08" ]; then miss "minimum blank: wrote output"; else pass "minimum blank: nothing written"; fi

# 14 must-fail: a schedule with no minimum stated; joining the instruction would have read "no minimum" -> exit 1
fresh minunstated
cp "${HERE}/variants/program-minimum-unstated.md" "${TMP}/minunstated/program/program.md"
runit "${TMP}/minunstated" 2026-08 2026-10-01
expect_code "minimum not stated, instruction present" 1
case "${ERR}" in *"does not state the minimum"*) pass "minimum not stated: says so";; *) miss "minimum not stated: ${ERR}";; esac

# 15 the minimum on a marked indented line under the field is the owner's value and is read
fresh minindented
cp "${HERE}/variants/program-minimum-indented.md" "${TMP}/minindented/program/program.md"
runit "${TMP}/minindented" 2026-08 2026-10-01
expect_code "minimum on a marked indented line" 0
contains "minimum on a marked indented line" "${TMP}/minindented/payouts/2026-08/statement.md" "minimum payout 25.00 USD"
contains "minimum on a marked indented line" "${TMP}/minindented/payouts/2026-08/statement.csv" "below minimum 25.00: carried forward 7.50"

# 16 codes only in section 5: the missing link file is not a gap
fresh codesonly
rm "${TMP}/codesonly/exports/link-attribution-2026-08.csv"
sed 's/Changes here change every report: code first, then tracked link \[default\]/Changes here change every report: codes only [owner]/' \
  "${HERE}/ws-green/program/program.md" >"${TMP}/codesonly/program/program.md"
runit "${TMP}/codesonly" 2026-08 2026-10-01
expect_code "codes only, no link file" 0

# 17 program-setup's own filled programme (copied verbatim) reads to the same statement as the green programme
fresh filled
cp "${HERE}/variants/program-filled-by-program-setup.md" "${TMP}/filled/program/program.md"
runit "${TMP}/filled" 2026-08 2026-10-01
expect_code "program-setup's filled programme" 0
if diff -q "${HERE}/expected/final/statement.csv" "${TMP}/filled/payouts/2026-08/statement.csv" >/dev/null; then
  pass "program-setup's filled programme: statement.csv matches expected/final"
else miss "program-setup's filled programme: statement.csv differs from expected/final"; fi
contains "program-setup's filled programme" "${TMP}/filled/payouts/2026-08/statement.md" "WELCOME10 on 2 orders"

# 18 a carried amount survives an unfinalised month: July final carries 8.00 for c-fff666, August is only a
#    preview, September reads the 8.00 from July; a rerun of August then warns that September exists
fresh walk
runit "${TMP}/walk" 2026-08 2026-09-10
runit "${TMP}/walk" 2026-09 2026-10-15
contains "carry walks back past a preview" "${TMP}/walk/payouts/2026-09/statement.csv" "carried in 8.00 from 2026-07"
contains "carry walks back past a preview" "${TMP}/walk/payouts/2026-09/statement.md" "rows of 2026-08's statement are not final"
runit "${TMP}/walk" 2026-08 2026-10-01
contains "rerun after a later statement" "${TMP}/walk/payouts/2026-08/statement.md" "a later statement exists (2026-09)"

# 19 "today" is the UTC date
fresh utc
runit "${TMP}/utc" 2026-08 "$(date -u +%F)"
expect_code "run date of today in UTC" 0

# 20 the self-referral off-words are performance-report's list: "none" switches the rule off
fresh selfoff
sed 's/does not earn commission \[default\]: applies \[default\]/does not earn commission [default]: none [owner]/' \
  "${HERE}/ws-green/program/program.md" >"${TMP}/selfoff/program/program.md"
runit "${TMP}/selfoff" 2026-08 2026-10-01
contains "self-referral off by 'none'" "${TMP}/selfoff/payouts/2026-08/statement.csv" "c-aaa111,Creator A (fixture),manual,9,3,305.00,20.00,285.00,20,57.00,"

# 21 must-fail: the attribution line reads "as written" (schemas section 12: counts as missing) -> exit 1
fresh aswritten
sed 's/Changes here change every report: code first, then tracked link \[default\]/Changes here change every report: as written [default]/' \
  "${HERE}/ws-green/program/program.md" >"${TMP}/aswritten/program/program.md"
runit "${TMP}/aswritten" 2026-08 2026-10-01
expect_code "attribution as written" 1
case "${ERR}" in *"section 5"*"Attribution model"*) pass "attribution as written: names section 5";; *) miss "attribution as written: ${ERR}";; esac

# 22 the self-referral off-words match the whole value only: a sentence holding the word "no" keeps the rule on
fresh selfon
sed 's/does not earn commission \[default\]: applies \[default\]/does not earn commission [default]: an order the creator places earns no commission [owner]/' \
  "${HERE}/ws-green/program/program.md" >"${TMP}/selfon/program/program.md"
runit "${TMP}/selfon" 2026-08 2026-10-01
expect_code "self-referral sentence with 'no'" 0
contains "self-referral sentence with 'no'" "${TMP}/selfon/payouts/2026-08/statement.csv" "c-aaa111,Creator A (fixture),manual,9,4,255.00,20.00,235.00,20,47.00,"
contains "self-referral sentence with 'no'" "${TMP}/selfon/payouts/2026-08/statement.md" "self-referral rule applied"

# 23 the test-order entry is read dated ("2026-07-16 test order #1026", the green roster) and as an undated
#    legacy entry ("test order #1026")
fresh legacytest
sed 's/;2026-07-16 test order #1026/;test order #1026/' "${HERE}/ws-green/data/creators.csv" >"${TMP}/legacytest/data/creators.csv"
runit "${TMP}/legacytest" 2026-08 2026-10-01
expect_code "undated legacy test-order entry" 0
contains "undated legacy test-order entry" "${TMP}/legacytest/payouts/2026-08/statement.md" "| the onboarding test order (named in the roster notes) | 1 | 28.90 |"

say "${passes} passed, ${misses} missed"
[ "${misses}" -eq 0 ]
