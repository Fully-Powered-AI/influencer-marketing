#!/usr/bin/env bash
# Fixtures for plan_budget.py and check_plan.py. Each case copies the fixture workspace to a
# temporary folder, may edit one file, runs one script, and compares the exit code and, where
# given, a text the output or a file must contain. Exits non-zero if any case misses.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "$HERE/.." && pwd)"
SLUG=2026-12-holiday-tote
TMP="$(mktemp -d "${TMPDIR:-/tmp}/campaign-plan-fixtures.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

fresh() { rm -rf "$TMP/ws"; cp -R "$HERE/ws" "$TMP/ws"; }
# edit FILE OLD NEW: replace one exact text in a file (fails the case if absent)
edit() { python3 -I - "${1}" "${2}" "${3}" <<'PY'
import sys, pathlib
p, old, new = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
t = p.read_text(encoding="utf-8")
if old not in t:
    sys.exit(f"edit: text not found in {p}: {old}")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
PY
}
budget() { python3 -I "$SCRIPTS/plan_budget.py" "$TMP/ws" --campaign "$SLUG" --assumptions "$TMP/ws/campaigns/$SLUG/assumptions.csv" "$@"; }
full() { budget --shortlist "$TMP/ws/data/shortlist-2026-10-18.csv" --window 2026-12-01 2026-12-31 --rail-fee-pct 0 --rail-fee-basis commission "$@"; }
check() { python3 -I "$SCRIPTS/check_plan.py" "$TMP/ws" --campaign "$SLUG"; }

# expect NAME CODE PATTERN COMMAND...: PATTERN (may be empty) must appear in the output
expect() {
  local name="${1}" want="${2}" pattern="${3}"; shift 3
  local out code
  out="$("$@" 2>&1)"; code=$?
  if [ "$code" -ne "$want" ]; then
    echo "MISS $name: exit $code, wanted $want"; echo "$out" | tail -5; fail=$((fail+1)); return
  fi
  if [ -n "$pattern" ] && ! printf '%s' "$out" | grep -qF -- "$pattern"; then
    echo "MISS $name: output lacks: $pattern"; echo "$out" | tail -5; fail=$((fail+1)); return
  fi
  echo "ok   $name (exit $code)"; pass=$((pass+1))
}
# expect_file NAME FILE PATTERN: the file must contain PATTERN
expect_file() {
  if grep -qF -- "${3}" "${2}"; then echo "ok   ${1}"; pass=$((pass+1)); else echo "MISS ${1}: ${2} lacks: ${3}"; fail=$((fail+1)); fi
}

B="$TMP/ws/campaigns/$SLUG/budget.csv"
P="$TMP/ws/campaigns/$SLUG/plan.md"
PROG="$TMP/ws/program/program.md"

# ---- green: full run, hand-computed rows, then the checker passes
fresh
expect "green: budget complete" 0 "Result: complete." full --sale-pct 20
# schemas.md section 12 by hand, micro cpa base: AOV 40.00; revenue per order 40 x 0.85 = 34.00;
# commission 0.15 x 34 = 5.10; cost of goods 40 x 0.45 = 18.00 (low margin) or 14.00 (high);
# contribution per order 10.90 or 14.90. 20 orders: revenue 680, discount 120, commission 102,
# gifts 4 x 6.50 = 26; programme cost 248; per order 12.40; return 680 / 248 = 2.74;
# contribution 20 x 10.90 - 26 = 192.00 and 20 x 14.90 - 26 = 272.00
expect_file "green: micro base row" "$B" "$SLUG,base,micro,cpa,4,20.00,user,680.00,680.00,120.00,102.00,0.00,26.00,0.00,248.00,12.40,2.74,192.00,272.00,Estimated"
# conservative halves orders, keeps gifts: 10 orders, cost 60 + 51 + 26 = 137
expect_file "green: micro conservative row" "$B" "$SLUG,conservative,micro,cpa,4,10.00,user,340.00,340.00,60.00,51.00,0.00,26.00,0.00,137.00,13.70,2.48,83.00,123.00,Estimated"
# sale of 20 percent first: basket 32.00, code 4.80, revenue 27.20, commission 4.08;
# contribution per order 27.20 - 18.00 - 4.08 = 5.12, times 20, less 26 = 76.40
expect_file "green: micro sale row" "$B" "$SLUG,sale,micro,cpa,4,20.00,user,544.00,544.00,96.00,81.60,0.00,26.00,0.00,203.60,10.18,2.67,76.40,156.40,Estimated"
# hybrid fee 150 over contribution per order 10.90 = 13.8, up to 14; over 14.90 = 10.1, up to 11
expect_file "green: fee break-even, section 12 rule" "$P" "breaks even at 14 tracked orders per creator at the low margin and 11 at the high margin"
expect_file "green: thin read flagged from section 5" "$P" "below the 5 at which programme section 5 calls a creator's read thin"
expect_file "green: codes end with the window" "$P" "| 2026-12-31 | creator codes end with the window"
expect_file "green: fee flag names section 4 rule" "$P" "hybrid only for mid tier and above, the owner approves each one"
expect_file "green: holdback date" "$P" "| 2027-01-30 | the last order in the window clears its holdback"
expect_file "green: rights date" "$P" "| 2027-06-30 | reuse rights end for a post made on the last window day"
# shortlist per schemas.md section 8: the tier column wins over the follower band, and the
# disagreement is flagged. Nano: A, B, F, H engage plus E (podcast) engage = 5; C, D negotiate = 2;
# G on tiktok not cleared = 1; planned 6.
expect_file "green: supply uses the tier column" "$P" "| nano | 5 | 2 | 1 | 6 |"
expect_file "green: tier disagreement flagged" "$P" "1 engage or negotiate rows in the shortlist carry a tier that differs from their follower band"
expect "green: plan passes the check" 0 "Result: pass." check

