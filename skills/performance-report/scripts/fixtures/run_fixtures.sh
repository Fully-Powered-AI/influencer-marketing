#!/usr/bin/env bash
# Runs compute_performance.py against copies of the fixture workspace and exits non-zero on any miss.
# The fixture files are never written to; every case runs in a fresh temporary copy.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../compute_performance.py"
CHECK="${HERE}/check.py"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
SLUG="2026-11-tote-launch"
WINDOW=(--campaign "${SLUG}" --from 2026-11-01 --to 2026-11-30 --as-of 2026-12-10)
FAILS=0
CASES=0

fresh() { rm -rf "${TMP}/ws"; cp -R "${HERE}/ws-green" "${TMP}/ws"; }
run() { python3 -I "${SCRIPT}" "${TMP}/ws" "$@" >"${TMP}/out" 2>"${TMP}/err"; echo "$?" >"${TMP}/code"; }
expect_exit() {
  local want="${1}" name="${2}" got
  got="$(cat "${TMP}/code")"
  CASES=$((CASES + 1))
  if [ "${got}" != "${want}" ]; then
    echo "FAIL ${name}: exit ${got}, expected ${want}"; sed 's/^/  | /' "${TMP}/err" | head -5; FAILS=$((FAILS + 1)); return 1
  fi
  return 0
}
expect_text() {
  local name="${1}" pattern="${2}"
  if ! grep -qi -- "${pattern}" "${TMP}/out" "${TMP}/err"; then
    echo "FAIL ${name}: output does not mention '${pattern}'"; FAILS=$((FAILS + 1)); return 1
  fi
  return 0
}
assert() {
  local name="${1}"; shift
  if ! python3 -I "${CHECK}" "$@"; then echo "FAIL ${name}: check $* missed"; FAILS=$((FAILS + 1)); return 1; fi
  return 0
}
pass() { echo "ok   ${1}"; }
fail() { echo "FAIL ${1}"; FAILS=$((FAILS + 1)); }
PERF="${TMP}/ws/campaigns/${SLUG}/performance.csv"
REPORT="${TMP}/ws/campaigns/${SLUG}/report-2026-12-10.md"

# 1. green: complete inputs; hand-computed values; full-file regression lock; drafts; no leak between notes
fresh; run "${WINDOW[@]}"
if expect_exit 0 "green" \
  && assert "green hand values" keys "${PERF}" "${HERE}/expected/key-values.csv" \
  && diff -u "${HERE}/expected/performance.csv" "${PERF}" >"${TMP}/diff" \
  && head -1 "${REPORT}" | grep -q "(complete)" \
  && expect_text "green" "unattributed code FIXH20: 1 order(s), 32.00 USD; owner c-hhhhh8 (status ended)" \
  && expect_text "green" "18 paid store orders in the window, 10 of them creator-tracked" \
  && assert "green test order excluded" value "${PERF}" c-aaaaa1 excluded_detail "test_order:1;refunded:1;not_paid:1;self_referral:1" \
  && grep -q "1 tracked order refunded to nothing, counted with a zero basis" "${PERF}" \
  && expect_text "green" "store promotion code WELCOME10 (programme section 5): 1 order(s)" \
  && ! grep -qi "unattributed code WELCOME10" "${TMP}/out" \
  && ! grep -q "unattributed code WELCOME10" "${TMP}/out" \
  && expect_text "green" "c-iiiii9 (merged into c-aaaaa1)" && ! grep -q "c-iiiii9" "${PERF}" \
  && expect_text "green" "from programme section 5" \
  && assert "green notes stay private" notes "${TMP}/ws/campaigns/${SLUG}/results-notes" "${TMP}/ws/data/creators.csv" \
  && assert "green no email or input text in outputs" nopii "${TMP}/ws/campaigns/${SLUG}"; then pass "green"
else [ -s "${TMP}/diff" ] && head -20 "${TMP}/diff"; fail "green"; fi

