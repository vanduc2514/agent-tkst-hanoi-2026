"""Loading, validating and saving src/events.json."""

import json
import re

from config import EVENTS, FESTIVAL_END, FESTIVAL_START, GENRE
from match import slug_of

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load(path=EVENTS):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(data, path=EVENTS):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def validate(data):
    """Return (problems, notes). Problems break the app; notes are documented quirks."""
    problems, notes = [], []
    events = data.get("events", [])
    places = {place["id"] for place in data.get("places", [])}
    clusters = set(data.get("clusters", {}))

    seen_ids, seen_urls = set(), {}
    for event in events:
        eid = event.get("id")
        if eid in seen_ids:
            problems.append(f"{eid}: duplicate id")
        seen_ids.add(eid)

        if not _DATE.match(event.get("date") or ""):
            problems.append(f"{eid}: bad date {event.get('date')!r}")
        if event.get("dateEnd") and not _DATE.match(event["dateEnd"]):
            problems.append(f"{eid}: bad dateEnd {event['dateEnd']!r}")
        if event.get("dateEnd") and event["dateEnd"] < event.get("date", ""):
            problems.append(f"{eid}: dateEnd before date")

        for field in ("startTime", "endTime"):
            if not _TIME.match(event.get(field) or ""):
                problems.append(f"{eid}: bad {field} {event.get(field)!r}")

        if not event.get("dateEnd") or event["dateEnd"] == event.get("date"):
            if (event.get("endTime") or "") < (event.get("startTime") or ""):
                notes.append(f"{eid}: endTime before startTime")

        if event.get("placeId") not in places:
            problems.append(f"{eid}: unknown placeId {event.get('placeId')}")
        if event.get("clusterId") not in clusters:
            problems.append(f"{eid}: unknown clusterId {event.get('clusterId')}")

        url = event.get("officialUrl")
        if url:
            if url in seen_urls:
                problems.append(f"{eid}: officialUrl also used by {seen_urls[url]}")
            seen_urls[url] = eid

        for slot in event.get("slots") or []:
            if not _TIME.match(slot.get("start") or "") or not _TIME.match(slot.get("end") or ""):
                problems.append(f"{eid}: bad slot {slot}")
            if not _DATE.match(slot.get("date") or ""):
                problems.append(f"{eid}: bad slot date {slot.get('date')}")

        for act in event.get("lineup") or []:
            if not _TIME.match(act.get("start") or "") or not _TIME.match(act.get("end") or ""):
                problems.append(f"{eid}: bad lineup row {act}")

    numbers = [event.get("number") for event in events]
    for index in range(1, len(numbers)):
        if numbers[index] != numbers[index - 1] + 1:
            problems.append(f"numbering breaks at {events[index].get('id')}")
            break

    return problems, notes


def renumber(data):
    for index, event in enumerate(data.get("events", []), start=1):
        event["number"] = index


def next_number(events):
    return max((event.get("number") or 0 for event in events), default=0) + 1


def new_event(draft, place, number, detail=None):
    """Build a fully-populated event from a social draft."""
    event = {
        "id": f"e{number}",
        "number": number,
        "date": draft["date"],
        "dateEnd": draft.get("dateEnd") or draft["date"],
        "days": None,
        "title": draft["title"].strip(),
        "placeId": place["id"],
        "clusterId": place["clusterId"],
        "startTime": draft["startTime"],
        "endTime": draft["endTime"],
        "spotlight": bool(draft.get("spotlight")),
        "tags": [tag for tag in (genres(draft), place["name"]) if tag],
        "description": draft.get("description") or draft.get("detail") or "",
    }
    if draft.get("slots"):
        event["slots"] = draft["slots"]
    if draft.get("type"):
        event["officialType"] = draft["type"]
    if draft.get("source"):
        event["officialUrl"] = draft["source"]
    if draft.get("detail"):
        event["officialDetail"] = draft["detail"]
    if draft.get("venue"):
        event["officialVenue"] = draft["venue"]
    if detail:
        event.update(detail)
    return event


def genres(draft):
    kind = draft.get("type") or ""
    first = kind.split(",")[0].strip()
    return GENRE.get(first, first.lower()) if first else ""


def within_festival(event):
    end = event.get("dateEnd") or event.get("date")
    return end >= FESTIVAL_START and event.get("date", "") <= FESTIVAL_END


def known_slugs(events):
    return {slug for event in events if (slug := slug_of(event))}
