# What each figure in performance.csv means

Written 2026-10-20 for the performance-report skill, version 0.1.0; revised the same day to the pack's shared definitions (schemas.md section 12) and programme template 0.1.2. The script `scripts/compute_performance.py` computes every figure; this file says what each one is, which label it carries and where it comes from. The ranking metric and the thin-read floor are the owner's, read from programme section 5; every run prints both and where they came from.

## Contents

1. Labels
2. Which orders count
3. Columns of performance.csv
4. Facts the script relies on, with sources

## 1. Labels

| label | meaning here |
|---|---|
| Measured | read from the store's orders export, or from the publications log as the programme lead checked the post on the platform |
| User-provided | supplied by a person: fees and gift units in `costs.csv`, the roster's flat fee, a creator's screenshot or a public view counter typed into `reach.csv` |
| Estimated | inferred: a discount worked out from the programme's customer discount when the export has no Discount Amount column, a cost row marked `estimate`, contribution at the margin band |

A figure built from several inputs takes the weakest label among them, in the order Estimated, User-provided, Measured. Cost totals are therefore usually User-provided, because gifts and fees come from a person.

## 2. Which orders count

- Window: an order counts when its order date (Created at, else Paid at) falls on or between the window's first and last day, as the store's export writes the date.
- Attribution: the programme's section 5 model, in `scripts/attribution.py`. A code belonging to an active creator wins; a link recorded for the order in `exports/link-attribution-<YYYY-MM>.csv` is second, also only for an active creator; nothing else is attributed. Two active creators' codes on one order leave it unattributed and listed. A code belonging to no active creator is listed under unattributed codes with its owner if the code is known; the store's own promotion codes named in programme section 5 are listed apart from them, each read as the first word before any colon on its line (schemas.md section 10).
- A month in the window with no link-attribution file makes the run partial only when an active creator holds a link and some order in that month carries no active creator's code, so a link could have attributed it; otherwise the coverage line says no link could have attributed an order there (schemas.md section 10).
- The export's layout, as the pack's rule until a real export settles it (schemas.md section 10): order-level cells come from the first row of each order, and several codes in one Discount Code cell are split on commas.
- The ranked set: every creator whose pipeline stage for the campaign is `agreed` or later, plus anyone with a publication in the campaign. Creators who never reached agreement are listed apart, not ranked. A duplicate retired by a merge (status `ended`, note `merged into c-xxxxxx`) is never counted (schemas.md section 4).
- Exclusions, tested in this order, each order taking the first that applies: the onboarding test order (its name appears in the creator's roster `notes` as the entry `test order <Name>`, matched by its phrase after the entry's date (`2026-07-02 test order #1001`, as affiliate-onboarding writes it) and also in an undated older entry; schemas.md sections 4 and 12); the creator has no agreement date on the roster (not assessed; the run is partial); dated before the creator's agreement date; financial status empty; cancelled; fully refunded; not paid (anything but `paid` or `partially_refunded`); self-referral (the order's email matches the creator's roster email); sale amount unreadable; partly refunded with no refund amount. An order before the agreement date is excluded from the ranking as it is from commission, and listed under exclusions in both (schemas.md section 12).
- An order refunded to nothing (refund equal to the sale, payment state still paid or partly refunded) stays a tracked order with a zero basis, as in commission-statement (schemas.md section 12); the row's notes say how many.
- Self-referral (schemas.md section 12): section 5's rule is off only when the line's whole value, after the template text, is exactly one of off, no, none, not applied, does not apply or disabled; a word inside a sentence ("earns no commission") leaves it on. A blank line stops the run naming section 5. The same rule as commission-statement's reader.
- A tracked order (schemas.md section 12) is an attributed, paid order that no exclusion caught. Payability is not this report's question, so orders still inside the holdback are tracked; they are counted in `orders_in_holdback` because a refund may still move them.

## 3. Columns of performance.csv

One row per ranked creator, in rank order, then a TOTAL row for the campaign.