# 2. rerun on the same day regenerates an untouched draft; a draft whose marker was deleted is kept
run "${WINDOW[@]}"
grep -v "performance-report draft" "${REPORT}" >"${TMP}/r.md"; echo "OWNER PROSE" >>"${TMP}/r.md"; cp "${TMP}/r.md" "${REPORT}"
run "${WINDOW[@]}"
if expect_exit 0 "rerun keeps written prose" && grep -q "OWNER PROSE" "${REPORT}" && expect_text "rerun keeps written prose" "kept"; then
  pass "rerun keeps written prose"; else fail "rerun keeps written prose"; fi

# 3. a later as-of keeps the earlier performance.csv and compares with it
run --campaign "${SLUG}" --from 2026-11-01 --to 2026-11-30 --as-of 2026-12-11 --prior "campaigns/${SLUG}/performance.csv"
if expect_exit 0 "later run keeps and compares" && [ -f "${TMP}/ws/campaigns/${SLUG}/performance-2026-12-10.csv" ] \
  && grep -q "Prior as of" "${TMP}/ws/campaigns/${SLUG}/report-2026-12-11.md"; then pass "later run keeps and compares"
else fail "later run keeps and compares"; fi

# 4. links were issued but the month's link file is missing: partial, and link-only orders are not counted
fresh; rm "${TMP}/ws/exports/link-attribution-2026-11.csv"; run "${WINDOW[@]}"
if expect_exit 2 "no link file" && expect_text "no link file" "link-only orders" \
  && assert "no link file A" value "${PERF}" c-aaaaa1 tracked_orders 3 && assert "no link file B" value "${PERF}" c-bbbbb2 tracked_orders 3 \
  && head -1 "${REPORT}" | grep -q "(partial)"; then pass "no link file"; else fail "no link file"; fi

# 5. the programme attributes codes only: link files are ignored by rule, and the run is complete
fresh; sed -i.bak 's/every report: code first, link second \[default\]/every report: codes only [owner]/' "${TMP}/ws/program/program.md"; run "${WINDOW[@]}"
if expect_exit 0 "codes only" && assert "codes only A" value "${PERF}" c-aaaaa1 tracked_orders 3; then pass "codes only"; else fail "codes only"; fi

# 6. no costs file: gift cost unknown, partial
fresh; rm "${TMP}/ws/campaigns/${SLUG}/costs.csv"; run "${WINDOW[@]}"
if expect_exit 2 "no costs file" && expect_text "no costs file" "leaves out gift" \
  && assert "no costs file B fee unknown" value "${PERF}" c-bbbbb2 cost_missing "fee;gift" \
  && assert "no costs file B fee not counted" value "${PERF}" c-bbbbb2 cost_fee ""; then pass "no costs file"; else fail "no costs file"; fi

# 7. export without Financial Status: partial, nothing counted as a sale
fresh
python3 -I -c 'import csv,sys
p=sys.argv[1]; rows=list(csv.reader(open(p,newline="")))
i=rows[0].index("Financial Status"); w=csv.writer(open(p,"w",newline=""),lineterminator="\n")
[w.writerow(r[:i]+r[i+1:]) for r in rows]' "${TMP}/ws/exports/orders-2026-11.csv"
run "${WINDOW[@]}"
if expect_exit 2 "no financial status" && expect_text "no financial status" "no Financial Status column" \
  && assert "no financial status A" value "${PERF}" c-aaaaa1 tracked_orders 0; then pass "no financial status"; else fail "no financial status"; fi

# 8. ranking under another declared metric
fresh; run "${WINDOW[@]}" --rank-by tracked_orders --rank-by-source "the campaign plan" --no-drafts
if expect_exit 0 "rank by tracked orders" && assert "rank A" value "${PERF}" c-aaaaa1 rank 1 \
  && assert "rank B" value "${PERF}" c-bbbbb2 rank 2 && assert "rank C" value "${PERF}" c-ccccc3 rank 3 \
  && assert "rank E" value "${PERF}" c-eeeee5 rank 4 && assert "rank D" value "${PERF}" c-ddddd4 rank 5; then pass "rank by tracked orders"; else fail "rank by tracked orders"; fi

