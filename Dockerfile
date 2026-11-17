FROM nginxinc/nginx-unprivileged:1.30.0-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 index.html index.md llms.txt events.json /usr/share/nginx/html/

USER 101
EXPOSE 8080
