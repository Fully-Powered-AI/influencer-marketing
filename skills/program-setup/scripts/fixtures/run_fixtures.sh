#!/usr/bin/env bash
# Fixtures for program-setup's scripts. Exits non-zero on any miss.
# Run from anywhere: bash scripts/fixtures/run_fixtures.sh
set -u

# Physical paths (pwd -P), so a skill installed by symbolic link still finds the pack beside it.
HERE="$(cd "$(dirname "${0}")" && pwd -P)"
SCRIPTS="$(cd "$HERE/.." && pwd -P)"
SKILL="$(cd "$SCRIPTS/.." && pwd -P)"
TEMPLATE="$SKILL/assets/program-template.md"
FILLED="$HERE/filled-program.md"
PACK_SCHEMAS="$SKILL/../../references/schemas.md"
REFERENCE="$SKILL/references/compensation-models.md"
INIT=(python3 -I "$SCRIPTS/init_workspace.py")
COMPARE=(python3 -I "$SCRIPTS/compare_models.py")

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILS=0
pass() { echo "PASS ${1}"; }
miss() { echo "FAIL ${1}"; FAILS=$((FAILS + 1)); }

expect_exit() { # name expected actual
  if [ "${3}" -eq "${2}" ]; then pass "${1} (exit ${3})"; else miss "${1} (expected exit ${2}, got ${3})"; fi
}

workspace_with() { # name source-file -> prints workspace path
  local ws="$WORK/${1}"
  mkdir -p "$ws/program"
  cp "${2}" "$ws/program/program.md"
  echo "$ws"
}

# 1. green: an empty folder becomes the skeleton
WS="$WORK/empty"; mkdir -p "$WS"
"${INIT[@]}" "$WS" > "$WORK/out1" 2>&1; expect_exit "empty folder -> skeleton" 0 $?
for d in program data campaigns codes payouts exports agreements; do
  [ -d "$WS/$d" ] || miss "skeleton folder $d/ missing"
done
cmp -s "$TEMPLATE" "$WS/program/program.md" && pass "program.md is a copy of the template" || miss "program.md differs from the template"
for f in creators pipeline publications; do
  [ "$(wc -l < "$WS/data/$f.csv" | tr -d ' ')" = "1" ] && pass "data/$f.csv is header-only" || miss "data/$f.csv is not header-only"
done

# 2. green: a second run keeps everything and changes nothing
cp -R "$WS" "$WORK/empty-before"
"${INIT[@]}" "$WS" > "$WORK/out2" 2>&1; expect_exit "second run on the same folder" 0 $?
diff -r "$WORK/empty-before" "$WS" > /dev/null && pass "second run changed nothing" || miss "second run changed files"

# 3. must-fail: the unfilled template is not ready
"${INIT[@]}" "$WS" --check > "$WORK/out3" 2>&1; expect_exit "unfilled template --check" 2 $?
grep -q "^Result: partial" "$WORK/out3" && pass "unfilled template reports partial" || miss "unfilled template did not report partial"

# 4. green: a filled sample programme passes, all twelve sections
WS="$(workspace_with filled "$FILLED")"
"${INIT[@]}" "$WS" --check --require all > "$WORK/out4" 2>&1; expect_exit "filled programme --check, all sections" 0 $?

# 5. must-fail: heading 7 missing -> exit 1
WS="$WORK/no7"; mkdir -p "$WS/program"
grep -v '^## 7\. ' "$FILLED" > "$WS/program/program.md"
"${INIT[@]}" "$WS" --check > "$WORK/out5" 2>&1; expect_exit "programme missing heading 7" 1 $?
grep -q "## 7. Approved and forbidden claims' is missing" "$WORK/out5" && pass "missing heading 7 is named" || miss "missing heading 7 not named"

# 6. must-fail: [open] in section 6 -> exit 2, naming section 6
WS="$WORK/open6"; mkdir -p "$WS/program"
sed 's/^\(- Rail chosen: .*\) \[owner\]$/\1 [open]/' "$FILLED" > "$WS/program/program.md"
grep -q '^- Rail chosen: .*\[open\]$' "$WS/program/program.md" || miss "fixture edit for section 6 did not apply"
"${INIT[@]}" "$WS" --check > "$WORK/out6" 2>&1; expect_exit "[open] in section 6" 2 $?
grep -q "^  section 6: open: Rail chosen" "$WORK/out6" && pass "the open section 6 line is named" || miss "the open section 6 line is not named"

