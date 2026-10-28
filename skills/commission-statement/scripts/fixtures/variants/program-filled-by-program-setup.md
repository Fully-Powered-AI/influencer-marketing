# Programme file: Cedar Lane creator programme

Fixture for the script tests: every value below is invented to exercise the parser and is not a decision of the brand. Template version 0.1.2, 2026-10-20.

Mark every line with its source in square brackets.

## 1. Brand and products

- Brand name: Cedar Lane [owner]

- Brand name and one-line description: Cedar Lane, home-goods products for everyday spaces [owner]
- Products, one per line: name, category, materials or ingredients, variants, sizes, list price, and owner-cleared attributes. Unlisted product statements require review:
  - Canvas Tote: woven-canvas; 4 oz 16.00, 16 oz 34.00; cleared: fixture compatibility statement A [owner]
  - Desk Organizer: powder-coated; 16 oz 34.00; cleared: fixture compatibility statement B [owner]
- Average order value, store currency, and the date it was measured: 41.50 USD, from the store's own report, read 2026-10-21 by finance [observed]
- Gross margin band (a range is fine; it sets the commission ceiling): 55 to 65 percent [owner]
  State whether the band is on list price or on net revenue; the pack's scripts read it as on list price unless this says otherwise.
  on list price [owner]
- Store currency: USD [observed]

## 2. Audience and markets

- Who the brand is for, in the brand's words: fixture audience line [owner]
- Countries sold to and shipped to: United States [owner]
- Jurisdictions whose advertising rules apply (based on the actual audience, markets and activities): United States [default]
- Languages: English [owner]

## 3. Platforms

One row per platform.

| platform | organic creator posts | paid by the brand | labelling and age gating required | why (cite `references/platform-and-compliance-notes.md` line or the owner) |
|---|---|---|---|---|
| instagram | with conditions: pending the branded-content confirmation | with conditions: health focus, 18+ | paid-partnership tool; 18+ | notes 5 Meta [owner] |
| tiktok | no | with conditions: US, 18+, health focus | none while organic is no | notes 5 TikTok [owner] |
| youtube | with conditions: health focus | with conditions: 18+, listed countries | paid promotion box; spoken disclosure | notes 5 YouTube [owner] |
| x | with conditions: commercial language | with conditions: no innuendo | Paid Partnership label | notes 5 X [owner] |
| onlyfans (creator-owned pages) | unknown | unknown | not in the references | not in the references; verify [owner] |
| reddit | unknown | unknown | Brand Affiliate tag, secondary | notes 5 Reddit [owner] |
| podcasts and newsletters | with conditions: spoken disclosure | unknown | spoken and written disclosure | notes 1 [owner] |
| grindr and scruff (brand advertising only) | no | yes | adults-only apps | notes 5 Grindr, Scruff [owner] |
| other | unknown | unknown | none | no platform named [owner] |

Allowed values for the two middle columns: `yes`, `no`, `with conditions` (state them), `unknown`. End each row's last cell with its mark.

- The brand's own channels (site pages, email list, social accounts with their handles, retail partners), one per indented line, each with the role that publishes on it:
  - site product pages: channel publisher [owner]
  - email list: channel publisher [owner]
  - instagram @fixturebrand: channel publisher [owner]

## 4. Compensation

The programme's answer to "pay for sales or pay for reach".

- Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme: cpa [default]
- Commission rate for `cpa` and `hybrid`, percent of the commission basis: 15 [owner]
- Commission basis: `subtotal after discounts, before shipping and tax` [default] or another: subtotal after discounts, before shipping and tax [default]
- Customer-facing discount carried by each creator's code, percent or fixed amount: 15 percent [owner]
- Whether creator codes combine with other discounts (other codes, automatic discounts, free shipping), and which ones: no other code or order discount; free-shipping offers yes [owner]
- Flat-fee anchors by tier, store currency, for the owner's reference only (ranges, not offers): nano / micro / mid / macro: none set [owner]
- When a flat or hybrid deal is allowed, and who approves one (role): only with the owner's written approval, per creator [owner]
- Gifting: which products, how many units a year, and whether a post is expected: one unit of the product to be posted about, no post required [owner]
- Break-even check inputs the `creator-outreach` skill uses: average order value, gross margin band, customer discount, commission rate (copied from above so a script can read one section): average order value 41.50; margin 55 to 65; discount 15; commission 15 [owner]
- Codes after a campaign window: `end` with the window, or `stay active` [default stay active]: stay active [default]
- Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to the refunded share of the order: full refunded amount [default]
- Exceptions log pointer: section 12.

