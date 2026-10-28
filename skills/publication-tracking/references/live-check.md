# The live check: what to look at on a creator's published post

Dated 2026-10-20. The facts below are carried, with their sources, from the pack's `references/platform-and-compliance-notes.md` (sections 1, 5 and 6; every source there was read 2026-10-20). When that file is updated, re-check this one against it. For this brand the programme file rules: section 3 (the platform table), section 8 (disclosure wording and placement), section 9 (the age evidence the brand requires). Where the programme and this file differ, the programme wins; where the programme is silent, the owner is asked. Nothing here is legal advice.

## Contents

1. The lines of the check
2. Platform labels
3. Audience age settings
4. Background: why the brand looks at all
5. What each recorded value means

## 1. The lines of the check

| # | line | what the person looks at | where the rule comes from | how it is recorded |
|---|---|---|---|---|
| 1 | disclosure in every form section 8 requires | the caption as posted, the spoken words, the on-screen text, the platform's own label | programme section 8 | `--disclosure-seen yes`, `partial` or `no`, with `--disclosure-form` |
| 2 | visible before any cut | where the caption is cut behind a "more" link; whether the disclosure sits in a run of hashtags or links at the end | FTC "Disclosures 101": with the endorsement, not behind "more", not mixed into hashtags (notes section 1) | only below the cut or inside the hashtag run is `partial` |
| 3 | video, reel and live: heard and seen | the opening of the video; for a live stream, whether it is repeated | FTC: in the video itself, audible and on screen; repeated in live streams (notes section 1) | the script refuses `yes` for these formats without `spoken` and `on_screen` |
| 4 | story and image: on the picture | whether the disclosure is placed over the image long enough to read | FTC: superimpose it on the image (notes section 1) | the script refuses `yes` for a story without `on_screen` |
| 5 | the words count | words section 8 says do not count | programme section 8; FTC lists "sp", "spon", "collab" and "thanks" or "ambassador" alone as failing, and calls "Gifted" alone ambiguous (notes section 1) | words that do not count are not a form; record `no`, or `partial` if another form is there |
| 6 | the platform's tool, in addition | the platform's paid-partnership label (section 2 below) | programme section 8; FTC: do not rely on the platform's tool alone (notes section 1) | add `platform_tool` to the forms when it is on |
| 7 | the code as issued | the code wherever it appears, letter for letter | programme section 5; the code issued for this post | `--code-in-post` exactly as shown, or `--no-code-in-post` |
| 8 | the link as issued | wherever the post sends people: caption, bio, sticker, description; say where | programme section 5; the link issued for this post | `--link-in-post` exactly as shown, or `--no-link-in-post`; the place goes in `--note` |
| 9 | matches the approval | product statements, claims, code and wording against the approval record | programme section 7; `campaigns/<slug>/approvals/<approval_id>.md` | `--matches-approval yes` or `no`; a new product statement is `no` |
| 10 | audience evidence meets the configured rule, or none is required | the setting, or the creator's screenshot of it | programme section 9; section 3 below | `--age-setting confirmed`, `not-set`, `not-offered`, `not-required` or `unchecked` |
| 11 | the platform is allowed | the "organic creator posts" column for this platform | programme section 3 | the script reads section 3 itself |

Discount codes and disclosure: the FTC FAQ says a personal code may show a relationship but not necessarily a financial one, and recommends erring towards disclosure (notes section 1). A code in the caption is never counted as the disclosure.

## 2. Platform labels

| platform | the label the platform offers | source, as the notes record it |
|---|---|---|
| TikTok | the commercial content disclosure toggle, which branded content must switch on | TikTok Branded Content Policy, published 2026-08-04 (notes section 5). Verify current category and market applicability before use. |
| YouTube | the paid promotion setting, which adds a label at the start of the video; the label alone does not meet the FTC standard | YouTube help article 154235 (notes section 5) |
| X | a native "Paid Partnership" label, added March 2026; paid-partnership posts need clear commercial language | press coverage and an excerpt of X's paid-partnerships policy (notes section 5) |
| Instagram and Facebook | the paid-partnership tool | marked unsourced in the notes (from training knowledge); verify against Meta's Branded Content Policies |
| Reddit | a "Brand Affiliate" tag | secondary coverage only (notes section 5); subreddit rules unsourced |
| podcasts and newsletters | none in the references | programme section 8 sets the spoken or written form |

## 3. Audience age settings

Optional tools below are historical observations, not a requirement for every product. Use them only when programme section 9 requires an audience restriction; verify availability and behavior at use.

| platform | what a creator can set | what the notes record about it |
|---|---|---|
| Instagram, per post | a minimum age and location on feed posts, Reels, videos and stories, for creators with access to the paid-partnership label | it cannot be added or changed after publishing (search-result excerpt, notes section 6), so a missing per-post setting has no after-the-fact fix: the programme lead decides |
| Instagram, account | a default minimum age for professional accounts | search-result excerpt (notes section 6) |
| Facebook Page | age restrictions in the Page's settings; needs full control of the Page | search-result excerpt (notes section 6) |
| YouTube | Studio, Audience, "Age restriction (advanced)" | viewers must be signed in and 18 or over; YouTube warns that videos meant as ads should not use it, and age-restricted videos may earn little or no ad revenue (notes section 6) |
| TikTok | Audience Controls, marking a video or LIVE as 18 and over | search-result excerpts (notes section 6) |
| X | marking media as sensitive | under-18 users and users without a birth date cannot view it (notes section 6) |
| other platforms | not in the references | verify |

The notes infer that no platform found lets the brand switch on an age restriction for a creator's organic post; the brand can require it in the agreement, and checking it fits the same review as the disclosure (notes section 6, inferred).

Stories and live replays: whether and when a platform takes them down by itself is not in the references. When one is gone at a check, it is recorded `removed`, and the removal review says whether it lapsed or was taken down, when the person knows.

## 4. Background: why the brand looks at all

- The FTC FAQ expects advertisers to train and monitor their endorsers: say which claims are allowed, instruct on disclosure, periodically search what endorsers say, and act on questionable practices. It sets no frequency (notes section 1).
- Responsibility for disclosure rests with the influencer and the brand, not the platform (FTC FAQ, notes section 1). Advertisers can be liable for what endorsers say and for undisclosed connections (16 CFR 255.1(d), notes section 1).
- A new or changed product statement goes to content-approval and the owner under programme section 7; it is not merely a wording correction.

## 5. What each recorded value means

| value | meaning |
|---|---|
| disclosure `yes` | every form section 8 requires for this platform and format was seen, before any cut, in words that count |
| disclosure `partial` | at least one adequate form was seen, but not all, or not where section 8 puts it |
| disclosure `no` | no adequate disclosure was seen; `--disclosure-form` stays empty |
| code or link `match`, `differs`, `absent` | the script's comparison with what was issued for this post; `absent` means someone looked and it was not there |
| age `confirmed` | the evidence meets the actual programme section 9 rule |
| age `not-set` | the platform offers it and it is not on |
| age `not-offered` | the platform or format has no such setting; a required restriction remains open |
| age `not-required` | section 9 explicitly requires no restriction; otherwise this is an open issue |
| age or any line `unchecked` | no one looked; shown under NOT CHECKED until someone does |
| matches approval `no` | the live post says or shows something the approval did not cover |
