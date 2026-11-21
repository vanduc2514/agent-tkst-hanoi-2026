"""Schedule overrides from the organiser's posts. Pure functions, no I/O.

The listing API publishes coarse, often wrong hours, while the organiser posts the
real times on Facebook and Instagram. A post therefore wins over the curated
schedule, but only when it names exactly one event and carries its own schedule.
Map pins, titles and per-day `slots`/`lineup`/`days` stay curated.
"""

from config import FESTIVAL_END, FESTIVAL_START
from extract import schedule_claim
from match import named_event


def _singleday(event):
    return (event.get("dateEnd") or event.get("date")) == event.get("date")


def schedule_proposals(posts, events):
    """The newest dated claim per event: {eventId, dates, startTime, endTime, ...}."""
    proposals = {}
    for post in posts:
        text = post.get("text") or ""
        claim = schedule_claim(text)
        if claim["ambiguous"] or not claim["times"]:
            continue
        dates = [day for day in claim["dates"] if FESTIVAL_START <= day <= FESTIVAL_END]
        if claim["dates"] and not dates:
            continue  # the only dates it names are outside the festival
        event = named_event(text, events)
        if not event:
            continue
        if event.get("slots") or event.get("lineup") or event.get("days"):
            continue  # a curated per-day schedule is richer than one post
        previous = proposals.get(event["id"])
        if previous and (previous["postedAt"] or "") >= (post.get("posted_at") or ""):
            continue
        start, end = claim["times"][0].split("–")
        proposals[event["id"]] = {
            "eventId": event["id"],
            "title": event["title"],
            "dates": dates,
            "startTime": start,
            "endTime": end,
            "postUrl": post.get("source"),
            "network": post.get("network"),
            "postedAt": post.get("posted_at"),
        }
    return sorted(proposals.values(), key=lambda item: item["eventId"])


def schedule_changes(event, proposal):
    """The curated fields where the post disagrees with the stored schedule."""
    changes = []
    for field in ("startTime", "endTime"):
        if proposal.get(field) and proposal[field] != event.get(field):
            changes.append({"field": field, "was": event.get(field), "social": proposal[field]})
    dates = proposal.get("dates") or []
    if dates:
        first, last = dates[0], dates[-1]
        if first != event.get("date"):
            changes.append({"field": "date", "was": event.get("date"), "social": first})
        if last != (event.get("dateEnd") or event.get("date")):
            changes.append({"field": "dateEnd", "was": event.get("dateEnd") or event.get("date"), "social": last})
    return changes


def can_override(event, proposal):
    """A single date on a multi-day event is one session, not a reschedule."""
    return len(proposal.get("dates") or []) != 1 or _singleday(event)


def apply_schedules(data, proposals):
    """Write the claims a post may override; return what was applied and what to review."""
    events = {event["id"]: event for event in data["events"]}
    applied, review = [], []
    for proposal in proposals:
        event = events.get(proposal["eventId"])
        if not event:
            continue
        changes = schedule_changes(event, proposal)
        if not changes:
            continue
        if not can_override(event, proposal):
            review.append((event, proposal, changes))
            continue
        for change in changes:
            event[change["field"]] = change["social"]
        applied.append((event, proposal, changes))
    return applied, review
