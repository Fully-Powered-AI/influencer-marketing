#!/usr/bin/env bash
# Fixtures for check_brief.py. Run from anywhere: bash scripts/fixtures/run_fixtures.sh
# Exits non-zero if any case gives the wrong exit code, or the right code for the wrong reason.
#
# The fixture workspace (workspace/) holds an invented programme file, roster, code plan, plan,
# agreements and three briefs: c-fx0001 and c-fx0002 are green and form a cohort; c-fx0003 is a
# partial draft for a creator still negotiating. Each must-fail case below is the green brief
# with one edit, made in a temporary folder, so the cases cannot drift from the green brief.
set -u

here="$(cd "$(dirname "${0}")" && pwd)"
check="$here/../check_brief.py"
ws="$here/workspace"
briefs="$ws/campaigns/2026-12-fixture-launch/briefs"
green="$briefs/c-fx0001.md"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
misses=0
runs=0

# mutate SRC DEST OLD NEW: copy SRC to DEST with the first OLD replaced by NEW.
mutate() {
  python3 -I -c '
import sys
src, dest, old, new = sys.argv[1:5]
text = open(src, encoding="utf-8").read()
if old not in text:
    sys.exit("fixture setup: text not found in " + src + ": " + old)
open(dest, "w", encoding="utf-8").write(text.replace(old, new, 1))
' "${1}" "${2}" "${3}" "${4}" || { echo "SETUP FAILED for ${2}"; exit 3; }
}

# progcase NAME CODE PHRASE OLD NEW: a copy of the workspace whose programme file has OLD replaced
# by NEW, checked with the green brief; for programme lines written in another shape.
progcase() {
  local name="${1}" want="${2}" phrase="${3}" old="${4}" new="${5}"
  local dir="$tmp/ws-$(printf '%s' "$name" | tr -c 'a-z0-9' '-')"
  cp -R "$ws" "$dir"
  mutate "$ws/program/program.md" "$dir/program/program.md" "$old" "$new"
  expect "$name" "$want" "$phrase" "$dir" "$dir/campaigns/2026-12-fixture-launch/briefs/c-fx0001.md"
}

# expect NAME CODE PHRASE ARGS...: run the check; the exit code must be CODE and the output
# must contain PHRASE, so a case that fails for some other reason is a miss.
expect() {
  local name="${1}" want="${2}" phrase="${3}"
  shift 3
  local out got
  out="$(python3 -I "$check" "$@" --today 2026-10-20 2>&1)"
  got=$?
  runs=$((runs + 1))
  if [ "$got" != "$want" ]; then
    echo "MISS $name: exit $got, wanted $want"
    printf '%s\n' "$out" | sed 's/^/    /'
    misses=$((misses + 1))
  elif ! printf '%s' "$out" | grep -qF -- "$phrase"; then
    echo "MISS $name: exit $got as wanted, but the output lacks: $phrase"
    printf '%s\n' "$out" | sed 's/^/    /'
    misses=$((misses + 1))
  else
    echo "ok   $name (exit $got)"
  fi
}

# --- the template and the script agree --------------------------------------------------
# The green brief passes the script, so if the template carries the same headings and the
# same fixed sentence under "What you can say", the template matches the script's constants.
runs=$((runs + 1))
if python3 -I -c '
import sys
tpl, brief = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
heads = lambda t: [l for l in t.splitlines() if l.startswith("## ")]
fixed = "Statements about the product stay in these exact words. Everything around them is yours."
sys.exit(0 if heads(tpl) == heads(brief) and fixed in tpl else 1)
' "${here}/../../assets/brief-template.md" "$green"; then
  echo "ok   template headings match the script (via the green brief)"
else
  echo "MISS template headings or fixed sentence differ from the green brief"
  misses=$((misses + 1))
fi

