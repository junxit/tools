# Overview

[Cloudflare](https://www.cloudflare.com) is a service provider known
for [DNS](https://en.wikipedia.org/wiki/Domain_Name_System), [CDN](https://en.wikipedia.org/wiki/Content_delivery_network),
storage and many other services.

Their developer API is great.

Occasionally, some small scripts/tools will be added here when I get a chance to clean those up, remove my API keys and
such.

## Purge Cache

`flush_cache.sh` takes your API token with `purge:cache` permissions and lets you specify your domain on a command line
for which you want to purge all cache entries (and force Cloudflare to refresh its cache).

It is a quick way to flush/purge the cache without logging in to your Cloudflare portal, especially if you have many
domains that you copy content to from the command line like I do (I use [rsync](https://en.wikipedia.org/wiki/Rsync))