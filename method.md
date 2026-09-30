# Method

Everything here was run on 29 September 2026 (UTC), read-only. Nothing was starred, followed, forked, commented on or posted. Timestamps for each account are in the `fetched_utc` column of [data/profiles.csv](data/profiles.csv).

## Selection rule

The unit is a GitHub user account. 62 accounts were checked, from three lists:

| List | How it was built | Checked |
|---|---|---|
| `top-followed` | `GET /search/users?q=followers:>10000 type:user&sort=followers&order=desc`, 3 pages of 100 (300 of 359 matches), duplicates removed. Ranks 1 to 44 of that list. | 44 |
| `design-peer` | `in:bio` searches for `designer`, `"design engineer"` and `"creative developer"`, 299 unique profiles, top 100 by followers. Ranks 1 to 9. | 9 |
| `seo-peer` | `in:bio` searches for SEO, AEO and marketing terms, top 100 by followers. Ranks 1 to 9. | 9 |

One account, seo-peer-07, is in both peer lists (design rank 24, SEO rank 7). It is counted once, under `seo-peer`.

Two notes on the search. First, `sort=followers` is silently ignored on a bare `type:user` query, so the numeric `followers:>10000` qualifier is needed for a real leaderboard. Second, the peer-set searches are not re-run here. The 62 resulting logins are frozen in [data/selection.csv](data/selection.csv) with their list and rank, and that file is the input to the script.

Accounts were checked in list order, in stages, until 30 had a profile README. The number of accounts checked (62) therefore depends on where the 30th README fell. The top-followed list was checked through rank 44, where the 30th README was found, and no account beyond that was checked.

## API calls

For each login (`code_profiles.py`):

| Call | Used for |
|---|---|
| `GET /users/{login}` | `followers` |
| `GET /repos/{login}/{login}/readme` with `Accept: application/vnd.github.raw` | the profile README. A 404 means no README. |
| `GET /repos/{login}/{login}` | only after a README 404, to tell "no profile repo" from "repo without README" (`profile_repo_exists`) |
| `POST /graphql`: `user(login){ pinnedItems(first:6){totalCount} repositories(first:1, ownerAffiliations:OWNER, isFork:false, orderBy:{field:STARGAZERS, direction:DESC}){nodes{name stargazerCount}} }` | `pinned_count`, and `known_for` (the account's most-starred owned non-fork repo) with `known_for_stars` |

`known_for` is a rule, not a biography. For someone whose famous repo lives in an organisation, it names their best personal repo instead.

Auth is `GITHUB_TOKEN`, or a logged-in `gh` CLI. The token is used in memory and never printed or stored. The GraphQL call needs one.

No README text is stored. The CSV keeps `readme_bytes` (UTF-8 bytes of the raw file) and `readme_sha256`, so a reader can fetch the same file and compare.

## Coding rules

Applied by `code_readme()` in `code_profiles.py`. Each is a fixed rule on the text.

| Column | Rule |
|---|---|
| `lines` | `len(text.splitlines())` |
| `has_stats_widget` | An image source (Markdown `![](url)`, `<img src>`, `<source src/srcset>`) matches `github-readme-stats`, `streak-stats`, `wakatime.com`, `github-profile-summary-cards`, `activity-graph`, `metrics.lecoq.io`, `github-profile-trophy` or `github-stats`. A text link to a widget's docs does not count. |
| `has_typing_svg` | An image source matches `readme-typing-svg` or `typing-svg`. |
| `badge_images` | Count of image sources matching `img.shields.io`, `shields.io/badge`, `badgen.net`, `skillicons.dev`, `forthebadge.com`, `cdn.simpleicons.org` or `devicon`. |
| `has_badges_wall` | `badge_images` is 5 or more. The threshold is my choice. |
| `has_shields` | Any image source contains `shields.io`. |
| `links_count` | Distinct link targets, from Markdown `[text](url)` (images removed first, so a linked badge counts as its link), `<a href>` and `<https://...>` autolinks. Anchors (`#...`) and `mailto:` are excluded. |
| `first_line_type` | The first non-blank line after removing HTML comments. Starts with `#`: `heading`. Starts with `![`: `image`. Starts with `<`: `html`. Starts with `[`: `link`. Anything else: `text`. Nothing: `empty`. |
| `has_greeting` | In the first 60 characters of the text with markup removed: `hi`, `hello`, `hey`, `hola`, `ola`, `welcome`, `salut`, `bonjour`, `hallo`, or a waving-hand emoji. |
| `has_headers` | A Markdown heading line (`#` to `######`) or an HTML `<h1>` to `<h6>`. |
| `pinned_count` | `pinnedItems.totalCount`, which GitHub caps at 6. Includes pinned gists. |

`summarize.py` computes every figure in the README from the CSV alone: counts, medians, quartiles and the Spearman correlation (average ranks for ties).

One statement in the README is not from the CSV. The breakdown of the 7 badge walls (4 tech-stack icons, 2 live counters, 1 contact links) comes from reading their image URLs by hand.

## Reproduce

```
python code_profiles.py     # rewrites data/profiles.csv
python summarize.py         # prints the numbers used in README.md
```

Standard library only, Python 3.10 or later. Follower counts and pin counts drift daily, so expect small differences. READMEs change rarely. Compare `readme_sha256`.

## Checks run

| Check | Result |
|---|---|
| `gh api repos/anuraghazra/github-readme-stats` | 79,820 stars, 38,093 forks, 295 open issues, last push 2026-08-31, read 2026-09-29. A third-party post had quoted "65,000+". That figure was not used. |
| `gh api repos/abhisheknaiidu/awesome-github-profile-readme` (the largest profile README template gallery) | 31,207 stars, read 2026-09-29. Read as 31,202 earlier the same day. Not used in the guide's numbers. |
| Re-fetch of the 30 READMEs against an earlier same-day fetch | All 30 are content-identical. The earlier pass's stored "bytes" equal the character count of its stored text, and its text re-encodes to the UTF-8 byte count found now for every file. The earlier figures were characters, not bytes. |
| Re-coding of features | Stats widgets 3 of 30 (as before), typing headers 0 of 30 (as before). The earlier pass reported 11 with shields.io badges, 13 with a greeting and 14 with headers. This pass has 9, 9 and 20 under the fixed rules above. Those three differences come from the rules, not from changes in the READMEs. |
| Accounts with no profile README | 32 of 62 (as before). The earlier pass said none of the 32 had a `{login}/{login}` repo. This pass finds 31 with no repo, and one (lucidrains) with the repo but no README file. |
| Pinned counts | 37 of 62 with six pins (earlier pass: 35). karpathy and diego3g each show 6 now against 5 before. |

## Licences

Text and data: CC BY 4.0. Scripts (`code_profiles.py`, `summarize.py`): MIT.


## Pseudonyms

The 18 accounts from the two peer sets (found by searching bios, not by follower rank) appear as `design-peer-NN` and `seo-peer-NN` in the data. They did not ask to be in a study, so they are not named. The top-followed accounts keep their logins. Re-running the two bio searches in the selection rule above reproduces the peer sets.