# --- green -------------------------------------------------------------------------------
expect "green single brief" 0 "Result: ready (exit 0)" "$ws" "$green"
expect "green cohort of two" 0 "2 briefs share every common section" \
  "$ws" "$green" "$briefs/c-fx0002.md" --cohort
expect "partial draft says PARTIAL" 2 "Status: PARTIAL, NOT READY TO SEND" "$ws" "$briefs/c-fx0003.md"

# --- must fail: content (exit 2) ---------------------------------------------------------
mutate "$green" "$tmp/uncleared-claim.md" '- Canvas Bag: "Washes off with water."' \
  '- Canvas Bag: "Lasts as long as steel."'
expect "uncleared claim" 2 "is not an Approved [owner] line for Canvas Bag" "$ws" "$tmp/uncleared-claim.md"

mutate "$green" "$tmp/observed-claim.md" '- Canvas Bag: "Washes off with water."' \
  '- Canvas Bag: "Compatible with model A appliances."'
expect "claim marked [observed], not [owner]" 2 "marked [observed], not [owner]" "$ws" "$tmp/observed-claim.md"

mutate "$green" "$tmp/other-product.md" '- Canvas Bag: "Washes off with water."' \
  '- Canvas Bag: "Oil-based."'
expect "claim approved for another product" 2 "approved for another product" "$ws" "$tmp/other-product.md"

mutate "$green" "$tmp/too-many.md" '- Canvas Bag: "Washes off with water."' \
  $'- Canvas Bag: "Washes off with water."\n- Canvas Bag: "Made to stay slick through a long session."\n- Desk Tray: "Oil-based."'
expect "four talking points" 2 "the limit is 3" "$ws" "$tmp/too-many.md"

mutate "$green" "$tmp/wrong-code.md" 'Your code: FIXONE10' 'Your code: FIXTWO10'
expect "wrong code (another creator's)" 2 "the code FIXONE10 from the roster is not in" "$ws" "$tmp/wrong-code.md"

mutate "$green" "$tmp/wrong-discount.md" 'gives your audience 10 percent off' 'gives your audience 20 percent off'
expect "wrong discount" 2 "does not state the discount 10" "$ws" "$tmp/wrong-discount.md"

mutate "$green" "$tmp/wrong-rate.md" 'You earn 15 percent commission' 'You earn 20 percent commission'
expect "wrong commission rate" 2 "commission rate, 15 percent" "$ws" "$tmp/wrong-rate.md"

mutate "$green" "$tmp/forbidden.md" 'woven-canvas Cedar Lane.' 'woven-canvas Cedar Lane, and it protects against STIs.'
expect "forbidden phrase in the why" 2 'forbidden phrase "protects against STIs"' "$ws" "$tmp/forbidden.md"

mutate "$green" "$tmp/no-disclosure.md" 'Wording: "Paid partnership with Cedar Lane"' 'Wording: "#ad"'
expect "disclosure wording missing" 2 'disclosure wording "Paid partnership with Cedar Lane"' "$ws" "$tmp/no-disclosure.md"

mutate "$green" "$tmp/tiktok.md" 'Platform: instagram' 'Platform: tiktok'
expect "platform section 3 says no" 2 "programme section 3 says no organic creator posts on tiktok" "$ws" "$tmp/tiktok.md"

mutate "$green" "$tmp/no-conditions.md" "On Instagram, Cedar Lane's rule for creator posts: health-focused framing only; minimum age 18 set on the post." \
  "On Instagram, keep it tasteful."
expect "section 3 conditions not stated" 2 "conditions for instagram word for word" "$ws" "$tmp/no-conditions.md"

mutate "$green" "$tmp/pending-in-text.md" '- Canvas Bag: "Washes off with water."' \
  $'- Canvas Bag: "Washes off with water."\n\nAlso coming, to be cleared by the owner: it lasts as long as steel.'
expect "pending point in the creator's text" 2 "waiting for the owner is in the creator's text" "$ws" "$tmp/pending-in-text.md"

