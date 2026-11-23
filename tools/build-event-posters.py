#!/usr/bin/env python3
"""Generate a poster for every event that has no photograph of its own.

The organiser does not photograph every activity. Rather than show a generic
kind tile, this draws a card for the event itself: its title, when it runs and
where, in the colour and with the icon of its kind. The result is committed
under src/images/posters and served as the event's cover.

    python3 tools/build-event-posters.py            # write the posters
    python3 tools/build-event-posters.py --check    # fail if any is out of date

Only the standard library is used, so it runs anywhere Python does. The rules
for the kind (colour, icon, label) mirror EVENT_TYPE_RULES in src/index.html.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "src" / "events.json"
KINDS = ROOT / "src" / "images" / "kinds"
OUT = ROOT / "src" / "images" / "posters"

# Colour and label per kind, matching EVENT_TYPES in src/index.html.
KIND_STYLE = {
    "exhibition": ("#a8683a", "Triển lãm"),
    "workshop": ("#2f7660", "Workshop"),
    "talk": ("#37768f", "Toạ đàm"),
    "tour": ("#6c7d33", "Tour"),
    "fair": ("#b2543c", "Hội chợ"),
    "film": ("#55607f", "Chiếu phim"),
    "performance": ("#9c4266", "Biểu diễn"),
    "class": ("#3c7f8a", "Lớp học"),
    "game": ("#5b6b93", "Trò chơi"),
    "reading": ("#7d6a4a", "Đọc sách"),
    "food": ("#a8642f", "Ẩm thực"),
    "award": ("#8d6b1f", "Trao giải"),
    "festival": ("#245c4b", "Lễ hội Thiết kế Sáng tạo"),
}

KIND_RULES = [
    ("exhibition", r"triển lãm|trưng bày|sắp đặt|mở xưởng|pavilion|tác phẩm|khu trưng bày"),
    ("class", r"yoga"),
    ("workshop", r"workshop|thực hành|hướng dẫn|lớp học|làm nghề|craft toolkit"),
    ("game", r"gameplay|trò chơi|board game"),
    ("reading", r"reading party|đọc sách|book show"),
    ("talk", r"t[ọo][ạa]\s*đàm|trao đổi|hội thảo|thảo luận|talk"),
    ("tour", r"tour|đi bộ|bộ hành|tham quan|dạo phố"),
    ("fair", r"hội chợ|chợ phiên"),
    ("film", r"chiếu phim|điện ảnh"),
    ("performance", r"biểu diễn|trình diễn|nghệ thuật|sân khấu|hòa nhạc|hoà nhạc|múa|xiếc|ca nhạc|đêm nhạc|tuồng|chèo|diễn xướng"),
    ("food", r"ẩm thực|bia thủ công|đồ uống"),
    ("award", r"trao giải"),
]
KIND_BY_TAG = {
    "triển lãm": "exhibition", "trưng bày": "exhibition", "sắp đặt": "exhibition",
    "pavilion": "exhibition", "workshop": "workshop", "toạ đàm": "talk",
    "tọa đàm": "talk", "tour": "tour", "hội chợ": "fair", "chiếu phim": "film",
    "trình diễn": "performance", "ẩm thực": "food",
}
KIND_OVERRIDES = {"e11": "tour", "e22": "fair", "e100": "performance",
                  "e113": "exhibition", "e140": "tour"}

WIDTH, HEIGHT = 1200, 750


def kind_of(event):
    if event["id"] in KIND_OVERRIDES:
        return KIND_OVERRIDES[event["id"]]
    for key, pattern in KIND_RULES:
        if re.search(pattern, event.get("title") or "", re.I):
            return key
    for tag in event.get("tags") or []:
        key = KIND_BY_TAG.get(str(tag).strip().lower())
        if key:
            return key
    return "festival"


def icon_of(kind):
    """The line icon from the kind poster, so both share one drawing."""
    path = KINDS / f"{kind}.svg"
    if not path.exists():
        path = KINDS / "festival.svg"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<g transform=\"translate\(120 198\)[^>]*>(.*?)</g>", text, re.S)
    return match.group(1).strip() if match else ""


def darken(color, factor=0.52):
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{max(0, int(c * factor)):02x}" for c in rgb)


def escape(text):
    """XML-safe for both element text and attribute values (titles carry quotes)."""
    return ((text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def wrap(text, limit=30, lines=3):
    """Greedy wrap by characters, because SVG cannot measure text here."""
    words, out, current = (text or "").split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
            continue
        out.append(current)
        current = word
        if len(out) == lines:
            break
    if current and len(out) < lines:
        out.append(current)
    if len(out) == lines and len(" ".join(words)) > len(" ".join(out)):
        out[-1] = out[-1][: limit - 1].rstrip() + "…"
    return out


def date_label(event):
    start, end = event.get("date") or "", event.get("dateEnd") or ""
    if not start:
        return ""
    day, month, year = start[8:10], start[5:7], start[:4]
    if end and end != start:
        if end[:7] == start[:7]:
            return f"{day}–{end[8:10]}.{month}.{year}"
        return f"{day}.{month}–{end[8:10]}.{end[5:7]}.{year}"
    return f"{day}.{month}.{year}"


def poster(event, place_name):
    """Bottom-anchored layout: the meta line never collides with a long title."""
    kind = kind_of(event)
    color, label = KIND_STYLE[kind]
    title_lines = wrap(event.get("title") or "") or [""]
    meta = " · ".join(part for part in (date_label(event), place_name or "") if part)

    footer = HEIGHT - 46
    meta_y = footer - 58
    rule_y = meta_y - 40
    last_title_y = rule_y - 34
    first_title_y = last_title_y - (len(title_lines) - 1) * 68
    chip_y = first_title_y - 96

    title_svg = "\n".join(
        f'    <text x="96" y="{first_title_y + index * 68}" font-family="Helvetica Neue, Arial, sans-serif" '
        f'font-size="58" font-weight="700" fill="#ffffff">{escape(line)}</text>'
        for index, line in enumerate(title_lines)
    )
    chip_width = 26 + len(label) * 12
    # A large ghost number keeps a wall of posters from looking identical, and it is
    # the same number the card shows next to the title.
    number = event.get("number") or ""
    diagonal = (1, 1) if sum(bytearray(event["id"].encode())) % 2 else (0, 0)
    x2, y2 = diagonal
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{escape(event.get('title'))}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="{x2}" y2="{y2}">
      <stop offset="0" stop-color="{color}"/>
      <stop offset="1" stop-color="{darken(color)}"/>
    </linearGradient>
    <pattern id="dots" width="36" height="36" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="2" fill="#ffffff" opacity="0.10"/>
    </pattern>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#dots)"/>
  <g fill="none" stroke="#ffffff" stroke-opacity="0.14">
    <circle cx="1040" cy="140" r="170" stroke-width="2"/>
    <circle cx="1040" cy="140" r="240" stroke-width="2"/>
    <circle cx="1040" cy="140" r="310" stroke-width="2"/>
  </g>
  <text x="{WIDTH - 72}" y="300" text-anchor="end" font-family="Helvetica Neue, Arial, sans-serif"
        font-size="300" font-weight="700" fill="#ffffff" opacity="0.10">{escape(str(number))}</text>
  <g transform="translate(96 {chip_y})">
    <rect x="0" y="-34" width="{chip_width}" height="34" rx="17" fill="#ffffff" opacity="0.16"/>
    <text x="13" y="-10" font-family="Helvetica Neue, Arial, sans-serif" font-size="18" font-weight="700"
          fill="#ffffff" opacity="0.95">{escape(label)}</text>
  </g>
{title_svg}
  <rect x="96" y="{rule_y}" width="72" height="5" rx="2.5" fill="#ffffff" opacity="0.62"/>
  <text x="96" y="{meta_y}" font-family="Helvetica Neue, Arial, sans-serif" font-size="26"
        fill="#ffffff" opacity="0.92">{escape(meta)}</text>
  <text x="96" y="{footer}" font-family="Helvetica Neue, Arial, sans-serif" font-size="17"
        letter-spacing="2" fill="#ffffff" opacity="0.6">LỄ HỘI THIẾT KẾ SÁNG TẠO HÀ NỘI 2026</text>
  <text x="{WIDTH - 96}" y="{footer}" text-anchor="end" font-family="Helvetica Neue, Arial, sans-serif"
        font-size="17" letter-spacing="2" fill="#ffffff" opacity="0.6">BẢN ĐỒ TỔNG HỢP</text>
</svg>
"""


