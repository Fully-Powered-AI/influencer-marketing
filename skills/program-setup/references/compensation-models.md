# Compensation models: pay per sale or pay for reach

Written 2026-10-20 for `program-setup`, programme section 4. Citations name a section of the pack's dated references, read 2026-10-20 (paths are given from this skill's folder): "notes N" is `../../references/platform-and-compliance-notes.md`, "rails N" is `../../references/shopify-affiliate-rails.md`. This file carries no market rate for commissions or fees, because none was sourced: any rate or fee anchor in the programme file is the owner's.

## Contents

1. The four models
2. What each costs the brand
3. Rail fees
4. Why the default proposal is `cpa` with a customer discount code
5. Where the creator channel sits among the store's channels
6. The questions that decide it
7. Worked example
8. Not carried here

## 1. The four models

| model (programme value) | the brand pays | the creator gets | the brand's risk | fits this programme when |
|---|---|---|---|---|
| `cpa` | a commission on the basis of each tracked order, the discount the code gives the customer, and the product sent to try | a share of every sale their code or link brings while the code is live | low: a post that sells nothing costs only the product sent; larger creators often refuse it | the default: spend follows Measured orders (programme section 5) |
| `flat` | a fee per deliverable set, whatever it sells, plus the product sent | a known fee | all of it: cost per tracked order is known only after the period | the audience is right and the creator will not work on commission, or the brand wants content to reuse where sections 3 and 11 allow |
| `hybrid` | a smaller fee plus the commission | part certainty, part upside | the fee, less than a flat deal's | a commission-only offer was refused and the owner approves the exception (section 4) |
| `gift` | the product sent, and the discount if a code is issued | the product | small and uncertain: the post rate is unknown | nano creators, seeding, or testing fit before a paid deal; disclosure is still required, because free product is a material connection (notes 1, 16 CFR 255.5) |

## 2. What each costs the brand

The per-order arithmetic is the pack's shared definition, `../../references/schemas.md` section 12 ("Per-order arithmetic for offers and plans"), so this skill, `creator-outreach` and `campaign-plan` give the same figures for the same inputs. Vocabulary, per tracked order unless stated:

| symbol | meaning | from |
|---|---|---|
| L | average order value as section 1 states it, before discounts | programme section 1 |
| m | gross margin, read on list price unless section 1 says otherwise; computed at both ends of the band | programme section 1 |
| D | discount on the order: L times the discount fraction, or a fixed amount; the line says which (`15 percent`, `fixed 5.00 USD`) | programme section 4 |
| c | the deal's commission rate: the programme rate for `cpa` and `hybrid`, none for `flat` and `gift` | programme section 4 |
| F | fee per deliverable set, flat or hybrid | the owner, per deal |
| G | product sent to one creator, shipping included | the owner |

Formulas (`scripts/compare_models.py` is the one place in this skill they run):

- revenue per order: L minus D
- commission basis: revenue per order (the template default, subtotal after discounts); L if section 4 says before discounts
- cost of goods per order: L times (1 minus m); when section 1 states the band on net revenue, revenue per order times (1 minus m)
- commission per order: the basis times c
- contribution per tracked order: revenue per order, minus cost of goods, minus commission
- highest commission rate before a tracked order loses money: (revenue per order minus cost of goods) divided by the basis, rounded down
- fixed cost per deliverable set: `cpa` G; `flat` F plus G; `hybrid` F plus G; `gift` G
- tracked orders to cover the fixed cost: the fixed cost divided by the contribution per tracked order at the deal's own commission, rounded up

If creator codes combine with other discounts (the section 4 line on combining), D is the combined discount on a typical coded order; pass that figure to the script to see what stacking costs. The API records combination as the `combinesWith` field of a code discount (rails 4); how an order carrying several codes appears in the orders export is not documented (rails 6), so a combined order may be hard to attribute to one creator.

After a campaign, cost per tracked order is the programme cost (commission, flat fees, gifted units, discounts given and any rail or app fee) divided by tracked orders, as schemas.md section 12 defines both. It is Measured only from the orders export and `costs.csv` for the window.

## 3. Rail fees

Rail and app fees are programme costs, recorded in `campaigns/<campaign_slug>/costs.csv` (schemas.md section 12), not part of the per-order arithmetic above. What the references record:

