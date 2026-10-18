#!/bin/zsh
# Show the email-related DNS records of one or more domains:
# MX, SPF, DMARC, BIMI, MTA-STS, TLS-RPT, plus DKIM and MAIL FROM SPF on request.
#
# Usage: check_email_dns.sh [-r resolver] [-s selector]... [-m subdomain]... [-f file] [domain ...]
#   -r  resolver to query, e.g. 1.1.1.1 (default: the system resolver)
#   -s  DKIM selector to look up at <selector>._domainkey.<domain> (repeatable)
#   -m  custom MAIL FROM subdomain whose SPF to show, e.g. "bounce" (repeatable)
#   -f  file with one domain per line; text after # is ignored
set -euo pipefail

script=$0  # inside a function, zsh sets $0 to the function name

usage() {
    sed -n 's/^# \{0,1\}//; 5,9p' "$script"
    exit 1
}

dig_opts=()
selectors=()
mail_from=()
domains=()

while getopts "r:s:m:f:h" opt; do
    case $opt in
        r) dig_opts+=("@$OPTARG") ;;
        s) selectors+=("$OPTARG") ;;
        m) mail_from+=("$OPTARG") ;;
        f)
            while IFS= read -r line || [ -n "$line" ]; do
                line=${line%%#*}
                line=${line//[[:space:]]/}
                if [ -n "$line" ]; then
                    domains+=("$line")
                fi
            done < "$OPTARG"
            ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))
domains+=("$@")
[ ${#domains[@]} -gt 0 ] || usage

if ! command -v dig > /dev/null; then
    echo "Error: 'dig' is required but not installed." >&2
    exit 1
fi

# Print the records of one type at one name, keeping only lines that match a pattern.
records() {  # records <type> <name> <grep-pattern>
    dig +short "${dig_opts[@]}" "$1" "$2" 2>/dev/null | grep -iE "$3" || true
}

# Print one labeled row; long values are shortened so each row stays readable.
row() {  # row <label> <values>
    local value
    if [ -z "$2" ]; then
        printf '  %-14s %s\n' "$1" "(none)"
        return
    fi
    while IFS= read -r value; do
        [ ${#value} -gt 100 ] && value="${value:0:97}..."
        printf '  %-14s %s\n' "$1" "$value"
    done <<< "$2"
}

for domain in "${domains[@]}"; do
    echo "$domain"
    row "MX" "$(records MX "$domain" '.')"
    row "SPF" "$(records TXT "$domain" '^"v=spf1')"
    row "DMARC" "$(records TXT "_dmarc.$domain" '^"v=DMARC1')"
    row "BIMI" "$(records TXT "default._bimi.$domain" 'v=BIMI1')"
    row "MTA-STS" "$(records TXT "_mta-sts.$domain" 'v=STSv1')"
    row "TLS-RPT" "$(records TXT "_smtp._tls.$domain" 'v=TLSRPTv1')"
    for selector in "${selectors[@]}"; do
        row "DKIM $selector" "$(records TXT "$selector._domainkey.$domain" '.')"
    done
    for subdomain in "${mail_from[@]}"; do
        row "SPF $subdomain" "$(records TXT "$subdomain.$domain" '^"v=spf1')"
    done
    echo
done
