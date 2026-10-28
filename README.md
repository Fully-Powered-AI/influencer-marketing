# Influencer Marketing

Part of **Fully Powered Capability Templates** by [Fully Powered AI](https://fullypowered.ai/).

Build a creator programme around your products, your audience and your operating rules. This package brings together 14 skills for planning campaigns, finding creators, preparing partnerships, reviewing content, tracking posts and reconciling commissions.

Built for consumer and product brands with a storefront, especially Shopify. Use Shopify Collabs, an affiliate app or a manual code/export workflow; the scripts prepare material for your team's review.

## Install the whole package

Clone the entire repository into a stable location:

```bash
git clone https://github.com/Fully-Powered-AI/influencer-marketing.git
cd influencer-marketing
```

You can also download a release archive. Keep `skills/` and `references/` together: skills read sibling helpers, templates and shared schemas. Copying one skill folder alone is not supported. Register the skill folders with your assistant if it supports local skill registration, or ask it to read the relevant `SKILL.md` by its full path. Keep any symlink registration pointed at this intact package.

The Python tools use the standard library only. Use **Python 3.10 or newer**. The existing fixture suites also use **Bash and standard POSIX utilities** such as `diff`, `sed`, `grep` and `mktemp`; they run on macOS/Linux without network access, account credentials or third-party Python packages. Real discovery and store operations require your chosen browsing/tools and explicit authority for the relevant live actions.

## Customize your programme, step by step

### 1. Choose a separate runtime workspace and initialize it

Keep creator contact details, agreements, exports and payout files **outside this public repository**. The package is reusable tooling; each brand gets its own private runtime workspace. From the package root, for example:

```bash
mkdir -p "$HOME/creator-workspaces/my-brand"
python3 -I skills/program-setup/scripts/init_workspace.py "$HOME/creator-workspaces/my-brand"
python3 -I skills/program-setup/scripts/init_workspace.py "$HOME/creator-workspaces/my-brand" --check --require all
```

Initialization copies [program-template.md](skills/program-setup/assets/program-template.md) into `<workspace>/program/program.md`, creates the operating folders and adds header-only CSVs. It does not overwrite existing files. The readiness check will initially report a partial programme (exit 2); fill the owner's decisions before expecting it to pass.

A sample request to your assistant:

> Read `/absolute/path/to/influencer-marketing/skills/program-setup/SKILL.md` and use it to set up my consumer-brand creator programme in `/absolute/path/to/my-private-workspace`. I will supply the brand, product evidence, markets and commercial rules. Draft missing decisions as open and walk me through them. Keep all runtime data in that workspace.

Read [brand-context.md](references/brand-context.md) for configuration examples and [schemas.md](references/schemas.md) for the file contract. **Cedar Lane is a fictional home-goods brand** used in tests and examples. No example product fact, platform permission, rate or policy is a recommendation for your business.

### 2. Supply the brand, products and approved claims

In workspace `program/program.md`, fill **section 1** with the exact `Brand name`, one-line description, products, category, variants, materials/ingredients, prices, currency, average order value and margin basis. The exact name drives first-brand-mention checks in spoken disclosures; `check_caption.py --brand-name` can supply an explicit name when needed.

Keep supporting evidence in workspace `program/brand-facts.md` or `exports/` and record its pointer and date in the programme. The package intentionally contains no real brand facts.

In **section 7**, resolve the generic product-evidence review prompts, or record `none found` with the evidence checked. Add product-specific owner-cleared wording under Approved:

```markdown
- Canvas Tote: "Cotton canvas construction" [owner]
```

This example is fictional. Quote exact phrases under Forbidden and explain the reason outside the quotes. Statements on neither list need review. Optionally add `Claim review cues: "waterproof"; "recycled"; "certified" [owner]` above the Approved heading to configure heuristic checks for your category. `none [owner]` disables those cues, while exact claim checks and human review remain in place.

### 3. Set audience, market and platform rules

Fill **section 2** with your audience, countries, languages and applicable jurisdictions. In **section 3**, decide organic sponsorship and paid amplification separately for each relevant platform. Record current source evidence, conditions, required labels and any required audience controls.

Fill **section 9** with content suitability, redlines, voice, competitors and audience requirements. An ordinary category may have no audience age restriction: after the full Audience age label, write `none; <reason> [owner]`. A category with an applicable restriction records its actual minimum age and required evidence. Missing or open rules remain unresolved; the package does not impose an adult-only audience on every brand.

Use **section 8** for platform-specific disclosure wording, placement, spoken/on-screen forms, the live-check role and correction timing. [Dated policy notes](references/platform-and-compliance-notes.md) include optional restricted-category examples and sources recorded on 2026-10-20. **Verify relevant current rules at use** for the actual category, market and placement. Historical examples do not establish current permission or universal restrictions.

### 4. Decide compensation, codes, attribution and payout

Fill **section 4** with `cpa`, `flat`, `hybrid` or `gift`, commission basis/rate, customer discount, stacking, fee approvals, gifting and refund handling. Use your own commercial inputs, then compare them:

```bash
python3 -I skills/program-setup/scripts/compare_models.py "$HOME/creator-workspaces/my-brand"
```

Fill **section 5** with the code template, tracked-link template, landing pages, attribution precedence, holdback, self-referral rule and reporting thresholds. For example, a code scheme may be `{HANDLE}{DISCOUNT}`; link schemes use your actual domain and the supported tokens in [code-and-link-schemes.md](skills/affiliate-onboarding/references/code-and-link-schemes.md). The default supported attribution is matching code first, tracked link second, otherwise unattributed. A manual UTM link is not by itself order-level sales evidence.

In **section 6**, select the rail after checking the real store, account permissions and vendor eligibility. Record payout schedule, minimum amount, statement approver and payment role. Check [rail-prerequisites.md](skills/program-setup/references/rail-prerequisites.md) and verify any dated vendor observation before relying on it. Statements and payout lists are review artifacts; generating them does not transfer money.

### 5. Assign roles and approvals

Fill **section 10** with the owner, programme lead, content reviewer, finance, counsel and channel publisher roles, including who approves each operation and which account sends outreach. Fill **section 11** with the agreement jurisdiction/template, counsel review record, usage-rights and exclusivity windows, minimum time live and response/takedown terms. Log decisions in **section 12**.

Drafting outreach does not send it. Code planning is separate from live issuance. Confirm authority and prerequisites at the point an operation sends, changes a store, purchases or pays. The onboarding live-code path retains its terminal confirmation and duplicate checks.

### 6. Preserve labels; customize values

Edit **values in the workspace programme**, not the installed package's template for each new brand. Keep the numbered section headings, complete field-label text, table headers, CSV column order and identifier shapes. Several labels contain colons themselves; put the value after the **final colon of the full template label**. Keep `[owner]`, `[observed]`, `[default]` or `[open]` last. Sections 7 and 8 require `[owner]` for cleared decisions.

A blank value or `[open]` is unresolved. `as above`, `as written` and bare `default` are not usable values. Do not duplicate a field to revise it. Optional configuration such as `Claim review cues` is documented in [brand-context.md](references/brand-context.md). Changes to schemas, labels or script behavior are package development and require updating affected parsers and running tests.

Run the readiness check again. Resolve the fields needed by the next operation; do not invent values to make the check green. Machine-readable completeness does not prove that a commercial, legal or platform decision is correct.

### 7. Run a small first campaign

Start with one product, one approved platform and a small creator cohort. Use `creator-discovery` and `creator-vetting`, then register selected creators with `creator-roster`. Use `campaign-plan` to document the budget and assumptions. Prepare outreach and terms with `creator-outreach` and `partnership-agreement`; obtain the required approvals before sending.

After agreement, use `affiliate-onboarding` to plan the code/link and welcome kit. Follow [test-order-check.md](skills/affiliate-onboarding/assets/test-order-check.md) with an authorized store test before broad issuance: verify the landing page, discount combinations and actual attribution evidence. Use `creator-brief` and `content-approval` for the first deliverable, then `publication-tracking` for the live post and follow-ups. Reconcile an exported sample with `commission-statement` and `performance-report` before scaling. Reuse content only within the granted rights using `content-reuse`.

## The 14 skills

| Skill | What it does |
|---|---|
| [program-setup](skills/program-setup/SKILL.md) | Initialize the workspace and record shared owner decisions. |
| [creator-discovery](skills/creator-discovery/SKILL.md) | Build an evidenced longlist from public profiles or supplied exports. |
| [creator-vetting](skills/creator-vetting/SKILL.md) | Score audience fit, content and suitability with explicit evidence. |
| [creator-roster](skills/creator-roster/SKILL.md) | Maintain creators, pipeline and publications, including a local workbook view. |
| [campaign-plan](skills/campaign-plan/SKILL.md) | Plan a campaign, budget and stated assumptions. |
| [creator-outreach](skills/creator-outreach/SKILL.md) | Draft outreach/follow-ups and calculate offers. |
| [partnership-agreement](skills/partnership-agreement/SKILL.md) | Prepare terms and flag issues in incoming agreements. |
| [affiliate-onboarding](skills/affiliate-onboarding/SKILL.md) | Plan codes/links, record onboarding and check welcome kits. |
| [creator-brief](skills/creator-brief/SKILL.md) | Write and validate creator-specific campaign briefs. |
| [content-approval](skills/content-approval/SKILL.md) | Check claims, disclosure, code/link and approval records. |
| [publication-tracking](skills/publication-tracking/SKILL.md) | Record live posts, required evidence, follow-ups and rights dates. |
| [commission-statement](skills/commission-statement/SKILL.md) | Compute reviewable commission statements and payout lists. |
| [performance-report](skills/performance-report/SKILL.md) | Report measured orders and costs separately from estimated reach. |
| [content-reuse](skills/content-reuse/SKILL.md) | Inventory cleared content and plan reuse within rights and platform rules. |

## Run the offline tests

From the package root:

```bash
python3 -B tests/run_tests.py
```

This runs all 14 existing fixture suites plus focused public-configuration tests. Logs go to `.test-results/`, temporary work to `.test-tmp/`, and a nonzero exit means at least one check failed. Fixtures use invented entities and example.com addresses; simulated store calls never need credentials. The tests cover parsing, failure cases, identifier/CSV consistency, attribution and accounting as well as configurable brand/audience behavior. They do not certify live platform compatibility or legal compliance.

Root `.gitignore` entries for runtime folders are anchored so fixture subdirectories remain trackable. `.gitattributes` uses `* -text` to preserve fixture bytes through Git checkouts.

## License and sources

MIT — copyright 2026 Fully Powered AI. See [LICENSE](LICENSE). [SOURCES.md](SOURCES.md) credits upstream ideas and preserves their recorded repositories, commits, paths and licenses. Third-party projects retain their own licenses. This public package excludes customer records, real brand evidence and operational exports.

## Public releases

Releases flow one way from private authoring through a curated export and patch manifest into this public edition. Customer context and runtime data remain private. Changes in the public repository are reviewed separately and are not automatically merged into private authoring.