## 5. Tracking and attribution

- Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number: `{HANDLE}{DISCOUNT}` [owner]
  Write it as a brace template, for example `{HANDLE}{DISCOUNT}`; the tokens are `{HANDLE}`, `{NAME}`, `{REF}` and `{DISCOUNT}` (`skills/affiliate-onboarding/references/code-and-link-schemes.md`).
- Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values): `https://www.example.com/pages/creator?utm_source=creator&utm_medium={platform}&utm_campaign={campaign}&utm_content={ref}` [owner]
  Write it as an `https://` template with `{handle}`, `{ref}`, `{code}`, `{platform}` and `{campaign}` where they belong.
- Landing pages: which page each product campaign sends to: the product page of the product named in the brief [owner]
- Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]
- Cookie or click window the rail uses, in days, as the rail documents it: not documented by the rail as read [observed]
- Holdback before a sale counts as commissionable, in days (refund window) [default 30]: 30 [default]
- Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]
- What is Measured, what is Estimated: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]
- Ranking metric for performance reports [default cost per tracked order]: cost per tracked order [default]
- Tracked orders below which a creator's read is called thin [default 5]: 5 [default]
- Store promotion codes that are not creators' codes (so the unattributed list shows only unknown codes), one per indented line:
  - WELCOME10: newsletter first-order offer [owner]

## 6. Shopify and the payout rail

- Store URL and Shopify plan: fixture-store.myshopify.com, plan as reported by finance [owner]
- Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet: manual [owner]
- Prerequisites verified on the store, each with the date and the role that checked: Shopify Payments active, country supported, Collabs or app installed, discount-creation access, API access scope and token custodian role:
  - verified 2026-10-21 by finance: discount-creation access [owner]
  - verified 2026-10-21 by finance: write_discounts scope, token held by finance [owner]
- How a creator joins: application page URL (Collabs or app), or the pack's onboarding path: the pack's onboarding path [owner]
- Payout schedule (for example monthly, after the holdback) and minimum payout amount: monthly after the holdback, minimum 25.00 [owner]
  Write the minimum as `minimum <amount>` or `no minimum`.
- Who approves a statement before anything is paid (role), and who pays (role): owner approves, finance pays [owner]

## 7. Approved and forbidden claims

Creators may say about the product only what is under "Approved".

Review prompts for owner-supplied product evidence.

- Product specifications that conflict across sources: settled 2026-10-21: fixture ruling one [owner]
- Variant-specific claims that differ from general product copy: settled 2026-10-21: fixture ruling two [owner]
- Ingredient or material statements that conflict with the current label: settled 2026-10-21: fixture ruling three [owner]
- Directions or intended-use statements needing owner confirmation: settled 2026-10-21: fixture ruling four [owner]

### Approved claims (verbatim wording the owner has cleared, one per line, with the product it applies to)

- Canvas Tote: "fixture approved statement one" [owner]
- Desk Organizer: "fixture approved statement two" [owner]

### Forbidden claims (one per line, with the reason)

- Any unsupported performance, health, environmental or safety claim: "prevents all damage", "protects against STIs"; outside a lubricant's cleared indications [owner]
- Any compatibility statement not listed under Approved for that exact product: "works with every appliance"; compatibility is product-specific [owner]
- Any material or ingredient performance claim beyond the approved evidence: unsubstantiated health claim [owner]
- Comparisons to a named competitor: the owner has not cleared any [owner]
- Fabricated personal results or an implied customer relationship that does not exist: endorsement rules [owner]

## 8. Disclosure rules

