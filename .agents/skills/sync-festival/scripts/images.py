"""Promotion images for every event.

Two jobs, kept apart so the second can be tested offline:

* `select()` is pure: it decides which image belongs to which event and in what
  order, using the text read from each image (OCR) and the post that carried it.
* `harvest()` does the I/O: it collects candidates from the site's API and the
  fetched posts, downloads them once, runs OCR, then writes the winners.

The rules come from review failures, so they are deliberately conservative:

1. An image from a post is attached only when the post's opening line names the
   event, and the post carries at most six images. Longer carousels are roundups.
2. A designed card (portrait or square, printing hours, a date or bilingual
   captions) belongs to the event whose name it prints *first*, near the top. A
   performer listed in a credits block at the bottom does not count.
3. A card that prints no name of ours belongs to another programme.
4. Images that print the same information are the same picture: perceptual hash.
5. Photos an event shares with at most one other event are allowed (an exhibition
   and its tour); series documentation is given to the canonical tour only.

Without OCR the run still works: post attribution stays, cards are not picked,
because nothing can prove a card's subject.
"""

import hashlib
import io
import json
import re
import shutil
import subprocess
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import (
    CARD_DIR, EVENTS, IMAGE_URL_CARDS, IMAGE_URL_EVENTS, MAX_IMAGES_PER_EVENT,
    OCR_BIN, OCR_SOURCE, PHOTO_DIR, POSTER_DIR, SITE, SCAN_DIR, SRC, UA,
)

try:  # Pillow is only needed when images are actually harvested
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - reported by harvest()
    Image = None
    ImageOps = None


# ------------------------------------------------------------------ text helpers

TYPE_WORDS = (r"(workshop|trình diễn|triển lãm|trưng bày|tọa đàm|toạ đàm|trao đổi|lớp thực hành|"
              r"đêm nhạc|chiếu phim|tour|sự kiện|hội chợ|sắp đặt|trình tương tác|múa đương đại|"
              r"bộ hành|chương trình|tác phẩm|trải nghiệm|chuỗi|chiếu)")
TYPE_TOKENS = {re.sub(r"[^a-z0-9 ]", " ", word.strip().lower()) for word in TYPE_WORDS.strip("()").split("|")}
FRAGMENT_STARTS = {"thuoc", "cua", "va", "trong", "du", "an", "tai", "tu", "den", "voi",
                   "cho", "cac", "nhung", "mot", "khi", "de", "la", "co", "the", "phan"}

# Cards reviewed by eye that the rules above cannot separate from their look-alike.
# Keyed by event id, matched against folded OCR text.
MANUAL_REJECT = {
    "e03": re.compile(r"mu a am thanh|mua am thanh"),   # a graphic about the water tower
    "e99": re.compile(r"mudi thuong|muoi thuong"),      # "mười thương"'s card, credits a dancer
}

# Album titles are thematic, so they are mapped by hand instead of matched.
DINH_SERIES = ["e08", "e34", "e36", "e37", "e38", "e39", "e40", "e41", "e42", "e43", "e44"]
# The heritage tour keeps the shared documentation; a set, so "e3" is not "e34".
CANONICAL_SERIES_OWNERS = {"e34"}
ALBUM_EVENTS = {
    "pho-trang-tien-thanh-san-dien-thoi-trang-cua-sinh-vien": ["e80"],
    "tieng-chieng-muong-ngan-vang-ben-ho-hoan-kiem": ["e68"],
    "trai-nghiem-hoi-cho-nghe-nghe": ["e53"],
    "hinh-anh-so-duyet-chuong-trinh-nghe-thuat-thang-long-ke-nghe": ["e06"],
    "nhung-hinh-anh-an-tuong-khai-mac-le-hoi-thiet-ke-sang-tao-ha-noi-2026": ["e06"],
    "dao-hoi-cho-cham-hoa-dua-nao-ben-ho-hoan-kiem": ["e04"],
    "dao-hoi-cho-cham-hoa-dua-no-ben-ho-hoan-kiem": ["e04"],
    "mot-chieu-theo-dau-nghe-qua-6-ngoi-dinh-pho-co": DINH_SERIES,
}

