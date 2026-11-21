"""Pure text helpers: normalising, HTML, dates and times."""

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from config import FESTIVAL_YEAR

VN = timezone(timedelta(hours=7))

_ENTITIES = {
    "nbsp": " ", "amp": "&", "quot": '"', "apos": "'", "lt": "<", "gt": ">",
    "ndash": "–", "mdash": "—", "hellip": "…", "rsquo": "’", "lsquo": "‘",
    "rdquo": "”", "ldquo": "“",
}

_QUOTED = re.compile(r"[“\"]([^”\"]{3,})[”\"]")
_TIME_RANGE = re.compile(r"(\d{1,2})[:h](\d{2})\s*[-–—]\s*(\d{1,2})[:h](\d{2})")
_LABEL_SCHEDULE = re.compile(r"(?:Thời gian|Time)\s*[:：]\s*([^\n]{0,240})", re.I)
_SENTENCE_SPLIT = re.compile(r"[^.!?\n]+[.!?]?")
_FULL_RANGE = re.compile(r"(\d{1,2})/(\d{1,2})\s*(?:[-–—]|đến)\s*(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")
_DAY_RANGE = re.compile(r"(?<![/\d])(\d{1,2})\s*(?:[-–—]|đến)\s*(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")
_SINGLE_DATE = re.compile(r"(?:ngày\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")


def fold(text):
    """Lower-case, strip diacritics and punctuation so spellings compare equal."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def decode_entities(text):
    text = re.sub(r"&#x([0-9a-f]+);", lambda m: chr(int(m.group(1), 16)), text, flags=re.I)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    return re.sub(r"&([a-z]+);", lambda m: _ENTITIES.get(m.group(1).lower(), m.group(0)), text, flags=re.I)


def html_to_text(html):
    """detailHtml to the plain-text shape stored in officialDetail."""
    if not html:
        return ""
    text = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", "", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|section|li|h[1-6]|tr|blockquote)>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = decode_entities(text)
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def same_text(left, right):
    """Whitespace-insensitive comparison, so re-converting HTML is a no-op."""
    def norm(value):
        value = re.sub(r"[ \t\u00a0]+", " ", value or "")
        return re.sub(r" ?\n ?", "\n", value).strip()
    return norm(left) == norm(right)


def vn_parts(iso):
    """The site sends UTC; the festival and the page use UTC+7."""
    if not iso:
        return None
    try:
        moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(VN)
    return {"date": local.strftime("%Y-%m-%d"), "time": local.strftime("%H:%M")}


def epoch_parts(seconds):
    try:
        local = datetime.fromtimestamp(int(seconds), VN)
    except (TypeError, ValueError, OSError):
        return None
    return {"date": local.strftime("%Y-%m-%d"), "time": local.strftime("%H:%M")}


def parse_times(text):
    """All "19:00 - 21:00" style ranges, de-duplicated, in order."""
    found = []
    for match in _TIME_RANGE.finditer(text or ""):
        value = f"{int(match.group(1)):02d}:{match.group(2)}–{int(match.group(3)):02d}:{match.group(4)}"
        if value not in found:
            found.append(value)
    return found


def _valid(day, month, year):
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def parse_dates(text, year=FESTIVAL_YEAR):
    """Every date the prose mentions, ascending, ISO formatted."""
    found = []
    text = text or ""

    def add(day, month, y):
        if _valid(day, month, y):
            found.append(f"{y:04d}-{month:02d}-{day:02d}")

    # Full range first so "13/11 đến 28/11" is not read as "11 đến 28/11".
    for match in _FULL_RANGE.finditer(text):
        y = int(match.group(5) or year)
        add(int(match.group(1)), int(match.group(2)), y)
        add(int(match.group(3)), int(match.group(4)), y)
    for match in _DAY_RANGE.finditer(text):
        y = int(match.group(4) or year)
        add(int(match.group(1)), int(match.group(3)), y)
        add(int(match.group(2)), int(match.group(3)), y)
    for match in _SINGLE_DATE.finditer(text):
        add(int(match.group(1)), int(match.group(2)), int(match.group(3) or year))
    return sorted(set(found))


def prose_facts(text):
    """The "Thời gian / Địa điểm" labels, plus whatever dates and times exist."""
    source = text or ""
    flat = re.sub(r"\n+", " ", source)

    def label(name):
        match = re.search(name + r"\s*[:：]\s*([^\n|]{0,220})", source, flags=re.I)
        if not match:
            match = re.search(
                name + r"\s*[:：]\s*([^|]{0,220}?)(?=\s*(?:Thời gian|Địa điểm|Time|Location)\s*[:：]|$)",
                flat, flags=re.I)
        return match.group(1).strip() if match else None

    return {
        "time": label("Thời gian"),
        "place": label("Địa điểm"),
        "times": parse_times(flat),
        "dates": parse_dates(flat),
    }


def quoted(text):
    match = _QUOTED.search(text or "")
    return match.group(1) if match else None


def schedule_claim(text):
    """Dates and times from the post's own schedule, not from the whole caption.

    Captions usually repeat the festival's 13–28/11 window in a footer, so reading
    the whole text would turn every post into a claim about the entire festival.
    Only the "Thời gian / Time" labels, or the sentences that carry a time range,
    are read.
    """
    source = text or ""
    segments = [match.group(1) for match in _LABEL_SCHEDULE.finditer(source)]
    if not segments:
        segments = [part.strip() for part in _SENTENCE_SPLIT.findall(source)
                    if _TIME_RANGE.search(part)]

    claims = [(parse_times(segment), parse_dates(segment)) for segment in segments]
    first_times = [times[0] for times, _ in claims if times]
    if len(set(first_times)) > 1:
        # Two different schedules: the post describes several sessions.
        return {"dates": [], "times": [], "ambiguous": True}

    dates, times = [], []
    for segment_times, segment_dates in claims:
        for value in segment_times:
            if value not in times:
                times.append(value)
        for value in segment_dates:
            if value not in dates:
                dates.append(value)
    return {"dates": sorted(dates), "times": times, "ambiguous": False}


def in_window(start, end=None):
    if not start:
        return False
    return (end or start) >= "2026-11-13" and start <= "2026-11-28"