- Required disclosure wording and placement, per platform (text at the start of the caption, spoken aloud and on screen in video, platform paid-partnership tool switched on in addition):
  - instagram: "#ad" at the start of the caption, paid-partnership tool on [owner]
  - youtube: "#ad" in the first line of the description; spoken: this video is sponsored by Cedar Lane; in the first 30 seconds and on screen; paid promotion box ticked [owner]
  - x: "#ad" at the start of the post, Paid Partnership label on [owner]
  - podcast: "This episode is sponsored by Cedar Lane" read aloud before the mention; spoken: this episode is sponsored by Cedar Lane [owner]
  - newsletter: "Sponsored" above the mention, with a commission sentence beside the link [owner]
- Words that do not count as disclosure (for example `#sp`, `#collab`, `#ambassador` alone, `thanks to`): "#sp", "#spon", "#collab", "#ambassador" alone, "thanks" alone [owner]
- Who checks a live post for disclosure and when (role; `publication-tracking` runs the check): programme lead, on the day of posting [owner]
- Time a creator has to correct a live post after being asked, in days: 2 [owner]

## 9. Brand safety and content rules

- Content suitability policy: permitted themes and presentation for the category and markets (the owner decides; the pack has no category default): fixture policy [owner]
- Audience age: applicable audience restrictions and required evidence, or none with a reason: the platform's adults-only setting where it exists [owner]
- Redlines: topics, words, imagery or associations the brand will not appear beside: fixture redlines [owner]
- Brand voice in a few words, for creators to understand, never to imitate word for word: fixture voice [owner]
- Creative freedom: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]
- Competitor conflicts: which categories count as competitors for exclusivity purposes: home-goods products [owner]
  Name the competitor brands, so discovery can note a creator's mentions of them.
  fixture competitor brand one; fixture competitor brand two [owner]

## 10. Roles and approvals

| role | does | approves |
|---|---|---|
| owner | decides the programme, signs agreements, approves exceptions | programme file changes, flat and hybrid deals, statements [owner] |
| programme lead | runs discovery, outreach, briefs, tracking | shortlists, briefs, publication receipts [owner] |
| content reviewer | runs `content-approval` | go or no-go on content [owner] |
| finance | runs `commission-statement`, pays through the rail | payout list after the owner's approval [owner] |
| counsel | reviews agreement terms | agreement templates and any clause change [owner] |
| channel publisher | publishes and removes reuse placements on the brand's own channels (site, email, social) | nothing [owner] |

- Sending account per outreach channel (which brand account or mailbox sends creator outreach; the programme lead writes as the brand unless stated): email from the brand's partnerships mailbox; instagram DMs from the brand account [owner]

## 11. Legal

- Governing jurisdiction for agreements: fixture state [owner]
- Agreement template location and version (drafted by `partnership-agreement`, reviewed by counsel before first use): agreements/template-v1.md, not yet reviewed [owner]
- Default usage-rights window for reusing creator content (for example 6 months from posting), and whether paid reuse is included: 6 months, organic reuse only [owner]
- Default exclusivity: none [default], or the category and period: none [default]
- Counsel review rule: no agreement is sent to a creator before counsel has reviewed the template once, and any non-template clause goes back to counsel [default]: no agreement is sent to a creator before counsel has reviewed the template once, and any non-template clause goes back to counsel [default]
- Counsel review record, in the form `reviewed by counsel YYYY-MM-DD, version N`: reviewed by counsel 2026-10-25, version 1 [owner]
- Whether the terms sheet itself may go to creators after counsel's review, or only counsel's full agreement: only counsel's full agreement [owner]
- Dispute window on a commission statement, in days: 14 [owner]
- Minimum time a post stays live, in days: 30 [owner]
- Brand approval turnaround on submitted content, in days: 3 [owner]
- Time allowed to take down a post after notice, in days: 2 [owner]
- Notice period for ending without cause, in days: 30 [owner]

## 12. Decisions log

- 2026-10-21, owner, programme file set up with program-setup 0.1.0 (fixture), sections 1 to 11