mutate "$green" "$tmp/dollar.md" 'once it reaches USD 20' "once it reaches $(printf '\044')20"
expect "dollar sign before a digit" 2 "dollar sign before a digit" "$ws" "$tmp/dollar.md"

mutate "$briefs/c-fx0003.md" "$tmp/false-ready.md" 'Status: PARTIAL, NOT READY TO SEND: 5 gaps' \
  "Status: READY TO SEND after the programme lead's read"
expect "status line claims ready on a partial" 2 "the first line says ready" "$ws" "$tmp/false-ready.md"

mutate "$briefs/c-fx0003.md" "$tmp/pay-before-agreed.md" \
  '[MISSING: pay as agreed - from the signed agreement (partnership-agreement)]' 'You earn 15 percent commission.'
expect "pay stated before terms are agreed" 2 "states terms before they are agreed" "$ws" "$tmp/pay-before-agreed.md"

mutate "$briefs/c-fx0002.md" "$tmp/c-fx0002-drift.md" \
  'Get Canvas Bag into the hands of people who have never tried a woven-canvas Cedar Lane.' \
  'Get Canvas Bag to people who like a woven-canvas feel.'
expect "cohort drift" 2 "cohort briefs differ in 'Why we are doing this'" \
  "$ws" "$green" "$tmp/c-fx0002-drift.md" --cohort

mutate "$green" "$tmp/rights-not-granted.md" 'Exclusivity: none in your agreement.' \
  'Exclusivity: no other lubricant brands until 2027-06-30.'
expect "exclusivity stated though none was granted" 2 "which means none was granted" "$ws" "$tmp/rights-not-granted.md"

mutate "$green" "$tmp/turnaround.md" 'We reply within 3 days' 'We reply within 5 days'
expect "approval turnaround differs from section 11" 2 "approval turnaround from programme section 11, 3 days" \
  "$ws" "$tmp/turnaround.md"

cp -R "$ws" "$tmp/ws-dnc"
mutate "$ws/data/creators.csv" "$tmp/ws-dnc/data/creators.csv" '2026-10-15,2026-10-15 fixture row' \
  '2026-10-19,2026-10-19 do not contact'
expect "roster notes say do not contact" 2 "say do not contact" \
  "$tmp/ws-dnc" "$tmp/ws-dnc/campaigns/2026-12-fixture-launch/briefs/c-fx0001.md"

cp -R "$ws" "$tmp/ws-merged"
mutate "$ws/data/creators.csv" "$tmp/ws-merged/data/creators.csv" ',negotiating,cpa,15,,,,none,' \
  ',ended,cpa,15,,FIXONE10,,none,'
mutate "$tmp/ws-merged/data/creators.csv" "$tmp/ws-merged/data/creators.csv" '2026-10-18 fixture row' \
  '2026-10-19 merged into c-fx0001'
expect "green beside a merged duplicate with the same code" 0 "Result: ready (exit 0)" \
  "$tmp/ws-merged" "$tmp/ws-merged/campaigns/2026-12-fixture-launch/briefs/c-fx0001.md"

# --- pay terms and the spoken disclosure (findings round, 2026-10-21) ----------------------
mutate "$green" "$tmp/holdback.md" 'after a 30-day hold' 'after a 14-day hold'
expect "holdback differs from section 5" 2 "holdback from programme section 5, 30 days" "$ws" "$tmp/holdback.md"

mutate "$green" "$tmp/minimum.md" 'once it reaches USD 20' 'once it reaches USD 50'
expect "minimum payout differs from section 6" 2 "minimum payout from programme section 6, 20" "$ws" "$tmp/minimum.md"

progcase "section 6 says no minimum, the brief states one" 2 "does not say 'no minimum'" \
  'monthly after the holdback; minimum USD 20 [owner]' 'monthly after the holdback; no minimum [owner]'
