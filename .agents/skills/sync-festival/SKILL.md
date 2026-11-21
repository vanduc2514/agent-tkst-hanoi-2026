---
name: sync-festival
description: Refresh src/events.json from the Hanoi Design Festival's official site and from the organiser's Facebook, Instagram and Threads accounts, retrieved through Apify. Use when events may have been added, moved, renamed or cancelled, before a deploy, or when a poster or social post disagrees with the local data. The organiser's posts win every date and time conflict, because they are the freshest source; map pins and curated per-day schedules are never overwritten.
argument-hint: "[fetch|diff|apply|check]"
---

# Sync the festival programme

Keeps `src/events.json` aligned with what the organiser publishes.

Two sources, two jobs:

| Source | Retrieved with | Provides |
|---|---|---|
| `lehoithietkesangtao.vn` | its public JSON API | titles, types, venues, detail prose |
| Facebook, Instagram, Threads | **Apify actors** | changes, additions and the real schedule |

The map pins, clusters and per-day schedules in the repo are curated here. A post
only overrides `date`, `dateEnd`, `startTime` and `endTime`.

## Ground rules

1. **Apify is the retrieval layer.** Social content comes from three actors over
   the Apify REST API; no browser driving, no HTML scraping, no manual paste.
2. **The site is JSON, not HTML.** `/su-kien/` is a client-side app; its data is
   `/api/public/events`. Read the API.
3. **The site's dates are coarse.** `startAt`/`endAt` are UTC listing values and
   often contradict the event's own prose. They surface in the report; they are
   never applied.
4. **Social wins a schedule conflict.** The accounts post the real hours and any
   change, and they post it later than the listing is updated. When a post names
   exactly one event and carries its own schedule, it overrides `date`,
   `dateEnd`, `startTime` and `endTime`. The report states every override before
   `apply` writes it.
5. **Two field classes.** `official*` belongs to the organiser and may be
   refreshed. `slots`, `lineup`, `days`, `placeId`, `clusterId`, `tags`,
   `spotlight` and `number` are curated and only change by hand — a curated
   per-day schedule is richer than one post, so an event that has one is never
   overridden.

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

The report has exactly two sections, both keyed by event name then id:

| Section | Rows | Action |
|---|---|---|
| Changes made | what the last `apply` wrote, with the post or listing it came from | none, it is a record |
| Needs your review | title or schedule drift, single sessions of a longer run, new slugs, dead listing pages | read the row, then edit by hand or run `apply` |

Both tables use `| Event | id | Change | Source |`. A row whose difference a post
already settles is not repeated under review. Everything the sync deliberately
leaves alone — curated official values, per-day schedules, venue-label notes, posts
outside the window — is a single "Nothing to do" line under the tables, along with
the ids that have no listing URL.

### 3. Apply

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply --no-social
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply --insert-social
```

`apply` writes the social schedule overrides first, then fills empty organiser
fields, and reports what it kept. `--no-social` skips the overrides when the
fetched posts are stale. Add `--insert-social` to insert drafts that carry a date,
a time, a resolvable place and an event-like title, and that are not duplicates or
outside 13–28/11.

An override only happens when the post names exactly one event, carries its own
`Thời gian`/`Time` line (or a sentence with a time range), and either gives a date
range or targets a single-day event. A single date inside a longer run is one
session, not a reschedule: it lands in "social needs a review" instead. The newest
post per event wins.

### 4. Check

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py check
python3 .agents/skills/sync-festival/scripts/selftest.py
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
python3 -m http.server 8080 --directory src
```

`check` catches duplicate ids, unknown places/clusters, malformed times,
`dateEnd < date` and broken numbering. `selftest.py` is 40 offline tests over the
parsers, matcher, diff, schedule override and inserter; it must pass before any
edit is committed.

## Commands

| Command | Effect |
|---|---|
| `fetch [--limit N]` | run the three Apify actors → `tmp/sync/social.json` |
| `diff` | site API + social → `tmp/sync/report.md`, `social-drafts.json` |
| `enrich [--write]` | registration links from the fetched posts → `registrationUrl` |
| `social` | rebuild drafts from `social.json` without touching the site |
| `apply [--no-social] [--insert-social]` | write social schedule overrides + safe fills |
| `check` | validate `events.json`, no network |

`apply` also writes `tmp/sync/applied.json`, the ledger the "Changes made"
section is built from.

Exit codes: `0` clean, `1` something to review or a validation problem, `2`
retrieval failed.

## Field ownership

| Field | Owner | Written by |
|---|---|---|
| `title` | organiser, curated by hand | manual |
| `officialUrl`, `officialType`, `officialVenue`, `officialVenueAddress` | organiser | `apply`, only when empty |
| `officialDetail`, `officialSummary` | organiser | manual |
| `registrationUrl` | organiser (posted on social) | `enrich` |
| `date`, `dateEnd`, `startTime`, `endTime` | organiser (posted on social), else curated | `apply` from the newest post |
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
| `scripts/enrich.py` | registration links from posts (pure) |
| `scripts/schedule.py` | schedule overrides from posts (pure) |
| `scripts/extract.py` | text normalising, HTML, dates, times (pure) |
| `scripts/match.py` | venue lookup, duplicate detection, slugs (pure) |
| `scripts/events_model.py` | load, validate, save, build events (pure) |
| `scripts/config.py` | accounts, actors, prices, festival window |
| `scripts/selftest.py` | 40 offline tests |
| `tmp/sync/applied.json` | the ledger the "Changes made" table is built from |
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
| a schedule override looks wrong | the post describes one session of a run, or a stale fetch | check the post URL in the report; rerun with `--no-social` to skip |
