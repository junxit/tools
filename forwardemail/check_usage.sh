#!/bin/zsh

# This scripts retrieves the diskspace usage information for all aliases in the given list of `domains` and stores those in the corresponding .usage.txt file.

export API_KEY="your_key_here"

# List of domains
domains=("example1.com" "example2.com")  # Add your domains here

# Loop through each domain
for domain in "${domains[@]}"
do
  echo "Processing domain: $domain"
  
  # Run the export command
  python3 check-usage.py "$domain" | tee "$domain.usage.txt"
  
  echo "Finished processing domain: $domain"
done
