# Overview

These are tools to back up `ForwardEmail.net`'s alias configurations locally and restore them at will. This enables you
to edit the configs offline then push them back quickly, if desired.

This assumes the proper dependencies were installed using `pip install` or `pip3 install`.

# Python Scripts

The easiest way to run these scripts is to use `python3 script.py`.

## check-usage.py

Checks the usage by each `alias` in a specified `domain`.

## fe-full.py

Can do a full export/import to/from `json` files, or partialß backup/restore to/from `csv` files.

# Shell Scripts

## backup_emails.sh

Calls `fe-full export` for each `domain` specified. Allows you to put the API key in one place (if you choose to place
the key in the file vs. your environment).

## check_usage.sh

Checks the usage of `aliases` for a `domain`.

## reset_pop.sh

Deletes all emails for an account. This is useful if you only access your email via `POP3` (and not `IMAP`).

When your email client deletes the emails via `POP3`, `ForwardEmail.net`, at the time of publishing this tool, would
simply move the POP3 deleted emails to the `Trash` folder for that alias (as can be confirmed via `IMAP`). This means
your storage will continue to grow. While ForwardEmail.net likely will clear an email from `Trash` after 30 days, this
can help you reset the mailbox if needed.

Please note this deletes ***ALL YOUR MAL*** including emails in your `Inbox`.

# References

1. [ForwardEmail API Documentation](https://forwardemail.net/en/email-api)
2. [ForwardEmail's Landing Page](https://forwardemail.net/)