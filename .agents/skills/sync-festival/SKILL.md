---
name: sync-festival
description: Refresh src/events.json from the Hanoi Design Festival's official site and from the organiser's Facebook, Instagram and Threads accounts, retrieved through Apify. Use when events may have been added, moved, renamed or cancelled, before a deploy, or when a poster or social post disagrees with the local data. Compares the official JSON API with the local file, applies only fields the organiser owns, and never overwrites curated times or map pins.
argument-hint: "[fetch|diff|apply|check]"
---

# Sync the festival programme

Keeps `src/events.json` aligned with what the organiser publishes.

Two sources, two jobs:

| Source | Retrieved with | Provides |
|---|---|---|
| `lehoithietkesangtao.vn` | its public JSON API | titles, types, venues, detail prose, dates |
| Facebook, Instagram, Threads | **Apify actors** | changes and additions the site has not published |

The map pins, clusters, opening times and routes in the repo are curated here.
They are never overwritten automatically.

## Ground rules

1. **Apify is the retrieval layer.** Social content comes from three actors over
   the Apify REST API; no browser driving, no HTML scraping, no manual paste.
2. **The site is JSON, not HTML.** `/su-kien/` is a client-side app; its data is
   `/api/public/events`. Read the API.
3. **The site's dates are coarse.** `startAt`/`endAt` are UTC listing values and
   often contradict the event's own prose. They surface in the report; they are
   never applied.
4. **Two field classes.** `official*` belongs to the organiser and may be
   refreshed. `date`, `dateEnd`, `startTime`, `endTime`, `slots`, `lineup`,
   `placeId`, `clusterId`, `tags`, `spotlight`, `number` are curated and only
   change by hand.

## Workflow

### 1. Fetch

```sh
export APIFY_TOKEN=...            # never written to a file
python3 .agents/skills/sync-festival/scripts/sync_festival.py fetch [--limit 25]
```

Runs the three actors, waits for them, and writes `tmp/sync/social.json` with the
raw datasets and the spend. Costs about $0.04 for the default sweep; see
[references/apify.md](./references/apify.md).

### 2. Diff

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py diff
```

Writes `tmp/sync/report.md` — a 2–3 KB triage sheet — and
`tmp/sync/social-drafts.json`. Read the report; do not open the raw datasets.

| Section | Meaning | Action |
|---|---|---|
| needs a human | title or date differs | read the detail page, decide |
| safe fills | empty `official*` field | `apply` |
| kept curated | the repo already has a different value | leave it |
| new in window | slug the repo has never seen | review, add by hand |
| new outside the window | past editions and announcements | ignore |
| curated schedules | event has `slots`/`lineup` | leave it |
| no officialUrl | curated from posters, unverifiable | attach a URL when found |
| social posts | drafts with `ready` / `duplicate` / `announcement` flags | see below |

### 3. Apply

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply --insert-social
```

`apply` fills empty organiser fields and reports what it kept. Add
`--insert-social` to insert drafts that carry a date, a time, a resolvable place
and an event-like title, and that are not duplicates or outside 13–28/11.

### 4. Check

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py check
python3 .agents/skills/sync-festival/scripts/selftest.py
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
python3 -m http.server 8080 --directory src
```

`check` catches duplicate ids, unknown places/clusters, malformed times,
`dateEnd < date` and broken numbering. `selftest.py` is 26 offline tests over the
parsers, matcher, diff and inserter; it must pass before any edit is committed.

## Commands

| Command | Effect |
|---|---|
| `fetch [--limit N]` | run the three Apify actors → `tmp/sync/social.json` |
| `diff` | site API + social → `tmp/sync/report.md`, `social-drafts.json` |
| `social` | rebuild drafts from `social.json` without touching the site |
| `apply [--insert-social]` | write safe fills, optionally insert drafts |
| `check` | validate `events.json`, no network |

Exit codes: `0` clean, `1` something to review or a validation problem, `2`
retrieval failed.

## Field ownership

| Field | Owner | Written by |
|---|---|---|
| `title` | organiser, curated by hand | manual |
| `officialUrl`, `officialType`, `officialVenue`, `officialVenueAddress` | organiser | `apply`, only when empty |
| `officialDetail`, `officialSummary` | organiser | manual |
| `date`, `dateEnd`, `startTime`, `endTime` | curated | manual |
| `slots`, `lineup`, `days` | curated | manual |
| `placeId`, `clusterId` | curated map pins | manual |
| `tags`, `description`, `spotlight`, `number` | curated | `apply --insert-social` adds, then renumbers |

Schema details and how to extend it: [references/schema.md](./references/schema.md).
Wiring a new field into the page: [references/ui-checklist.md](./references/ui-checklist.md).

## Cost

Measured 2026-11-20 on the free plan ($5/month, no card):

| Run | Items | Cost |
|---|---|---|
| Instagram, 5 posts | 5 | $0.0135 |
| Facebook, 5 posts | 5 | $0.0250 |
| Threads profile | 1 item with 13 posts nested | $0.0050 |
| Default sweep, three accounts | ~11 items | **~$0.04** |

That is ~120 sweeps a month, or one a day with room for a full refresh after
each announcement. Prices and plan limits: [references/apify.md](./references/apify.md).

## Files

| Path | Purpose |
|---|---|
| `scripts/sync_festival.py` | CLI: fetch, diff, apply, check |
| `scripts/apify.py` | Apify REST client: run actor, poll, read dataset |
| `scripts/social.py` | dataset shapes → drafts (pure) |
| `scripts/extract.py` | text normalising, HTML, dates, times (pure) |
| `scripts/match.py` | venue lookup, duplicate detection, slugs (pure) |
| `scripts/events_model.py` | load, validate, save, build events (pure) |
| `scripts/config.py` | accounts, actors, prices, festival window |
| `scripts/selftest.py` | 26 offline tests |
| `references/apify.md` | actors, inputs, pricing, dataset shapes |
| `references/schema.md` | field ownership and extension procedure |
| `references/ui-checklist.md` | wiring new metadata into the page |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `APIFY_TOKEN is not set` | token not exported | `export APIFY_TOKEN=...` in the same shell |
| `ApifyError: 401` | token revoked | issue a new token in Apify Console |
| `ApifyError: ... finished FAILED` | actor input rejected | check the input against `references/apify.md` |
| `fetch` reports 0 items | actors see no new posts | widen `--limit`; check the accounts still exist |
| many `announcement` drafts | the organiser posts updates, not events | normal; only `ready` drafts are insertable |
| `needs a human` rows repeat | the site is coarser than the curated value | leave them; the report is a triage sheet, not a work list |
