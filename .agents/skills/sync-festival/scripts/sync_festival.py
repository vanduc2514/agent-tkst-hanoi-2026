#!/usr/bin/env python3
"""Keep src/events.json in step with the organiser.

Retrieval is Apify only: three actors cover the Facebook page, the Instagram
profile and the Threads profile. The official site is read over its public JSON
API. Nothing here scrapes HTML pages or drives a browser.

    python3 sync_festival.py fetch            # Apify → tmp/sync/social.json
    python3 sync_festival.py diff             # site API + social → tmp/sync/report.md
    python3 sync_festival.py apply            # write the safe fills
    python3 sync_festival.py apply --insert-social   # also add new events from drafts
    python3 sync_festival.py check            # validate events.json only

Exit codes: 0 fine, 1 something to review or a validation problem, 2 retrieval
failed.
"""

import argparse
import json
import sys
import urllib.request

import apify
import social
from config import EVENTS, FESTIVAL_END, FESTIVAL_START, PUBLIC_API, WORK
from events_model import (
    known_slugs, load, new_event, next_number, renumber, save, validate, within_festival,
)
from extract import html_to_text, same_text, vn_parts
from match import best_place, official_url, slug_of

UA = "Mozilla/5.0 (compatible; tkst-sync/2.0)"
META = {"officialType", "officialVenue", "officialVenueAddress", "officialUrl", "officialSummary", "title"}


# --------------------------------------------------------------------- retrieval

