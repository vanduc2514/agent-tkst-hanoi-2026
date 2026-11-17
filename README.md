# tkst

Static site for Lễ hội Thiết kế Sáng tạo Hà Nội 2026, served at https://tkst.nvduc.dev.

`events.json` is the canonical content source. It is never published: the image embeds it into
`index.html` at build time and serves only that page plus `index.md` and `llms.txt`.

## Local build

```sh
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev   # regenerate index.md + llms.txt
docker build -t tkst:local .                                    # embed events.json, build the image
docker run --rm -p 8080:8080 tkst:local
```

Opening `index.html` directly still works for development: without the embedded block the page
falls back to fetching `events.json` from disk.

## CI

One workflow, `.github/workflows/build.yml`, runs on both platforms:

| | GitHub | Forgejo |
|---|---|---|
| Registry | `ghcr.io/<owner>/<repo>` | `registry.example.com/<owner>/<repo>` |
| Auth | `GITHUB_TOKEN` | secret `REGISTRY_TOKEN` |

The registry is chosen from `GITHUB_SERVER_URL`, so no forking is needed. Every push to `main`
publishes `:<git-sha>` and `:latest`, and the job fails if `index.md`, `llms.txt` or the
`index.html` agent hints are out of date.

Promote a build by pinning its tag and digest in
`deploy-repo/apps/profile/tkst/values.yaml`.
