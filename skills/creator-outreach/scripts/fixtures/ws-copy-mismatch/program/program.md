# Programme file: Cedar Lane creator programme

Fixture for scripts/fixtures only, written 2026-10-20. Every value below is invented for testing and is not the client's programme. Headings and line text follow template version 0.1.2.

Mark every line with its source in square brackets: `[owner]` for what the owner said, `[observed]` for what was read from a public page or the store on a date, `[default]` for a pack default the owner accepted, `[open]` for an undecided item.

## 1. Brand and products

- Brand name: Cedar Lane [owner]

- Brand name and one-line description: fixture brand [owner]
- Products, one per line: name, category, materials or ingredients, variants, sizes, list price, and owner-cleared attributes. Unlisted product statements require review: fixture product, water, 4 oz, 16.00 [owner]
- Average order value, store currency, and the date it was measured: 42.00 USD, measured 2026-09-30 [owner]
  - measured over the 90 days to 2026-09-30, before discounts, from the store's sales report [owner]
- Gross margin band (a range is fine; it sets the commission ceiling): 55 to 65 percent [owner]
  State whether the band is on list price or on net revenue; the pack's scripts read it as on list price unless this says otherwise. On list price [owner]
- Store currency: USD [observed]

## 2. Audience and markets

- Who the brand is for, in the brand's words: fixture audience [owner]
- Countries sold to and shipped to: United States [owner]
- Jurisdictions whose advertising rules apply (based on the actual audience, markets and activities): United States [default]
- Languages: English [owner]

## 3. Platforms

One row per platform. "Organic" means a creator's own post about the product; "paid" means the brand's own advertising, including boosting a creator's post.

| platform | organic creator posts | paid by the brand | labelling and age gating required | why (cite `references/platform-and-compliance-notes.md` line or the owner) |
|---|---|---|---|---|
| instagram | with conditions: post age-restricted to 18 and over [owner] | with conditions [owner] | paid-partnership label and age restriction [owner] | fixture |
| tiktok | no [owner] | with conditions [owner] | not applicable [owner] | fixture |
| youtube | yes [owner] | no [owner] | paid promotion box [owner] | fixture |
| x | yes [owner] | no [owner] | sensitive media setting [owner] | fixture |
| onlyfans (creator-owned pages) | unknown [open] | no [owner] | | fixture |
| reddit | unknown [open] | no [owner] | | fixture |
| podcasts and newsletters | yes [owner] | no [owner] | spoken disclosure [owner] | fixture |
| grindr and scruff (brand advertising only) | no [owner] | yes [owner] | | fixture |
| other | unknown [open] | no [owner] | | fixture |

Allowed values for the two middle columns: `yes`, `no`, `with conditions` (state them), `unknown`. End each row's last cell with its mark.

- The brand's own channels (site pages, email list, social accounts with their handles, retail partners), one per indented line, each with the role that publishes on it:
  - the brand Instagram account, channel publisher [owner]

## 4. Compensation

The programme's answer to "pay for sales or pay for reach". Fill every line; `none` is an answer.

- Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme: cpa [owner]
- Commission rate for `cpa` and `hybrid`, percent of the commission basis: 15 [owner]
- Commission basis: `subtotal after discounts, before shipping and tax` [default] or another: subtotal after discounts, before shipping and tax [default]
- Customer-facing discount carried by each creator's code, percent or fixed amount: 15 percent [owner]
- Whether creator codes combine with other discounts (other codes, automatic discounts, free shipping), and which ones: free shipping only [owner]
- Flat-fee anchors by tier, store currency, for the owner's reference only (ranges, not offers): nano / micro / mid / macro:
  - nano 0 to 150 [owner]
  - micro 150 to 600 [owner]
  - mid 600 to 2,500 [owner]
  - macro by exception [owner]
- When a flat or hybrid deal is allowed, and who approves one (role): only for mid and macro creators with a reach objective in the campaign plan; the owner approves each one in writing [owner]
- Gifting: which products, how many units a year, and whether a post is expected: one fixture product per creator, no post expected [owner]
- Break-even check inputs the `creator-outreach` skill uses: average order value, gross margin band, customer discount, commission rate (copied from above so a script can read one section): average order value 42.00, gross margin band 55 to 65, customer discount 15 percent, commission rate 20 [owner]
- Codes after a campaign window: `end` with the window, or `stay active` [default stay active]: stay active [default]
- Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to the refunded share of the order: full refunded amount [default]
- Exceptions log pointer: section 12.

## 5. Tracking and attribution

- Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number: handle plus 15 [owner]
- Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values): fixture [owner]
- Landing pages: which page each product campaign sends to: fixture [owner]
- Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report: as stated [default]
- Cookie or click window the rail uses, in days, as the rail documents it: unknown [open]
- Holdback before a sale counts as commissionable, in days (refund window) [default 30]: 30 [default]
- Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]: as stated [default]
- What is Measured, what is Estimated: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]: as stated [default]

## 6. Shopify and the payout rail

- Store URL and Shopify plan: fixture [owner]
- Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet: manual [owner]
- Prerequisites verified on the store, each with the date and the role that checked: Shopify Payments active, country supported, Collabs or app installed, discount-creation access, API access scope and token custodian role: fixture [owner]
- How a creator joins: application page URL (Collabs or app), or the pack's onboarding path: the pack's onboarding path [owner]
- Payout schedule (for example monthly, after the holdback) and minimum payout amount: monthly after the holdback, minimum 25.00 [owner]
- Who approves a statement before anything is paid (role), and who pays (role): owner approves, finance pays [owner]

## 7. Approved and forbidden claims

Creators may say about the product only what is under "Approved". Anything under "Forbidden" is a stop in `content-approval`. A claim not on either list is "ask", and `content-approval` routes it to the owner.

### Approved claims (verbatim wording the owner has cleared, one per line, with the product it applies to)

- "Compatible with model A appliances." Fixture product only. [owner]

### Forbidden claims (one per line, with the reason)

- Any unsupported performance, health, environmental or safety claim: forbidden [default]
- Any compatibility statement not listed under Approved for that exact product: forbidden [default]
- Any material or ingredient performance claim beyond the approved evidence: forbidden [default]
- Comparisons to a named competitor: forbidden [default]
- Fabricated personal results or an implied customer relationship that does not exist: forbidden [default]

## 8. Disclosure rules

- Required disclosure wording and placement, per platform (text at the start of the caption, spoken aloud and on screen in video, platform paid-partnership tool switched on in addition): "Ad" at the start of the caption, spoken and on screen in video, platform tool on as well [owner]
- Words that do not count as disclosure (for example `#sp`, `#collab`, `#ambassador` alone, `thanks to`): as listed [default]
- Who checks a live post for disclosure and when (role; `publication-tracking` runs the check): programme lead, day 1 [owner]

## 9. Brand safety and content rules

- Content suitability policy: permitted themes and presentation for the category and markets (the owner decides; the pack has no category default): fixture [owner]
- Audience age: applicable audience restrictions and required evidence, or none with a reason: fixture [owner]
- Redlines: topics, words, imagery or associations the brand will not appear beside: fixture [owner]
- Brand voice in a few words, for creators to understand, never to imitate word for word: fixture [owner]
- Creative freedom: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]: as stated [default]
- Competitor conflicts: which categories count as competitors for exclusivity purposes: home-goods products [owner]

## 10. Roles and approvals

Roles, never names. A skill addresses its handoff to a role.

| role | does | approves |
|---|---|---|
| owner | decides the programme, signs agreements, approves exceptions | programme file changes, flat and hybrid deals, statements |
| programme lead | runs discovery, outreach, briefs, tracking | shortlists, briefs, publication receipts |
| content reviewer | runs `content-approval` | go or no-go on content |
| finance | runs `commission-statement`, pays through the rail | payout list after the owner's approval |
| counsel | reviews agreement terms | agreement templates and any clause change |
| channel publisher | publishes and removes reuse placements on the brand's own channels (site, email, social) | nothing |

- Sending account per outreach channel (which brand account or mailbox sends creator outreach; the programme lead writes as the brand unless stated): DMs from the brand Instagram account; email from the partnerships mailbox; the programme lead writes as themselves at the brand [owner]

## 11. Legal

- Governing jurisdiction for agreements: fixture [owner]
- Agreement template location and version (drafted by `partnership-agreement`, reviewed by counsel before first use): fixture [owner]
- Default usage-rights window for reusing creator content (for example 6 months from posting), and whether paid reuse is included: 6 months from posting, organic reuse only [owner]
- Default exclusivity: none [default], or the category and period: none [default]
- Counsel review rule: no agreement is sent to a creator before counsel has reviewed the template once, and any non-template clause goes back to counsel [default]: as stated [default]

## 12. Decisions log

Dated entries, newest last: `YYYY-MM-DD, role, what was decided, which section changed`.

- 2026-10-20, owner, fixture programme written for tests, all sections.