# 7. must-fail: an Approved claim marked [observed] -> invalid, exit 2
WS="$WORK/observed7"; mkdir -p "$WS/program"
sed 's/^\(- Canvas Tote: "fixture approved statement one"\) \[owner\]$/\1 [observed]/' "$FILLED" > "$WS/program/program.md"
"${INIT[@]}" "$WS" --check > "$WORK/out7" 2>&1; expect_exit "Approved claim marked [observed]" 2 $?
grep -q "section 7: invalid: Approved: Canvas Tote" "$WORK/out7" && pass "the uncleared claim is flagged invalid" || miss "the uncleared claim was not flagged"

# 8. must-fail: a platform cell outside the allowed values -> exit 2 for section 3
WS="$WORK/badcell3"; mkdir -p "$WS/program"
sed 's/^| tiktok | no |/| tiktok | maybe |/' "$FILLED" > "$WS/program/program.md"
"${INIT[@]}" "$WS" --check --require 3 > "$WORK/out8" 2>&1; expect_exit "section 3 cell 'maybe'" 2 $?

# 9. must-fail: a line with a value and no mark -> unmarked, exit 2
WS="$WORK/unmarked4"; mkdir -p "$WS/program"
sed 's/^\(- Commission rate for .*: 15\) \[owner\]$/\1/' "$FILLED" > "$WS/program/program.md"
"${INIT[@]}" "$WS" --check > "$WORK/out9" 2>&1; expect_exit "section 4 value without a mark" 2 $?
grep -q "section 4: unmarked: Commission rate" "$WORK/out9" && pass "the unmarked line is named" || miss "the unmarked line is not named"

# 10. must-fail: an existing CSV with a wrong header stops before any write
WS="$WORK/badheader"; mkdir -p "$WS/data"
printf 'creator_ref,handle\n' > "$WS/data/creators.csv"
"${INIT[@]}" "$WS" > "$WORK/out10" 2>&1; expect_exit "existing CSV with a wrong header" 1 $?
[ ! -e "$WS/program" ] && pass "nothing was written after the header refusal" || miss "files were written despite the header refusal"
grep -q "missing display_name" "$WORK/out10" && pass "the missing columns are named" || miss "the missing columns are not named"

# 11. green: the worked example in references/compensation-models.md section 7
WS="$WORK/compare"; mkdir -p "$WS"
"${COMPARE[@]}" "$WS" --aov 34.00 --margin 55 65 --discount 15 --commission 15 \
  --flat-fee 300 --hybrid-fee 100 > "$WORK/out11" 2>&1; expect_exit "worked example" 0 $?
while IFS='|' read -r label low high; do
  pattern="$(printf '%s' "$label" | sed 's/[][\.*^$()+?{}|]/\\&/g')"
  if grep -E "^  ${pattern} +${low} +${high}\$" "$WORK/out11" > /dev/null; then pass "script: $label"; else miss "script: $label (expected $low and $high)"; fi
  if grep -F "| ${label} | ${low} | ${high} |" "$REFERENCE" > /dev/null; then pass "reference: $label"; else miss "reference: $label (expected $low and $high)"; fi
done <<'ROWS'
discount given to the customer|5.10|5.10
revenue per order|28.90|28.90
commission basis|28.90|28.90
cost of goods per order|15.30|11.90
commission at the programme rate (cpa and hybrid)|4.34|4.34
contribution per tracked order, cpa or hybrid|9.27|12.67
contribution per tracked order, flat or gift|13.60|17.00
highest commission rate before an order loses money (percent, rounded down)|47.0|58.8
ROWS
grep -q "flat: fixed cost 300.00 (flat fee); tracked orders to cover it: 23 at 55.0 percent, 18 at 65.0 percent" "$WORK/out11" \
  && grep -qF "| flat: tracked orders to cover 300.00 | 23 | 18 |" "$REFERENCE" && pass "flat break-even matches the reference" || miss "flat break-even differs"
grep -q "hybrid: fixed cost 100.00 (hybrid fee); tracked orders to cover it: 11 at 55.0 percent, 8 at 65.0 percent" "$WORK/out11" \
  && grep -qF "| hybrid: tracked orders to cover 100.00 | 11 | 8 |" "$REFERENCE" && pass "hybrid break-even matches the reference" || miss "hybrid break-even differs"

