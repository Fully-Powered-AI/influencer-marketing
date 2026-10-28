# Inventory and plan codes

Dated 2026-10-20 (fix round the same day: brand channels, not-granted, merged duplicates; findings round 2026-10-21: no claim cleared, rights from posting), for the content-reuse skill. The vocabulary `scripts/rights_check.py` writes and checks. The script is the authority for every rule below; the expiring window is the constant `EXPIRING_DAYS` in the script, and the script prints its value on every run.

Contents: 1 Inventory columns. 2 Rights status. 3 Holds. 4 Notes. 5 Channel codes. 6 Plan columns and the plan check. 7 Where each input is read.

## 1. `campaigns/<slug>/reuse/inventory.csv`

One row per publication of the campaign, rebuilt on every run. A row for a publication no longer in `data/publications.csv` is kept, never deleted, with `suggested_uses` set to `none` and an `orphan` note.

| column | meaning |
|---|---|
| `publication_id` | from `data/publications.csv` |
| `creator_ref` | from the publication row |
| `format`, `platform` | from the publication row |
| `rights_until` | when the roster's `notes` carry `rights from posting: <n> months`, the publication's own `rights_until` (computed by `publication-tracking` from the posting date), with no roster date applied; otherwise the earlier of the publication's `rights_until` and the roster's `usage_rights_until` when both are present, whichever exists when only one does, and empty when neither does |
| `rights_status` | section 2 |
| `checked_as_of` | the `--as-of` date the status was judged on |
| `paid_reuse` | `yes`, `no` or `unknown`, read from the agreement file the roster names; never from programme section 11's default, which is a starting point for new agreements and not a grant |
| `approved_claims_present` | which approved claims (A1 = the first `[owner]` line under "Approved claims" in programme section 7, A2 the next) appear word for word in the asset's approval record, `;` separated; `none` when the record was read and none appears, and for every asset with a record when section 7 records that no claim is cleared yet; empty when there is no record to read |
| `suggested_uses` | the channel codes this asset may go to (section 5), or `none` |
| `holds` | section 3, `;` separated, or `none` |
| `notes` | section 4, `;` separated |

## 2. Rights status

| value | when | reusable |
|---|---|---|
| `active` | a written agreement date is on the roster and `rights_until` is later than the as-of date by more than the expiring window | yes |
| `expiring` | as `active`, but `rights_until` falls within the expiring window | yes, with every placement ending by `rights_until`; an extension ask is worth drafting |
| `expired` | `rights_until` is before the as-of date | no |
| `not-granted` | the roster has an `agreement_file` and an `agreement_date` but an empty `usage_rights_until` and no `rights from posting` note, which `schemas.md` section 4 reads as no rights granted | no |
| `unknown` | the creator is not on the roster, the roster row is a merged duplicate (`status` `ended` with a `merged into c-...` note), the roster has no `agreement_date`, the window runs from posting but the publication row has no `rights_until` yet, or no rights date exists anywhere | no |

## 3. Holds

A hold stops reuse even inside the rights window, until the role named clears it.

| code | meaning | who clears it, and how |
|---|---|---|
| `no-approval` | the publication names no approval record, or the record is not in `campaigns/<slug>/approvals/` | content reviewer, by running `content-approval`; the programme lead records the approval in the publication row |
| `approval-stop` | the record's verdict is `stop` | not cleared for this version; a revised version needs a new approval |
| `approval-unread` | the record has no readable `verdict:` line | content reviewer, by completing the record |
| `disclosure-missing`, `disclosure-partial`, `disclosure-unchecked` | `disclosure_seen` is `no`, `partial` or empty for the live post | programme lead, through `publication-tracking`, once the creator's fix is confirmed |
| `post-removed` | a day 1, 7 or 30 check found the post removed | programme lead, after finding out why (a platform takedown or a dispute matters here) |
| `brand-safety-exclude`, `brand-safety-review`, `creator-excluded` | the roster flags the creator | owner |
| `product-statement-without-cleared-claim` | section 7 records that no claim is cleared yet, and the approval record quotes a product statement | owner, by clearing the wording in section 7 through `program-setup`; then the content reviewer re-reviews the asset |
| `product-statements-unread` | section 7 records that no claim is cleared yet, and the approval record has no "Product statements" table to read | content reviewer, by completing the record |
| `no-channel-granted` | the agreement grants no owned channel and no paid platform the programme allows | owner, through `partnership-agreement` |

## 4. Notes

