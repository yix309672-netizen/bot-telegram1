#!/bin/bash
set -e

DOMAIN="${1:-your-domain.com}"
EMAIL="${2:-yix309672@gmail.com}"

echo "[DEPLOY] Domain: $DOMAIN, Email: $EMAIL"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Install Docker on the target host before proceeding."
  exit 1
fi
if ! command -v docker-compose >/dev/null 2>&1; then
  echo "Docker Compose not found. Install Docker Compose on the target host before proceeding."
  exit 1
fi

echo "[DEPLOY] Starting docker-compose deployment..."
docker-compose up -d --build

echo "[DEPLOY] Requesting TLS certificate via certbot..."
bash tls_setup.sh "$DOMAIN" "$EMAIL"

echo "[DEPLOY] Deployment finished. Access https://$DOMAIN"
