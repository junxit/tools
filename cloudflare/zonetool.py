"""Back up and restore the DNS records of a Cloudflare zone.

Typical usage example:

    export CF_TOKEN=...
    uv run cloudflare/zonetool.py example.com export example.com.txt
    uv run cloudflare/zonetool.py example.com import example.com.txt
    uv run cloudflare/zonetool.py example.com list example.com.json
    uv run cloudflare/zonetool.py example.com restore example.com.json
    uv run cloudflare/zonetool.py example.com delete_all

Attributes:
    CF_TOKEN: Cloudflare API token, read from the environment.
    CF_API_BASE: Root of the Cloudflare v4 API.
    TIMEOUT: Seconds to wait for each HTTP request.
    PER_PAGE: DNS records requested per page.
    DUPLICATE_RECORD_CODES: Error codes Cloudflare returns when an identical record exists.
    UPDATABLE_FIELDS: Settings restore re-applies to a record that already exists.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import requests

CF_TOKEN = os.getenv("CF_TOKEN")
CF_API_BASE = "https://api.cloudflare.com/client/v4"
TIMEOUT = 30
PER_PAGE = 5000
DUPLICATE_RECORD_CODES = {81057, 81058}
UPDATABLE_FIELDS = ("ttl", "proxied", "comment", "tags", "settings")

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def make_session():
    """Create an HTTP session that authenticates with CF_TOKEN.

    Returns:
        A requests.Session carrying the bearer token on every request.
    """
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {CF_TOKEN}"
    return session


def fetch_zone_id(session, domain):
    """Fetch the Zone ID for a given domain.

    Args:
        session: An authenticated session from make_session().
        domain: The zone name, e.g. "example.com".

    Returns:
        The zone's ID.

    Raises:
        LookupError: If no zone by that name is visible to the token.
    """
    response = session.get(
        f"{CF_API_BASE}/zones", params={"name": domain}, timeout=TIMEOUT
    )
    response.raise_for_status()
    zones = response.json()["result"]
    if not zones:
        raise LookupError(f"No zone named {domain} is visible to this token.")
    return zones[0]["id"]


def list_records(session, zone_id, **filters):
    """Fetch every DNS record in a zone, following pagination.

    Args:
        session: An authenticated session from make_session().
        zone_id: The zone to read.
        **filters: Optional list filters such as type="MX" or name="www.example.com".

    Returns:
        A list of DNS record objects.
    """
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"
    records = []
    page = 1
    while True:
        params = {**filters, "page": page, "per_page": PER_PAGE}
        response = session.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        records.extend(data["result"])
        if page >= data["result_info"].get("total_pages", 1):
            return records
        page += 1


def export_dns(session, zone_id, filename):
    """Export every DNS record in the zone to a BIND file.

    Args:
        session: An authenticated session from make_session().
        zone_id: The zone to export.
        filename: Path of the BIND file to write.
    """
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records/export"
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    # Write the raw response content directly to a file
    with open(filename, "wb") as file:
        file.write(response.content)

    logging.info(f"Exported DNS records to {filename}.")


def import_dns(session, zone_id, filename):
    """Import DNS records from a BIND file.

    Args:
        session: An authenticated session from make_session().
        zone_id: The zone to import into.
        filename: Path of a BIND file, such as one written by export_dns().
    """
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records/import"
    with open(filename, "rb") as file:
        response = session.post(url, files={"file": file}, timeout=TIMEOUT)
    response.raise_for_status()

    result = response.json()["result"]
    logging.info(
        f"Imported {result.get('recs_added')} of {result.get('total_records_parsed')} "
        f"records from {filename}."
    )


def list_dns(session, zone_id, filename):
    """Save every DNS record in the zone to a JSON file.

    Args:
        session: An authenticated session from make_session().
        zone_id: The zone to read.
        filename: Path of the JSON file to write.
    """
    records = list_records(session, zone_id)
    logging.info(f"Found {len(records)} records.")

    snapshot = {"result": records, "result_info": {"count": len(records)}}
    with open(filename, "w") as file:
        json.dump(snapshot, file, indent=4)

    logging.info(f"Listed DNS records to {filename}.")


def record_payload(record):
    """Build a create request body from a listed record, leaving out read-only fields.

    Args:
        record: One record object from a JSON snapshot.

    Returns:
        A dict containing only fields the create endpoint accepts.
    """
    payload = {"type": record["type"], "name": record["name"], "ttl": record["ttl"]}
    # Structured types (SRV, CAA, ...) are defined by `data`; the rest by `content`.
    if record.get("data"):
        payload["data"] = record["data"]
    else:
        payload["content"] = record["content"]
    if record.get("priority") is not None:
        payload["priority"] = record["priority"]
    if record.get("proxiable"):
        payload["proxied"] = record.get("proxied", False)
    for field in ("comment", "tags", "settings"):
        if record.get(field):
            payload[field] = record[field]
    return payload


def same_record(a, b):
    """Report whether two records have the same type, name, value, and priority.

    Args:
        a: A record object.
        b: Another record object.

    Returns:
        True if both describe the same DNS record, so a multi-value set such as several
        MX records on one name never matches the wrong member.
    """
    value = "data" if b.get("data") else "content"
    return all(a.get(key) == b.get(key) for key in ("type", "name", value, "priority"))


def restore_dns(session, zone_id, filename):
    """Recreate the records in a JSON snapshot, updating identical records in place.

    Args:
        session: An authenticated session from make_session().
        zone_id: The zone to restore into.
        filename: Path of a JSON file written by list_dns().

    Returns:
        The number of records that failed to restore.
    """
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"
    with open(filename) as file:
        records = json.load(file)["result"]

    created_count = 0
    updated_count = 0
    unchanged_count = 0
    failed_count = 0

    for record in records:
        label = f"{record['name']} ({record['type']})"
        payload = record_payload(record)
        try:
            response = session.post(url, json=payload, timeout=TIMEOUT)
            if response.ok:
                created_count += 1
                logging.info(f"Created record: {label}")
                continue

            codes = {error.get("code") for error in response.json().get("errors", [])}
            if not codes & DUPLICATE_RECORD_CODES:
                failed_count += 1
                logging.error(f"Failed to create record: {label}: {response.text}")
                continue

            # An identical record already exists; bring its settings in line with the snapshot.
            candidates = list_records(
                session, zone_id, type=record["type"], name=record["name"]
            )
            matches = [
                existing for existing in candidates if same_record(existing, record)
            ]
            if not matches:
                failed_count += 1
                logging.error(
                    f"Cloudflare reported a duplicate but no exact match: {label}"
                )
                continue

            existing = matches[0]
            changes = {
                field: payload[field]
                for field in UPDATABLE_FIELDS
                if field in payload and existing.get(field) != payload[field]
            }
            if not changes:
                unchanged_count += 1
                logging.info(f"Already present: {label}")
                continue

            patch_response = session.patch(
                f"{url}/{existing['id']}", json=changes, timeout=TIMEOUT
            )
            patch_response.raise_for_status()
            updated_count += 1
            logging.info(f"Updated record: {label} ({', '.join(changes)})")
        except requests.RequestException as e:
            failed_count += 1
            logging.error(f"Failed to restore record: {label}: {e}")

    logging.info(
        f"Restore summary: {created_count} created, {updated_count} updated, "
        f"{unchanged_count} unchanged, {failed_count} failed."
    )
    return failed_count


def delete_all_dns(session, zone_id, domain):
    """Back up the zone to a BIND file, then delete every DNS record in it.

    Args:
        session: An authenticated session from make_session().
        zone_id: The zone to empty.
        domain: The zone name, used to name the backup file.

    Returns:
        The number of records that failed to delete (0 if the user cancels).
    """
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"

    # First confirmation
    confirm = input("Are you sure you want to delete all DNS records? (yes/no): ")
    if confirm.lower() != "yes":
        logging.info("Operation cancelled.")
        return 0

    # Second confirmation
    confirm = input("This action is irreversible. Are you really sure? (yes/no): ")
    if confirm.lower() != "yes":
        logging.info("Operation cancelled.")
        return 0

    backup = f"{domain}.{datetime.now():%Y%m%d-%H%M%S}.before-delete.txt"
    export_dns(session, zone_id, backup)

    records = list_records(session, zone_id)
    logging.info(f"Found {len(records)} records.")

    deleted_count = 0
    failed_count = 0

    for record in records:
        try:
            response = session.delete(f"{url}/{record['id']}", timeout=TIMEOUT)
            response.raise_for_status()
            deleted_count += 1
        except requests.RequestException as e:
            failed_count += 1
            logging.error(
                f"Failed to delete record: {record['name']} ({record['type']}): {e}"
            )

    logging.info(
        f"Deleted {deleted_count} records. Failed to delete {failed_count} records. "
        f"Backup: {backup}"
    )
    return failed_count


def main():
    """Parse the command line and run the requested command.

    Returns:
        The process exit status: 0 on success, 1 on any failure.
    """
    parser = argparse.ArgumentParser(
        description="Cloudflare DNS Record Management Tool"
    )
    parser.add_argument("domain", help="The domain to manage DNS records for")
    parser.add_argument(
        "command",
        choices=["export", "import", "list", "restore", "delete_all"],
        help="The command to execute",
    )
    parser.add_argument(
        "filename", nargs="?", help="The file to export to or import from"
    )

    args = parser.parse_args()
    if args.command != "delete_all" and not args.filename:
        parser.error(f"the {args.command} command needs a filename")

    if not CF_TOKEN:
        logging.error("CF_TOKEN environment variable is not set.")
        return 1

    session = make_session()
    try:
        zone_id = fetch_zone_id(session, args.domain)
        if args.command == "export":
            export_dns(session, zone_id, args.filename)
        elif args.command == "import":
            import_dns(session, zone_id, args.filename)
        elif args.command == "list":
            list_dns(session, zone_id, args.filename)
        elif args.command == "restore":
            return 1 if restore_dns(session, zone_id, args.filename) else 0
        else:
            return 1 if delete_all_dns(session, zone_id, args.domain) else 0
    except (requests.RequestException, LookupError) as e:
        detail = getattr(getattr(e, "response", None), "text", "")
        logging.error(f"{e} {detail}".rstrip())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
