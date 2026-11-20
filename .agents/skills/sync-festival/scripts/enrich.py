"""Registration links from social posts. Pure functions, no I/O."""

import re

from match import best_event

_FORM_HOST = re.compile(r"(forms\.gle|docs\.google\.com/forms|airtable\.com|typeform\.com|tally\.so|jotform\.com|forms\.office\.com)", re.I)
_URL = re.compile(r"https?://[^\s\"'<>)]+")


def form_links(text):
    """Registration URLs in one post, de-duplicated and stripped of trailing punctuation."""
    found = []
    for raw in _URL.findall(text or ""):
        url = raw.rstrip(".,;:)")
        if _FORM_HOST.search(url) and url not in found:
            found.append(url)
    return found


def registration_proposals(posts, events):
    """One proposal per event: {eventId, url, postUrl, network, postedAt}."""
    proposals = {}
    for post in posts:
        links = form_links(post.get("text") or "")
        if not links:
            continue
        match = best_event(post.get("text") or "", events)
        if not match:
            continue
        event_id = match["id"]
        # Keep the newest post for an event; older ones usually carry dead links.
        previous = proposals.get(event_id)
        if previous and (previous["postedAt"] or "") >= (post.get("posted_at") or ""):
            continue
        proposals[event_id] = {
            "eventId": event_id,
            "title": match["title"],
            "url": links[0],
            "postUrl": post.get("source"),
            "network": post.get("network"),
            "postedAt": post.get("posted_at"),
        }
    return sorted(proposals.values(), key=lambda p: p["eventId"])


def apply_registrations(data, proposals):
    """Fill registrationUrl where it is missing; report what was kept."""
    events = {event["id"]: event for event in data["events"]}
    filled, kept = [], []
    for proposal in proposals:
        event = events.get(proposal["eventId"])
        if not event:
            continue
        if event.get("registrationUrl"):
            if event["registrationUrl"] != proposal["url"]:
                kept.append((event["id"], event["registrationUrl"], proposal["url"]))
            continue
        event["registrationUrl"] = proposal["url"]
        filled.append((event["id"], proposal["url"]))
    return filled, kept
