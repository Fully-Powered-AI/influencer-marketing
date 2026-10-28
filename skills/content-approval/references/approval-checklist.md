# Approval checklist: the lines, the classes, the verdict table and the settings

Dated 2026-10-20; caption windows and the spoken form revised 2026-10-21. Written for the `content-approval` skill of the consumer-brand creator pack. Both scripts read this file by its headings: `check_caption.py` reads section 5, `check_record.py` reads sections 1 and 3. A value changes here and nowhere else.

Origins used below: "programme" is the client's `program/program.md`; "notes" is the pack's `references/platform-and-compliance-notes.md` (dated 2026-10-20); "facts" is the pack's `references/brand-context.md`; "build" is a choice made when this skill was written, for the owner to keep or change.

## Contents

1. The lines, in order
2. Product statements: what counts and how each is classed
3. The verdict table
4. States and fixes
5. Settings the scripts read
6. What a change request carries
7. Worked example

## 1. The lines, in order

The `a fail is` column: `stop` means any fail on that line stops the content; `fixable` means the reviewer chooses the fix (text, resubmit, or stop when the content itself is the problem); `by statement` means section 2 decides; `feedback` means the line judges the reviewer's own feedback, which is corrected before the record is saved.

| # | id | what it checks | rule from | a fail is | at posting allowed |
|---|---|---|---|---|---|
| 1 | brief | the deliverable matches the creator's brief: product, platform, format, number of pieces, posting window, call to action | the brief at `campaigns/<slug>/briefs/<creator_ref>.md`; programme section 9 | fixable | no |
| 2 | code-link | the creator's own code and tracked link appear exactly as the roster holds them, in the place the brief names | roster columns `code` and `affiliate_link`; programme section 5 | fixable | no |
| 3 | claims | every product statement is one the owner cleared for this exact product, word for word | programme sections 1 and 7 | by statement | no |
| 4 | disclosure-wording | the disclosure uses wording that programme section 8 accepts for this platform, and nothing section 8 says does not count stands alone | programme section 8; notes section 1 | fixable | no |
| 5 | disclosure-placement | the disclosure is visible before any fold: inside the caption window of section 5 below, not only at the end, in a hashtag pile, in a bio or behind a "more" link | programme section 8; notes section 1, placement | fixable | no |
| 6 | disclosure-video | for video and audio: the disclosure is spoken (the section 8 wording, or the platform line's `spoken:` form) and shown on screen, within the spoken window of section 5 below, and repeated through a live stream | programme section 8; notes section 1, video | fixable | no |
| 7 | disclosure-tool | the platform's paid-partnership or branded-content tool is switched on, in addition to the words | programme sections 3 and 8; notes sections 1 and 5 | fixable | yes |
| 8 | platform | programme section 3 allows organic creator posts on this platform for this brand, and every condition written in that row is met | programme section 3; notes section 5 | stop | no |
| 9 | age | the content and audience evidence meet programme section 9; no age restriction is imposed when the programme explicitly requires none | programme sections 3 and 9; notes section 6 | fixable | yes |
| 10 | redlines | nothing in the words, images, sound or setting crosses programme section 9: the redlines and the content suitability policy | programme section 9 | stop | no |
| 11 | no-fabrication | no invented result, no experience the creator has not had, nothing implying an unpaid or ordinary customer relationship, nothing that contradicts the disclosure | programme section 7, last forbidden line; notes sections 1 and 2 | stop | no |
| 12 | creative-freedom | the feedback asks only for changes to failed lines and leaves the creator's voice, hook, humour, format and opinions alone | programme section 9, creative freedom | feedback | no |

Line 9 is `fixable` because a missing age setting is a posting fix; content aimed at or showing someone who appears under 18 is a fail whose fix is `stop`.

## 2. Product statements: what counts and how each is classed

Three kinds of sentence in a submission:

| kind | what it is | examples of the shape | where it is judged |
|---|---|---|---|
| product statement | says what a product is, contains, does, is safe or compatible with, how long it lasts, or how it compares; it can be true or false | "cotton canvas", "compatible with model A", "will not stain", "lasts longer than the others" | line 3, this section |
| opinion | the creator's own taste or feeling about the product | "my favourite", "I love the texture", "this is the one I reach for" | not a claim; the creator's voice; never edited for wording |
| experience statement | what the creator says happened to them | "I've used it for years", "it got me through a long weekend" | line 11; a health outcome is also a product statement in the first category below |

Every product statement gets one class:

| class | meaning | effect |
|---|---|---|
| approved | the statement matches a line under "Approved" in programme section 7 for the product the post is about, after normalising case, punctuation and spacing | none |
| reword | outside the categories below, it says the same thing as an approved line for this product in other words | line 3 fails; the fix asks for the approved wording (text in a caption, resubmit if spoken); the creator may instead ask the owner to rule, which makes it `ask` |
| forbidden | it matches a line under "Forbidden", or falls in a category below without being approved word for word for this product | line 3 fails with fix `stop` |
| ask | anything else: not approved, not forbidden | line 3 is `ask`; the owner rules; the reviewer never approves it |

Categories where rewording is never available; a statement in one of them is approved word for word for this exact product, or it is forbidden:

- unsupported performance, environmental, health or safety statements (programme section 7);
- compatibility or intended-use statements not cleared for the exact product (programme sections 1 and 7);
- effects of ingredients on the body beyond the label (programme section 7, forbidden line 3);
- comparison with a named competitor (programme section 7, forbidden line 4);
- results the creator did not have, or a customer relationship that does not exist (programme section 7, forbidden line 5).

The desensitizing creams and the supplement carry their own regulatory limits (notes section 4). A statement about either that is not approved word for word is `ask` at least, and a health outcome is `forbidden`.

## 3. The verdict table

Read from the top; the first row that matches decides. `n/a` lines and `at posting` lines never block a verdict; `at posting` lines become the record's conditions at posting. Line 12 is excluded: it must be `pass` before the record is saved.

| order | when | verdict | stop_reason |
|---|---|---|---|
| 1 | any product statement is `forbidden`, or any line fails with fix `stop` | stop | rule-broken |
| 2 | any line is `ask` or `not checked` | stop | on-hold |
| 3 | any line fails with fix `resubmit` | stop | resubmit |
| 4 | any line fails with fix `text` | approve-with-changes | none |
| 5 | none of the above | approve | none |

## 4. States and fixes

| state | meaning |
|---|---|
| pass | the reviewer saw it and it meets the line |
| fail | the reviewer saw it and it does not; a fix is named |
| ask | the reviewer cannot rule; the owner (or the role section 10 names) must |
| not checked | the reviewer could not see what the line needs, for example a video it could not watch; never a guess |
| n/a | the line does not apply to this format; the note says why |
| at posting | the line can only be seen once the post is set up (lines marked "yes" in section 1); it becomes a condition the creator meets before publishing and `publication-tracking` confirms |

| fix | meaning |
|---|---|
| text | a change to the caption, description or show notes that a person can confirm by reading the live post: moving the disclosure to the start, correcting the code, replacing a reworded line with the approved wording |
| resubmit | a change to the video, audio or images, or one that needs a fresh look: a spoken disclosure added, on-screen text, a new take; the revised version is a new attempt |
| stop | the content as made cannot run; a revised version is a new attempt |

## 5. Settings the scripts read

### Caption window

The whole first accepted disclosure must sit inside this many characters, counted from the first visible character of the caption or description.

| platform | caption window | origin |
|---|---|---|
| instagram | 125 | notes section 8, secondary source; not stated by the platform |
| tiktok | 100 | notes section 8, secondary source for organic posts; TikTok's ad guidance gives the same figure |
| youtube | 100 | notes section 8, secondary source, description and Shorts |
| x | 280 | notes section 8, secondary source; a standard post has no fold |
| onlyfans | 100 | notes section 8, inferred default: visible without a tap on every platform cited |
| reddit | 100 | notes section 8, inferred default |
| podcast | 100 | notes section 8, inferred default, applied to show notes |
| newsletter | 100 | notes section 8, inferred default, applied to the top of the issue |
| bluesky | 100 | notes section 8, inferred default |
| threads | 100 | notes section 8, inferred default |
| other | 100 | notes section 8, inferred default |

No platform states its fold; every figure above is approximate, and device, screen width, line breaks and emoji move it (notes section 8). Programme section 8's default still asks for the disclosure "at the start of the caption"; the window is the outer limit the script enforces, and the posted caption is checked on a phone after publication.

### Spoken window and formats

| setting | value | origin |
|---|---|---|
| spoken window | 150 | build: the notes (section 1) put the disclosure with the endorsement; 150 characters of transcript is about one or two spoken sentences after the first mention of the brand or the code |
| formats that need a transcript | video;reel;story;live;podcast | build, from programme section 8 (spoken in video) and the format list in the pack's `references/schemas.md` section 6 |

### Cue words

A cue is a word that often sits inside a product statement in a forbidden category. The script lists each cue it finds with its sentence; a cue is not a verdict, and the reviewer classes the sentence under section 2. English only.

| category | cue words | origin |
|---|---|---|
| safety-and-performance | prevent;prevents;protect;protects;safe;waterproof;compatible;guaranteed;certified | generic review cues; programme section 7 can replace them |
| materials-and-environment | organic;natural;recycled;biodegradable;sustainable;non toxic;hypoallergenic | generic review cues; not compliance conclusions |
| comparison | better than;best;number one;#1;vs;versus;unlike;compared to;beats;than any;than other | programme section 7 |
| results-and-relationship | proven;clinically;recommended by;approved;not sponsored;not an ad;not paid;nobody paid;my own money;i bought | programme section 7 |

The optional `Claim review cues` field in programme section 7 replaces these defaults. Use quoted literal phrases, or `none`; see shared `brand-context.md`. Missing configuration keeps these generic defaults. Exact Approved and Forbidden checks and manual review still apply.

## 6. What a change request carries

| part | what goes in it |
|---|---|
| line | the checklist id, in brackets, so the record check can match it |
| where | caption character or line, timecode, or screenshot number |
| what we see | the words or moment, quoted |
| what we need | the exact replacement only when the words come from the programme (the approved wording in section 7, the disclosure wording in section 8); otherwise the problem in plain words, and the creator chooses how to fix it |
| why | one line naming the rule and its programme section |

Nothing else goes in: no "nice to have", no new hook, no rewording of an opinion.

## 7. Worked example

A fictional Instagram reel for a cotton canvas construction. The roster code is `FIXA15`. The caption begins "Okay this is the tote I take everywhere, it works with every appliance, use FIXA15 for 15 percent off" and, after two more sentences, ends "#tote #home #ad". The transcript has neither the section 8 wording nor the line's spoken form.

| line | state | fix | why |
|---|---|---|---|
| claims | fail | stop | "works with every appliance" is a compatibility statement; section 7 approves only "compatible with model A appliances" for this product, so it is forbidden, and rewording is not available |
| disclosure-placement | fail | text | "#ad" runs from character 140 to 143, past Instagram's window of 125 |
| disclosure-video | fail | resubmit | no spoken or on-screen disclosure in the transcript or screenshots |
| code-link | pass | | the code appears as issued |

Verdict: stop, rule-broken, because row 1 of the verdict table matches before any other. The feedback names three changes (the compatibility line removed or replaced by the approved wording, "#ad" moved to the start, the disclosure said and shown in the first seconds) and leaves "the tote I take everywhere" alone, because it is an opinion. The revised reel is attempt 2.