# 12. green: values are read from a filled programme file
WS="$(workspace_with comparefile "$FILLED")"
"${COMPARE[@]}" "$WS" > "$WORK/out12" 2>&1; expect_exit "comparison from the programme file" 0 $?
grep -q "average order value at list price: 41.50 USD \[Measured, programme section 1\]" "$WORK/out12" \
  && pass "section 1 values read with their label" || miss "section 1 values not read"

# 13. must-fail: no margin anywhere -> exit 1 naming section 1
WS="$WORK/nomargin"; mkdir -p "$WS"
"${COMPARE[@]}" "$WS" --aov 34 --discount 15 --commission 15 > "$WORK/out13" 2>&1; expect_exit "comparison without a margin" 1 $?
grep -q "programme section 1" "$WORK/out13" && pass "the missing section is named" || miss "the missing section is not named"

# 14. partial: a requested model without its input -> exit 2, first line says partial
"${COMPARE[@]}" "$WS" --aov 34 --margin 55 65 --discount 15 --commission 15 --models cpa,flat > "$WORK/out14" 2>&1; expect_exit "flat requested without a fee" 2 $?
head -1 "$WORK/out14" | grep -q "^Partial" && pass "partial comparison says so first" || miss "partial comparison does not say so first"

# 15. line shapes the sibling checkers parse (lead's fix round)
shape_case() { # name sed-expression expected-exit require grep-pattern
  local ws="$WORK/shape-${1}"
  mkdir -p "$ws/program"
  sed "${2}" "$FILLED" > "$ws/program/program.md"
  cmp -s "$FILLED" "$ws/program/program.md" && miss "${1}: the fixture edit did not apply"
  "${INIT[@]}" "$ws" --check --require "${4}" > "$WORK/out-${1}" 2>&1; expect_exit "${1}" "${3}" $?
  [ -z "${5}" ] || { grep -q "${5}" "$WORK/out-${1}" && pass "${1}: named" || miss "${1}: not named"; }
}
shape_case approved-unquoted 's/^- Desk Organizer: "fixture approved statement two" \[owner\]$/- Desk Organizer: fixture approved statement two [owner]/' 2 7 "invalid: Approved: Desk Organizer"
shape_case approved-no-product 's/^- Canvas Tote: "fixture approved statement one" \[owner\]$/- "fixture approved statement one" [owner]/' 2 7 "invalid: Approved:"
shape_case no-claim-line '/^- Canvas Tote: "fixture/d; /^- Desk Organizer: "fixture/d; s/^### Approved claims/- No claim is cleared yet; every product statement is ask [owner]\
\
### Approved claims/' 0 7 ""
shape_case no-claim-with-claims 's/^### Approved claims/- No claim is cleared yet; every product statement is ask [owner]\
\
### Approved claims/' 2 7 "invalid: Approved claims"
shape_case forbidden-odd-quote 's/"works with every appliance";/"works with every appliance;/' 2 7 "invalid: Forbidden"
shape_case wording-row-label 's/^  - podcast: "This episode/  - podcasts and newsletters: "This episode/' 2 8 "write the platform as a roster value"
shape_case wording-unquoted 's/^  - instagram: "#ad" at the start/  - instagram: #ad at the start/' 2 8 "invalid: wording line"
shape_case wording-two-quotes 's/spoken: this video is sponsored by Cedar Lane;/spoken: "this video is sponsored by Cedar Lane";/' 2 8 "one straight-quoted wording"
shape_case wording-default-mark 's/^\(  - instagram: .*\) \[owner\]$/\1 [default]/' 2 8 "mark each platform line \[owner\]"
shape_case wording-spoken-no-colon 's/spoken: this video is sponsored by Cedar Lane;/spoken as this video is sponsored by Cedar Lane;/' 2 8 "spoken: <phrase>"
shape_case forbidden-default-mark 's/^\(- Comparisons to a named competitor: the owner has not cleared any\) \[owner\]$/\1 [default]/' 2 7 "take \[owner\] only"
shape_case attribution-as-written 's/^\(- Attribution model, declared once: .*every report:\) a matching code wins; .* \[default\]$/\1 as written [default]/' 2 5 "'as written' is not a value"
shape_case attribution-unreadable 's/^\(- Attribution model, declared once: .*every report:\) a matching code wins; .* \[default\]$/\1 whatever the rail reports [owner]/' 2 5 "code first, then tracked link"
shape_case selfref-as-above 's/^\(- Self-referral rule: .*\[default\]:\) an order placed .* \[default\]$/\1 as above [default]/' 2 5 "'as above' is not a value"
shape_case discount-ambiguous 's/^\(- Customer-facing discount carried by each creator.s code, percent or fixed amount:\) 15 percent \[owner\]$/\1 5.00 off [owner]/' 2 4 "say 'percent' or 'fixed'"
shape_case minimum-missing 's/monthly after the holdback, minimum 25.00 \[owner\]/monthly after the holdback [owner]/' 2 6 "minimum <amount>"
shape_case wording-curly 's/^  - x: "#ad"/  - x: \xe2\x80\x9c#ad\xe2\x80\x9d/' 2 8 "invalid: wording line"
shape_case wording-missing-platform '/^  - newsletter: /d' 2 8 "disclosure line for newsletter"
shape_case conditions-no-colon 's/^| youtube | with conditions: health focus |/| youtube | with conditions health focus |/' 2 3 "invalid: youtube"

