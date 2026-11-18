#!/usr/bin/env node
// Renders browser-friendly HTML wrappers for the plain-text files.
// Browsers and readers that ask for text/html get the wrapper; everyone else
// keeps getting the raw text. Content is never altered, only escaped.
//
// Usage: node tools/render-text-html.mjs [--out <dir>]   (default: next to the sources)

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outArgIndex = process.argv.indexOf("--out");
const outDir = join(root, outArgIndex > -1 ? process.argv[outArgIndex + 1] : ".");

const files = [
  { source: "index.md", title: "Lễ hội Thiết kế Sáng tạo Hà Nội 2026 — bản Markdown" },
  { source: "llms.txt", title: "Lễ hội Thiết kế Sáng tạo Hà Nội 2026 — chỉ mục cho AI agent" },
];

const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const page = ({ title, source, body }) => `<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <link rel="alternate" type="text/plain" href="${source}">
  <style>
    :root { color-scheme: light dark; }
    body { margin: 0; padding: 32px 20px 64px; background: #f7faf8; color: #1f2a25;
      font: 15px/1.65 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif; }
    main { max-width: 900px; margin: 0 auto; }
    h1 { margin: 0 0 4px; font-size: 15px; }
    p.note { margin: 0 0 20px; color: #6b7a73; font-size: 12px; }
    p.note a { color: #245c4b; }
    pre { margin: 0; padding: 20px; border: 1px solid #e2e8e4; border-radius: 10px;
      background: #fff; white-space: pre-wrap; word-break: break-word;
      font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace; }
    @media (prefers-color-scheme: dark) {
      body { background: #101815; color: #e6efea; }
      pre { background: #16211d; border-color: #26332d; }
      p.note { color: #9aaba4; }
      p.note a { color: #7fd1b3; }
    }
  </style>
</head>
<body>
  <main>
    <h1>${escapeHtml(title)}</h1>
    <p class="note">Bản văn bản gốc: <a href="${source}">/${source}</a> · máy đọc dùng
      <code>Content-Type: text/plain</code>, trình duyệt nhận trang này.</p>
    <pre>${body}</pre>
  </main>
</body>
</html>
`;

await mkdir(outDir, { recursive: true });
for (const { source, title } of files) {
  const text = await readFile(join(root, source), "utf8");
  const html = page({ title, source, body: escapeHtml(text) });
  await writeFile(join(outDir, `${source}.html`), html, "utf8");
  console.log(`${source}.html  ${html.length} chars`);
}
