# tkst

Static site for Lễ hội Thiết kế Sáng tạo Hà Nội 2026, served at https://tkst.nvduc.dev.

`events.json` is the canonical content. `index.md` and `llms.txt` are generated from it:

```sh
node tools/build-agent-files.mjs --base https://tkst.nvduc.dev
```

Forgejo Actions builds and pushes `registry.example.com/OWNER/tkst:<git-sha>` on every push to `main`. The ArgoCD app in `deploy-repo/apps/profile/tkst` runs that image; promoting a build means bumping the image tag there.
