# tools

Random tools that can be useful in some situations: small command-line utilities, one folder per
service, plus a few write-ups.

## Cloudflare

Tools for [Cloudflare](https://www.cloudflare.com)'s services. See [cloudflare/README.md](cloudflare/README.md).

- [zonetool.py](cloudflare/zonetool.py) — back up and restore a zone's DNS records (BIND export/import,
  JSON snapshot/restore, and a delete-everything command that backs up first).
- [flush_cache.sh](cloudflare/flush_cache.sh) — purge a zone's whole CDN cache.
- [ddns.sh](cloudflare/ddns.sh) — point an A record at this machine's current public IP (dynamic DNS).

## Forward Email

Tools for [Forward Email](https://forwardemail.net)'s services. They have great API documentation
[here](https://forwardemail.net/en/email-api). See [forwardemail/README.md](forwardemail/README.md).

- [fe-full.py](forwardemail/fe-full.py) — back up a domain's alias settings to JSON and restore them.
- [check-usage.py](forwardemail/check-usage.py) — report the storage each alias uses.
- [backup_emails.sh](forwardemail/backup_emails.sh), [check_usage.sh](forwardemail/check_usage.sh) — run
  the two scripts above for a list of domains.
- [reset_pop.sh](forwardemail/reset_pop.sh) — empty a POP3-only mailbox.

## DNS

Provider-agnostic DNS tools. See [dns/README.md](dns/README.md).

- [scandns.py](dns/scandns.py) — rebuild a BIND zone file from DNS answers, for hosts with no export.
- [flatten-spf.py](dns/flatten-spf.py) — flatten an SPF record into IP ranges, and check it for drift.
- [check_email_dns.sh](dns/check_email_dns.sh) — show a domain's MX, SPF, DKIM, DMARC, BIMI, MTA-STS, and
  TLS-RPT records.
- [rdap-lookup.zsh](dns/rdap-lookup.zsh) — look up domain registration data over RDAP.

## Claude Code

Configuration for [Claude Code](https://claude.com/claude-code).

[claude-telemetry.zsh](claude-code/claude-telemetry.zsh) — environment variables that disable
Claude Code's non-essential network traffic (usage analytics, error reporting, feature flags,
auto-updates, and the transcript-uploading `/feedback` command). Source it from your shell profile.
Side effects: Claude Code stops updating itself, so run `claude update` yourself, and Remote Control
is unavailable while feature flags are off. To undo, unset the variables; setting some of them to `0`
still opts out. Shell-profile exports only reach sessions started from a shell that loaded them; the
same variables can go in the `env` block of `~/.claude/settings.json`, which applies however Claude
Code is launched.

[status-line-prompt.md](claude-code/status-line-prompt.md) — prompt for generating the status line
script.

## Best Practices

Write-ups on engineering practice rather than code.

[Small-PRs.md](best-practices/Small-PRs.md) — the case for small pull requests: why review quality and
merge latency degrade with size, and the patterns for splitting work that *feels* atomic
(refactor-then-behave, vertical slices, expand/migrate/contract, stacked PRs, and dark launches).

## Prerequisites

- macOS or Linux. Developed on macOS (Apple silicon); CI runs on Ubuntu 24.04 (x86_64).
- [uv](https://docs.astral.sh/uv/) 0.13.1, the version CI pins. uv installs Python 3.15.0 (pinned in
  `.python-version`) and the exact dependency versions in `uv.lock`, so no separate Python or pip
  setup is needed.
- zsh for the shell scripts (the macOS default shell; `apt install zsh` on Linux).
- `curl` and `jq` for the shell scripts, and `dig` for `dns/check_email_dns.sh` (included with macOS;
  `dnsutils` on Debian/Ubuntu).
- API credentials, read from environment variables: `CF_TOKEN` for Cloudflare and `API_KEY` for
  Forward Email. Nothing secret belongs in this repo.

## Installation

```bash
git clone https://github.com/junxit/tools.git
cd tools
uv sync --locked
```

## How to Run

Run the Python tools through uv so they use the pinned environment; the shell scripts run directly.
Each folder's README has the details.

```bash
export CF_TOKEN=...   # Cloudflare API token
uv run cloudflare/zonetool.py example.com export example.com.txt
cloudflare/ddns.sh example.com home.example.com

export API_KEY=...    # Forward Email API key
uv run forwardemail/fe-full.py export example.com example.com.json

uv run dns/flatten-spf.py example.com
dns/check_email_dns.sh example.com
dns/rdap-lookup.zsh example.com
```

## How to Test

There is no automated test suite. CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) lints
every pull request and push to `main`; run the same checks locally with:

```bash
uv run --locked ruff check
uv run --locked ruff format --check
git ls-files -z '*.sh' '*.zsh' | xargs -0 uv run --locked shellcheck -s bash
```

## How to Delete / Uninstall

```bash
# Remove Python cache files
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# Remove the virtual environment and the linter cache
rm -rf .venv .ruff_cache

# Remove the files the scripts write (backups may hold personal data; keep any you need first)
rm -f ./*.json ./*.txt ./*.usage.txt ./*.before-delete.txt ./*.scan.txt
```

To remove everything, delete the cloned directory.

## Assumptions

- Credentials come from environment variables. The Forward Email wrapper scripts still contain an
  `API_KEY` placeholder to edit; don't commit a real key.
- The scripts write their output files to the current directory. `.gitignore` keeps the usual output
  names out of git, because backups contain personal data such as alias recipients.
- The restore commands (`fe-full.py import`, `zonetool.py import`/`restore`/`delete_all`) change live
  settings. Try them on a test alias or zone before relying on them.
