# Campaign plan: <campaign_slug> (draft)

<!-- Template 0.1.0, 2026-10-20, from the campaign-plan skill. The title's bracket says draft or partial when the skill writes it; only the owner's word makes it approved YYYY-MM-DD. Keep every numbered heading, the generated-block markers, the KPI rows, checklist ids M1 to M10 and risk ids R1 to R9, which scripts/check_plan.py looks for. Replace every angle-bracketed placeholder. -->

- Products in this campaign (programme section 1, owner to confirm): <product names>
- Why now, in the owner's words: <one sentence>
- Live window: see section 5
- Programme file read: program/program.md, <date of its latest decisions-log entry>

## 1. Objective

In this programme's order:

1. Tracked orders and new customers through creators' codes and links, at a cost per tracked order the owner accepts.
2. Content assets with reuse rights the brand can use within their windows.
3. Reach, reported apart and never used to rank creators.

<two or three sentences: what this campaign is for and why this window. Targets are not written here: they are the base and conservative cases in section 4.>

## 2. KPIs and attribution

Attribution model: <copy programme section 5's attribution model word for word>

Ranking metric: <copy programme section 5's ranking metric for performance reports>

Each KPI follows the pack's shared definitions (schemas.md section 12), so this plan's projections and the later report measure the same thing.

| KPI | what it counts | computed from | label when reported | target |
|---|---|---|---|---|
| tracked orders | paid orders in the store export attributed by the model above (code first, link file second), outside the holdback, not self-referrals, dated on or after the creator's agreement | Shopify orders export, plus the link-attribution export if links count | Measured | section 4, base and conservative |
| new customers | tracked orders whose hashed email has its first paid order in the exports inside the window; unknown when the export has no customer identifier | the same orders export | Measured | not projected |
| cost per tracked order | programme cost (commission, flat fees, gifted units at unit cost, discount given, rail or app fees) divided by tracked orders; undefined at zero orders | statement, roster, `costs.csv`, orders export | Measured | section 4 |
| commission return on sales | the commission basis summed over tracked orders, divided by the same programme cost (budget.csv column `commission_return_on_sales`) | as above | Measured | section 4 |
| posts live with disclosure | live posts whose disclosure was seen as posted, over posts due | data/publications.csv | Measured | <posts due> |
| assets with reuse rights | approved posts whose rights run past the planned reuse date | data/publications.csv and the roster | Measured | <count> |
| reported apart: reach, views, likes | what platforms or creators' screenshots show | platform analytics or screenshots | Estimated or User-provided | none |

## 3. Creator mix

| tier | compensation | creators | platforms | from the shortlist | owner approval |
|---|---|---|---|---|---|
| <tier> | <cpa, hybrid, flat or gift> | <whole number> | <platform;platform> | <creator_refs or "n of m engage rows"> | <not needed, pending, or approved YYYY-MM-DD> |

<three to five sentences: why this mix, citing the supply table and the flags in section 4; the conditions any platform carries from programme section 3.>

## 4. Budget

<!-- plan_budget:budget:begin -->
<!-- plan_budget:budget:end -->

## 5. Timeline

<!-- plan_budget:dates:begin -->
<!-- plan_budget:dates:end -->

| milestone | date | label | role (programme section 10) | skill |
|---|---|---|---|---|
| plan approved | <date or "to be set"> | User-provided | owner | campaign-plan |
| first touches drafted and sent | <date> | User-provided | programme lead | creator-outreach |
| terms agreed, template reviewed by counsel once | <date> | User-provided | owner, counsel | partnership-agreement |
| codes and links issued and tested | <date> | User-provided | programme lead | affiliate-onboarding |
| briefs sent | <date> | User-provided | programme lead | creator-brief |
| content due for approval | <date> | User-provided | content reviewer | content-approval |
| live window: no post before it opens, because codes, links and the landing page must be live first | see the generated dates | User-provided | creators post | publication-tracking |
| day 1, 7 and 30 checks | from each post's date | per post | programme lead | publication-tracking |
| statements | see the generated dates | computed | finance, owner approves | commission-statement |
| performance report | see the generated dates | computed | programme lead | performance-report |

