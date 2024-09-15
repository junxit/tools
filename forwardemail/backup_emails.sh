#!/bin/zsh

export API_KEY="your_key_here"

# List of domains
domains=("example1.com" "example2.com")  # Add your domains here

# Loop through each domain
for domain in "${domains[@]}"
do
  echo "Processing domain: $domain"
  
  # Run the export command
  python3 fe-full.py export "$domain" "$domain.json"
  
  echo "Finished processing domain: $domain"
done
