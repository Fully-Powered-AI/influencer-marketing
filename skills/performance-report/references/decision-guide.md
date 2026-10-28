# Decision guide: from the script's signals to a proposal for the owner

Written 2026-10-20 for the performance-report skill, version 0.1.0. A vocabulary of next-cycle decisions, the signals that point toward or away from each, the checks to make before proposing that a creator be dropped, the landing-page questions, and a worked example. The owner decides; this guide only shapes the proposal. Thresholds are the programme's (section 5) as the script applies them, not this file's.

## Contents

1. The decisions
2. Signals and what they point to
3. Before proposing a drop
4. What the report cannot see, and where it might show
5. Landing-page questions for the next cycle
6. Who acts on each decision
7. Worked example (the fixture campaign)

## 1. The decisions

| decision | what it means | needs |
|---|---|---|
| repeat | another round on the same terms | the owner's yes |
| repeat with a change | same creator, one thing different: format, product, platform, or the call to action | the owner's yes; a new brief |
| change the deal | for example from a hybrid fee to pay per sale, or a smaller fee | the owner's approval for any flat or hybrid term (programme section 4); new terms |
| retainer or ambassador | a standing arrangement across months instead of one campaign | the owner's approval (section 4); offer arithmetic; new terms reviewed under section 11 |
| get a read first | not enough orders to judge; one more round before deciding | the owner's yes |
| pause pending a fix | a disclosure or claims problem is open | the fix recorded, then a fresh decision |
| end | no further rounds | the owner's decision; the roster updated |

Propose one decision per creator with its reason and the strongest alternative. Never fold two creators into one row.

## 2. Signals and what they point to

| signal (from the script's table) | points toward | check before leaning on it |
|---|---|---|
| read ok, cost per order at or below the plan target, pays back at both margin ends | repeat; retainer if it held across more than one campaign | the share of new customers; whether a few large orders carry it |
| read thin, pays back at both margin ends | get a read first, or repeat on the same terms | a thin read says little about volume either way |
| does not pay back, and a flat fee paid is most of the cost | change the deal before ending it | whether the orders themselves were healthy (new customers, few refunds) |
| does not pay back, pay per sale, gift is most of the cost | repeat without further gifting, or end | under pay per sale a creator with no sales costs only the gift |
| no tracked orders after live posts | repeat with a change, or end | the checks in section 3 |
| no post and no code | follow up on onboarding, not a performance question | the pipeline's next action |
| disclosure partly seen or not seen | pause pending a fix; if it recurs, end | whether the fix was asked for and made (publication notes) |
| post removed by the platform | a platform note; repeat with a change of platform per programme section 3 | the publication notes; never assume why a platform acted |
| posted on a platform the programme table rules out | a process gap in brief or approval; fix that first | which approval the post went out under |
| reuse rights expired or unknown | nothing for the creator's ranking; a note for content-reuse | the agreement file |
| high reported reach, few orders | at most a format or landing-page question | reach is apart from the ranking and never decides alone |
| many new customers relative to orders | weigh toward repeat when the campaign's objective is acquisition | the plan's objective |

## 3. Before proposing a drop

An empty or weak result has ordinary causes that are not the creator's audience. Look at each before writing "end":

- Was the code in the post as issued (`code_in_post`), and the link (`link_in_post`)?
- Was the post live long enough (the day 1, 7 and 30 checks), or removed early?
- Was link attribution available for the month, or did only codes attribute?
- Was the product the post named in stock, and did the landing page work, during the window? The report cannot see this; ask the programme lead.
- Was the creator's post made late in the window, so most of its effect falls in the next report?
- Did the creator's code turn up under another creator's orders or under unattributed codes (a typo, an old code)?

If any of these explains the result, propose "repeat with a change" or "get a read first", and say which.

## 4. What the report cannot see, and where it might show

- Sales a post caused without the code or a recorded link (people who search for the brand later, type the address, or hear of it from a friend) are real and unmeasured here. A post-purchase "how did you hear about us" survey, if the store runs one, is the place they show; its answers are User-provided by customers.
- The rail's or an app's own dashboard may count differently from this report (other windows, other rules). The report's numbers are the programme's model applied to the store's export; where the two differ, the report says which it used.
- The sum of creator-tracked orders is checked against the store's paid orders in the window; a creator programme that claims most of the store's orders deserves a second look at how codes are being shared.

## 5. Landing-page questions for the next cycle

Only where link orders exist or a post sent people to a page:

- Did the page named in programme section 5 match what the posts said: the same product and formula, the same offer, the code shown or explained?
- Did the page carry any claim beyond programme section 7? Remove placeholders and verify the product and offer on the landing page; check the page before sending creator traffic to it.
- Was the page usable on a phone, where most creator traffic lands? The report cannot see sessions; answer from the page itself.

## 6. Who acts on each decision

| after the owner decides | who | with which skill |
|---|---|---|
| status changes (paused, ended) | programme lead | creator-roster, its update command, with the owner's decision as the dated note |
| new terms (deal change, retainer) | owner, then counsel for non-template clauses | creator-outreach for the offer arithmetic, partnership-agreement for the terms |
| another round | programme lead | campaign-plan for the next cycle, then creator-brief |
| reuse of assets with active rights | programme lead | content-reuse |
| payable amounts | finance | commission-statement |

## 7. Worked example (the fixture campaign)

The fixture in `scripts/fixtures/ws-green/` gives five ranked creators. Read as a proposal, not a ruling:

| creator | signals | a proposal | the alternative |
|---|---|---|---|
| A (pay per sale) | rank 1; thin read at 4 orders; pays back at both margin ends; one story partly disclosed | repeat on the same terms, with the disclosure point raised | retainer later, once a second campaign confirms it |
| C (gift) | rank 2; thin read; post removed by the platform; posted on a platform section 3 rules out | repeat with a change of platform, after the disclosure fix | end, if the owner wants no gift-only deals |
| B (hybrid with a fee) | rank 3; the fee is most of the cost; does not pay back | change the deal to pay per sale | end |
| E (agreed, no code) | no post, no code | follow up on onboarding | end the agreement |
| D (pay per sale) | live post, no orders | repeat with a change, after the section 3 checks | end |