def site_json(path):
    request = urllib.request.Request(f"{PUBLIC_API}{path}", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def site_events():
    return site_json("/events?limit=500")


def site_venues():
    return site_json("/venues?limit=500")


def site_detail(slug):
    return site_json(f"/events/{slug}")


# -------------------------------------------------------------------------- diff

def compare(data, remote):
    """Field-level differences between the site and events.json."""
    events, places = data["events"], data["places"]
    by_slug, by_title = {}, {}
    for event in events:
        slug = slug_of(event)
        if slug:
            by_slug[slug] = event
        by_title[event["title"].strip().lower()] = event

    seen, rows = set(), []
    for item in remote:
        event = by_slug.get(item["slug"]) or by_title.get(item["title"].strip().lower())
        start, end = vn_parts(item.get("startAt")), vn_parts(item.get("endAt"))
        if event is None:
            rows.append({"kind": "new", "slug": item["slug"], "item": item, "start": start, "end": end})
            continue

        seen.add(event["id"])
        changes = []

        def note(field, site_value):
            was = event.get(field)
            changes.append({"field": field, "was": was, "site": site_value, "empty": not was})

        def squash(value):
            return " ".join((value or "").split())

        # Whitespace-only differences are not drift.
        if squash(item["title"]).lower() != squash(event["title"]).lower():
            note("title", item["title"])
        if item.get("eventType") and item["eventType"] != (event.get("officialType") or ""):
            note("officialType", item["eventType"])
        if item.get("venueName") and item["venueName"] != (event.get("officialVenue") or ""):
            note("officialVenue", item["venueName"])
        url = official_url(item["slug"])
        if url != (event.get("officialUrl") or ""):
            note("officialUrl", url)

        # A curated per-day schedule cannot be expressed by the site's window.
        curated = bool(event.get("slots") or event.get("lineup"))
        dates = []
        if curated:
            dates.append({"field": "schedule", "curated": True})
        else:
            if start and (start["date"] != event["date"] or start["time"] != event["startTime"]):
                dates.append({"field": "start", "was": f"{event['date']} {event['startTime']}", "site": f"{start['date']} {start['time']}"})
            if end and (end["date"] != (event.get("dateEnd") or event["date"]) or end["time"] != event.get("endTime")):
                dates.append({"field": "end", "was": f"{event.get('dateEnd') or event['date']} {event['endTime']}", "site": f"{end['date']} {end['time']}"})

        venue_note = None
        found = best_place(places, item.get("venueName") or "")
        if found and found[0]["id"] != event["placeId"]:
            current = next((p["name"] for p in places if p["id"] == event["placeId"]), event["placeId"])
            venue_note = {"site": item.get("venueName"), "pin": current, "suggested": found[0]["name"]}

        rows.append({
            "kind": "changed" if changes or any(not d.get("curated") for d in dates) else "same",
            "id": event["id"],
            "slug": item["slug"],
            "changes": changes,
            "dates": dates,
            "venueNote": venue_note,
        })

    # An event whose slug never appeared is either unpublished or renamed; events
    # without a URL cannot be checked at all.
    missing = [e for e in events if e["id"] not in seen and slug_of(e)]
    unlinked = [e for e in events if not slug_of(e)]
    return {"rows": rows, "missing": missing, "unlinked": unlinked}


def render(data, rows, missing, unlinked, social_drafts=None):
    """A 4 KB triage sheet: what to fix, what is safe, what to ignore."""
    lines = []
    add = lines.append
    changed = [row for row in rows if row["kind"] == "changed"]
    same = [row for row in rows if row["kind"] == "same"]
    new_in = [row for row in rows if row["kind"] == "new" and within_festival({"date": (row["start"] or {}).get("date", ""), "dateEnd": (row["end"] or {}).get("date")})]
    new_out = [row for row in rows if row["kind"] == "new" and row not in new_in]

    human = [row for row in changed if any(c["field"] == "title" for c in row["changes"])
             or any(not d.get("curated") for d in row["dates"])]
    fills = [row for row in changed if row not in human and any(c.get("empty") for c in row["changes"])]
    kept = [row for row in changed if row not in human and row not in fills]
    curated = sum(1 for row in rows if any(d.get("curated") for d in row.get("dates", [])))

    add(f"# Festival sync — {FESTIVAL_START} → {FESTIVAL_END}\n")
    add("| bucket | count | action |")
    add("|---|---|---|")
    add(f"| needs a human | {len(human)} | read the table, edit by hand |")
    add(f"| safe fills | {len(fills)} | `sync_festival.py apply` |")
    add(f"| kept curated | {len(kept)} | already set here, left alone |")
    add(f"| new in window | {len(new_in)} | review, then add by hand |")
    add(f"| new outside the window | {len(new_out)} | ignore |")
    add(f"| curated schedules | {curated} | kept as-is |")
    add(f"| no drift | {len(same)} | — |")
    add(f"| no officialUrl | {len(unlinked)} | unverifiable |")
    add("")

    if new_in:
        add("## New in the window\n")
        add("| slug | title | start | venue |")
        add("|---|---|---|---|")
        for row in new_in:
            start = row["start"] or {}
            add(f"| `{row['slug']}` | {row['item']['title']} | {start.get('date', '—')} {start.get('time', '')} | {row['item'].get('venueName') or '—'} |")
        add("")

    if human:
        add("## Needs a human\n")
        add("| id | field | events.json | site |")
        add("|---|---|---|---|")
        for row in human:
            for change in row["changes"]:
                if change["field"] == "title":
                    add(f"| `{row['id']}` | title | {change['was']} | {change['site']} |")
            for date in row["dates"]:
                if not date.get("curated"):
                    add(f"| `{row['id']}` | {date['field']} | {date['was']} | {date['site']} |")
        add("")

    if fills:
        add("## Safe fills\n")
        for field in sorted({c["field"] for row in fills for c in row["changes"]}):
            ids = [row["id"] for row in fills if any(c["field"] == field for c in row["changes"])]
            add(f"- **{field}** ({len(ids)}): {', '.join(ids)}")
        add("")

    if kept:
        add("## Kept curated values\n")
        for row in kept[:10]:
            for change in row["changes"]:
                if change["field"] != "title":
                    add(f"- `{row['id']}` {change['field']}: keeping {change['was']!r} (site says {change['site']!r})")
        add("")

    if social_drafts is not None:
        ready = [d for d in social_drafts if is_ready(d)]
        dupes = [d for d in social_drafts if d["confidence"]["duplicateOf"]]
        add("## Social posts\n")
        add(f"{len(social_drafts)} posts · {len(ready)} ready to add · {len(dupes)} match an existing event")
        for draft in ready[:10]:
            add(f"- {draft['date']} {draft['startTime']} `{draft['placeId']}` {draft['title'][:70]}")
        add("")

    notes = [row for row in rows if row.get("venueNote")]
    if notes:
        add(f"## Venue label vs pin ({len(notes)}) — informational\n")
        add("The site names an area, the repo pins a building. Nothing to change.")
        add("")

    if missing:
        add("## Slug no longer on the site\n")
        for event in missing[:10]:
            add(f"- `{event['id']}` {event['title']} — {event.get('officialUrl')}")
        add("")

    if unlinked:
        add("## No officialUrl — cannot be verified\n")
        add(", ".join(event["id"] for event in unlinked))
        add("")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------- apply

def apply_safe(data, rows):
    """Fill empty organiser fields. Curated values are reported, never overwritten."""
    events = {event["id"]: event for event in data["events"]}
    filled, kept = [], []
    for row in rows:
        if row["kind"] != "changed":
            continue
        event = events.get(row.get("id"))
        if not event:
            continue
        for change in row["changes"]:
            field = change["field"]
            if field not in META or field == "title":
                continue
            if field == "officialSummary":
                continue
            if not event.get(field):
                event[field] = change["site"]
                filled.append((event["id"], field))
            else:
                kept.append((event["id"], field, event[field], change["site"]))
    return filled, kept


def apply_social(data, drafts):
    """Insert drafts that carry a date, a time and a resolvable place."""
    places = data["places"]
    inserted, skipped = [], []
    for draft in drafts:
        found = best_place(places, draft.get("place") or "")
        if not is_ready(draft) or not found:
            skipped.append(draft)
            continue
        if not within_festival({"date": draft["date"], "dateEnd": draft.get("dateEnd")}):
            skipped.append(draft)
            continue
        number = next_number(data["events"])
        data["events"].append(new_event(draft, found[0], number))
        inserted.append((f"e{number}", draft["title"]))
    renumber(data)
    return inserted, skipped


def is_ready(draft):
    """A draft is insertable only when every field is present and it is a real activity."""
    confidence = draft.get("confidence") or {}
    return bool(
        draft.get("date")
        and draft.get("startTime")
        and draft.get("placeId")
        and len(draft.get("title") or "") >= 8
        and social.is_event_title(draft.get("title"))
        and confidence.get("eventLike")
        and not confidence.get("duplicateOf")
        and not confidence.get("outOfWindow")
    )


# --------------------------------------------------------------------------- CLI

def read_social():
    path = WORK / "social.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return social.read_posts(payload.get("collected", {}))


def cmd_fetch(args):
    collected, spend = apify.fetch_all(args.limit)
    WORK.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetchedAt": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "spendUsd": spend,
        "collected": {network: {"run": entry["run"], "items": entry["items"]} for network, entry in collected.items()},
    }
    (WORK / "social.json").write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    for network, entry in collected.items():
        print(f"  {network:<10} {len(entry['items']):>3} item(s)  ${entry['run']['cost_usd']:.4f}")
    print(f"spend ${spend:.4f} → {WORK / 'social.json'}")
    return 0


