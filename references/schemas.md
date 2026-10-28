# Shared shapes: the workspace, the identifiers and the CSV files

Written 2026-10-20 as the contract between the skills in this pack. Every skill reads and writes the same files in the same shapes, so a creator found by one skill is the same row the next skill picks up. The canonical runtime copy ships inside `skills/creator-roster/references/schemas.md`; this file is the build-time source. If the two ever differ, the roster skill's copy is the one the scripts enforce.

## 1. The workspace

Keep one runtime workspace outside the installed package. Every skill takes its path as the first input (default: the current directory) and never writes outside it. Nothing in it is sent anywhere by a skill.

```
<workspace>/
  program/program.md                 the programme file, read first by every skill (template: skills/program-setup/assets/program-template.md)
  data/creators.csv                  the roster: one row per creator, the system of record
  data/pipeline.csv                  outreach and delivery stages, one row per creator per campaign
  data/publications.csv              live posts and their checkpoints
  data/longlist-YYYY-MM-DD.csv       what discovery found on a date
  data/shortlist-YYYY-MM-DD.csv      what vetting scored on a date
  campaigns/<campaign_slug>/plan.md
  campaigns/<campaign_slug>/briefs/<creator_ref>.md
  campaigns/<campaign_slug>/approvals/<approval_id>.md
  campaigns/<campaign_slug>/report-YYYY-MM-DD.md
  codes/code-plan-YYYY-MM-DD.csv     codes to mint or minted, with their status
  payouts/<period>/statement.csv     commission owed per creator for the period
  payouts/<period>/payout-list.csv   what goes to the payout rail
  payouts/<period>/statement.md      the readable statement
  exports/                           files the person drops in: Shopify orders exports, platform analytics, creator-supplied screenshots
  agreements/<creator_ref>-YYYY-MM-DD.md   drafted or reviewed agreement terms (never a signed instrument)
  agreements/<creator_ref>-YYYY-MM-DD-r<n>.md   a later version the same day
  data/scores-YYYY-MM-DD.csv         vetting's confirmed scores with evidence (shape: skills/creator-vetting/references/scoring.md section 9)
  exports/posts-YYYY-MM-DD.csv       recent posts gathered for vetting (same reference)
  exports/incoming-terms-<creator_ref>-YYYY-MM-DD.txt   incoming agreement paper pasted as text (partnership-agreement)
  exports/<approval_id>-caption.txt, exports/<approval_id>-transcript.txt   what content-approval reviewed
  exports/link-attribution-<period>.csv   link attribution exported from the rail or the API (section 10)
  campaigns/<campaign_slug>/assumptions.csv, budget.csv, budget-superseded-<UTC stamp>.csv   (skills/campaign-plan/references/planning-frame.md sections 4 and 5)
  campaigns/<campaign_slug>/outreach/<creator_ref>.md, outreach/replies.md   outreach drafts, never sent (creator-outreach)
  campaigns/<campaign_slug>/welcome/<creator_ref>.md   the welcome kit (affiliate-onboarding)
  campaigns/<campaign_slug>/reuse/inventory.csv, reuse/plan-YYYY-MM-DD.md   (skills/content-reuse/references/inventory-codes.md section 1)
  campaigns/<campaign_slug>/performance.csv, performance-<as_of>.csv, costs.csv, reach.csv, results-notes/<creator_ref>-YYYY-MM-DD.md   (skills/performance-report/references/metric-definitions.md)
  codes/payloads-YYYY-MM-DD/<creator_ref>-<CODE>.json   Admin API request bodies, written dry (affiliate-onboarding)
```

### 1.1 The workbook (the human view)

The initial workflow uses CSVs and an optional workbook, without a CRM integration. The three living files, `data/creators.csv`, `data/pipeline.csv` and `data/publications.csv`, are the contract every script reads and writes. For people, the roster skill keeps a local Excel workbook beside them, `data/creator-programme.xlsx`, with one sheet per file, named `creators`, `pipeline` and `publications`, each sheet's first row being the exact header below (a local workbook view of the shared CSV files). Two commands in `creator-roster` move data between the two: `export-xlsx` builds the workbook from the CSVs, and `import-xlsx` reads an edited workbook back into the CSVs, reporting every changed cell. Both are standard-library Python (a `.xlsx` is a zip of XML). The rule for a person: edit the workbook, run `import-xlsx`, then run any skill; after a skill has written, run `export-xlsx` so the workbook is current. The workbook carries no formulas; a regenerated workbook loses any formatting a person added, so the workbook is a view, never the only copy. No other skill reads or writes the workbook. Shopify Collabs or an affiliate app keeps its own creator list; the workbook mirrors it and the `rail` column says where the code and payout live. A new creator typed into the workbook receives its `creator_ref` from `import-xlsx` and from nowhere else; the workbook carries an export stamp in its custom properties, which is how `import-xlsx` refuses a workbook older than the CSVs and `export-xlsx` refuses to overwrite edits nobody imported. No other skill adds workbook logic.

