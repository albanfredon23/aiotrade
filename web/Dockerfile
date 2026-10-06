# Site AIOTrade : build Vite puis service statique nginx.
# Seul conteneur exposé : HTTP 8080 et HTTPS 8443 (ports 80 / 443 sur l'hôte).
# Proxy /api vers le moteur par le réseau interne ; métriques lues en lecture seule.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/site.conf /etc/nginx/snippets/site.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --chmod=755 nginx/40-aiotrade-tls.sh /docker-entrypoint.d/40-aiotrade-tls.sh
COPY --from=build /app/dist /usr/share/nginx/html
RUN mkdir -p /etc/nginx/aiotrade /etc/nginx/certs /srv/metrics
EXPOSE 8080 8443
HEALTHCHECK --interval=15s --timeout=4s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8081/healthz || exit 1
