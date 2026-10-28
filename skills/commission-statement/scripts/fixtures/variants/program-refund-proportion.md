# Programme file: Cedar Lane creator programme (test fixture for commission-statement, invented values)

Template version 0.1.2, 2026-10-20 (0.1.2 adds lines to sections 3, 4, 5, 6, 8, 9, 10 and 11; no earlier line changed). The `program-setup` skill fills this in with the owner and saves it as `<workspace>/program/program.md`. Every other skill in the pack reads it first and takes its rules from here, never from its own knowledge. Headings are fixed: skills find sections by their numbers. A blank line under a heading means "not yet decided"; a skill that needs it stops and asks, once.

Mark every line with its source in square brackets: `[owner]` for what the owner said, `[observed]` for what was read from a public page or the store on a date, `[default]` for a pack default the owner accepted, `[open]` for an undecided item. Write the value after the template's text on each line and put the mark last; never edit the template's text, because scripts find each line by it. Extra detail goes on indented lines under the field, each with its own mark.

## 1. Brand and products

- Brand name: Cedar Lane [owner]

- Brand name and one-line description: Cedar Lane, fixture programme for the commission-statement tests [default]
- Products, one per line: name, category, materials or ingredients, variants, sizes, list price, and owner-cleared attributes. Unlisted product statements require review:
- Average order value, store currency, and the date it was measured:
- Gross margin band (a range is fine; it sets the commission ceiling):
  State whether the band is on list price or on net revenue; the pack's scripts read it as on list price unless this says otherwise.
- Store currency: USD [observed]

## 2. Audience and markets

- Who the brand is for, in the brand's words:
- Countries sold to and shipped to:
- Jurisdictions whose advertising rules apply (based on the actual audience, markets and activities):
- Languages:

## 3. Platforms

One row per platform. "Organic" means a creator's own post about the product; "paid" means the brand's own advertising, including boosting a creator's post.

| platform | organic creator posts | paid by the brand | labelling and age gating required | why (cite `references/platform-and-compliance-notes.md` line or the owner) |
|---|---|---|---|---|
| instagram | | | | |
| tiktok | | | | |
| youtube | | | | |
| x | | | | |
| onlyfans (creator-owned pages) | | | | |
| reddit | | | | |
| podcasts and newsletters | | | | |
| grindr and scruff (brand advertising only) | | | | |
| other | | | | |

Allowed values for the two middle columns: `yes`, `no`, `with conditions` (state them), `unknown`. End each row's last cell with its mark.

- The brand's own channels (site pages, email list, social accounts with their handles, retail partners), one per indented line, each with the role that publishes on it:

## 4. Compensation

The programme's answer to "pay for sales or pay for reach". Fill every line; `none` is an answer.

- Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme: cpa [owner]
- Commission rate for `cpa` and `hybrid`, percent of the commission basis: 15 [owner]
- Commission basis: `subtotal after discounts, before shipping and tax` [default] or another: subtotal after discounts, before shipping and tax [default]
- Customer-facing discount carried by each creator's code, percent or fixed amount:
- Whether creator codes combine with other discounts (other codes, automatic discounts, free shipping), and which ones: other codes no, automatic discounts yes, free shipping yes [owner]
- Flat-fee anchors by tier, store currency, for the owner's reference only (ranges, not offers): nano / micro / mid / macro:
- When a flat or hybrid deal is allowed, and who approves one (role):
- Gifting: which products, how many units a year, and whether a post is expected:
- Break-even check inputs the `creator-outreach` skill uses: average order value, gross margin band, customer discount, commission rate (copied from above so a script can read one section):
- Codes after a campaign window: `end` with the window, or `stay active` [default stay active]:
- Partial refunds: subtract the full refunded amount from the basis [default], or in proportion to the refunded share of the order: in proportion [owner]
- Exceptions log pointer: section 12.

## 5. Tracking and attribution

- Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number:
  Write it as a brace template, for example `{HANDLE}{DISCOUNT}`; the tokens are `{HANDLE}`, `{NAME}`, `{REF}` and `{DISCOUNT}` (`skills/affiliate-onboarding/references/code-and-link-schemes.md`).
- Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values):
  Write it as an `https://` template with `{handle}`, `{ref}`, `{code}`, `{platform}` and `{campaign}` where they belong.
