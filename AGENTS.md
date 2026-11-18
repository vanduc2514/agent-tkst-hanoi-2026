

## Project
An unofficial companion site for the Hanoi Design Festival 2026: a static page with an
interactive map, a route planner, and agent-readable Markdown.
## Hints
- `index.html` is the whole app: plain HTML, CSS, and vanilla JavaScript with no build step.
  MapLibre and Tailwind load from CDNs.
- `events.json` is the single source of truth for all festival data.
- `tools/build-agent-files.mjs` generates `index.md` and `llms.txt` from `events.json`, plus
  browser-readable `index.md.html` and `llms.txt.html` wrappers.
- Generated files are gitignored. CI regenerates them, then builds the nginx image.
- Use`tmp` in this workspace to store temporary script, artifact or anything that is not included in the app or in build process
## Local Development
```sh
python3 -m http.server 8080                                        # start local development server
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev     # generate markdown + HTML agent files
```

## Deployment

- Never deploy directly by pushing Docker images to the registry
- Trigger CI action, skip if it is triggered automatically. Then wait for the CI action to complete

## Conventions
- There is no test suite, linter, or package manager. Verify changes by serving the page and open the page via browser
- Keep the site dependency-free: no bundler, framework, or npm packages.
- Commit subjects are imperative sentences with no prefix.
