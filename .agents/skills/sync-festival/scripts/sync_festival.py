#!/usr/bin/env python3
"""Keep src/events.json in step with the organiser.

Retrieval is Apify only: three actors cover the Facebook page, the Instagram
profile and the Threads profile. The official site is read over its public JSON
API. Nothing here scrapes HTML pages or drives a browser.

    python3 sync_festival.py fetch            # Apify → tmp/sync/social.json
    python3 sync_festival.py diff             # site API + social → tmp/sync/report.md
    python3 sync_festival.py enrich --write   # registration links from posts
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
from datetime import datetime

import apify
import enrich
import schedule
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


def social_schedule(data, proposals):
    """Split the post claims into the ones a post may override and the ones to review."""
    events = {event["id"]: event for event in data["events"]}
    applied, review = [], []
    for proposal in proposals or []:
        event = events.get(proposal["eventId"])
        if not event:
            continue
        changes = schedule.schedule_changes(event, proposal)
        if not changes:
            continue
        if schedule.can_override(event, proposal):
            applied.append((event, proposal, changes))
        else:
            review.append((event, proposal, changes))
    return applied, review


FIELD_LABEL = {
    "startTime": "start", "endTime": "end", "date": "date", "dateEnd": "end date",
    "officialType": "type", "officialVenue": "venue", "officialVenueAddress": "address",
    "officialUrl": "official page",
}


def _label(field):
    return FIELD_LABEL.get(field, field)


def _source(label, url=None):
    return f"[{label}]({url})" if url else label


def _site(event):
    """The organiser's own page, named by domain and linked."""
    return _source("lehoithietkesangtao.vn",
                   event.get("officialUrl") or official_url(event.get("slug") or ""))


