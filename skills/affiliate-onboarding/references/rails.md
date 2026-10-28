# The three Shopify rails, as they bear on onboarding a creator

Dated 2026-10-20. Drawn only from the pack's `references/shopify-affiliate-rails.md`, whose sources were all read on 2026-10-20; the number in square brackets after a line is the section of that file. Where that file says a fact was not found, this file says so too. Lines marked "inferred" are the pack's reading, not Shopify's words. Shopify changes these pages; re-check a line before relying on it.

## Contents

1. Can a creator sign up and be paid out automatically?
2. Shopify Collabs
3. A third-party affiliate app
4. Manual: codes through the Admin API or the admin
5. What nobody can know without logging into the store
6. Words

## 1. Can a creator sign up and be paid out automatically?

| | Shopify Collabs | an affiliate app | manual |
|---|---|---|---|
| How a creator joins | an application page on the store, a direct invite, or an open-access programme [1]. Collabs "isn't accepting new creator signups at this time"; creators who already have Collabs accounts still can [1]. Whether an invited creator without an account can join is not stated [1] | through the app's own portal or recruitment page where its listing names one; not checked app by app [3] | no self-signup: written terms first, then this skill gives the code |
| How the code and link are made | Collabs makes a personalised link and a discount code for each approved creator [1]; both stay the same if the creator moves between programmes [1] | the app makes them; several listings name coupons made automatically (UpPromote on its Professional plan, BixGrow) [3] | the brand makes one code per creator, through `discountCodeBasicCreate` or in the admin [4, 7]; the link is the brand's own address carrying UTM values [6] |
| How a sale is credited | through the creator's link or code [1]. The attribution window, and which wins when an order has both, were not found [1] | by link or coupon, as the app tracks them [3] | by the code, in the orders export's "Discount Code" column [6]. A UTM link shows only in the marketing reports and the API's customer-journey data; the orders export has no referrer or UTM column [6] |
| How payouts run | automatically, through the brand's Shopify bill, in USD, after the holding period, once the creator has turned on auto-payouts; until then commission waits as "waiting for creator" [1] | by the app, mostly through PayPal; ACH, bank transfer, gift cards or store credit on some plans; which plan carries which method differs by app [3] | not automatic: the pack's statement works out what is owed, and finance pays outside Shopify [7] |
| What it costs | free to install; a 2.9 percent processing fee on every automatic commission payment [1] | from free to USD 1,500 a month as listed, plus a share of sales on several plans [3] | the least of the three; the cost is a person's time on payouts, tax forms and leak control [7] |
| Is it automatic, then? | signup: only for creators who already have Collabs accounts, as of 2026-10-20; codes, links, tracking and payout: yes, once the creator has turned on auto-payouts | yes, within what the app's plan includes | no |

What a person still does on each rail:

