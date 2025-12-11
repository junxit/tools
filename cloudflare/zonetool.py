import os
import requests
import argparse
import logging
import json

CF_TOKEN = os.getenv('CF_TOKEN')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cloudflare API Base URL
CF_API_BASE = 'https://api.cloudflare.com/client/v4'

def fetch_zone_id(domain):
    """Fetch the Zone ID for a given domain."""
    url = f"{CF_API_BASE}/zones"
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {"name": domain}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    
    if data['success']:
        return data['result'][0]['id']
    else:
        raise Exception("Failed to fetch zone ID")

def export_dns(domain, filename):
    """Export DNS records to a text file."""
    zone_id = fetch_zone_id(domain)
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records/export"
    
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Write the raw response content directly to a file
    with open(filename, 'wb') as file:
        file.write(response.content)
    
    logging.info(f"Exported DNS records to {filename}.")

def import_dns(domain, filename):
    """Import DNS records from a text file."""
    zone_id = fetch_zone_id(domain)
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records/import"
    
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    with open(filename, 'r') as file:
        data = file.read()
    
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    
    logging.info(f"Imported DNS records from {filename}.")

def list_dns(domain, filename):
    """List DNS records and save to a JSON file."""
    zone_id = fetch_zone_id(domain)
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"
    
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    logging.info(f"Found {len(data['result'])} records.")
    
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)
    
    logging.info(f"Listed DNS records to {filename}.")

def restore_dns(domain, filename):
    """Restore DNS records from a JSON file."""
    zone_id = fetch_zone_id(domain)
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"
    
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    with open(filename, 'r') as file:
        records = json.load(file)
    
    created_count = 0
    updated_count = 0
    failed_count = 0
    
    for record in records['result']:
        # Remove the record ID if it exists because it's not needed for POST
        record.pop('id', None)
        
        # Attempt to create the record first
        response = requests.post(url, headers=headers, json=record)
        
        if response.status_code == 200:  # Record created successfully
            created_count += 1
            logging.info(f"Created record: {record['name']} ({record['type']})")
        elif response.status_code == 409:  # Record already exists, try to update
            logging.info(f"Record already exists, attempting to update: {record['name']} ({record['type']})")
            # Find the existing record's ID
            existing_record_url = f"{url}?name={record['name']}&type={record['type']}"
            get_response = requests.get(existing_record_url, headers=headers)
            get_response.raise_for_status()
            existing_data = get_response.json()
            if existing_data['success'] and existing_data['result']:
                record_id = existing_data['result'][0]['id']
                update_url = f"{url}/{record_id}"
                put_response = requests.put(update_url, headers=headers, json=record)
                if put_response.status_code == 200:
                    updated_count += 1
                    logging.info(f"Updated record: {record['name']} ({record['type']})")
                else:
                    failed_count += 1
                    logging.error(f"Failed to update record: {record['name']} ({record['type']})")
            else:
                failed_count += 1
                logging.error(f"Failed to find existing record for update: {record['name']} ({record['type']})")
        else:
            failed_count += 1
            logging.error(f"Failed to create record: {record['name']} ({record['type']})")

    logging.info(f"Restore summary: {created_count} created, {updated_count} updated, {failed_count} failed.")

def delete_all_dns(domain):
    """Delete all DNS records for a domain."""
    zone_id = fetch_zone_id(domain)
    url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"
    
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # First confirmation
    confirm = input("Are you sure you want to delete all DNS records? (yes/no): ")
    if confirm.lower() != 'yes':
        logging.info("Operation cancelled.")
        return
    
    # Second confirmation
    confirm = input("This action is irreversible. Are you really sure? (yes/no): ")
    if confirm.lower() != 'yes':
        logging.info("Operation cancelled.")
        return
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    total_records = len(data['result'])
    
    logging.info(f"Found {total_records} records.")
    
    deleted_count = 0
    failed_count = 0
    
    for record in data['result']:
        record_url = f"{url}/{record['id']}"
        delete_response = requests.delete(record_url, headers=headers)
        
        if delete_response.status_code == 200:
            deleted_count += 1
        else:
            failed_count += 1
    
    logging.info(f"Deleted {deleted_count} records. Failed to delete {failed_count} records.")

def main():
    parser = argparse.ArgumentParser(description="Cloudflare DNS Record Management Tool")
    parser.add_argument("domain", help="The domain to manage DNS records for")
    parser.add_argument("command", choices=["export", "import", "list", "restore", "delete_all"], help="The command to execute")
    parser.add_argument("filename", nargs='?', help="The file to export to or import from")

    args = parser.parse_args()

    if not CF_TOKEN:
        logging.error("CF_TOKEN environment variable is not set.")
        return

    if args.command == "export":
        export_dns(args.domain, args.filename)
    elif args.command == "import":
        import_dns(args.domain, args.filename)
    elif args.command == "list":
        list_dns(args.domain, args.filename)
    elif args.command == "restore":
        restore_dns(args.domain, args.filename)
    elif args.command == "delete_all":
        delete_all_dns(args.domain)
    else:
        logging.error("Unknown command.")

if __name__ == "__main__":
    main()