# The organiser's designed programme cards, published as one deck per series.
CARD_DECKS = {
    "https://www.instagram.com/p/Dfrjb22mYkx/": ["e06", "e31", "e127", "e138", "e83", "e146",
                                                "e99", "e143", "e109", "e139", "e100", "e134",
                                                "e137", "e97", "e131"],
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
# Mirrors EVENT_TYPE_OVERRIDES in src/index.html.
KIND_OVERRIDES = {"e11": "tour", "e22": "fair", "e100": "performance",
                  "e113": "exhibition", "e140": "tour"}

INFO_HINT = re.compile(r"\d{1,2}[:h]\d{2}|\d{1,2}/\d{1,2}|\d{4}", re.I)


def fold(text):
    text = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").replace("y", "i")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def tokens(text):
    return {word for word in fold(text).split() if word}


def fallback_image(event):
    """A generated poster when one exists, else the tile for the event's kind."""
    poster = POSTER_DIR / f"{event['id']}.svg"
    if (SRC / "images" / "posters" / poster.name).exists():
        return f"images/posters/{poster.name}"
    return f"images/kinds/{kind_of(event)}.svg"


def kind_of(event):
    """Poster kind for an event with no usable photo (mirrors the page's rules)."""
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


def info_score(text):
    """How much information a designed card prints. Below 3 it reads as a photo."""
    text = (text or "").strip()
    if len(text) < 40:
        return 0
    score = len(text) / 40 + len(text.split()) / 8
    if INFO_HINT.search(text):
        score += 3
    if re.search(r"\(vie\)|\(eng\)|việt|english", text, re.I):
        score += 2
    return round(score, 2)


# --------------------------------------------------------------------- names index

class Names:
    """Every way an event can be written, so a card or post can name it."""

    def __init__(self, events):
        self.by_id = {event["id"]: event for event in events}
        frequency = {}
        for event in events:
            for word in set(tokens(event.get("title"))):
                frequency[word] = frequency.get(word, 0) + 1
        total = max(len(events), 1)
        self.generic = {word for word, count in frequency.items() if count > max(6, total * 0.05)}
        self.owners = {}
        for event in events:
            for name in self.variants(event.get("title") or ""):
                self.owners.setdefault(name, set()).add(event["id"])

    def variants(self, title):
        title = title.strip()
        bare = re.sub(r"^" + TYPE_WORDS + r"\s+", "", re.sub(r"^[“\"]", "", title), flags=re.I)
        bare = re.sub(r"[”\"]$", "", bare)
        out = {title, bare, re.sub(r"\s*\([^)]*\)\s*$", "", title)}
        # Malformed titles ("Tác phẩm "X" thuộc dự án") hide the name inside quotes,
        # so every pair of consecutive quotes is a candidate, not just disjoint pairs.
        quotes = [match.start() for match in re.finditer(r"[“”\"]", title)]
        for start, end in zip(quotes, quotes[1:]):
            fragment = title[start + 1:end].strip()
            words = fold(fragment).split()
            if not words or words[0] in FRAGMENT_STARTS:
                continue
            if fold(fragment) in TYPE_TOKENS or all(word in TYPE_TOKENS for word in words):
                continue
            out.add(fragment)
        keep = set()
        for name in out:
            folded = fold(name)
            words = folded.split()
            distinctive = any(word not in self.generic and len(word) > 2 for word in words)
            if len(words) >= 2 and (distinctive or len(folded) >= 12):
                keep.add(folded)
        return keep

    def positions(self, text):
        """{event_id: index of the first character of its name} in folded text."""
        folded = fold(text)
        found = {}
        for name, owners in self.owners.items():
            match = re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", folded)
            if not match:
                continue
            for event_id in owners:
                if event_id not in found or match.start() < found[event_id]:
                    found[event_id] = match.start()
        return found

    def named(self, text):
        """{event_id: [names printed]}."""
        return {event_id: [name for name, owners in self.owners.items()
                           if event_id in owners
                           and re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", fold(text))]
                for event_id in self.positions(text)}

    def decisive(self, text):
        """Events a text names, preferring those named by a name nobody else owns."""
        matched = self.named(text)
        if not matched:
            return []
        unique = [event_id for event_id, names in matched.items()
                  if any(len(self.owners[name]) == 1 for name in names)]
        return sorted(unique or matched)

    def card_belongs(self, text, event_id):
        """A card belongs to the event whose name it prints first, near the top."""
        found = self.positions(text)
        if event_id not in found:
            return False
        mine = found[event_id]
        if any(other != event_id and position < mine for other, position in found.items()):
            return False
        folded = fold(text)
        head = " ".join(fold(line) for line in [line for line in (text or "").splitlines() if line.strip()][:6])
        return mine <= len(folded) * 0.45 or mine < len(head)


# ------------------------------------------------------------------------ select

def perceptual_hash(image, size=8):
    small = image.convert("L").resize((size + 1, size), Image.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = pixels[row * (size + 1) + col]
            right = pixels[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return bits


def hamming(left, right):
    return bin(left ^ right).count("1")


def select(candidates, texts, images, names, max_per_event=MAX_IMAGES_PER_EVENT):
    """{event_id: [photo]} after attribution, cards rule and de-duplication.

    candidates: [{event_id, url, source, posted, order}]
    texts:      {url: ocr text}
    images:     {url: PIL image}
    """
    per_event = {}
    for candidate in candidates:
        url = candidate["url"]
        image = images.get(url)
        if image is None:
            continue
        text = texts.get(url, "")
        folded = fold(text)
        # Cards are paper-shaped; a landscape photo with a sign is still a photo.
        aspect = image.width / image.height
        info = info_score(text) if aspect <= 1.05 else 0
        printed = names.positions(text)
        if info >= 3:
            owners = [event_id for event_id in printed if names.card_belongs(text, event_id)]
        elif printed and len(printed) <= 3:
            owners = sorted(printed)
        elif info < 3 and not printed:
            owners = [candidate["event_id"]]
        else:
            owners = []
        for event_id in owners:
            reject = MANUAL_REJECT.get(event_id)
            if reject and reject.search(folded):
                continue
            per_event.setdefault(event_id, []).append({
                "url": url, "image": image, "info": info, "text": text,
                "source": candidate["source"], "posted": candidate["posted"],
                "order": candidate["order"],
            })

    # Series documentation is shared by many events; keep it with the canonical owner.
    share_count = {}
    for photos in per_event.values():
        for photo in photos:
            share_count[photo["url"]] = share_count.get(photo["url"], 0) + 1

    kept = {}
    for event_id, photos in per_event.items():
        photos.sort(key=lambda photo: (-photo["info"], photo["order"], photo["posted"]))
        unique, seen = [], []
        for photo in photos:
            if share_count[photo["url"]] > 2 and event_id not in CANONICAL_SERIES_OWNERS:
                continue
            digest = perceptual_hash(photo["image"])
            if any(hamming(seen_hash, digest) <= 12 for seen_hash in seen):
                continue
            seen.append(digest)
            unique.append(photo)
            if len(unique) >= max_per_event:
                break
        if unique:
            kept[event_id] = unique
    return kept


def apply(data, kept):
    """Write `image`/`images` on every event; return the ids that lost their gallery."""
    written = {}
    for event_id, photos in kept.items():
        written[event_id] = photos
    cleared = []
    for event in data["events"]:
        photos = written.get(event["id"])
        if photos:
            event["images"] = list(photos)
            event["image"] = photos[0]
        else:
            had = bool(event.pop("images", None))
            event["image"] = fallback_image(event)
            if had:
                cleared.append(event["id"])
    return cleared


def save_photos(kept, photo_dir, card_dir):
    """Write each selected image once, content-addressed; return {event_id: [path]}."""
    photo_dir.mkdir(parents=True, exist_ok=True)
    card_dir.mkdir(parents=True, exist_ok=True)
    for folder in (photo_dir, card_dir):
        for stale in folder.glob("*.jpg"):
            stale.unlink()
    written = {}
    for event_id, photos in kept.items():
        paths = []
        for photo in photos:
            buffer = io.BytesIO()
            photo["image"].save(buffer, "JPEG", quality=74, optimize=True, progressive=True)
            payload = buffer.getvalue()
            name = hashlib.sha1(payload).hexdigest()[:10] + ".jpg"
            folder = card_dir if photo["info"] >= 3 else photo_dir
            target = folder / name
            if not target.exists():
                target.write_bytes(payload)
            prefix = IMAGE_URL_CARDS if folder == card_dir else IMAGE_URL_EVENTS
            paths.append(f"{prefix}/{name}")
        written[event_id] = paths
    return written


# --------------------------------------------------------------------------- I/O

def _get_json(path):
    request = urllib.request.Request(f"{SITE}/api/public{path}",
                                     headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def post_images(post, collected):
    """Every image URL on the post that produced `post`."""
    items = collected.get(post["network"], {}).get("items", [])
    if post["network"] == "instagram":
        item = next((entry for entry in items if entry.get("url") == post["source"]), None)
        if not item:
            return []
        urls = [url for url in item.get("images") or [] if isinstance(url, str)]
        if item.get("displayUrl"):
            urls.append(item["displayUrl"])
        for child in item.get("childPosts") or []:
            if child.get("displayUrl"):
                urls.append(child["displayUrl"])
            urls += [url for url in child.get("images") or [] if isinstance(url, str)]
        return list(dict.fromkeys(urls))
    item = next((entry for entry in items
                 if post["source"] in (entry.get("url"), entry.get("facebookUrl"))), None)
    if not item:
        return []
    urls = []
    for media in item.get("media") or []:
        uri = (media.get("image") or {}).get("uri")
        if uri and "fbcdn" in uri:
            urls.append(uri)
        elif media.get("thumbnail") and "fbcdn" in media["thumbnail"]:
            urls.append(media["thumbnail"])
    return list(dict.fromkeys(urls))


def social_candidates(posts, collected, names):
    """Candidates from posts whose opening line names an event."""
    candidates = []
    for post in posts:
        # A post is evidence when its opening block names an event, or when the whole
        # post is about exactly one. A roundup that names several is not evidence.
        text = post["text"] or ""
        event_ids = names.decisive(text[:220])
        if not event_ids:
            whole = names.decisive(text)
            event_ids = whole if len(whole) == 1 else []
        if not event_ids:
            continue
        urls = post_images(post, collected)
        if len(urls) > 6:
            continue  # a long carousel is a roundup of the week
        for index, url in enumerate(urls):
            for event_id in event_ids:
                candidates.append({"event_id": event_id, "url": url, "source": post["source"],
                                   "posted": post.get("posted_at") or "", "order": index})
    return candidates


def site_candidates(collected, names):
    """Candidates from the festival's media library, albums, projects and articles."""
    candidates = []

    def add(event_ids, url, source=SITE, posted="", order=0):
        for event_id in event_ids:
            candidates.append({"event_id": event_id, "url": url, "source": source,
                               "posted": posted, "order": order})

    for deck_url, order in CARD_DECKS.items():
        deck = next((item for item in collected.get("instagram", {}).get("items", [])
                     if item.get("url") == deck_url), None)
        if not deck:
            continue
        photos = list(deck.get("images") or [])
        for position, event_id in enumerate(order):
            if position < len(photos):
                candidates.append({"event_id": event_id, "url": photos[position],
                                   "source": deck_url, "posted": "2026-11-13", "order": -100})

    for item in _get_json("/media"):
        if item.get("mediaType") != "Image" or not item.get("url"):
            continue
        alt = item.get("altText") or ""
        url = SITE + item["url"]
        if "Chuyện Đình trong Phố" in alt:
            add(DINH_SERIES, url)
            continue
        add(names.decisive(alt), url)

    for album in _get_json("/media-albums?sort=time&limit=48"):
        targets = ALBUM_EVENTS.get(album.get("slug"), [])
        if not targets:
            continue
        photos = [SITE + item["url"] for item in album.get("items") or []
                  if item.get("mediaType") == "Image" and item.get("url")]
        for position, event_id in enumerate(targets):
            shift = (position * 3) % max(len(photos), 1)
            for url in photos[shift:] + photos[:shift]:
                add([event_id], url)

    for project in _get_json("/projects"):
        if project.get("coverImageUrl"):
            add(names.decisive(project.get("title") or ""), SITE + project["coverImageUrl"])

    # The content endpoint is paged and has changed shape once already, so accept
    # either a bare list or the {items, totalPages} envelope.
    page = 1
    while page <= 12:
        payload = _get_json(f"/content?page={page}&pageSize=50")
        if isinstance(payload, dict):
            articles = payload.get("items") or []
            pages = payload.get("totalPages") or 1
        else:
            articles = payload or []
            pages = 1
        for article in articles:
            if not isinstance(article, dict) or not article.get("coverImageUrl"):
                continue
            if article.get("contentType") == "Page":
                continue
            add(names.decisive(article.get("title") or ""), SITE + article["coverImageUrl"])
        if page >= pages:
            break
        page += 1
    return candidates


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": SITE + "/"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def prepare(raw, max_width=1000, min_side=320):
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, "#ffffff")
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    if min(image.size) < min_side:
        return None
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.LANCZOS)
    return image


def fetch_all(urls, workers=8):
    """Download each URL once; the prepared image is cached under tmp/sync/scan."""
    SCAN_DIR.mkdir(parents=True, exist_ok=True)

    def one(url):
        key = hashlib.sha1(url.encode()).hexdigest()
        raw_path, jpg_path = SCAN_DIR / f"{key}.bin", SCAN_DIR / f"{key}.jpg"
        if jpg_path.exists():
            try:
                return url, Image.open(jpg_path).convert("RGB")
            except Exception:  # noqa: BLE001 - a half-written cache is not fatal
                pass
        try:
            raw = raw_path.read_bytes() if raw_path.exists() else download(url)
        except Exception:  # noqa: BLE001 - one bad URL must not stop the sweep
            return url, None
        raw_path.write_bytes(raw)
        try:
            image = prepare(raw)
        except Exception:  # noqa: BLE001
            return url, None
        if image is not None:
            image.save(jpg_path, "JPEG", quality=88)
        return url, image

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(one, urls))


def ensure_ocr():
    """Compile the Swift helper on macOS; None elsewhere (Linux CI has no Vision)."""
    if OCR_BIN.exists():
        return OCR_BIN
    if shutil.which("swiftc") is None:
        return None
    OCR_BIN.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["swiftc", "-O", str(OCR_SOURCE), "-o", str(OCR_BIN)],
                            capture_output=True, text=True)
    return OCR_BIN if result.returncode == 0 and OCR_BIN.exists() else None


def ocr_all(urls, binary):
    """{url: text}. Cached per image under tmp/sync/scan, so a rerun is free."""
    if binary is None:
        return {url: "" for url in urls}
    keys = {url: hashlib.sha1(url.encode()).hexdigest() for url in urls}
    todo = [key for key in keys.values()
            if not (SCAN_DIR / f"{key}.txt").exists() and (SCAN_DIR / f"{key}.jpg").exists()]
    for start in range(0, len(todo), 40):
        chunk = [str(SCAN_DIR / f"{key}.jpg") for key in todo[start:start + 40]]
        result = subprocess.run([str(binary), *chunk], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = Path(payload["file"]).stem
            (SCAN_DIR / f"{key}.txt").write_text(payload.get("text") or "", encoding="utf-8")
    texts = {}
    for url, key in keys.items():
        path = SCAN_DIR / f"{key}.txt"
        texts[url] = path.read_text(encoding="utf-8") if path.exists() else ""
    return texts


def harvest(data, posts, collected, max_per_event=MAX_IMAGES_PER_EVENT, use_ocr=True):
    """Full run: candidates → download → OCR → select → save. Returns (kept, stats)."""
    if Image is None:
        raise RuntimeError("Pillow is required: python3 -m pip install pillow")

    names = Names(data["events"])
    candidates = site_candidates(collected, names) + social_candidates(posts, collected, names)
    urls = list(dict.fromkeys(candidate["url"] for candidate in candidates))
    images = fetch_all(urls)
    binary = ensure_ocr() if use_ocr else None
    texts = ocr_all([url for url in urls if images.get(url) is not None], binary)
    kept = select(candidates, texts, images, names, max_per_event)
    stats = {
        "candidates": len(candidates),
        "downloaded": sum(1 for image in images.values() if image is not None),
        "ocr": binary is not None,
    }
    return kept, stats
