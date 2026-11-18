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
  time. The green Live button on the map toggles it; switching the date in Khám phá to
  another day or "Tất cả ngày" turns it off and shows the whole programme, and picking
  today turns it back on. The list refreshes on focus and once a minute as events end.
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
  drift apart.

## Run it locally

```sh
node tools/build-agent-files.mjs --base https://example.com   # regenerate index.md + llms.txt
docker build -t tkst:local .
docker run --rm -p 8080:8080 tkst:local
```

Then open http://localhost:8080.

To edit the page itself, open `index.html` directly in a browser: without the inlined data
block it falls back to reading `events.json` from the same folder, so no build is needed.

## Data and credits

- Schedule, descriptions and links come from the organiser's official site,
  <https://lehoithietkesangtao.vn>.
- Basemap: [OpenFreeMap](https://openfreemap.org) with data ©
  [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- This is a community project, not an official festival site.
