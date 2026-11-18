FROM nginxinc/nginx-unprivileged:1.30.0-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 index.html events.json index.md llms.txt /usr/share/nginx/html/
COPY --chown=101:101 index.md.html llms.txt.html robots.txt prompts.json /usr/share/nginx/html/

USER 101
EXPOSE 8080
