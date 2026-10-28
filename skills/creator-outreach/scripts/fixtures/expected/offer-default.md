# Offer arithmetic

Computed by scripts/offer_calc.py from program/program.md in the workspace, as of 2026-10-20. Paste this block as it stands; do not retype its figures.

## Inputs

| input | value | label |
|---|---|---|
| store currency | USD | Measured (marked [observed] in programme section 1) |
| average order value | USD 42.00, measured 2026-09-30 | User-provided (the owner, programme section 1) |
| gross margin band | 55 to 65 percent | User-provided (the owner, programme section 1) |
| customer discount | 15 percent | User-provided (the owner, programme section 4) |
| commission rate | 15 percent | User-provided (the owner, programme section 4) |
| gross margin read on | list price | User-provided (the owner, programme section 1) |
| commission basis | subtotal after discounts, before shipping and tax | User-provided (pack default the owner accepted, programme section 4) |
| default model | cpa | User-provided (the owner, programme section 4) |

## One tracked order at the average order value

Every row is Estimated: computed from the inputs above for one order at the average order value.

| figure | at 55 percent margin | at 65 percent margin |
|---|---|---|
| order subtotal before the discount | USD 42.00 | USD 42.00 |
| customer discount | USD 6.30 | USD 6.30 |
| revenue per order: the subtotal the customer pays, before shipping and tax | USD 35.70 | USD 35.70 |
| cost of goods | USD 18.90 | USD 14.70 |
| gross profit before commission | USD 16.80 | USD 21.00 |
| commission to the creator at 15 percent | USD 5.36 | USD 5.36 |
| contribution per order after commission | USD 11.45 | USD 15.65 |
| highest commission rate before an order loses money (rounded down) | 47 percent | 58.8 percent |

## Lines for data/pipeline.csv

- offer_summary, default per-sale deal: cpa 15 pct, code 15 pct off, no fee

## Not in these figures

Shipping, payment processing, rail and app fees, refunds, the holdback and the cost of any gifted product. If the margin band does not already allow for them, the contribution is lower than shown. The arithmetic is the pack's per-order definition (schemas.md section 12): the average order value is before discounts; if the owner measured it after discounts, the discount is counted twice and the contribution shown is low.

Section 4's break-even line agrees with the lines it copies.

Coverage: inputs used: section 1 average order value, gross margin band and the line under it, store currency; section 4 commission rate, customer-facing discount, commission basis. Inputs missing: none. Not judged: whether creator orders match the average order value, how many orders this creator will drive, refunds, and the costs listed above.
