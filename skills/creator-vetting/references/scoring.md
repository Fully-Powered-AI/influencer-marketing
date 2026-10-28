# Scoring reference for creator-vetting

Dated 2026-10-20. Public consumer-brand template; examples are fictional. Every value marked "pack default" is the owner's to change: change it in the settings block in section 8 and record the change in programme section 12. `scripts/score_creators.py` reads section 8 on every run, so this file is the only place a threshold lives.

Origins used below: [programme] the programme file rules it; [schema] the pack's shared file shapes; [pack default] the build's choice, the owner to confirm; [brief] the build brief for this skill.

## Contents

1. The six lines and their anchors
2. Absent and unseen: two different things
3. Engagement rate: the formula
4. Starting norms by tier
5. Confidence
6. Verdicts
7. Labels for numbers
8. Settings (read by the script)
9. Input file shapes

## 1. The six lines and their anchors

Each line is a whole number from 0 to 5 [schema]. The anchors fix 0, 3 and 5; 1, 2 and 4 sit between them. One line of evidence per score says what was seen, where, and on what date.

### audience_fit

What it measures: whether the people who engage with this creator are the people programme section 2 describes (who the brand is for, where it ships, which languages).

What to look at: how commenters describe themselves and each other, the creator's stated audience, language and place signals in comments, and the creator's own analytics when the creator has supplied them.

| score | anchor |
|---|---|
| 0 | The visible audience is plainly someone else: interests outside section 2, a market the brand does not ship to, or an audience outside the configured eligibility rules. |
| 3 | The creator's subject and stated audience fit section 2 and a fair share of the visible commenters do too, but the signals are mixed or the main market is unclear. |
| 5 | The creator's own analytics show an audience matching section 2's interests and markets, and the public comments agree. |

Public pages do not show demographics. Without the creator's own analytics the highest score is 4.

### engagement_quality

What it measures: how strongly the audience responds, against the norm for the creator's tier, and whether the responses are conversation or noise.

What to look at: the rate and its position from the rates run (section 3 and 4), then the comments on at least three recent posts.

| score | anchor |
|---|---|
| 0 | Position `far below`, and comments are mostly emoji, single words or unrelated to the post. |
| 3 | Position `within`, and some comments are real exchanges about the post. |
| 5 | Position `above` or `far above` (with authenticity checked), comments specific to the post, and the creator replies. |

A media kit's engagement figure is the creator's claim and never sets this score.

### authenticity

What it measures: whether the followers and the engagement come from real people rather than bought or traded activity. Buying fake indicators such as bot followers is one of the practices the FTC's 2024 rule on reviews and testimonials bans (pack reference `platform-and-compliance-notes.md`, section 2), so this line protects the brand as well as the budget.

