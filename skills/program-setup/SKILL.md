---
name: "program-setup"
description: "Sets up a consumer-brand creator programme with its owner: creates the shared workspace and fills program/program.md, the file every other skill in the pack reads first, with the products and their cleared claims, the platforms creators may post on, whether creators are paid per sale or for reach, codes and tracking, the Shopify payout rail, disclosure, brand safety, roles and the decisions log. Use when someone says 'set up the creator programme', 'start our influencer programme', 'fill in the programme file', 'should we pay creators per sale or per post', 'which platforms can creators post on', 'what are creators allowed to say about the product', 'change a programme rule' or 'is the programme file ready'. Not for finding creators (creator-discovery), drafting a creator's terms (partnership-agreement) or making codes (affiliate-onboarding)."
license: "MIT"
compatibility: "Claude Code, or claude.ai with custom skills enabled. Code execution on for the bundled Python 3 scripts (standard library only). No connectors; network none. Reads the pack's dated references at ../../references/, so install the pack folder whole. The owner, or someone with the owner's authority, takes part in the conversation."
metadata:
  version: "0.2.0"
  pack: "influencer-marketing"
  stage: "setup"
  built: "2026-10-20"
  reads-program-file: "yes"
allowed-tools: "Bash Read Write Edit"
---
# Programme setup

Create a runtime workspace and fill `program/program.md` with the owner's decisions. Every downstream skill reads this file. Keep the runtime workspace outside the installed public package. This skill creates local files; it does not contact creators, log into a store or issue payouts.

## Inputs

Read `../../references/brand-context.md`, `assets/program-template.md` and `../../references/schemas.md`. The owner supplies the brand, product evidence, markets and commercial rules. `../../references/platform-and-compliance-notes.md` and `../../references/shopify-affiliate-rails.md` contain dated source leads: verify relevant current sources at use. Do not import restricted-category examples as rules for unrelated products.

## Workflow

1. Use the user-designated runtime folder. Create it if authorized and absent, then run `python3 -I scripts/init_workspace.py <workspace>`. The script requires the folder to exist, copies the template, creates header-only CSVs and never overwrites existing files. A bad existing header stops initialization; hand that file to `creator-roster`.
2. Run `python3 -I scripts/init_workspace.py <workspace> --check --require all`. On an existing programme, change only requested decisions or unresolved fields. This check assesses machine-readable completeness, not compliance or permission to send.
3. Fill section 1 with the exact **Brand name**, description, product scope, variants, category, evidence, prices, currency, measured average order value and margin basis. Supporting evidence belongs in workspace `program/brand-facts.md` or `exports/`, with a pointer in the programme. No product facts ship with the package.
4. Fill section 2 from the owner's actual audience, countries, markets, jurisdictions and languages. Fill section 3 separately for organic posts and paid amplification, with conditions and dated source evidence. Verify category and market applicability first; leave unresolved decisions `unknown` or `[open]`. Read `references/platform-and-disclosure-proposals.md` for the format.
5. Review the four generic evidence prompts in section 7. Record each applicable contradiction and the owner's resolution; record `none found` with evidence when appropriate. Do not clear a claim affected by an unresolved conflict. Approved claims are verbatim, product-specific, owner-cleared lines. Forbidden phrases are exact quoted strings with unquoted reasons. Optional `Claim review cues` may replace the generic heuristic word list; cues never replace manual review.
6. Decide section 4 compensation with `references/compensation-models.md`. Run `python3 -I scripts/compare_models.py <workspace>` after average order value, margin, discount and commission are filled. Pass `--flat-fee`, `--hybrid-fee` or `--gift-cost` for scenarios the owner requests. Report the script's arithmetic and measured/estimated labels, not invented market rates. Record discount stacking, refund handling, fee approval and gifting.
7. Read `references/rail-prerequisites.md` and choose section 6's Shopify rail after checking the actual store and vendor eligibility. Record verification date and role, payout schedule, minimum payout, statement approval and payment role. No vendor or payment gateway is presumed available to every category or market.
8. Fill section 5 with the code and HTTPS link templates, landing pages, attribution precedence, rail click window, holdback, self-referrals, store promotion codes and performance thresholds. The supported default attribution is code first, tracked link second, otherwise unattributed. A manual UTM link alone is not order-level link attribution. Validate the actual landing page and later perform an authorized test order.
9. Fill section 8 with disclosure wording and placement appropriate to each allowed platform and market. Write one indented platform line per roster platform; video may carry `spoken: <phrase>` in the placement. Current source verification and the owner's ruling are required before operational use. Record correction timing and who checks publication.
10. Fill section 9's content suitability, audience rule, evidence, redlines, voice, creative freedom and competitors. There is no universal adult-audience rule. An ordinary product may record `none; <reason>`; a restricted category records its actual minimum age and evidence. Missing audience decisions remain open.
11. Fill section 10 roles and sending accounts. Fill section 11 agreement jurisdiction, counsel review, reuse and exclusivity, response times, minimum time live, takedown and termination windows. Record changes in section 12. The owner may combine roles; preserve the approval boundaries that the user chose.
12. Run the readiness check again. Report settled, open and invalid fields with the role that can resolve each. Start discovery only with the relevant fields settled; offers, codes, briefs and payment wait for their own dependencies. Never invent values to get a green result.

## Machine-readable format

Preserve numbered headings, template label text and CSV headers. Put values **after** the complete field label, with the source mark last: `[owner]`, `[observed]`, `[default]` or `[open]`. Indented marked details supplement a field; they do not override a value already on its own line. A repeated field is not a valid way to revise it.

Sections 7 and 8 require `[owner]`, including an accepted proposal. Do not write `as above`, `as written` or bare `default` as a value. A settled decision is the actual sentence or number.

```markdown
- Brand name: Cedar Lane [owner]
- Canvas Tote: "Cotton canvas construction" [owner]
  - youtube: "#ad" at the start of the description; spoken: this video is sponsored by Cedar Lane; on screen at the beginning [owner]
```

These are separate shape examples: the product claim goes under section 7 Approved, and the YouTube line belongs under the disclosure field in section 8. Cedar Lane and its products are fictional. If no claim is cleared, put `- No claim is cleared yet; every product statement is ask [owner]` **above** the Approved subheading and leave Approved empty.

Platform cells are `yes`, `no`, `unknown` or `with conditions: <conditions>`. End each row with its source mark. Use roster platform values in disclosure lines; split the combined podcasts/newsletters row into `podcast` and `newsletter` lines. Discounts say `percent` or `fixed`; payout minimums say `minimum <amount>` or `no minimum`. Code and link tokens are documented in `../affiliate-onboarding/references/code-and-link-schemes.md`.

## Validation and handoff

The scripts use Python 3 standard library only. Run this skill's `scripts/fixtures/run_fixtures.sh` through the root `python3 tests/run_tests.py` entrypoint with the full package installed. Report initialization changes, readiness results and unresolved owner decisions. Suggest a small first campaign after setup, with explicit approvals for any live message, code creation, purchase or payment.
