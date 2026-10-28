# Programme file: Cedar Lane creator programme

Fixture for the content-approval scripts, 2026-10-20. Not the client's programme: every product name and claim below is a test string, not a cleared claim. Shaped on template version 0.1.2, with sections 7 and 8 in the line shapes program-setup writes.

## 1. Brand and products

- Brand name: Cedar Lane [owner]

- Brand name and one-line description: Cedar Lane, fixture description [owner]
- Products, one per line: name, category, materials or ingredients, variants, sizes, list price, and owner-cleared attributes. Unlisted product statements require review: Canvas Tote (fixture), water, compatible with model A appliances [owner]
- Average order value, store currency, and the date it was measured: 30.00 USD, 2026-10-01 [owner]
- Gross margin band (a range is fine; it sets the commission ceiling): 50 to 60 percent [owner]
- Store currency: USD [owner]

## 2. Audience and markets

- Who the brand is for, in the brand's words: fixture audience [owner]
- Countries sold to and shipped to: United States [owner]
- Jurisdictions whose advertising rules apply (based on the actual audience, markets and activities): United States [default]
- Languages: English [owner]

## 3. Platforms

| platform | organic creator posts | paid by the brand | labelling and age gating required | why (cite `references/platform-and-compliance-notes.md` line or the owner) |
|---|---|---|---|---|
| instagram | yes | no | paid-partnership label; 18+ setting | fixture value [owner] |
| tiktok | no | no | not used | fixture value [owner] |
| youtube | with conditions: nothing sexually suggestive | no | paid promotion box; 18+ setting | fixture value [owner] |
| x | unknown | unknown | unknown | fixture value [open] |
| onlyfans (creator-owned pages) | unknown | no | unknown | fixture value [open] |
| reddit | unknown | unknown | unknown | fixture value [open] |
| podcasts and newsletters | yes | no | spoken disclosure | fixture value [owner] |
| grindr and scruff (brand advertising only) | no | yes | not used | fixture value [owner] |
| other | unknown | unknown | unknown | fixture value [open] |

## 4. Compensation

- Default model for new creators: `cpa` (commission on tracked sales), `flat` (fee per deliverable), `hybrid` (small fee plus commission), `gift` (product only). Default for this programme: cpa [owner]

## 5. Tracking and attribution

- Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number: fixture scheme [owner]

## 6. Shopify and the payout rail

- Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet: manual [owner]

## 7. Approved and forbidden claims

Creators may say about the product only what is under "Approved". Anything under "Forbidden" is a stop in `content-approval`. A claim not on either list is "ask", and `content-approval` routes it to the owner.

- Product specifications that conflict across sources: [open]

### Approved claims (verbatim wording the owner has cleared, one per line, with the product it applies to)

- Canvas Tote (fixture): "Cotton canvas construction" [owner]
- Canvas Tote (fixture): "Compatible with model A appliances" [owner]
- Desk Tray (fixture): "Washes off with water" [owner]

### Forbidden claims (one per line, with the reason)

- Any unsupported performance, health, environmental or safety claim: "prevents all damage", "protects against HIV" [default]
- Any compatibility statement not listed under Approved for that exact product: "works with every appliance" [default]
- Any material or ingredient performance claim beyond the approved evidence: [default]
- Comparisons to a named competitor: [default]
- Fabricated personal results or an implied customer relationship that does not exist: [default]

## 8. Disclosure rules

- Required disclosure wording and placement, per platform (text at the start of the caption, spoken aloud and on screen in video, platform paid-partnership tool switched on in addition): per platform, below [owner]
  - instagram: "#ad" at the start of the caption; spoken and on screen in video; paid-partnership label on [owner]
  - youtube: "#ad" in the first line of the description; spoken: this video is sponsored by Cedar Lane; on screen in the first seconds; paid promotion box ticked [owner]
- Words that do not count as disclosure (for example `#sp`, `#collab`, `#ambassador` alone, `thanks to`): `#sp`, `#collab`, `#ambassador`, "thanks to" [owner]
- Who checks a live post for disclosure and when (role; `publication-tracking` runs the check): programme lead, day 1 [owner]
- Time a creator has to correct a live post after being asked, in days: 2 [owner]

## 9. Brand safety and content rules

- Content suitability policy: permitted themes and presentation for the category and markets (the owner decides; the pack has no category default): fixture policy [owner]
- Audience age: applicable audience restrictions and required evidence, or none with a reason: the platform's 18+ setting where offered [owner]
- Redlines: topics, words, imagery or associations the brand will not appear beside: "gambling", "crypto giveaway" [owner]
- Creative freedom: creators speak in their own voice; the brand supplies the why, up to three talking points, the call to action and the guardrails, and does not script [default]:

## 10. Roles and approvals

| role | does | approves |
|---|---|---|
| owner | decides the programme | programme file changes |
| programme lead | runs briefs and tracking | briefs |
| content reviewer | runs `content-approval` | go or no-go on content |

## 11. Legal

- Governing jurisdiction for agreements: fixture [owner]

## 12. Decisions log

- 2026-10-20, owner, fixture programme written for tests, sections 1 to 11
