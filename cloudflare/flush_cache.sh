#!/bin/zsh

# Cloudflare API Token (ensure it has `purge:cache` permission for the domain)
API_TOKEN="your_api_token_here"

# Check if domain is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <domain>"
    exit 1
fi

DOMAIN=$1

# Cloudflare API endpoint
API_URL="https://api.cloudflare.com/client/v4/zones"

# Log function to print verbose output
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1"
}

# Get Zone ID for the domain
log "Fetching Zone ID for domain: $DOMAIN"
ZONE_ID=$(curl -s -X GET "$API_URL?name=$DOMAIN" \
     -H "Authorization: Bearer $API_TOKEN" \
     -H "Content-Type: application/json" | jq -r '.result[0].id')

if [ "$ZONE_ID" = "null" ] || [ -z "$ZONE_ID" ]; then
    log "Error: Unable to find Zone ID for domain: $DOMAIN"
    exit 1
fi
log "Zone ID for $DOMAIN: $ZONE_ID"

# Purge cache for the domain
log "Purging cache for domain: $DOMAIN"
RESPONSE=$(curl -s -X POST "$API_URL/$ZONE_ID/purge_cache" \
     -H "Authorization: Bearer $API_TOKEN" \
     -H "Content-Type: application/json" \
     --data '{"purge_everything":true}')

# Check if purge was successful
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')

if [ "$SUCCESS" = "true" ]; then
    log "Cache successfully purged for domain: $DOMAIN"
else
    log "Error: Failed to purge cache for domain: $DOMAIN"
    log "Response: $RESPONSE"
    exit 1
fi
