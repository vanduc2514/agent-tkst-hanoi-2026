FROM nginxinc/nginx-unprivileged:1.30.0-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 src/index.html src/events.json src/index.md src/llms.txt /usr/share/nginx/html/
COPY --chown=101:101 src/index.md.html src/llms.txt.html src/robots.txt src/prompts.json /usr/share/nginx/html/

USER 101
EXPOSE 8080