progcase "section 6 payout line in another shape" 2 "without 'minimum <amount>' or 'no minimum'" \
  'monthly after the holdback; minimum USD 20 [owner]' 'monthly after the holdback, at least USD 20 [owner]'

mutate "$green" "$tmp/no-spoken.md" 'In video or audio, say it in these words: this post is a paid partnership with Cedar Lane.' \
  'In video or audio, say it your way.'
expect "spoken disclosure missing" 2 "the spoken disclosure from programme section 8 for instagram" "$ws" "$tmp/no-spoken.md"

# --- a usage window that runs from posting (last round, 2026-10-21) ----------------------
cp -R "$ws" "$tmp/ws-fromposting"
mutate "$ws/data/creators.csv" "$tmp/ws-fromposting/data/creators.csv" \
  ',agreements/c-fx0001-2026-10-15.md,2027-06-30,,2026-12-fixture-launch,2026-10-15,2026-10-15 fixture row' \
  ',agreements/c-fx0001-2026-10-15.md,,,2026-12-fixture-launch,2026-10-15,2026-10-15 fixture row;2026-10-15 programme lead: rights from posting: 6 months'
reshare='Cedar Lane may reshare your post on its own Instagram, website and email until 2027-06-30. Paid reuse, running your post as an ad, is not included.'
mutate "$green" "$tmp/fromposting.md" "$reshare" \
  'Reuse: 6 months from the day you post, on the brand Instagram, website and email; paid reuse is not included.'
expect "window from posting, stated as a duration" 0 "stated as a duration from the day they post" \
  "$tmp/ws-fromposting" "$tmp/fromposting.md"
expect "window from posting, but the brief states a fixed date" 2 "rights from posting: 6 months" \
  "$tmp/ws-fromposting" "$green"
mutate "$tmp/fromposting.md" "$tmp/fromposting-3.md" 'Reuse: 6 months' 'Reuse: 3 months'
expect "window from posting, wrong duration" 2 "must say \"Reuse: 6 months from the day you post" \
  "$tmp/ws-fromposting" "$tmp/fromposting-3.md"
cp -R "$tmp/ws-fromposting" "$tmp/ws-fromposting-live"
printf '%s\n' 'publication_id,campaign_slug,creator_ref,platform,post_url,posted_at,format,disclosure_seen,disclosure_form,code_in_post,link_in_post,approval_id,check_day1,check_day7,check_day30,rights_until,notes' \
  'p-fx0001,2026-12-fixture-launch,c-fx0001,instagram,https://www.instagram.example.com/p/fixture,2026-12-01T18:00Z,reel,yes,caption;spoken;platform_tool,FIXONE10,,2026-12-fixture-launch--c-fx0001--1,live,not_checked,not_checked,2027-06-01,2026-12-01 fixture post' \
  > "$tmp/ws-fromposting-live/data/publications.csv"
mutate "$green" "$tmp/fromposting-live.md" 'until 2027-06-30' 'until 2027-06-01'
expect "window from posting, post live, brief states its computed date" 0 "computed date 2027-06-01" \
  "$tmp/ws-fromposting-live" "$tmp/fromposting-live.md"

# --- programme lines in another shape are findings, never read loosely ---------------------
progcase "Approved line in typographic quotes" 2 "is not in the shape - <product>" \
  '- Canvas Bag: "Washes off with water." [owner]' '- Canvas Bag: “Washes off with water.” [owner]'
progcase "Approved line written wording-then-product" 2 "is not in the shape - <product>" \
  '- Canvas Bag: "Washes off with water." [owner]' '- "Washes off with water." (Canvas Bag) [owner]'
progcase "Approved line with two wordings" 2 "is not in the shape - <product>" \
  '- Canvas Bag: "Washes off with water." [owner]' '- Canvas Bag: "Washes off with water." "Rinses clean." [owner]'
progcase "Forbidden phrase in typographic quotes" 2 "only phrases in straight double quotes are read" \
  'for example "protects against STIs"' 'for example “protects against STIs”'
