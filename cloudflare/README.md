# Overview

[Cloudflare](https://www.cloudflare.com) is a service provider known
for [DNS](https://en.wikipedia.org/wiki/Domain_Name_System), [CDN](https://en.wikipedia.org/wiki/Content_delivery_network),
storage and many other services.

Their developer API is great.

Occasionally, some small scripts/tools will be added here when I get a chance to clean those up, remove my API keys and
such.

## Purge Cache

`flush_cache.sh` takes your API token with `purge:cache` permissions and lets you specify your domain on a command line
for which you want to purge all cache entries (and force Cloudflare to refresh its cache).

It is a quick way to flush/purge the cache without logging in to your Cloudflare portal, especially if you have many
domains that you copy content to from the command line like I do (I use [rsync](https://en.wikipedia.org/wiki/Rsync))

## Back Up and Restore DNS Records

`zonetool.py` exports and imports the DNS records of a Cloudflare zone. It reads an API token from the `CF_TOKEN`
environment variable: `export` and `list` need Zone:Read and DNS:Read permissions on the zone, while `import`,
`restore`, and `delete_all` need DNS:Edit.

```bash
export CF_TOKEN=...
uv run cloudflare/zonetool.py example.com export example.com.txt    # BIND file: every record, Cloudflare's own format
uv run cloudflare/zonetool.py example.com import example.com.txt    # load a BIND file back in
uv run cloudflare/zonetool.py example.com list example.com.json     # JSON snapshot, including comments and tags
uv run cloudflare/zonetool.py example.com restore example.com.json  # recreate records from a snapshot
uv run cloudflare/zonetool.py example.com delete_all                # back up, then delete every record
```

- `export` and `import` are the complete round trip. Cloudflare limits imports to 256 KiB files and 3 requests a
  minute.
- `restore` recreates the records in a snapshot. When Cloudflare reports that a record already exists, the record with
  the same type, name, and value gets the snapshot's TTL, proxy status, comment, and tags. Records that share a name
  (several MX or TXT records, say) are matched by value, so the wrong one is never overwritten.
- `delete_all` asks twice, then writes a timestamped `<domain>.<date>-<time>.before-delete.txt` BIND backup before
  deleting anything.
- Every command follows the API's pagination, and the script exits non-zero if anything fails.

## Dynamic DNS

`ddns.sh` points an existing A record at the public IPv4 address of the machine it runs on, and does nothing if the
address hasn't changed. It needs `CF_TOKEN` with DNS:Edit permission on the zone, plus `curl` and `jq`.

```bash
export CF_TOKEN=...
cloudflare/ddns.sh example.com home.example.com
```

It changes only the record's address (a `PATCH`), so the record's TTL, proxy status, comment, and tags stay as they
are. Run it from cron or launchd to keep the record current.