| code | meaning |
|---|---|
| `not-in-roster`, `creator-merged-into:c-...`, `no-written-agreement`, `no-rights-date` | why a status is `unknown`; a merged duplicate's publication row is re-pointed to the surviving `creator_ref` through `creator-roster` |
| `no-rights-granted` | why a status is `not-granted` |
| `rights-from-posting:N-months` | the roster says the window runs from each post's date; `rights_until` came from the publication row |
| `rights-from-posting-undated`, `rights-from-posting-not-yet-live` | why a status is `unknown` under that note: the post is live but its `rights_until` has not been recorded (the lead records it through `publication-tracking` and `creator-roster`), or the publication row has no posting time |
| `brand-has-no:...` | channels the agreement allows but programme section 3 does not list among the brand's own channels; they are left out of `suggested_uses` |
| `rights-mismatch:publication=...+roster=...+used-earlier` | the two rights dates differ; the earlier one was used; a person corrects the wrong one |
| `rights-from-roster` | the publication row had no `rights_until` |
| `days-left:N` | days from the as-of date to `rights_until`, for an expiring asset |
| `no-agreement-file`, `agreement-file-missing`, `paid-reuse-not-stated`, `paid-reuse-conflict` | why `paid_reuse` is `unknown` |
| `channels-from-agreement:...`, `channels-not-stated`, `channels-none-granted` | the owned channels the agreement lists; when not stated, all four owned channels are suggested and the programme lead confirms the scope against the signed agreement |
| `paid-platforms-not-stated`, `paid-platform-not-allowed-by-section-3:...` | how the agreement's paid platforms met programme section 3 |
| `disclosure-in-asset:on_screen+spoken` or `disclosure-not-in-asset` | whether the creator's disclosure travels inside the file; when it does not, the reuse carries the section 8 wording beside the asset |
| `code-in-asset:CODE` | the creator's code appears in the post; the owner decides whether it stays visible |
| `post-edited:reuse-the-approved-version` | the live post was edited after approval |
| `reapproval-needed-after:YYYY-MM-DD` | programme section 7 changed (decisions log, section 12) after the asset was reviewed; each plan row for it needs an approval record dated on or after that day |
| `approval-date-unknown` | neither the approval record nor the publication gave a date to compare |
| `orphan:...` | the publication is no longer in `data/publications.csv` |

## 5. Channel codes

`product-page`, `email`, `brand-social`, `retail-deck` for the owned channels, each suggested only when programme section 3 lists at least one channel of that kind; `paid:<platform>` where programme section 3 says `yes` under "paid by the brand"; `paid-with-conditions:<platform>` where it says `with conditions`. `<platform>` is the section 3 row name in lower-case kebab, for example `instagram` or `grindr-and-scruff`. A paid code appears only when `paid_reuse` is `yes`.

## 6. The plan's placements table and what the check enforces

Columns, in any order: `publication_id`, `channel`, `placement`, `start`, `end`, `removed_on`, `approval_id`, `cut`, `credit and disclosure`, `code shown`, `owner_role`.

A row fails when: the asset is not in the inventory or cannot be reused; the channel is not in its `suggested_uses`; a date is missing, malformed or the start is after the end; the end is after `rights_until`; the `approval_id` is not an approval for this creator in this campaign, has no record, or does not read `approve` (`approve-with-changes` counts as approve); the asset needs re-approval and the row's record is dated before the change; the cut is not one of `full`, `trim`, `crop`, `still`, `quote`, `other`, or is `other` with the original approval; the credit and disclosure cell is empty, `[open]` or `TBD`; `code shown` is not `yes` or `no`; `owner_role` is not a role in programme section 10; an owned row's `owner_role` is not a role section 3 names for a channel of that kind; a paid row's `owner_role` is not `owner` [pack default: paid spend is the owner's decision].

The take-down list reads every `plan-*.md` in the campaign's reuse folder and lists each row with an empty `removed_on` whose end falls within the expiring window or has passed, whose end is after the asset's current `rights_until`, or whose asset is now expired or unknown.

## 7. Where each input is read

- Programme file: section 3 (the "paid by the brand" column, and the brand's own channels line with its indented lines: each line goes under the first channel code whose words it contains, checked in the order retail or wholesale, email or newsletter, social account or handle, site or page, and takes the longest section 10 role named in it), section 7 ("Approved claims" list lines marked `[owner]`; the words inside double quotation marks when a line has them, otherwise the line without its trailing parenthesis and source tag; and program-setup's marked line `No claim is cleared yet` above the Approved heading, read as no claim cleared. Both at once, or neither, stops the script), section 10 (role names), section 12 (decisions log lines whose last field names section 7).
- Approval record: the `verdict:` line, the `reviewed_at:` date and, when no claim is cleared, the rows of the "Product statements" table that quote a statement, as `content-approval` writes them.
- Roster `notes`: `merged into c-...` and `rights from posting: <n> months` (`schemas.md` section 4).
- Agreement file: the "Owned channels the brand may reuse content on", "Paid reuse" and "Paid reuse platforms" lines of the `partnership-agreement` terms sheet. A placeholder in angle brackets counts as not stated.
