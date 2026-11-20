"""Social datasets to event drafts. Pure functions over the Apify payloads."""

import re

from extract import in_window, parse_dates, parse_times, quoted, vn_parts
from match import best_place, find_duplicate

_TYPE_WORD = re.compile(
    r"^(Trình diễn|Triển lãm|Trưng bày|Workshop|Tọa đàm|Toạ đàm|Trao đổi|Đêm nhạc|Chuỗi|Lễ|"
    r"Sắp đặt|Tour|Chiếu phim|Ra mắt|Giới thiệu|Pavilion|Sự kiện)", re.I)
_ANY_TYPE = re.compile(
    r"(Trình diễn|Triển lãm|Trưng bày|Workshop|Tọa đàm|Toạ đàm|Trao đổi|Đêm nhạc|Chuỗi|Sắp đặt|Tour|"
    r"Chiếu phim|Ra mắt|Giới thiệu|Múa đương đại|Múa rối|Vở múa|Vở kịch|Kịch múa|Cải lương|"
    r"Hoà nhạc|Hòa nhạc|Biểu diễn|Diễu hành|Trình tương tác|Điền dã|Lớp thực hành|Bộ hành|"
    r"Trải nghiệm|Pavilion|Sự kiện)", re.I)
_FESTIVAL_NAME = re.compile(r"^Lễ hội Thiết kế Sáng tạo", re.I)
_RELATIVE = re.compile(r"^(\d+\s*(giây|phút|giờ|ngày|tuần|tháng)\s*(trước)?|vừa xong|hôm qua)$", re.I)
_LABEL = re.compile(r"^(Thời gian|Địa điểm|Time|Location)\s*[:：]", re.I)
_SCHEDULE = re.compile(r"^(Diễn ra|Mở cửa|Kéo dài|Từ ngày)\b", re.I)
_BILINGUAL = re.compile(r"^\(?English below\)?$", re.I)


def _caption(item):
    caption = item.get("caption")
    if isinstance(caption, dict):
        return caption.get("text") or ""
    return caption if isinstance(caption, str) else ""


def read_posts(collected):
    """Flatten the three dataset shapes into {text, source, posted_at, network}."""
    posts = []
    for item in collected.get("instagram", {}).get("items", []):
        text = _caption(item)
        if text:
            posts.append({
                "text": text,
                "source": item.get("url") or (f"https://www.instagram.com/p/{item['shortCode']}/" if item.get("shortCode") else None),
                "posted_at": (vn_parts(item.get("timestamp")) or {}).get("date"),
                "network": "instagram",
            })
    for item in collected.get("facebook", {}).get("items", []):
        text = item.get("text") or ""
        if text:
            posts.append({
                "text": text,
                "source": item.get("url") or item.get("facebookUrl"),
                "posted_at": (vn_parts(item.get("time") or item.get("timestamp")) or {}).get("date"),
                "network": "facebook",
            })
    for profile in collected.get("threads", {}).get("items", []):
        for item in profile.get("latestPosts") or []:
            text = _caption(item)
            if not text:
                continue
            code = item.get("code")
            posts.append({
                "text": text,
                "source": item.get("canonical_url") or (f"https://www.threads.net/@{profile.get('username')}/post/{code}" if code else None),
                "posted_at": (vn_parts(_iso(item.get("taken_at"))) or {}).get("date"),
                "network": "threads",
            })
    return posts


def _iso(epoch):
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _heading(text, place_names):
    """The line that names the activity, else its quoted name, else the first sentence."""
    cleaned = []
    for original in _lines(text):
        line = re.sub(r"^[^0-9A-Za-zÀ-ỹ]+", "", original).strip()  # drop bullets and emoji
        if not line:
            continue
        if not 12 <= len(line) <= 160:
            continue
        if line.startswith("#") or "http" in line.lower() or line.lower().startswith("link"):
            continue
        if _FESTIVAL_NAME.match(line) or _RELATIVE.match(line) or _LABEL.match(line):
            continue
        if _SCHEDULE.match(line) or _BILINGUAL.match(line) or line.lower() in place_names:
            continue
        if line == line.upper() and len(line) < 48:  # "THÔNG BÁO DỜI LỊCH"
            continue
        cleaned.append(line)

    phrase = quoted(text)
    for line in cleaned:
        if _TYPE_WORD.match(line) and phrase and phrase in line:
            return _trim(line)
    if phrase:
        for line in cleaned:
            if phrase in line:
                return _trim(line)
        # Prose caption: the type word before the quote is the title.
        at = text.find(phrase)
        offset = max(0, at - 80)
        found = list(_ANY_TYPE.finditer(text[offset:at]))
        if found:
            return _trim(text[offset + found[-1].start(): at + len(phrase) + 2])
    for line in cleaned:
        if _TYPE_WORD.match(line):
            return _trim(line)
    if cleaned:
        return _trim(cleaned[0])
    paragraphs = [line for line in _lines(text) if len(line) >= 12]
    candidate = next((p for p in paragraphs if p != p.upper()), paragraphs[0] if paragraphs else "")
    sentence = re.split(r"(?<=[.!?])\s", candidate)[0]
    return _trim(sentence[:100] + ("…" if len(sentence) > 100 else ""))


def _trim(line):
    line = re.sub(r"\s*(?:vào\s+)?lúc\s+\d{1,2}[:h]\d{2}.*$", "", line, flags=re.I)
    line = re.sub(r"\s*(?:ngày\s+)?\d{1,2}/\d{1,2}.*$", "", line)
    line = re.sub(r"\s*(?:sẽ\s+)?(?:diễn\s+ra|tổ\s+chức|khai\s+mạc)\s*$", "", line, flags=re.I)
    line = line.strip(" ,;.–-")
    return line[:1].upper() + line[1:] if line else line


def build_draft(post, events, places):
    """One draft, with the flags a reviewer needs to triage it."""
    text = re.sub(r"[ \t]+", " ", post["text"].replace("\r", "")).strip()
    flat = " ".join(_lines(text))
    place_names = {place["name"].lower() for place in places}

    dates = parse_dates(flat)
    times = parse_times(flat)
    start, end = (times[0].split("–") if times else ("", ""))
    found_place = best_place(places, _venue_hint(flat, places))
    date_source = "prose" if dates else ("post" if post.get("posted_at") else None)
    date = dates[0] if dates else post.get("posted_at")
    date_end = dates[-1] if dates else date

    return {
        "title": _heading(text, place_names),
        "date": date or "",
        "dateEnd": date_end or "",
        "startTime": start,
        "endTime": end,
        "place": found_place[0]["name"] if found_place else "",
        "placeId": found_place[0]["id"] if found_place else "",
        "type": "",
        "detail": text[:1200],
        "source": post.get("source"),
        "network": post.get("network"),
        "postedAt": post.get("posted_at"),
        "confidence": {
            "venue": round(found_place[1], 2) if found_place else 0,
            "duplicateOf": find_duplicate(flat, events),
            "dateSource": date_source,
            "eventLike": bool(times) or any(_TYPE_WORD.match(line) for line in _lines(text)),
            "outOfWindow": bool(date) and not in_window(date, date_end or date),
        },
    }


def is_event_title(title):
    """A title has to start with the activity type; a quote inside prose is not one."""
    return bool(_TYPE_WORD.match(title or ""))


def _venue_hint(text, places):
    """The venue label is the longest known place name that appears verbatim."""
    folded = text.lower()
    found = [place["name"] for place in places if place["name"].lower() in folded]
    return max(found, key=len) if found else ""