Dates in file names and in cells are ISO, `YYYY-MM-DD`. Times, when needed, are UTC `YYYY-MM-DDTHH:MMZ`.

## 2. Identifiers

| identifier | shape | assigned by | rule |
|---|---|---|---|
| `creator_ref` | `c-` followed by six lowercase letters or digits, for example `c-7k2m9q` | `creator-roster` at first insert | Stable for life. Never a handle; handles change and are reused. Every other file refers to a creator by this. |
| `campaign_slug` | lowercase kebab, starting with `YYYY-MM-`, for example `2026-12-holiday-tote` | `campaign-plan` | Folder name under `campaigns/`. |
| `code` | upper case, letters and digits only, 4 to 20 characters, per the scheme in `program.md` section 5 | `affiliate-onboarding` | Collision-checked against `data/creators.csv` and `codes/`. One active code per creator unless the programme says otherwise. |
| `approval_id` | `<campaign_slug>--<creator_ref>--<n>` with `n` the attempt number from 1 | `content-approval` | A re-review of revised content is a new `n`, never an overwrite. |
| `publication_id` | `p-` followed by six lowercase letters or digits | `publication-tracking` | One per live post. |
| `period` | `YYYY-MM` | `commission-statement` | A calendar month of order dates, closed after the holdback in `program.md` section 5. |

## 3. CSV rules every script follows

- UTF-8, comma separated, header row exactly as listed, in this order. A script refuses a file whose header differs and says which column is missing or extra.
- Empty cell means unknown. Never `N/A`, `null` or a dash.
- Lists inside a cell are separated by `;` with no spaces, for example `instagram:@handle;x:@handle`.
- Money is a plain decimal in the store currency with no symbol, for example `34.00`. Percentages are plain decimals of percent, for example `15` means fifteen percent.
- A script never deletes a row. Status changes and corrections append or update in place; `creators.csv` keeps `notes` for the reason.
- Every write is preceded by a read of the whole file and followed by the script printing how many rows it read, added and changed.

## 4. `data/creators.csv`

The roster. One row per creator across all campaigns.

| column | meaning | allowed values |
|---|---|---|
| `creator_ref` | stable id | see section 2 |
| `display_name` | public name or handle to show in reports | free text |
| `primary_platform` | where they matter most | `instagram`, `tiktok`, `youtube`, `x`, `onlyfans`, `reddit`, `podcast`, `newsletter`, `bluesky`, `threads`, `other` |
| `primary_handle` | handle on the primary platform, with `@` | free text |
| `profile_url` | public profile URL on the primary platform | URL |
| `other_platforms` | `platform:@handle` list | `;` list |
| `tier` | by followers on the primary platform | `nano` (under 10,000), `micro` (10,000 to 49,999), `mid` (50,000 to 499,999), `macro` (500,000 and up) |
| `followers_primary` | count as last observed | integer |
| `followers_as_of` | date of that observation | date |
| `engagement_rate_pct` | as computed by `creator-vetting` | decimal |
| `engagement_as_of` | date of that computation | date |
| `niche_tags` | what they make content about | `;` list of lowercase tags |
| `audience_fit_score` | total from the latest vetting | integer 0 to 30 |
| `brand_safety_flag` | from vetting or later review | `none`, `review`, `exclude` |
| `contact_path` | how they can be reached | `email`, `dm`, `agent`, `form`, `unknown` |
| `contact_email` | only if public or given by the creator | email |
| `status` | where the relationship stands | `prospect`, `contacted`, `negotiating`, `agreed`, `active`, `paused`, `declined`, `ended`, `excluded` |
| `compensation_model` | the deal | `cpa`, `flat`, `hybrid`, `gift`, `none` |
| `commission_rate_pct` | for `cpa` and `hybrid` | decimal |
| `flat_fee` | for `flat` and `hybrid`, per deliverable set, store currency | decimal |
| `code` | their active discount code | code |
| `affiliate_link` | their tracked link | URL |
| `rail` | where the code and payout live | `collabs`, `app`, `manual`, `none` |
| `agreement_date` | date terms were agreed in writing | date |
| `agreement_file` | path under `agreements/` | path |
| `usage_rights_until` | last day the brand may reuse their content | date |
| `exclusivity_until` | last day of any category exclusivity | date |
| `first_campaign` | first `campaign_slug` | slug |
| `last_activity` | date of the most recent row change in any file | date |
| `notes` | reasons and context, dated entries separated by `;` | free text |