# lead time counted from --as-of; a window that opens on or before it is flagged
fresh
expect "lead time from --as-of" 0 "Lead time: 42 calendar days from the plan's date (2026-10-20" full --as-of 2026-10-20
fresh
expect "negative lead time flagged" 0 "on or before the plan's date (2027-01-15): the lead time is -45 days" full --as-of 2027-01-15

# section 4 says codes do not combine: the sale case is flagged as something the store will not allow
fresh
edit "$PROG" "and which ones: automatic discounts and free shipping, not other codes [owner]" "and which ones: no, never [owner]"
expect "sale case against a no-stacking rule is flagged" 0 "would not stack" full --sale-pct 20

# rail fee as a percent of commission: micro base 20 orders x 5.10 x 2.9 percent = 2.958
fresh
expect "rail fee on commission" 0 "" budget --shortlist "$TMP/ws/data/shortlist-2026-10-18.csv" --window 2026-12-01 2026-12-31 --rail-fee-pct 2.9 --rail-fee-basis commission
expect_file "rail fee rounded into the row" "$B" "$SLUG,base,micro,cpa,4,20.00,user,680.00,680.00,120.00,102.00,0.00,26.00,2.96,250.96,12.55,2.71,189.04,269.04,Estimated"

# a before-discounts basis (programme section 4): commission and the return use the 40.00 basket
fresh
edit "$PROG" "or another: subtotal after discounts, before shipping and tax [default]" "or another: subtotal before discounts [owner]"
expect "before-discounts basis" 0 "" full
expect_file "commission on the list basket" "$B" "$SLUG,base,micro,cpa,4,20.00,user,680.00,800.00,120.00,120.00,0.00,26.00,0.00,266.00,13.30,3.01,"

# re-running with changed assumptions keeps the earlier budget.csv under a superseded name
edit "$TMP/ws/campaigns/$SLUG/assumptions.csv" "micro,4,5" "micro,4,6"
expect "re-run supersedes, never deletes" 0 "kept it as budget-superseded-" budget --shortlist "$TMP/ws/data/shortlist-2026-10-18.csv" --window 2026-12-01 2026-12-31 --rail-fee-pct 2.9 --rail-fee-basis commission

# ---- partial runs: exit 2, and the checker then wants a partial title
fresh
expect "partial: no rail fee" 2 "rail fees not included" budget --shortlist "$TMP/ws/data/shortlist-2026-10-18.csv" --window 2026-12-01 2026-12-31
expect "partial block needs a partial title" 1 "title's status must be (partial)" check
fresh
expect "partial: no window" 2 "dates not computed (no --window given)" budget --shortlist "$TMP/ws/data/shortlist-2026-10-18.csv" --rail-fee-pct 0 --rail-fee-basis sales

# ---- must fail: programme and assumptions problems, exit 1 naming what to fix
fresh
edit "$PROG" "percent of the commission basis: 15 percent [owner]" "percent of the commission basis: [open]"
expect "must fail: commission rate open" 1 "Programme section 4: 'commission rate' is blank, [open] or a placeholder" full
fresh
edit "$PROG" "or another: subtotal after discounts, before shipping and tax [default]" "or another: as written [default]"
expect "must fail: commission basis 'as written'" 1 "Programme section 4: 'commission basis' is blank, [open] or a placeholder such as 'as written'" full
fresh
edit "$PROG" "and who approves one (role): hybrid only for mid tier and above, the owner approves each one [owner]" "and who approves one (role):"
expect "must fail: fee row without the section 4 rule" 1 "Programme section 4: 'when a flat or hybrid deal is allowed" full
# a blank value above an unmarked indented instruction stays blank: the instruction is template text
fresh
edit "$PROG" "it sets the commission ceiling): 55 to 65 percent [owner]" "it sets the commission ceiling):"
expect "must fail: blank margin under an indented instruction" 1 "Programme section 1: 'gross margin band' is blank" full
# a marked indented line is part of the value: on list price is fine, on net revenue stops the budget
fresh
edit "$PROG" "  State whether the band is on list price" "  - on list price [owner]
  State whether the band is on list price"
expect "marked indented line read: list price" 0 "Result: complete." full
fresh
edit "$PROG" "  State whether the band is on list price" "  - on net revenue [owner]
  State whether the band is on list price"
