---
on:
  schedule: daily
  workflow_dispatch:
engine: copilot
permissions:
  contents: read
network:
  allowed:
    - defaults
tools:
  bash:
    - python3
    - node
    - git
    - cat
    - sed
    - grep
    - mkdir
    - ls
    - diff
  edit:
safe-outputs:
  create-pull-request:
    title-prefix: "[sync] "
    labels: [festival-sync]
    base-branch: main
    protected-files: allowed
  noop:
steps:
  - name: Fetch and resolve the programme
    env:
      APIFY_TOKEN: ${{ secrets.APIFY_TOKEN }}
    run: |
      set -e
      skill=.agents/skills/sync-festival/scripts/sync_festival.py
      python3 "$skill" fetch
      # `diff` exits 1 when there is something to review, which is the normal case.
      rc=0
      python3 "$skill" diff || rc=$?
      if [ "$rc" -eq 2 ]; then exit 2; fi
      python3 "$skill" enrich --write
      python3 "$skill" apply
  - name: Validate
    run: |
      python3 .agents/skills/sync-festival/scripts/sync_festival.py check
      python3 .agents/skills/sync-festival/scripts/selftest.py
      node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
---

# Sync the festival programme

Keep `src/events.json` in step with the organiser, following
`.agents/skills/sync-festival/SKILL.md`. Read that file first; it defines the
sources, the precedence rules and the reporting contract.

## Steps

1. Run the retrieval and the comparison, in this order:

   ```sh
   python3 .agents/skills/sync-festival/scripts/sync_festival.py fetch
   python3 .agents/skills/sync-festival/scripts/sync_festival.py diff
   python3 .agents/skills/sync-festival/scripts/sync_festival.py enrich --write
   python3 .agents/skills/sync-festival/scripts/sync_festival.py apply
   ```

   The Apify token is already in the environment as `APIFY_TOKEN`. Never write it
   to a file, a commit or the pull request.

2. Run the checks and stop if either fails:

   ```sh
   python3 .agents/skills/sync-festival/scripts/sync_festival.py check
   python3 .agents/skills/sync-festival/scripts/selftest.py
   node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
   ```

3. Resolve what the report still lists under "Needs your review", but only where
   the sources let you. The rules are in the skill's ground rules: a curated
   per-day schedule stays; a conflict between the site and a post stays; a slug
   that needs a map pin stays. Do not invent a value.

4. If `src/events.json` did not change, call `noop` with a one-line summary and
   stop. Do not open an empty pull request.

5. Open a pull request with `create-pull-request`:

   - Title: `Sync the festival programme for <date>`
   - Body: the **full, unmodified contents of `tmp/sync/report.md`**, pasted as
     Markdown, followed by one line naming the commands that ran.
   - Commit only `src/events.json`, `src/index.md`, `src/llms.txt` and the two
     HTML wrappers when they changed. `tmp/` is gitignored and must stay out.

## Rules

- Never deploy, never build an image, never touch `.github/`.
- Never edit `src/events.json` by hand when the skill can do it.
- The report body must keep its two sections, `## Changes made` and
  `## Needs your review`, exactly as generated.
