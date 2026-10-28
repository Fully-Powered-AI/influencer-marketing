# Statement rules: what the script applies, and where each rule comes from

Written 2026-10-20 for `scripts/commission_statement.py` (pack version 0.1.0); revised the same day for the shared definitions in `references/schemas.md` sections 4 and 12, programme template 0.1.2, and the lead's rulings on the reviews. This file lists rules and definitions; the steps are in `SKILL.md`. Where a rule is the programme's, the number lives in `program/program.md` and is read at run time; where it is the build's own default, the constant sits at the top of the script and is named here so the owner can change it. Origins: **programme** (the owner's programme file), **schemas** (the pack's `references/schemas.md`, 2026-10-20; section 12 holds the definitions every script shares), **brief** (the build brief for this skill), **build** (a default chosen while building, for the owner to confirm).

## Contents

1. Which orders count
2. Attribution
3. Exclusions, in the order they are tested
4. The basis, stacked discounts and refunds
5. Commission, flat fees, carried amounts and the minimum
6. Outcomes: final, preview, partial
7. The statement's columns
8. The payout list's columns
9. Worked example (the fixture)

## 1. Which orders count

| rule | origin |
|---|---|
| A programme value is the text after the template's own wording on the field's line, plus any indented line under it that carries `[owner]`, `[observed]` or `[default]`. An unmarked indented line is template text (for example the section 6 instruction on how to write the minimum) and is never read as a value. A blank value or `[open]` counts as missing, and so does `as written` or `as above` on the attribution line. A store promotion code is the first word of its line, before any colon (`WELCOME10: newsletter first-order offer [owner]` names `WELCOME10`); a line may list several, separated by commas. | programme template 0.1.2; schemas section 12 |
| The run date may not be later than today, judged in UTC like the rest of the pack's scripts. | lead's ruling |
| A period is a calendar month of order dates, `YYYY-MM`. | schemas section 2 |
| The order date is the `Created at` date as exported (the store's local date); `Paid at` only if `Created at` is absent, and the run is then partial. | schemas section 10 |
| An order appears once even when it sits in two exports; the first file in name order wins. | build |
| Rows sharing an order `Name` within one file are line items of one order; order-level cells (status, code, subtotal, refund, email, dates) come from its first row only. | schemas section 10 |
| The script reads every CSV in `exports/` that has an order identifier column and at least two known order columns; other CSVs are listed as skipped. | build (`SIGNATURE_MIN`) |

## 2. Attribution

The declared model is single-touch and rule-based: each order gets at most one creator, by the first rule that fits, and nothing is shared or weighted across creators. A platform or rail that reports its own attributed sales may claim the same order under a different model; the statement does not adjust to it.

| rule | origin |
|---|---|
| An order carrying the code of an active creator belongs to that creator. Codes come from the roster's `code` and from code-plan rows with status `minted` or `active`. Matching ignores case. Several codes in one cell are split on commas. | programme section 5; schemas section 10; build (code-plan states) |
| An order with no active creator's code, listed in `exports/link-attribution-<period>.csv` against an active creator, belongs to that creator. | programme section 5; schemas section 10 |
| With no link file for the period, only codes attribute. If an active creator holds a tracked link (`affiliate_link` on the roster) and some order dated in the period carries no active creator's code, that creator's row is not assessed and the run is partial, as in `performance-report`. With no such order (an empty month, or every order carrying a creator code) the file could change nothing and is not a gap. | schemas section 10 |
| Nothing else attributes: not views, reach, screenshots or a creator's own report. | programme section 5 |
| A code that belongs to no active creator (an ended creator's code, a code nobody recognises) goes to the unattributed list with its order count and subtotal; the script assigns it to no one. A code the programme lists as a store promotion is shown apart, below that list. | schemas section 10; programme section 5 |
| A row retired by a merge (`ended`, with a `merged into c-xxxxxx` note) is never active: its code goes to the unattributed list naming the row it was merged into, and a carried amount or fee milestone on it goes to a person to move. | schemas section 4 |
| An order carrying codes of two active creators, or listed in the link file against two creators, is not attributed and goes to a person. | build |
| Programme section 5 may instead say "codes only"; the link file is then ignored. Any other declared model stops the run (exit 1). | build |

## 3. Exclusions, in the order they are tested

An attributed order gets the first reason that applies, so each excluded order is counted once. What passes every test is a tracked order in the sense of schemas section 12.

| order | reason | test | origin |
|---|---|---|---|
| first | onboarding test order | the order's `Name` appears in the creator's roster `notes` as the entry `test order <Name>`, which `affiliate-onboarding` writes as its own dated entry with the export's `#` (for example `2026-07-02 test order #1001`); an undated legacy entry `test order #1001` is read too | schemas sections 4 and 12 |
| 0 | not assessed | the creator has no `agreement_date`, so the start of eligibility is unknown; the run is partial | brief (rule needs the date) |
| 1 | before agreement | order date earlier than the creator's `agreement_date` | brief |
| 2 | financial status unknown | `Financial Status` empty or the column missing | schemas section 10 |
| 3 | cancelled | `Canceled at` filled, when the column exists | schemas section 12 |
| 4 | fully refunded | `Financial Status` is `refunded` | brief |
| 5 | not paid | any status other than `paid` or `partially_refunded`; the rails file names `authorized` as one, and the full list of statuses is not in the references (verify on the first real export) | brief; schemas section 12 |
| 6 | self-referral | the order email equals the creator's `contact_email`, ignoring case; checked only when the roster holds that email. The rule is off only when section 5's value, after the template text and without its mark, is exactly one of off, no, none, not applied, does not apply or disabled; the whole value is compared, never a word inside a sentence, so "an order the creator places earns no commission" keeps the rule on. `performance-report` holds the same list | programme section 5; brief; schemas section 12 |
| then | pending | order date plus the holdback days is later than the run date | programme section 5 (holdback); brief |
| else | cleared | counts toward commission; an order refunded down to a zero basis is cleared with a zero basis, not excluded | schemas section 12 |

## 4. The basis, stacked discounts and refunds

| rule | origin |
|---|---|
| The basis is the order's `Subtotal`: after discounts, before shipping and tax. Section 4 may instead name the order total. | programme section 4; schemas section 10 |
| Stacked discounts: an order can carry a creator code together with another code or an automatic discount when the store's combination settings allow it. Whatever combined, the exported `Subtotal` is already net of every discount, so commission is paid on what the customer paid for the goods and no discount is subtracted twice. An automatic discount never appears in `Discount Code` and never attributes. A second code that is not a creator's is listed under unattributed codes and does not move the order. Programme section 4 records which discounts creator codes combine with; the basis rule is the same whichever they are. | build, from `orders-export-columns.md` |
| A refund lowers the basis by the whole `Refunded Amount` (the default), or, when section 4's "Partial refunds" line says in proportion, by the subtotal times the refunded amount divided by the order `Total`, rounded half up to the cent for each order. Never below zero. An absent or blank line means in full. Shopify's refunded figure may include refunded shipping or tax; the in-proportion rule keeps those out of the creator's basis. | programme section 4; schemas section 12 |
| A `partially_refunded` order whose refunded amount the export does not give, or (in proportion) whose `Total` does not read, is not assessed; the run is partial. | build |
| Money is read as a plain decimal; a cell that does not read is never turned into zero, and the order is not assessed. | schemas section 3; build |

## 5. Commission, flat fees, carried amounts and the minimum

| rule | origin |
|---|---|
| Rate: the roster's `commission_rate_pct`, else section 4's rate. Applies to `cpa` and `hybrid` deals; `flat`, `gift` and `none` earn no commission. A creator with no `compensation_model` takes section 4's default model. | programme section 4; brief |
| Commission = basis times rate, on each creator's total basis, rounded half up to the cent once. | build |
| Flat fee: one roster `flat_fee` per publication row whose notes hold the entry `YYYY-MM-DD fee milestone reached by <role>: finance to pay` dated inside the period, for `flat` and `hybrid` deals. The text after the colon is not read, because the owner's note replaces it for a second deliverable set. `fee milestone part` and `fee milestone held` make nothing due. A milestone on a `cpa` deal is listed for a person and earns nothing. | schemas section 6; `publication-tracking`'s notes vocabulary |
| Disclosure as posted: a publication in the period with `disclosure_seen` of `no` or `partial` is named in the row's notes and under "Needs a person". The script does not withhold anything for it; the owner decides before approving. | programme rules; build |
| Carried in: the amount in a `carried forward <amount>` note on the creator's latest earlier statement row marked `final statement`, when that row is `draft` or `approved`. Earlier statements are read newest first; a preview or partial row is walked past (and named under "Could not judge"), so a month that never reached final does not lose an amount carried into it. A final row, or a statement with no row for the creator, ends the walk. A `disputed` row is not carried and is listed. A rerun of a period that already has a later statement is flagged for a person, since an amount may already have been carried past it. | programme section 6; lead's ruling |
| Total due = commission + flat fee + carried in. | build |
| Payout amount: the total due for `manual` (and `none`) rails; for `collabs` and `app`, only the flat fee and carried amount, because the rail pays its own commission. | brief; `orders-export-columns.md` |
| Minimum: a payout amount above zero and below section 6's minimum is not listed; the row notes `below minimum <min>: carried forward <amount>` and the next final statement adds it. | programme section 6; brief |

## 6. Outcomes: final, preview, partial

| outcome | when | payout list | exit |
|---|---|---|---|
| final | run date on or after the last day of the period plus the holdback, and nothing missing | rows for complete, final creators at or above the minimum | 0 |
| preview | run date earlier than that; nothing missing | header only | 0 |
| partial | an export lacks a needed column (`Name`, `Created at`, `Financial Status`, `Discount Code`, `Subtotal`, `Refunded Amount`, `Email` while the self-referral rule applies), a fallback column was used, rows could not be read, or a creator's row could not be assessed (including the link-file case in section 2) | header only when the gap is in an export; otherwise every creator except the affected ones | 2 |
| bad input | a programme value the run needs is blank or `[open]`, a CSV header differs from the schemas, a code belongs to two active creators, the run date is after today (UTC) or before the period, a person has already marked rows of this period | nothing written | 1 |

## 7. The statement's columns (`payouts/<period>/statement.csv`, schemas section 11)

| column | meaning here |
|---|---|
| `orders_attributed` | every order dated in the period given to this creator, whatever happened to it next |
| `orders_excluded` | of those, the ones excluded by a rule in section 3 (pending orders are not excluded) |
| `gross_sales` | sum of the basis column over the cleared orders, before refunds |
| `refunds` | refunds taken off those cleared orders |
| `commission_basis` | `gross_sales` minus `refunds` |
| `commission_rate_pct` | the rate used; `0` for a deal without commission |
| `commission_due`, `flat_fee_due`, `total_due` | as in section 5; `total_due` includes any carried amount |
| `holdback_until` | the last day of the period plus the holdback days |
| `status` | always `draft` when written; a person changes it |
| `notes` | `;`-separated: the run marker first (`<date> final statement`, `<date> preview, holdback open until <date>` or `<date> partial statement`), then rate source, exclusions, pending, link counts, fee milestones, carried amounts, rail, disclosure flags, gaps, the minimum note |

## 8. The payout list's columns (`payouts/<period>/payout-list.csv`)

The shape is schemas section 11.

`period, creator_ref, display_name, rail, amount, currency, statement_status, notes`

`amount` is the payout amount from section 5, in the store currency of programme section 1. `statement_status` is copied as `draft`; finance pays a row only after the owner has set the matching statement row to `approved`. The list carries no payment details; finance holds them.

## 9. Worked example (the fixture, period 2026-08, run 2026-10-01, holdback 30 days, minimum 25)

| creator | what happened | result |
|---|---|---|
| c-aaa111, cpa at 20 percent (roster) | 9 orders by code; 4 excluded (the onboarding test order named in the roster notes, one refunded, one pending payment, one placed with the creator's own email); 5 cleared with subtotals 40, 60, 80, 20 and 55, the 80 refunded by 20 | basis 255.00 minus 20.00 = 235.00; commission 47.00; on the payout list |
| c-bbb222, cpa at 15 percent (section 4) | one order before the agreement date, one cleared at 50 | commission 7.50, below the minimum, carried forward |
| c-ccc333, hybrid at 10 percent, flat fee 150 | one order by code (120) and one by the link file (70); one fee milestone in August | 19.00 + 150.00 = 169.00; on the payout list |
| c-eee555, cpa at 15 percent on collabs | three orders at 100, 10 and 12 | commission 18.30, reconciliation only, nothing on the payout list |
| c-fff666, cpa at 15 percent | two orders (30 and 20); 8.00 carried from July | 7.50 + 8.00 = 15.50, below the minimum, carried forward |

With section 4 set to in proportion, c-aaa111's partly refunded order (subtotal 80, total 87, refunded 20) loses 18.39 of basis instead of 20, so its basis is 236.61 and its commission 47.32.

Run on 2026-09-10 instead, the same workspace gives a preview: only orders dated up to 2026-08-11 have cleared (the one dated 2026-08-11 clears on the run date itself, the one dated 2026-08-12 a day later), nine orders worth 477.00 of basis are pending, and the payout list is empty.