## 6. Measurement setup before launch

Nothing here is done by the skill. Each line is ticked by the role named, before the first post goes live.

- [ ] M1 Claims: every product in this campaign has approved wording in programme section 7; a product without any stays out. Role: owner.
- [ ] M2 Codes: each agreed creator has one code on the programme section 6 rail, formed by the section 5 scheme, and a test order applied the section 4 discount; if a store sale or another code runs in the window, a second test order shows how they combine, matching the owner's ruling in section 8. Role: programme lead, with `affiliate-onboarding`.
- [ ] M3 Links: each creator's tracked link carries the section 5 UTM values and was opened once to confirm where it lands. Role: programme lead.
- [ ] M4 Landing page and stock: the section 5 page for each product is live, shows the product, accepts the code at checkout and carries no placeholder text; stock covers the gift units and the base case's tracked orders in section 4. Role: programme lead.
- [ ] M5 Holdback and self-referral: the section 5 holdback and self-referral rule are set, and the rail's own hold matches where the rail holds commission. Role: finance.
- [ ] M6 Disclosure: the section 8 wording and placement for each platform is in every brief and every agreement, with the platform's paid-partnership tool used as well. Role: programme lead, with `creator-brief` and `partnership-agreement`.
- [ ] M7 Audience rules: each creator knows the configured restrictions and evidence, or the programme states none with a reason. Role: programme lead.
- [ ] M8 Exports: who exports orders, how often, and whether a link-attribution export will be made, so that link-only orders can count. Role: finance.
- [ ] M9 Rights: each agreed creator's `usage_rights_until` and `exclusivity_until` are in the roster. Role: programme lead, with `creator-roster`.
- [ ] M10 Baseline: orders on creator codes in the last comparable period, or "none recorded: first campaign". Role: finance.

## 7. Risks and contingencies

| id | risk | what we would see | what we do | who decides |
|---|---|---|---|---|
| R1 | a platform removes a post or an account for category reasons | a removed post at the day 1, 7 or 30 check | <for this campaign> | owner |
| R2 | a creator skips or buries the disclosure | `disclosure_seen` no or partial | <for this campaign> | programme lead, owner if repeated |
| R3 | a claim slips past the approved wording | a content-approval stop, or a live post saying more than section 7 | <for this campaign> | owner, with counsel |
| R4 | a rights window lapses before the content is reused | rights end dates in section 5 before the planned reuse | <for this campaign> | owner |
| R5 | a code leaks to coupon sites, or a creator buys through their own code | redemptions with no post behind them; orders to the creator's address | <for this campaign> | finance, owner |
| R6 | link-only orders do not show in the orders export | links in posts, few or no orders without a code | <for this campaign> | programme lead |
| R7 | creators agree and do not post, or post and sell little | content not submitted by the due date; tracked orders near the conservative case or below | <for this campaign> | programme lead |
| R8 | the rail does not work as planned | an invite that cannot be accepted, or a hold that differs from section 5 | <for this campaign> | owner, finance |
| R9 | a store sale overlaps the window: the code stacks and the order earns too little, or it does not stack and the buyer takes the sale untracked | the sale case's flags in section 4; orders in the sale with no creator code | <for this campaign> | owner |

## 8. Approvals and open items

<each decision the owner makes, one per line, as concrete options with a recommendation: the plan itself, each fee row, any platform with conditions, any claim not yet cleared, how codes and a store sale interact in the window when programme section 4's combining line is blank or the sale case is flagged, and, only when programme section 4's codes-after-window line is blank, whether the codes end with the window.>

## 9. Revisions

- <YYYY-MM-DD, role, what changed and why>

## 10. Coverage

- Inputs used: <files and programme sections>
- Inputs missing: <each, and what in the plan rests on its absence>
- Could not judge: <for example whether tracked orders are caused by the creators; reach; the store's real set-up>