Rules for the roster: a duplicate retired by a merge keeps `status` `ended` with a note `merged into c-xxxxxx`, and every script treats such a row as inactive and never counts it (a `merged` status is a candidate for version 0.2). An empty `usage_rights_until` or `exclusivity_until` with a non-empty `agreement_file` means none was granted, unless `notes` carry `rights from posting: <n> months` (a window that runs from the posting date, set by the programme lead through `creator-roster` when the post goes live); empty with no agreement means unknown. A creator who asked not to be approached again carries `do not contact` in `notes`, and no outreach draft is written for them. Every `notes` entry is dated, `YYYY-MM-DD <text>`, including the fixed entries below, which readers match by their phrase after the date. Fixed `notes` entries other skills read: `merged into c-xxxxxx`, `do not contact`, `test order <Name>` (the onboarding test order, excluded from commission and from reports), `rights from posting: <n> months` (written by the programme lead through `creator-roster` at the agreement's hand-off when the usage window runs from the posting date; it concerns usage rights only, never exclusivity; a usage window stated as a duration with no start (for example "6 months, organic reuse only") runs from posting, and partnership-agreement's printed hand-off writes this note for it; `publication-tracking` dates every post from its own posting date plus the window and writes that post's `rights_until`, and the roster's `usage_rights_until` carries the latest of them; `creator-roster` reports such a row with no live post as "window from posting, not yet live", not as none granted; `content-reuse` reads each post's own date).

## 5. `data/pipeline.csv`

One row per creator per campaign, updated as the stage moves.

| column | allowed values |
|---|---|
| `campaign_slug` | slug |
| `creator_ref` | ref |
| `stage` | `identified`, `first_touch`, `followed_up`, `replied`, `negotiating`, `agreed`, `declined`, `no_response`, `onboarded`, `briefed`, `content_due`, `content_submitted`, `approved`, `live`, `closed` |
| `stage_date` | date the stage was reached |
| `next_action` | one line, what a person does next |
| `next_action_date` | date |
| `owner_role` | the role that acts, from `program.md` section 10, never a person's name |
| `last_message_date` | date of the last message either way |
| `offer_summary` | one line, for example `cpa 15 pct, code 15 pct off, no fee` |
| `notes` | dated entries, `;` separated |

Rules for the pipeline: `followed_up` covers every follow-up, and the count is kept in `notes` as `YYYY-MM-DD followed_up N`, written by `creator-outreach`'s pipeline script. `briefed` is recorded by the programme lead after the brief is sent, not by `creator-brief`. `content_submitted`, `approved` and a return to `content_due` are recorded by the programme lead through the same pipeline script after `content-approval` has written its record; `content-approval` moves no stage. `onboarded` is written by `affiliate-onboarding`'s recording script once the code has passed its test order.

## 6. `data/publications.csv`

| column | allowed values |
|---|---|
| `publication_id` | id |
| `campaign_slug` | slug |
| `creator_ref` | ref |
| `platform` | as in the roster |
| `post_url` | URL |
| `posted_at` | UTC time |
| `format` | `video`, `reel`, `story`, `post`, `thread`, `newsletter`, `podcast`, `live`, `other` |
| `disclosure_seen` | `yes`, `no`, `partial` |
| `disclosure_form` | `;` list of `caption`, `spoken`, `on_screen`, `platform_tool` |
| `code_in_post` | the code as it appears, or empty |
| `link_in_post` | the link as it appears, or empty |
| `approval_id` | the approval this post was published under |
| `check_day1`, `check_day7`, `check_day30` | `live`, `removed`, `edited`, `not_checked` |
| `rights_until` | date, copied from the roster at publication |
| `notes` | dated entries |

Rules for publications: `notes` entries follow `skills/publication-tracking/references/notes-vocabulary.md`; in particular a reached fee milestone is the entry `YYYY-MM-DD fee milestone reached by <role>: <text>`, matched up to the colon, which `commission-statement` reads; `part` and `held` entries make nothing due. `disclosure_seen`, `disclosure_form`, `code_in_post` and `link_in_post` hold the latest observation; the first live check in `notes` keeps the post as first seen. Code and link are compared with what was issued for that post at the time it was recorded, not with the roster's current values.

## 7. `data/longlist-YYYY-MM-DD.csv` (discovery output)

`display_name, platform, handle, profile_url, followers, followers_source, niche_tags, found_via, already_talks_about_category, contact_path, notes`

`followers_source` is `profile`, `search_result`, `media_kit` or `estimate`; for the pack's number labels, `profile` is Measured, `media_kit` is User-provided, `search_result` and `estimate` are Estimated. Longlist `notes` use the keys in `skills/creator-discovery/references/search-recipes.md` section 9, and `creator-vetting` carries `notes` to the shortlist unchanged. `found_via` names the search recipe. `already_talks_about_category` is `yes`, `no` or `unknown`.

## 8. `data/shortlist-YYYY-MM-DD.csv` (vetting output)

All longlist columns, then: `audience_fit, engagement_quality, authenticity, brand_safety, sponsored_track_record, contactability` (each an integer 0 to 5), `total` (0 to 30), `confidence` (`high`, `medium`, `low`), `verdict` (`engage`, `negotiate`, `skip`, `exclude`), `reasons` (one line), `scored_as_of` (date), `creator_ref` (filled when the roster has the creator, else empty), `tier` (from `followers`, by the bands in section 4), `engagement_rate_pct` (as computed, or empty when no posts were supplied), `brand_safety_flag` (`none`, `review` or `exclude`, as vetting judged it; the roster copies it). A `skip` row may carry an empty `total` when a line could not be judged.

## 9. `codes/code-plan-YYYY-MM-DD.csv`

`creator_ref, code, discount_type, discount_value, applies_to, starts_at, ends_at, usage_limit, once_per_customer, status, minted_at, minted_by, notes`

`discount_type` is `percentage` or `fixed_amount`. `status` is `planned`, `minted`, `active`, `disabled`, `collision`. `minted_by` is `collabs`, `app`, `api`, `admin_ui` or empty. An empty `usage_limit` or `ends_at` means none when the row's `notes` say so; otherwise it means not yet decided.

## 10. Shopify orders export, as read by `commission-statement` and `performance-report`

The scripts read the orders CSV that Shopify's admin exports and look for these columns by name, case-insensitively. The exact names Shopify uses are recorded in `references/shopify-affiliate-rails.md`; if a column is absent the script says so and continues with what it has, and the output's coverage line names what was missing.

| what the script needs | the export column it looks for first | fallback |
|---|---|---|
| order identifier | `Name` | `Id` |
| order date | `Created at` | `Paid at` |
| payment state | `Financial Status` | none; rows without it are `unknown` and excluded from commission |
| fulfilment state | `Fulfillment Status` | optional |
| the discount code used | `Discount Code` | none |
| sale amount for the commission basis | `Subtotal` (after discounts, before shipping and tax) | `Total` with a coverage note |
| refunds | `Refunded Amount` | none; a missing column is reported |
| the tracked link | none: the orders CSV export carries no referring-site or landing-site column (`shopify-affiliate-rails.md` section 6); link attribution comes from the optional `exports/link-attribution-<period>.csv` below, exported from the rail or the Admin API by a person | the code alone |
| repeat purchase | `Email` hashed before use, or `Customer Id` | none |

Optional link-attribution file, `exports/link-attribution-<period>.csv`: `order_name, creator_ref, source, exported_at`, where `source` is `collabs`, `app`, `api` or `manual`. A person exports it from the rail's own report or from the Admin API's customer-journey data; the scripts join it on `order_name` to the orders export. Without it, only codes attribute, and the coverage line says so; the run is partial only when some order in the period carries no active creator's code (so a link could have attributed it) and an active creator holds a link; a period with no such order stays complete. A store promotion code listed in programme section 5 is read as the first word before any colon on its line.

Attribution order, as the programme file declares it: a matching code wins; a tracked link without a code is second; nothing else is attributed. An order that carries a code belonging to no active creator is listed under "unattributed codes" for a person to look at.

Two layout points of the orders export are not yet confirmed on a real store export and are read the same way by every script until they are: order-level cells are taken from the first row of each order (line-item rows that repeat them are ignored for order-level values), and several codes in one `Discount Code` cell are split on commas. `references/shopify-affiliate-rails.md` records what the documentation says; the first real export settles both.

## 11. `payouts/<period>/statement.csv`

`period, creator_ref, display_name, rail, orders_attributed, orders_excluded, gross_sales, refunds, commission_basis, commission_rate_pct, commission_due, flat_fee_due, total_due, holdback_until, status, notes`

`status` is `draft`, `approved`, `sent_to_rail`, `paid`, `disputed`. A skill moves a row only to `draft` or `approved`; `sent_to_rail` and `paid` are a person's entries after the fact.

`payouts/<period>/payout-list.csv`: `period, creator_ref, display_name, rail, amount, currency, statement_status, notes`, as `commission-statement` writes it.

## 12. Shared definitions

Every script that computes one of these uses this definition and no other, so a plan, an offer, a statement and a report agree.

- **Attribution model line** (programme section 5): its value is the full sentence the owner accepted or changed, never "as written"; a plan copies the sentence; a reader that finds a blank or "as written" treats the line as missing.
- **Tracked order**: an order in the store export whose payment state is paid or partially refunded, not cancelled (no cancellation date), attributed by code first and by the link file second (section 10), outside the holdback as of the run date when payability is the question, not a self-referral under programme section 5 (the self-referral rule is on unless the value of its line, after the template text, is exactly one of `off`, `no`, `none`, `not applied`, `does not apply`, `disabled`, matched as the whole value and never as a word inside a sentence; a blank line is missing and stops the run naming section 5), not the onboarding test order (the order name recorded in the creator's roster `notes` as `test order <Name>` by `affiliate-onboarding`), and dated on or after the creator's `agreement_date`. An order before the agreement date is excluded from commission and from the performance ranking alike, and listed under exclusions in both.
- **Commission basis**: as programme section 4 states it; the default is the export's subtotal after every discount, before shipping and tax, with the refunded amount subtracted in full unless section 4 says in proportion; an order refunded to nothing stays a tracked order with a zero basis.
- **Programme cost for a window**: commission due on tracked orders, plus flat fees paid, plus gifted units at the unit cost in `costs.csv`, plus the customer discount given on tracked orders, plus any rail or app fee recorded in `costs.csv`.
- **Cost per tracked order**: programme cost divided by tracked orders; undefined (shown as such) when tracked orders are zero.
- **Commission return on sales**: the sum of the commission basis over tracked orders divided by programme cost.
- **New customer**: a hashed customer email whose first paid order in the exports supplied falls inside the window; repeat otherwise; unknown when the export carries no customer identifier. The credit goes to the creator attributed on that first order, whatever brought earlier unpaid orders.
- **Per-order arithmetic for offers and plans**: average order value as programme section 1 states it, before discounts, in the store currency; cost of goods per order = average order value times (1 minus the gross margin), the margin read on list price unless section 1 says otherwise; revenue per order = average order value times (1 minus the customer discount) for a percentage discount, or average order value minus the fixed amount capped at the order value; when a store-wide sale overlaps the window the sale is taken first; commission per order = rate times the commission basis per order as programme section 4 states it (on the default basis that equals revenue per order); contribution per order = revenue per order minus cost of goods minus commission minus any per-order rail or app fee the programme states, none when it states none. "Net revenue" in programme section 1 means revenue per order after the customer discount. A flat fee breaks even at fee divided by contribution per order, rounded up. Flat fees count as paid in a performance report and as due in a statement, so the two can differ inside one window and each says which it counts.
- **Reach, views and likes** are never part of a ranking in a performance report; there they are reported apart as User-provided or Estimated. In vetting, a count read directly off a public page on a stated date (followers, likes, comments, views on a post) is Measured for the vetting signal it feeds, as the contract's label rule says.
