# Poster legend vs `events.json` — what changed, what did not

Scope: the legend ("Sự kiện/hoạt động") and the activity names printed on the five posters.
Poster dates and times are treated as unreliable (confirmed wrong by the owner), so they were not used as evidence.

**Applied:** 25 `officialType` corrections (plus the new `Fair` label).
**Not applied, by owner decision:** no inserted events, no title changes, no sub-activity modelling.

See the per-event table in [`events-update-table.md`](events-update-table.md).

## Why the legend needed work

The posters use seven activity types. `events.json` had a value for six of them:

| Poster legend | `officialType` | Before | After |
|---|---|---|---|
| Triển lãm | `Exhibition` | 29 events | 41 events |
| Pavilion | `Pavilion` | 4 | 4 |
| Tọa đàm | `Talk` | 8 | 8 |
| Workshop | `Workshop` | 21 | 23 |
| Trình diễn | `Performance` | 20 | 26 |
| Hội chợ | **absent** | 0 | **2 (`Fair`)** |
| Event | `Event` | 10 | 11 |

So the gap was `Hội chợ`, plus 23 poster-matched events that carried no type at all. The two `Hội chợ` records were
typed `Event`/`Event, Community`; they now read `Fair`.

Because `Fair` is a new value, `TYPE_VI` in [`tools/build-agent-files.mjs`](tools/build-agent-files.mjs) gained
`Fair: "Hội chợ"` so the generated `index.md` prints "Hội chợ" instead of the raw English label.

## What remains untyped

25 events still have `officialType: null`. None of them appear on these five posters, so the posters give no evidence
for their type; they need the official site or manual curation.

## Poster activities with no record

Kept out of `events.json` on purpose. Eight are not on the official site at all, and the ninth is an existing record:

| Poster | Activity | Note |
|---|---|---|
| cv #09 | Trao đổi "Nhịp điệu đô thị và Kiến trúc sinh thái" | no official page in `/sitemap.xml` |
| qt #02 | Tour Nghệ thuật "Mạch sống vô hình" | only the exhibition (`e59`) and "Gặp nghệ sĩ" (`e78`) exist |
| qt #04, dinh #20 | Trò chuyện "Con đường sơn mài Việt Nhật" | no official page |
| dinh #07 | "Dòng chảy bách nghệ" (Đình Kim Ngân mùa 2) | no official page |
| dinh #12 | Trải nghiệm sản phẩm dược và thủ công gắn với Phố nghề Lãn Ông | no official page |
| dinh #16 | Không gian sáng tạo nghệ thuật biểu diễn truyền thống trong đời sống đương đại | no official page |
| dinh #18 | Trưng bày sản phẩm sơn mài Hạ Thái | no official page |
| dx #06 | Trưng bày ghế thiết kế HANOI SEAT N' READ 2026 | no official page |
| dx #16 | Lớp thực hành thử nghiệm âm thanh | is `e91` — same `officialUrl`, so inserting would duplicate it |

If any of these should become a record later, resolve the date from the organiser first; the poster dates are known to
be wrong.

## Verification

```sh
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev   # parses events.json, reports the counts
```

It runs clean after the change. `events.json` still has 154 events and 59 places, and the only modified field across
the file is `officialType`.