- Landing pages: which page each product campaign sends to:
- Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report: code first, then tracked link [default]
- Cookie or click window the rail uses, in days, as the rail documents it:
- Holdback before a sale counts as commissionable, in days (refund window) [default 30]: 30 [default]
- Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]: applies [default]
- What is Measured, what is Estimated: Measured is an order in the store export with a code or tracked link; Estimated is anything inferred from views, reach or a creator's screenshot [default]:
- Ranking metric for performance reports [default cost per tracked order]:
- Tracked orders below which a creator's read is called thin [default 5]:
- Store promotion codes that are not creators' codes (so the unattributed list shows only unknown codes), one per indented line:
  - WELCOME10 [owner]

## 6. Shopify and the payout rail

- Store URL and Shopify plan:
- Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet: manual [owner]
- Prerequisites verified on the store, each with the date and the role that checked: Shopify Payments active, country supported, Collabs or app installed, discount-creation access, API access scope and token custodian role:
- How a creator joins: application page URL (Collabs or app), or the pack's onboarding path:
- Payout schedule (for example monthly, after the holdback) and minimum payout amount: monthly, after the holdback; minimum 25 [owner]
  Write the minimum as `minimum <amount>` or `no minimum`.
- Who approves a statement before anything is paid (role), and who pays (role): owner approves; finance pays [default]

## 7. Approved and forbidden claims

Creators may say about the product only what is under "Approved". Anything under "Forbidden" is a stop in `content-approval`. A claim not on either list is "ask", and `content-approval` routes it to the owner.

Review prompts for owner-supplied product evidence (`references/brand-context.md` section 2). The owner settles each before any claim it touches enters Approved; replace `[open]` with the ruling and `[owner]`:

- Product specifications that conflict across sources: [open]
- Variant-specific claims that differ from general product copy: [open]
- Ingredient or material statements that conflict with the current label: [open]
- Directions or intended-use statements needing owner confirmation: [open]

### Approved claims (verbatim wording the owner has cleared, one per line, with the product it applies to)

### Forbidden claims (one per line, with the reason)

- Any unsupported performance, health, environmental or safety claim:
- Any compatibility statement not listed under Approved for that exact product:
- Any material or ingredient performance claim beyond the approved evidence:
- Comparisons to a named competitor:
- Fabricated personal results or an implied customer relationship that does not exist:

## 8. Disclosure rules

- Required disclosure wording and placement, per platform (text at the start of the caption, spoken aloud and on screen in video, platform paid-partnership tool switched on in addition):
- Words that do not count as disclosure (for example `#sp`, `#collab`, `#ambassador` alone, `thanks to`):
- Who checks a live post for disclosure and when (role; `publication-tracking` runs the check):
- Time a creator has to correct a live post after being asked, in days:

## 9. Brand safety and content rules

- Content suitability policy: permitted themes and presentation for the category and markets (the owner decides; the pack has no category default):
- Audience age: applicable audience restrictions and required evidence, or none with a reason:
- Redlines: topics, words, imagery or associations the brand will not appear beside:
- Brand voice in a few words, for creators to understand, never to imitate word for word:
- Creative freedom: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]:
- Competitor conflicts: which categories count as competitors for exclusivity purposes:
  Name the competitor brands, so discovery can note a creator's mentions of them.

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

- Sending account per outreach channel (which brand account or mailbox sends creator outreach; the programme lead writes as the brand unless stated):

## 11. Legal

- Governing jurisdiction for agreements:
- Agreement template location and version (drafted by `partnership-agreement`, reviewed by counsel before first use):
- Default usage-rights window for reusing creator content (for example 6 months from posting), and whether paid reuse is included:
- Default exclusivity: none [default], or the category and period:
- Counsel review rule: no agreement is sent to a creator before counsel has reviewed the template once, and any non-template clause goes back to counsel [default]:
- Counsel review record, in the form `reviewed by counsel YYYY-MM-DD, version N`:
- Whether the terms sheet itself may go to creators after counsel's review, or only counsel's full agreement:
- Dispute window on a commission statement, in days:
- Minimum time a post stays live, in days:
- Brand approval turnaround on submitted content, in days:
- Time allowed to take down a post after notice, in days:
- Notice period for ending without cause, in days:

## 12. Decisions log

Dated entries, newest last: `YYYY-MM-DD, role, what was decided, which section changed`.
