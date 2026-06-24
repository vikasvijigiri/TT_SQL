FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=20s --timeout=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/api/health || exit 1
