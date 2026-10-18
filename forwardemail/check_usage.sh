#!/bin/zsh

# This script retrieves the disk space usage of every alias in the given list of `domains` and stores it in the corresponding .usage.txt file.
set -euo pipefail

export API_KEY="your_key_here"

script_dir=$(cd "$(dirname "$0")" && pwd)

# List of domains
domains=("example1.com" "example2.com")  # Add your domains here

# Loop through each domain
for domain in "${domains[@]}"
do
  echo "Processing domain: $domain"

  # Run the usage report
  uv run --project "$script_dir/.." "$script_dir/check-usage.py" "$domain" | tee "$domain.usage.txt"

  echo "Finished processing domain: $domain"
done
