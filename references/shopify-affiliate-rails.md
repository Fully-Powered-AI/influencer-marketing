# Shopify rails for a pay-per-sale creator programme

Scope: this file covers the Shopify tools a merchant can use to give creators their own codes and links, attribute orders to them, and pay commission. It covers Shopify Collabs, Shopify's acceptable-use and Shopify Payments eligibility rules as they bear on a sexual-wellness merchant, third-party affiliate apps, the Admin GraphQL API for discount codes, and the order exports and marketing reports used for reconciliation. Every source was read on 2026-10-20. Pages that render their key details only in the browser are noted where the detail could not be seen. Lines marked "inferred" are our reading.

## Contents

1. Shopify Collabs
2. Shopify rules that bear on an adult or sexual-wellness merchant
3. Third-party affiliate apps
4. Admin GraphQL API: creating discount codes
   - 4.1 Endpoint and access-token header
   - 4.2 Fixed-amount discounts and `combinesWith`
   - 4.3 `userErrors` when a code already exists
5. Bulk codes in the admin, and CSV
   - 5.1 The discounts export
6. Order exports and marketing reports
   - 6.1 Orders CSV: line-item rows, and several codes on one order
   - 6.2 UTM parameters per order through the Admin API
7. What this means for a pay-per-sale creator programme

## 1. Shopify Collabs

