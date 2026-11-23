---
on:
  # Paused until the Copilot model routing is confirmed on this account; a daily
  # run that fails only produces noise. Re-enable with `schedule: daily`.
  workflow_dispatch:
engine: copilot
# The fine-grained PAT behind COPILOT_GITHUB_TOKEN is entitled to the GPT chat
# models only; the default `auto` resolves to Sonnet, which the API answers with
# 502 because no fallback model can be dispatched.
model: gpt-4.1
permissions:
  contents: read
network:
  allowed:
    - defaults
tools:
  # The agent edits files and opens a PR through safe-outputs; it never needs the
  # GitHub MCP server, which costs a container pull and ~7 KB of generated steps.
  github: false
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
  # Failures are visible in the Actions tab; do not open an issue per attempt.
  report-failure-as-issue: false
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

## Already done, before you started

The `Fetch and resolve the programme` step has run these, with `APIFY_TOKEN` in
its own environment:

```sh
sync_festival.py fetch
sync_festival.py diff        # exit 1 means "something to review", not an error
sync_festival.py enrich --write
sync_festival.py apply
```

and the `Validate` step has run `check`, `selftest.py` and the agent-file build.
So `tmp/sync/report.md` and the resolved `src/events.json` are on disk. That
retrieval is finished: do not repeat it, and do not look for `APIFY_TOKEN`. It is
not in your environment on purpose, and the Apify spend is already made.

`images` is not part of this run. It needs Pillow and Apple's Vision OCR to verify
which picture belongs to which event, and the runner has neither, so the image
fields stay exactly as committed here. Do not edit `image` or `images`, and do not
attach a picture you did not verify.

## Your job

1. Read `tmp/sync/report.md`. That is the report for this run.

2. The `## Needs your review` rows are for a human unless one of them is a value
   the sources already settle and the skill has a rule for. In that case, make the
   smallest edit that rule allows, then re-run the checks:

   ```sh
   python3 .agents/skills/sync-festival/scripts/sync_festival.py check
   python3 .agents/skills/sync-festival/scripts/selftest.py
   node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
   ```

   Leave alone, without exception: a curated per-day schedule, a conflict between
   the site and a post, a slug that needs a map pin, and a page that disappeared.
   Never invent a value. If every row is one of those, that is a valid outcome.

3. If `src/events.json` did not change, call `noop` with a one-line summary and
   stop. Do not open an empty pull request.

4. Otherwise open a pull request with `create-pull-request`:

   - Title: `Sync the festival programme for <date>`
   - Body: the **full, unmodified contents of `tmp/sync/report.md`**, pasted as
     Markdown, followed by one line naming what you changed.
   - Commit only `src/events.json` and the generated `src/index.md`,
     `src/llms.txt`, `src/index.md.html`, `src/llms.txt.html` when they changed.
     `tmp/` is gitignored and must stay out.

## Rules

- Never deploy, never build an image, never touch `.github/`.
- Never edit `src/events.json` by hand outside the skill's own rules.
- The report body must keep its two sections, `## Changes made` and
  `## Needs your review`, exactly as generated.
