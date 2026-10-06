#!/bin/sh
# Choisit le mode HTTP / HTTPS au démarrage du conteneur.
#   Certificats présents (/etc/nginx/certs/fullchain.pem + privkey.pem) :
#     HTTPS sur 8443, HTTP redirigé vers HTTPS, HSTS actif.
#   Sinon : HTTP seul (développement local) et avertissement dans les journaux.
set -eu
CERTS=/etc/nginx/certs
OUT=/etc/nginx/aiotrade
mkdir -p "$OUT"

if [ -s "$CERTS/fullchain.pem" ] && [ -s "$CERTS/privkey.pem" ]; then
    cat > "$OUT/tls-server.conf" <<'CONF'
server {
    listen 8443 ssl;
    http2 on;
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:aiotrade_tls:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    include /etc/nginx/snippets/site.conf;
}
CONF
    echo 'return 301 https://$host$request_uri;' > "$OUT/http-mode.conf"
    echo "aiotrade : HTTPS actif sur 8443, HTTP redirigé vers HTTPS"
else
    : > "$OUT/tls-server.conf"
    : > "$OUT/http-mode.conf"
    echo "aiotrade : aucun certificat dans $CERTS, HTTPS désactivé (HTTP seul). En production, montez fullchain.pem et privkey.pem."
fi
