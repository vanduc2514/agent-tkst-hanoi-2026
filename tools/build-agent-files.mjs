#!/usr/bin/env node
// Derives agent-facing markdown from events.json.
// events.json stays the canonical source but is never published; index.md and
// llms.txt are the formats LLM agents actually consume. Pass --base to rewrite
// the agent-hint blocks in index.html to absolute URLs.
//
// Usage: node tools/build-agent-files.mjs [--base https://your-domain.vn]

import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const baseArgIndex = process.argv.indexOf("--base");
const base = baseArgIndex > -1 ? process.argv[baseArgIndex + 1].replace(/\/$/, "") : "";
const abs = (path) => (base ? `${base}/${path}` : `/${path}`);

const data = JSON.parse(await readFile(join(root, "events.json"), "utf8"));
const { festival, clusters, places, events, presets } = data;

const placeById = new Map(places.map((p) => [p.id, p]));
const clusterName = (id) => clusters[id]?.name ?? id;
const eventById = new Map(events.map((e) => [e.id, e]));

const formatDate = (start, end) =>
  end && end !== start ? `${start} → ${end}` : start;
const formatDays = (e) =>
  e.days && e.days.length ? e.days.join(", ") : formatDate(e.date, e.dateEnd);
const oneLine = (text) => String(text ?? "").replace(/\s+/g, " ").trim();
const cell = (text) => oneLine(text).replace(/\|/g, "\\|");
const venue = (e) => placeById.get(e.placeId)?.name || e.officialVenue || e.placeId;
const address = (e) => placeById.get(e.placeId)?.address || "";
const hours = (e) =>
  e.startTime === "00:00" && e.endTime === "00:00"
    ? "Cả ngày"
    : `${e.startTime}–${e.endTime}`;

const TYPE_VI = {
  Exhibition: "Triển lãm",
  Pavilion: "Pavilion",
  Event: "Sự kiện",
  Workshop: "Workshop",
  Performance: "Trình diễn",
  Talk: "Tọa đàm",
  Community: "Cộng đồng",
  Tour: "Tour",
  "": "Chưa phân loại",
  "triển lãm": "Triển lãm",
  "trình diễn": "Trình diễn",
  workshop: "Workshop",
  "tọa đàm": "Tọa đàm",
  "sự kiện": "Sự kiện",
  "cộng đồng": "Cộng đồng",
  "trải nghiệm": "Trải nghiệm",
  pavilion: "Pavilion",
  tour: "Tour",
  "chiếu phim": "Chiếu phim",
  "trưng bày": "Trưng bày",
  "sắp đặt": "Sắp đặt",
  "lễ": "Lễ hội",
  "trao đổi": "Trao đổi",
};
const TYPE_VI_BY_LOWER = new Map();
for (const [key, value] of Object.entries(TYPE_VI)) {
  TYPE_VI_BY_LOWER.set(key.toLowerCase(), value);
  TYPE_VI_BY_LOWER.set(value.toLowerCase(), value);
}

// tags mix art-form words with venue names; only art forms carry genre signal
const placeNames = new Set(places.map((p) => p.name));
const isVenueTag = (tag) => placeNames.has(tag) || /\d/.test(tag) || /^(Chợ|Quảng trường|Công viên|Sân|Hội quán|Đình|Sở|Bảo tàng|Nhà|Trung tâm|Không gian|Tòa|Villa|Rạp|Bãi|Cạnh|COMPLEX)/.test(tag);