| rail | fee | source |
|---|---|---|
| Shopify Collabs | 2.9 percent processing fee on every automatic commission payment | rails 1 |
| an affiliate app | several plans add a percent of referral or affiliate sales (for example 2 percent on one plan, 3 percent on others), on top of a monthly plan price | rails 3, table |
| manual (codes plus the pack's statement script) | no rail fee in the references; the payout provider's fee is not in the references | rails 7 |

## 4. Why the default proposal is `cpa` with a customer discount code

- Paid reuse requires both a rights grant and current platform permission for the category and market. Do not include paid amplification in forecast reach unless those dependencies are verified.
- A code survives what a link loses. The orders export carries a "Discount Code" column and no referrer, landing-site or UTM column, and journey data goes missing when visitors decline tracking (rails 6). A code is the attribution the export alone can show.
- The discount gives the audience a reason to use the code and the creator something to offer.
- Pay per sale keeps spend in proportion to Measured orders, the only outcome the programme counts (section 5).
- What the default costs: the discount is given on every coded order, including orders that would have happened anyway, and codes can leak to coupon sites; Collabs can open a dispute for a leaked code (rails 1). The self-referral rule and the "unattributed codes" list in `commission-statement` exist for this.

## 5. Where the creator channel sits among the store's channels

A store weighs each channel by what an acquired order costs against what that order earns, and the creator programme competes for the same money as the brand's email, search, television and advertising. Two things set this brand apart. Its paid social reach is narrow (section 4 above), so creators carry more of the reach a store would otherwise buy. And a `cpa` deal is the one channel where the cost arrives after the order, not before it. The comparison only means something against the store's own figures: what an order from another channel costs today, and how often a first order becomes a second (the orders export can show repeats by email, rails 6). Both are the owner's or finance's figures, User-provided, or absent. A monthly ceiling on total creator spend is a campaign decision, made in `campaign-plan`.

## 6. The questions that decide it

1. What is the programme buying first: tracked orders, or reach and content? Orders point to `cpa`. Content to reuse on the brand's own channels points to a `flat` deal with usage rights, and only where sections 3 and 11 allow the reuse.
2. Can the margin carry the discount and a commission, and how does that compare with what the store already pays for an order elsewhere? The script prints the highest commission rate before an order loses money at both ends of the band. A rate close to that ceiling leaves nothing for the product sent, rail fees and returns; the store's cost per order from other channels is the owner's figure.
3. Will the creators the programme wants accept commission only? Setup cannot know; the answer arrives in outreach. Settling now when a `hybrid` or `flat` deal is allowed, and which role approves it, means a refusal does not stall a negotiation.

## 7. Worked example

Illustrative inputs, each labelled. Average order value 34.00 (Estimated: invented example, not measured store data). Margin band 55 to 65 percent on list price (Estimated: illustrative, not the brand's). Discount 15 percent and commission 15 percent (illustrative). Flat fee 300.00 and hybrid fee 100.00 (illustrative). No product sent.

Output of `scripts/compare_models.py` on these inputs, Estimated; `scripts/fixtures/run_fixtures.sh` checks that the script still prints these figures:

| figure | at 55 percent margin | at 65 percent margin |
|---|---|---|
| discount given to the customer | 5.10 | 5.10 |
| revenue per order | 28.90 | 28.90 |
| commission basis | 28.90 | 28.90 |
| cost of goods per order | 15.30 | 11.90 |
| commission at the programme rate (cpa and hybrid) | 4.34 | 4.34 |
| contribution per tracked order, cpa or hybrid | 9.27 | 12.67 |
| contribution per tracked order, flat or gift | 13.60 | 17.00 |
| highest commission rate before an order loses money (percent, rounded down) | 47.0 | 58.8 |
| flat: tracked orders to cover 300.00 | 23 | 18 |
| hybrid: tracked orders to cover 100.00 | 11 | 8 |

On these inputs a creator on `cpa` costs nothing until an order arrives, while the 300.00 flat deal needs 18 to 23 tracked orders before it has paid for itself.

## 8. Not carried here

- Market rates for commissions or flat fees by tier: none sourced. An anchor in section 4 is the owner's figure, labelled User-provided.
- Payout-provider fees for the manual rail, and tax treatment beyond what rails 1 records for Collabs (W9 collection, Form 1099): finance and counsel.