def cmd_diff(args):
    data = load()
    remote = site_events()
    diff = compare(data, remote)
    drafts = read_social()
    if drafts:
        drafts = [social.build_draft(post, data["events"], data["places"]) for post in drafts]

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "report.md").write_text(render(data, diff["rows"], diff["missing"], diff["unlinked"], drafts), encoding="utf-8")
    if drafts is not None:
        (WORK / "social-drafts.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = {}
    for row in diff["rows"]:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    print(f"site {len(remote)} · events.json {len(data['events'])} · same {counts.get('same', 0)} · "
          f"changed {counts.get('changed', 0)} · new {counts.get('new', 0)} · unlinked {len(diff['unlinked'])}")
    print(f"report {WORK / 'report.md'}")
    return 1 if counts.get("changed") else 0


def cmd_apply(args):
    data = load()
    diff = compare(data, site_events())
    filled, kept = apply_safe(data, diff["rows"])
    inserted, skipped = [], []
    if args.insert_social:
        drafts = read_social() or []
        drafts = [social.build_draft(post, data["events"], data["places"]) for post in drafts]
        inserted, skipped = apply_social(data, drafts)
    save(data)

    print(f"filled {len(filled)} · kept curated {len(kept)} · inserted {len(inserted)}")
    for eid, field in filled[:15]:
        print(f"  {eid}: {field}")
    for eid, field, kept_value, site_value in kept[:10]:
        print(f"  kept {eid} {field}={kept_value!r} (site {site_value!r})")
    for eid, title in inserted:
        print(f"  + {eid} {title}")
    if skipped:
        print(f"  {len(skipped)} draft(s) not inserted — missing date, time, place or outside the window")
    problems, notes = validate(data)
    print("validation clean" if not problems else f"validation: {len(problems)} problem(s)")
    for problem in problems[:10]:
        print(f"  {problem}")
    return 1 if problems else 0


def cmd_social(args):
    drafts = read_social()
    if drafts is None:
        print("no social.json yet — run `sync_festival.py fetch` first", file=sys.stderr)
        return 2
    data = load()
    built = [social.build_draft(post, data["events"], data["places"]) for post in drafts]
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "social-drafts.json").write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ready = [d for d in built if is_ready(d)]
    print(f"{len(built)} posts · {len(ready)} ready · {len(built) - len(ready)} need review")
    for draft in built[:10]:
        flags = []
        if draft["confidence"]["duplicateOf"]:
            flags.append(f"dup:{draft['confidence']['duplicateOf']['id']}")
        if not draft["confidence"]["eventLike"]:
            flags.append("announcement")
        if draft["confidence"]["outOfWindow"]:
            flags.append("out-of-window")
        print(f"  {draft['date'] or '??????????'} {draft['startTime'] or '--:--'} "
              f"{(draft['placeId'] or '--'):<4} {draft['title'][:48]}"
              + (f"  [{', '.join(flags)}]" if flags else ""))
    print(f"written {WORK / 'social-drafts.json'}")
    return 0


def cmd_check(args):
    data = load()
    problems, notes = validate(data)
    print(f"{len(data['events'])} events, {len(data['places'])} places — {len(problems)} problem(s), {len(notes)} note(s)")
    for problem in problems:
        print(f"  problem: {problem}")
    for note in notes:
        print(f"  note: {note}")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Keep events.json in step with the organiser (Apify retrieval).")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="run the Apify actors")
    fetch.add_argument("--limit", type=int, default=25, help="posts per profile (default 25)")
    fetch.set_defaults(func=cmd_fetch)

    diff = sub.add_parser("diff", help="compare the site with events.json")
    diff.set_defaults(func=cmd_diff)

    apply_cmd = sub.add_parser("apply", help="write safe fills")
    apply_cmd.add_argument("--insert-social", action="store_true", help="also add new events from social drafts")
    apply_cmd.set_defaults(func=cmd_apply)

    social_cmd = sub.add_parser("social", help="turn the fetched posts into drafts")
    social_cmd.set_defaults(func=cmd_social)

    check = sub.add_parser("check", help="validate events.json")
    check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
