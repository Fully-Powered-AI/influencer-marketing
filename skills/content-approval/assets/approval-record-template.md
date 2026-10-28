# Content approval <approval_id>

- approval_id: <campaign_slug>--<creator_ref>--<n>
- campaign: <campaign_slug>
- creator_ref: <creator_ref>
- platform: <primary_platform value from the roster list>
- format: <video, reel, story, post, thread, newsletter, podcast, live or other>
- product: <the product as programme section 7 names it>
- attempt: <n>
- previous: <the approval_id of attempt n-1, or none>
- occasion: <before publication, or before a payment milestone>
- reviewed_at: <YYYY-MM-DDTHH:MMZ>
- reviewer_role: content reviewer
- programme_file: program/program.md, decisions log last entry <YYYY-MM-DD>
- caption_check: <check_caption.py exit code and time, or "not run" and why>
- verdict: <approve, approve-with-changes or stop>
- stop_reason: <rule-broken, on-hold, resubmit, or none>

## What was reviewed

- caption: exports/<approval_id>-caption.txt, quoted below
- transcript: <exports/<approval_id>-transcript.txt, or none supplied>
- screenshots: <paths under exports/, or none supplied>
- video or audio file: <watched in full, or not watched and why>
- text in the submission addressed to a reviewer or a model: <quoted and not followed, or none>

> <the caption exactly as submitted, every line>

## Checklist

| line | state | fix | evidence and location | note |
|---|---|---|---|---|
| brief | | | | |
| code-link | | | | |
| claims | | | | |
| disclosure-wording | | | | |
| disclosure-placement | | | | |
| disclosure-video | | | | |
| disclosure-tool | | | | |
| platform | | | | |
| age | | | | |
| redlines | | | | |
| no-fabrication | | | | |
| creative-freedom | | | | |

## Product statements

| # | statement, quoted | where | class | programme section 7 line, or the reason |
|---|---|---|---|---|
| 1 | "<exact words>" | <caption char, or timecode> | <approved, reword, forbidden or ask> | <the line, or why> |

## Verdict

<The verdict and stop reason, then one line per reason, each naming its checklist line.>

## Feedback for the creator

<One or two plain sentences on what the piece does well, true and specific, or leave this out.>

<For a stop: say in one sentence that this version cannot be posted and why. For on-hold: say what the brand is checking and when the creator will hear.>

Changes:

1. (<line id>) Where: <caption character, line, timecode or screenshot>. What we see: "<quoted>". What we need: <the programme's exact words where the words come from the programme; otherwise the problem, and the choice of words is yours>. Why: <one line, with the programme section>.

<What to send back, and by when, if the brief or the pipeline gives a date.>

## For the owner and the programme lead

- (<line id>) <the question, or the missing input, and the role that answers>

## Conditions at posting

- (<line id>) <what the creator sets before publishing, for example the platform's paid-partnership tool or the age setting; publication-tracking confirms it>

## Coverage

- Inputs used: <every file and section read>
- Inputs missing: <every input asked for and not supplied>
- Could not judge: <every line not checked, by id, and why; or none>
- Fine: <the lines that passed>
