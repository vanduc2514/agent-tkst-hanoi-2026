FROM nginxinc/nginx-unprivileged:1.30.0-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 src/index.html src/events.json src/index.md src/llms.txt src/i18n.js /usr/share/nginx/html/
COPY --chown=101:101 src/index.md.html src/llms.txt.html src/robots.txt src/prompts.json /usr/share/nginx/html/
COPY --chown=101:101 src/i18n /usr/share/nginx/html/i18n
COPY --chown=101:101 src/images /usr/share/nginx/html/images

USER 101
EXPOSE 8080
