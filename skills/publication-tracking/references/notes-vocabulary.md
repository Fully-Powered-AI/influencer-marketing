# The entries publication-tracking writes in data/publications.csv

Dated 2026-10-20; revised in the fix round of the same day (schemas.md section 6 now points here). This is the contract between this skill's script and the skills that read the same rows. The CSV's columns are fixed by the pack's `references/schemas.md` section 6; everything about a post's history goes into its `notes` cell as dated entries.

## The shape of an entry

`YYYY-MM-DD <token> [arguments] by <role>[: free text]`

- Entries are separated by `;`, oldest first. Free text never contains `;` (the script turns one into a comma).
- `<role>` is a role from programme section 10, never a person's name.
- Arguments are single words or `key=value` pairs with no spaces; a list inside a value is joined with `+`.
- An entry a person types in the workbook that does not follow this shape is kept as it is and ignored by the script.
- Nothing is removed. A later observation is a new entry; the earlier one stays.

## The entries

| entry | written by | read by |
|---|---|---|
| `added issued-code=<code> issued-link=<url> verdict=<v>` | `add`: the code and link issued for this post (from the roster at that moment) and the approval record's verdict | this script compares later re-checks with what was issued then, not with the roster's current values |
| `live-check disclosure=<yes,no,partial> forms=<a+b or none> code=<r> link=<r> age=<v> approval=<match,differs>` | `add`, and every re-run of the live check; only the lines looked at that time | this script (the latest value of each line); `performance-report` can take the first one as the post as first seen |
| `check day<N>=<live,removed,edited,not_checked>` | `record --day1`, `--day7`, `--day30` | this script |
| `fix-requested <issue> due=<date>` | `record --fix-requested` after the programme lead has sent the ask; the text says how the date was set ("due from programme section 8, N days after the request", or "due set by <role>" with section 8's window when it differs) | this script; other skills can show it |
| `fix-confirmed <issue>` | the script, when a re-check closes an open item | this script; other skills can show it |
| `waived <issue>` | `record --waived`, owner only, with the reason | this script |
| `removal-reviewed` | `record --removal-reviewed`, with the outcome in the text | this script; `performance-report` (removals) |
| `fee milestone reached` | `record --fee-milestone reached`; text "finance to pay" unless a note is given | `commission-statement` reads an entry with these words, dated in its period, as the flat fee falling due (its own script sets the rule) |
| `fee milestone part` | `record --fee-milestone part`, with which post of the set | this script; no fee falls due from it |
| `fee milestone held` | `record --fee-milestone held`, with the reason and the agreement term | this script; no fee falls due from it |
| `rights-until <new> from=<old>` | `record --rights-from-roster`, with the agreement and how the date was set (copied from the roster, or dated from posting) in the text | `content-reuse` |
| `rights-not-covered roster=<date>` | `record --rights-not-covered`, with the reason: the roster's later date does not cover this post | this script, which stops prompting until the roster's date changes |
| `approval <approval_id> verdict=<v> [from=<old>]` | `record --approval`, for a post recorded without one or re-reviewed after posting | this script |
| `note` | `record --note` | people |

## The items an entry can name

| item | open when |
|---|---|
| `disclosure` | the latest `disclosure_seen` is `no` or `partial` |
| `code` | the code in the post differs from the one issued, or someone looked and it was absent |
| `link` | the same, for the link |
| `age` | the audience setting is `not-set` |
| `content` | the live post does not match its approval |
| `approval` | no approval is on record, or the post went live under a `stop` verdict |
| `platform` | programme section 3 says organic creator posts on that platform: `no` |

An open item is closed by a re-check that finds it right, by the owner's waiver, or, for `approval`, by linking an approval. Once a check records the post `removed`, its open items are no longer listed; the removal review stands in for them.

## The columns this skill keeps

- `disclosure_seen`, `disclosure_form`, `code_in_post`, `link_in_post`: the latest observation. The post as first seen is the first `live-check` entry.
- `check_day1`, `check_day7`, `check_day30`: the result of that check, `not_checked` until it is recorded.
- `rights_until`: set when the post is recorded. Under a roster note `rights from posting: <n> months` it is this post's own posting date plus the window, and the roster's `usage_rights_until` carries the latest of those dates; otherwise it is copied from the roster's `usage_rights_until`. It is changed only by `record --rights-from-roster`.
- `approval_id`: the approval the post went live under; replaced only by a later attempt for the same campaign and creator.