Signals to look for: follower or like counts that are suspiciously round or identical across posts; a sudden follower jump with no post that explains it (visible only with a history tool or the creator's analytics); the same generic comments, or the same accounts, on every post; comments in languages unrelated to the audience; position `far above` with low views; sponsored posts drawing a fraction of what organic posts draw.

| score | anchor |
|---|---|
| 0 | One decisive signal (for example, identical generic comments from the same accounts across posts, or the creator advertising engagement trading), or two clear signals together. |
| 3 | One ambiguous signal with a plausible innocent cause, or too little visible to rule anything out. |
| 5 | None of the signals: comments varied and specific, from accounts that look like people; engagement in line with views and with the norm. |

The sponsored-versus-organic gap counts here only when another signal points the same way. On its own it belongs to `sponsored_track_record`.

### brand_safety

What it measures: whether the creator's content and audience sit inside programme section 9 as the owner wrote it. The owner decides section 9; this line applies it and never re-decides it [programme].

What to look at: the last three months of content on the channel they would post on for the brand, and their other public channels; explicitness against section 9's content suitability policy; section 9's redlines; audience age against section 9's audience-age line; section 9's competitor categories.

| score | anchor |
|---|---|
| 0 | A section 9 redline is hit (name it in the evidence), or any sign that the creator, or a meaningful part of the audience, is under 18. |
| 1 | Content on the channel they would use for the brand goes beyond the section 9 content suitability policy. |
| 3 | Inside the policy, with one thing to settle first: content on a separate creator-owned page that section 9 allows only with conditions; age settings that section 9 requires and that are not visibly in use; a current partnership in a section 9 competitor category; or a past controversy that appears resolved. |
| 5 | Inside the policy on every channel seen; audience suitability evidenced as section 9 requires, with age evidence only if applicable; nothing near a redline in three months. |

When a question about section 9 goes to the owner, the brand_safety evidence says `owner to rule` and what the question is. The script then flags the row `review` (section 6).

### sponsored_track_record

What it measures: whether the creator's sponsored posts still reach their audience, and what partnerships they have done.

What to look at: past posts labelled as ads or paid partnerships (mark them `sponsored` in the posts file so the rates run compares them with the rest), partnerships in the configured category or adjacent categories, and whether past sponsorships were disclosed (disclosure duties: pack reference `platform-and-compliance-notes.md`, section 1).

| score | anchor |
|---|---|
| 0 | Sponsored posts draw a small fraction of organic posts, consistently; or past sponsored posts went undisclosed; or a current exclusive partnership in a section 9 competitor category. |
| 2 | Looked, and found no sponsored posts: there is no track record to read. |
| 3 | A few disclosed sponsored posts that hold roughly the organic level, none in the category. |
| 5 | Several disclosed sponsored posts, including the category or an adjacent one (as defined by the owner), holding the organic level. |

### contactability

What it measures: whether there is a public and suitable way to reach the creator about brand work.

| score | anchor |
|---|---|
| 0 | Looked, and found no public path: no email, closed messages, no form, no manager. |
| 3 | Public direct messages, or a generic form or link page, only. |
| 5 | A public business email or a manager's address stated for brand enquiries. |

Public paths only. A private or leaked address is never recorded and scores as if it were absent.

## 2. Absent and unseen: two different things

- **Looked and found none** is a finding and takes a score: no sponsored posts is a 2 on `sponsored_track_record`; no public contact path is a 0 on `contactability`.
- **Could not look** (a private account, a page that would not load, a count the platform hides) is not a finding. Leave the score cell empty and write in the evidence why it could not be seen. The script treats an empty cell as "not judged": the creator cannot be engaged on that run, and the run is partial.

## 3. Engagement rate: the formula

Computed by the script, never by hand [brief].

- Interactions on a post: likes plus comments, plus shares where the platform shows them. An empty shares cell adds nothing.
- Followers basis (every platform not listed in `views_basis_platforms`): post rate = interactions divided by the creator's followers on the longlist, times 100.
- Views basis (platforms listed in `views_basis_platforms`): post rate = interactions divided by that post's views, times 100. A post with no views given is not used.
- A post is usable when likes and comments are given, it was posted within `posts_window_days` before the as-of date, and the divisor is known and above zero.
- The creator's rate is the median of the usable posts' rates, so one viral post does not set it. Reported to two decimals.
- Sponsored comparison: when the posts file marks posts `sponsored`, the script reports the median for sponsored posts and for the rest, with their counts. It does not score them.
- Position against the norm for the creator's tier and basis: `far below` (under `far_below_fraction` times the low end), `below`, `within`, `above`, `far above` (over `far_above_multiple` times the high end).

Tier comes from the longlist's followers on the creator's platform, using the floors in section 8, which copy the roster schema's bands [schema].

## 4. Starting norms by tier

The norm bands in section 8 (`norm_followers_<tier>` and `norm_views_<tier>`) are **Estimated starting values, not measurements**. No measured benchmark is in the pack's references. They follow common practitioner rules of thumb (one library skill gives roughly one to three percent of followers as healthy on Instagram and TikTok at scale, higher for the smallest accounts) and should be replaced with the programme's own medians once about 20 creators per tier have been vetted [pack default]. The script prints them as "starting norm" so nobody reads them as a market fact.

## 5. Confidence

Computed by the script from how complete the evidence is [brief]. Three checks:

1. Followers are recent: `followers_source` is `profile` and the longlist's file date is within `followers_max_age_days` of the as-of date.
2. The sample is full: at least `min_posts_high` usable posts within the window.
3. Engagement is computed: at least one usable post.

`high` when all three pass, `medium` when two pass, `low` when one or none passes, and `low` whenever a line was not judged.

## 6. Verdicts

The script applies these in order [brief; pack default where marked]:

1. `exclude` when the roster already holds the creator with status `excluded`; only the owner reverses that, in creator-roster [pack default].
2. `exclude` when `brand_safety` is at or below `exclude_brand_safety_max`. A redline hit is scored 0, so a redline always excludes [brief].
3. `skip` when any line is not judged; the reasons say which, and the run is partial [pack default].
4. `skip` when programme section 3 says `no` to organic creator posts on the creator's platform [programme].
5. `engage` when the total reaches `engage_min_total` and `brand_safety` reaches `engage_min_brand_safety`; otherwise `negotiate` when the total reaches `negotiate_min_total` and `brand_safety` reaches `negotiate_min_brand_safety`; otherwise `skip` [pack default].
6. `skip` in place of `engage` or `negotiate` when `authenticity` is below `min_authenticity` [pack default].
7. `negotiate` in place of `engage` when confidence is `low`, when programme section 3 says `unknown` for the platform, or when a section 9 question is open for the owner (`owner to rule` in the brand_safety evidence) [pack default].

The shortlist's `brand_safety_flag`, for creator-roster to copy into the roster's column of the same name [pack default]:

| flag | when |
|---|---|
| `exclude` | the verdict is `exclude` |
| `review` | brand_safety is not judged; or the brand_safety evidence says `owner to rule`; or brand_safety is at or below `review_brand_safety_max` |
| `none` | every other row |

What each verdict means for the next skill:

| verdict | meaning |
|---|---|
| `engage` | Approach on the programme's default terms (programme section 4). |
| `negotiate` | Worth approaching, with something to settle first; the reasons say what (a lower total, thin evidence, a platform condition, a brand-safety point). |
| `skip` | Not now. A creator can be vetted again on a later date. |
| `exclude` | Do not approach. If the creator is on the roster, creator-roster records it. |

## 7. Labels for numbers

| number | label |
|---|---|
| followers, `followers_source` = `profile` | Measured: the platform's displayed count on the longlist date |
| followers, `search_result` | Estimated: second-hand and possibly stale; does not count as recent |
| followers, `media_kit` | User-provided: the creator's claim |
| followers, `estimate` | Estimated |
| engagement rate | Measured: computed from likes, comments, shares and views read directly off the public post pages on the date the posts file is named for |
| engagement rate, when the posts file name states no date | User-provided: the person's record, with no stated read date |
| any figure from a media kit (followers, engagement, audience shares) | User-provided: the creator's claim |
| figures in a creator's analytics screenshot | User-provided: the creator's own data, not verified |
| the six scores and the total | User-provided: the programme lead's confirmed judgments |
| norm bands | Estimated starting values (section 4) |

The rule behind the table is the pack's: a count read directly off a public page on a stated date is Measured; what the person or a media kit says is User-provided; anything inferred is Estimated (contract section 4; schemas sections 7 and 12). The followers rows follow the longlist schema's mapping.

## 8. Settings (read by the script)

Change a value here and nowhere else. Each line is `key = value`; the script refuses to run if a key is missing.

```settings
# evidence windows [pack default]
followers_max_age_days = 30
posts_window_days = 90
min_posts_high = 10

# which platforms use views as the divisor [pack default]
views_basis_platforms = tiktok,youtube

# tier floors in followers: nano under 10,000; micro 10,000 to 49,999; mid 50,000 to 499,999;
# macro 500,000 and up; copied from the roster schema, change only with that file [schema]
tier_floor_micro = 10000
tier_floor_mid = 50000
tier_floor_macro = 500000

# starting norms, percent, low to high; Estimated, not measured (section 4) [pack default]
norm_followers_nano = 2.0 to 6.0
norm_followers_micro = 1.5 to 4.0
norm_followers_mid = 1.0 to 3.0
norm_followers_macro = 0.5 to 2.0
norm_views_nano = 4.0 to 10.0
norm_views_micro = 3.0 to 8.0
norm_views_mid = 2.5 to 7.0
norm_views_macro = 2.0 to 6.0

# position words [pack default]
far_below_fraction = 0.5
far_above_multiple = 3

# verdicts [brief for the exclusion line; pack default for the rest]
exclude_brand_safety_max = 1
engage_min_total = 21
engage_min_brand_safety = 4
negotiate_min_total = 15
negotiate_min_brand_safety = 3
min_authenticity = 2

# brand_safety_flag: review at or below this score (section 6) [pack default]
review_brand_safety_max = 3
```

## 9. Input file shapes

The script refuses a file whose header differs from these, and says which column is missing or extra. Empty cell means unknown [schema].

`scores-YYYY-MM-DD.csv` (header in `assets/scores-template.csv`):

`handle, platform, audience_fit, engagement_quality, authenticity, brand_safety, sponsored_track_record, contactability, evidence`

- `handle` and `platform` match a longlist row (handles compared without `@` and case).
- Each score is a whole number 0 to 5, or empty when the line could not be judged (section 2).
- `evidence` holds one entry per line, each starting with the line's name and a colon, entries separated by `;`, for example `audience_fit: comments on 8 of 10 posts from men naming design stores in two US cities, read 2026-10-18;brand_safety: ...`. Every line needs an entry, scored or not. Do not use `;` inside an entry.

`posts-YYYY-MM-DD.csv` (header in `assets/posts-template.csv`), named for the day the counts were read off the post pages (the last day, if the reading took more than one). That date is what makes the counts Measured (section 7):

`handle, platform, post_url, posted_at, likes, comments, shares, views, sponsored`

- `posted_at` is an ISO date or a UTC time.
- `likes`, `comments`, `shares`, `views` are whole numbers as the post shows them, or empty when the platform hides them.
- `sponsored` is `yes` (labelled as an ad or paid partnership), `no`, or empty. The column may be left out entirely; the other eight are required.
