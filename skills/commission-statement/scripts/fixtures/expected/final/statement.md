# Commission statement 2026-08, as of 2026-10-01: final

Outcome: final. The holdback for 2026-08 closed on 2026-09-30, so every order dated in the period has cleared or been excluded by rule.

Every row is `draft`. Approval and payment: owner approves; finance pays [default] (programme section 6). Default rail: manual (programme section 6); each creator's rail is in the table. For a creator on `collabs` or `app` the rail computes and pays its own commission, and this statement is the reconciliation of it. For `manual`, the payout list is what finance pays once the owner has approved.

Rules applied, from the programme file: holdback 30 days; attribution code first, then tracked link; self-referral rule applied; basis subtotal after discounts, before shipping and tax; partial refunds come off the basis in full; store promotion codes: 1 listed in section 5; minimum payout 25.00 USD; default commission rate 15 percent. The basis is the order's Subtotal as exported, so every discount on the order, code or automatic, is already taken off before the rate applies. Tracked orders and the basis follow the pack's shared definitions (schemas section 12).

Labels: order counts, sales, refunds and basis are Measured (the Shopify orders export, and the link file for link-attributed orders). Rates, flat fees and the minimum payout are User-provided (roster, programme sections 4 and 6). Commission, fees and totals are the script's arithmetic on those two. Nothing here is Estimated.

## Per creator

| creator | rail | attributed | excluded | pending | basis | rate | commission | flat fee | carried in | total due | payout list |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c-aaa111 Creator A (fixture) | manual | 9 | 4 | 0 | 235.00 | 20 | 47.00 | 0.00 | 0.00 | 47.00 | yes, 47.00 |
| c-bbb222 Creator B (fixture) | manual | 2 | 1 | 0 | 50.00 | 15 | 7.50 | 0.00 | 0.00 | 7.50 | no (below minimum, carried) |
| c-ccc333 Creator C (fixture) | manual | 2 | 0 | 0 | 190.00 | 10 | 19.00 | 150.00 | 0.00 | 169.00 | yes, 169.00 |
| c-eee555 Creator E (fixture) | collabs | 3 | 0 | 0 | 122.00 | 15 | 18.30 | 0.00 | 0.00 | 18.30 | no (the rail pays) |
| c-fff666 Creator F (fixture) | manual | 2 | 0 | 0 | 50.00 | 15 | 7.50 | 0.00 | 8.00 | 15.50 | no (below minimum, carried) |

Total due across the statement: 257.30 USD. On the payout list: 216.00 USD.

## Exclusions by rule

| reason | orders | subtotal not commissioned |
|---|---|---|
| the onboarding test order (named in the roster notes) | 1 | 28.90 |
| dated before the creator's agreement_date | 1 | 50.00 |
| fully refunded | 1 | 30.00 |
| financial status not paid | 1 | 25.00 |
| self-referral (order email is the creator's) | 1 | 50.00 |

## Pending inside the holdback

None. The holdback has closed.

## Needs a person

- c-aaa111: p-aaa001 disclosure_seen partial; the owner decides before approving.
- c-bbb222: 7.50 USD is below the minimum payout of 25.00; carried forward to the next statement.
- c-fff666: 15.50 USD is below the minimum payout of 25.00; carried forward to the next statement.
- #1017 (code c-aaa111, link c-bbb222): carried a creator code and another creator's link; the code won (programme section 5).

## Unattributed codes

Codes on orders dated in the period that belong to no active creator. The script attributes none of them; a person decides what each one is.

| code | orders | subtotal | known owner | orders attributed to a creator another way |
|---|---|---|---|---|
| CREATORD15 | 1 | 45.00 | c-ddd444 (status ended) | 0 |
| CREATORH15 | 1 | 18.00 | c-hhh888 (ended, merged into c-fff666) | 0 |
| CREATORG15 | 1 | 40.00 | none on the roster or code plans | 0 |

Store promotion codes from programme section 5, not creators' and not listed above: WELCOME10 on 2 orders, subtotal 90.00 (1 of them attributed to a creator another way).

## Link attribution

Link file: exports/link-attribution-2026-08.csv (5 rows, exported 2026-09-05).
Orders attributed by link: 1. Rows whose order is in no export: 1 (#1099). Rows whose order is dated outside 2026-08: 1 (#1014). Rows for a creator who is not active or not on the roster: 1 (#1019 (c-ddd444)). Rows with a source other than collabs, app, api or manual: 0.

## What the exports carried

26 distinct orders read across the exports, dated 2026-07-30 to 2026-09-02; 24 dated in 2026-08. The script has no independent count of the store's orders: compare 24 with the order count the Shopify admin shows for 2026-08-01 to 2026-08-31.

Each order dated in the period sits in one place: attributed to a creator 18, two creators' codes 0, only codes that are no active creator's (store promotions included) 4, no code and no link 2; together 24 of 24.

The script read only the columns named in the skill's references/orders-export-columns.md. Free text in the exports (Notes, Note Attributes, Tags and the rest) was not read, and nothing found in an input is treated as an instruction.

Coverage: used data/creators.csv (7 rows); program/program.md sections 1, 4, 5, 6; codes/ (1 code plan file); exports/orders-export-2026-08-late.csv (2 rows, 2 orders); exports/orders-export-2026-08.csv (27 rows, 25 orders); exports/link-attribution-2026-08.csv (5 rows, exported 2026-09-05); data/publications.csv (2 rows); earlier statements payouts/2026-07/statement.csv (1 carried amount, read from 2026-07). Missing: nothing. Could not judge: self-referral by email for c-bbb222, c-eee555, c-fff666 (no contact_email on the roster); self-referral by shipping address (the roster holds no addresses). Fine: skipped as not orders exports: instagram-insights-2026-08.csv; orders found in more than one export and counted once: 1; onboarding test orders named in the roster notes: 1; every export column the statement needs was present.