def render(data, rows, missing, unlinked, social_drafts=None, schedule_proposals=None, ledger=None):
    """Two sections: what `apply` wrote, and what a human has to decide."""
    lines = []
    add = lines.append
    changed = [row for row in rows if row["kind"] == "changed"]
    same = [row for row in rows if row["kind"] == "same"]
    new_in = [row for row in rows if row["kind"] == "new"
              and within_festival({"date": (row["start"] or {}).get("date", ""),
                                   "dateEnd": (row["end"] or {}).get("date")})]
    new_out = [row for row in rows if row["kind"] == "new" and row not in new_in]
    overrides, review = social_schedule(data, schedule_proposals)

    settled = {proposal["eventId"] for proposal in schedule_proposals or []}
    human = [row for row in changed if any(c["field"] == "title" for c in row["changes"])
             or any(not d.get("curated") for d in row["dates"])]
    explained = [row for row in human if row["id"] in settled]
    human = [row for row in human if row["id"] not in settled]
    others = [row for row in changed if row not in human and row["id"] not in settled]
    fills = [row for row in others if any(c.get("empty") for c in row["changes"])]
    kept = [row for row in others if row not in fills]
    curated = sum(1 for row in rows if any(d.get("curated") for d in row.get("dates", [])))
    notes = [row for row in rows if row.get("venueNote")]

    add(f"# Festival sync — {FESTIVAL_START} → {FESTIVAL_END}\n")
    add(f"{len(same)} unchanged · {len(changed)} differ from the official site · "
        f"{len(new_in)} new on the official site · {len(unlinked)} without an official page\n")

    add("## Changes made\n")
    written = (ledger or {}).get("changes") or []
    if written:
        add(f"`apply`, {ledger.get('appliedAt', '—')}\n")
        add("| Event | id | Change | Source |")
        add("|---|---|---|---|")
        for item in written:
            add(f"| {item['title']} | `{item['eventId']}` | {item['change']} | {item['source']} |")
    else:
        add("Nothing written yet — run `sync_festival.py apply`.")
    add("")

    add("## Needs your review\n")
    add("`Difference` is ours against the remote value, and names where the remote value came from.\n")
    add("| Event | id | Difference |")
    add("|---|---|---|")
    pending = 0
    for row in human:
        event = next((e for e in data["events"] if e["id"] == row["id"]), {})
        title = event.get("title") or row["id"]
        for change in row["changes"]:
            if change["field"] == "title":
                add(f"| {title} | `{row['id']}` | title differs: ours \"{change['was']}\", "
                    f"{_site(event)} says \"{change['site']}\" |")
                pending += 1
        for date in row["dates"]:
            if not date.get("curated"):
                add(f"| {title} | `{row['id']}` | {_label(date['field'])} differs: ours {date['was']}, "
                    f"{_site(event)} says {date['site']} |")
                pending += 1
    for event, proposal, changes in review:
        label = f"{proposal['network'] or 'post'} post, {proposal['postedAt'] or '—'}"
        source = _source(label, proposal.get("postUrl"))
        note = ""
        if not schedule.can_override(event, proposal):
            # The post names one session inside a longer run, not a reschedule.
            session = (proposal.get("dates") or [""])[0]
            changes = [change for change in changes if change["field"] in ("startTime", "endTime")]
            note = f", a session on {session} inside our run"
        for change in changes:
            add(f"| {event['title']} | `{event['id']}` | {_label(change['field'])} differs: "
                f"ours {change['was']}, {source} {change['social']}{note} |")
            pending += 1
    for row in new_in:
        start = row["start"] or {}
        when = f"{start.get('date', '—')} {start.get('time', '')}".strip()
        venue = row["item"].get("venueName")
        where = f" at {venue}" if venue else ""
        add(f"| {row['item']['title']} | `{row['slug']}` | not in events.json: "
            f"{_source('lehoithietkesangtao.vn', official_url(row['slug']))} has it starting {when}{where} |")
        pending += 1
    for event in missing:
        add(f"| {event['title']} | `{event['id']}` | we still list it: {_site(event)} dropped the "
            f"slug and the sitemap |")
        pending += 1
    if not pending:
        add("| — | — | nothing to decide |")
    add("")

    quiet = []
    if overrides:
        quiet.append(f"{len(overrides)} schedule override(s) waiting for `apply`")
    if fills:
        quiet.append(f"{len(fills)} event(s) with an empty organiser field")
    if kept:
        quiet.append(f"{len(kept)} curated official value(s) kept")
    if curated:
        quiet.append(f"{curated} curated per-day schedule(s) left alone")
    if explained:
        quiet.append(f"{len(explained)} official-site difference(s) already settled by a post")
    if notes:
        quiet.append(f"{len(notes)} venue labels differing from the pin")
    if new_out:
        quiet.append(f"{len(new_out)} new slug(s) outside the window")
    if social_drafts is not None:
        ready = [draft for draft in social_drafts if is_ready(draft)]
        dupes = sum(1 for draft in social_drafts if draft["confidence"]["duplicateOf"])
        announcements = sum(1 for draft in social_drafts if not draft["confidence"]["eventLike"])
        quiet.append(f"{len(social_drafts)} posts: {len(ready)} insertable, {dupes} about an existing event, "
                     f"{announcements} announcements")
    if quiet:
        add("Nothing to do: " + "; ".join(quiet) + ".")
    if unlinked:
        add("No official page, so unverifiable: " + ", ".join(event["id"] for event in unlinked) + ".")
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


