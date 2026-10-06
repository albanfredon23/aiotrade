# Certificats TLS

Déposez ici `fullchain.pem` et `privkey.pem` (Let's Encrypt ou votre autorité de certification) pour activer
HTTPS : le conteneur web les lit en lecture seule, sert le site sur le port 443 et redirige le port 80 vers
HTTPS. Sans certificat, le site est servi en HTTP seul (développement local).

Ces fichiers ne sont jamais versionnés (voir `.gitignore`) ni copiés dans une image (voir `.dockerignore`).
Un autre emplacement peut être indiqué avec `AIOTRADE_CERTS_DIR`.
