#!/usr/bin/env bash
# Fixture runner for scripts/checks_due.py (publication-tracking, 2026-10-20).
# Every fixture workspace is copied to a temporary folder first; the fixtures themselves are never written.
# Exits 0 when every expectation holds, 1 on any miss. Each expected line is written out with its date
# arithmetic so a reader can check it by hand: a check is due on the posting date plus 1, 7 or 30 days (from
# then it is listed under ACT NOW, exit 2) and is overdue after GRACE_DAYS more (1, 2 and 3 days); a rights
# window is listed when it ends within 30 days.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../checks_due.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CHECKS=0; MISSES=0; OUT=""; CODE=0
miss() { MISSES=$((MISSES + 1)); echo "MISS: ${1}"; }
run() { local want="${1}"; shift; CHECKS=$((CHECKS + 1))
  OUT="$(python3 -I "$SCRIPT" "$@" 2>&1)"; CODE=$?
  if [ "$CODE" != "$want" ]; then miss "exit $CODE, wanted $want: checks_due.py $*"; printf '%s\n' "$OUT" | sed 's/^/    /'; fi; }
has() { CHECKS=$((CHECKS + 1)); printf '%s\n' "$OUT" | grep -qF -- "${1}" || miss "output lacks: ${1}"; }
lacks() { CHECKS=$((CHECKS + 1)); if printf '%s\n' "$OUT" | grep -qF -- "${1}"; then miss "output should not contain: ${1}"; fi; }
file_has() { CHECKS=$((CHECKS + 1)); grep -qF -- "${2}" "${1}" || miss "$(basename "${1}") lacks: ${2}"; }
copy() { rm -rf "$TMP/${2}"; cp -R "$HERE/${1}" "$TMP/${2}"; }
PL="programme lead"

echo "== green: nothing due on 2026-12-15"
# p-grn001 and p-grn002 have every check recorded; p-grn003 was posted 2026-12-15, so its day 1 check is due
# 2026-12-16 (not yet); p-grn004's rights ended 2026-09-30 and are only counted.
run 0 "$HERE/green" --as-of 2026-12-15
has "Result: nothing needs attention (exit 0)"
has "Rights already ended: 1 [p-grn004]"
# p-grn004's rights ended 2026-09-30; the roster's later 2027-06-30 was recorded as not covering it.
lacks "rights ended 2026-09-30"
lacks "OVERDUE"

echo "== green: a check is due from its due date (ACT NOW, exit 2), not yet overdue (2026-12-16)"
run 2 "$HERE/green" --as-of 2026-12-16
has "Result: needs attention (exit 2): 0 overdue, 1 to act on"
has "p-grn003 (2026-11-launch, c-aaaaa1, instagram story): day 1 check due 2026-12-16 (posted 2026-12-15 + 1 day): open the post and record it; overdue after 2026-12-17 (+1 day)"

echo "== green: the same check is overdue once its window closes (2026-12-18)"
run 2 "$HERE/green" --as-of 2026-12-18
has "day 1 check due 2026-12-16 (posted 2026-12-15 + 1 day), window closed 2026-12-17 (+1 day), not recorded"

