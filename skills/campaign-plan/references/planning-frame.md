# Planning frame for a consumer-brand creator campaign

Written 2026-10-20 for the `campaign-plan` skill. Definitions, the reasoning behind the plan's defaults, and the meaning of each column the scripts read and write. The steps are in `SKILL.md`; the arithmetic is in `scripts/plan_budget.py`. Where this file says "build's reasoning", the line is the pack's argument, not a measurement for this brand.

## Contents

1. Why the objectives come in this order
2. The default mix: small creators on commission
3. Where a reach deal fits
4. The assumptions file
5. budget.csv
6. What the budget takes as given, and what it cannot see
7. Seasonal windows, launches and store sales

## 1. Why the objectives come in this order

| order | objective | why it sits here |
|---|---|---|
| 1 | tracked orders and new customers | A pay-per-sale programme pays when a tracked order arrives, and an order in the store export with a code or tracked link is the one result the programme file calls Measured (programme section 5). A code used by someone who already buys is a discount on a sale the store would have had, so new customers are counted apart, by hashed email in the orders export (pack `schemas.md` section 10). |
| 2 | content assets with reuse rights | Each post is also an asset the brand may reuse inside the rights window the agreement grants (programme section 11). Value that outlives the window is worth planning for, and `content-reuse` uses it. |
| 3 | reach | Reach and views come from platform analytics or a creator's screenshot, so they are Estimated or User-provided, never Measured. Count paid amplification only after rights and platform permission are verified (`references/rails-and-risks.md` section 1). Reach is reported apart and never ranks a creator. |

## 2. The default mix: small creators on commission

The plan's default argument for a `cpa` programme is a portfolio of nano and micro creators (tiers as in pack `schemas.md` section 4). Build's reasoning, in four parts:

- Cost follows results. Under commission, the brand's cost is the commission, the discount given and any gifts; the first two arise only when an order does. A fee is owed whatever happens.
- Platform risk is spread. Several creators on several cleared platforms means one removed post or account (risk R1) does not end the campaign.
- More assets for the same spend, each with its own rights window.
- Fit is judged, not assumed. Whether a small creator's audience matches this brand is the vetting's audience-fit score, not a property of the tier.

What the argument does not claim: that nano or micro creators sell more per follower, or at any particular rate. No source in the pack measures that for this category, so the plan never states it.

## 3. Where a reach deal fits

A `hybrid` (small fee plus commission) or `flat` (fee only) row buys a placement whatever it sells. Programme section 4 says when one is allowed and which role approves it; the plan lists each as an exception with its approval entry. The conservative case shows the exposure: fees and gifts stay fixed while orders halve. The budget block prints each fee row's break-even orders per creator by the shared rule (fee over contribution per order, rounded up, pack `schemas.md` section 12); `creator-outreach` computes the same figure for each actual offer.

## 4. The assumptions file

`campaigns/<campaign_slug>/assumptions.csv`, one row per tier and compensation (template: `assets/assumptions-template.csv`). The header is the first seven columns in this order, optionally followed by `compensation` and then `basis`.

