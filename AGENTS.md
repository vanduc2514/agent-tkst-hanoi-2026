

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

### Apify through mise
`mise.toml` pins the Apify CLI; the gitignored `mise.local.toml` holds `APIFY_TOKEN` as an
environment variable. Run the sync skill through `mise exec` so the token reaches the process:

```sh
mise install                                                       # once per machine, installs apify-cli
mise exec -- python3 .agents/skills/sync-festival/scripts/sync_festival.py fetch
mise exec -- python3 .agents/skills/sync-festival/scripts/sync_festival.py diff
```

`mise env` lists the exported variables. Never pass the token as an argument or copy it into
another file.

## Deployment

- Never deploy directly by pushing Docker images to the registry
- Trigger CI action, skip if it is triggered automatically. Then wait for the CI action to complete
- GitHub is the primary remote (`origin`). A push to `main` builds and pushes the image to
  `ghcr.io`.

### Scheduled festival sync

`.github/workflows/sync-festival.md` is a GitHub Agentic Workflow: it runs daily, executes the
skill, and opens a pull request whose body is `tmp/sync/report.md`. `sync-festival.lock.yml` is
generated — edit the `.md` and run `gh aw compile`, never the lock file.

Required repository secrets: `APIFY_TOKEN` and `COPILOT_GITHUB_TOKEN`. The Copilot secret must be
a fine-grained PAT (`github_pat_…`) with Copilot access; OAuth tokens (`gho_…`) are rejected.

## Conventions
- There is no test suite, linter, or package manager. Verify changes by serving the page and open the page via browser
- Keep the site dependency-free: no bundler, framework, or npm packages.
- Commit subjects are imperative sentences with no prefix.
