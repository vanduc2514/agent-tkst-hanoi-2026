# Wiring new metadata into the page

`src/index.html` is the app: plain HTML, CSS and vanilla JS, no build step. New
event metadata is invisible until it passes these seams.

## 1. Search index

`eventSearchText()` builds one folded string per event. Anything a user might type
must appear there.

```js
return foldForSearch([
  event.title,
  ...
  event.officialType || "",
  ...(event.lineup || []).flatMap((slot) => [slot.date, slot.start, slot.end, slot.act]),
].join(" "));
```

Check a search with and without diacritics afterwards: "trien lam" must find
"Triển lãm".

## 2. Detail panel

Around the `detail-official` section, the panel renders `officialType`,
`officialDetail` and the `lineup` table. Add a row in the same shape, escaping
every value:

```js
${event.capacity ? `<p class="detail-official-row"><span>Sức chứa</span><strong>${escapeHtml(String(event.capacity))}</strong></p>` : ""}
```

`lineup` is the model for a repeating structure: sort a copy, render a
`detail-times` block.

## 3. Time display

`eventTimeLabel()` and `slotsFor()` decide the "14:00–17:00 hằng ngày" text. If a
field changes when an event is open, update both the label and the Live-mode
check so the pulsing pin stays correct.

## 4. Agent build

`tools/build-agent-files.mjs` renders `index.md`. Add the field to the per-event
block and extend `TYPE_VI` for a new activity type:

```js
const TYPE_VI = { Exhibition: "Triển lãm", ..., Fair: "Hội chợ" };
```

## 5. README

Update the feature list and the counts ("154 activities at 59 venues"). The counts
appear in the README, the sidebar hint and the meta description.

## 6. Verify

```sh
python3 .agents/skills/sync-festival/scripts/selftest.py
python3 .agents/skills/sync-festival/scripts/sync_festival.py check
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
python3 -m http.server 8080 --directory src
```

There is no test suite for the page: open it, search the new value with and
without diacritics, filter the right date, and open a card.

## Anti-patterns

- Adding a field to JSON only, then wondering why the page ignores it.
- Rendering unescaped values: every interpolation goes through `escapeHtml`.
- Storing dates as `Date` objects; the file uses strings so it stays diffable.
- Adding a type without a `TYPE_VI` entry.
- Renumbering by hand: `apply` renumbers 1..n.
