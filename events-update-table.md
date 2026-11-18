# Events touched by the poster audit — final status

Scope: the legend ("Sự kiện/hoạt động") and activity names printed on the five posters. Poster dates/times are ignored
(confirmed wrong by the owner).

**Decision applied:** only `officialType` was changed. No events were inserted, no titles were changed.

Legend key: **Triển lãm** ^ chevron · **Pavilion** swoosh · **Tọa đàm** squiggle · **Workshop** triangle · **Trình diễn** quarter circle · **Hội chợ** person · **Event** donut.

## Applied — 25 `officialType` changes

| # | Event | Poster | Legend | Old `officialType` | New `officialType` |
|---|---|---|---|---|---|
| 1 | `e04` | qt #09 | Hội chợ | `Event` | `Fair` |
| 2 | `e53` | qt #03 | Hội chợ | `Event, Community` | `Fair` |
| 3 | `e07` | sd #06 | Trình diễn | `null` | `Performance` |
| 4 | `e12` | qt #12 | Triển lãm | `null` | `Exhibition` |
| 5 | `e14` | qt #08 | Triển lãm | `null` | `Exhibition` |
| 6 | `e16` | dinh #14 | Triển lãm | `null` | `Exhibition` |
| 7 | `e17` | dinh #17 | Triển lãm | `null` | `Exhibition` |
| 8 | `e18` | dinh #19 | Triển lãm | `null` | `Exhibition` |
| 9 | `e22` | dx #19 | Event | `null` | `Event` |
| 10 | `e23` | cv #14 | Triển lãm | `null` | `Exhibition` |
| 11 | `e32` | qt #13 | Triển lãm | `null` | `Exhibition` |
| 12 | `e48` | cv #05 | Triển lãm | `null` | `Exhibition` |
| 13 | `e54` | dx #17 | Event | `null` | `Event` |
| 14 | `e56` | qt #04 | Triển lãm | `null` | `Exhibition` |
| 15 | `e57` | qt #04 | Triển lãm | `null` | `Exhibition` |
| 16 | `e58` | qt #04 | Triển lãm | `null` | `Exhibition` |
| 17 | `e60` | dx #02 | Triển lãm | `null` | `Exhibition` |
| 18 | `e66` | cv #08 | Workshop | `null` | `Workshop` |
| 19 | `e69` | qt #01 | Trình diễn | `null` | `Performance` |
| 20 | `e80` | qt #06 | Trình diễn | `null` | `Performance` |
| 21 | `e81` | qt #01 | Trình diễn | `null` | `Performance` |
| 22 | `e88` | dx #18 | Event | `null` | `Tour` |
| 23 | `e110` | dinh #03 | Workshop | `null` | `Workshop` |
| 24 | `e123` | qt #05 | Trình diễn | `null` | `Performance` |
| 25 | `e132` | qt #07 | Trình diễn | `null` | `Performance` |

`Fair` is new to the file, so `TYPE_VI` in `tools/build-agent-files.mjs` now maps it to "Hội chợ" (the generated
`index.md` shows "Hội chợ" in the Loại column). `e88` uses `Tour`, matching the two tour records already in the file.

## Dropped — 9 inserts

No events were inserted. Checked against the official sitemap (`/sitemap.xml`, 118 event-like URLs): none of these
activity names has its own page, and the ninth is the official page of an existing record.

| Poster | Activity | Why dropped |
|---|---|---|
| cv #09 | Trao đổi "Nhịp điệu đô thị và Kiến trúc sinh thái" | no official page |
| qt #02 | Tour Nghệ thuật "Mạch sống vô hình" | no official page (only the exhibition and "Gặp nghệ sĩ") |
| qt #04 / dinh #20 | Trò chuyện "Con đường sơn mài Việt Nhật" | no official page |
| dinh #07 | Không gian kể chuyện Đình Kim Ngân mùa 2: "Dòng chảy bách nghệ" | no official page |
| dinh #12 | Trải nghiệm sản phẩm dược và thủ công gắn với Phố nghề Lãn Ông | no official page |
| dinh #16 | Không gian sáng tạo nghệ thuật biểu diễn truyền thống trong đời sống đương đại | no official page |
| dinh #18 | Trưng bày sản phẩm sơn mài Hạ Thái | no official page |
| dx #06 | Trưng bày ghế thiết kế HANOI SEAT N' READ 2026 | no official page |
| dx #16 | Lớp thực hành thử nghiệm âm thanh | **is** `e91` — its `officialUrl` is `/workshop/lop-thuc-hanh-thu-nghiem-am-thanh-390747.html`, so an insert would duplicate the record |

## Dropped — title changes

No titles were changed. The official URL slugs also contradict several poster wordings, which supports leaving the
current titles alone:

| Event | Current title | Poster wording | Official slug evidence |
|---|---|---|---|
| `e53` | Hội chợ "Nghề Nghệ" | Hội chợ Sáng tạo: Nghệ & Nghề | `hoi-cho-nghe-nghe` — matches current |
| `e70` | Triển lãm "Vén Lớp Hoạ Điệp" | Không gian sắp đặt và tương tác "Vén Lớp Hoạ Điệp" | `trien-lam-ven-lop-hoa-diep` — matches current |
| `e15` | Trưng bày "Chạm di sản - Sáng tạo cùng sơn mài" | Trưng bày "Đôi lời từ sơn mài Đường Lâm" | `trung-bay-cham-di-san-sang-tao-cung-son-mai` — matches current |
| `e05` | Pavilion Hồ Gương \| UNESCO & SOVICO vì sự phát triển bền vững | Pavilion "Hồ Gương" | `pavilion-ho-guong-unesco-sovico-vi-su-phat-trien-ben-vung` — the pipe is in the official title; the build escapes it in tables |
| `e19` | Trưng bày làng nghề Sơn Đồng | … Sơn Đồng, văn hóa Trà Việt và Việt phục | slug has the longer form, but the owner asked for no title edits |
| `e68` | Trình diễn "Âm nhạc xứ Mường" | Trình diễn "Âm vang xứ Mường" | slug has `am-vang-xu-muong`, but the owner asked for no title edits |
| `e91` | Lớp thực hành "Lắng nghe sâu" | Lớp thực hành thử nghiệm âm thanh | slug is `lop-thuc-hanh-thu-nghiem-am-thanh`, but the owner asked for no title edits |

## Dropped — sub-activity modelling

`e25` (2 workshops), `e61` (22 artworks) and `e73` (4 sessions) were left as they are; their sub-activities stay inside
`officialDetail` and `slots`.
