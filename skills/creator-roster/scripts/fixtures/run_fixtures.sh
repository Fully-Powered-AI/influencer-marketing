#!/usr/bin/env bash
# Runs every fixture for scripts/roster.py on copies of the sample workspace.
# Exits non-zero if any case misses. Standard tools only: bash, python3, grep, cmp.
set -u
HERE="$(cd "$(dirname "${0}")" && pwd)"
SKILL="$(cd "$HERE/../.." && pwd)"
ROSTER="$SKILL/scripts/roster.py"
TOOLS="$HERE/fixture_tools.py"
IN="$HERE/inputs"
EXP="$HERE/expected"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/roster-fixtures.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
fail=0
WS="$TMP/ws"
OUT="$TMP/out.txt"
ROLE="programme lead"

fresh() { rm -rf "$WS"; cp -R "$HERE/workspace" "$WS"; }
roster() { python3 -I "$ROSTER" "$WS" "$@" > "$OUT" 2>&1; echo $?; }
tool() { python3 -I "$TOOLS" "$@"; }
ok() { pass=$((pass + 1)); echo "ok    ${1}"; }
miss() { fail=$((fail + 1)); echo "MISS  ${1}: ${2}"; sed 's/^/        | /' "$OUT" | head -n 40; }
expect_exit() { # name expected actual
  if [ "${3}" = "${2}" ]; then ok "${1}"; else miss "${1}" "exit ${3}, expected ${2}"; fi
}
expect_text() { # name text
  if grep -qF -- "${2}" "$OUT"; then ok "${1}"; else miss "${1}" "output lacks: ${2}"; fi
}
expect_eq() { # name expected actual
  if [ "${3}" = "${2}" ]; then ok "${1}"; else miss "${1}" "got '${3}', expected '${2}'"; fi
}
snapshot() { cat "$WS"/data/*.csv > "$TMP/snap"; }
unchanged() { cat "$WS"/data/*.csv > "$TMP/snap2"; if cmp -s "$TMP/snap" "$TMP/snap2"; then ok "${1}"; else miss "${1}" "the CSVs changed"; fi; }

echo "== schema and rules"
fresh
e=$(roster schema); expect_exit "schema prints" 0 "$e"
if cmp -s "$OUT" "$EXP/schema.txt"; then ok "schema as read equals expected/schema.txt"; else miss "schema as read" "differs from expected/schema.txt"; fi
python3 -I "$TOOLS" schema-drift "$SKILL/references/schemas.md" "$SKILL/../../references/schemas.md" > "$OUT" 2>&1
expect_exit "runtime schemas.md matches the pack source" 0 $?
if [ ! -f "$SKILL/SKILL.md" ]; then echo "SKILL.md missing" > "$OUT"; miss "SKILL.md present" "missing"
elif grep -nE '\b(30|60|90) days\b|\b(30|60|90)-day' "$SKILL/SKILL.md" > "$OUT"; then miss "no window or age written into SKILL.md" "found"
else ok "no window or age written into SKILL.md"; fi
if grep -rnE '\$[0-9]' "$SKILL" > "$OUT"; then miss "no dollar sign before a digit" "found"; else ok "no dollar sign before a digit"; fi

echo "== check"
fresh
e=$(roster check --as-of 2026-10-20); expect_exit "green: sample workspace is clean" 0 "$e"
fresh
sed -i.bak '1s/,status,/,state,/' "$WS/data/creators.csv" && rm -f "$WS/data/creators.csv.bak"
e=$(roster check --as-of 2026-10-20); expect_exit "must-fail: header break exits 1" 1 "$e"
expect_text "header break names the missing column" "missing column status"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-g7h8i9 status superstar
e=$(roster check --as-of 2026-10-20); expect_exit "must-fail: invalid enum exits 1" 1 "$e"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-j1k2l3 notes "2026-05-01 programme lead: 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
e=$(roster check --as-of 2026-10-20); expect_exit "must-fail: a hashed identifier in the roster exits 1" 1 "$e"
expect_text "hashed identifier is named" "hashed identifier"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 code ALPHA15
e=$(roster check --as-of 2026-10-20); expect_exit "must-fail: a code on two creators exits 1" 1 "$e"
fresh
tool set-cell "$WS/data/pipeline.csv" creator_ref=c-m4n5o6 creator_ref c-zz9zz9
e=$(roster check --as-of 2026-10-20); expect_exit "must-fail: a pipeline ref missing from the roster exits 1" 1 "$e"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 followers_as_of N/A
e=$(roster check --as-of 2026-10-20); expect_exit "must-fail: N/A instead of an empty cell exits 1" 1 "$e"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-g7h8i9 tier mid
tool set-cell "$WS/data/pipeline.csv" creator_ref=c-m4n5o6 owner_role "the intern"
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: tier against followers and an unknown role exit 2" 2 "$e"
expect_text "tier warning names the band" "is nano by the bands"
expect_text "role warning names the role" "owner_role 'the intern'"
fresh
rm "$WS/program/program.md"
e=$(roster check --as-of 2026-10-20); expect_exit "partial: no programme file exits 2" 2 "$e"
expect_text "partial says what was not checked" "owner_role against the roles"

echo "== find"
fresh
e=$(roster find --handle fixture_Alpha_TT); expect_exit "find: a handle on another platform" 0 "$e"
expect_text "find names the record" "c-a1b2c3  Fixture Creator A"
e=$(roster find --platform instagram --handle @nobody_here); expect_exit "find: not in the roster" 0 "$e"
expect_text "find says not found, not an error" "not in the roster: no record has instagram @nobody_here"
e=$(roster find --handle @fixture_alpha --url https://instagram.example.com/fixture_echo); expect_exit "find: two records" 0 "$e"
expect_text "find flags a possible merge" "found 2 records"
e=$(roster find); expect_exit "must-fail: find with nothing to look for exits 1" 1 "$e"

fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 notes "2026-10-10 programme lead: status prospect -> contacted (reason: first touch sent by DM);2026-10-18 programme lead: do not contact (asked by DM)"
e=$(roster find --handle @fixture_echo); expect_text "find shows do not contact" "DO NOT CONTACT"
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: an open pipeline row for a do-not-contact creator exits 2" 2 "$e"
expect_text "the warning names the creator" "c-m4n5o6 carries 'do not contact'"
e=$(roster report --as-of 2026-10-20); expect_text "the report lists do not contact" "asked not to be approached again: c-m4n5o6"

echo "== add"
fresh
e=$(roster add --from-shortlist "$IN/shortlist-2026-10-19.csv" --role "$ROLE" --date 2026-10-20 --seed 1)
expect_exit "green: add engage and negotiate rows" 0 "$e"
expect_eq "three creators added" 8 "$(tool rows "$WS/data/creators.csv")"
expect_text "skip and exclude verdicts are not selected" "Not selected by verdict: exclude 1, skip 1"
expect_eq "handle stored with @" "@fixture_foxtrot" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator F" primary_handle)"
expect_eq "followers with a thousands comma recorded" "15400" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator F" followers_primary)"
expect_eq "an estimated follower count is not recorded" "" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator H" followers_primary)"
expect_eq "tier read from the shortlist (section 8)" "micro" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator F" tier)"
expect_eq "engagement_rate_pct read from the shortlist" "3.8" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator F" engagement_rate_pct)"
expect_eq "engagement_as_of taken from scored_as_of" "2026-10-19" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator F" engagement_as_of)"
case "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator G" notes)" in *"followers User-provided (media_kit)"*) ok "a media-kit figure is recorded with its label (section 7)";; *) miss "media-kit label" "not in the note";; esac
expect_eq "brand_safety_flag copied from the shortlist" "review" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator G" brand_safety_flag)"
expect_eq "an empty brand_safety_flag stays empty (unknown)" "" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator H" brand_safety_flag)"
ref=$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator F" creator_ref)
if echo "$ref" | grep -qE '^c-[a-z0-9]{6}$' && ! echo "$ref" | grep -q foxtrot; then ok "ref has the schema shape and is not built from the handle"; else miss "ref shape" "$ref"; fi
e=$(roster check --as-of 2026-10-20); expect_exit "check is clean after add" 0 "$e"
fresh
e=$(roster add --from-shortlist "$IN/shortlist-2026-10-19.csv" --verdicts engage,negotiate,skip --role "$ROLE" --date 2026-10-20 --seed 1)
expect_exit "a skip row with an empty total is accepted (section 8)" 0 "$e"
expect_eq "the skip row has no audience_fit_score" "" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator I" audience_fit_score)"
expect_eq "a search_result follower count (Estimated) is not recorded" "" "$(tool cell "$WS/data/creators.csv" display_name="Fixture Creator I" followers_primary)"
expect_text "the Estimated figure is reported, not dropped silently" "followers 5000 (Estimated, search_result)"
e=$(roster check --as-of 2026-10-20); expect_exit "check is clean after adding a skip row" 0 "$e"
fresh
cut -d, -f1-23 "$IN/shortlist-ambiguous-2026-10-19.csv" > "$TMP/shortlist-old-2026-10-19.csv"
e=$(roster add --from-shortlist "$TMP/shortlist-old-2026-10-19.csv" --role "$ROLE" --date 2026-10-20 --seed 1 --dry-run)
expect_text "a shortlist without the section 8 columns is named in the coverage" "shortlist columns absent (tier, engagement_rate_pct, brand_safety_flag)"
fresh
snapshot
e=$(roster add --from-shortlist "$IN/shortlist-2026-10-19.csv" --role "$ROLE" --date 2026-10-20 --seed 1 --dry-run)
expect_exit "dry run exits 0" 0 "$e"
expect_text "dry run names no ref it would draw" "(ref on write)  instagram @fixture_foxtrot"
if grep -E '^  c-[a-z0-9]{6} ' "$OUT" > /dev/null; then miss "dry run prints no new ref" "a ref was printed"; else ok "dry run prints no new ref"; fi
unchanged "dry run writes nothing"
fresh
e=$(roster add --from-shortlist "$IN/shortlist-duplicates-2026-10-19.csv" --role "$ROLE" --date 2026-10-20 --seed 1)
expect_exit "must-fail: duplicates are reported, not added (exit 0, only the new creator added)" 0 "$e"
expect_eq "only one new row" 6 "$(tool rows "$WS/data/creators.csv")"
expect_text "duplicate handle, other case, found" "instagram @fixture_alpha: already c-a1b2c3"
expect_text "duplicate found through other_platforms" "tiktok @fixture_alpha_tt: already c-a1b2c3"
expect_text "duplicate found through the profile URL" "already c-m4n5o6 (same profile URL"
expect_text "duplicate inside the shortlist found" "It was added earlier in this run."
expect_eq "tier computed from the bands when the shortlist has none" "nano" "$(tool cell "$WS/data/creators.csv" primary_handle=@fixture_kilo tier)"
fresh
snapshot
e=$(roster add --from-shortlist "$IN/shortlist-ambiguous-2026-10-19.csv" --role "$ROLE" --date 2026-10-20 --seed 1)
expect_exit "partial: a row matching two records is skipped (exit 2)" 2 "$e"
expect_text "ambiguous row names both refs" "c-a1b2c3 by instagram @fixture_alpha; c-m4n5o6 by profile URL"
VETTING_GREEN="$SKILL/../creator-vetting/scripts/fixtures/cases/expected-green-shortlist.csv"
if [ -f "$VETTING_GREEN" ]; then
  fresh
  e=$(roster add --from-shortlist "$VETTING_GREEN" --role "$ROLE" --date 2026-10-20 --seed 2)
  expect_exit "vetting's current green shortlist adds cleanly" 0 "$e"
  if grep -q "shortlist columns absent" "$OUT"; then miss "vetting's shortlist carries every column add reads" "absent columns named"; else ok "vetting's shortlist carries every column add reads"; fi
  expect_eq "vetting's brand_safety_flag copied" "none" "$(tool cell "$WS/data/creators.csv" primary_handle=@fixture_creator_a brand_safety_flag)"
  e=$(roster check --as-of 2026-10-20); expect_exit "check is clean after adding vetting's shortlist" 0 "$e"
else
  echo "skip  vetting's green shortlist (creator-vetting is not installed beside this skill)"
fi
fresh
e=$(roster add --from-shortlist "$IN/shortlist-2026-10-19.csv" --role "intern" --date 2026-10-20)
expect_exit "must-fail: a role not in programme section 10 exits 1" 1 "$e"

echo "== update"
fresh
e=$(roster update c-m4n5o6 status=negotiating --note "replied by DM, asked for terms" --role "$ROLE" --date 2026-10-20)
expect_exit "green: status update" 0 "$e"
notes=$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 notes)
case "$notes" in *";2026-10-20 programme lead: status contacted -> negotiating (reason: replied by DM, asked for terms)") ok "dated note with the role appended";; *) miss "dated note appended" "$notes";; esac
expect_eq "last_activity set" "2026-10-20" "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 last_activity)"
e=$(roster check --as-of 2026-10-20); expect_exit "check is clean after update" 0 "$e"
fresh
e=$(roster update c-m4n5o6 contact_email=e@creator-e.example.com contact_path=email --note "given by the creator in a DM" --role "$ROLE" --date 2026-10-20)
expect_exit "green: contact email given by the creator" 0 "$e"
case "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 notes)" in *e@creator-e.example.com*) miss "the note does not copy the email" "copied";; *) ok "the note does not copy the email";; esac
fresh
snapshot
e=$(roster update c-m4n5o6 status=superstar --note "x" --role "$ROLE")
expect_exit "must-fail: invalid enum on update exits 1" 1 "$e"
expect_text "invalid enum lists the allowed values" "is not one of: prospect, contacted"
unchanged "invalid enum writes nothing"
e=$(roster update c-m4n5o6 code=ALPHA15 --note "x" --role "$ROLE"); expect_exit "must-fail: a code another creator holds exits 1" 1 "$e"
e=$(roster update c-m4n5o6 primary_handle=fixture_alpha --note "x" --role "$ROLE"); expect_exit "must-fail: a handle another record holds exits 1" 1 "$e"
e=$(roster update c-m4n5o6 creator_ref=c-zzzzzz --note "x" --role "$ROLE"); expect_exit "must-fail: creator_ref cannot change" 1 "$e"
e=$(roster update c-m4n5o6 status=paused --note "one; two" --role "$ROLE"); expect_exit "must-fail: a note with ';' exits 1" 1 "$e"
unchanged "refused updates write nothing"

fresh
e=$(roster update c-m4n5o6 status=agreed --note "terms agreed in principle" --role "$ROLE" --date 2026-10-20)
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: agreed with no agreement_date exits 2" 2 "$e"
expect_text "the warning names the hand-off" "only at partnership-agreement's hand-off"
fresh
e=$(roster update c-d4e5f6 --note "paid for the 2026-10 period" --role finance --date 2026-10-31)
expect_exit "green: a note-only update" 0 "$e"
case "$(tool cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 notes)" in *";2026-10-31 finance: paid for the 2026-10 period") ok "note-only entry written with date and role";; *) miss "note-only entry" "missing";; esac
expect_eq "a note-only update moves last_activity" "2026-10-31" "$(tool cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 last_activity)"
e=$(roster update c-d4e5f6 --note "late entry for an old call" --role finance --date 2026-09-01)
expect_eq "last_activity never moves backwards" "2026-10-31" "$(tool cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 last_activity)"
e=$(roster update c-d4e5f6 last_activity=2026-11-01 --note "x" --role finance); expect_exit "must-fail: last_activity is not set directly" 1 "$e"
expect_text "the refusal gives the note-only form" "update c-d4e5f6 --note"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 last_activity 2026-10-10
e=$(roster check --as-of 2026-10-20); expect_exit "last_activity equal to the latest note and pipeline date is clean" 0 "$e"
tool set-cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 last_activity 2026-10-05
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: one later dated note or pipeline row exits 2" 2 "$e"
expect_text "the stale last_activity warning gives the latest date" "latest dated note or pipeline row (2026-10-10)"
fresh
tool set-cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 usage_rights_until ""
e=$(roster update c-d4e5f6 --note "rights from posting: 6 months" --role "$ROLE" --date 2026-10-20)
e=$(roster check --as-of 2026-10-20); expect_exit "rights from posting with no post yet is clean" 0 "$e"
e=$(roster report --as-of 2026-10-20)
expect_text "report: window from posting, not none granted" "Window from posting, not yet live: 1 creator (c-d4e5f6 (6 months))"
if grep -q "None granted: .*c-d4e5f6" "$OUT"; then miss "from-posting row is not none granted" "listed as none granted"; else ok "from-posting row is not none granted"; fi
tool set-cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 usage_rights_until ""
e=$(roster update c-a1b2c3 --note "rights from posting: 6 months" --role "$ROLE" --date 2026-10-20)
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: a post is recorded but the from-posting date is not set" 2 "$e"
expect_text "the warning names the post date" "a post was recorded on 2026-10-12"
e=$(roster update c-a1b2c3 usage_rights_until=2027-04-12 --note "six months from the 2026-10-12 post" --role "$ROLE" --date 2026-10-20)
expect_exit "update accepts the from-posting date while the note stands" 0 "$e"
tool set-cell "$WS/data/publications.csv" publication_id=p-q7r8s9 rights_until 2027-04-12
e=$(roster check --as-of 2026-10-20); expect_exit "no warning when the date is set and the note stands" 0 "$e"
e=$(roster update c-a1b2c3 usage_rights_until=2027-06-30 --note "a later post extends the window" --role "$ROLE" --date 2026-10-20)
expect_exit "update accepts a later usage_rights_until on a from-posting row" 0 "$e"
expect_eq "the later date is recorded" "2027-06-30" "$(tool cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 usage_rights_until)"
e=$(roster check --as-of 2026-10-20); expect_exit "still clean with the later date" 0 "$e"
tool set-cell "$WS/data/publications.csv" publication_id=p-q7r8s9 rights_until 2027-09-30
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: a post's rights_until later than the roster's date exits 2" 2 "$e"
expect_text "the warning says the roster carries the latest" "The roster carries the latest of them"
fresh
e=$(roster update c-d4e5f6 --note "rights from posting six months" --role "$ROLE" --date 2026-10-20)
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: a malformed rights-from-posting note exits 2" 2 "$e"
expect_text "the warning gives the fixed form" "rights from posting: <n> months"

fresh
notes="$(tool cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 notes);2026-10-20 programme lead: test order #1001 is the brand's own and earns no commission"
tool set-cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 notes "$notes"
tool set-cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 last_activity 2026-10-20
tool set-cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 usage_rights_until ""
notes="$(tool cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 notes);2026-10-20 programme lead: rights from posting: 6 months (organic reuse only, from the agreement's hand-off)"
tool set-cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 notes "$notes"
tool set-cell "$WS/data/creators.csv" creator_ref=c-d4e5f6 last_activity 2026-10-20
e=$(roster check --as-of 2026-10-20); expect_exit "dated test order and rights-from-posting entries are read without a warning" 0 "$e"
e=$(roster report --as-of 2026-10-20); expect_text "a dated rights-from-posting entry is read as a window from posting" "Window from posting, not yet live: 1 creator (c-d4e5f6 (6 months))"
tool set-cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 notes "$(tool cell "$WS/data/creators.csv" creator_ref=c-a1b2c3 notes);test order #1002"
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: an undated fixed entry still warns (every entry is dated)" 2 "$e"
expect_text "the warning names the undated entry" "notes entry 'test order #1002' does not start with its date"
fresh
e=$(roster update c-g7h8i9 --note "do not contact, asked by DM" --role "$ROLE")
last="$(tool cell "$WS/data/creators.csv" creator_ref=c-g7h8i9 notes | awk -F';' '{print $NF}')"
if echo "$last" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2} programme lead: do not contact, asked by DM$'; then ok "update --note dates the entry even without --date"; else miss "update --note dates the entry" "$last"; fi
fresh
e=$(roster report --as-of 2026-10-20)
expect_text "a live row's next action is listed as due on its date" "| 2026-10-launch-tote | c-a1b2c3 | live | run the day 7 check | 2026-10-19 | programme lead |"
if sed -n '/^## Pipeline actions past their date/,/^## Post checks due/p' "$OUT" | grep -q "c-a1b2c3"; then miss "a live row is not graded overdue" "listed under past their date"; else ok "a live row is not graded overdue"; fi
expect_text "the report says publication-tracking grades live rows" "publication-tracking's due list says which to act on now"

echo "== merge"
fresh
cat >> "$WS/data/creators.csv" <<'EOF'
c-p7q8r9,Fixture Creator E (second record),instagram,@fixture_echo2,https://instagram.example.com/fixture_echo,,micro,33000,2026-10-15,,,fitness;humour,22,,email,echo@creator-e.example.com,contacted,cpa,15,,ECHO15,,manual,,,,,2026-12-holiday-tote,2026-10-16,2026-10-16 programme lead: added in the workbook;2026-10-17 programme lead: do not contact (asked by email)
EOF
cat >> "$WS/data/pipeline.csv" <<'EOF'
2026-12-holiday-tote,c-p7q8r9,first_touch,2026-10-16,first follow-up,2026-10-22,programme lead,2026-10-16,"cpa 15 pct, code 15 pct off, no fee",2026-10-16 programme lead: first touch by email
EOF
tool set-cell "$WS/data/pipeline.csv" creator_ref=c-p7q8r9 stage closed
tool set-cell "$WS/data/pipeline.csv" creator_ref=c-m4n5o6 stage closed
e=$(roster check --as-of 2026-10-20); expect_exit "warnings: a likely duplicate exits 2" 2 "$e"
expect_text "the duplicate warning names both refs" "c-m4n5o6 and c-p7q8r9 share profile URL"
snapshot
e=$(roster merge c-p7q8r9 c-m4n5o6 --note "same profile URL" --role "$ROLE" --date 2026-10-20)
expect_exit "must-fail: keeping the newer ref exits 1" 1 "$e"
expect_text "the refusal gives the right order" "Run: merge c-m4n5o6 c-p7q8r9"
unchanged "a refused merge writes nothing"
e=$(roster merge c-m4n5o6 c-p7q8r9 --note "same profile URL, creator confirmed by DM" --role "$ROLE" --date 2026-10-20)
expect_exit "green: merge into the older record" 0 "$e"
expect_eq "rows are kept, none deleted" 6 "$(tool rows "$WS/data/creators.csv")"
expect_eq "the newer record takes the merged status" "ended" "$(tool cell "$WS/data/creators.csv" creator_ref=c-p7q8r9 status)"
expect_eq "the code moves to the kept record" "ECHO15" "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 code)"
expect_eq "the pipeline row now names the kept ref" "c-m4n5o6" "$(tool cell "$WS/data/pipeline.csv" campaign_slug=2026-12-holiday-tote creator_ref)"
case "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 notes)" in *"merged c-p7q8r9 into this record"*) ok "the kept record's notes record the other ref";; *) miss "kept notes" "no merge note";; esac
case "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 notes)" in *"do not contact, carried from the newer record"*) ok "do not contact is carried to the kept record";; *) miss "do not contact carried" "not on the kept record";; esac
e=$(roster check --as-of 2026-10-20); expect_exit "check is clean after merge" 0 "$e"
e=$(roster add --from-shortlist "$IN/shortlist-duplicates-2026-10-19.csv" --role "$ROLE" --date 2026-10-20 --seed 1)
expect_text "a later match on the merged record goes to the kept ref" "already c-m4n5o6"

echo "== report"
fresh
e=$(roster report --as-of 2026-10-20); expect_exit "green: report" 0 "$e"
if cmp -s "$OUT" "$EXP/report-2026-10-20.txt"; then ok "report equals expected/report-2026-10-20.txt"; else miss "report" "differs from expected/report-2026-10-20.txt"; diff "$EXP/report-2026-10-20.txt" "$OUT" | head -20; fi
e=$(roster report --as-of 2026-10-20 --out ../outside.md); expect_exit "must-fail: report outside the workspace exits 1" 1 "$e"

echo "== workbook"
fresh
e=$(roster export-xlsx); expect_exit "green: export" 0 "$e"
parts=$(tool parts "$WS/data/creator-programme.xlsx" | tr '\n' ' ')
expect_eq "the workbook has the minimal parts" "[Content_Types].xml _rels/.rels docProps/custom.xml xl/_rels/workbook.xml.rels xl/styles.xml xl/workbook.xml xl/worksheets/sheet1.xml xl/worksheets/sheet2.xml xl/worksheets/sheet3.xml " "$parts"
snapshot
e=$(roster import-xlsx --role "$ROLE"); expect_exit "round trip: import of an unedited export" 0 "$e"
expect_text "round trip finds no changes" "No changes: the workbook matches the CSVs."
unchanged "round trip: CSVs are byte-identical"
tool edit-xlsx "$WS/data/creator-programme.xlsx" "$TMP/shared.xlsx" shared
e=$(roster import-xlsx "$TMP/shared.xlsx" --role "$ROLE"); expect_exit "round trip through shared strings" 0 "$e"
expect_text "shared strings read as the same text" "No changes"
fresh
roster export-xlsx > /dev/null
serial=$(tool serial 2026-10-15)
tool edit-xlsx "$WS/data/creator-programme.xlsx" "$TMP/edited.xlsx" \
  "set:creators:creator_ref=c-m4n5o6:status=negotiating" \
  "number:creators:creator_ref=c-g7h8i9:followers_as_of=$serial" \
  "number:creators:creator_ref=c-g7h8i9:followers_primary=8200" \
  "append:creators:display_name=Fixture Creator L,primary_platform=bluesky,primary_handle=@fixture_lima,status=prospect" \
  shared
cp "$TMP/edited.xlsx" "$WS/data/creator-programme.xlsx"
e=$(roster check --as-of 2026-10-20); expect_exit "check warns of unimported workbook edits" 2 "$e"
expect_text "the warning says to import" "Run import-xlsx before any other skill writes"
e=$(roster export-xlsx); expect_exit "must-fail: export refuses to overwrite unimported edits" 1 "$e"
snapshot
e=$(roster import-xlsx --dry-run --seed 5 --date 2026-10-20); expect_exit "edited workbook: dry run" 0 "$e"
expect_text "dry run prints the changed cell" "data/creators.csv | c-m4n5o6 | status | 'contacted' | 'negotiating'"
expect_text "dry run says it converted a date serial" "Excel stored $serial (a date serial); read as 2026-10-15"
expect_text "import dry run names no ref it would draw" "(new ref 1, drawn on write)"
unchanged "dry run writes nothing"
e=$(roster import-xlsx --role "$ROLE" --seed 5 --date 2026-10-20); expect_exit "edited workbook: import" 0 "$e"
expect_eq "status imported" "negotiating" "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 status)"
expect_eq "serial stored as an ISO date" "2026-10-15" "$(tool cell "$WS/data/creators.csv" creator_ref=c-g7h8i9 followers_as_of)"
newref=$(tool cell "$WS/data/creators.csv" primary_handle=@fixture_lima creator_ref)
if echo "$newref" | grep -qE '^c-[a-z0-9]{6}$'; then ok "a new workbook row gets a ref"; else miss "new row ref" "$newref"; fi
case "$(tool cell "$WS/data/creators.csv" creator_ref=c-m4n5o6 notes)" in *"2026-10-20 programme lead: edited in the workbook (status contacted -> negotiating)") ok "import notes the edit with the date and role";; *) miss "import note" "missing";; esac
e=$(roster check --as-of 2026-10-20); expect_exit "check is clean after import (workbook refreshed)" 0 "$e"
fresh
roster export-xlsx > /dev/null
tool edit-xlsx "$WS/data/creator-programme.xlsx" "$TMP/renamed.xlsx" "rename:pipeline:Pipeline 2026"
snapshot
e=$(roster import-xlsx "$TMP/renamed.xlsx" --role "$ROLE"); expect_exit "must-fail: a renamed sheet exits 1" 1 "$e"
expect_text "the renamed sheet is named" "no sheet named pipeline"
expect_text "the new name is shown" "'Pipeline 2026'"
unchanged "a refused import writes nothing"
tool edit-xlsx "$WS/data/creator-programme.xlsx" "$TMP/dropped.xlsx" "drop:creators:creator_ref=c-j1k2l3"
e=$(roster import-xlsx "$TMP/dropped.xlsx" --role "$ROLE"); expect_exit "must-fail: a deleted row exits 1" 1 "$e"
expect_text "nothing is deleted" "Nothing is deleted"
tool edit-xlsx "$WS/data/creator-programme.xlsx" "$TMP/badenum.xlsx" "set:creators:creator_ref=c-g7h8i9:status=Prospect"
e=$(roster import-xlsx "$TMP/badenum.xlsx" --role "$ROLE"); expect_exit "must-fail: an invalid value typed in the workbook exits 1" 1 "$e"
tool edit-xlsx "$WS/data/creator-programme.xlsx" "$TMP/dupe.xlsx" "append:creators:display_name=Again,primary_platform=instagram,primary_handle=@FIXTURE_ECHO"
e=$(roster import-xlsx "$TMP/dupe.xlsx" --role "$ROLE"); expect_exit "must-fail: a new workbook row that duplicates a creator exits 1" 1 "$e"
unchanged "refused imports write nothing"
fresh
roster export-xlsx > /dev/null
roster update c-g7h8i9 status=contacted --note "first touch by DM" --role "$ROLE" --date 2026-10-20 > /dev/null
e=$(roster import-xlsx --role "$ROLE"); expect_exit "must-fail: a stale workbook is not imported over newer CSVs" 1 "$e"
expect_text "stale workbook: says to export" "Run export-xlsx to refresh the workbook"

echo
echo "fixtures: $pass passed, $fail missed"
[ "$fail" -eq 0 ]