| column | what it is | label |
|---|---|---|
| `campaign_slug`, `window_from`, `window_to`, `as_of` | the run's scope | not a measurement |
| `creator_ref`, `display_name`, `primary_platform`, `tier` | from the roster | not a measurement |
| `compensation_model`, `commission_rate_pct` | the deal: roster value, else programme section 4 | not a measurement |
| `pipeline_stage`, `roster_status` | where the creator stands | not a measurement |
| `tracked_orders`, `orders_by_code`, `orders_by_link` | tracked orders and how each attributed | Measured |
| `gross_sales`, `refunds`, `net_sales` | the export's sale amount on tracked orders (Subtotal by default, programme section 4), the refunds taken off it (in full by default, or in proportion to the refunded share of the order's Total when section 4 says so), and the difference, which is the commission basis; a refund never takes an order below zero | Measured |
| `new_customers`, `repeat_customers` | among this creator's tracked orders, distinct customers whose first paid order in the exports supplied falls inside the window, and those whose first paid order is earlier (schemas.md section 12); customers are compared by a hash of the email held in memory and never written | Measured |
| `orders_customer_unknown` | tracked orders with no email or customer identifier | Measured |
| `orders_in_holdback` | tracked orders whose holdback (programme section 5) has not ended on the as-of date | Measured |
| `excluded_orders`, `excluded_detail` | attributed orders that did not count, by reason | Measured |
| `cost_commission` | the creator's rate applied to net sales, for cpa and hybrid deals; this is what the attribution implies, not the payable amount, which is commission-statement's | Measured |
| `cost_fee` | the flat fee paid, from `costs.csv`; empty (unknown, and the run partial) for a flat or hybrid deal with no fee recorded, and zero for a deal with no fee; the roster's flat fee is noted on the row but never counted | User-provided |
| `cost_gift` | gift units times unit cost from `costs.csv`; empty when not supplied | User-provided, or Estimated |
| `cost_rail_app_fee` | any rail or app fee recorded in `costs.csv`, for example a processing fee on commission payouts | User-provided, or Estimated |
| `cost_discount` | the customer discount given on tracked orders, from the export's Discount Amount; Estimated when worked out from section 4 | Measured, or Estimated |
| `cost_total`, `cost_label`, `cost_missing` | programme cost (schemas.md section 12): the sum of the five, the label it takes, and any part left out | `cost_label` says |
| `cost_per_tracked_order`, `cost_per_new_customer` | programme cost over tracked orders, and over new customers; empty (undefined) when the denominator is zero, never zero or infinite | `cost_label` says |
| `commission_return_on_sales` | the commission basis summed over tracked orders, divided by programme cost (schemas.md section 12); sales, not profit | `cost_label` says |
| `contribution_low_margin`, `contribution_high_margin` | net sales less the cost of goods at the low and the high end of the section 1 margin band, less commission, fee, gift and rail or app fee; the band is read on list price (net sales plus discount given) unless section 1's marked detail line says net revenue | Estimated |
| `pays_back` | `both`, `high_only`, `neither`, or `no_activity` when nothing was spent or sold | Estimated |
| `cpo_vs_target` | `at_or_below` or `above` the plan target passed with `--target-cpo` | User-provided target, Measured orders |
| `posts`, `posts_live_at_last_check`, `posts_removed`, `posts_edited` | the creator's campaign posts in the window and their latest day 30, day 7 or day 1 check | Measured |
| `disclosure_yes`, `disclosure_partial`, `disclosure_no`, `disclosure_not_checked`, `disclosure_yes_pct` | disclosure as recorded on each post, and the share seen in full among posts that were checked | Measured |
| `rights_active`, `rights_expired`, `rights_unknown` | posts whose `rights_until` is on or after the as-of date, before it, or empty | Measured |
| `approval_attempts` | approval records for the creator in `campaigns/<slug>/approvals/`, counted by file name | Measured |
| `rank_metric`, `rank`, `read` | the declared metric, the position under it, and `ok`, `thin` or `none` | not a measurement |
| `notes` | reasons and flags for the row, `;` separated | not a measurement |
| `reported_posts`, `views_reported`, `reach_reported`, `likes_reported`, `reported_label` | figures from `reach.csv`, summed per creator; never used in the ranking | `reported_label` says |

Ranking: lower is better for the two cost metrics, higher for the rest (including commission return on sales). A creator with no value for the metric (no orders, no new customers, or no cost) is ranked after those with one. Ties and the no-value group are ordered by more tracked orders, then lower programme cost, then `creator_ref`.

Reading the programme file: the margin band may be written "60 to 70", "60-70" or "60–70" percent; a dash is a range, never a minus sign, and a band with a dash or "to" but one figure stops the run naming section 1. A field's value is only what follows the template's text on its own line, plus indented lines that carry a source mark (`[owner]`, `[observed]`, `[default]`). Unmarked indented lines are the template's instructions and are never read as a value; a blank value or `[open]` is missing.

## 4. Facts the script relies on, with sources

From the pack's Shopify notes, `shopify-affiliate-rails.md`, read 2026-10-20:

- The orders CSV export lists Discount Code, Discount Amount, Financial Status, Fulfillment Status, Refunded Amount, Email, Name, Id, Created at, Paid at and Canceled at among its columns; a customer ID column is not listed (section 6).
- The Discount Code column shows codes and manual draft-order discounts; automatic discounts are left out, and the page does not say how several codes on one order appear (section 6). The pack's rule splits on commas (schemas.md section 10).
- Referring site, landing site and UTM parameters are not export columns; they live in the Admin API's customer-journey data and in each order's conversion summary (section 6). The conversion summary is empty when cookie tracking is blocked (a search-result excerpt of Shopify's help page), and journey data is reported missing when visitors decline tracking (developer-forum answers, not Shopify's documentation). Hence the separate link-attribution file.
- Guest checkouts without a customer record weaken repeat counts; matching on the export's Email is the fallback (section 6).
- Shopify's own marketing reports attribute UTM-tagged sales over a 30-day window under several models (section 6). They are a second view of link traffic, not this report's numbers.
- Collabs charges 2.9 percent on automatic commission payments, and several affiliate apps take a percentage of referral sales (sections 1 and 3). These enter programme cost when recorded as `rail_app_fee` in `costs.csv`.

That the orders export writes one row per line item is the pack's working rule (schemas.md section 10), not yet confirmed on a real export; the first real export settles it.