progcase "two section 8 lines for the platform" 2 "has 2 lines for instagram" \
  '  - all: "Ad"' '  - instagram: "Ad" in the caption [owner]
  - all: "Ad"'

mutate "$green" "$tmp/brief-claim-shape.md" '- Canvas Bag: "Cotton canvas."' '- Canvas Bag: “Cotton canvas.”'
expect "brief claim line in typographic quotes" 2 "is not a claim line in the shape" "$ws" "$tmp/brief-claim-shape.md"

# --- must fail: bad input (exit 1) -------------------------------------------------------
mutate "$green" "$tmp/no-approval.md" '## Approval' '## Review'
expect "missing section heading" 1 "missing: Approval" "$ws" "$tmp/no-approval.md"

mutate "$green" "$tmp/placeholder.md" 'Hello Fixture Creator One,' 'Hello {{display_name}},'
expect "template placeholder left in" 1 "still carries template guidance" "$ws" "$tmp/placeholder.md"

mutate "$green" "$tmp/unknown-creator.md" 'Creator: c-fx0001' 'Creator: c-zz9999'
expect "creator not in the roster" 1 "no row for c-zz9999" "$ws" "$tmp/unknown-creator.md"

expect "brief for a merged-away row" 1 "was merged into c-fx0001" \
  "$tmp/ws-merged" "$tmp/ws-merged/campaigns/2026-12-fixture-launch/briefs/c-fx0003.md"

cp -R "$ws" "$tmp/ws-no7"
python3 -I -c '
import re, sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
t2 = re.sub(r"## 7\..*?(?=## 8\.)", "", t, flags=re.S)
if t2 == t:
    sys.exit("fixture setup: section 7 not found")
open(p, "w", encoding="utf-8").write(t2)
' "$tmp/ws-no7/program/program.md" || { echo "SETUP FAILED for ws-no7"; exit 3; }
expect "programme without section 7" 1 "has no section 7" \
  "$tmp/ws-no7" "$tmp/ws-no7/campaigns/2026-12-fixture-launch/briefs/c-fx0001.md"

cp -R "$ws" "$tmp/ws-badroster"
mutate "$ws/data/creators.csv" "$tmp/ws-badroster/data/creators.csv" ',code,affiliate_link,' ',promo_code,affiliate_link,'
expect "roster header differs from schemas.md" 1 "header that differs from schemas.md" \
  "$tmp/ws-badroster" "$tmp/ws-badroster/campaigns/2026-12-fixture-launch/briefs/c-fx0001.md"

progcase "section 8 line for the platform in another shape" 1 "a line for it exists but in another shape" \
  '  - instagram: "Paid partnership with Cedar Lane"' '  - instagram: “Paid partnership with Cedar Lane”'
progcase "section 8 'all' line does not count for the platform" 1 "has no disclosure line for instagram" \
  '  - instagram: "Paid' '  - all: "Paid'
progcase "section 8 wording on the field line, not indented" 1 "has no disclosure line for instagram" \
  'switched on in addition): [owner]
  - instagram: "Paid partnership with Cedar Lane"' 'switched on in addition): instagram "Paid partnership with Cedar Lane" [owner]
  - youtube-only: "Paid partnership with Cedar Lane"'

cp -R "$ws" "$tmp/ws-no8line"
mutate "$ws/program/program.md" "$tmp/ws-no8line/program/program.md" '  - instagram: "Paid' '  - facebook: "Paid'
expect "section 8 has no line for the platform" 1 "has no disclosure line for instagram" \
  "$tmp/ws-no8line" "$tmp/ws-no8line/campaigns/2026-12-fixture-launch/briefs/c-fx0001.md"

echo
if [ "$misses" -eq 0 ]; then
  echo "all $runs fixture cases behaved as expected"
  exit 0
fi
echo "$misses of $runs fixture cases missed"
exit 1
