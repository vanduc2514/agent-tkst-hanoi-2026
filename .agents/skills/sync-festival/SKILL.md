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
3. **The site's dates are coarse, but they are the reference.** `startAt`/`endAt`
   are UTC values; a `00:00` time means "no hours published" and is ignored. Dates
   are written as given. Hours are written for single-day events; for a multi-day run
   one window cannot describe the programme, so those go to review
4. **The site leads, and the run fixes itself.** `apply` writes what the site says
   instead of asking: a single-day event takes its `startTime`/`endTime`, every event
   takes its `date`/`dateEnd`, and a title is corrected when the change is cosmetic
   (punctuation, casing, spacing). Empty organiser fields are filled the same way.
   Posts only fill what the site leaves unsaid, and never overrule a page that exists.
5. **Raise only what cannot be settled.** The review table is for real conflicts —
   the site and a post stating different values, a curated per-day schedule the site
   contradicts, a new event that needs a map pin, a listing that vanished. Everything
   else is corrected silently and appears under "Changes made".
6. **Two field classes.** `official*` belongs to the organiser and may be
   refreshed. `slots`, `lineup`, `days`, `placeId`, `clusterId`, `tags`,
   `spotlight` and `number` are curated and only change by hand — a curated
   per-day schedule is richer than one post, so an event that has one is never
   overridden.

## Workflow

> **When this runs from CI.** `.github/workflows/sync-festival.md` executes steps
> 1–3 below in frontmatter `steps`, with `APIFY_TOKEN` in that step's environment
> only. The agent that follows starts at step 4: `tmp/sync/report.md` is already on
> disk, `src/events.json` is already resolved, and `APIFY_TOKEN` is deliberately
> absent from the agent's environment. Do not re-run `fetch`, do not look for the
> token, and do not use `mise` — it is not installed on the runner. The Apify spend
> for the run has already been made.

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
| Changes made | what the last `apply` wrote on its own, with the linked page or post it came from | none, it is a record |
| Needs your review | contradictions and items only a human can settle | read the row, then edit by hand |

"Changes made" uses `| Event | id | Change | Source |`, where the source is the post
it came from, linked, or `lehoithietkesangtao.vn`. "Needs your review" uses
`| Event | id | Difference |`: the cell names the field, our value, and the remote
value with its origin spelled out and linked — `facebook post, 2026-11-20` when a
post exists, `lehoithietkesangtao.vn` otherwise — never the bare word "listing". A
post row also says when its date is one session inside our longer run rather than a
reschedule.

A difference a post already settles is not repeated under review. Everything the sync
deliberately leaves alone — curated official values, per-day schedules, venue-label
notes, posts outside the window — is a single "Nothing to do" line under the tables,
along with the ids that have no official page.

### 3. Apply

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply --no-social
python3 .agents/skills/sync-festival/scripts/sync_festival.py apply --insert-social
```

`apply` resolves the site first, in this order:

1. **Site corrections.** `date`, `dateEnd`, and `startTime`/`endTime` on single-day
   events; a `00:00` site time is treated as "no hours" and skipped. A title is
   rewritten only when the site's version folds to the same words or is 90% similar —
   a cosmetic fix, not a different event.
2. **Post fills.** A post writes `date`, `dateEnd`, `startTime` and `endTime` only for
   events that have no official page. It must name exactly one event and carry its own
   `Thời gian`/`Time` line; the newest post per event wins.
3. **Empty organiser fields**, filled from the API.

Anything the site and a post disagree about is not written: the event is reported for
review. `--no-social` skips the post fills when the fetch is stale. `--insert-social`
adds drafts that carry a date, a time, a resolvable place and an event-like title, and
that are not duplicates or outside 13–28/11.

### 4. Check

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py check
python3 .agents/skills/sync-festival/scripts/selftest.py
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
python3 -m http.server 8080 --directory src
```

`check` catches duplicate ids, unknown places/clusters, malformed times,
`dateEnd < date` and broken numbering. `selftest.py` is 46 offline tests over the
parsers, matcher, diff, schedule override and inserter; it must pass before any
edit is committed.

### 5. Report

Every run ends by pasting `tmp/sync/report.md` into the answer, unchanged and in
full, as Markdown. Not a summary of it, not a link to it — the tables themselves,
then one line on what you did with them. Skip this and the run is incomplete.

The file is generated by `render()`; do not hand-write it. Its shape is fixed:

```markdown
# Festival sync — 2026-11-13 → 2026-11-28

92 unchanged · 12 differ from the official site · 1 new on the official site · 48 without an official page

## Changes made

`apply`, 2026-11-21T13:02

| Event | id | Change | Source |
|---|---|---|---|
| … | `e122` | end 17:00 → 17:30 | [facebook post, 2026-11-20](…post url…) |

## Needs your review

Only what two sources contradict, or what `apply` cannot settle alone.

| Event | id | Difference |
|---|---|---|
| … | `e130` | end differs: ours 11:00, [lehoithietkesangtao.vn](…page…) says 12:00, [threads post, 2026-11-21](…post…) says 11:00 — the post and the site disagree |

Nothing to do: …
No official page, so unverifiable: …
```

Rules the format enforces:

1. Two sections only, `## Changes made` then `## Needs your review`, in that order.
2. Event name first, then the id in backticks, then the difference or change.
3. Name the source, never the mechanism. A post is `facebook post, 2026-11-20`,
   `instagram post, 2026-11-20` or `threads post, 2026-11-21`; the organiser's site is
   `lehoithietkesangtao.vn`. Both are links to the exact page or post. The word
   "listing" never appears.
4. A difference reads `<field> differs: ours <value>, <source> says <value>`. Titles
   are quoted. A missing event reads `not in events.json: <source> has it starting …`;
   a delisted one reads `we still list it: <source> dropped the slug and the sitemap`.
5. A review row exists only for a contradiction or an unresolvable item: the site and
   a post disagreeing, a curated per-day schedule the site contradicts, a slug that
   needs a map pin, a page that disappeared. Cite every source that speaks, the site
   first, then the post.
6. Anything the sync deliberately leaves alone, and anything `apply` is about to
   write, stays in the single "Nothing to do" line. Do not add sections, notes or
   commentary between the tables.

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
| `scripts/selftest.py` | 46 offline tests |
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
| `apply` rewrote a title into something odd | the site's title drifted past a cosmetic change | restore from git; the 90% guard is in `site_fixes` |
| the answer has prose but no tables | step 5 skipped | paste `tmp/sync/report.md` in full |