def main():
    check = "--check" in sys.argv
    data = json.loads(EVENTS.read_text(encoding="utf-8"))
    places = {place["id"]: place.get("name") or "" for place in data.get("places", [])}
    OUT.mkdir(parents=True, exist_ok=True)

    wanted, stale, changed = {}, [], []
    for event in data["events"]:
        image = event.get("image") or ""
        if image.startswith("images/posters/"):
            wanted[event["id"]] = poster(event, places.get(event.get("placeId"), ""))
        elif image.startswith("images/kinds/"):
            stale.append(event["id"])

    for event_id, svg in wanted.items():
        path = OUT / f"{event_id}.svg"
        if not path.exists() or path.read_text(encoding="utf-8") != svg:
            changed.append(event_id)
            if not check:
                path.write_text(svg, encoding="utf-8")

    for path in OUT.glob("*.svg"):
        if path.stem not in wanted:
            changed.append(f"-{path.stem}")
            if not check:
                path.unlink()

    print(f"posters {len(wanted)} · changed {len(changed)} · events still on a kind tile {len(stale)}")
    for event_id in stale:
        title = next(e["title"] for e in data["events"] if e["id"] == event_id)
        print(f"  kind tile: {event_id} {title[:56]}")
    if check and changed:
        print("out of date: rerun without --check", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
