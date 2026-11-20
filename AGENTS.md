

## Project
An unofficial companion site for the Hanoi Design Festival 2026: a static page with an
interactive map, a route planner, and agent-readable Markdown.
## Hints
- `src/index.html` is the whole app: plain HTML, CSS, and vanilla JavaScript with no build step.
  MapLibre and Tailwind load from CDNs.
- `src/events.json` is the single source of truth for all festival data.
- `tools/build-agent-files.mjs` reads `src/events.json` and writes `src/index.md` and
  `src/llms.txt`, plus browser-readable `src/index.md.html` and `src/llms.txt.html` wrappers.
- `src/` is the folder that gets served and copied into the image, so it holds the page, the
  data files and the generated output. `images/` sits at the root and is only used by the
  README, not by the site.
- `.agents/skills/sync-festival/` keeps `src/events.json` in step with the organiser. It reads
  the official JSON API and pulls Facebook, Instagram and Threads through Apify, then reports
  drift before anything is written. Read its `SKILL.md` first; the Python scripts live next to it.
- Generated files are gitignored. CI regenerates them, then builds the nginx image.
- Use`tmp` in this workspace to store temporary script, artifact or anything that is not included in the app or in build process
## Local Development
```sh
python3 -m http.server 8080 --directory src                        # start local development server
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev     # generate markdown + HTML agent files
```

## Deployment

- Never deploy directly by pushing Docker images to the registry
- Trigger CI action, skip if it is triggered automatically. Then wait for the CI action to complete

## Conventions
- There is no test suite, linter, or package manager. Verify changes by serving the page and open the page via browser
- Keep the site dependency-free: no bundler, framework, or npm packages.
- Commit subjects are imperative sentences with no prefix.
