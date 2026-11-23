

## Project
An unofficial companion site for the Hanoi Design Festival 2026: a static page with an
interactive map, a route planner, and agent-readable Markdown.
## Hints
- `src/index.html` is the whole app: plain HTML, CSS, and vanilla JavaScript with no build step.
  MapLibre and Tailwind load from CDNs.
- `src/events.json` is the single source of truth for all festival data.
- User-facing copy lives in `src/i18n/vi.json` and `src/i18n/en.json`, loaded by
  `src/i18n.js`: browser detection, Vietnamese as the default, `?lang=` override and a
  stored choice. Add every key to both files and keep them in sync; the Dockerfile copies
  these files next to the page, and event titles/descriptions stay as the organiser wrote
  them in Vietnamese.
- `src/events.json` is also the source for cluster names and venue kinds; their translations
  sit in the `vocab` block of each locale file, keyed by the source value.
- `tools/build-agent-files.mjs` reads `src/events.json` and writes `src/index.md` and
  `src/llms.txt`, plus browser-readable `src/index.md.html` and `src/llms.txt.html` wrappers.
- `src/` is the folder that gets served and copied into the image, so it holds the page, the
  data files and the generated output. `images/` sits at the root and is only used by the
  README, not by the site. `src/images/kinds/` holds the tile for each kind, used when an
  image fails to load; `src/images/events/` and `src/images/cards/` hold the organiser's own
  pictures; `src/images/posters/` holds the generated card for every event that has none.
- `.agents/skills/sync-festival/` keeps `src/events.json` in step with the organiser. It reads
  the official JSON API and pulls Facebook, Instagram and Threads through Apify, then reports
  drift before anything is written. Read its `SKILL.md` first; the Python scripts live next to it.
  Its `images` command gathers promotion photos and designed cards, reads each one with OCR to
  prove which event it shows, and stores the winners under `src/images`; it runs locally, not
  in CI, because it needs Pillow and Apple's Vision framework.
- `tools/build-event-posters.py` draws one poster per event that has no photograph:
  title, date and venue, in the colour of its kind. It is committed output, so rerun it
  (or `--check` in CI) after any title, date or venue change.
- Generated files are gitignored. CI regenerates them, then builds the nginx image.
- Use`tmp` in this workspace to store temporary script, artifact or anything that is not included in the app or in build process
## Local Development
```sh
python3 -m http.server 8080 --directory src                        # start local development server
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev     # generate markdown + HTML agent files
```

### Apify through mise
`mise.toml` pins the Apify CLI; the gitignored `mise.local.toml` holds `APIFY_TOKEN` as an
environment variable. Run the sync skill through `mise exec` so the token reaches the process:

```sh
mise install                                                       # once per machine, installs apify-cli
mise exec -- python3 .agents/skills/sync-festival/scripts/sync_festival.py fetch
mise exec -- python3 .agents/skills/sync-festival/scripts/sync_festival.py diff
mise exec -- python3 .agents/skills/sync-festival/scripts/sync_festival.py images
```

`images` needs Pillow (`python3 -m pip install pillow`) and compiles
`scripts/ocr.swift` on first use; without OCR it keeps only photos it can attribute
and never guesses a card.

`mise env` lists the exported variables. Never pass the token as an argument or copy it into
another file.

## Deployment

- Never deploy directly by pushing Docker images to the registry
- Trigger CI action, skip if it is triggered automatically. Then wait for the CI action to complete
- GitHub is the primary remote (`origin`). A push to `main` builds and pushes the image to
  `ghcr.io`.

### Scheduled festival sync

`.github/workflows/sync-festival.md` is a GitHub Agentic Workflow: it executes the skill in
frontmatter `steps` (so `APIFY_TOKEN` never reaches the agent), then lets the agent resolve the
review rows and open a pull request whose body is `tmp/sync/report.md`. `sync-festival.lock.yml`
is generated — edit the `.md` and run `gh aw compile`, never the lock file.

The schedule is paused; triggers are manual (`gh aw run sync-festival`) until the model routing
below is confirmed. `model: gpt-4.1` is pinned because the default `auto` resolves to a model the
token cannot call, which the API answers with 502. `tools.github: false` drops the GitHub MCP
server, which the agent never uses: files are edited directly and the PR is created by
safe-outputs. Threat detection stays on — the agent reads untrusted post text, so the detector that
screens its output is worth its ~28 KB.

Required repository secrets: `APIFY_TOKEN` and `COPILOT_GITHUB_TOKEN`. The Copilot secret must be
a fine-grained PAT (`github_pat_…`) whose only permission is Account → Copilot Requests; OAuth
tokens (`gho_…`) are rejected. Push the Apify secret from the local mise profile, never from a
copy of the value:

```sh
mise exec -- bash -c 'printf "%s" "$APIFY_TOKEN" | gh secret set APIFY_TOKEN --repo vanduc2514/agent-tkst-hanoi-2026'
```

## Conventions
- There is no test suite, linter, or package manager. Verify changes by serving the page and open the page via browser
- Keep the site dependency-free: no bundler, framework, or npm packages.
- Commit subjects are imperative sentences with no prefix.
