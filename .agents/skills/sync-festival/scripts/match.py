"""Lookup helpers: venues, duplicate posts, event slugs."""

import math
import re

from config import EVENT_URL, GENRE
from extract import fold, quoted

_SLUG = re.compile(r"lehoithietkesangtao\.vn/(?:su-kien|workshop)/(.+?)\.html")


def slug_of(event):
    match = _SLUG.search(event.get("officialUrl") or "")
    return match.group(1) if match else None


def official_url(slug):
    return EVENT_URL.format(slug=slug)


def tokens(text):
    return {word for word in fold(text).split() if word}


def coverage(outer, inner):
    """How much of `inner` appears in `outer`."""
    outer_tokens, inner_tokens = tokens(outer), tokens(inner)
    if not inner_tokens:
        return 0.0
    return len(outer_tokens & inner_tokens) / len(inner_tokens)


def best_place(places, venue):
    """Map a venue label to a pin. Exact, then containment, then token overlap."""
    if not venue or not venue.strip():
        return None
    wanted = fold(venue)
    best = None
    for place in places:
        name = fold(place.get("name"))
        address = fold(place.get("address") or "")
        if name == wanted or address == wanted:
            score = 1.0
        elif name and (name in wanted or wanted in name):
            score = 0.9
        else:
            score = max(coverage(name, wanted), coverage(wanted, name))
        if score >= 0.75 and (best is None or score > best[1]):
            best = (place, score)
    return best


class TitleIndex:
    """Token rarity across event titles, so generic words count for little."""

    def __init__(self, events):
        self.total = max(len(events), 1)
        self.frequency = {}
        for event in events:
            for word in tokens(event.get("title")):
                self.frequency[word] = self.frequency.get(word, 0) + 1

    def weight(self, word):
        return 1 / math.log(1 + self.total / max(self.frequency.get(word, 1), 1))

    def rare(self, word):
        return self.frequency.get(word, 0) <= max(3, self.total * 0.05)

    def score(self, text, title):
        words = list(tokens(title))
        if not words:
            return 0.0, 0.0, 0
        posted = tokens(text)
        hits = [word for word in words if word in posted]
        weight_all = sum(self.weight(word) for word in words)
        weight_hit = sum(self.weight(word) for word in hits)
        return (
            weight_hit / weight_all if weight_all else 0.0,
            len(hits) / len(words),
            sum(1 for word in hits if self.rare(word)),
        )


def find_duplicate(text, events):
    """The event a post most likely talks about, or None."""
    index = TitleIndex(events)
    phrase = quoted(text)
    candidates = []
    for event in events:
        weighted, plain, distinctive = index.score(text, event.get("title") or "")
        if weighted < 0.75 or plain < 0.75 or distinctive < 1:
            continue
        if phrase:
            overlap = max(coverage(phrase, event["title"]), coverage(event["title"], phrase))
            if overlap < 0.34:
                continue
        candidates.append((event, weighted))
    if not candidates:
        return None
    event, score = max(candidates, key=lambda pair: pair[1])
    return {"id": event["id"], "title": event["title"], "score": round(score, 2)}


def genre_tag(event_type):
    first = (event_type or "").split(",")[0].strip()
    return GENRE.get(first, first.lower())
