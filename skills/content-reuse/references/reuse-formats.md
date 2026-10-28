# Reuse formats: what each channel needs, and the cuts allowed

Dated 2026-10-20, for the content-reuse skill. Two tables and a short vocabulary. Rows marked "[pack default]" are this pack's choices, which the owner may change; rows marked "[general practice, verify]" are production habits, not platform rules, and are checked against the channel's current settings before anything is cut. Policy lines are in `reuse-rules-extract.md`, cited by section.

## 1. What each channel needs

| channel code | what the asset becomes | orientation and length | caption | credit line | disclosure beside it |
|---|---|---|---|---|---|
| `product-page` | a clip or still in a creator section of its own on the product page, or in a shoppable-video widget or carousel the store already runs; never in the reviews, the star rating or product questions and answers, never under a verified-purchase badge (extract 1) | keep the source orientation and let the theme's media slot crop; a short continuous cut plays better than the whole piece [general practice, verify] | the creator's own words or none; any brand line is the owner's copy | creator handle and platform, from the roster (`primary_handle`, `primary_platform`); the terms sheet requires the handle | the connection wording from programme section 8, visible without a click or hover (extract 1) |
| `email` | a still frame or a short silent loop that links to the full piece on the product page or the creator's post | a still crops to the template's image slot; many email clients do not play video [general practice, verify] | the creator's words in quotation marks, whole sentences only | handle and platform under the image | section 8 wording in the same block as the image, not in the footer |
| `brand-social` | a repost or reshare of the approved piece on one of the brand's own accounts, as programme section 3 lists them | the platform's native orientation for the format; keep the on-screen and spoken disclosure in the cut [general practice, verify] | the brand's caption is the owner's; the creator's caption may be quoted, never reworded | tag or name the creator by handle | section 8 wording at the start of the caption; a platform label for the brand's own repost is "not in the references; verify" (extract 6); a shopping tag only where the brand's shop on that platform is approved for this category (extract 5 and 6) |
| `retail-deck` | a still or a quote on a slide shown to a retail or wholesale buyer | landscape slide; one asset per slide [general practice] | the creator's exact words | handle and platform on the slide | the connection line on the slide, plus "creator content shown with permission; not licensed for the retailer's own use" [pack default] |
| `paid:<platform>` or `paid-with-conditions:<platform>` | the licensed asset run as the brand's own ad from the brand's own ad account | per the ad platform's current specification: "not in the references; verify" (extract 6) | ad copy is the owner's, health-focused and not about pleasure where the platform requires it (extract 3) | creator named by handle | section 8 wording inside the ad itself, not only on the landing page; 18-and-over targeting set by the brand (extract 4) |

Every channel: the end date of the placement is no later than the asset's `rights_until`, including product pages and widgets, which stay up until a person removes them. A product tag or hotspot on a video names the exact product and formula shown or spoken about in the asset, never a different formula (extract 2). A shoppable-video or gallery app is a third party that receives the creator's file: the owner approves the vendor before an asset is uploaded to it [pack default].

## 2. Cut types

| cut | what it is | must stay whole | new `content-approval` record needed |
|---|---|---|---|
| `full` | the approved piece as approved | everything | no |
| `trim` | one shorter continuous section of the piece | the spoken and on-screen disclosure, every qualifier said or shown near a product statement, the creator's voice | no, if all of that stays; yes, if a product statement is cut part-way |
| `crop` | the same frames in a new frame shape or size | on-screen disclosure and any on-screen text, whole | no, if on-screen text stays whole |
| `still` | one frame | the on-screen disclosure if that frame carries it; otherwise the disclosure line beside the still | no, but the pack's terms sheet lists cropping and trimming as the brand's edits, not stills: use only where the signed agreement allows, or ask through `partnership-agreement` |
| `quote` | the creator's exact words, whole sentences, in quotation marks | the qualifier in the same or the next sentence; the attribution | yes, unless every product statement in it is an approved claim word for word (`approved_claims_present`); the terms sheet does not list quotes among the brand's edits, so the signed agreement must allow them |
| anything else | new text or captions over the video, a new voice-over, re-ordering, music over speech, joining two creators, a translation, an AI-altered frame | not applicable | yes, always, and the agreement must allow it |

The pack's terms sheet (`partnership-agreement`, section 6) lets the brand crop, trim, add its own caption and add the platform's partnership label, and never change a product statement or remove the creator's disclosure. A signed agreement that says otherwise wins; the plan names which one it relied on.

## 3. Words used in the plan

- placement: one asset on one channel in one spot, with a start and an end date.
- live or story assets: a live stream or a story is reused only from a recording or file the creator supplied under the agreement; a brand-hosted live with a creator is new content, briefed through `creator-brief` and approved through `content-approval`, not reuse.
- take-down: removing a placement by its end date, recorded by the person in the plan's `removed_on` column.
