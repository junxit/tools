"""Back up and restore Forward Email aliases as JSON.

An export captures every alias on a domain; an import recreates missing aliases
and updates existing ones with every setting the export captured.

Typical usage example:

    export API_KEY=...
    uv run forwardemail/fe-full.py export example.com example.com.json
    uv run forwardemail/fe-full.py import example.com example.com.json

Attributes:
    API_BASE_URL: Root of the Forward Email REST API.
    TIMEOUT: Seconds to wait for each HTTP request.
    PAGE_LIMIT: Aliases requested per page (the API's maximum).
    RESTORABLE_FIELDS: Alias fields the create/update endpoints accept as-is.
    VACATION_FIELDS: Keys of an export's nested vacation_responder object.
"""

import argparse
import json
import logging
import os
import sys

import requests

API_BASE_URL = "https://api.forwardemail.net/v1"
TIMEOUT = 30
PAGE_LIMIT = 1000
RESTORABLE_FIELDS = (
    "name",
    "recipients",
    "description",
    "labels",
    "has_recipient_verification",
    "is_enabled",
    "error_code_if_disabled",
    "has_imap",
    "has_pgp",
    "public_key",
    "has_smime",
    "smime_certificate",
    "has_wkd_disabled",
    "retention",
    "smtp_limit",
)
VACATION_FIELDS = ("is_enabled", "start_date", "end_date", "subject", "message")

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def make_session():
    """Create an HTTP session authenticated with the API_KEY environment variable.

    Returns:
        A requests.Session that sends the key as the Basic-auth username.

    Raises:
        SystemExit: If API_KEY is not set.
    """
    api_key = os.getenv("API_KEY")
    if not api_key:
        sys.exit("API_KEY environment variable not set.")
    session = requests.Session()
    session.auth = (api_key, "")
    return session


def get_aliases(session, domain):
    """Fetch every alias for a domain, following the API's pagination headers.

    Args:
        session: An authenticated session from make_session().
        domain: The domain whose aliases to list.

    Returns:
        A list of alias objects as returned by the API.
    """
    url = f"{API_BASE_URL}/domains/{domain}/aliases"
    aliases = []
    page = 1
    while True:
        logging.info(f"GET {url} (page {page})")
        response = session.get(
            url, params={"page": page, "limit": PAGE_LIMIT}, timeout=TIMEOUT
        )
        logging.info(f"Response Status Code: {response.status_code}")
        response.raise_for_status()
        batch = response.json()
        aliases.extend(batch)
        if not batch or page >= int(response.headers.get("X-Page-Count", page)):
            return aliases
        page += 1


def export_aliases_to_json(session, domain, json_file):
    """Export every alias on a domain to a JSON file.

    Args:
        session: An authenticated session from make_session().
        domain: The domain to export.
        json_file: Path of the JSON file to write.
    """
    aliases = get_aliases(session, domain)
    with open(json_file, "w") as jf:
        json.dump(aliases, jf, indent=4)

    logging.info(f"Total aliases exported: {len(aliases)}")


def quota_string(size_bytes):
    """Express a byte count in the form the API expects for max_quota.

    Args:
        size_bytes: The quota in bytes, as an export reports it.

    Returns:
        A string such as "10 GB", or the plain byte count when no unit divides it evenly.

    Example:
        >>> quota_string(10 * 1024**3)
        '10 GB'
    """
    for unit, size in (("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if size_bytes >= size and size_bytes % size == 0:
            return f"{size_bytes // size} {unit}"
    return str(size_bytes)


def alias_payload(alias):
    """Build a create/update request body that restores everything an export captured.

    Args:
        alias: One alias object from an export.

    Returns:
        A dict of API input fields. The quota is converted to a unit string and the nested
        vacation responder is flattened into vacation_responder_* fields.
    """
    payload = {
        field: alias[field]
        for field in RESTORABLE_FIELDS
        if alias.get(field) is not None
    }
    max_quota = alias.get("max_quota")
    if max_quota:
        payload["max_quota"] = (
            quota_string(max_quota) if isinstance(max_quota, int) else max_quota
        )
    vacation = alias.get("vacation_responder") or {}
    for field in VACATION_FIELDS:
        if vacation.get(field) is not None:
            payload[f"vacation_responder_{field}"] = vacation[field]
    return payload


def import_aliases_from_json(session, domain, json_file):
    """Create missing aliases and update existing ones from a JSON export.

    Existing aliases are matched by name and updated by ID, so catch-all and regex
    aliases never end up in a URL path.

    Args:
        session: An authenticated session from make_session().
        domain: The domain to restore into.
        json_file: Path of a JSON file written by the export command.

    Returns:
        The number of aliases that failed to import.
    """
    with open(json_file) as jf:
        aliases = json.load(jf)

    url = f"{API_BASE_URL}/domains/{domain}/aliases"
    existing = {alias["name"]: alias["id"] for alias in get_aliases(session, domain)}

    total_added = 0
    total_updated = 0
    total_failed = 0

    logging.info(f"Total records to import: {len(aliases)}")

    for alias in aliases:
        name = alias["name"]
        payload = alias_payload(alias)
        try:
            if name in existing:
                logging.info(f"PUT {url}/{existing[name]} ({name})")
                response = session.put(
                    f"{url}/{existing[name]}", json=payload, timeout=TIMEOUT
                )
                response.raise_for_status()
                total_updated += 1
            else:
                logging.info(f"POST {url} ({name})")
                response = session.post(url, json=payload, timeout=TIMEOUT)
                response.raise_for_status()
                if not payload.get("recipients"):
                    # On create, the API replaces empty recipients with the account's own
                    # address; an update is the only way to clear them again.
                    alias_url = f"{url}/{response.json()['id']}"
                    session.put(
                        alias_url, json={"recipients": []}, timeout=TIMEOUT
                    ).raise_for_status()
                total_added += 1
        except requests.RequestException as e:
            detail = e.response.text if e.response is not None else ""
            logging.error(f"Failed to process alias {name}: {e} {detail}".rstrip())
            total_failed += 1

    total_processed = total_added + total_updated + total_failed
    logging.info(f"Total processed: {total_processed}")
    logging.info(f"Total added: {total_added}")
    logging.info(f"Total updated: {total_updated}")
    logging.info(f"Total failed: {total_failed}")
    return total_failed


def main():
    """Parse the command line and run the export or import command.

    Returns:
        The process exit status: 0 on success, 1 if any request failed.
    """
    parser = argparse.ArgumentParser(
        description="Manage email aliases with forwardemail.net API using JSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand for exporting aliases to JSON
    export_parser = subparsers.add_parser("export", help="Export aliases to JSON")
    export_parser.add_argument("domain", help="The domain to export aliases from")
    export_parser.add_argument("json_file", help="Output JSON file")

    # Subcommand for importing aliases from JSON
    import_parser = subparsers.add_parser(
        "import", help="Import aliases from JSON and create/update them"
    )
    import_parser.add_argument("domain", help="The domain to create/update aliases for")
    import_parser.add_argument("json_file", help="Input JSON file")

    args = parser.parse_args()
    session = make_session()

    try:
        if args.command == "export":
            export_aliases_to_json(session, args.domain, args.json_file)
            return 0
        return (
            1 if import_aliases_from_json(session, args.domain, args.json_file) else 0
        )
    except requests.RequestException as e:
        logging.error(f"Request failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
