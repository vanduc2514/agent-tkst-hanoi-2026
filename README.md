# agent-tkst-hanoi-2026

An unofficial companion for **Lễ hội Thiết kế Sáng tạo Hà Nội 2026** (Hanoi Design Festival,
13–28 November 2026). It turns the organiser's published calendar into an interactive map, a
trip planner, and a Markdown document that AI agents can read and quote.

## What it does

- **154 activities at 59 venues**, grouped into five clusters: Hồ Gươm & Tràng Tiền,
  Chợ Đồng Xuân & Hàng Đậu, Đình & Di tích Phố Cổ, Công viên Thống Nhất & Lân cận, and
  Điểm Vệ tinh.
- **Explore** — search by title, artist, description, type, venue or keyword without
  typing Vietnamese diacritics ("trien lam" finds "Triển lãm"), filter by date and cluster,
  and open any pin or card for the full address, opening hours, and the organiser's own
  write-up with a link to the official page.
- **Live mode** — the map opens filtered to what is still open today, using Hanoi clock
  time, and the pill counts them as "đang và sẽ diễn ra". Picking any date in Khám phá turns
  Live off and shows every activity of that day (pill: "sự kiện trong ngày"); "Tất cả ngày"
  shows the whole programme (pill: "sự kiện"). The green Live button brings the clock back,
  and switching it off again falls back to the date already selected — today on a first
  visit — rather than the entire festival.
  While Live is on, pins for events that are playing right now get a pulsing ring (static
  under `prefers-reduced-motion`) and the Lộ trình list marks those stops with a dot,
  because both views share the same pins. The view refreshes on focus and once a minute as
  events end.
- **Plan a route** — collect events into a route, order the stops nearest-first from a chosen
  start point or the browser's location, and send the whole itinerary to Google Maps.
- **Shareable route links** — a link such as `?tab=route&route=e01,e94,e109` opens the map
  straight on the Lộ trình tab with those stops in that order; `&origin=<lat>,<lng>` adds a
  start point, and `?preset=old-town` opens a curated itinerary. The address bar follows any
  later change to the route, so it can be copied and shared.
- **Preset routes** — thirteen curated itineraries covering the Old Quarter, Hoàn Kiếm lakeside,
  Đồng Xuân Market, traditional crafts, park installations, evening art, family visits, and
  selected festival dates. Each route lists its stops and date range.
- **Agent-readable output** — `index.md` holds the entire programme as Markdown (schedule
  table, venues with coordinates, per-event details and organiser excerpts), `llms.txt`
  is a short index pointing agents at it, and `prompts.json` lists the suggested questions
  with a title and prompt body. The Explore panel renders those prompts from JSON and offers
  one-tap icon buttons for ChatGPT, Claude and Gemini; the prompt opens in the chosen web
  chat already filled in. A copy button keeps the prompt available for pasting into a
  native app. The data files are generated from the same source as the map, so they cannot
  drift apart. `index.md`, `llms.txt` and their HTML wrappers are not committed: CI
  regenerates them before the image build, so they cannot go stale in the repository. The
  agent hint in the sidebar is plain HTML with relative links for readers without
  JavaScript, and the page fills in the event total and absolute URLs at runtime.

## Run it locally

`index.html` fetches `events.json` from the same folder, so opening the file over HTTP is
enough to browse the map:

```sh
python3 -m http.server 8080     # then open http://localhost:8080
```

To build the image, produce the generated files first — the same command CI runs:

```sh
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev   # index.md, llms.txt + HTML wrappers
docker build -t tkst:local .
docker run --rm -p 8080:8080 tkst:local
```

That one command writes `index.md`, `llms.txt`, `index.md.html` and `llms.txt.html` into the
working tree, where git ignores them.

Then open http://localhost:8080.

To edit the page itself there is no build step: serve the folder over HTTP as above and
reload. Opening `index.html` straight from disk will not work, because the page fetches
`events.json` and browsers block that request on `file://`.

## Data and credits

- Schedule, descriptions and links come from the organiser's official site,
  <https://lehoithietkesangtao.vn>.
- Playing times are curated per date in `events.json` (`slots`) wherever the organiser's
  write-up splits a day into two blocks, changes the window per date, or lists separate
  sessions. `events.json` is the source of truth for those times; edit it directly. Four
  activities (e62, e102, e105, e140) publish no time text at all, so they keep the listing
  values.
- When one activity runs as a series of named sets, `lineup` holds
  `{ date, start, end, act }` entries. The page lists them under "Lịch biểu diễn" and the
  search box matches the act names.
- Basemap: [OpenFreeMap](https://openfreemap.org) with data ©
  [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- This is a community project, not an official festival site.
