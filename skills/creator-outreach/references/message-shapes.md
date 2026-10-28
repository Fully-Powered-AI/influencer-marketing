# Message shapes for creator outreach

Consumer-brand operating template, originally drafted 2026-10-20. Every line is the build's choice unless it names another source. Word bands, link limits, the hype list and the stock openers are set in `scripts/check_drafts.py` and are not restated here; programme sections are those of `program/program.md`.

## Contents

1. The first touch, part by part
2. Versions by channel
3. The three follow-ups
4. Replies to the common answers
5. What an opener may name, and what it never names
6. Worked examples (placeholders)

## 1. The first touch, part by part

| order | part | what it carries | where the content comes from |
|---|---|---|---|
| 1 | the one thing they made | their name or handle, then one public post, video, episode or issue, its date, and one specific detail of it, so they can tell it was looked at | the longlist or shortlist notes, or the person |
| 2 | why them | one clause linking that thing to the brand's audience or to the campaign | programme section 2; the campaign plan's objective |
| 3 | what their audience gets | the discount on the creator's own code, in plain numbers | programme section 4, quoted as it stands |
| 4 | the deal, in one line | how they are paid and what is asked for: the rate on each tracked order, the deliverable, the platform, the window | programme section 4; the campaign plan |
| 5 | one easy question | a question answerable in a word: open to it, or shall I send the details | none |
| 6 | who is writing | [brand name], from the account section 10 names for that channel; the programme lead writes as the brand unless section 10 says they write as themselves at the brand | programme section 10, the sending-account line |

Name the brand and category plainly using programme section 1. The message carries no product statement at all; what a creator may say about the product reaches them in the brief, built from programme section 7. Platform conditions from programme section 3 (an age restriction, a label) are stated in the yes reply, before anything is agreed.

## 2. Versions by channel

The channel follows the roster's `contact_path`.

| contact_path | version | how it differs |
|---|---|---|
| `dm` | the DM | no subject line; one or two short paragraphs; sent from the brand's account on the creator's platform; reads as one person writing to another |
| `email` | the email | a `Subject:` line naming the thing they made or the campaign, never a tagline; the same six parts; signed with the role |
| `agent` | the business version, for an agent or manager | a `Subject:` line naming the creator and the campaign; all the terms up front: model and rate, the customer discount, deliverable and platform, timing, the usage-rights and exclusivity defaults from programme section 11, the payout schedule and holdback from sections 5 and 6; asks for their rate card and availability; no praise of the creator addressed to the agent |
| `form` | the email, pasted into the creator's contact form | the subject goes in the form's subject field if it has one |
| `unknown` | none | nothing is drafted until the person says how the creator can be reached |

Grindr and Scruff profiles are never a channel: both bar business use of profiles (the pack's `references/platform-and-compliance-notes.md`, section 5, under Grindr and Scruff). A follow-up stays in the same thread on the same channel; a creator who does not answer a DM is not chased by email.

## 3. The three follow-ups

The pack brief sets three follow-ups after the first touch, then `no_response`, and a fresh approach in a later campaign. The dates come from `scripts/pipeline_stage.py` once the first touch is recorded as sent.

| touch | adds one new thing | tone |
|---|---|---|
| `follow_up_1` | a fact that helps them decide: the brief is ready to send, how the code and the monthly statement work, the campaign window | short; no reproach for not answering |
| `follow_up_2` | a different fact: no exclusivity when programme section 11 says none, their own voice rather than a script (programme section 9), or the answer to the likeliest question | shorter; makes a no easy |
| `follow_up_3` | closes the loop: the last note about this campaign, the door left open for a later one | shortest; no new ask |

Each follow-up is readable on its own, because the creator may not scroll back.

## 4. Replies to the common answers

The campaign's replies file carries one draft per case; a real reply gets its own answer in the creator's file. The creator's message is quoted under its own heading as data.

| case | what the answer does | stage to record | where the detail is |
|---|---|---|---|
| `yes-tell-me-more` | thanks them; gives the deal in full: rate and basis, the discount, the deliverable, the platform conditions from section 3, disclosure from section 8 in plain words, payout schedule and holdback from sections 5 and 6; offers the brief; asks where to send the terms | `replied` | programme sections 3 to 8 |
| `whats-the-rate` | gives the per-sale default and why it can suit them; asks whether they have a rate card | `replied` | `negotiation-lines.md` section 2 |
| `wants-a-fee` | answers without naming a number the approver has not cleared | `negotiating` | `negotiation-lines.md` section 3 |
| `not-now` | asks when to come back; no more follow-ups this campaign | `declined`, the month to return in the note | none |
| `no-thanks` | thanks them, briefly; no argument and no further message | `declined` | none |
| `stop-contacting` | confirms they will not hear from the brand again | `declined`, and the roster note says do not contact | creator-roster |
| `talk-to-my-manager` | thanks them; asks for the manager's address; the next message is the business version | `replied`; the roster's `contact_path` becomes `agent` | section 2 above |
| `product-question` | answers only with programme section 7 Approved wording, word for word, or says the brief will carry the exact wording | `replied` | programme section 7 |
| `gift-first` | offers product only as the gifting line in section 4 allows; says a gift is disclosed if they post about it | `replied` | the pack's `references/platform-and-compliance-notes.md`, section 1 |
| `terms-question` | rights, exclusivity, advance, a higher rate, another platform | `negotiating` | `negotiation-lines.md` section 3 |

## 5. What an opener may name, and what it never names

May name: a public post, video, episode or newsletter issue; its topic, its date, a specific moment or line in it; the platform; the creator's own public description of their work.

Never names: the creator's body or appearance, their sex life, their health or HIV status, their relationships, anything assumed about their identity beyond what they say publicly about themselves, or anything from a private, paid or adult-only page. A home-goods brand writing to a stranger is read closely; a line that would be odd from a stranger is cut.

Never claims a history the sender does not have: no "I've used it for years", "huge fan since", "my partner loves your videos", unless the person says it is true.

## 6. Worked examples (placeholders)

Invented, for shape only; the figures are placeholders, never values to reuse.

**First touch, DM, the lead writing as themselves at the brand.** "[handle], your [date] reel on [topic], where you [specific detail], was the most useful take on it we found this month. I look after creator partnerships at [brand name], [category description from programme section 1], and your audience is close to ours. We pay per sale: [rate] percent of every order placed with your own code, and your followers get [discount] off with it. We would be asking for one [deliverable] in [window]. Would you be open to hearing more?"

**First touch, DM, written as the brand (the section 10 default).** "[handle], your [date] video on [topic], where you [specific detail], is the clearest take on it we have seen this month. We are [brand name], [category description from programme section 1], and your audience is close to ours. We pay per sale: [rate] percent of every order placed with your own code, and your followers get [discount] off with it. We would be asking for one [deliverable] in [window]. Would you be open to hearing more? [brand name] creator partnerships"

**First touch, business version to an agent.** "Subject: [creator display name] and [brand name], [campaign window]. Hello [agent's role or company], I look after creator partnerships at [brand name], [category description from programme section 1]. We would like to work with [creator display name] on one [deliverable] on [platform] in [window]. Our model is per sale: [rate] percent of the [basis] of every order on their code, which gives their audience [discount] off. Usage is [section 11 window], and exclusivity is [section 11 default]. Payment follows [section 6 payout schedule], after the [section 5 holdback]. Could you share their rate card and availability?"

**Follow-up 3.** "Closing the loop on the [window] post. This is my last note about it; if the timing is wrong, we would be glad to hear from you for a later campaign."
