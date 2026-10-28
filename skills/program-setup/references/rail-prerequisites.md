# Shopify rail prerequisites and store context

Written 2026-10-20 for `program-setup`, programme sections 5 and 6. Citations: "rails N" is `../../references/shopify-affiliate-rails.md` (paths from this skill's folder). None of these items can be confirmed from outside the store: the owner or finance checks in the Shopify admin, or with the vendor, and reports what they saw (rails 7).

## Contents

1. What the research found on 2026-10-20
2. Store context to ask for first
3. Items per rail
4. How an item is recorded

## 1. What the research found on 2026-10-20

- Shopify Collabs was not accepting new creator sign-ups; creators already partnered can still use it, and the help pages do not say whether an invited creator without an account can join (rails 1).
- The orders CSV export has a "Discount Code" column and no referring-site, landing-site or UTM column; link attribution needs a separate export from the rail or the API (rails 6).
- Collabs documents no attribution window and does not say which wins when an order has both a link and a code (rails 1).
- Verify payment-provider eligibility for the actual category and markets; historical restricted-category examples are not a ruling for this store (rails 2).
- Confirm the storefront, currency, plan, payment gateway and installed apps with the owner; no store facts are bundled.

## 2. Store context to ask for first

| ask | why it matters | source |
|---|---|---|
| discount codes and automatic discounts live today, with their names | a new creator code must not collide with a live one, and every combination with an existing offer raises the discount per order | rails 7; owner evidence |
| apps already installed that issue codes, track referrals or offer discounts in pop-ups | an existing app may already be a rail, or may double-count | rails 7; owner evidence |
| the UTM values the store's email and ad campaigns already use | creator links need values that keep creator traffic apart in Shopify's marketing reports, which read UTM parameters | rails 6 |
| whether a post-purchase "how did you hear about us" question runs | it is the only view of orders that neither code nor link caught; `performance-report` points to it | no reference; the owner's answer |
| the share of guest checkouts | guest orders weaken repeat-purchase counts | rails 6, 7 |
| the free-shipping thresholds in force | the landing page and welcome kit must match the actual current thresholds | owner evidence |

## 3. Items per rail

Walked in this order; the owner may stop at the first rail whose items all verify, or choose another.

| rail | item | why | source |
|---|---|---|---|
| collabs | the Shopify plan is not Starter or Retail | Collabs is unavailable on those plans | rails 1 |
| collabs | Shopify Network Intelligence is enabled in privacy settings | Collabs requires it | rails 1 |
| collabs | Collabs shows as compatible on the App Store install screen for this store | its compatibility criteria load only in the browser | rails 1 |
| collabs | new creator sign-ups are open again, or one test invite to a creator without an account succeeds | sign-ups were closed when read | rails 1 |
| collabs | Shopify Payments is active, or which gateway processes cards, and whether Shopify has accepted the store's categories | commissions are billed through the Shopify bill | rails 2, 7 |
| collabs | target creators' countries | open-access programmes accept only US, UK and Canadian creators; no limit is stated for invites | rails 1 |
| collabs | fees, hold and payout terms: 2.9 percent on automatic payments, a 30-day default hold settable from 1 to 90 days, payouts in USD after the bill is paid, creators must switch on auto-payouts | these set section 6's schedule and section 5's holdback | rails 1 |
| collabs | W9 collection and Form 1099 | creators without a W9 are capped at a yearly payout limit | rails 1 |
| app | the vendor confirms in writing that a merchant in the actual category and markets is accepted | no app's terms on this were checked | rails 3 |
| app | the plan and its fees, monthly and per sale | entry prices run from free to large monthly fees, several with a percent of sales | rails 3 |
| app | the payout method and the account it needs (for example a PayPal Business account) | most apps pay through PayPal | rails 3, 7 |
| app | who issues Form 1099 | the brand may need to | rails 7 |
| manual | a custom app or staff access with the `write_discounts` scope, and the role that holds the token | codes are created through the Admin API or the admin | rails 4 |
| manual | `read_orders`, and `read_all_orders` if orders older than 60 days are read through the API | the API shows only 60 days without it | rails 4 |
| manual | codes cannot be imported by CSV; they are made in the admin, through the API, or with a bulk-code app | sets how `affiliate-onboarding` mints codes | rails 5 |
| manual | who exports orders each month and drops the file in `exports/`; exports over 50 orders arrive by email | the statement script reads that file | rails 6 |
| manual | how creators are paid outside Shopify, and who issues tax forms | payouts, tax forms and leak control are manual on this rail | rails 7 |

## 4. How an item is recorded

Verified: `verified YYYY-MM-DD by <role>: <what they saw> [owner]`, as an indented line under the prerequisites field of section 6. Not yet checked: `<what to check>, <role who checks> [open]`. A finding that differs from section 1 above (for example Collabs sign-ups open again) also gets a dated line in section 12.
