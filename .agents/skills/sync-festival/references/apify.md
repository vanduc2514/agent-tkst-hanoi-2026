# Apify: the retrieval layer

Checked 2026-11-20. All social data comes from three Apify actors through the REST
API. There is no browser automation, no HTML scraping and no manual paste.

## Accounts

The handles are not guessable and they differ between networks. They come from
the festival site footer and were confirmed on each profile.

| Network | Handle | URL |
|---|---|---|
| Instagram | `lehoithietkesangtaohanoi` | https://www.instagram.com/lehoithietkesangtaohanoi/ |
| Facebook | `lehoithietkesangtaohn` | https://www.facebook.com/lehoithietkesangtaohn |
| Threads | `lehoithietkesangtaohanoi` | https://www.threads.com/@lehoithietkesangtaohanoi |

Facebook drops the `hanoi` suffix; Instagram and Threads keep it.

## Actors and inputs

`scripts/apify.py` builds these payloads. `fetch --limit N` sets the post count.

| Network | Actor | Input |
|---|---|---|
| Instagram | `apify/instagram-scraper` | `directUrls`, `resultsType: posts`, `resultsLimit`, `onlyPostsNewerThan: 60 days` |
| Facebook | `apify/facebook-posts-scraper` | `startUrls: [{url}]`, `resultsLimit`, `onlyPostsNewerThan: 2026-10-01` |
| Threads | `apify/threads-profile-api-scraper` | `usernames: [handle]` |

## Dataset shapes

The importer normalises three different shapes; know which is which when a run
looks empty.

| Network | Shape | Notes |
|---|---|---|
| Instagram | one item per post: `caption`, `timestamp`, `url`, `shortCode` | the feed is mostly collab posts: `ownerUsername` is often a partner and the festival appears in `coauthorProducers` |
| Facebook | one item per post: `text`, `time`, `url`, `pageName` | some rows are event links with empty `text`; they are dropped |
| Threads | **one item per profile** with `latestPosts[]` nested | a profile sweep is a single cheap result, not one per post |

## Cost

The free plan needs no card and includes **$5 of usage per month**; unused credit
expires each cycle and the account pauses instead of billing overage. Actor
prices are tiered by plan — the free plan pays the highest per-item rate.

| Actor | Free-plan price | $5 buys |
|---|---|---|
| `apify/instagram-scraper` | $0.0027 / result | ~1,850 |
| `apify/facebook-posts-scraper` | $0.005 / post (+$0.001 start, +$0.002 filter) | ~1,000 |
| `apify/threads-profile-api-scraper` | $0.005 / profile | ~1,000 |

Measured on the first real run: Instagram 5 posts $0.0135, Facebook 5 posts
$0.0250, Threads profile $0.0050 — **$0.0435** total, about 50 seconds wall clock
because the three actors run one after another and each takes 12–36 s.

`usageTotalUsd` sometimes reports 0 until billing settles; `apify.py` then falls
back to the list price multiplied by the item count, so the printed spend stays
truthful.

## Runtime

| Stage | Expected |
|---|---|
| Actor start | 10–40 s |
| 5–25 posts per profile | 15–40 s |
| Whole sweep | ~50 s serial, ~35 s if run concurrently |

The actors return what the platforms show, so freshness equals how often you run
`fetch`. A daily sweep plus a manual one after each announcement fits the free
credit with room to spare.

## Token

`APIFY_TOKEN` only. Never commit it, never write it to a file inside the repo, and
never echo it into a report. `apify.py` reads it from the environment and fails
with a clear message when it is missing.
