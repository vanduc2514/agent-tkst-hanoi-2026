# `events.json` schema

`src/events.json` is the single source of truth for the app. `src/index.html`
reads it directly; `tools/build-agent-files.mjs` renders it into `index.md` and
`llms.txt`.

## Top level

```jsonc
{
  "festival": { "start": "2026-11-13", "end": "2026-11-28", "name": "…" },
  "clusters": { "g1": { "name": "…", "color": "#E11D48" } },
  "places":   [ /* 59 pins */ ],
  "events":   [ /* 154 activities */ ],
  "presets":  [ /* 13 curated routes */ ]
}
```

## `places[]`

| Field | Type | Notes |
|---|---|---|
| `id` | `p01` | stable; referenced by `events[].placeId` |
| `name` | string | shown on the card and searched |
| `lat`, `lng` | number | WGS84 |
| `clusterId` | `g1`…`g5` | pin colour and default filter |
| `kind` | string | "Đình", "Chợ truyền thống", … |
| `address` | string | human address |
| `mapsQuery` | string | Google Maps deep link |

Add a place before adding an event at a new venue; only a human knows where the
pin goes.

## `events[]`

| Field | Type | Owner | Written by |
|---|---|---|---|
| `id`, `number` | `eNNN`, int | repo | `apply --insert-social` |
| `date`, `dateEnd` | `YYYY-MM-DD` | organiser (posted on social), else repo | `apply` from the newest post, else manual |
| `days` | `string[]` | repo | manual |
| `startTime`, `endTime` | `HH:MM`, UTC+7 | organiser (posted on social), else repo | `apply` from the newest post, else manual |
| `slots` | `[{date,start,end}]` | repo | manual |
| `lineup` | `[{date,start,end,act}]` | repo | manual |
| `title` | string | organiser | manual |
| `image` | string | repo | `images`; the cover, always the first entry of `images` |
| `images` | `string[]` | repo | `images`; up to 10 promotion images, cover first: images that print information (a designed card, a poster with hours and venue, read by OCR) in `images/cards/`, then photos in `images/events/`; absent when the event has none and `image` points at `images/kinds/<kind>.svg` |
| `placeId` | `pNN` | repo | manual |
| `clusterId` | `gN` | repo | manual |
| `spotlight` | bool | repo | manual |
| `tags` | `string[]` | repo | `apply --insert-social` |
| `description` | string | repo | manual |
| `officialUrl`, `officialType`, `officialSummary`, `officialDetail`, `officialVenue`, `officialVenueAddress` | string | organiser | `apply`, fills only when empty |
| `registrationUrl` | string | organiser (posted on social) | `enrich`, fills only when empty |

`endTime` may be earlier than `startTime` on a single day for the events whose
listing publishes no hours (`e102`, `e140`); `check` reports them as notes.

The organiser's posts are the freshest schedule, so `apply` lets them override
`date`, `dateEnd`, `startTime` and `endTime`. An event that carries `slots`,
`lineup` or `days` is skipped: a curated per-day schedule is richer than one post.

Images are described in [images.md](./images.md): where they come from, the
attribution rules, and how to add a card deck. `check` also fails when an `image`
or `images` path is not a file under `src/`, so a remote URL cannot slip in.

## Extending the schema

Add a field only when the source provides it and the page has somewhere to put
it. The `lineup` field is the precedent, and it touched four places:

1. `src/events.json` — the data.
2. `src/index.html` — `eventSearchText()` so search finds it, the detail panel so
   it renders, and `eventTimeLabel()` if it changes opening hours.
3. `tools/build-agent-files.mjs` — the per-event Markdown block, plus `TYPE_VI`
   if it introduces a new activity type.
4. `README.md` — the feature list and the counts.

If the field is organiser-owned, add it to `config.ORGANISER_FIELDS` and, when it
may be auto-filled, to `config.FILL_WHEN_EMPTY`. If it is curated, leave it out of
both so `apply` cannot touch it.

Naming: camelCase, singular nouns, `HH:MM` for times, `YYYY-MM-DD` for dates, and
repeating data as arrays of objects with `date`/`start`/`end` keys.

## Validating

```sh
python3 .agents/skills/sync-festival/scripts/sync_festival.py check
```

Checks duplicate ids, `dateEnd < date`, malformed dates/times, unknown
`placeId`/`clusterId`, duplicate `officialUrl`, broken numbering, malformed
`slots`/`lineup`.
