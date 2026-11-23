# Promotion images

Every event has an `image` (its cover) and, when more than one picture survives,
an `images` gallery. Both live on disk under `src/images`, because the page is
served by nginx from `src` and a CDN URL expires within days.

| Folder | Holds | When |
|---|---|---|
| `src/images/events/` | photos of the event itself | whenever the organiser published one |
| `src/images/cards/` | designed cards: title, dates, hours, venue | the card names the event |
| `src/images/posters/` | a generated card per event: title, dates, venue | the event has no truthful photo |
| `src/images/kinds/` | one tile per kind | last resort, when an image fails to load |

Files are content-addressed (`<sha1 of the jpeg payload>.jpg`), so a picture used
by two events is stored once and re-running the harvest does not churn git.

## Where candidates come from

| Source | Endpoint or dataset | Notes |
|---|---|---|
| media library | `/api/public/media` | alt text names the event |
| media albums | `/api/public/media-albums?sort=time&limit=48` | album titles are thematic, mapped by hand in `ALBUM_EVENTS` |
| projects and articles | `/api/public/projects`, `/api/public/content` | cover image, title names the event |
| card decks | an Instagram post that carries one card per programme | mapped by hand in `CARD_DECKS` |
| posts | `tmp/sync/social.json` | every image on the post, including carousel children |

## The attribution rules

1. **A post attaches its images to an event only when its opening block names the
   event.** A post that names events deep in the body is a roundup.
2. **A post with more than six images is a roundup** and contributes nothing.
3. **A card belongs to the event whose name it prints first, near the top.**
   Anything else named earlier wins; a name that appears only in a credits block at
   the bottom does not count. This is what keeps a performer's card out of a
   different event.
4. **A card that prints no name of ours belongs to another programme** — a venue
   card, a sponsor's card, another festival's card.
5. **Paper-shaped only.** A card is portrait or square. A landscape photo that
   happens to contain a sign is still a photo, so it never becomes a cover.
6. **Identical pictures are kept once**, by 64-bit perceptual hash, 12 bits of
   tolerance.
7. **Series documentation is shared, not duplicated.** When three or more events
   point at the same photo (the đình walk documents eleven temples), it stays with
   `CANONICAL_SERIES_OWNERS` only.
8. **Reviewed exceptions.** `MANUAL_REJECT` holds (event, regex) pairs that the
   rules cannot separate, e.g. a news graphic about another artwork.

Nothing is inferred from an image's colours or filename: the OCR text and the post
are the only evidence.

## When an event has no photo

`images` never invents one. It points the event at
`images/posters/<id>.svg`, drawn by `tools/build-event-posters.py`, which prints
the event's own title, dates and venue in the colour of its kind. Run that script
after any title, date or venue change; `--check` reports drift and the sync
workflow runs it as part of validation. The kind tiles stay only as the browser's
fallback when a file fails to load.

## Adding a card deck

When the organiser publishes a new set of programme cards:

1. Find the post's shortcode (the `/p/<code>/` part of its URL).
2. Open the run's `tmp/sync/social.json` and read the deck's `images` array; the
   order is the carousel order.
3. Write the event ids in that order into `CARD_DECKS` in `scripts/images.py`.
4. Run `images --dry-run`; a card whose layout cannot be read will simply not be
   picked, and its event keeps a photo.

## Reading a run

`tmp/sync/images.json` records, per event, `[url, source, info]` for every picture
that was kept. `info` is the information score: below 3 the picture is a photo,
3 and above it is a card. Use it to explain why a cover changed:

```sh
jq '."e03"' tmp/sync/images.json
```

## Without OCR

`--no-ocr`, or any machine without Swift, loses rule 3 and rule 4: a card cannot
prove its subject, so no card is used. Photos attributed by their post still work,
and every event without one falls back to its kind poster. That is the intended
behaviour on Linux CI — never hand-place a card there.
