"""Report how much storage each Forward Email alias on a domain uses.

Typical usage example:

    export API_KEY=...
    uv run forwardemail/check-usage.py example.com

Attributes:
    API_BASE_URL: Root of the Forward Email REST API.
    TIMEOUT: Seconds to wait for each HTTP request.
    PAGE_LIMIT: Aliases requested per page (the API's maximum).
"""

import argparse
import logging
import os
import sys

import requests

API_BASE_URL = "https://api.forwardemail.net/v1"
TIMEOUT = 30
PAGE_LIMIT = 1000

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


def get_aliases_with_storage(session, domain):
    """Fetch every alias, with storage details, following the API's pagination headers.

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


def human_readable_size(size_bytes):
    """Convert bytes to a human-readable format (bytes, KB, MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / 1024**2:.2f} MB"


def report_storage(session, domain):
    """Report storage usage for each alias under the domain.

    Args:
        session: An authenticated session from make_session().
        domain: The domain to report on.
    """
    aliases = get_aliases_with_storage(session, domain)
    for alias in aliases:
        alias_name = alias["name"]
        storage_used = alias.get("storage_used", 0)
        max_quota = alias.get("max_quota", 0)

        storage_str = human_readable_size(storage_used)
        max_quota_str = human_readable_size(max_quota)

        logging.info(
            f"Alias: {alias_name}, Storage Used: {storage_str}, Max Quota: {max_quota_str}"
        )
        print(f"Alias: {alias_name}")
        print(f"  Storage Used: {storage_str}")
        print(f"  Max Quota: {max_quota_str}")


def main():
    """Parse the command line and print the storage report.

    Returns:
        The process exit status: 0 on success, 1 if a request failed.
    """
    parser = argparse.ArgumentParser(
        description="Report storage usage for email aliases with forwardemail.net API."
    )
    parser.add_argument("domain", help="The domain to report aliases for")

    args = parser.parse_args()
    session = make_session()
    try:
        report_storage(session, args.domain)
    except requests.RequestException as e:
        logging.error(f"Request failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
