# Code and link schemes: the forms the scripts read

Dated 2026-10-20. How `scripts/mint_codes.py`, `scripts/record_onboarding.py` and `scripts/check_kit.py` read programme sections 4 and 5, with worked examples. The code shape comes from the pack's schemas (section 2): upper case letters and digits only, 4 to 20 characters. The examples use invented creators.

## Contents

1. Code scheme (programme section 5, "Code scheme" line)
2. Link scheme (programme section 5, "Link scheme" line)
3. Customer discount (programme section 4)
4. Window and limits (given by the programme lead for each batch, the end date within programme section 4's rule)
5. Plan row to request
6. Values the welcome kit carries, in the one form the check accepts

## 1. Code scheme (programme section 5, "Code scheme" line)

Written as a template in backticks after the template's text on the same line, mark last. The template's indented line under it is an instruction, not a value, and is never read as one:

`- Code scheme (...) followed by the discount number: `{HANDLE}{DISCOUNT}` [owner]`

| token | becomes |
|---|---|
| `{HANDLE}` | the roster's `primary_handle` without `@`, letters and digits only, upper case |
| `{NAME}` | the roster's `display_name`, letters and digits only, upper case |
| `{REF}` | the six characters after `c-` in `creator_ref`, upper case |
| `{DISCOUNT}` | the number in section 4's customer discount, whole numbers only |

Literal upper case letters and digits may sit between tokens. A scheme needs at least one of `{HANDLE}`, `{NAME}` or `{REF}`, or every creator would get the same code. A scheme written in words is not read.

| scheme | creator | code |
|---|---|---|
| `{HANDLE}{DISCOUNT}` | `@sample.creator.a`, 15 percent | `SAMPLECREATORA15` |
| `BB{REF}` | `c-aaaaa1` | `BBAAAAA1` |
| `{NAME}{DISCOUNT}` | Sample Creator B, 15 percent | `SAMPLECREATORB15` |
| `{HANDLE}{DISCOUNT}` | `@a.very.long.handle.indeed`, 15 percent | `AVERYLONGHANDLEINDEED15`: 23 characters, too long, so the creator is not planned until a code is set by hand |

## 2. Link scheme (programme section 5, "Link scheme" line)

An `https://` address template, in backticks, with these tokens:

| token | becomes |
|---|---|
| `{handle}` | the handle without `@`, lower case; letters, digits, dot, underscore, hyphen |
| `{ref}` | `creator_ref` |
| `{code}` | the creator's code |
| `{platform}` | the roster's `primary_platform` |
| `{campaign}` | the `campaign_slug` of the creator's pipeline row at `agreed`, or `--campaign` |

It needs at least one of `{handle}`, `{ref}` or `{code}`, or one link would serve every creator and could not show whose sale it was.

Example: `https://www.example.com/?utm_source={platform}&utm_medium=creator&utm_campaign={campaign}&utm_content={ref}` gives `https://www.example.com/?utm_source=instagram&utm_medium=creator&utm_campaign=2026-11-launch&utm_content=c-aaaaa1`.

The brand builds the link on the manual rail, and on an app that lets the brand set the address (`--link built`). On Collabs the link is the one Collabs gives.

## 3. Customer discount (programme section 4)

| written | read as |
|---|---|
| `15 percent`, `15%`, `15 pct` | percentage, 15 (the request carries 0.15) |
| `USD 5`, `5 USD`, `5 dollars` | fixed amount, 5.00 in the store currency (the request carries `discountAmount` `"5.00"`, split across the order) |

A percentage must be above 0 and at most 100.

## 4. Window and limits (given by the programme lead for each batch, the end date within programme section 4's rule)

| flag | written in the plan | in the request |
|---|---|---|
| `--starts 2026-11-01` | `2026-11-01T00:00Z` | `startsAt` `2026-11-01T00:00:00Z` |
| `--ends 2026-12-31` | `2026-12-31T23:59Z` | `endsAt` `2026-12-31T23:59:59Z` |
| `--ends none` | empty, with "no end date" in notes | no `endsAt` |
| no `--ends`, section 4 says `stay active` | empty, with "no end date: programme section 4" in notes | no `endsAt` |
| no `--ends`, section 4 says `end` | refused: the window's last day is needed | none |
| `--ends` with a date, section 4 says `stay active` | refused: it contradicts section 4 | none |
| `--once-per-customer yes` | `yes` | `appliesOncePerCustomer` true |
| `--usage-limit 500` | `500` | `usageLimit` 500 |
| `--usage-limit none` | empty, with "no total use limit" in notes | no `usageLimit` |

Times are UTC; the store's own time zone is not known without logging in (references/rails.md section 5).

## 5. Plan row to request

| plan column | request field | source |
|---|---|---|
| `code` | `code` | the scheme, or `--code` |
| `creator_ref`, `code` | `title`, as "Creator code c-aaaaa1 SAMPLECREATORA15" | the pack's choice, so the admin shows whose code it is without a person's name |
| `discount_value` (percentage) | `customerGets.value.percentage`, divided by 100 | section 4 |
| `discount_value` (fixed amount) | `customerGets.value.discountAmount`: `amount` as written, `appliesOnEachItem` false | section 4; shopify reference 4.2 |
| `applies_to` = `all` | `customerGets.items.all` true | the only scope the references document |
| none | `context.all` = `ALL` | every buyer |
| none | `combinesWith`, three true or false values | section 4's combining line, by the rules below; left out when the rules do not settle all three |

How section 4's combining line becomes `combinesWith` (`orderDiscounts`, `productDiscounts`, `shippingDiscounts`; Shopify's default for each is false):

- A line that opens with `no` or `yes` sets every class not named later.
- The line splits into clauses at `;`, `,` and `but`. A clause with `no`, `not` or `never` sets the classes it names to no; one with `yes`, `with`, `allowed` or `only` sets them to yes.
- `shipping` names the shipping class. `order`, `code`, `codes`, `automatic` or `discount` name the order and product classes; `product` names the product class.
- A clause with `only` that says yes sets every class it does not name to no.
- Any class still unset means the line is not settled, so `combinesWith` is not sent and the plan note says so.

| section 4 line | order | product | shipping |
|---|---|---|---|
| `no` | no | no | no |
| `no other code or order discount; free-shipping offers yes` | no | no | yes |
| `yes, with free shipping only` | no | no | yes |
| `order no, product no, shipping yes` | no | no | yes |
| `yes` | yes | yes | yes |
| `with other codes but not with automatic discounts` | not settled: codes and automatic discounts are not Shopify's classes | | |

## 6. Values the welcome kit carries, in the one form the check accepts

| value | form | example |
|---|---|---|
| customer discount, on the "What your audience gets" line | `<n> percent`, or `<currency> <amount>` | `15 percent`; `USD 5.00` |
| holdback, on the "commissionable" line | `<n> days` | `30 days` |
| commission (`cpa`, `hybrid`) | `<rate> percent of <basis>` | `15 percent of subtotal after discounts, before shipping and tax` |
| payout schedule and minimum | section 6's text, word for word | as the owner wrote it |
| attribution sentence | manual: section 5's attribution model (the pack's default wording when the owner accepted it as written); Collabs or an app: the rail's record decides | "An order is credited to you when it carries your code; ..." |

`scripts/record_onboarding.py` prints these values after it records a creator.
