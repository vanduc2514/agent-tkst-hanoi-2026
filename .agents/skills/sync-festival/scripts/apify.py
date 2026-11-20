"""The only retrieval path: Apify actors over their REST API (stdlib only)."""

import json
import os
import time
import urllib.error
import urllib.request

from config import ACCOUNTS, ACTOR_COST

BASE = "https://api.apify.com/v2"
ACTORS = {
    "instagram": "apify/instagram-scraper",
    "facebook": "apify/facebook-posts-scraper",
    "threads": "apify/threads-profile-api-scraper",
}


class ApifyError(RuntimeError):
    pass


def _token():
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise ApifyError("APIFY_TOKEN is not set; export the token first")
    return token


def _request(path, payload=None):
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    request.add_header("Authorization", f"Bearer {_token()}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise ApifyError(f"{error.code} {url}: {error.read()[:200].decode(errors='ignore')}") from error


def run_actor(actor, payload, timeout=600, poll=5):
    """Run an actor to completion and return {run_id, dataset_id, cost_usd}."""
    actor_path = actor.replace("/", "~")
    run = _request(f"/acts/{actor_path}/runs?waitForFinish=60", payload)["data"]
    deadline = time.time() + timeout
    while run["status"] in {"READY", "RUNNING"}:
        if time.time() > deadline:
            raise ApifyError(f"{actor} timed out after {timeout}s")
        time.sleep(poll)
        run = _request(f"/actor-runs/{run['id']}")["data"]
    if run["status"] != "SUCCEEDED":
        raise ApifyError(f"{actor} finished {run['status']}")
    return {
        "actor": actor,
        "run_id": run["id"],
        "dataset_id": run["defaultDatasetId"],
        "cost_usd": run.get("usageTotalUsd") or 0.0,
        "items": run.get("stats", {}).get("datasetItemCount", 0),
    }


def dataset_items(dataset_id, limit=1000):
    items, offset = [], 0
    while True:
        page = _request(f"/datasets/{dataset_id}/items?clean=true&format=json&limit={min(limit, 1000)}&offset={offset}")
        if not page:
            return items
        items.extend(page)
        offset += len(page)
        if len(page) < 1000 or len(items) >= limit:
            return items


def inputs(posts_per_profile=25):
    """Actor inputs for the three accounts, with the festival window applied."""
    return {
        "instagram": {
            "directUrls": [ACCOUNTS["instagram"]],
            "resultsType": "posts",
            "resultsLimit": posts_per_profile,
            "onlyPostsNewerThan": "60 days",
        },
        "facebook": {
            "startUrls": [{"url": ACCOUNTS["facebook"]}],
            "resultsLimit": posts_per_profile,
            "onlyPostsNewerThan": "2026-10-01",
        },
        "threads": {"usernames": [ACCOUNTS["threads"]]},
    }


def fetch_all(posts_per_profile=25):
    """Run the three actors and return their items plus the spend."""
    payloads = inputs(posts_per_profile)
    collected, spend = {}, 0.0
    for network, payload in payloads.items():
        run = run_actor(ACTORS[network], payload)
        items = dataset_items(run["dataset_id"])
        # usageTotalUsd can lag behind the event log, so fall back to the list price.
        run["cost_usd"] = run["cost_usd"] or ACTOR_COST[ACTORS[network]] * len(items)
        spend += run["cost_usd"]
        collected[network] = {"run": run, "items": items}
    return collected, round(spend, 4)