What it does
- Shopify describes Collabs as helping "businesses and creators connect using a marketplace-style app". Merchants can send direct invites, run an open-access commission programme, or accept affiliate applications through a page on their store (https://help.shopify.com/en/manual/promoting-marketing/collabs, read 2026-10-20).
- The App Store listing names these features: a custom affiliate application page, direct invitations, an open-access programme, gifting through Shopify, personalised affiliate links and discount codes for approved creators, and "Automatic commission tracking and payment via your Shopify bill" (https://apps.shopify.com/collabs, read 2026-10-20).
- Invite programmes set a commission percentage and a customer discount. A creator belongs to one programme at a time, and when moved "Their affiliate link and discount code stay the same" (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/collabs-programs, read 2026-10-20).
- Direct invites expire after 30 days, and a merchant can send up to 100 in any 7-day period (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/recruiting-creators, read 2026-10-20).

Requirements
- Plans: "Shopify Collabs is available on all Shopify plans except for the Starter and Retail plans" (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/setup, read 2026-10-20).
- Privacy setting: "Using this feature requires Shopify Network Intelligence to be enabled in your privacy settings" (https://help.shopify.com/en/manual/promoting-marketing/collabs, read 2026-10-20).
- Creator signups: "Collabs isn't accepting new creator signups at this time." Existing creators with partnerships can still use it (https://help.shopify.com/en/manual/promoting-marketing/collabs, read 2026-10-20). Inferred: this may block onboarding creators who do not already have a Collabs account. The help pages do not say whether an invited creator without an account can join. Test it before choosing Collabs.
- Creator countries: for open access, "only creators in the United States, the United Kingdom, and Canada are currently eligible"; no restriction is stated for invite programmes (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/collabs-programs, read 2026-10-20).
- Shopify Payments prerequisite: not stated on the Collabs help pages read. The App Store page has a compatibility notice ("Shopify Collabs is only compatible with stores that:") whose criteria load only in the browser (https://apps.shopify.com/collabs, read 2026-10-20). Not found.
- Restrictions on adult or sexual-wellness merchants: none stated on the Collabs setup, programmes, payments or merchant community-guidelines pages read (URLs above, read 2026-10-20). The creator-side Collabs Community Guidelines were not read. Not found.

Fees and payouts
- Pricing: "Free to install" with "+ 2.9% commission processing fee on automatic payments may apply" (https://apps.shopify.com/collabs, read 2026-10-20).
- "There's a 2.9% processing fee applied to every automatic commission payment" (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/payments, read 2026-10-20).
- Payment route: commissions are "processed through your Shopify bill" as "Shopify Collabs Commission", in USD, and are paid out after the bill is paid. The creator must activate auto-payouts, or the commission waits in a "waiting for creator" state (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/payments, read 2026-10-20).
- Holding period: 30 days by default, configurable from 1 to 90 days. Commissions on cancelled and fully refunded orders are cancelled automatically during the hold (same URL, read 2026-10-20).
- Manual payments, including through PayPal, are no longer used for new commissions; outstanding manual payouts had to be settled by 28 February 2024 (same URL, read 2026-10-20).
- Tax: US merchants can switch on W9 collection. Creators who do not submit a W9 are then limited to USD 599.99 a year in payouts (the page writes the amount with a currency symbol), and merchants may need to issue Form 1099 (same URL, read 2026-10-20).
- Minimum payout: not on the payments help page. A Shopify blog post is reported to give a USD 25 creator threshold (search-result summary of https://www.shopify.com/blog/how-to-get-started-with-shopify-collabs, read 2026-10-20; not opened).

Attribution
- "Affiliate commissions can be earned by a creator through affiliate links or discount codes"; a commission is earned when "a creator's audience makes a purchase using an affiliate link or code" (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/payments, read 2026-10-20).
- Cookie or attribution window, and which wins when both a link and a code are used: not found on Shopify's pages. Searched "Shopify Collabs affiliate link attribution window days cookie". Community posts claim last-click attribution and a 30-day cookie; these are not authoritative (search results, read 2026-10-20).
- Collabs disputes: Shopify may open a dispute automatically for violations such as "discount code leaks or paid ads activity". An unresolved dispute pauses the connection after 30 days and cancels the commission, links and codes (https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants/payments, read 2026-10-20).
- A merchant review dated 5 October 2026 on the App Store says Shopify offers "no such API access for Collabs" (https://apps.shopify.com/collabs, read 2026-10-20; merchant opinion, not Shopify documentation).

## 2. Shopify rules that bear on an adult or sexual-wellness merchant

Acceptable Use Policy
- The current AUP is written as principles, not a list of categories. Its headings are quoted exactly: "You can't use Shopify to do anything that's illegal where you do business."; "You can't breach the social contract of commerce."; "You need to follow our agreements with you."; "Payment Terms (and terms from other add-on products) can also apply."; "There are also channel rules that could apply."; "The most common product eligibility disputes originate from outside of Shopify."; "We expect you to act in good faith. If you don't, account-level action may be appropriate." (https://www.shopify.com/legal/aup, read 2026-10-20).
- No adult-products or sexual-wellness category heading appears in the AUP (https://www.shopify.com/legal/aup, read 2026-10-20).

Shopify Payments: prohibited businesses
- The eligibility page's section heading is "Prohibited businesses and products". It lists "high-level categories for prohibited products and services prohibited by the Shopify Payments Terms of Service" (https://help.shopify.com/en/manual/payments/shopify-payments/onboarding/eligibility, read 2026-10-20). Three categories are relevant, quoted exactly:
  - "Regulated or illegal products and services: Products or services that require regulatory approval or compliance, such as cannabis and related products, prescription drugs, medical devices, tobacco and related products, firearms, holsters, ammunition, or weapons."
  - "Adult products: Products or services that contain sexually explicit content, such as adult videos, pay-per-view adult content, or adult magazines."
  - "Pseudo pharmaceuticals: Pharmaceuticals and other products that make health claims that are not verified by a local or national regulatory body."
- The same page says the list "isn't exhaustive and it varies depending on your region". A merchant that isn't eligible can add a third-party payment provider (same URL, read 2026-10-20).
- Inferred: personal lubricants are FDA Class II medical devices (see platform-and-compliance-notes.md, section 3), so the "medical devices" wording could reach them. The brand's supplement could reach "Pseudo pharmaceuticals". How Shopify applies these categories to a given store can only be confirmed by Shopify.
- US terms: the section headed "Prohibited and Restricted Businesses." defers to "each Payment Processor in your Designated Country" (https://www.shopify.com/legal/terms-payments/us, which resolves to https://www.shopify.com/legal/terms-shopify-payments, read 2026-10-20). For the United States, the processor list names Stripe, Inc. and PayPal, Inc. (https://www.shopify.com/legal/processor-list, read 2026-10-20).
- Stripe's list (last updated 2026-09-22) has "Adult content and services" under Prohibited Businesses. That category covers adult services, adult video stores, strip clubs, and "Pornography and other mature audience content ... designed for the purpose of sexual gratification". It does not name lubricants or sexual-wellness goods. "Nutraceuticals and pseudo-pharmaceuticals" is also prohibited where "not safe or make harmful claims". Under Restricted Businesses, "Pharmaceuticals, medical devices, and telemedicine" includes "Prescription-only and regulated medical devices" (https://stripe.com/legal/restricted-businesses, read 2026-10-20). The US-specific page, https://stripe.com/us/legal/restricted-businesses, was not read separately.

Shop channel
- The prohibited product types on Shop include "Mature and adult content or services, or products that have nudity" and "Medication, medical devices and accessories" (https://help.shopify.com/en/manual/online-sales-channels/shop/eligibility/prohibited-products, read 2026-10-20). Inferred: a lubricant brand may not be listable on the Shop app even if its online store is fine.

## 3. Third-party affiliate apps

Prices are the entry or lowest paid tier as shown on the App Store listing; all charges are billed in USD. Payout methods are taken from the listing's feature tags or highlights. "Not listed" means the listing did not show the item.

| App | One-line description (from listing) | Pays out itself? | Entry price as listed | App Store URL (read 2026-10-20) |
|---|---|---|---|---|
| UpPromote Affiliate Marketing | Affiliate and influencer programmes; "Tracking by affiliate link/coupon"; auto-generated coupons on Professional | Yes: "PayPal auto-payment" (Professional); "Store credit" (Growth); manual payout on Free; tags list bank transfers and card payouts | Free (review USD 3,000 referral sales a month); Growth USD 29.99 a month + 2% of successful referral sales | https://apps.shopify.com/affliate-by-secomapp |
| GOAFFPRO Affiliate Marketing | Affiliate portal and referral links; "Numerous payout options"; discount codes mentioned in review summary | Yes: tags list ACH, bank transfers, auto-payments, card payouts, gift card payouts, PayPal (which plan not stated) | Free plan; Premium USD 49 a month | https://apps.shopify.com/goaffpro |
| Refersion Affiliate Marketing | First-party tracking links "no cookies or redirects"; affiliate, influencer and publisher payouts | Yes: "Affiliate payouts via PayPal, ACH, Bank Transfers and more; automated Tax Forms" | Marketplace listing free; Launch USD 39 a month + 3% of affiliate-generated sales; "External charges may be billed by Refersion, Inc. separately" | https://apps.shopify.com/refersion |
| Snowball: Affiliate Marketing (Social Snowball) | Affiliate, referral and influencer automation; "Prevent fraud & code leaks" | Yes: "Bulk send instant cash or gift card payouts"; tags list PayPal, ACH, bank transfer | Snow Day USD 249 a month + 3% of affiliate revenue | https://apps.shopify.com/social-snowball |
| LeadDyno Affiliate Marketing | Affiliates, influencers and ambassadors; "Customize commission tiers, percentages, coupon codes"; "Per Shopify Collection Affiliate Codes" on Essential | Yes: "Pay hundreds of affiliates in minutes with payout integrations"; tags list PayPal and bulk payouts | Lite USD 49 a month (up to 50 affiliates) | https://apps.shopify.com/leaddyno |
| BixGrow Affiliate Marketing | Links and "Auto-generated Coupons"; "Create coupons in bulk" and "Anti-leak coupon" on PRO | Yes: "Automated PayPal payouts, weekly or monthly — or pay with store credit" ("PayPal Integration & Store Credit" on PRO, USD 29.99) | Starter free (50 referral orders a month, up to 30 affiliates); Scale USD 19.99 a month | https://apps.shopify.com/bixgrow-affiliate-marketing |
| Superfiliate | Co-branded creator storefronts, seeding, social listening | Not listed | Tier 1 USD 1,500 a month + 3% of affiliate revenue | https://apps.shopify.com/superfiliate |
| Tapfiliate Affiliate Marketing | Affiliate, influencer and referral programmes with tracking links | Tag lists auto-payments; PayPal in "Works with"; method detail not listed | Launch USD 89 a month (50 affiliates, 500 conversions a month) | https://apps.shopify.com/tapfiliate |
| Shopify Collabs (for comparison) | See section 1 | Yes, via the Shopify bill | Free + 2.9% on automatic payments | https://apps.shopify.com/collabs |

- Listed ratings: UpPromote 4.9 (3,893 reviews), GOAFFPRO 4.6 (952), Refersion 4.8 (495), Snowball 4.6 (212), LeadDyno 4.4 (221), BixGrow 4.9 (1,338), Superfiliate 5.0 (40), Collabs 4.2 (439) (listing URLs above, read 2026-10-20).
- Not checked: each app's own terms on adult or sexual-wellness merchants (read 2026-10-20). Inferred: confirm in writing with the chosen vendor before signing up.

## 4. Admin GraphQL API: creating discount codes

- Current stable version: 2026-10 is marked "Latest stable", released 1 October 2026 and accessible until 16 October 2027 at 15:00 UTC. 2027-01 is a release candidate. Versions ship quarterly, and each stable version is "supported for a minimum of 12 months" (https://shopify.dev/docs/api/usage/versioning, read 2026-10-20).
- Mutation for one code: `discountCodeBasicCreate(basicCodeDiscount: DiscountCodeBasicInput!)`, which returns `codeDiscountNode` and `userErrors`. Required scope: "Apps must have `write_discounts` access scope" (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate, read 2026-10-20).
- Input fields of `DiscountCodeBasicInput`: `title`, `code`, `startsAt`, `endsAt`, `context`, `customerGets`, `appliesOncePerCustomer`, `usageLimit`, `minimumRequirement`, `combinesWith`, `recurringCycleLimit` and `tags`. `customerSelection` is deprecated; use `context` instead (https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DiscountCodeBasicInput, read 2026-10-20).
- `context.all` takes the enum `DiscountBuyerSelection`, whose only value is `ALL` (https://shopify.dev/docs/api/admin-graphql/latest/enums/DiscountBuyerSelection, read 2026-10-20). `percentage` "must be between 0.00 - 1.00" (https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DiscountCustomerGetsValueInput, read 2026-10-20).
- Many codes on one discount: `discountRedeemCodeBulkAdd(discountId, codes)` adds up to 250 codes per call. It runs asynchronously and returns a `bulkCreation` job that can be tracked with the `discountRedeemCodeBulkCreation` query. Scope: `write_discounts` (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountRedeemCodeBulkAdd, read 2026-10-20). Inferred: one code per creator on a single discount gives every creator the same customer offer, and orders can still be told apart by code.
- Rate limits: query cost is calculated per field; mutations default to 10 points. Restore rates are 100 points a second on Standard, 200 on Advanced, 1,000 on Plus and 2,000 on Commerce Components. A single query cannot exceed 1,000 points. Throttle state appears in `extensions.cost.throttleStatus` (`maximumAvailable`, `currentlyAvailable`, `restoreRate`) (https://shopify.dev/docs/apps/build/apis/graphql-admin/rate-limits, read 2026-10-20). Input arrays accept at most 250 items (https://shopify.dev/docs/api/usage/limits, read 2026-10-20).
- Reading attribution back: `Order.discountCodes` gives "The discount codes used for the order. Multiple codes can be applied to a single order." Querying orders requires `read_orders`. Only the last 60 days of orders are accessible unless the app also has `read_all_orders` (https://shopify.dev/docs/api/admin-graphql/latest/objects/Order, read 2026-10-20).

Minimal mutation, as given in Shopify's example (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate, read 2026-10-20):

```graphql
mutation CreateSummerDiscount($input: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $input) {
    codeDiscountNode {
      id
      codeDiscount {
        ... on DiscountCodeBasic {
          title
          codes(first: 10) { nodes { code } }
          startsAt
          endsAt
        }
      }
    }
    userErrors { field message }
  }
}
```

Illustrative variables. We assembled these from the documented fields (`context` with `all: ALL`, a percentage between 0.00 and 1.00) and have not tested them; try them in a development store first. The code value is a placeholder.

```json
{
  "input": {
    "title": "Creator code - placeholder",
    "code": "CREATORCODE10",
    "startsAt": "2026-11-01T00:00:00Z",
    "context": { "all": "ALL" },
    "customerGets": {
      "value": { "percentage": 0.10 },
      "items": { "all": true }
    },
    "appliesOncePerCustomer": false
  }
}
```

### 4.1 Endpoint and access-token header

- Endpoint: "GraphQL queries are executed by sending `POST` HTTP requests to the endpoint:" `https://{store_name}.myshopify.com/admin/api/2026-10/graphql.json`. The date in the path is the API version (see the versioning line above), and Shopify advises: "To keep your app stable, make sure that you specify a supported version in the URL." (https://shopify.dev/docs/api/admin-graphql, read 2026-10-20).
- Header: "Every GraphQL Admin API request carries an access token in the `X-Shopify-Access-Token` header." The same page adds that for most apps the Shopify CLI template or Direct API access sets the token for each request (https://shopify.dev/docs/api/admin-graphql, read 2026-10-20).
- The `discountCodeBasicCreate` page's own curl example uses the same shape: `https://your-development-store.myshopify.com/admin/api/2026-10/graphql.json`, `-H 'Content-Type: application/json'`, `-H 'X-Shopify-Access-Token: {access_token}'`, and a JSON body carrying `query` and `variables` (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate, read 2026-10-20).
- Inferred: the host is the store's `.myshopify.com` address, as in both examples, not a custom storefront domain.

Shopify's example request, verbatim (https://shopify.dev/docs/api/admin-graphql, read 2026-10-20):

```bash
# Replace {SHOPIFY_ACCESS_TOKEN} with your actual access token
  curl -X POST \
  https://{shop}.myshopify.com/admin/api/2026-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Access-Token: {SHOPIFY_ACCESS_TOKEN}' \
  -d '{
  "query": "query { shop { name } }"
  }'
```

### 4.2 Fixed-amount discounts and `combinesWith`

- Required on create: `code`, `context` (or deprecated `customerSelection`), `customerGets`, `startsAt` and `title` (https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DiscountCodeBasicInput, read 2026-10-20).
- The value: `DiscountCustomerGetsValueInput` lists three fields: `percentage` (Float, "Value must be between 0.00 - 1.00"), `discountAmount` (`DiscountAmountInput`, "The value of the discount.") and `discountOnQuantity` (`DiscountOnQuantityInput`) (https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DiscountCustomerGetsValueInput, read 2026-10-20). A fixed amount uses `discountAmount`.
- `DiscountAmountInput` has two fields: `amount` (Decimal, "The value of the discount.") and `appliesOnEachItem` (Boolean): "If true, then the discount is applied to each of the entitled items. If false, then the amount is split across all of the entitled items." (https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DiscountAmountInput, read 2026-10-20). The input has no currency field.
- Shopify's example "Create an amount off discount code with an end date" (20 off all items, one use per customer) passes `"customerGets": { "value": { "discountAmount": { "amount": 20, "appliesOnEachItem": false } }, "items": { "all": true } }`. That example still uses the deprecated `"customerSelection": { "all": true }`. The page's two other amount-off examples pass the amount as a string, `"amount": "20.00"`, and read it back as `amount { amount currencyCode }` (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate, read 2026-10-20). Inferred: the amount is in the store's currency; confirm on a development store.
- `combinesWith` takes `DiscountCombinesWithInput`, "The input fields to determine which discount classes the discount can combine with." Its three Booleans each show "Default:false": `orderDiscounts` ("Whether the discount combines with the order discount class."), `productDiscounts` ("Whether the discount combines with the product discount class.") and `shippingDiscounts` ("Whether the discount combines with the shipping discount class.") (https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DiscountCombinesWithInput, read 2026-10-20).
- A fourth field, `productDiscountsWithTagsOnSameCartLine` (`ProductDiscountsWithTagsOnSameCartLineInput`), is "Available only on a Shopify Plus plan and requires the `productDiscounts` field to be set to `true`." (same URL, read 2026-10-20).
- Inferred: a code created without `combinesWith` takes the defaults, so it combines with no other discount class.
- Codes per order: "Customers can use a maximum of 5 product or order discount codes and 1 shipping discount code on the same order." (https://help.shopify.com/en/manual/discounts/discount-combinations, read 2026-10-20).

Illustrative variables for a fixed-amount code. We assembled these from the documented fields above and have not tested them; try them in a development store first. The code value is a placeholder, and the combining choices are examples for the programme to rule on.

```json
{
  "input": {
    "title": "Creator code - placeholder",
    "code": "CREATORCODE10",
    "startsAt": "2026-11-01T00:00:00Z",
    "context": { "all": "ALL" },
    "customerGets": {
      "value": { "discountAmount": { "amount": "10.00", "appliesOnEachItem": false } },
      "items": { "all": true }
    },
    "combinesWith": {
      "orderDiscounts": false,
      "productDiscounts": false,
      "shippingDiscounts": true
    },
    "appliesOncePerCustomer": false
  }
}
```

### 4.3 `userErrors` when a code already exists

- Shape: discount mutations return `DiscountUserError` objects with `code` (a `DiscountErrorCode`), `extraInfo`, `field` ("The path to the input field that caused the error.") and `message` (https://shopify.dev/docs/api/admin-graphql/latest/objects/DiscountUserError, read 2026-10-20). Shopify's `discountCodeBasicCreate` examples request only `field` and `message` (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate, read 2026-10-20).
- Codes that could fit: `DiscountErrorCode` includes `TAKEN` ("The input value is already taken."), `DUPLICATE` ("The input value is already present.") and `IMPLICIT_DUPLICATE` ("The value is already present through another selection.") (https://shopify.dev/docs/api/admin-graphql/latest/enums/DiscountErrorCode, read 2026-10-20).
- Which code and message a duplicate code returns: not found in Shopify's documentation. The mutation page gives no error example and names no error code (https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate, read 2026-10-20). Searched shopify.dev, community.shopify.com and community.shopify.dev for "discountCodeBasicCreate" with "must be unique", "already exists" and "duplicate code" (search results, read 2026-10-20).
- Message wording, from a Shopify community answer: a Shopify staff reply of 19 August 2025, reproducing a reported bug with emoji-only codes, says later codes "Fails with “Code must be unique”". The reporter said the behaviour was the same "in both the admin UI and through the API"; neither post names the mutation (https://community.shopify.dev/t/discount-name-with-only-emojis-odd-bug-and-repeatable-edge-case/21419, read 2026-10-20; community thread, not documentation).
- Legacy REST wording: the REST `DiscountCode` resource's sample shows `"errors": { "code": [ "must be unique. Please try a different code." ] }`. Shopify says "The REST Admin API is a legacy API as of October 1, 2024." (https://shopify.dev/docs/api/admin-rest/latest/resources/discountcode, read 2026-10-20).
- Bulk route: for `discountRedeemCodeBulkAdd`, each code's result is a `DiscountRedeemCodeBulkCreationCode` whose `errors` is a list of `DiscountUserError`; its `discountRedeemCode` is null "If the discount redeem code couldn't be created" (https://shopify.dev/docs/api/admin-graphql/latest/objects/DiscountRedeemCodeBulkCreationCode, read 2026-10-20).
- Inferred: request `code` as well as `field` and `message`; treat `TAKEN` or `DUPLICATE`, or a message containing "unique", "taken" or "already", as a code that already exists; and confirm the real response once on a development store.

## 5. Bulk codes in the admin, and CSV

- CSV import of discount codes is not supported: "You can't import discount codes to your store using CSV files." Discounts can be exported, "only to a CSV file" (https://help.shopify.com/en/manual/discounts/export-discount-codes, read 2026-10-20).
- Bulk generation in the admin: not found on Shopify's discounts pages (https://help.shopify.com/en/manual/discounts and https://help.shopify.com/en/manual/discounts/discounts-faq, read 2026-10-20). Community threads disagree on whether a native "discount set" generator exists (search results, read 2026-10-20). Not confirmed.
- Apps fill the gap. For example, Bulk Discount Code Bot by Seguno: Starter is free ("Get three discount sets at no charge") and Basic is USD 19 a month ("Generate unlimited discount codes", "Not available for Shopify Plus") (https://apps.shopify.com/bulk-discount-generator, read 2026-10-20).

### 5.1 The discounts export

- It exists. "From your Shopify admin, go to Discounts." "From the Discounts page, click Export." The options are "Current page", "All discounts", "Selected discounts" and "Current search"; the formats are "CSV for Excel, Numbers, and other spreadsheet programs" and "Plain CSV file"; then "Click Export discounts to download your discounts CSV." The page describes the export as "a broad overview of your discount code history" (https://help.shopify.com/en/manual/discounts/export-discount-codes, read 2026-10-20).
- Column names: not found. The export page lists none (https://help.shopify.com/en/manual/discounts/export-discount-codes, read 2026-10-20). Searched help.shopify.com, community.shopify.com and community.shopify.dev for the export's headers ("discounts export CSV columns", "Times used", "Usage count"); the column lists found belong to third-party export apps, for example https://matrixify.app/documentation/discounts/, not to Shopify's own export (search results, read 2026-10-20). Inferred: export once from the store and record the headers before any script relies on them.
- Nearest documented per-code view: the "Sales by discount codes" report. Its columns include Discount name, Discount ID, Discount class, Discount method, Discount type, Discount code, Automatic discount title, Discount amount, Other discounts, Orders, Total sales and Shipping; Orders is the number of orders the discount was applied to (https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/sales-report, read 2026-10-20, through our fetcher, which reworded the column descriptions; the page refused a direct download). A plan requirement for the report was not stated on the page as read.

## 6. Order exports and marketing reports

Orders CSV export (https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders, read 2026-10-20):
- Discount code: the "Discount Code" column. "Only discounts and discounts applied manually to draft orders will be displayed in this column." Automatic discounts are excluded, and the page does not say how several codes on one order appear. "Discount Amount" and "Lineitem discount" are separate columns.
- Financial status: "Financial Status" (paid, authorized, refunded and so on).
- Fulfilment status: "Fulfillment Status", plus a per-line "Lineitem fulfillment status".
- Refunds: "Refunded Amount".
- Customer identifiers: "Email" and "Phone", billing and shipping names and addresses, and "Accepts Marketing". The order identifiers are "Name" (the order number) and "Id". A customer ID column is not listed.
- Also present: "Source" (for example web, draft order, POS), "Tags", "Payment Method", "Created at", "Paid at", "Canceled at", "Notes", "Note Attributes" and "Risk Level".
- Referring site, landing site and UTM parameters are not listed among the export columns.
- Delivery: exports of 50 orders or fewer download directly; larger or date-based exports are emailed to the user and the store owner.

Where referrer, landing page and UTM data live instead
- In the API: `Order.customerJourneySummary` (with `firstVisit` and `lastVisit`, each carrying `landingPage`, `referrerUrl`, `source` and `utmParameters`). The older order fields `landingPageUrl`, `referrerUrl` and `referralCode` are deprecated (https://shopify.dev/docs/api/admin-graphql/latest/objects/Order, read 2026-10-20; visit field names from a search-result excerpt of https://shopify.dev/docs/api/admin-graphql/latest/objects/customerjourneysummary, read 2026-10-20).
- Shopify stopped setting the `_landing_page` and `_orig_referrer` cookies on 15 September 2025 (search-result excerpt of https://shopify.dev/changelog/trackingconsent-landingpage-origreferrer-cookies-will-no-longer-be-set, read 2026-10-20). Developer-forum answers say journey data is missing when visitors decline tracking (search results, read 2026-10-20; not authoritative).
- In the admin: each order's "Conversion summary" shows the referring source and landing page. It is empty when cookie tracking is blocked (search-result excerpt of https://help.shopify.com/en/manual/fulfillment/managing-orders/analytics/conversion-summary, read 2026-10-20).

Repeat-purchase counting
- The customers CSV includes "Total Orders" ("The customer's total number of orders") and "Total Spent" (https://help.shopify.com/en/manual/customers/import-export-customers, read 2026-10-20). Inferred: guest checkouts without a customer record weaken repeat counts. `Order.customer` "returns null for guest checkouts that have no customer authentication" (https://shopify.dev/docs/api/admin-graphql/latest/objects/Order, read 2026-10-20). Matching orders on Email in the orders export is the fallback.

Marketing reports
- The listed reports are Performance by marketing channel, Performance by marketing campaign, Sales attributed to marketing, and Sessions attributed to marketing campaigns. "Sales attributed to marketing" "includes the sales that can be attributed to trackable marketing efforts", including "externally managed efforts that use Urchin Tracking Module (UTM) parameters" (https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/marketing-reports, read 2026-10-20).
- The attribution models available are last non-direct click, last click, first click, any click and linear, over a 30-day window. The page names two different defaults without reconciling them (same URL, read 2026-10-20).
- Inferred: giving each creator a UTM-tagged link (for example `utm_source=creator&utm_campaign=<handle>`) lets these reports split traffic by creator. A discount code is still the attribution that survives blocked cookies.

### 6.1 Orders CSV: line-item rows, and several codes on one order

- Shopify's statement: "In your order CSV file, orders with multiple line items display their additional line items on separate lines. Many of the fields are left blank to indicate that multiple items were purchased on the same order." The page does not list which fields stay filled (https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders, read 2026-10-20).
- Which fields repeat, from a Shopify community answer (13 October 2026): "The first row carries the order-level data (email, statuses, totals, shipping/billing address, shipping method). The following rows carry only their own Lineitem columns. All rows share the same Name (order number)." (https://community.shopify.com/t/help-explain-the-data-fields-in-the-csv-file-when-exporting-an-order/336928, read 2026-10-20; community answer, not documentation).
- Another Shopify community answer, asked for an export without blank cells, says "there is no way to do this natively with Shopify" (https://community.shopify.com/t/need-to-export-orders-with-no-blank-cells/180952, read 2026-10-20; community answer).
- Inferred: Name repeats on every row of an order; Email, Financial Status, Subtotal and Total appear on the first row only. Discount Code is not named in the answer, but it is an order-level column, so expect it on the first row only. Group rows by Name and take order-level values from the first row; never count rows as orders.
- Several codes on one order: the page defines "Discount Code" as "The discount code that was applied to the order." and does not say how two or more codes appear (https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders, read 2026-10-20). Other multi-value columns on the same page state their separator: Payment Method, Payment References and Payment ID each say "Multiple entries are separated with a space, a +, and another space." (same URL, read 2026-10-20). That rule is not stated for Discount Code.
- Separator for several codes in the Discount Code cell: not found. Searched help.shopify.com, community.shopify.com and community.shopify.dev for "Discount Code column multiple discount codes one order", "comma-separated" and "orders csv export two discount codes" (search results, read 2026-10-20). Inferred: export one test order that carries two codes before a script splits the cell; the API's `Order.discountCodes`, a list (section 4), avoids the question.

### 6.2 UTM parameters per order through the Admin API

- The field: `Order.customerJourneySummary`, of type `CustomerJourneySummary`: "The customer's visits and interactions with the online store before placing the order." `Order.customerJourney` is marked deprecated (https://shopify.dev/docs/api/admin-graphql/latest/objects/Order, read 2026-10-20).
- Scope: `CustomerJourneySummary` "Requires `read_orders` access scope, `read_marketplace_orders` access scope or `read_buyer_membership_orders` access scope." (https://shopify.dev/docs/api/admin-graphql/latest/objects/CustomerJourneySummary, read 2026-10-20).
- Its fields: `firstVisit` ("The customer's first session going into the shop."), `lastVisit` ("The last session before an order is made."), `moments` ("The events preceding a customer's order, such as shop sessions."), `momentsCount` ("Returns null if the order is still in the process of being attributed."), `ready` ("Whether the attributed sessions for the order have been created yet."), `daysToConversion` and `customerOrderIndex` (same URL, read 2026-10-20).
- Window: `daysToConversion` counts from "the first session since the last order, or the first session within the 30 day attribution window, if more than 30 days have passed since the last order." (same URL, read 2026-10-20).
- Each visit is a `CustomerVisit` with `landingPage`, `referrerUrl`, `referralCode`, `source`, `sourceDescription`, `sourceType`, `marketingEvent`, `occurredAt` and `utmParameters` ("A set of UTM parameters gathered from the URL parameters of the referrer.") (https://shopify.dev/docs/api/admin-graphql/latest/objects/CustomerVisit, read 2026-10-20).
- `referralCode` is the "Marketing referral code from the link that the customer clicked to visit the store. Supports the following URL attributes: *ref*, *source*, or *r*." Shopify's example: for `?ref=j2tj1tn2` the value is `j2tj1tn2` (same URL, read 2026-10-20).
- `UTMParameters` has five String fields: `campaign`, `content`, `medium`, `source` and `term` (https://shopify.dev/docs/api/admin-graphql/latest/objects/UTMParameters, read 2026-10-20).
- Reach: the `orders` query returns "the last 60 days worth of orders from a store by default", and "For large order datasets, consider using bulk operations" (https://shopify.dev/docs/api/admin-graphql/latest/queries/orders, read 2026-10-20). Filters accept comparisons such as `created_at:<=2024` (same URL, read 2026-10-20).
- Inferred: a link-attribution export can be one row per order with `name`, `discountCodes`, `ready`, and the last visit's `occurredAt`, `landingPage`, `referralCode` and `utmParameters`. Rows with `ready` false are read again later. Journey data is missing where the visitor declined tracking (see "Where referrer, landing page and UTM data live instead" above).

Illustrative query. We assembled it from the documented fields and have not tested it; try it in a development store first. The date is a placeholder.

```graphql
query OrdersWithJourney($cursor: String) {
  orders(first: 50, after: $cursor, query: "created_at:>=2026-11-01") {
    nodes {
      name
      discountCodes
      customerJourneySummary {
        ready
        lastVisit {
          occurredAt
          landingPage
          referralCode
          utmParameters { source medium campaign content term }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

## 7. What this means for a pay-per-sale creator programme

The three rails (inferred, from the sources above)
1. Shopify Collabs. It is free apart from 2.9% on automatic payouts, and it issues codes and links, holds commissions and pays creators through the Shopify bill. Three open questions: new creator signups are closed, the attribution window is undocumented, and Shopify's eligibility rules for a medical-device and adult-adjacent merchant are unconfirmed.
2. A third-party app (UpPromote, GOAFFPRO, Refersion, Social Snowball, LeadDyno, BixGrow, Tapfiliate, Superfiliate). It handles codes, links, tracking and payouts, mostly through PayPal, with ACH, gift cards or store credit on some plans. Entry cost runs from free to USD 1,500 a month, plus a percentage of sales on several plans.
3. The API (or a bulk-code app) plus a spreadsheet. Create one code per creator with `discountCodeBasicCreate` or `discountRedeemCodeBulkAdd` (`write_discounts`), export orders monthly, filter on "Discount Code", exclude refunds using "Financial Status" and "Refunded Amount", and pay creators outside Shopify. It costs least, but payouts, tax forms and leak control are all manual.

What the merchant must verify about its own store before choosing
- Its Shopify plan. Collabs excludes Starter and Retail, and API rate limits scale with plan.
- Whether Shopify Payments is active, or which third-party gateway processes cards, and whether Shopify has accepted the store's product categories. This bears on Collabs compatibility and on whether payouts via the Shopify bill are workable.
- Whether Shopify Network Intelligence is enabled, since Collabs requires it.
- Whether Collabs shows as compatible on the App Store install screen for this store.
- Whether target creators already have Collabs accounts, and whether an invite works for a creator without one.
- Whether the store already has apps or codes for affiliates, and how existing discount codes are named and used.
- Whether a PayPal Business account (or another payout account) is available for app payouts, and who will issue 1099s.
- How many orders are guest checkouts, which affects repeat-purchase attribution.

What cannot be known without logging into the store
- The plan, payment gateway and Shopify Payments status; installed apps; the Network Intelligence setting; Collabs compatibility.
- Existing discount codes and their redemption counts; the share of orders that carry a code; refund and cancellation rates.
- Order exports, conversion summaries and marketing-report data; whether UTM parameters are reaching the store.
- Whether Shopify has flagged any product or category for this store.
