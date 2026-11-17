#!/usr/bin/env node
// Inlines events.json into a copy of index.html so the published page carries its
// own data and the raw JSON is never served as a file.
//
// Usage: node tools/embed-events.mjs [--out dist]

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outArgIndex = process.argv.indexOf("--out");
const outDir = join(root, outArgIndex > -1 ? process.argv[outArgIndex + 1] : "dist");

const data = JSON.parse(await readFile(join(root, "events.json"), "utf8"));
for (const key of ["festival", "clusters", "places", "events", "presets"]) {
  if (!(key in data)) throw new Error(`events.json is missing "${key}"`);
}

const payload = JSON.stringify(data).replace(/</g, "\\u003c");
const tag = `<script type="application/json" id="events-data">${payload}</script>`;

const html = await readFile(join(root, "index.html"), "utf8");
const existing = /  <script type="application\/json" id="events-data">[\s\S]*?<\/script>\n/;
const output = existing.test(html)
  ? html.replace(existing, () => `${tag}\n`)
  : html.replace(/\n<\/body>/, () => `\n  ${tag}\n</body>`);

if (output === html) throw new Error("could not place the embedded data block in index.html");

await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, "index.html"), output, "utf8");
console.log(`index.html  data embedded (${payload.length} chars) -> ${outDir}/index.html`);
