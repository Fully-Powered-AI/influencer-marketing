# Programme file: Cedar Lane creator programme

Fixture for the campaign-plan scripts, 2026-10-20, in the shape of programme template 0.1.2. Every value below is invented for testing; none is the brand's.

## 1. Brand and products

- Brand name: Cedar Lane [owner]

- Brand name and one-line description: Cedar Lane, home-goods products [observed]
- Products, one per line: Canvas Tote, woven canvas, 4 oz and 8 oz [owner]
- Average order value, store currency, and the date it was measured: 40.00 USD, measured 2026-09-30 [observed]
- Gross margin band (a range is fine; it sets the commission ceiling): 55 to 65 percent [owner]
  State whether the band is on list price or on net revenue; the pack's scripts read it as on list price unless this says otherwise.
- Store currency: USD [observed]

## 2. Audience and markets

- Who the brand is for, in the brand's words: gay men [owner]
- Countries sold to and shipped to: United States [owner]
- Jurisdictions whose advertising rules apply (based on the actual audience, markets and activities): United States [default]
- Languages: English [owner]

## 3. Platforms

| platform | organic creator posts | paid by the brand | labelling and age gating required | why (cite `references/platform-and-compliance-notes.md` line or the owner) |
|---|---|---|---|---|
| instagram | with conditions: paid-partnership label and minimum age 18 set before posting [owner] | with conditions [owner] | yes | owner ruling |
| tiktok | no [owner] | with conditions [owner] | yes | owner ruling |
| youtube | with conditions: health-focused, nothing suggestive [owner] | with conditions [owner] | yes | owner ruling |
| x | yes [owner] | with conditions [owner] | yes | owner ruling |
| onlyfans (creator-owned pages) | unknown [open] | no [owner] | yes | owner ruling |
| reddit | unknown [open] | unknown [open] | yes | owner ruling |
| podcasts and newsletters | yes [owner] | yes [owner] | spoken disclosure | owner ruling |
| grindr and scruff (brand advertising only) | no [owner] | yes [owner] | yes | owner ruling |
| other | unknown [open] | unknown [open] | yes | owner ruling |

## 4. Compensation

- Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme: cpa [owner]
- Commission rate for `cpa` and `hybrid`, percent of the commission basis: 15 percent [owner]
- Commission basis: `subtotal after discounts, before shipping and tax` [default] or another: subtotal after discounts, before shipping and tax [default]
- Customer-facing discount carried by each creator's code, percent or fixed amount: 15 percent [owner]
- Whether creator codes combine with other discounts (other codes, automatic discounts, free shipping), and which ones: automatic discounts and free shipping, not other codes [owner]
- Codes after a campaign window: `end` with the window, or `stay active` [default stay active]: end [owner]
- Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to the refunded share of the order: full [default]
- Flat-fee anchors by tier, store currency, for the owner's reference only (ranges, not offers): nano / micro / mid / macro: none set [owner]
- When a flat or hybrid deal is allowed, and who approves one (role): hybrid only for mid tier and above, the owner approves each one [owner]
- Gifting: which products, how many units a year, and whether a post is expected: Canvas Tote 4 oz, up to 40 units a year, no post expected [owner]
- Break-even check inputs the `creator-outreach` skill uses: average order value, gross margin band, customer discount, commission rate (copied from above so a script can read one section): 40.00 USD; 55 to 65 percent; 15 percent; 15 percent [owner]
- Exceptions log pointer: section 12.

## 5. Tracking and attribution

- Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number: handle without punctuation followed by 15 [owner]
- Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values): store domain, utm_source=creator, utm_medium=social, utm_campaign=campaign slug, utm_content=creator_ref [owner]
- Landing pages: which page each product campaign sends to: the Tote product page [owner]
- Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]
- Cookie or click window the rail uses, in days, as the rail documents it: unknown [open]
- Holdback before a sale counts as commissionable, in days (refund window) [default 30]: 30 [default]
- Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]:
- What is Measured, what is Estimated: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]:
- Ranking metric for performance reports [default cost per tracked order]: cost per tracked order [default]
- Tracked orders below which a creator's read is called thin [default 5]: 5 [default]
- Store promotion codes that are not creators' codes (so the unattributed list shows only unknown codes), one per indented line:
  - WELCOME10, the newsletter first-order code [owner]

## 6. Shopify and the payout rail

- Store URL and Shopify plan: example store, plan unknown [open]
- Rail chosen: manual [owner]
- Prerequisites verified on the store, each with the date and the role that checked: none yet [open]
- How a creator joins: the pack's onboarding path [owner]
- Payout schedule (for example monthly, after the holdback) and minimum payout amount: monthly after the holdback, minimum 25.00 USD [owner]
- Who approves a statement before anything is paid (role), and who pays (role): owner approves, finance pays [owner]

## 7. Approved and forbidden claims

### Approved claims (verbatim wording the owner has cleared, one per line, with the product it applies to)

- Canvas Tote: woven canvas [owner]

### Forbidden claims (one per line, with the reason)

- Any unsupported performance, health, environmental or safety claim: device claim [default]

## 8. Disclosure rules

- Required disclosure wording and placement, per platform (text at the start of the caption, spoken aloud and on screen in video, platform paid-partnership tool switched on in addition): "Ad" at the start of the caption, spoken in video [owner]
- Words that do not count as disclosure (for example `#sp`, `#collab`, `#ambassador` alone, `thanks to`): as listed [default]
- Who checks a live post for disclosure and when (role; `publication-tracking` runs the check): programme lead, day 1 [owner]

## 9. Brand safety and content rules

- Explicitness policy: set by the owner [owner]
- Audience age: adults only [owner]
- Redlines: none listed [owner]
- Brand voice in a few words, for creators to understand, never to imitate word for word: playful [owner]
- Creative freedom: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]
- Competitor conflicts: other lubricant brands [owner]

## 10. Roles and approvals

| role | does | approves |
|---|---|---|
| owner | decides the programme | programme file changes |
| programme lead | runs discovery, outreach, briefs, tracking | shortlists, briefs |
| content reviewer | runs `content-approval` | go or no-go on content |
| finance | runs `commission-statement` | payout list |
| counsel | reviews agreement terms | agreement templates |

## 11. Legal

- Governing jurisdiction for agreements: New York [owner]
- Agreement template location and version (drafted by `partnership-agreement`, reviewed by counsel before first use): agreements/template-v1.md [owner]
- Default usage-rights window for reusing creator content (for example 6 months from posting), and whether paid reuse is included: 6 months from posting, organic reuse only [owner]
- Default exclusivity: none [default]
- Counsel review rule: no agreement is sent to a creator before counsel has reviewed the template once, and any non-template clause goes back to counsel [default]

## 12. Decisions log

- 2026-10-20, owner, fixture created for script tests, all sections
