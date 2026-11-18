FROM node:22-alpine AS build

ARG SITE_BASE=https://tkst.nvduc.dev

WORKDIR /src
COPY index.html events.json prompts.json /src/
COPY tools/ /src/tools/
RUN node tools/build-agent-files.mjs --base "${SITE_BASE}" \
 && node tools/embed-events.mjs --out dist \
 && node tools/render-text-html.mjs --out dist

FROM nginxinc/nginx-unprivileged:1.30.0-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /src/dist/index.html /usr/share/nginx/html/index.html
COPY --from=build --chown=101:101 /src/dist/index.md.html /usr/share/nginx/html/index.md.html
COPY --from=build --chown=101:101 /src/dist/llms.txt.html /usr/share/nginx/html/llms.txt.html
COPY --from=build --chown=101:101 /src/index.md /src/llms.txt /usr/share/nginx/html/
COPY --chown=101:101 robots.txt prompts.json /usr/share/nginx/html/

USER 101
EXPOSE 8080