echo "== must-attend: overdue checks, open issues and an expiring right (2026-11-20)"
run 2 "$HERE/must-attend" --as-of 2026-11-20
has "Result: needs attention (exit 2): 2 overdue, 7 to act on, 1 with lines not checked, 2 coming up"
# p-att001 posted 2026-11-10: day 7 due 2026-11-17, window closed 2026-11-19.
has "p-att001 (2026-11-launch, c-aaaaa1, instagram reel): day 7 check due 2026-11-17 (posted 2026-11-10 + 7 days), window closed 2026-11-19 (+2 days), not recorded"
has "p-att001 (2026-11-launch, c-aaaaa1, instagram reel): disclosure partial (forms seen: caption), no fix asked"
# p-att003: the fix was asked 2026-11-09 for 2026-11-12, and no re-check has confirmed it.
has "p-att003 (2026-11-launch, c-ddddd4, x post): disclosure no (forms seen: none); fix asked 2026-11-09, due 2026-11-12, not confirmed by a re-check"
# p-att002 posted 2026-11-18 under a flat deal: day 1 due 2026-11-19, window to 2026-11-20; rights end
# 2026-12-10, 20 days after 2026-11-20; the roster has since moved to 2027-03-10.
has "p-att002 (2026-11-launch, c-bbbbb2, youtube video): flat deal, fee milestone not recorded"
has "p-att002 (2026-11-launch, c-bbbbb2, youtube video): day 1 check due 2026-11-19 (posted 2026-11-18 + 1 day): open the post and record it; overdue after 2026-11-20 (+1 day)"
has "rights end 2026-12-10 (rights_until on the row), in 20 days: content-reuse to plan, partnership-agreement to extend; the roster now says 2027-03-10"
# p-att004 removed at the day 7 check (2026-11-19); its day 30 check is no longer listed.
has "p-att004 (2026-11-launch, c-eeeee5, instagram post): removed at the day 7 check on 2026-11-19"
# Section 11 sets 30 days live; 2026-11-19 is 7 days after posting on 2026-11-12.
has "programme section 11 sets a minimum of 30 days live: seen removed 7 days after posting, inside it"
lacks "p-att004 (2026-11-launch, c-eeeee5, instagram post): day 30"
# p-att005 recorded with no live check; posted 2026-11-19, so day 1 due 2026-11-20.
has "p-att005 (2026-11-launch, c-aaaaa1, instagram post): not recorded: disclosure, code, link, age setting, match to approval"
has "p-att005 (2026-11-launch, c-aaaaa1, instagram post): day 1 check due 2026-11-20 (posted 2026-11-19 + 1 day): open the post and record it; overdue after 2026-11-21 (+1 day)"
has "p-att005 (2026-11-launch, c-aaaaa1, instagram post): rights window not on the row; the roster now says 2027-06-30"
# p-att006: a TikTok post, which the fixture's section 3 bars, published with no approval; gift deal, no code.
has "p-att006 (2026-11-launch, c-fffff6, tiktok video): programme section 3 says organic creator posts on tiktok: no"
has "p-att006 (2026-11-launch, c-fffff6, tiktok video): no approval on record"
# p-att005's roster row has a rights date the row lacks (unknown); c-fffff6 has an agreement on file and no
# rights date, which schemas.md section 4 reads as none granted.
has "Rights window unknown: 1 [p-att005]"
has "No reuse rights granted: 1 [p-att006]"

echo "== must-attend: a lapsed rights window the roster has since extended is pointed out (2026-12-15)"
# p-att002's rights_until 2026-12-10 has passed; the roster now says 2027-03-10.
run 2 "$HERE/must-attend" --as-of 2026-12-15
has "p-att002 (2026-11-launch, c-bbbbb2, youtube video): rights ended 2026-12-10 (rights_until on the row); the roster now says 2027-03-10: if the extension covers this post, record --rights-from-roster"

copy must-attend rn
run 0 "$TMP/rn" record p-att002 --role "$PL" --on 2026-12-15 --rights-not-covered --note "the extension covers new posts only"
run 2 "$TMP/rn" --as-of 2026-12-15
lacks "rights ended 2026-12-10"

echo "== a usage error exits 1, not 2"
run 1 "$HERE/green" --as-of 2026-12-15 --bogus
has "unrecognized arguments: --bogus"

echo "== must-attend: dealing with items clears them"
copy must-attend ma
run 0 "$TMP/ma" record p-att004 --role "$PL" --on 2026-11-20 --removal-reviewed "inside the window; referred to the programme lead, agreement takedown term"
run 0 "$TMP/ma" record p-att002 --role "$PL" --on 2026-11-20 --fee-milestone reached
has "Recorded: fee milestone reached."
run 0 "$TMP/ma" record p-att002 --role "$PL" --on 2026-11-20 --rights-from-roster --note "extension agreed 2026-11-15, covers this post"
has "Recorded: rights_until 2026-12-10 -> 2027-03-10 (copied from the roster)."
run 2 "$TMP/ma" --as-of 2026-11-20
lacks "removed at the day 7 check"
lacks "fee milestone not recorded"
lacks "rights end 2026-12-10"
file_has "$TMP/ma/data/publications.csv" "2026-11-20 fee milestone reached by programme lead: finance to pay"
# The milestone is recorded once; a part of a set needs a note saying which part.
run 1 "$TMP/ma" record p-att002 --role "$PL" --on 2026-11-21 --fee-milestone reached
has "already has a fee milestone reached"
run 1 "$TMP/ma" record p-att002 --role "$PL" --on 2026-11-21 --fee-milestone part
has "--fee-milestone part needs --note"
# A part stays on the list while no post for the same creator and campaign carries reached (fresh copy).
copy must-attend mp
run 0 "$TMP/mp" record p-att002 --role "$PL" --on 2026-11-20 --fee-milestone part --note "post 1 of 2 per the agreement"
has "COMING UP: fee milestone part on 2026-11-20; no post of this campaign carries reached yet"

