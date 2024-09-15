import argparse
import logging
import os

import requests
from requests.auth import HTTPBasicAuth

API_BASE_URL = "https://api.forwardemail.net/v1"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_aliases_with_storage(domain):
    """Fetch the list of aliases with storage details for a domain."""
    url = f"{API_BASE_URL}/domains/{domain}/aliases"
    api_key = os.getenv("API_KEY")
    if not api_key:
        logging.error("API_KEY environment variable not set.")
        raise EnvironmentError("API_KEY environment variable not set.")

    auth = HTTPBasicAuth(api_key, "")
    logging.info(f"GET {url}")
    response = requests.get(url, auth=auth)
    logging.info(f"Response Status Code: {response.status_code}")
    response.raise_for_status()
    return response.json()


def human_readable_size(size_bytes):
    """Convert bytes to a human-readable format (bytes, KB, MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / 1024 ** 2:.2f} MB"


def report_storage(domain):
    """Report storage usage for each alias under the domain."""
    aliases = get_aliases_with_storage(domain)
    for alias in aliases:
        alias_name = alias['name']
        storage_used = alias.get('storage_used', 0)
        max_quota = alias.get('max_quota', 0)

        storage_str = human_readable_size(storage_used)
        max_quota_str = human_readable_size(max_quota)

        logging.info(f"Alias: {alias_name}, Storage Used: {storage_str}, Max Quota: {max_quota_str}")
        print(f"Alias: {alias_name}")
        print(f"  Storage Used: {storage_str}")
        print(f"  Max Quota: {max_quota_str}")


def main():
    parser = argparse.ArgumentParser(description="Report storage usage for email aliases with forwardemail.net API.")
    parser.add_argument('domain', help='The domain to report aliases for')

    args = parser.parse_args()
    report_storage(args.domain)


if __name__ == "__main__":
    main()
