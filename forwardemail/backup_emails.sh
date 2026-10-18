#!/bin/zsh
# Back up the alias settings (not the mail) of each domain to <domain>.json.
set -euo pipefail

export API_KEY="your_key_here"

script_dir=$(cd "$(dirname "$0")" && pwd)

# List of domains
domains=("example1.com" "example2.com")  # Add your domains here

# Loop through each domain
for domain in "${domains[@]}"
do
  echo "Processing domain: $domain"

  # Run the export command
  uv run --project "$script_dir/.." "$script_dir/fe-full.py" export "$domain" "$domain.json"

  echo "Finished processing domain: $domain"
done
