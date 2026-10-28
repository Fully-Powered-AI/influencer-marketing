# Orders export columns, the link file, and what each rail does with commission

Written 2026-10-20, revised the same day for the layout rule in `references/schemas.md` section 10. Taken from the pack's `references/shopify-affiliate-rails.md` (sources read 2026-10-20, sections 1, 4 and 6) and `references/schemas.md` section 10, so that this skill stands alone when installed. Shopify changes its exports and apps; re-check a line against those files, or against the cited page, before relying on it. Lines marked "inferred" are the pack's reading, not Shopify's words.

## The columns the script reads

The script looks columns up by name, ignoring case, and reads nothing else from the export.

| what the script needs | column read first | fallback | if neither is there |
|---|---|---|---|
| order identifier | `Name` (the order number, for example `#1001`) | `Id` | not an orders export; with `--export`, exit 1 |
| order date | `Created at` | `Paid at` | partial |
| payment state | `Financial Status` | none | partial; every order is "financial status unknown" and earns nothing |
| creator code | `Discount Code` | none | partial; no order attributes by code |
| basis | `Subtotal` (after discounts, before shipping and tax) | `Total`, which includes shipping and tax | partial |
| refunds | `Refunded Amount` | none | partial; a partly refunded order is not assessed |
| self-referral check | `Email` | none | partial while the rule applies |
| cancellation | `Canceled at` | none | not partial; cancellations are then judged by the financial status alone, and the coverage line says so |

Facts behind the table, from the Shopify help page on exporting orders (https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders, read 2026-10-20, as recorded in `shopify-affiliate-rails.md` section 6):

- The export has `Discount Code`, `Financial Status`, `Fulfillment Status`, `Refunded Amount`, `Email`, `Name`, `Id`, `Created at`, `Paid at`, `Canceled at`, `Notes`, `Note Attributes`, `Tags`, and separate `Discount Amount` and `Lineitem discount` columns. A customer ID column is not listed.
- `Discount Code` shows discount codes and discounts applied by hand to draft orders. Automatic discounts are not shown there. The page does not say how several codes on one order are written; until a real export settles it, every pack script splits the cell on commas (schemas section 10).
- Referring site, landing page and UTM values are not columns of the export.
- Exports of 50 orders or fewer download at once; larger or date-ranged exports are emailed to the person who asked and to the store owner.
- Inferred: the per-line columns (`Lineitem fulfillment status`, `Lineitem discount`) mean the export has one row per line item. Until a real export settles it, every pack script takes order-level cells from the first row of each order and ignores them on later rows (schemas section 10).
- `Financial Status` values include paid, authorized and refunded "and so on"; the full list is not on the page read. The script reads `partially_refunded` with a space or an underscore.

## Stacked discounts

The export does not split `Subtotal` by discount. `Discount Amount` gives the order's total discount without saying which code or automatic discount produced which part. The statement therefore takes the basis net of every discount on the order (see `statement-rules.md` section 4) and does not try to allocate a discount between a creator code and anything stacked with it.

## The link-attribution file

Shape, from schemas section 10: `exports/link-attribution-<period>.csv` with the header `order_name, creator_ref, source, exported_at`. `source` is `collabs`, `app`, `api` or `manual`. `order_name` is the export's `Name`; a leading `#` is optional.

Where a person can find the data (`shopify-affiliate-rails.md` sections 4 and 6):

- The Admin API's `Order.customerJourneySummary` carries first and last visits with landing page, referrer and UTM parameters. Querying orders needs the `read_orders` scope, and only the last 60 days of orders can be read without `read_all_orders`, so build the file soon after the period ends.
- Shopify stopped setting the `_landing_page` and `_orig_referrer` cookies on 15 September 2025; forum answers say journey data is missing when a visitor declines tracking (not authoritative). Expect some link-driven orders to have no journey data at all.
- Each order's "Conversion summary" in the admin shows the referring source and landing page, and is empty when cookie tracking is blocked.
- Collabs and the affiliate apps keep their own record of link-driven orders; an export from the rail's report is the other source.

Matching each journey to a creator uses the UTM convention in programme section 5. That match is a person's work, made before the run; the script trusts `creator_ref` in the file and checks only that the creator is on the roster and active.

## What each rail does with commission

| rail | who computes and pays commission | what this statement is |
|---|---|---|
| `manual` | finance, outside Shopify, from the payout list after the owner approves | the instruction for the payout list |
| `collabs` | Shopify Collabs computes it and pays it through the store's Shopify bill as "Shopify Collabs Commission", in USD, after the bill is paid; the creator must switch on auto-payouts or the commission waits | a reconciliation of the Collabs figure |
| `app` | the affiliate app, by the payout methods of its plan (often PayPal; some offer ACH, gift cards or store credit) | a reconciliation of the app's figure |

Collabs facts that explain a reconciliation difference (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/payments, read 2026-10-20, as recorded in `shopify-affiliate-rails.md` section 1):

- Commissions are held for 30 days by default, adjustable from 1 to 90 days, and are cancelled automatically on cancelled and fully refunded orders during the hold. If the Collabs hold differs from programme section 5, the two will clear different orders.
- A commission is earned through an affiliate link or a code. Shopify's pages do not document the attribution window or which wins when both a link and a code are used; community posts claiming last click and 30 days are not authoritative.
- A processing fee of 2.9 percent applies to every automatic commission payment. It is a cost to the store, not part of what the creator is owed.
- Shopify may open a dispute for code leaks or paid-ads activity; an unresolved dispute pauses the connection after 30 days and cancels the commission.
- With W9 collection on, a US creator without a W9 is limited to USD 599.99 a year in payouts, and the store may need to issue Form 1099. The statement computes no tax figure.
- A merchant review dated 5 October 2026 reports no API access for Collabs (opinion, not documentation), so the Collabs figure is read from its admin report by a person.