echo "== must-attend: an edited post needs the live check again"
# p-att001's day 7 check (due 2026-11-17) is recorded late, on 2026-11-20, as edited.
run 0 "$TMP/ma" record p-att001 --role "$PL" --on 2026-11-20 --day7 edited
has "Recorded: day 7 check: edited."
run 2 "$TMP/ma" --as-of 2026-11-20
has "p-att001 (2026-11-launch, c-aaaaa1, instagram reel): edited at the day 7 check on 2026-11-20: re-run the live check"
lacks "p-att001 (2026-11-launch, c-aaaaa1, instagram reel): day 7 check due"
run 0 "$TMP/ma" record p-att001 --role "$PL" --on 2026-11-20 --disclosure-seen partial --disclosure-form caption --matches-approval yes
run 2 "$TMP/ma" --as-of 2026-11-20
lacks "edited at the day 7 check"
has "p-att001 (2026-11-launch, c-aaaaa1, instagram reel): disclosure partial (forms seen: caption), no fix asked"

echo "== must-fail: a header without approval_id is refused and nothing is written"
before="$(cksum < "$HERE/must-fail/data/publications.csv")"
run 1 "$HERE/must-fail" --as-of 2026-11-20
has "header differs from the schema (missing approval_id)"
CHECKS=$((CHECKS + 1)); [ "$before" = "$(cksum < "$HERE/must-fail/data/publications.csv")" ] || miss "must-fail file changed"

echo "== must-fail: a programme without section 3 is refused"
copy green nos3
python3 -I - "$TMP/nos3/program/program.md" <<'PY'
import re, sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write(re.sub(r"^## 3\. Platforms.*?(?=^## 4\.)", "", t, flags=re.M | re.S))
PY
run 1 "$TMP/nos3" --as-of 2026-12-15
has "the programme file has no section 3 (Platforms)"

echo "== add: a new live post"
copy green ws
# Posted 2026-12-14T11:00-08:00, which is 2026-12-14T19:00Z.
LINK_C="https://www.example.com/?utm_source=creator&utm_medium=affiliate&utm_campaign=2026-11-launch&utm_content=c-ccccc3"
run 0 "$TMP/ws" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXADD001/" --posted-at 2026-12-14T11:00-08:00 --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2026-12-15 \
  --disclosure-seen partial --disclosure-form caption --code-in-post CREATORC15 --link-in-post "$LINK_C" \
  --age-setting confirmed --matches-approval yes
has "publication_id=p-"
has "data/publications.csv: read 4 rows, added 1, changed 0. rights_until: 2027-04-30 (copied from the roster)."
has "data/pipeline.csv: read 3 rows, added 0, changed 1."
has "ACT NOW: disclosure partial (forms seen: caption), no fix asked"
PID="$(printf '%s\n' "$OUT" | sed -n 's/^publication_id=\(p-[a-z0-9]\{6\}\)$/\1/p')"
has "Pipeline next action: day 1 check of $PID on 2026-12-15"
CHECKS=$((CHECKS + 1)); [ -n "$PID" ] || miss "no publication_id printed"
file_has "$TMP/ws/data/publications.csv" "$PID,2026-11-launch,c-ccccc3,instagram,https://www.instagram.example.com/reel/FIXADD001/,2026-12-14T19:00Z,reel,partial,caption,CREATORC15"
file_has "$TMP/ws/data/publications.csv" "not_checked,not_checked,not_checked,2027-04-30,"
file_has "$TMP/ws/data/publications.csv" "2026-12-15 added issued-code=CREATORC15 issued-link=$LINK_C verdict=approve by programme lead"
file_has "$TMP/ws/data/pipeline.csv" "2026-11-launch,c-ccccc3,live,2026-12-14,day 1 check of $PID,2026-12-15,programme lead"