# 16. a margin band on net revenue: cost of goods on revenue after the discount (schemas.md section 12)
WS="$WORK/netrevenue"; mkdir -p "$WS/program"
sed 's/^  on list price \[owner\]$/  on net revenue [owner]/' "$FILLED" > "$WS/program/program.md"
"${COMPARE[@]}" "$WS" > "$WORK/out16" 2>&1; expect_exit "margin band on net revenue" 0 $?
grep -Eq "^  cost of goods per order +15.87 +12.35$" "$WORK/out16" && pass "net-revenue cost of goods is 35.275 times (1 minus the margin)" || miss "net-revenue cost of goods wrong"

# 16b. the discount must say percent or fixed (review 1 F3)
WS="$WORK/fixeddiscount"; mkdir -p "$WS/program"
sed 's/^\(- Customer-facing discount carried by each creator.s code, percent or fixed amount:\) 15 percent \[owner\]$/\1 5.00 USD off the order [owner]/' "$FILLED" > "$WS/program/program.md"
"${COMPARE[@]}" "$WS" > "$WORK/out16b" 2>&1; expect_exit "a currency on the discount reads as fixed" 0 $?
grep -q "customer discount: 5.00 per order (fixed amount)" "$WORK/out16b" && pass "5.00 USD read as a fixed amount" || miss "5.00 USD not read as a fixed amount"
WS="$WORK/ambiguousdiscount"; mkdir -p "$WS/program"
sed 's/^\(- Customer-facing discount carried by each creator.s code, percent or fixed amount:\) 15 percent \[owner\]$/\1 5.00 off [owner]/' "$FILLED" > "$WS/program/program.md"
"${COMPARE[@]}" "$WS" > "$WORK/out16c" 2>&1; expect_exit "a discount without percent or fixed" 1 $?

# 16c. a thousands separator stays one number (review 1 F9)
WS="$WORK/thousands"; mkdir -p "$WS/program"
sed 's/^\(- Average order value, store currency, and the date it was measured:\) 41.50 USD/\1 1,234.00 USD/' "$FILLED" > "$WS/program/program.md"
"${COMPARE[@]}" "$WS" > "$WORK/out16d" 2>&1; expect_exit "average order value with a thousands separator" 0 $?
grep -q "average order value at list price: 1234.00 USD" "$WORK/out16d" && pass "1,234.00 read as 1234.00" || miss "1,234.00 misread"

# 17. sibling parsers read the filled fixture (skipped when the sibling is absent)
SIBLINGS="$SKILL/.."
if [ -f "$SIBLINGS/content-approval/scripts/check_caption.py" ] && [ -f "$SIBLINGS/creator-brief/scripts/check_brief.py" ]; then
  python3 -I - "$SIBLINGS" "$FILLED" "$SCRIPTS/programme_file.py" > "$WORK/out17" 2>&1 <<'PY'
