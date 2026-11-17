#!/usr/bin/env node
// Derives agent-facing markdown from events.json.
// events.json stays the canonical machine format; index.md and llms.txt are the
// formats LLM agents actually consume. Pass --base to rewrite the agent-hint
// blocks in index.html to absolute URLs.
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

const spotlights = events.filter((e) => e.spotlight);
const clusterCounts = Object.keys(clusters)
  .map((id) => `${clusterName(id)} (${events.filter((e) => e.clusterId === id).length})`)
  .join(", ");

const header = [
  `# ${festival.name}`,
  "",
  `> ${oneLine(festival.name)} — ${events.length} hoạt động tại ${places.length} địa điểm, ${festival.start} đến ${festival.end}, Hà Nội.`,
  "> Giờ theo Asia/Ho_Chi_Minh (UTC+7). Ngày theo định dạng YYYY-MM-DD.",
  `> Bản văn bản máy đọc của ${base || "trang bản đồ lễ hội"}. Nguồn dữ liệu: ${abs("events.json")}.`,
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
  "- Bảng \"Danh sách hoạt động\" đủ để trả lời câu hỏi về lịch, khung giờ, địa điểm, cụm.",
  "- Mục \"Chi tiết từng hoạt động\" có mô tả đầy đủ và link trang chính thức của ban tổ chức.",
  "- Mục \"Địa điểm\" có địa chỉ và toạ độ để tính khoảng cách hoặc vẽ bản đồ.",
  "- Hoạt động diễn ra nhiều ngày rời rạc được liệt kê từng ngày trong cột \"Ngày\".",
  "",
];

const table = [
  "## Danh sách hoạt động",
  "",
  "| # | Hoạt động | Ngày | Giờ | Địa điểm | Cụm |",
  "|---:|---|---|---|---|---|",
  ...events.map(
    (e) =>
      `| ${e.number} | ${cell(e.title)} | ${cell(formatDays(e))} | ${hours(e)} | ${cell(venue(e))} | ${cell(clusterName(e.clusterId))} |`,
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
  "Bảng trên đã có ngày, giờ và địa điểm. Phần này thêm mô tả đầy đủ, toạ độ và nguồn chính thức.",
  "",
  ...events.flatMap((e) => {
    const place = placeById.get(e.placeId);
    return [
      `### ${e.number}. ${oneLine(e.title)}`,
      `- Id: ${e.id} · Ngày: ${formatDays(e)} · Giờ: ${hours(e)}`,
      `- Địa điểm: ${venue(e)}${place?.kind ? ` (${place.kind})` : ""} · Cụm: ${clusterName(e.clusterId)}`,
      e.spotlight ? "- Suất đặc biệt: có" : null,
      `- Mô tả: ${oneLine(e.description)}`,
      e.officialVenue && e.officialVenue !== venue(e) ? `- Khu vực theo ban tổ chức: ${e.officialVenue}` : null,
      e.officialUrl ? `- Nguồn: ${e.officialUrl}` : null,
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
  `- [index.md](${abs("index.md")}): toàn bộ lịch, địa điểm, mô tả và link chính thức ở dạng Markdown, dùng bản này để trả lời câu hỏi về lễ hội.`,
  `- [events.json](${abs("events.json")}): cùng dữ liệu ở dạng JSON có cấu trúc, dùng khi cần phân tích bằng code.`,
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
    `          <a href="${abs("index.md")}">${abs("index.md")}</a> · chỉ mục tệp tại <a href="${abs("llms.txt")}">${abs("llms.txt")}</a> · dữ liệu gốc tại`,
    `          <a href="${abs("events.json")}">${abs("events.json")}</a>. Trang này cần JavaScript để hiển thị bản đồ và danh sách.`,
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