expect "must fail: margin band stated on net revenue" 1 "states the gross margin band on net revenue" full
fresh
edit "$PROG" "and the date it was measured: 40.00 USD, measured 2026-09-30 [observed]" "and the date it was measured:"
expect "must fail: no average order value" 1 "Programme section 1: 'average order value' is blank" full

# the attribution value is the sentence after the template's tail; "as written" or blank is missing
fresh; full >/dev/null 2>&1
edit "$PROG" "Changes here change every report: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]" "Changes here change every report: as written [default]"
expect "check must fail: attribution 'as written'" 1 "Programme section 5: the attribution model is blank, [open] or a placeholder" check
fresh; full >/dev/null 2>&1
edit "$PROG" "Changes here change every report: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]" "Changes here change every report:"
expect "check must fail: attribution blank after the template text" 1 "Programme section 5: the attribution model is blank, [open] or a placeholder" check
fresh; full >/dev/null 2>&1
edit "$P" "Attribution model: a matching code wins" "Attribution model: A matching code wins"
expect "check must fail: attribution copy not verbatim" 1 "copy the sentence verbatim" check
fresh
edit "$TMP/ws/campaigns/$SLUG/assumptions.csv" "screenshot in exports/)" "" 
edit "$TMP/ws/campaigns/$SLUG/assumptions.csv" "the creator's own code results from a 2026-06 campaign with another brand (" ""
expect "must fail: estimate without its basis" 1 "an estimate needs its basis named" full
fresh
edit "$TMP/ws/campaigns/$SLUG/assumptions.csv" "nano,6,2,user,0,1,6.50,cpa" "tiny,6,2,user,0,1,6.50,cpa"
expect "must fail: unknown tier" 1 "tier 'tiny' is not one of nano, micro, mid, macro" full
fresh
edit "$TMP/ws/campaigns/$SLUG/assumptions.csv" "nano,6,2,user,0,1,6.50,cpa" "nano,6,,user,0,1,6.50,cpa"
expect "must fail: no orders figure" 1 "the script does not supply one" full
fresh
edit "$TMP/ws/campaigns/$SLUG/assumptions.csv" "gift_unit_cost,compensation,basis" "gift_unit_cost,basis,compensation"
expect "must fail: header out of order" 1 "the header must be" full
fresh
expect "must fail: bad slug" 1 "is not a campaign slug" python3 -I "$SCRIPTS/plan_budget.py" "$TMP/ws" --campaign holiday-2026 --assumptions "$TMP/ws/campaigns/$SLUG/assumptions.csv"
fresh
edit "$P" "# Campaign plan: $SLUG (draft)" "# Campaign plan: $SLUG (approved 2026-10-25)"
expect "must fail: approved plan is not rewritten" 1 "will not change an approved plan's budget" full

# ---- checker must-fail cases, each on a plan the green run filled
fresh; full >/dev/null 2>&1
edit "$P" "| mid | hybrid | 1 | youtube |" "| mid | hybrid | 1 | tiktok |"
expect "check must fail: platform section 3 rules no" 1 "rules 'no' for organic creator posts on tiktok" check
fresh; full >/dev/null 2>&1
edit "$P" "| nano | cpa | 6 |" "| nano | cpa | 7 |"
expect "check must fail: mix differs from budget.csv" 1 "differ from budget.csv's base case" check
fresh; full >/dev/null 2>&1
edit "$P" "Status: complete" "Status: complete, checked"
expect "check must fail: block edited by hand" 1 "was edited by hand" check
fresh; full >/dev/null 2>&1
edit "$P" "## 7. Risks and contingencies" "## 7. Risks"
expect "check must fail: heading missing" 1 "Missing heading(s): ## 7. Risks and contingencies" check
fresh; full >/dev/null 2>&1
edit "$P" "| mid | hybrid | 1 | youtube | c-ab12cd | pending |" "| mid | hybrid | 1 | youtube | c-ab12cd | not needed |"
expect "check must fail: fee row without owner approval" 1 "needs the owner's approval entry" check
fresh; full >/dev/null 2>&1
edit "$P" "Attribution model: a matching code wins" "Attribution model: any code wins"
expect "check must fail: attribution not copied" 1 "differs from programme section 5" check
fresh; full >/dev/null 2>&1
edit "$P" "Ranking metric: cost per tracked order" "Ranking metric: reach"
expect "check must fail: ranking metric not copied" 1 "ranking-metric line differs from programme section 5" check
fresh; full >/dev/null 2>&1
edit "$P" "| R9 | sale overlap |" "| R10 | sale overlap |"
expect "check must fail: risk R9 missing" 1 "Section 7 lacks risk R9" check

# a plan copied from the template and never filled fails on its placeholders
fresh
sed "s/<campaign_slug>/$SLUG/" "$SCRIPTS/../assets/plan-template.md" > "$P"
full >/dev/null 2>&1
expect "check must fail: template placeholders left" 1 "still holds a template placeholder" check

# a check that cannot run is reported as skipped, never as passed
fresh; full >/dev/null 2>&1
rm "$B"
expect "check partial: no budget.csv" 2 "skipped: mix against budget.csv" check

echo "fixtures: $pass passed, $fail missed"
[ "$fail" -eq 0 ]
