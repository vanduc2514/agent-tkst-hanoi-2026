# tkst

Static site for Lễ hội Thiết kế Sáng tạo Hà Nội 2026, served at https://tkst.nvduc.dev.

`events.json` is the canonical content. `index.md` and `llms.txt` are generated from it:

```sh
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
```

Forgejo Actions builds and pushes `registry.example.com/OWNER/tkst:<git-sha>` on every push to `main`. The ArgoCD app in `deploy-repo/apps/profile/tkst` runs that image; promoting a build means bumping the image tag there.

## CI

- Runs on the always-on `ubuntu-latest` runner (NEC Mate).
- Requires the repository secret `REGISTRY_TOKEN` with package write access to `registry.example.com`.
- Every push to `main` publishes `registry.example.com/OWNER/tkst:<git-sha>` and `:latest`.
- Promote a build by pinning its tag and digest in `deploy-repo/apps/profile/tkst/values.yaml`.