def read_ledger():
    """What the last `apply` wrote, so `diff` can show it."""
    path = WORK / "applied.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_ledger(changes):
    WORK.mkdir(parents=True, exist_ok=True)
    payload = {
        "appliedAt": datetime.now().astimezone().isoformat(timespec="minutes"),
        "changes": changes,
    }
    (WORK / "applied.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    proposals = None
    if drafts:
        proposals = schedule.schedule_proposals(drafts, data["events"])
        drafts = [social.build_draft(post, data["events"], data["places"]) for post in drafts]

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "report.md").write_text(
        render(data, diff["rows"], diff["missing"], diff["unlinked"], drafts, proposals, read_ledger()),
        encoding="utf-8")
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
    applied_schedule, review_schedule = [], []
    posts = read_social() or []
    if not args.no_social:
        applied_schedule, review_schedule = schedule.apply_schedules(
            data, schedule.schedule_proposals(posts, data["events"]))
    if args.insert_social:
        drafts = [social.build_draft(post, data["events"], data["places"]) for post in posts]
        inserted, skipped = apply_social(data, drafts)
    save(data)

    written = []
    for event, proposal, changes in applied_schedule:
        posted = f"{proposal['network'] or 'post'} · {proposal['postedAt'] or '—'}"
        for change in changes:
            written.append({
                "eventId": event["id"],
                "title": event["title"],
                "change": f"{_label(change['field'])} {change['was']} → {change['social']}",
                "source": _source(posted, proposal.get("postUrl")),
            })
    events = {event["id"]: event for event in data["events"]}
    for event_id, field in filled:
        written.append({
            "eventId": event_id,
            "title": events[event_id]["title"],
            "change": f"{_label(field)} filled in",
            "source": "official site",
        })
    for event_id, title in inserted:
        written.append({
            "eventId": event_id,
            "title": title,
            "change": "added from a post",
            "source": "post",
        })
    if written:
        write_ledger(written)

    proposals = None if args.no_social else schedule.schedule_proposals(posts, data["events"])
    drafts = [social.build_draft(post, data["events"], data["places"]) for post in posts] if posts else None
    (WORK / "report.md").write_text(
        render(data, diff["rows"], diff["missing"], diff["unlinked"], drafts, proposals, read_ledger()),
        encoding="utf-8")

    print(f"filled {len(filled)} · kept curated {len(kept)} · social schedule {len(applied_schedule)} · "
          f"inserted {len(inserted)}")
    for event, proposal, changes in applied_schedule:
        detail = ", ".join(f"{_label(c['field'])} {c['was']}→{c['social']}" for c in changes)
        print(f"  social {event['id']}: {detail}")
    for event, proposal, changes in review_schedule[:10]:
        print(f"  review {event['id']}: a single session of a longer run, left alone")
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
    print(f"report {WORK / 'report.md'}")
    return 1 if problems else 0


def cmd_enrich(args):
    """Registration links (and other missing facts) from the fetched posts."""
    posts = read_social()
    if posts is None:
        print("no social.json yet — run `sync_festival.py fetch` first", file=sys.stderr)
        return 2
    data = load()
    proposals = enrich.registration_proposals(posts, data["events"])
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "enrich.json").write_text(json.dumps(proposals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    filled, kept = enrich.apply_registrations(data, proposals) if args.write else ([], [])
    print(f"registration links found: {len(proposals)}")
    for proposal in proposals[:12]:
        print(f"  {proposal['eventId']:<5} {proposal['title'][:42]:<42} {proposal['url'][:52]}")
    if args.write:
        save(data)
        print(f"filled {len(filled)} · kept {len(kept)}")
        for event_id, url in filled:
            print(f"  + {event_id} {url}")
        problems, _ = validate(data)
        print("validation clean" if not problems else f"validation: {len(problems)} problem(s)")
        return 1 if problems else 0
    print(f"written {WORK / 'enrich.json'} — rerun with --write to apply")
    return 0


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
    duplicates = sum(1 for d in built if d["confidence"]["duplicateOf"])
    announcements = sum(1 for d in built if not d["confidence"]["eventLike"])
    incomplete = len(built) - len(ready) - duplicates - announcements + sum(1 for d in built if d["confidence"]["duplicateOf"] and not d["confidence"]["eventLike"])
    print(f"{len(built)} posts · {len(ready)} insertable · {duplicates} about an existing event · "
          f"{announcements} announcements · {max(incomplete, 0)} incomplete")
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

    apply_cmd = sub.add_parser("apply", help="write safe fills and the social schedule overrides")
    apply_cmd.add_argument("--insert-social", action="store_true", help="also add new events from social drafts")
    apply_cmd.add_argument("--no-social", action="store_true", help="skip the schedule overrides from posts")
    apply_cmd.set_defaults(func=cmd_apply)

    enrich_cmd = sub.add_parser("enrich", help="registration links from social posts")
    enrich_cmd.add_argument("--write", action="store_true", help="write the links into events.json")
    enrich_cmd.set_defaults(func=cmd_enrich)

    social_cmd = sub.add_parser("social", help="turn the fetched posts into drafts")
    social_cmd.set_defaults(func=cmd_social)

    check = sub.add_parser("check", help="validate events.json")
    check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
