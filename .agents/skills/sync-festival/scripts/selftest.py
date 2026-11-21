#!/usr/bin/env python3
"""Offline tests for the sync helpers. No network, no fixture files on disk.

    python3 selftest.py            # quiet
    python3 selftest.py -v         # verbose
"""

import json
import sys
import unittest
from pathlib import Path

import social
import apify
from config import EVENTS
from events_model import load, new_event, validate, within_festival
from extract import (fold, html_to_text, in_window, parse_dates, parse_times, prose_facts,
                     same_text, schedule_claim, vn_parts)
from match import best_event, best_place, coverage, find_duplicate, genre_tag, named_event, slug_of
from enrich import apply_registrations, form_links, registration_proposals

sys.path.insert(0, str(Path(__file__).parent))
import schedule  # noqa: E402
import sync_festival as cli  # noqa: E402


class Helpers(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(fold("Triển lãm"), "trien lam")
        self.assertEqual(fold("Đình"), "dinh")
        self.assertEqual(fold("  Hội   chợ  "), "hoi cho")
        self.assertEqual(fold("A|B"), "a b")
        self.assertEqual(fold("“Nghề Nghệ”"), "nghe nghe")

    def test_vn_parts(self):
        self.assertEqual(vn_parts("2026-11-28T12:00:00"), {"date": "2026-11-28", "time": "19:00"})
        self.assertEqual(vn_parts("2026-11-13T17:00:00"), {"date": "2026-11-14", "time": "00:00"})
        self.assertIsNone(vn_parts(None))
        self.assertIsNone(vn_parts("nonsense"))

    def test_html(self):
        self.assertEqual(html_to_text("<p>a</p><p>b</p>"), "a\nb")
        self.assertEqual(html_to_text("a<br>b"), "a\nb")
        self.assertEqual(html_to_text("<script>x</script>keep"), "keep")
        self.assertEqual(html_to_text("<ul><li>one</li></ul>"), "- one")
        self.assertEqual(html_to_text("A&nbsp;B &amp; C &#8211; D"), "A B & C – D")
        self.assertEqual(html_to_text(None), "")

    def test_same_text(self):
        self.assertTrue(same_text("(English Below) \nPavilion", "(English Below)\nPavilion"))
        self.assertTrue(same_text("a  b", "a b"))
        self.assertFalse(same_text("Hội chợ", "Hội chợ!"))
        self.assertTrue(same_text(None, ""))

    def test_times(self):
        self.assertEqual(parse_times("09:00 - 19:00"), ["09:00–19:00"])
        self.assertEqual(parse_times("14h00 – 16h30 và 17:00-18:00"), ["14:00–16:30", "17:00–18:00"])
        self.assertEqual(parse_times("no times"), [])

    def test_dates(self):
        self.assertEqual(parse_dates("ngày 20/11"), ["2026-11-20"])
        self.assertEqual(parse_dates("từ ngày 13/11 đến 28/11/2026"), ["2026-11-13", "2026-11-28"])
        self.assertEqual(parse_dates("14–15/11"), ["2026-11-14", "2026-11-15"])
        self.assertEqual(parse_dates("31/02/2026"), [])

    def test_prose(self):
        facts = prose_facts("Thời gian: 19:30 - 21:30 ngày 28/11/2026\nĐịa điểm: Chợ Đồng Xuân")
        self.assertEqual(facts["time"], "19:30 - 21:30 ngày 28/11/2026")
        self.assertEqual(facts["place"], "Chợ Đồng Xuân")
        self.assertEqual(facts["times"], ["19:30–21:30"])
        self.assertEqual(facts["dates"], ["2026-11-28"])

    def test_window(self):
        self.assertTrue(in_window("2026-11-13"))
        self.assertTrue(in_window("2026-11-20", "2026-12-13"))
        self.assertFalse(in_window("2026-11-12"))
        self.assertFalse(in_window("2024-11-13"))

    def test_schedule_claim_reads_only_the_labelled_line(self):
        text = ("Lễ hội diễn ra từ 13/11 đến 28/11/2026.\n"
                "Thời gian: 09h00 – 11h00, Chủ nhật, ngày 22/11/2026\n"
                "Địa điểm: 47 Hàng Dầu")
        claim = schedule_claim(text)
        self.assertEqual(claim["times"], ["09:00–11:00"])
        self.assertEqual(claim["dates"], ["2026-11-22"])
        self.assertFalse(claim["ambiguous"])

    def test_schedule_claim_without_a_label_uses_the_sentence(self):
        claim = schedule_claim('Trình diễn "Sắc mưa" diễn ra lúc 15:00 - 16:00 ngày 14/11/2026 tại Hà Nội.')
        self.assertEqual(claim["times"], ["15:00–16:00"])
        self.assertEqual(claim["dates"], ["2026-11-14"])

    def test_schedule_claim_flags_two_different_sessions(self):
        text = ("Trình diễn A\nThời gian: 15:00 - 16:00 ngày 14/11/2026\n"
                "Trình diễn B\nThời gian: 20:00 - 21:00 ngày 15/11/2026")
        self.assertTrue(schedule_claim(text)["ambiguous"])
        bilingual = "Thời gian: 09:00 - 11:00 ngày 22/11/2026\nTime: 9:00 - 11:00, 22 November 2026"
        self.assertFalse(schedule_claim(bilingual)["ambiguous"])


class Matching(unittest.TestCase):
    def setUp(self):
        self.data = load()
        self.places = self.data["places"]
        self.events = self.data["events"]

    def test_coverage(self):
        self.assertEqual(coverage("a b c", "a b"), 1.0)
        self.assertEqual(coverage("a b", "a b c"), 2 / 3)

    def test_venue(self):
        self.assertEqual(best_place(self.places, "Sân mái chợ Đồng Xuân")[0]["id"], "p60")
        self.assertEqual(best_place(self.places, "Chợ Đồng Xuân")[0]["id"], "p01")
        self.assertIsNone(best_place(self.places, "Atlantis"))
        self.assertIsNone(best_place(self.places, ""))

    def test_duplicate(self):
        found = find_duplicate('Trình diễn "Sắc mưa" lúc 15:00 ngày 14/11', self.events)
        self.assertEqual(found["id"], "e07")
        self.assertIsNone(find_duplicate("HFCD26 OFFICAL AGENDA gần 150 hoạt động", self.events))

    def test_slug(self):
        self.assertEqual(slug_of({"officialUrl": "https://lehoithietkesangtao.vn/su-kien/a-b.html"}), "a-b")
        self.assertIsNone(slug_of({}))

    def test_genre(self):
        self.assertEqual(genre_tag("Performance, Event"), "trình diễn")
        self.assertEqual(genre_tag(""), "")


class Validation(unittest.TestCase):
    def test_real_file(self):
        problems, _ = validate(load())
        self.assertEqual(problems, [])

    def test_broken(self):
        data = load()
        broken = json.loads(json.dumps(data))
        broken["events"][0]["placeId"] = "nope"
        broken["events"][0]["startTime"] = "9:00"
        broken["events"][0]["dateEnd"] = "2000-01-01"
        broken["events"][1]["id"] = broken["events"][0]["id"]
        broken["events"][2]["number"] = 99
        problems = "\n".join(validate(broken)[0])
        for expected in ("unknown placeId", "bad startTime", "dateEnd before date", "duplicate id", "numbering"):
            self.assertIn(expected, problems)


class Diff(unittest.TestCase):
    def test_buckets(self):
        data = {
            "clusters": load()["clusters"],
            "places": [
                {"id": "pA", "name": "Chợ Đồng Xuân", "address": "phố Đồng Xuân", "clusterId": "g2"},
                {"id": "pB", "name": "Sân mái chợ Đồng Xuân", "address": "phố Đồng Xuân", "clusterId": "g2"},
            ],
            "events": [
                {"id": "e001", "number": 1, "date": "2026-11-14", "dateEnd": "2026-11-14",
                 "startTime": "09:00", "endTime": "17:00", "title": "A", "placeId": "pB",
                 "clusterId": "g2", "officialType": "Fair",
                 "officialUrl": "https://lehoithietkesangtao.vn/su-kien/a.html"},
                {"id": "e002", "number": 2, "date": "2026-11-15", "dateEnd": "2026-11-15",
                 "startTime": "09:00", "endTime": "10:00", "title": "B", "placeId": "pA", "clusterId": "g2"},
                {"id": "e003", "number": 3, "date": "2026-11-16", "dateEnd": "2026-11-16",
                 "startTime": "09:00", "endTime": "10:00", "title": "C", "placeId": "pA", "clusterId": "g2",
                 "officialUrl": "https://lehoithietkesangtao.vn/su-kien/gone.html"},
            ],
        }
        remote = [
            {"slug": "a", "title": "A", "eventType": "Exhibition",
             "startAt": "2026-11-14T02:00:00", "endAt": "2026-11-14T10:00:00", "venueName": "Sân mái chợ Đồng Xuân"},
            {"slug": "b", "title": "B", "eventType": "Workshop",
             "startAt": "2026-11-15T02:00:00", "endAt": "2026-11-15T03:00:00", "venueName": "Chợ Đồng Xuân"},
            {"slug": "d", "title": "D", "eventType": "Talk",
             "startAt": "2026-11-20T02:00:00", "endAt": "2026-11-20T03:00:00", "venueName": "Chợ Đồng Xuân"},
        ]
        diff = cli.compare(data, remote)
        row_a = next(row for row in diff["rows"] if row.get("id") == "e001")
        row_b = next(row for row in diff["rows"] if row.get("id") == "e002")

        type_change = next(c for c in row_a["changes"] if c["field"] == "officialType")
        self.assertEqual((type_change["was"], type_change["site"]), ("Fair", "Exhibition"))
        self.assertTrue(any(c["field"] == "officialVenue" and c["empty"] for c in row_b["changes"]))
        self.assertEqual([row["slug"] for row in diff["rows"] if row["kind"] == "new"], ["d"])
        self.assertEqual([e["id"] for e in diff["missing"]], ["e003"])

    def test_whitespace_title_is_not_drift(self):
        data = {"clusters": load()["clusters"], "places": load()["places"][:1], "events": [{
            "id": "e001", "number": 1, "date": "2026-11-14", "dateEnd": "2026-11-14",
            "startTime": "09:00", "endTime": "10:00", "title": 'Trình  tương tác "x"',
            "placeId": load()["places"][0]["id"], "clusterId": "g2", "officialType": "Talk",
            "officialVenue": load()["places"][0]["name"],
            "officialUrl": "https://lehoithietkesangtao.vn/su-kien/a.html"}]}
        remote = [{"slug": "a", "title": 'Trình tương tác "x"', "eventType": "Talk",
                   "startAt": "2026-11-14T02:00:00", "endAt": "2026-11-14T03:00:00",
                   "venueName": load()["places"][0]["name"]}]
        diff = cli.compare(data, remote)
        self.assertEqual(diff["rows"][0]["kind"], "same")

    def test_curated_schedule_is_not_drift(self):
        place = load()["places"][0]
        data = {"clusters": load()["clusters"], "places": load()["places"], "events": [{
            "id": "e001", "number": 1, "date": "2026-11-14", "dateEnd": "2026-11-14",
            "startTime": "09:00", "endTime": "17:00", "title": "Y", "placeId": place["id"],
            "clusterId": place["clusterId"], "officialType": "Exhibition",
            "officialVenue": place["name"], "officialUrl": "https://lehoithietkesangtao.vn/su-kien/y.html",
            "slots": [{"date": "2026-11-14", "start": "10:00", "end": "12:00"}]}]}
        remote = [{"slug": "y", "title": "Y", "eventType": "Exhibition",
                   "startAt": "2026-11-14T20:00:00", "endAt": "2026-11-14T21:00:00",
                   "venueName": place["name"]}]
        diff = cli.compare(data, remote)
        self.assertEqual(diff["rows"][0]["kind"], "same")
        self.assertTrue(diff["rows"][0]["dates"][0]["curated"])


class Drafts(unittest.TestCase):
    def setUp(self):
        data = load()
        self.events, self.places = data["events"], data["places"]

    def post(self, text, posted="2026-11-12"):
        return {"text": text, "source": "https://example.test/p/1", "posted_at": posted, "network": "facebook"}

    def test_schedule_change(self):
        draft = social.build_draft(self.post('Trình diễn "Sắc mưa" diễn ra lúc 15:00 - 16:00 ngày 14/11/2026\ntại Nhà hát Tuổi Trẻ.'), self.events, self.places)
        self.assertEqual(draft["title"], 'Trình diễn "Sắc mưa"')
        self.assertEqual([draft["date"], draft["startTime"], draft["endTime"]], ["2026-11-14", "15:00", "16:00"])
        self.assertEqual(draft["placeId"], "p16")
        self.assertEqual(draft["confidence"]["duplicateOf"]["id"], "e07")
        self.assertTrue(draft["confidence"]["eventLike"])

    def test_prose_caption(self):
        draft = social.build_draft(self.post("Diễn ra từ 09:00 - 19:00 hằng ngày, từ 13 - 28/11/2026, "
                                             "Pavilion “Hồ Gương” đã trở thành điểm dừng chân của nhiều người."), self.events, self.places)
        self.assertEqual(draft["title"], "Pavilion “Hồ Gương”")
        self.assertEqual([draft["date"], draft["dateEnd"]], ["2026-11-13", "2026-11-28"])
        self.assertEqual(draft["confidence"]["dateSource"], "prose")

    def test_announcement(self):
        draft = social.build_draft(self.post("HFCD26 OFFICAL AGENDA\n\n16 ngày Lễ hội sắp tới, gần 150 hoạt động sáng tạo đang chờ bạn khám phá."), self.events, self.places)
        self.assertFalse(draft["confidence"]["eventLike"])
        self.assertEqual(draft["confidence"]["dateSource"], "post")
        self.assertEqual(draft["date"], "2026-11-12")

    def test_post_shapes(self):
        collected = {
            "instagram": {"items": [{"shortCode": "ABC", "caption": "Triển lãm \"X\" 09:00 - 17:00 ngày 20/11/2026 tại Bảo tàng Hà Nội", "timestamp": "2026-11-19T03:00:00.000Z", "url": "https://www.instagram.com/p/ABC/"}]},
            "facebook": {"items": [{"text": "Nội dung", "time": "2026-11-18T13:55:47.000Z", "url": "https://facebook.com/x"}]},
            "threads": {"items": [{"username": "lehoithietkesangtaohanoi", "latestPosts": [{"caption": {"text": "Bài Threads"}, "code": "XYZ", "taken_at": 1794543180}]}]},
        }
        posts = social.read_posts(collected)
        self.assertEqual([p["network"] for p in posts], ["instagram", "facebook", "threads"])
        self.assertEqual(posts[0]["posted_at"], "2026-11-19")
        self.assertEqual(posts[1]["posted_at"], "2026-11-18")
        self.assertIn("/post/XYZ", posts[2]["source"])
        self.assertEqual(social.read_posts({}), [])


class Apply(unittest.TestCase):
    def test_safe_fills_only(self):
        data = load()
        place = data["places"][0]
        event = {"id": "e001", "number": 1, "date": "2026-11-14", "dateEnd": "2026-11-14",
                 "startTime": "09:00", "endTime": "10:00", "title": "A", "placeId": place["id"],
                 "clusterId": place["clusterId"], "officialType": "Fair", "officialUrl": "u"}
        data = {"clusters": data["clusters"], "places": data["places"], "events": [event]}
        rows = [{"kind": "changed", "id": "e001", "changes": [
            {"field": "officialType", "was": "Fair", "site": "Event", "empty": False},
            {"field": "officialVenue", "was": None, "site": place["name"], "empty": True},
            {"field": "title", "was": "A", "site": "A2", "empty": False},
        ]}]
        filled, kept = cli.apply_safe(data, rows)
        self.assertEqual(event["officialType"], "Fair")
        self.assertEqual(event["officialVenue"], place["name"])
        self.assertEqual(event["title"], "A")
        self.assertEqual([field for _, field in filled], ["officialVenue"])
        self.assertEqual([field for _, field, _, _ in kept], ["officialType"])

    def test_insert_social(self):
        data = load()
        before = len(data["events"])
        drafts = [{
            "title": "Sự kiện Thử Nghiệm", "date": "2026-11-20", "dateEnd": "2026-11-20",
            "startTime": "19:00", "endTime": "21:00", "place": "Chợ Đồng Xuân", "placeId": "p01",
            "type": "Performance", "detail": "x", "source": "https://example.test/p/1",
            "confidence": {"eventLike": True, "duplicateOf": None, "outOfWindow": False},
        }, {
            "title": "Ngoài lễ hội", "date": "2026-08-01", "startTime": "09:00", "endTime": "10:00",
            "place": "Chợ Đồng Xuân", "placeId": "p01",
            "confidence": {"eventLike": True, "duplicateOf": None, "outOfWindow": True},
        }]
        inserted, skipped = cli.apply_social(data, drafts)
        self.assertEqual(len(data["events"]), before + 1)
        self.assertEqual(inserted[0][1], "Sự kiện Thử Nghiệm")
        self.assertEqual(len(skipped), 1)
        self.assertEqual(data["events"][-1]["placeId"], "p01")
        self.assertEqual(data["events"][-1]["number"], before + 1)


class SocialSchedule(unittest.TestCase):
    def setUp(self):
        # Synthetic events: the real file changes as the sync writes overrides.
        self.events = [
            {"id": "e001", "title": 'Trao đổi chuyên môn "Trình diễn thơ - Vượt qua đường biên chữ"',
             "date": "2026-11-22", "dateEnd": "2026-11-22", "startTime": "09:00", "endTime": "12:00"},
            {"id": "e002", "title": 'Pavilion "Hồ Gương"',
             "date": "2026-11-13", "dateEnd": "2026-11-28", "startTime": "09:00", "endTime": "19:00"},
            {"id": "e003", "title": "Chuỗi Culture Show: Xẩm, Ca trù",
             "date": "2026-11-15", "dateEnd": "2026-11-28", "startTime": "20:00", "endTime": "21:00",
             "days": ["2026-11-15", "2026-11-21"]},
            {"id": "e004", "title": 'Trao đổi chuyên môn "Di sản tự sinh"',
             "date": "2026-11-20", "dateEnd": "2026-11-20", "startTime": "09:00", "endTime": "11:00"},
        ]

    def data(self):
        return {"events": json.loads(json.dumps(self.events))}

    def post(self, text, posted="2026-11-20"):
        return {"text": text, "source": "https://example.test/p/1", "posted_at": posted, "network": "facebook"}

    def test_named_event_skips_a_generic_heading(self):
        text = 'Trao đổi chuyên môn "Trình diễn thơ - Vượt qua đường biên chữ" - Thời gian: 09h00 – 11h00'
        self.assertEqual(named_event(text, self.events)["id"], "e001")
        self.assertIsNone(named_event("Trao đổi chuyên môn", self.events))
        self.assertIsNone(named_event("HFCD26 OFFICAL AGENDA gần 150 hoạt động", self.events))

    def test_social_wins_the_schedule(self):
        text = ("📍 Trao đổi chuyên môn “Trình diễn thơ – Vượt qua đường biên chữ”\n"
                "Thời gian: 09h00 – 11h00, Chủ nhật, ngày 22/11/2026\n"
                "Địa điểm: Hội trường Sở Văn hóa, Thể thao và Du lịch Hà Nội, 47 Hàng Dầu")
        proposals = schedule.schedule_proposals([self.post(text)], self.events)
        self.assertEqual([p["eventId"] for p in proposals], ["e001"])

        data = self.data()
        applied, review = schedule.apply_schedules(data, proposals)
        event = data["events"][0]
        self.assertEqual([applied_event["id"] for applied_event, _, _ in applied], ["e001"])
        self.assertEqual(review, [])
        self.assertEqual([event["startTime"], event["endTime"]], ["09:00", "11:00"])
        self.assertEqual(event["date"], "2026-11-22")

    def test_a_single_date_in_a_longer_run_is_not_a_reschedule(self):
        text = "Pavilion “Hồ Gương”\nThời gian: 10:00 - 18:00 ngày 20/11/2026"
        data = self.data()
        proposals = schedule.schedule_proposals([self.post(text)], self.events)
        applied, review = schedule.apply_schedules(data, proposals)
        self.assertEqual(applied, [])
        self.assertEqual([event["id"] for event, _, _ in review], ["e002"])
        self.assertEqual(data["events"][1]["startTime"], "09:00")

    def test_curated_per_day_schedule_is_left_alone(self):
        text = "Chuỗi Culture Show: Xẩm, Ca trù\nThời gian: 20:00 - 21:30 ngày 27/11/2026"
        self.assertEqual(schedule.schedule_proposals([self.post(text)], self.events), [])

    def test_newest_post_wins(self):
        older = self.post('Trao đổi chuyên môn "Trình diễn thơ" - Thời gian: 09:00 - 10:00 ngày 22/11/2026',
                          posted="2026-11-18")
        newer = self.post('Trao đổi chuyên môn "Trình diễn thơ" - Thời gian: 09:00 - 11:00 ngày 22/11/2026',
                          posted="2026-11-20")
        proposals = schedule.schedule_proposals([newer, older], self.events)
        self.assertEqual(proposals[0]["endTime"], "11:00")

    def test_real_file_still_matches_the_poetry_talk(self):
        events = load()["events"]
        text = 'Trao đổi chuyên môn "Trình diễn thơ - Vượt qua đường biên chữ"'
        self.assertEqual(named_event(text, events)["id"], "e130")


class Enrichment(unittest.TestCase):
    def setUp(self):
        self.data = load()
        self.events = self.data["events"]

    def test_form_links(self):
        text = "Đăng ký tại https://forms.gle/SMmuryqHy43cCFCRA và https://example.com/x. Dự phòng https://docs.google.com/forms/d/e/abc/viewform,"
        links = form_links(text)
        self.assertEqual(links[0], "https://forms.gle/SMmuryqHy43cCFCRA")
        self.assertIn("https://docs.google.com/forms/d/e/abc/viewform", links)
        self.assertEqual(len(links), 2, "trailing comma stripped, non-form host ignored")
        self.assertEqual(form_links("không có link"), [])

    def test_best_event_requires_a_name(self):
        self.assertEqual(best_event('Mời đăng ký Trao đổi chuyên môn "Khao Khát Nguyên Bản" diễn ra 18/11', self.events)["id"], "e97")
        self.assertEqual(best_event('Tour di sản "Chuyện Đình trong Phố" ba tuyến', self.events)["id"], "e34")
        self.assertIsNone(best_event("Cuộc thi thời trang MARKET TO MODE", self.events))

    def test_registration_proposals_and_apply(self):
        posts = [
            {"text": 'Mời đăng ký "Khao Khát Nguyên Bản" tại https://forms.gle/OLD', "source": "p1", "posted_at": "2026-11-10", "network": "facebook"},
            {"text": 'Mời đăng ký "Khao Khát Nguyên Bản" tại https://forms.gle/NEW', "source": "p2", "posted_at": "2026-11-17", "network": "facebook"},
        ]
        proposals = registration_proposals(posts, self.events)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["url"], "https://forms.gle/NEW", "newest post wins")

        data = {"events": [{"id": "e97", "title": self.events[96]["title"] if False else "x"}]}
        data["events"][0]["id"] = "e97"
        filled, kept = apply_registrations(data, proposals)
        self.assertEqual(filled, [("e97", "https://forms.gle/NEW")])
        self.assertEqual(kept, [])
        filled, kept = apply_registrations(data, proposals)
        self.assertEqual(filled, [])
        self.assertEqual(kept, [])