| Collabs | an app | manual |
|---|---|---|
| sends the invite or approves the application; sets the programme's commission and customer discount to match programme sections 4 and 5; sets the holding period to the section 5 holdback; pays the Shopify bill; checks each creator has turned on auto-payouts; decides on W9 collection (US merchants; without a W9 a creator's payouts are capped at USD 599.99 a year, and Form 1099 may be needed) [1]; copies each creator's code and link out of Collabs, because a merchant review dated 2026-10-05 says Collabs gives no API access (opinion, not Shopify documentation) [1] | adds or approves the creator; sets commission, discount and payout method in the app; keeps the payout account funded, for example a PayPal Business account [7]; gets the vendor's written word that it serves a merchant in the actual product category and markets (each app's terms were not checked) [3] | creates each code; exports the orders each month; leaves out refunds using "Financial Status" and "Refunded Amount"; pays each creator; issues tax forms [7] |

## 2. Shopify Collabs

- Plans: every plan except Starter and Retail [1].
- Shopify Network Intelligence must be switched on in the store's privacy settings [1].
- A direct invite expires after 30 days; up to 100 invites can go out in any 7-day period [1].
- Open access takes creators in the United States, the United Kingdom and Canada only; no country limit is stated for invite programmes [1].
- A creator belongs to one programme at a time [1].
- Holding period: 30 days by default, adjustable from 1 to 90; commission on a cancelled or fully refunded order is cancelled during the hold [1].
- Manual payments, PayPal included, are no longer used for new commissions [1].
- Shopify may open a dispute by itself, for example over "discount code leaks or paid ads activity". A dispute left unresolved for 30 days pauses the connection and cancels the commission, links and codes [1].
- Minimum payout: not on the payments help page. A Shopify blog post is reported to give USD 25 for creators; the post was not opened [1].
- Whether Collabs needs Shopify Payments: not found. The App Store's compatibility criteria load only in a browser [1].
- Category-specific merchant limits: none stated on the pages read; the creator-side community guidelines were not read [1].

## 3. A third-party affiliate app

As listed on each app's Shopify App Store page; prices are the entry or lowest paid tier, billed in USD [3].

| app | pays creators itself, as listed | entry price as listed |
|---|---|---|
| UpPromote | PayPal auto-payment (Professional); store credit (Growth); manual on Free | Free; Growth USD 29.99 a month plus 2 percent of referral sales |
| GOAFFPRO | ACH, bank transfer, auto-payments, card, gift card, PayPal (plan not stated) | Free; Premium USD 49 a month |
| Refersion | PayPal, ACH, bank transfer and more, with tax forms | Launch USD 39 a month plus 3 percent of affiliate sales |
| Snowball (Social Snowball) | instant cash or gift card payouts; PayPal, ACH, bank transfer | USD 249 a month plus 3 percent |
| LeadDyno | payout integrations; PayPal and bulk payouts | Lite USD 49 a month, up to 50 affiliates |
| BixGrow | PayPal weekly or monthly, or store credit (PRO) | Starter free; Scale USD 19.99 a month |
| Tapfiliate | auto-payments tag; method detail not listed | Launch USD 89 a month |
| Superfiliate | not listed | USD 1,500 a month plus 3 percent |

Inferred: confirm in writing with the chosen vendor, before signing up, that it accepts a merchant in the actual product category and markets [3].

## 4. Manual: codes through the Admin API or the admin

- API version 2026-10 is the latest stable version, released 2026-10-01 and reachable until 2027-10-16 at 15:00 UTC; each stable version is supported for at least 12 months [4].
- One code: `discountCodeBasicCreate(basicCodeDiscount: DiscountCodeBasicInput!)`, which returns `codeDiscountNode` and `userErrors`; the app needs the `write_discounts` scope [4].
- Input fields: `title`, `code`, `startsAt`, `endsAt`, `context`, `customerGets`, `appliesOncePerCustomer`, `usageLimit`, `minimumRequirement`, `combinesWith`, `recurringCycleLimit`, `tags`. `customerSelection` is deprecated in favour of `context` [4].
- `context.all` takes `ALL`; a percentage is written between 0.00 and 1.00 [4].
- The request variables were put together from the documented fields and are untested; try them in a development store first [4].
- Endpoint and header [4.1]: `POST` to `https://{store_name}.myshopify.com/admin/api/2026-10/graphql.json`, the token in the `X-Shopify-Access-Token` header, a JSON body with `query` and `variables`. Inferred: the host is the store's `.myshopify.com` address, not the storefront domain [4.1].
- Fixed amount and combining [4.2]: a fixed amount is `customerGets.value.discountAmount` with `amount` (Shopify's examples pass it as a string, `"20.00"`) and `appliesOnEachItem` (false splits the amount across the items); the input has no currency field. `combinesWith` takes `orderDiscounts`, `productDiscounts` and `shippingDiscounts`, each false by default. Inferred: a code created without it combines with no other discount class [4.2]. A customer can use at most 5 product or order codes and 1 shipping code on one order [4.2].
- A code that already exists [4.3]: `userErrors` can carry `code` (a `DiscountErrorCode`; `TAKEN`, `DUPLICATE` and `IMPLICIT_DUPLICATE` could fit), `field` and `message`. Which code a duplicate returns is not documented. A Shopify staff reply quotes the message "Code must be unique" (community thread, not documentation) [4.3].
- Not in the reference: the shape of `minimumRequirement`.
- Many codes on one discount: `discountRedeemCodeBulkAdd` takes up to 250 codes a call and runs asynchronously [4]. Inferred: every creator would then share one customer offer. This skill makes one discount per creator instead, so one creator's code can be ended without touching anyone else's (the pack's choice).
- Rate limits: a mutation costs 10 points by default; the bucket refills at 100 points a second on Standard, 200 on Advanced, 1,000 on Plus [4].
- Discount codes cannot be imported by CSV; they can be exported to CSV [5]. Bulk generation in the admin is not confirmed [5].
- Reading codes back on orders: `Order.discountCodes` (several codes can sit on one order), with `read_orders`; only the last 60 days without `read_all_orders` [4].

## 5. What nobody can know without logging into the store

The plan, the payment gateway and whether Shopify Payments is on; the installed apps; the Network Intelligence setting; whether Collabs shows as compatible; the discount codes that already exist and how often each is used; the share of orders carrying a code; refund and cancellation rates; whether UTM values reach the store; whether Shopify has flagged any product or category [7].

## 6. Words

- holding period: Collabs' name for the wait before commission is paid; the programme file calls it the holdback (section 5).
- auto-payouts: the Collabs setting a creator switches on to be paid automatically.
- application page, direct invite, open access: the three ways into a Collabs programme.
- rail: where a creator's code and payout live, `collabs`, `app` or `manual` (the roster's `rail` column).
