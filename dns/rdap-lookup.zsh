#!/usr/bin/env zsh
# rdap-lookup.zsh — Look up domain registration data via RDAP
# Usage: rdap-lookup.zsh <domain> [domain2 ...]
#
# Discovers the correct RDAP server from IANA's bootstrap file,
# so it works for Google TLDs (.app, .dev, .page, etc.) and others.
# Set RDAP_FULL_JSON=1 to also print each full JSON response.

set -euo pipefail

IANA_BOOTSTRAP="https://data.iana.org/rdap/dns.json"
SCRIPT_NAME=${0:t}  # inside a function, zsh sets $0 to the function name

usage() {
  print "Usage: $SCRIPT_NAME <domain> [domain2 ...]"
  print "Examples:"
  print "  $SCRIPT_NAME example.app"
  print "  $SCRIPT_NAME mysite.dev another.page"
  exit 1
}

# Check dependencies
for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    print -u2 "Error: '$cmd' is required but not installed."
    exit 1
  fi
done

[[ $# -eq 0 ]] && usage

# Fetch and cache the IANA bootstrap JSON once per run
print "Fetching IANA RDAP bootstrap..." >&2
BOOTSTRAP_JSON=$(curl -fsSL "$IANA_BOOTSTRAP") || {
  print -u2 "Error: Failed to fetch IANA bootstrap from $IANA_BOOTSTRAP"
  exit 1
}

# Given a TLD, return the RDAP base URL from the bootstrap data
get_rdap_base_url() {
  local tld="$1"
  # Each entry in "services" is [[tld1, tld2, ...], [url1, ...]]
  # Find the entry whose first array contains our TLD, return first URL
  echo "$BOOTSTRAP_JSON" | jq -r --arg tld "$tld" '
    .services[]
    | select(.[0] | index($tld) != null)
    | .[1][0]
  ' | head -1
}

lookup_domain() {
  local domain="$1"

  # Extract TLD (everything after the last dot)
  local tld="${domain##*.}"

  if [[ -z "$tld" || "$tld" == "$domain" ]]; then
    print -u2 "Error: '$domain' doesn't look like a valid domain name."
    return 1
  fi

  # Discover RDAP server
  local base_url
  base_url=$(get_rdap_base_url "$tld")

  if [[ -z "$base_url" ]]; then
    print -u2 "Warning: No RDAP server found for TLD '.$tld' in IANA bootstrap. Skipping $domain."
    return 1
  fi

  # Strip trailing slash, build query URL
  base_url="${base_url%/}"
  local rdap_url="${base_url}/domain/${domain}"

  print "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  print "Domain : $domain"
  print "Server : $base_url"
  print "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # One request returns the body followed by the status code on its own line
  local response http_code body
  response=$(curl -sS -w '\n%{http_code}' \
    -H "Accept: application/rdap+json" \
    "$rdap_url" 2>/dev/null) || true
  http_code="${response##*$'\n'}"
  body="${response%$'\n'*}"

  if [[ "$http_code" == "404" ]]; then
    print "Status : NOT FOUND (domain not registered or not in this registry)"
    return 0
  elif [[ "$http_code" != "200" ]]; then
    print -u2 "Error  : HTTP ${http_code:-error} from $rdap_url"
    return 1
  fi

  # Pretty-print key fields
  echo "$body" | jq -r '
    "Status : " + ([ .status[]? ] | join(", ")),
    "Handle : " + (.handle // "N/A"),
    "Created: " + ([ .events[]? | select(.eventAction=="registration") | .eventDate ] | first // "N/A"),
    "Updated: " + ([ .events[]? | select(.eventAction=="last changed")  | .eventDate ] | first // "N/A"),
    "Expires: " + ([ .events[]? | select(.eventAction=="expiration")    | .eventDate ] | first // "N/A"),
    "NS     : " + ([ .nameservers[]?.ldhName ] | join(", ") | if . == "" then "N/A" else . end)
  ' 2>/dev/null || {
    print "Raw response (jq parse failed):"
    echo "$body"
  }

  # Optionally dump full JSON
  if [[ "${RDAP_FULL_JSON:-}" == "1" ]]; then
    print "\nFull JSON:"
    echo "$body" | jq .
  fi
}

# Process each domain argument; keep going past failures, then report them
rc=0
for domain in "$@"; do
  lookup_domain "$domain" || rc=1
done

print ""
exit $rc
