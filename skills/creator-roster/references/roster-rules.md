# Roster rules: the windows, ages and value meanings the script uses

Dated 2026-10-20. Read by `scripts/roster.py` at every run (the `settings` block below is parsed; the prose is not). Every value is a pack default set at build time from the skill's brief, not an owner decision, until the owner changes it here and records the change in the programme file's section 12. Every status, stage, verdict, model and flag named here must exist in `references/schemas.md`; the script refuses to run if one does not.

```settings
# Windows and ages, in days. Origin: the skill brief, 2026-10-20 [default].
rights_ending_within_days: 30, 60
exclusivity_ending_within_days: 30, 60
stale_after_days: 90

# What a new row gets, by the shortlist verdict. Origin: build choice [default].
default_add_verdicts: engage, negotiate
new_creator_status: prospect
excluded_verdict: exclude
excluded_status: excluded
excluded_flag: exclude

# The status a duplicate record takes when it is merged into the older one.
# Origin: schemas.md section 4 (a merged duplicate keeps ended with a "merged into" note).
merged_status: ended

# Meanings used by check and report. Origin: schemas.md section 4 wording, read by the build.
stale_skips_statuses: declined, ended, excluded
needs_agreement_date: agreed, active
code_expected_status: active
rate_models: cpa, hybrid
fee_models: flat, hybrid
pipeline_done_stages: closed, declined

# Stages whose next action another skill grades. Origin: the lead's ruling, 2026-10-21
# (integration review 4b, N5): publication-tracking grades checks on live posts.
stages_graded_elsewhere: live
```

## What each setting means

| setting | used by | meaning |
|---|---|---|
| `rights_ending_within_days` | report | Two windows. A `usage_rights_until` date falls in the first if it is the report date or within the first number of days after it, in the second if it is later than that and within the second number. A date already past is not in either list. |
| `exclusivity_ending_within_days` | report | The same two windows for `exclusivity_until`. |
| `stale_after_days` | report | A creator is stale when the latest of `last_activity`, their pipeline `stage_date` and `last_message_date`, and their publications' `posted_at` is at least this many days before the report date. A creator with none of those dates is listed apart, as "no activity date recorded". |
| `stale_skips_statuses` | report | Statuses where silence is expected, so they are never listed as stale. |
| `default_add_verdicts` | add | Shortlist verdicts added when `--verdicts` is not given. |
| `new_creator_status` | add | Status given to a creator added from the shortlist. |
| `excluded_verdict`, `excluded_status`, `excluded_flag` | add | When the person asks to record excluded creators (so nobody approaches them again), that verdict gets that status and that `brand_safety_flag`. |
| `merged_status` | merge | Status of the newer record after a merge. Its notes carry `merged into c-` and the kept ref, which the script reads so that later matches go to the kept record. |
| `needs_agreement_date` | check | Statuses that mean terms were agreed in writing, so `agreement_date` should be set. |
| `code_expected_status` | report | The status listed when a creator in it has no `code`. |
| `rate_models`, `fee_models` | check | Which `compensation_model` values need `commission_rate_pct`, and which need `flat_fee` (schemas.md section 4: "for cpa and hybrid", "for flat and hybrid"). |
| `stages_graded_elsewhere` | report | Pipeline stages whose next action is listed as due on its date, never graded overdue here, because another skill owns the grading: for `live`, publication-tracking's due list with its act-now list and grace days. |
| `pipeline_done_stages` | check, report | Pipeline stages that need no further action: a past `next_action_date` on them is not listed, and a second row for the same creator and campaign at one of them is not a warning. |

## Tier bands

The tier bands are not here. The script reads them from `references/schemas.md` section 4 (`tier`) as written: "under 10,000" excludes 10,000, "10,000 to 49,999" includes both figures, "500,000 and up" includes 500,000. If the bands ever leave a gap or overlap, the tier check is not run and the coverage line says so.
