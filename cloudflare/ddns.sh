#!/bin/zsh
# Point a Cloudflare A record at this machine's current public IPv4 address.
#
# Usage: ddns.sh <zone> <record>     e.g. ddns.sh example.com home.example.com
#
# Needs CF_TOKEN in the environment, with DNS:Edit permission on the zone.
# Only the record's address changes; its TTL, proxy status, comment, and tags are kept.
set -euo pipefail

# Cloudflare API endpoint
API_URL="https://api.cloudflare.com/client/v4/zones"

# Log function to print verbose output
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1"
}

if [ $# -ne 2 ]; then
    echo "Usage: $0 <zone> <record>"
    exit 1
fi

if [ -z "${CF_TOKEN:-}" ]; then
    log "Error: CF_TOKEN environment variable is not set."
    exit 1
fi

for cmd in curl jq; do
    if ! command -v "$cmd" > /dev/null; then
        log "Error: '$cmd' is required but not installed."
        exit 1
    fi
done

ZONE_NAME=$1
RECORD_NAME=$2

# Call the zones API: cf_api <method> <endpoint> [extra curl arguments...]
cf_api() {
    local method=$1 endpoint=$2
    shift 2
    curl -sS -X "$method" "$API_URL$endpoint" \
         -H "Authorization: Bearer $CF_TOKEN" \
         -H "Content-Type: application/json" \
         "$@"
}

# Get current public IP
CURRENT_IP=$(curl -fsS --max-time 10 https://api.ipify.org)
if [[ ! "$CURRENT_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
    log "Error: Unexpected public IP lookup result: $CURRENT_IP"
    exit 1
fi
log "Current public IP: $CURRENT_IP"

# Get Zone ID for the zone
ZONE_RESPONSE=$(cf_api GET "?name=$ZONE_NAME")
ZONE_ID=$(echo "$ZONE_RESPONSE" | jq -r '.result[0].id // empty')
if [ -z "$ZONE_ID" ]; then
    log "Error: Unable to find Zone ID for zone: $ZONE_NAME"
    log "Response: $ZONE_RESPONSE"
    exit 1
fi

# Get the existing A record
RECORD_RESPONSE=$(cf_api GET "/$ZONE_ID/dns_records?type=A&name=$RECORD_NAME")
RECORD_ID=$(echo "$RECORD_RESPONSE" | jq -r '.result[0].id // empty')
OLD_IP=$(echo "$RECORD_RESPONSE" | jq -r '.result[0].content // empty')
if [ -z "$RECORD_ID" ]; then
    log "Error: No A record found for $RECORD_NAME"
    log "Response: $RECORD_RESPONSE"
    exit 1
fi

if [ "$CURRENT_IP" = "$OLD_IP" ]; then
    log "No change: $RECORD_NAME already points to $CURRENT_IP"
    exit 0
fi

# PATCH sends only the new address, so nothing else on the record is reset.
log "Updating $RECORD_NAME from $OLD_IP to $CURRENT_IP"
PAYLOAD=$(jq -nc --arg content "$CURRENT_IP" '{content: $content}')
RESPONSE=$(cf_api PATCH "/$ZONE_ID/dns_records/$RECORD_ID" --data "$PAYLOAD")

if [ "$(echo "$RESPONSE" | jq -r '.success')" = "true" ]; then
    log "DNS record updated: $RECORD_NAME -> $CURRENT_IP"
else
    log "Error: Failed to update DNS record for $RECORD_NAME"
    log "Response: $RESPONSE"
    exit 1
fi
