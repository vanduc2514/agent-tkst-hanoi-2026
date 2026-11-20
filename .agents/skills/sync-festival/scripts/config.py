"""Fixed facts about the festival and its data sources."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
EVENTS = SRC / "events.json"
WORK = ROOT / "tmp" / "sync"

SITE = "https://lehoithietkesangtao.vn"
PUBLIC_API = f"{SITE}/api/public"
EVENT_URL = SITE + "/su-kien/{slug}.html"

FESTIVAL_START = "2026-11-13"
FESTIVAL_END = "2026-11-28"
FESTIVAL_YEAR = 2026

# Verified against the site footer and the profiles themselves.
ACCOUNTS = {
    "instagram": "https://www.instagram.com/lehoithietkesangtaohanoi/",
    "facebook": "https://www.facebook.com/lehoithietkesangtaohn",
    "threads": "lehoithietkesangtaohanoi",
}

# Pay-per-event pricing on the free plan, per dataset item (checked 2026-11-20).
ACTOR_COST = {
    "apify/instagram-scraper": 0.0027,
    "apify/facebook-posts-scraper": 0.005,
    "apify/threads-profile-api-scraper": 0.005,
}

GENRE = {
    "Exhibition": "triển lãm",
    "Performance": "trình diễn",
    "Workshop": "workshop",
    "Talk": "tọa đàm",
    "Event": "sự kiện",
    "Community": "cộng đồng",
    "Pavilion": "pavilion",
    "Tour": "tour",
    "Fair": "hội chợ",
}

# Fields the organiser owns. Everything else in an event is curated here.
ORGANISER_FIELDS = ("officialUrl", "officialType", "officialSummary", "officialDetail",
                    "officialVenue", "officialVenueAddress")
FILL_WHEN_EMPTY = ("officialType", "officialVenue", "officialVenueAddress", "officialUrl")
