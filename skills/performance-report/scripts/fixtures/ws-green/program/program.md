# Programme file: Cedar Lane creator programme

Fixture for performance-report's tests, 2026-10-20, on template 0.1.2. Every value below is invented for the tests; none is the client's.

## 1. Brand and products

- Brand name: Cedar Lane [owner]

- Brand name and one-line description: fixture brand [owner]
- Products, one per line: name, category, materials or ingredients, variants, sizes, list price, and owner-cleared attributes. Unlisted product statements require review: fixture product, water, 16 oz, 40.00 [owner]
- Average order value, store currency, and the date it was measured: 32.00 USD, 2026-10-01 [owner]
- Gross margin band (a range is fine; it sets the commission ceiling): 60 to 70 percent [owner]
  State whether the band is on list price or on net revenue; the pack's scripts read it as on list price unless this says otherwise. on list price [owner]
- Store currency: USD [owner]

## 2. Audience and markets

- Who the brand is for, in the brand's words:
- Countries sold to and shipped to:
- Jurisdictions whose advertising rules apply (based on the actual audience, markets and activities): United States [default]
- Languages:

## 3. Platforms

| platform | organic creator posts | paid by the brand | labelling and age gating required | why (cite `references/platform-and-compliance-notes.md` line or the owner) |
|---|---|---|---|---|
| instagram | with conditions: health focus, adults only [owner] | unknown | yes | fixture [owner] |
| tiktok | no [owner] | no | yes | fixture [owner] |
| youtube | yes [owner] | unknown | yes | fixture [owner] |
| x | yes [owner] | unknown | yes | fixture [owner] |
| onlyfans (creator-owned pages) | unknown | no | yes | fixture [owner] |
| reddit | unknown | unknown | yes | fixture [owner] |
| podcasts and newsletters | yes [owner] | unknown | yes | fixture [owner] |
| grindr and scruff (brand advertising only) | no | unknown | yes | fixture [owner] |
| other | unknown | unknown | yes | fixture [owner] |

Allowed values for the two middle columns: `yes`, `no`, `with conditions` (state them), `unknown`. End each row's last cell with its mark.

## 4. Compensation

- Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme: cpa [default]
- Commission rate for `cpa` and `hybrid`, percent of the commission basis: 15 [owner]
- Commission basis: `subtotal after discounts, before shipping and tax` [default] or another: subtotal after discounts, before shipping and tax [default]
- Customer-facing discount carried by each creator's code, percent or fixed amount: 15 percent [owner]
- Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to the refunded share of the order: subtract the full refunded amount [default]
- Flat-fee anchors by tier, store currency, for the owner's reference only (ranges, not offers): nano / micro / mid / macro: none [owner]
- When a flat or hybrid deal is allowed, and who approves one (role): owner approves each [owner]
- Gifting: which products, how many units a year, and whether a post is expected: fixture product, up to 3 units per creator, no post expected [owner]
- Break-even check inputs the `creator-outreach` skill uses: average order value, gross margin band, customer discount, commission rate (copied from above so a script can read one section): 32.00; 60 to 70 percent; 15 percent; 15 [owner]
- Exceptions log pointer: section 12.

## 5. Tracking and attribution

- Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number: handle then 15 [owner]
- Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values): https://www.example.com/products/fixture with utm_source=creator [owner]
- Landing pages: which page each product campaign sends to: https://www.example.com/products/fixture [owner]
- Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report: code first, link second [default]
- Cookie or click window the rail uses, in days, as the rail documents it: unknown [open]
- Holdback before a sale counts as commissionable, in days (refund window) [default 30]: 30 [default]
- Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]: applies [default]
- Ranking metric for performance reports [default cost per tracked order]: cost per tracked order [default]
- Tracked orders below which a creator's read is called thin [default 5]: 5 [default]
- Store promotion codes that are not creators' codes (so the unattributed list shows only unknown codes), one per indented line:
  WELCOME10: newsletter first-order offer [owner]
- What is Measured, what is Estimated: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]: as written [default]

## 6. Shopify and the payout rail

- Store URL and Shopify plan: https://www.example.com, plan unknown [owner]
- Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet: app [owner]

## 7. Approved and forbidden claims

## 8. Disclosure rules

## 9. Brand safety and content rules

## 10. Roles and approvals

## 11. Legal

## 12. Decisions log