# 9. the owner's programme settings: thin floor 3, margin on net revenue, partial refunds in proportion
fresh
sed -i.bak -e 's/called thin \[default 5\]: 5 \[default\]/called thin [default 5]: 3 [owner]/' \
  -e 's/unless this says otherwise. on list price \[owner\]/unless this says otherwise. on net revenue [owner]/' \
  -e 's/refunded share of the order: subtract the full refunded amount \[default\]/refunded share of the order: in proportion [owner]/' \
  "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 0 "owner settings" && assert "thin floor 3, A" value "${PERF}" c-aaaaa1 read ok \
  && assert "thin floor 3, C" value "${PERF}" c-ccccc3 read thin \
  && assert "refund in proportion" value "${PERF}" c-aaaaa1 net_sales 102.70 \
  && assert "margin on net revenue" value "${PERF}" c-aaaaa1 contribution_low_margin 30.21; then pass "owner settings"; else fail "owner settings"; fi

# 10. must fail: the ranking metric line left blank; a metric passed for the run is accepted and named
fresh; sed -i.bak 's/for performance reports \[default cost per tracked order\]: cost per tracked order \[default\]/for performance reports [default cost per tracked order]:/' "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 1 "no ranking metric" && expect_text "no ranking metric" "section 5 has no ranking metric"; then
  run "${WINDOW[@]}" --no-drafts --rank-by net_sales --rank-by-source "the owner"
  if expect_exit 0 "rank metric for one run" && expect_text "rank metric for one run" "rank-by for this run, as declared by the owner"; then
    pass "no ranking metric (must fail), then one run with --rank-by"; else fail "rank metric for one run"; fi
else fail "no ranking metric (must fail)"; fi

# 11. must fail: unknown campaign slug
fresh; run --campaign 2026-11-no-such-campaign --as-of 2026-12-10
if expect_exit 1 "unknown slug" && expect_text "unknown slug" "is not found"; then pass "unknown slug (must fail)"; else fail "unknown slug (must fail)"; fi

# 12. must fail: no commission rate in section 4 while a cpa creator has none on the roster
fresh; sed -i.bak 's/percent of the commission basis: 15 \[owner\]/percent of the commission basis:/' "${TMP}/ws/program/program.md"; run "${WINDOW[@]}"
if expect_exit 1 "no commission rate" && expect_text "no commission rate" "section 4"; then pass "no commission rate (must fail)"; else fail "no commission rate (must fail)"; fi

# 13. must fail: a publications header that differs from the schema
fresh; sed -i.bak '1s/disclosure_seen/disclosure/' "${TMP}/ws/data/publications.csv"; run "${WINDOW[@]}"
if expect_exit 1 "bad publications header" && expect_text "bad publications header" "disclosure_seen"; then pass "bad publications header (must fail)"; else fail "bad publications header (must fail)"; fi

# 14. must fail: a blank commission rate with an unmarked indented instruction under it that carries a number.
# The instruction is template text, never the owner's value, so the rate is missing (lead's rule, 2026-10-20).
fresh
python3 -I -c 'import sys
p=sys.argv[1]; t=open(p).read()
old="percent of the commission basis: 15 [owner]\n"
new="percent of the commission basis:\n  Write a number such as 15; scripts read it as a percent of the commission basis.\n"
assert old in t; open(p,"w").write(t.replace(old,new))' "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 1 "blank rate under an instruction" && expect_text "blank rate under an instruction" "section 4 has no commission rate"; then
  pass "blank rate under an unmarked instruction (must fail)"; else fail "blank rate under an unmarked instruction (must fail)"; fi