import importlib.util, sys
from pathlib import Path
sys.dont_write_bytecode = True
root, program = Path(sys.argv[1]), Path(sys.argv[2]).read_text(encoding="utf-8")
def load(name, path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def section(num):
    out, inside = [], False
    for line in program.splitlines():
        if line.startswith("## "):
            inside = line.startswith(f"## {num}. ")
            continue
        if inside:
            out.append(line)
    return out
cap = load("check_caption", root / "content-approval" / "scripts" / "check_caption.py")
brief = load("check_brief", root / "creator-brief" / "scripts" / "check_brief.py")
# Read the siblings' results by content, so a change in their return shapes does not matter.
seen = {
    "content-approval approved": repr(cap.approved_claims(section(7))),
    "content-approval forbidden": repr(cap.forbidden_phrases(section(7))),
    "content-approval section 8 youtube": repr(cap.disclosure_wordings(section(8), "youtube")),
    "content-approval section 8 podcast": repr(cap.disclosure_wordings(section(8), "podcast")),
    "creator-brief claims": repr(brief.read_claims(section(7))),
}
want = {
    "content-approval approved": ["fixture approved statement one", "fixture approved statement two", "Canvas Tote"],
    "content-approval forbidden": ["works with every appliance", "prevents all damage"],
    "content-approval section 8 youtube": ["'#ad'", "spoken: this video is sponsored by Cedar Lane"],
    "content-approval section 8 podcast": ["This episode is sponsored by Cedar Lane"],
    "creator-brief claims": ["fixture approved statement one", "works with every appliance"],
}
attribution_path = root / "performance-report" / "scripts" / "attribution.py"
if attribution_path.is_file():
    sys.path.insert(0, str(Path(sys.argv[3]).parent))
    import programme_file as pf
    value, _ = pf.field_value(program, 5, "Attribution model")
    report = load("attribution", attribution_path)
    seen["performance-report attribution model"] = repr(report.read_model(pf.MARK_RE.sub("", value).strip(), set()))
    want["performance-report attribution model"] = ["code_then_link"]
problems = [f"{k} lacks {w!r}" for k, ws in want.items() for w in ws if w.lower() not in seen[k].lower()]
print("; ".join(problems) or "content-approval, creator-brief and performance-report read the claims, forbidden phrases, youtube and podcast wording and the attribution model")
sys.exit(1 if problems else 0)
PY
  expect_exit "content-approval and creator-brief parse the filled fixture" 0 $?
  cat "$WORK/out17"
else
  echo "SKIP sibling parsers (content-approval or creator-brief not installed beside this skill)"
fi

# 18. drift: the script's headers and folders match the pack's schemas.md
if [ -f "$PACK_SCHEMAS" ]; then
  python3 -I - "$SCRIPTS/init_workspace.py" "$PACK_SCHEMAS" "$SCRIPTS/programme_file.py" > "$WORK/out15" 2>&1 <<'PY'
import ast, re, sys
values = {}
for path in (sys.argv[1], sys.argv[3]):
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("HEADERS", "FOLDERS", "ROSTER_PLATFORMS"):
                values[node.targets[0].id] = ast.literal_eval(node.value)
schemas = open(sys.argv[2], encoding="utf-8").read()
def columns(heading):
    part = schemas.split(heading, 1)[1].split("\n## ", 1)[0]
    cols = []
    for line in part.splitlines():
        if line.startswith("| `"):
            cols += re.findall(r"`([a-z0-9_]+)`", line.split("|")[1])
    return cols
expected = {
    "data/creators.csv": columns("## 4. `data/creators.csv`"),
    "data/pipeline.csv": columns("## 5. `data/pipeline.csv`"),
    "data/publications.csv": columns("## 6. `data/publications.csv`"),
}
bad = 0
for name, cols in expected.items():
    if values["HEADERS"][name] != cols:
        print(f"header drift in {name}: schemas.md has {cols}")
        bad = 1
layout = schemas.split("```", 2)[1]
folders = sorted({line.split()[0].split("/")[0] for line in layout.splitlines()
                  if line.startswith("  ") and line.split()})
if sorted(values["FOLDERS"]) != folders:
    print(f"folder drift: schemas.md has {folders}")
    bad = 1
row = next(l for l in schemas.splitlines() if l.startswith("| `primary_platform`"))
platforms = re.findall(r"`([a-z]+)`", row.split("|")[3])
if list(values["ROSTER_PLATFORMS"]) != platforms:
    print(f"platform drift: schemas.md section 4 primary_platform has {platforms}")
    bad = 1
sys.exit(bad)
PY
  expect_exit "headers, folders and roster platforms match references/schemas.md" 0 $?
  [ -s "$WORK/out15" ] && cat "$WORK/out15"
else
  echo "SKIP headers and folders against the pack's schemas.md (not found at $PACK_SCHEMAS)"
fi

echo
if [ "$FAILS" -eq 0 ]; then echo "All fixtures passed."; exit 0; fi
echo "$FAILS fixture check(s) failed."; exit 1
