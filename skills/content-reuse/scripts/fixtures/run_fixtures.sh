#!/usr/bin/env bash
# Runs every fixture of scripts/rights_check.py on a throwaway copy of its workspace.
# Each case states the exit code it must give and lines that must (or, prefixed NOT, must not)
# appear in the script's output or the inventory it writes. Exits 1 on any miss.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../rights_check.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SLUG="2026-11-fixture-launch"
misses=0

# run_case <case folder> <expected exit> <needles, one per line> -- <script arguments after the workspace>
run_case() {
  local name="${1}" want="${2}" needles="${3}"
  shift 4
  local ws="$TMP/$name"
  cp -R "$HERE/$name" "$ws"
  local out code
  out="$(python3 -I "$SCRIPT" "$ws" "$@" 2>&1)"
  code=$?
  local seen="$out"
  if [ -f "$ws/campaigns/$SLUG/reuse/inventory.csv" ]; then
    seen="$seen
$(cat "$ws/campaigns/$SLUG/reuse/inventory.csv")"
  fi
  local ok=1
  if [ "$code" != "$want" ]; then
    echo "MISS $name: exit $code, expected $want"
    ok=0
  fi
  while IFS= read -r needle; do
    [ -z "$needle" ] && continue
    case "$needle" in
      NOT\ *)
        if printf '%s\n' "$seen" | grep -qF -- "${needle#NOT }"; then
          echo "MISS $name: found '${needle#NOT }', which must not appear"; ok=0
        fi ;;
      *)
        if ! printf '%s\n' "$seen" | grep -qF -- "$needle"; then
          echo "MISS $name: '$needle' not found"; ok=0
        fi ;;
    esac
  done <<< "$needles"
  if [ "$ok" = 1 ]; then
    echo "ok   $name (exit $code)"
  else
    misses=$((misses + 1))
    printf '%s\n' "$out" | sed 's/^/     | /'
  fi
}

run_case green 0 "p-aaaaaa c-aaaaaa instagram reel: active until 2027-05-01
paid-with-conditions:instagram
every requested asset may be reused
plan check: plan-2026-12-01.md, 2 placement rows, 0 failing
code-in-asset:FIXTURE15
channels-from-agreement:product-page+email+brand-social
paid-platform-not-allowed-by-section-3:tiktok
brand channels (programme section 3): product-page by channel publisher; email by channel publisher; brand-social by channel publisher; retail-deck by programme lead
suggested product-page;email;brand-social;paid-with-conditions:instagram
result: complete
NOT suggested product-page;email;brand-social;retail-deck
NOT paid-with-conditions:tiktok" -- --campaign "$SLUG" --as-of 2026-12-01 --asset p-aaaaaa \
  --check-plan "campaigns/$SLUG/reuse/plan-2026-12-01.md"

run_case expiring 0 "p-bbbbbb c-bbbbbb instagram reel: expiring until 2026-12-20
days-left:19
disclosure-not-in-asset
channels-not-stated
paid reuse no
p-bbbbbb on email (fixture newsletter still): take down by 2026-12-20
product-page;email;brand-social;retail-deck
NOT paid:
NOT paid-with-conditions" -- --campaign "$SLUG" --as-of 2026-12-01 --asset p-bbbbbb

run_case expired 2 "p-cccccc: refused (rights expired
p-dddddd: refused (rights unknown (no-written-agreement)
p-ffffff: refused (rights not-granted
no-rights-granted
p-gggggg c-gggggg instagram reel: unknown (creator-merged-into:c-cccccc)
p-ffffff c-ffffff instagram reel: not-granted (no-rights-granted) until none granted
4 rows counted, 1 merged duplicates not counted
p-eeeeee c-eeeeee instagram reel: active until 2027-03-01; paid reuse unknown; holds disclosure-missing; suggested none
result: partial
p-cccccc,c-cccccc,reel,instagram,2026-11-15,expired,2026-12-01,unknown,A1,none,none
paid-reuse-not-stated" -- --campaign "$SLUG" --as-of 2026-12-01 \
  --asset p-cccccc --asset p-dddddd --asset p-ffffff

run_case bad-plan 2 "ends after rights end (2027-06-01 is after 2027-05-01)
channel 'retail-deck' is not allowed for this asset
section 7 changed on 2026-11-20
credit and disclosure line is empty or open
'code shown' must be yes or no
a paid row is the owner's decision
a cut of type other needs a new content-approval record
owner_role 'programme lead' does not publish on product-page
reapproval-needed-after:2026-11-20
planned end is after the rights end 2027-05-01" -- --campaign "$SLUG" --as-of 2026-12-01 \
  --check-plan "campaigns/$SLUG/reuse/plan-2026-12-01.md"

run_case bad-header 1 "header does not match the pack schema (missing rights_until)" -- --campaign "$SLUG" --as-of 2026-12-01

run_case no-channels 1 "the brand's own channels line lists no channel" -- --campaign "$SLUG" --as-of 2026-12-01

run_case none-cleared 0 "claims: programme section 7 records that no claim is cleared yet
p-aaaaaa,c-aaaaaa,reel,instagram,2027-05-01,active,2026-12-01,no,none,product-page;email;brand-social;retail-deck,none
p-hhhhhh c-hhhhhh instagram reel: active until 2027-05-01; paid reuse no; holds product-statement-without-cleared-claim; suggested none
every requested asset may be reused" -- --campaign "$SLUG" --as-of 2026-12-01 --asset p-aaaaaa

run_case from-posting 0 "p-iiiiii c-iiiiii instagram reel: active until 2027-05-08
rights-from-posting:6-months
p-jjjjjj c-jjjjjj instagram reel: unknown (rights-from-posting-undated)
p-kkkkkk c-kkkkkk instagram reel: active until 2027-05-08
NOT not-granted (no-rights-granted)
NOT rights-mismatch" -- --campaign "$SLUG" --as-of 2026-12-01 --asset p-iiiiii --asset p-kkkkkk

run_case no-claims 1 "Programme section 7 lists no approved claim marked [owner] and does not record that no claim is cleared yet" -- --campaign "$SLUG" --as-of 2026-12-01

if [ "$misses" -gt 0 ]; then
  echo "fixtures: $misses case(s) missed"
  exit 1
fi
echo "fixtures: all cases passed"
exit 0
