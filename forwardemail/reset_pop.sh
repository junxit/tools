#!/bin/zsh

API_KEY="your_key_here"

DOMAIN_NAME="example.com"
ALIAS="alias" # the part of the email before the "@" sign

curl -X POST https://api.forwardemail.net/v1/domains/$DOMAIN_NAME/aliases/$ALIAS/generate-password \
     -u "${API_KEY}:" \
     -H "Content-Type: application/json" \
     -d '{
           "new_password": "new_password!",
           "is_override": true
         }'

# The "new_password" can be the same as the existing one. What's important is passing "is_override" as "true"
