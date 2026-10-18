# Overview

DNS tools that work with any provider. The Python scripts run through uv (see the [root README](../README.md)); the
shell scripts need `zsh`, plus `dig` (`check_email_dns.sh`) or `curl` and `jq` (`rdap-lookup.zsh`).

## scandns.py

Rebuilds a BIND zone file from DNS answers, for a DNS host that offers no zone export. Give it the hostnames you know
about, either as arguments or as a file in any format that mentions them (a pasted dashboard page works). It queries
each one, plus `_dmarc` for each, and writes the answers in BIND format, ready for an import such as Cloudflare's.

```bash
uv run dns/scandns.py example.com www.example.com mail.example.com
uv run dns/scandns.py example.com --hosts-file pasted.txt -o example.com.scan.txt
```

- Queries go to one of the zone's own nameservers, so TTLs are the configured values. Use `--server` to ask a
  specific resolver instead.
- It writes the real SOA and NS records. A name that has a CNAME is written with the CNAME alone. Long TXT records,
  such as DKIM keys, keep their 255-character strings.
- DNS can't list a zone, so anything you don't name (wildcards, say) is missed. Check the result before importing it.

## flatten-spf.py

Flattens an SPF record into the `ip4:`/`ip6:` ranges it currently authorizes, which keeps a record under SPF's limit
of 10 DNS lookups. It expands `include:`, `a`, `mx`, and `redirect=`. It keeps `exists`, `ptr`, macros, and
non-pass terms such as `-include:` as they are, with a note, because those can't be flattened.

```bash
uv run dns/flatten-spf.py example.com
uv run dns/flatten-spf.py example.com --source "v=spf1 include:_spf.example.net ~all"
```

Providers change their addresses without notice, so a flattened record goes stale. Keep the unflattened source
somewhere (as text, or in a TXT record on a hostname of your choosing), and run `--check` regularly. It exits 1 and
lists the differences when the published record no longer matches the flattened source:

```bash
uv run dns/flatten-spf.py example.com --source _spf-source.example.com --check
```

## check_email_dns.sh

Shows a domain's email-related DNS records: MX, SPF, DMARC, BIMI, MTA-STS, and TLS-RPT, plus DKIM for the selectors
you name and SPF for custom MAIL FROM subdomains.

```bash
dns/check_email_dns.sh example.com example.org
dns/check_email_dns.sh -r 1.1.1.1 -s selector1 -m bounce -f domains.txt
```

`-f` reads one domain per line from a file; text after `#` is ignored.

## rdap-lookup.zsh

Looks up domain registration data (status, dates, nameservers) over
[RDAP](https://en.wikipedia.org/wiki/Registration_Data_Access_Protocol), the successor to WHOIS. It finds each TLD's
RDAP server in IANA's bootstrap file, so it works for TLDs without a WHOIS server, such as `.app` and `.dev`.

```bash
dns/rdap-lookup.zsh example.com example.dev
RDAP_FULL_JSON=1 dns/rdap-lookup.zsh example.app
```

### RDAP by hand

RDAP is plain HTTPS returning JSON, so `curl` works too. The server for each TLD is listed in IANA's bootstrap file:

```bash
curl https://data.iana.org/rdap/dns.json                                 # RDAP servers by TLD
curl https://pubapi.registry.google/rdap/domain/example.app              # a domain (Google Registry's server)
curl https://pubapi.registry.google/rdap/nameserver/ns1.example.dev      # a nameserver
curl https://pubapi.registry.google/rdap/help                            # the server's capabilities
```
