# Overview

These are tools to back up [Forward Email](https://forwardemail.net)'s alias configurations locally and restore them
at will. This enables you to edit the configs offline then push them back quickly, if desired.

They back up alias *settings* (recipients, labels, quotas, and so on), not the mail stored in mailboxes.

The Python scripts read your API key from the `API_KEY` environment variable and run through uv, which provides the
pinned dependencies (see the [root README](../README.md)):

```bash
export API_KEY=...
uv run forwardemail/fe-full.py export example.com example.com.json
```

Every request times out after 30 seconds, and each script exits non-zero if anything fails, so a wrapper or cron job
notices.

# Python Scripts

## check-usage.py

Checks the usage by each `alias` in a specified `domain`.

```bash
uv run forwardemail/check-usage.py example.com
```

## fe-full.py

Does a full export/import of a domain's aliases to/from a `json` file.

```bash
uv run forwardemail/fe-full.py export example.com example.com.json
uv run forwardemail/fe-full.py import example.com example.com.json
```

- `export` follows the API's pagination, so every alias is saved however many there are.
- `import` creates aliases that don't exist and updates the ones that do, matching them by name. It restores every
  setting the export captured: recipients, description, labels, enabled status (and the error code used when
  disabled), recipient verification, IMAP, OpenPGP and S/MIME settings, storage quota, retention, SMTP limit, and the
  vacation responder.
- An IMAP-only alias (one with no recipients) is restored without recipients. When an alias is created with no
  recipients, the API adds the account owner's address, so the script removes it again straight away.

# Shell Scripts

## backup_emails.sh

Calls `fe-full.py export` for each `domain` specified, writing `<domain>.json` to the current directory. Allows you to
put the API key in one place (if you choose to place the key in the file vs. your environment). It stops at the first
domain that fails.

## check_usage.sh

Checks the usage of `aliases` for each `domain` specified, saving each report to `<domain>.usage.txt`. It stops at the
first domain that fails.

## reset_pop.sh

Deletes all emails for an account. This is useful if you only access your email via `POP3` (and not `IMAP`).

When your email client deletes the emails via `POP3`, Forward Email, at the time of publishing this tool, would
simply move the POP3 deleted emails to the `Trash` folder for that alias (as can be confirmed via `IMAP`). This means
your storage will continue to grow. While Forward Email likely will clear an email from `Trash` after 30 days, this
can help you reset the mailbox if needed.

Please note this deletes ***ALL YOUR MAIL*** including emails in your `Inbox`.

# References

1. [Forward Email API Documentation](https://forwardemail.net/en/email-api)
2. [Forward Email's Landing Page](https://forwardemail.net/)