class Report(unittest.TestCase):
    def test_two_sections_with_event_first_columns(self):
        data = load()
        event = data["events"][0]
        ledger = {"appliedAt": "2026-11-21T13:02", "changes": [{
            "eventId": event["id"], "title": event["title"],
            "change": "end 17:00 → 17:30", "source": "facebook · 2026-11-20"}]}
        text = cli.render(data, [{"kind": "same"}], [], [], None, None, ledger)
        self.assertIn("## Changes made", text)
        self.assertIn("## Needs your review", text)
        self.assertLess(text.index("## Changes made"), text.index("## Needs your review"))
        self.assertEqual(text.count("| Event | id | Change | Source |"), 1)
        self.assertIn("| Event | id | Difference | Remote source |", text)
        self.assertIn(f"| {event['title']} | `{event['id']}` | end 17:00 → 17:30 | facebook · 2026-11-20 |", text)

    def test_a_post_row_links_the_post(self):
        data = {"clusters": {}, "places": [], "events": [{
            "id": "e001", "title": "Pavilion Hồ Gương", "date": "2026-11-13",
            "dateEnd": "2026-11-28", "startTime": "09:00", "endTime": "19:00"}]}
        proposals = [{
            "eventId": "e001", "title": "Pavilion Hồ Gương", "dates": ["2026-11-20"],
            "startTime": "10:00", "endTime": "18:00", "network": "facebook",
            "postedAt": "2026-11-20", "postUrl": "https://example.test/post"}]
        text = cli.render(data, [{"kind": "same"}], [], [], None, proposals, None)
        self.assertIn("| Event | id | Difference | Remote source |", text)
        self.assertIn("start — ours 09:00", text)
        self.assertIn("[facebook post, 2026-11-20](https://example.test/post)", text)
        self.assertIn("session on 2026-11-20 inside our run", text)
        self.assertNotIn("date — ours", text, "a session date is not a reschedule")

    def test_without_a_ledger(self):
        text = cli.render(load(), [{"kind": "same"}], [], [], None, None, None)
        self.assertIn("Nothing written yet", text)
        self.assertIn("| — | — | nothing to decide | — |", text)
        self.assertIn("| Event | id | Difference | Remote source |", text)


class Apify(unittest.TestCase):
    def test_inputs(self):
        payload = apify.inputs(10)
        self.assertEqual(payload["instagram"]["resultsLimit"], 10)
        self.assertEqual(payload["facebook"]["resultsLimit"], 10)
        self.assertIn("lehoithietkesangtaohanoi", payload["threads"]["usernames"])
        self.assertTrue(payload["instagram"]["directUrls"][0].startswith("https://www.instagram.com/"))

    def test_missing_token(self):
        import os
        previous = os.environ.pop("APIFY_TOKEN", None)
        try:
            with self.assertRaises(apify.ApifyError):
                apify.run_actor("apify/instagram-scraper", {})
        finally:
            if previous:
                os.environ["APIFY_TOKEN"] = previous


if __name__ == "__main__":
    unittest.main()
