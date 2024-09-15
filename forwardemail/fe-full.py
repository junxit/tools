import argparse
import json
import logging
import os

import requests
from requests.auth import HTTPBasicAuth

API_BASE_URL = "https://api.forwardemail.net/v1"
# Access the API key from the environment variable
API_KEY = os.getenv('API_KEY')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_aliases(domain):
    """Fetch the list of aliases for a domain."""
    url = f"{API_BASE_URL}/domains/{domain}/aliases"
    auth = HTTPBasicAuth(API_KEY, "")
    logging.info(f"GET {url}")
    response = requests.get(url, auth=auth)
    logging.info(f"Response Status Code: {response.status_code}")
    response.raise_for_status()
    return response.json()


def export_aliases_to_json(domain, json_file):
    """Export aliases to a JSON file."""
    aliases = get_aliases(domain)
    with open(json_file, 'w') as jf:
        json.dump(aliases, jf, indent=4)

    logging.info(f"Total aliases exported: {len(aliases)}")


def create_or_update_alias(domain, alias_name, recipients):
    """Create or update an alias using the API."""
    url = f"{API_BASE_URL}/domains/{domain}/aliases"
    auth = HTTPBasicAuth(API_KEY, "")
    data = {
        "name": alias_name,
        "recipients": recipients
    }
    logging.info(f"POST {url}")
    response = requests.post(url, json=data, auth=auth)

    if response.status_code == 400:
        if response.json().get('message') == 'Alias already exists for domain.':
            update_url = f"{url}/{alias_name}"
            logging.info(f"PUT {update_url}")
            update_response = requests.put(update_url, json=data, auth=auth)
            logging.info(f"Response Status Code: {update_response.status_code}")
            update_response.raise_for_status()
            return 'updated'
        else:
            logging.info(f"Response Status Code: {response.status_code}")
            response.raise_for_status()
    else:
        logging.info(f"Response Status Code: {response.status_code}")
        response.raise_for_status()
        return 'created'


def import_aliases_from_json(domain, json_file):
    """Import aliases from a JSON file and create/update them."""
    with open(json_file, 'r') as jf:
        aliases = json.load(jf)

    total_added = 0
    total_updated = 0
    total_failed = 0

    logging.info(f"Total records to import: {len(aliases)}")

    for alias in aliases:
        try:
            result = create_or_update_alias(domain, alias["name"], alias["recipients"])
            if result == 'created':
                total_added += 1
            elif result == 'updated':
                total_updated += 1
        except Exception as e:
            logging.error(f"Failed to process alias {alias['name']}: {str(e)}")
            total_failed += 1

    total_processed = total_added + total_updated + total_failed
    logging.info(f"Total processed: {total_processed}")
    logging.info(f"Total added: {total_added}")
    logging.info(f"Total updated: {total_updated}")
    logging.info(f"Total failed: {total_failed}")


def main():
    parser = argparse.ArgumentParser(description="Manage email aliases with forwardemail.net API using JSON.")
    subparsers = parser.add_subparsers(dest="command")

    # Subcommand for exporting aliases to JSON
    export_parser = subparsers.add_parser('export', help='Export aliases to JSON')
    export_parser.add_argument('domain', help='The domain to export aliases from')
    export_parser.add_argument('json_file', help='Output JSON file')

    # Subcommand for importing aliases from JSON
    import_parser = subparsers.add_parser('import', help='Import aliases from JSON and create/update them')
    import_parser.add_argument('domain', help='The domain to create/update aliases for')
    import_parser.add_argument('json_file', help='Input JSON file')

    args = parser.parse_args()

    if args.command == 'export':
        export_aliases_to_json(args.domain, args.json_file)
    elif args.command == 'import':
        import_aliases_from_json(args.domain, args.json_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