| column | meaning | allowed |
|---|---|---|
| `tier` | follower band on the creator's primary platform | `nano`, `micro`, `mid`, `macro` |
| `creators` | how many creators the row plans | whole number, 1 or more |
| `expected_orders_per_creator` | tracked orders one creator is expected to bring over the whole live window | decimal, 0 or more; never empty |
| `orders_source` | who the figure comes from | `user` (the person's working figure) or `estimate` (with its basis named) |
| `flat_fee` | fee per creator for the deliverable set, store currency | decimal; 0 for `cpa` and `gift` |
| `gift_units` | product units shipped to each creator | whole number |
| `gift_unit_cost` | the brand's cost per unit landed at the creator: product cost plus shipping, not the list price | decimal; above 0 when units are sent |
| `compensation` | the deal for the row | `cpa`, `hybrid`, `flat`, `gift`; if empty, `hybrid` when there is a fee, else `cpa` |
| `basis` | where the orders figure comes from | free text; required when `orders_source` is `estimate` |

A good basis names a file: past redemptions of a creator code in the store's discount report, a creator's own results screenshot in `exports/`, or a previous campaign's `performance.csv`. "Typical for the industry" is not a basis.

## 5. budget.csv

`campaigns/<campaign_slug>/budget.csv`, regenerated on every run; a changed earlier file is kept as `budget-superseded-<UTC stamp>.csv`. One row per assumptions row per scenario, then a `total` row per scenario. Money is in the store currency without a symbol; every row is labelled `Estimated`.

| column | meaning |
|---|---|
| `campaign_slug`, `scenario` | the campaign; `base`, `conservative` (base orders times the factor shown), or `sale` (base orders with a store-wide sale taken before the code) |
| `tier`, `compensation`, `creators`, `orders_source` | from the assumptions row |
| `expected_tracked_orders` | creators times orders per creator, times the scenario's factor; a projection of tracked orders as pack `schemas.md` section 12 defines them |
| `revenue` | orders times revenue per order: the average order value less the customer discount (and, in the sale case, the sale), before shipping and tax |
| `commission_basis` | orders times the commission basis per order: revenue per order by default, the average order value when programme section 4 sets a before-discounts basis; summed for every row, paid commission or not |
| `discount_cost` | the creator code's discount only; a store sale's discount is not a programme cost |
| `commission_cost` | the programme section 4 rate on the section 4 basis, for `cpa` and `hybrid` rows |
| `fee_cost`, `gift_cost` | creators times fee; creators times units times unit cost |
| `rail_fee_cost` | the rail's own charge, as a percent of commission or of sales; empty when not given |
| `programme_cost` | commission plus flat fees plus gifted units at unit cost plus the discount given plus rail fees (shared definition) |
| `cost_per_tracked_order` | programme cost over expected tracked orders; empty (undefined) when no orders are expected |
| `commission_return_on_sales` | the commission basis over programme cost (shared definition) |
| `contribution_low_margin`, `contribution_high_margin` | orders times contribution per order (revenue less cost of goods less commission, cost of goods at each end of the programme section 1 margin band, on list price), less fees, gifts and rail fees |
| `label`, `basis` | `Estimated`; the assumptions the row rests on |

## 6. What the budget takes as given, and what it cannot see

- A coded order's basket before discount equals the programme's average order value. Coded baskets may be larger or smaller; the first statement shows which.
- Every tracked order is counted as the creator's. Some buyers would have bought anyway; the plan cannot separate them.
- Buyers who saw a post and bought later without the code or link do not appear (the halo). Branded search and direct visits are real and unmeasured here.
- The rail fee is what the person gives. What each rail published on 2026-10-20 is in `references/rails-and-risks.md` section 2.
- Gift cost is as given; returns, damaged parcels and second shipments are not modelled.
- Refunds are not modelled: every planned order is taken as paid and kept, so programme section 4's partial-refund rule does not enter the plan.

## 7. Seasonal windows, launches and store sales

- Seasonal window. A season (holiday gifting, Pride month, an event the brand has marked before, `references/rails-and-risks.md` section 5) fixes the live window, and the plan works backward from it. Every stage before posting (first touches, terms and the counsel review, codes, briefs, one approval round) has to fit in the lead time the dates block reports. The pack sets no lead-time rule; the person's own estimate for each stage is the test.
- Launch. When the campaign launches a product, the creator lane follows the launch: no post before the product page, the code and the link are live; product in creators' hands early enough for one approval round before the window; stock enough for the gifts and the base case's orders.
- Store sale in the window. Whether a creator code combines with a store-wide sale, or with another code such as a newsletter first-order offer identified by the owner, is set in the store's discount settings and ruled by the owner in programme section 4 (template 0.1.1, the line on combining with other discounts). If it combines, the buyer's price, the commission basis after discounts and the margin all fall; the sale case computes this. If it does not combine, a buyer may take the sale and leave the code unused, so the order carries no creator attribution; no file says how many buyers would, so that case is not computed.
- After the window. Whether codes end with the window or stay active is the owner's ruling, recorded in programme section 4 (template 0.1.2); the dates block carries it and `affiliate-onboarding` sets the end date from it.