# 15. a blank margin band with section 1's real instruction line under it, unmarked: the instruction's words
# "list price" and "net revenue" are not read as a value; the margin is missing and contribution is not computed.
fresh
sed -i.bak -e 's/sets the commission ceiling): 60 to 70 percent \[owner\]/sets the commission ceiling):/' \
  -e 's/unless this says otherwise. on list price \[owner\]/unless this says otherwise./' "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 0 "blank margin under its instruction" && expect_text "blank margin under its instruction" "programme section 1 gross margin band" \
  && assert "no contribution without a margin" value "${PERF}" c-aaaaa1 contribution_low_margin ""; then
  pass "blank margin band under its instruction"; else fail "blank margin band under its instruction"; fi

# 16. the margin band filled, its instruction line left unmarked: the instruction mentions "net revenue" but is template
# text, so the band is read on list price, the pack's reading (A's low contribution stays 22.82).
fresh
sed -i.bak 's/unless this says otherwise. on list price \[owner\]/unless this says otherwise./' "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 0 "unmarked margin instruction" && assert "list price reading" value "${PERF}" c-aaaaa1 contribution_low_margin 22.82; then
  pass "unmarked margin instruction is not a value"; else fail "unmarked margin instruction is not a value"; fi

# 17. a margin band written with a hyphen reads as two positive figures (review 3, F8); a dash with one figure fails
fresh; sed -i.bak 's/sets the commission ceiling): 60 to 70 percent \[owner\]/sets the commission ceiling): 60-70 percent [owner]/' "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 0 "hyphenated margin" && assert "hyphen low" value "${PERF}" c-aaaaa1 contribution_low_margin 22.82 \
  && assert "hyphen high" value "${PERF}" c-aaaaa1 contribution_high_margin 34.62; then
  sed -i.bak 's/sets the commission ceiling): 60-70 percent \[owner\]/sets the commission ceiling): 60- percent [owner]/' "${TMP}/ws/program/program.md"
  run "${WINDOW[@]}" --no-drafts
  if expect_exit 1 "dash with one figure" && expect_text "dash with one figure" "section 1 gross margin band"; then
    pass "hyphenated margin band, and a dash with one figure (must fail)"; else fail "dash with one figure (must fail)"; fi
else fail "hyphenated margin band"; fi

# 18. self-referral: a word inside a sentence keeps the rule on; the whole value "none" turns it off; a blank line
# stops the run naming section 5 (schemas.md section 12)
SR='s/does not earn commission \[default\]: applies \[default\]/does not earn commission [default]: '
fresh; sed -i.bak "${SR}"'the creator earns no commission on their own orders [owner]/' "${TMP}/ws/program/program.md"
run "${WINDOW[@]}" --no-drafts
if expect_exit 0 "self-referral sentence" && assert "rule stays on" value "${PERF}" c-aaaaa1 tracked_orders 4; then
  fresh; sed -i.bak "${SR}"'none [owner]/' "${TMP}/ws/program/program.md"; run "${WINDOW[@]}" --no-drafts
  if expect_exit 0 "self-referral none" && assert "rule off, #1110 counts" value "${PERF}" c-aaaaa1 tracked_orders 5; then
    fresh; sed -i.bak "${SR}"'/' "${TMP}/ws/program/program.md"; run "${WINDOW[@]}" --no-drafts
    if expect_exit 1 "self-referral blank" && expect_text "self-referral blank" "section 5 has no value on the 'Self-referral rule' line"; then
      pass "self-referral whole-value rule, and a blank line (must fail)"; else fail "self-referral blank (must fail)"; fi
  else fail "self-referral none"; fi
else fail "self-referral sentence"; fi

# 19. no link file, but every order in the window carries an active creator's code: no link could have attributed
# one, so the run stays complete (schemas.md section 10)
fresh; rm "${TMP}/ws/exports/link-attribution-2026-11.csv"
run --campaign "${SLUG}" --from 2026-11-04 --to 2026-11-07 --as-of 2026-12-10 --no-drafts
if expect_exit 0 "no link file, every order coded" && expect_text "no link file, every order coded" "every order there carries an active creator's code"; then
  pass "no link file but every order coded stays complete"; else fail "no link file but every order coded stays complete"; fi

echo "${CASES} exit checks run, ${FAILS} failure(s)"
[ "${FAILS}" -eq 0 ]
