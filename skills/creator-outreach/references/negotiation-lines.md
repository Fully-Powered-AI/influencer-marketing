# Negotiation lines for creator outreach

Consumer-brand operating template, originally drafted 2026-10-20. The programme's rules come from `program/program.md` by section; everything else here is the build's choice. Every figure a line uses comes from `scripts/offer_calc.py` (the flag to run is in each row) or is a programme value quoted as its section states it.

## Contents

1. The ladder of offers
2. Why per sale can suit a creator
3. Situations, the line, the arithmetic and who approves
4. Rate reality

## 1. The ladder of offers

Rungs in the order they cost the brand more. Every rung keeps the creator's code, because the code is what tracks the sale.

| rung | what the creator gets | what it costs the brand, as `offer_calc.py` prints it | who can agree it |
|---|---|---|---|
| per sale, the default | the section 4 commission on every tracked order; their audience gets the section 4 discount | commission and contribution per order, at the low and high margin | the programme lead, within section 4 |
| per sale with product | the above, plus product as the section 4 gifting line allows | the product cost is not in the script's figures; the owner's gifting line limits it | the programme lead, within the gifting line |
| hybrid | a small fee per deliverable set plus the commission | the fee, and the tracked orders needed to recover it on the hybrid row (`--flat FEE`) | the approver section 4 names, before the fee is offered |
| flat | a fee, no commission | the tracked orders on the flat row (`--flat FEE`) | the approver section 4 names, before the fee is offered |
| part ways | thanks, and the door left open | nothing | the programme lead |

## 2. Why per sale can suit a creator

Say a reason only when the programme makes it true for this creator.

| reason | true when |
|---|---|
| income for as long as the code is live and orders come in | the agreement's term has no early cap (partnership-agreement sets the term) |
| their audience gets a discount it cannot get elsewhere, which gives them a reason to post that serves their followers | section 4 sets a customer discount |
| it pays on what their audience buys, which suits a small, loyal audience better than a fee priced on reach | always |
| they keep their other partners | section 11's default exclusivity is none |
| they can see what they earn: a statement per period, paid after the holdback | sections 5 and 6 set the holdback and the payout schedule |
| they say it in their own words, from a brief, not a script | section 9's creative-freedom line stands |

## 3. Situations, the line, the arithmetic and who approves

| they say or ask | the line, in shape | run first | who approves | stage |
|---|---|---|---|---|
| "what's your budget?", or a quoted rate | ask for their rate card before any number is named; the section 4 anchors are the owner's reference and are never quoted to a creator | `--tier TIER`, and `--flat THEIR_FEE --tier TIER` once a fee is known | none yet | `replied` |
| a fee, insisted on | acknowledge the work a post takes; set out the per-sale case (section 2 above); where section 4 allows a fee for this creator, say a smaller fee plus commission is possible subject to approval, and give the day an answer will come | `--flat THEIR_FEE --tier TIER`, then `--flat PROPOSED_FEE` | the section 4 approver, before any fee is put to them | `negotiating` |
| a higher commission | say the programme rate; a different rate is the owner's call; never above the highest rate the script shows at the low margin | `--commission ASKED` | the owner (sections 4 and 10) | `negotiating` |
| an advance against commission | treat it as a fee | `--flat ADVANCE` | the section 4 approver | `negotiating` |
| the brand wants longer usage or paid reuse | the section 11 default goes in the agreement; more time, or use in the brand's own ads, is priced as a fee; paid use only where section 3's paid column allows it | `--flat RIGHTS_FEE` | the section 4 approver; counsel for the clause (section 11) | `negotiating` |
| exclusivity | none by default (section 11); if the brand wants it, it is paid for, limited to the competitor categories in section 9 and a set period, because the creator gives up other income | `--flat EXCLUSIVITY_FEE` | the section 4 approver; counsel | `negotiating` |
| an agent or manager answers | the business version: every term in one message; ask for their rate card and their usual usage terms; agents expect a fee, so the per-sale case goes in numbers and the hybrid path only where section 4 allows | `--tier TIER`, `--flat FEE` as needed | as above | `negotiating` |
| a past partner | open with their own results, period by period, labelled Measured, from the statements; a draft statement's figures are given as not yet final | `--creator REF` | none for the default deal | `first_touch` |
| product first, before deciding | product only as section 4's gifting line allows; a gift is disclosed if they post about it (the pack's `references/platform-and-compliance-notes.md`, section 1) | none | the programme lead, within the gifting line | `replied` |
| a platform section 3 rules out | say the brand cannot run partnerships there and name the platforms it can | none | the owner, who rules section 3 | `negotiating` |
| what they can say about the product | the brief will carry the approved wording (section 7); they speak in their own voice; disclosure as section 8 sets it | none | none | `replied` |
| a code of their own choosing | the code follows the section 5 scheme and is made after signature by affiliate-onboarding | none | none | `replied` |

## 4. Rate reality

Published creator rates vary widely by niche, platform and region, and quoted rates start high. The section 4 anchors are ranges the owner set for reference, not prices. A fee is judged by the tracked orders it needs before it pays for itself, which the script prints, not by follower count.