echo "== add: refusals (nothing written)"
rows_before="$(wc -l < "$TMP/ws/data/publications.csv")"
run 1 "$TMP/ws" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://instagram.example.com/reel/FIXADD001" --posted-at 2026-12-14T19:00Z --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2026-12-15
has "this post is already recorded as $PID"
run 1 "$TMP/ws" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXADD003/" --posted-at 2026-12-14T19:00Z --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2026-12-15 --disclosure-seen yes --disclosure-form caption
has "a reel counts as disclosed only with on_screen and spoken"
run 1 "$TMP/ws" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXADD004/" --posted-at 2026-12-14T19:00Z --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role intern --on 2026-12-15
has "is not a role in programme section 10"
run 1 "$TMP/ws" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXADD005/" --posted-at 2026-12-14T19:00Z --format reel \
  --approval 2026-11-launch--c-ccccc3--9 --role "$PL" --on 2026-12-15
has "no approval record at"
run 1 "$TMP/ws" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXADD006/" --posted-at 2026-12-14 --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2026-12-15
has "must be a time with its zone"
CHECKS=$((CHECKS + 1)); [ "$rows_before" = "$(wc -l < "$TMP/ws/data/publications.csv")" ] || miss "a refused add changed publications.csv"

echo "== record: checks, a fix request, a re-check, refusals"
# Posted 2026-12-14, so the day 1 check is due 2026-12-15, not on 2026-12-14.
run 1 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-14 --day1 live
has "is not due until 2026-12-15"
run 0 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-15 --day1 live
has "Recorded: day 1 check: live."
# The pipeline row moves on to the day 7 check, due 2026-12-14 + 7 = 2026-12-21.
has "Next action: day 7 check of $PID on 2026-12-21."
file_has "$TMP/ws/data/pipeline.csv" "2026-11-launch,c-ccccc3,live,2026-12-14,day 7 check of $PID,2026-12-21,programme lead"
# No --due: section 8 of the fixture gives 2 days, so 2026-12-15 + 2 = 2026-12-17.
run 0 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-15 --fix-requested disclosure
has "Recorded: fix requested: disclosure, due 2026-12-17 (due from programme section 8, 2 days after the request)."
# 2026-12-16: the fix is awaited (coming up) and p-grn003's day 1 check is due (act now, exit 2).
run 2 "$TMP/ws" --as-of 2026-12-16
has "fix asked 2026-12-15, due 2026-12-17, awaiting the creator"
run 2 "$TMP/ws" --as-of 2026-12-18
has "fix asked 2026-12-15, due 2026-12-17, not confirmed by a re-check"
run 0 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-17 --disclosure-seen yes --disclosure-form "caption;spoken;on_screen;platform_tool"
has "Recorded: fix confirmed: disclosure."
file_has "$TMP/ws/data/publications.csv" "2026-12-17 fix-confirmed disclosure by programme lead: re-check of the live post"
file_has "$TMP/ws/data/publications.csv" "2026-12-15 live-check disclosure=partial forms=caption code=match link=match age=confirmed approval=match by programme lead"
# p-grn003's own day 1 check (due 2026-12-16) is recorded too, so the list is clear on 2026-12-18.
run 0 "$TMP/ws" record p-grn003 --role "$PL" --on 2026-12-16 --day1 live
run 0 "$TMP/ws" --as-of 2026-12-18
lacks "$PID"
run 1 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-18 --waived link --note "not needed"
has "only the owner can waive an issue"
run 1 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-18 --fee-milestone reached
has "a fee milestone applies only to flat and hybrid deals"

echo "== record: after the day 30 check the pipeline's next action is cleared"
run 0 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-21 --day7 live
has "Next action: day 30 check of $PID on 2027-01-13."
run 0 "$TMP/ws" record "$PID" --role "$PL" --on 2027-01-13 --day30 live
has "Next action: none (cleared)."
file_has "$TMP/ws/data/pipeline.csv" "2026-11-launch,c-ccccc3,live,2026-12-14,,,programme lead"

echo "== record: a --due that differs from section 8 is kept and pointed out"
run 0 "$TMP/ws" record "$PID" --role "$PL" --on 2026-12-18 --fix-requested code --due 2026-12-25
has "Warning: --due 2026-12-25 differs from programme section 8's 2 days from the request (2026-12-20)"
file_has "$TMP/ws/data/publications.csv" "2026-12-18 fix-requested code due=2026-12-25 by programme lead: due set by programme lead, programme section 8 gives 2 days"