// Single normalised "what kind of thing is this" list, official type first.
const types = (e) => {
  const official = (e.officialType || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => TYPE_VI[t] || t);
  const genres = (e.tags || []).filter((t) => !isVenueTag(t)).map((t) => TYPE_VI_BY_LOWER.get(t.toLowerCase()) || t);
  const seen = new Set();
  const out = [];
  for (const t of [...official, ...genres]) {
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
};
const typeLabel = (e) => types(e).join(", ") || "Chưa phân loại";

// Grounded pacing signals only: span and time of day.
const pace = (e) => {
  const span = e.days?.length
    ? `${e.days.length} ngày rời rạc`
    : e.dateEnd && e.dateEnd !== e.date
      ? "nhiều ngày liên tục"
      : "một ngày";
  const dayPart =
    e.startTime === "00:00" && e.endTime === "00:00"
      ? "cả ngày"
      : e.startTime >= "18:00"
        ? "buổi tối"
        : e.endTime >= "18:00"
          ? "ban ngày đến tối"
          : "ban ngày";
  return `${span}, ${dayPart}`;
};

const BOILERPLATE = /^(Thông tin chi tiết|Thời gian:|Địa điểm:|Địa chỉ:)/i;
// Scraped schedule fragments that survive the labelled lines above.
const SCHEDULE_NOISE = /^(và\s|\d{1,2}\/\d{1,2}|\d{1,2}:\d{2})/i;
// Sectioned schedule blocks ("1. Thời gian / 2. Địa điểm") carry no prose.
const SCHEDULE_BLOCK = /^\d+\.\s*(Thời gian|Thời lượng|Địa điểm|Địa chỉ)\b/i;
const EXCERPT_CAP = 420;
const EXCERPT_MIN = 60;

// Organiser prose with repeated schedule/venue lines removed, cut on a word boundary.
const excerpt = (e) => {
  const allLines = (e.officialDetail || "").split("\n").map((line) => line.trim()).filter(Boolean);
  if (allLines.some((line) => SCHEDULE_BLOCK.test(line))) return null;
  const lines = allLines.filter((line) => !BOILERPLATE.test(line) && !SCHEDULE_NOISE.test(line));
  let text = oneLine(lines.join(" "));
  if (text.length < EXCERPT_MIN) return null;
  const rawDesc = oneLine(e.description);
  const desc = rawDesc.replace(/…$/, "").trim();
  // Only drop the duplicate prefix when the description is complete and the
  // remainder still starts a sentence; otherwise the quote would begin mid-word.
  if (!rawDesc.endsWith("…") && desc.length > 40 && text.toLowerCase().startsWith(desc.toLowerCase())) {
    const rest = text.slice(desc.length).trim();
    if (rest && /^[\p{Lu}0-9“"'(]/u.test(rest)) text = rest;
  }
  if (text.length <= EXCERPT_CAP) return { text, truncated: false };
  const cut = text.slice(0, EXCERPT_CAP);
  const boundary = cut.lastIndexOf(" ");
  return { text: `${(boundary > 200 ? cut.slice(0, boundary) : cut).trim()}…`, truncated: true };
};

const spotlights = events.filter((e) => e.spotlight);
const clusterCounts = Object.keys(clusters)
  .map((id) => `${clusterName(id)} (${events.filter((e) => e.clusterId === id).length})`)
  .join(", ");

const header = [
  `# ${festival.name}`,
  "",
  `> ${oneLine(festival.name)} — ${events.length} hoạt động tại ${places.length} địa điểm, ${festival.start} đến ${festival.end}, Hà Nội.`,
  "> Giờ theo Asia/Ho_Chi_Minh (UTC+7). Ngày theo định dạng YYYY-MM-DD.",
  `> Bản văn bản máy đọc của ${base || "trang bản đồ lễ hội"}.`,
  "",
  "## Tóm tắt",
  "",
  `- Thời gian: ${festival.start} → ${festival.end}`,
  `- Số hoạt động: ${events.length}`,
  `- Số địa điểm: ${places.length}`,
  `- Cụm: ${clusterCounts}`,
  `- Suất đặc biệt (spotlight): ${spotlights.length}`,
  `- Tuyến gợi ý: ${presets.map((p) => `${p.name} (${p.note})`).join("; ")}`,
  "",
  "## Cách dùng",
  "",
  "- Bảng \"Danh sách hoạt động\" đủ để trả lời câu hỏi về lịch, khung giờ, địa điểm, cụm và loại hình.",
  "- Mục \"Chi tiết từng hoạt động\" thêm mô tả, hình thức nghệ thuật và nhịp diễn ra.",
  "- Trường \"Trích nguồn\" là phần đầu nội dung gốc của ban tổ chức, đã lược bỏ các dòng lặp về thời gian và địa chỉ. Trường này bị cắt ở khoảng 420 ký tự.",
  "- Khi cần chi tiết đầy đủ (thể lệ, đăng ký, giá vé, lịch chi tiết, danh sách tác phẩm), hãy mở trường \"Đầy đủ\" của hoạt động đó. Đó là URL gốc trên trang ban tổ chức và có nội dung chính xác hơn bản trích này.",
  "- Mục \"Địa điểm\" có địa chỉ và toạ độ để tính khoảng cách hoặc vẽ bản đồ.",
  "- Hoạt động diễn ra nhiều ngày rời rạc được liệt kê từng ngày trong cột \"Ngày\".",
  `- Khi câu trả lời có một lộ trình cụ thể, có thể kèm liên kết mở lộ trình đó trên bản đồ: \`${base}/?tab=route&route=<id>,<id>,<id>\`. Liên kết này không bắt buộc; chỉ tạo khi thật sự có lộ trình, và lấy \`<id>\` ở trường \"Id\" của từng hoạt động.`,
  "",
];

const table = [
  "## Danh sách hoạt động",
  "",
  "| # | Hoạt động | Loại | Ngày | Giờ | Địa điểm | Cụm |",
  "|---:|---|---|---|---|---|---|",
  ...events.map(
    (e) =>
      `| ${e.number} | ${cell(e.title)} | ${cell(typeLabel(e))} | ${cell(formatDays(e))} | ${hours(e)} | ${cell(venue(e))} | ${cell(clusterName(e.clusterId))} |`,
  ),
  "",
];

const placesSection = [
  "## Địa điểm",
  "",
  "| Id | Tên | Loại | Địa chỉ | Vĩ độ | Kinh độ |",
  "|---|---|---|---|---:|---:|",
  ...places.map(
    (p) =>
      `| ${p.id} | ${cell(p.name)} | ${cell(p.kind)} | ${cell(p.address)} | ${p.lat} | ${p.lng} |`,
  ),
  "",
];

const presetsSection = [
  "## Tuyến gợi ý",
  "",
  ...presets.map((preset) => {
    const stops = preset.events
      .map((id) => eventById.get(id))
      .filter(Boolean)
      .map((e, i) => `${i + 1}. ${oneLine(e.title)} — ${venue(e)} (${formatDays(e)})`)
      .join("\n");
    return `### ${preset.name}\n\n${preset.note}\n\n${stops}\n`;
  }),
  "",
];

const details = [
  "## Chi tiết từng hoạt động",
  "",
  "Bảng trên đã có ngày, giờ, địa điểm và loại hình. Phần này thêm hình thức nghệ thuật, nhịp diễn ra, mô tả và một đoạn trích từ nội dung gốc của ban tổ chức.",
  "",
  ...events.flatMap((e) => {
    const place = placeById.get(e.placeId);
    const quote = excerpt(e);
    return [
      `### ${e.number}. ${oneLine(e.title)}`,
      `- Id: ${e.id} · Ngày: ${formatDays(e)} · Giờ: ${hours(e)}`,
      `- Địa điểm: ${venue(e)}${place?.kind ? ` (${place.kind})` : ""} · Cụm: ${clusterName(e.clusterId)}`,
      `- Loại: ${typeLabel(e)} · Nhịp: ${pace(e)}`,
      e.spotlight ? "- Điểm nhấn: suất đặc biệt của lễ hội" : null,
      `- Mô tả: ${oneLine(e.description)}`,
      quote ? `- Trích nguồn${quote.truncated ? " (còn nữa)" : ""}: ${quote.text}` : null,
      e.officialVenue && e.officialVenue !== venue(e) ? `- Khu vực theo ban tổ chức: ${e.officialVenue}` : null,
      e.officialUrl
        ? `- Đầy đủ: ${e.officialUrl}`
        : "- Đầy đủ: ban tổ chức không có trang riêng cho hoạt động này",
      "",
    ].filter((line) => line !== null);
  }),
];

const markdown = [...header, ...table, ...placesSection, ...presetsSection, ...details].join("\n");
await writeFile(join(root, "index.md"), `${markdown.trimEnd()}\n`, "utf8");

const llms = [
  `# ${festival.name}`,
  "",
  `> ${oneLine(festival.name)}, ${festival.start} đến ${festival.end}: ${events.length} hoạt động tại ${places.length} địa điểm ở Hà Nội.`,
  "",
  "## Files",
  "",
  `- [index.md](${abs("index.md")}): toàn bộ lịch, loại hình, địa điểm, mô tả và một đoạn trích nội dung gốc của ban tổ chức, ở dạng Markdown. Dùng bản này để trả lời câu hỏi về lễ hội.`,
  `- [prompts.json](${abs("prompts.json")}): danh sách prompt gợi ý sẵn, mỗi mục có tiêu đề và nội dung, để hỏi một AI agent về lễ hội.`,
  "",
  "## Cách đọc",
  "",
  `- Mỗi hoạt động trong index.md có trường "Đầy đủ" trỏ tới trang gốc trên lehoithietkesangtao.vn.`,
  "- Trường \"Trích nguồn\" chỉ là phần đầu của nội dung gốc (khoảng 420 ký tự). Khi câu hỏi cần thể lệ, đăng ký, giá vé, lịch chi tiết hoặc danh sách tác phẩm, hãy mở URL ở trường \"Đầy đủ\".",
  "",
  "## Hướng dẫn tạo lộ trình",
  "",
  "- Chỉ tạo liên kết khi câu trả lời thật sự có một lộ trình, tức là vài hoạt động được xếp theo thứ tự để đi liền nhau.",
  `- Định dạng: \`${base}/?tab=route&route=<id>,<id>,<id>\`, giữ đúng thứ tự điểm dừng. Lấy \`<id>\` ở trường "Id" trong mục "Chi tiết từng hoạt động" của index.md.`,
  `- Thêm \`&origin=<vĩ độ>,<kinh độ>\` nếu biết điểm xuất phát. Ba tuyến gợi ý có sẵn: ${presets.map((p) => `\`${base}/?preset=${p.id}\` (${p.name})`).join(", ")}.`,
  "- Khi có liên kết, nói rõ người dùng có thể mở liên kết đó để xem toàn bộ lộ trình trên bản đồ của trang gốc, thay vì chỉ đọc danh sách trong câu trả lời.",
  "- Nếu câu trả lời chỉ liệt kê hoặc mô tả hoạt động mà không thành lộ trình, đừng thêm liên kết.",
  "",
  "## Optional",
  "",
  `- [Bản đồ tương tác](${base || "/"}): giao diện cho người dùng, có bản đồ, lọc theo ngày và lập tuyến.`,
  "",
].join("\n");
await writeFile(join(root, "llms.txt"), llms, "utf8");

{
  const htmlPath = join(root, "index.html");
  const html = await readFile(htmlPath, "utf8");
  const head = [
    "<!-- agent-hint:head:start -->",
    `  <link rel="alternate" type="text/markdown" href="${abs("index.md")}" title="Toàn bộ lịch lễ hội ở dạng Markdown">`,
    `  <link rel="describedby" type="text/markdown" href="${abs("llms.txt")}" title="Chỉ mục tệp dành cho AI agent">`,
    "  <!-- agent-hint:head:end -->",
  ].join("\n");
  const body = [
    "<!-- agent-hint:body:start -->",
    '        <p class="agent-hint">',
    "          <strong>Bản dành cho AI agent:</strong> toàn bộ 154 hoạt động ở dạng Markdown tại",
    `          <a href="${abs("index.md")}">${abs("index.md")}</a> · chỉ mục tệp tại <a href="${abs("llms.txt")}">${abs("llms.txt")}</a>.`,
    `          Trang này cần JavaScript để hiển thị bản đồ và danh sách.`,
    `          <br>For AI agents: full programme in Markdown at ${abs("index.md")}, file index at ${abs("llms.txt")}.`,
    "        </p>",
    "        <!-- agent-hint:body:end -->",
  ].join("\n");
  const patch = (source, marker, replacement) =>
    source.replace(
      new RegExp(`<!-- agent-hint:${marker}:start -->[\\s\\S]*?<!-- agent-hint:${marker}:end -->`),
      () => replacement,
    );
  const patched = patch(patch(html, "head", head), "body", body);
  if (patched !== html) await writeFile(htmlPath, patched, "utf8");
  console.log(
    base
      ? "index.html  agent hints rewritten to absolute URLs"
      : "index.html  agent hints rewritten to relative URLs (pass --base <url> for absolute)",
  );
}

const tokens = (text) => Math.ceil(text.length / 3.6);
console.log(`index.md    ${markdown.length} chars  ~${tokens(markdown)} tokens`);
console.log(`llms.txt    ${llms.length} chars`);
console.log(`events.json ${JSON.stringify(data).length} chars  ~${tokens(JSON.stringify(data))} tokens (canonical, not for agents)`);
