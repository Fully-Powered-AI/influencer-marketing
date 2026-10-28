#!/usr/bin/env bash
# Runs every fixture case for longlist_check.py on a temporary copy of its
# workspace and exits non-zero if any exit code or expected line is missed,
# or if a line listed in the case's reject.txt appears.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../longlist_check.py"
misses=0
total=0

# case | expected exit | longlist argument | extra flag
CASES=(
  "green|0|data/longlist-2026-10-20.csv|"
  "flagged|2|data/longlist-2026-10-20.csv|"
  "bad-header|1|data/longlist-2026-10-20.csv|"
  "no-program|1|data/longlist-2026-10-20.csv|"
  "no-section-3|1|data/longlist-2026-10-20.csv|"
  "bad-name|1|data/longlist.csv|"
  "roster-bad|2|data/longlist-2026-10-20.csv|"
  "sort|0|data/longlist-2026-10-20.csv|--sort"
  "roster-merged|2|data/longlist-2026-10-20.csv|"
)

for spec in "${CASES[@]}"; do
  IFS='|' read -r name expected longlist flag <<< "$spec"
  total=$((total + 1))
  tmp="$(mktemp -d)"
  cp -R "$HERE/$name/workspace" "$tmp/workspace"
  if [ -n "$flag" ]; then
    output="$(python3 -I "$SCRIPT" "$tmp/workspace" "$longlist" "$flag" 2>&1)"
  else
    output="$(python3 -I "$SCRIPT" "$tmp/workspace" "$longlist" 2>&1)"
  fi
  code=$?
  ok=1
  if [ "$code" != "$expected" ]; then
    echo "MISS $name: exit $code, expected $expected"
    ok=0
  fi
  while IFS= read -r want; do
    [ -z "$want" ] && continue
    if ! printf '%s\n' "$output" | grep -qF -- "$want"; then
      echo "MISS $name: output lacks: $want"
      ok=0
    fi
  done < "$HERE/$name/expect.txt"
  if [ -f "$HERE/$name/reject.txt" ]; then
    while IFS= read -r unwanted; do
      [ -z "$unwanted" ] && continue
      if printf '%s\n' "$output" | grep -qF -- "$unwanted"; then
        echo "MISS $name: output should not contain: $unwanted"
        ok=0
      fi
    done < "$HERE/$name/reject.txt"
  fi
  if [ "$name" = "sort" ]; then
    if ! diff -q "$tmp/workspace/$longlist" "$HERE/sort/expected-sorted.csv" > /dev/null; then
      echo "MISS sort: the sorted file differs from sort/expected-sorted.csv"
      ok=0
    fi
  fi
  if [ "$ok" = 1 ]; then
    echo "ok   $name (exit $code)"
  else
    misses=$((misses + 1))
    printf '%s\n' "$output" | sed 's/^/     | /'
  fi
  rm -rf "$tmp"
done

echo "fixtures: $((total - misses)) of $total passed"
[ "$misses" = 0 ]