echo "== must-fail: no correction window in section 8 and no --due"
copy green open8
python3 -I - "$TMP/open8/program/program.md" <<'PY2'
import sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
t = t.replace("after being asked, in days: 2 [owner]", "after being asked, in days: [open]")
open(p, "w", encoding="utf-8").write(t)
PY2
run 1 "$TMP/open8" record p-grn001 --role "$PL" --on 2026-12-15 --fix-requested link
has "is blank or [open]; ask the programme lead for the date and give it with --due DATE"
run 0 "$TMP/open8" record p-grn001 --role "$PL" --on 2026-12-15 --fix-requested link --due 2026-12-19
has "Recorded: fix requested: link, due 2026-12-19 (due set by programme lead)."

echo "== merged duplicates (schemas.md section 4) are refused and never counted"
copy green mg
python3 -I - "$TMP/mg/data" <<'PY2'
import csv, sys
d = sys.argv[1]
with open(f"{d}/creators.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f)); header = list(rows[0].keys())
dup = dict(rows[0]); dup.update(creator_ref="c-zzzzz9", status="ended", primary_handle="@creator_a_old",
                             notes="2026-11-01 merged into c-aaaaa1 by programme lead")
rows.append(dup)
with open(f"{d}/creators.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=header, lineterminator="\n"); w.writeheader(); w.writerows(rows)
with open(f"{d}/publications.csv", newline="", encoding="utf-8") as f:
    pubs = list(csv.DictReader(f)); ph = list(pubs[0].keys())
old = dict(pubs[0]); old.update(publication_id="p-mrg001", creator_ref="c-zzzzz9", post_url="https://www.instagram.example.com/reel/FIXMRG001/")
pubs.append(old)
with open(f"{d}/publications.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=ph, lineterminator="\n"); w.writeheader(); w.writerows(pubs)
PY2
run 2 "$TMP/mg" --as-of 2026-12-15
has "p-mrg001 (2026-11-launch, c-zzzzz9, instagram reel): creator c-zzzzz9 was merged into c-aaaaa1"
has "read 5 publication rows and 3 roster rows (1 merged duplicate not counted)"
run 1 "$TMP/mg" add --campaign 2026-11-launch --creator c-zzzzz9 --platform instagram \
  --url "https://www.instagram.example.com/p/FIXMRG002/" --posted-at 2026-12-14T19:00Z --format post \
  --approval none --role "$PL" --on 2026-12-15
has "creator c-zzzzz9 was merged into c-aaaaa1; record the post under c-aaaaa1."

echo "== add: a later approval attempt is pointed out"
copy green ws2
run 0 "$TMP/ws2" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/p/FIXADD002/" --posted-at 2026-12-14T19:00Z --format post \
  --approval 2026-11-launch--c-ccccc3--1 --role "$PL" --on 2026-12-15
has "a later approval attempt exists (2026-11-launch--c-ccccc3--2)"
has "NOT CHECKED: not recorded: disclosure, code, link, age setting, match to approval"
PID2="$(printf '%s\n' "$OUT" | sed -n 's/^publication_id=\(p-[a-z0-9]\{6\}\)$/\1/p')"
# Removed at the day 1 check: the pipeline asks for the removal review, then clears (no later check is due).
run 0 "$TMP/ws2" record "$PID2" --role "$PL" --on 2026-12-15 --day1 removed
has "Next action: removal review of $PID2 on 2026-12-15."
run 0 "$TMP/ws2" record "$PID2" --role "$PL" --on 2026-12-16 --removal-reviewed "inside the window; referred to the programme lead"
has "Next action: none (cleared)."

echo "== add: rights from posting (schemas.md section 4 roster note) when the roster date is empty"
copy green rfp
python3 -I - "$TMP/rfp/data/creators.csv" <<'PY2'
import csv, sys
p = sys.argv[1]
with open(p, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f)); header = list(rows[0].keys())
for r in rows:
    if r["creator_ref"] == "c-ccccc3":
        r["usage_rights_until"] = ""
        r["notes"] = "2026-10-25 rights from posting: 6 months by programme lead"
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=header, lineterminator="\n"); w.writeheader(); w.writerows(rows)
PY2
# Posted 2026-12-14; plus 6 months is 2027-06-14.
run 0 "$TMP/rfp" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXRFP001/" --posted-at 2026-12-14T19:00Z --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2026-12-15
has "rights_until: 2027-06-14 (posted 2026-12-14 + 6 months, from the roster note 'rights from posting: 6 months'"
has "update c-ccccc3 usage_rights_until=2027-06-14 --note 'rights from posting: 6 months, from p-"
file_has "$TMP/rfp/data/publications.csv" "not_checked,not_checked,not_checked,2027-06-14,"
has "Roster: the roster carries the latest from-posting date (empty now); the programme lead sets it with python3 -I "
# The printed command names creator-roster's script by an absolute path that exists, is dated with the
# posting date and names the role.
ROSTER_PY="$(printf '%s\n' "$OUT" | sed -n 's/^Roster: .* with python3 -I \([^ ]*roster\.py\) .*/\1/p')"
CHECKS=$((CHECKS + 1)); case "$ROSTER_PY" in /*) [ -f "$ROSTER_PY" ] || miss "printed roster script not found: $ROSTER_PY";; *) miss "printed roster script is not absolute: $ROSTER_PY";; esac
has "--role 'programme lead' --date 2026-12-14"

echo "== rights from posting: two posts under one window, each dated from its own posting"
# The programme lead has set the roster's date from the first post (simulated here: creator-roster's own
# script is not run by these fixtures).
set_roster_rights() { python3 -I - "$TMP/rfp/data/creators.csv" "${1}" <<'PY2'
import csv, sys
p, value = sys.argv[1], sys.argv[2]
with open(p, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f)); header = list(rows[0].keys())
for r in rows:
    if r["creator_ref"] == "c-ccccc3":
        r["usage_rights_until"] = value
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=header, lineterminator="\n"); w.writeheader(); w.writerows(rows)
PY2
}
set_roster_rights 2027-06-14
# Second post, 2027-01-20 + 6 months = 2027-07-20: its own date, not the roster's 2027-06-14, and later,
# so the roster update is printed.
run 0 "$TMP/rfp" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/reel/FIXRFP002/" --posted-at 2027-01-20T18:00Z --format reel \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2027-01-20
has "rights_until: 2027-07-20 (posted 2027-01-20 + 6 months, from the roster note"
has "Roster: the roster carries the latest from-posting date (2027-06-14 now); the programme lead sets it with"
has "update c-ccccc3 usage_rights_until=2027-07-20"
has "--date 2027-01-20"
file_has "$TMP/rfp/data/publications.csv" "not_checked,not_checked,not_checked,2027-07-20,"
set_roster_rights 2027-07-20
# A third post recorded late, posted 2026-12-20: 2027-06-20 is earlier than the roster's 2027-07-20, so
# no roster update.
run 0 "$TMP/rfp" add --campaign 2026-11-launch --creator c-ccccc3 --platform instagram \
  --url "https://www.instagram.example.com/p/FIXRFP003/" --posted-at 2026-12-20T18:00Z --format post \
  --approval 2026-11-launch--c-ccccc3--2 --role "$PL" --on 2027-01-20
has "rights_until: 2027-06-20 (posted 2026-12-20 + 6 months"
has "Roster: usage_rights_until 2027-07-20 is already the latest from-posting date (this post's 2027-06-20 is not later); no roster update."
lacks "update c-ccccc3 usage_rights_until="
# On 2027-06-01 the first post's window (2027-06-14) ends in 13 days and the third's (2027-06-20) in 19;
# the roster's later 2027-07-20 is the second post's, so no "the roster now says" hint.
run 2 "$TMP/rfp" --as-of 2027-06-01
has "rights end 2027-06-14 (rights_until on the row), in 13 days: content-reuse to plan, partnership-agreement to extend"
has "rights end 2027-06-20 (rights_until on the row), in 19 days"
lacks "the roster now says 2027-07-20"

echo "== add: a post that went live under a stop verdict is flagged"
run 0 "$TMP/ws2" add --campaign 2026-11-launch --creator c-aaaaa1 --platform instagram \
  --url "https://www.instagram.example.com/p/FIXADD007/" --posted-at 2026-12-14T19:00Z --format post \
  --approval 2026-11-launch--c-aaaaa1--3 --role "$PL" --on 2026-12-15
has "Warning: the verdict of 2026-11-launch--c-aaaaa1--3 is stop"
has "ACT NOW: published under 2026-11-launch--c-aaaaa1--3, whose verdict is stop"

echo "$CHECKS checks, $MISSES missed"
[ "$MISSES" -eq 0 ]
