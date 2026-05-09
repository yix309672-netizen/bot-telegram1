#!/bin/bash
set -e

DOMAIN="${1:-your-domain.com}"
EMAIL="${2:-yix309672@gmail.com}"
if [ "$DOMAIN" = "your-domain.com" ]; then
  echo "[TLS] Domain is not set. Please pass the real domain as the first argument."
  exit 1
fi

echo "[TLS] Requesting Let's Encrypt certificate for $DOMAIN with email $EMAIL"
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

sudo certbot --nginx -d "$DOMAIN" -m "$EMAIL" --agree-tos --no-eff-email

echo "[TLS] Certificate obtained and nginx updated. Check /etc/letsencrypt for certs."
