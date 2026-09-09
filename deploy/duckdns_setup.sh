#!/bin/bash
set -e
DOMAIN="${1:-telegramweb.duckdns.org}"
TOKEN="${2:-${DUCKDNS_TOKEN}}"
if [ -z "$TOKEN" ]; then
  echo "Usage: deploy/duckdns_setup.sh <domain> <token>"
  echo "Or set environment variable DUCKDNS_TOKEN with your DuckDNS token."
  exit 1
fi
SUBDOMAIN=$(echo "$DOMAIN" | cut -d'.' -f1)
CRON="*/5 * * * * curl -s https://duckdns.org/update?domains=${SUBDOMAIN}&token=${TOKEN} >/dev/null 2>&1"
(crontab -l 2>/dev/null; echo "$CRON") | crontab -
echo "DuckDNS cron added for $DOMAIN"
