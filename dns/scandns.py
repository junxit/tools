"""Rebuild a BIND zone file by querying DNS for the hostnames you know about.

Useful when a DNS host offers no zone export: list the hostnames (or point at any
text that mentions them, such as a pasted dashboard page), and this script queries
each one and writes the answers as a BIND zone file, ready for an import such as
Cloudflare's. Queries go to one of the zone's own nameservers, so TTLs are the
configured values rather than whatever is left in a resolver's cache.

Typical usage example:

    uv run dns/scandns.py example.com www.example.com mail.example.com
    uv run dns/scandns.py example.com --hosts-file pasted.txt -o example.com.scan.txt

Attributes:
    RECORD_TYPES: Record types queried for every hostname that is not a CNAME.
"""

import argparse
import logging
import re
import sys
from collections import Counter
from pathlib import Path

import dns.exception
import dns.name
import dns.resolver

RECORD_TYPES = ("A", "AAAA", "MX", "TXT", "SRV")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def extract_hostnames(domain, text):
    """Find every hostname at or below a domain in free-form text.

    Args:
        domain: The zone apex, e.g. "example.com".
        text: Any text that mentions hostnames.

    Returns:
        A set of lowercase hostnames without trailing dots.
    """
    pattern = rf"(?<![\w.-])((?:[\w-]+\.)*{re.escape(domain)})\.?(?![\w-])"
    hostnames = {match.lower() for match in re.findall(pattern, text, re.IGNORECASE)}
    logging.info("Found %d unique hostnames for domain '%s'.", len(hostnames), domain)
    return hostnames


def make_resolver(domain, server=None):
    """Build a resolver that asks the given server, or one of the zone's nameservers.

    Args:
        domain: The zone apex.
        server: An IP address to query instead of the zone's own nameserver.

    Returns:
        A dns.resolver.Resolver.
    """
    resolver = dns.resolver.Resolver()
    if server:
        resolver.nameservers = [server]
        return resolver
    try:
        nameserver = resolver.resolve(domain, "NS")[0].target.to_text(True)
        resolver.nameservers = [resolver.resolve(nameserver, "A")[0].address]
        logging.info("Querying authoritative nameserver %s.", nameserver)
    except dns.exception.DNSException as e:
        logging.warning(
            "No authoritative nameserver reachable (%s); TTLs may be from a cache.", e
        )
    return resolver


def query(resolver, name, rdtype):
    """Return the records of one type that a name itself owns.

    Args:
        resolver: The resolver to ask.
        name: The hostname to query.
        rdtype: The record type, e.g. "MX".

    Returns:
        A dns.rrset.RRset, or None if the name has no such records. Answers reached by
        following a CNAME belong to the target, not to `name`, so they are ignored.
    """
    try:
        answer = resolver.resolve(name, rdtype, raise_on_no_answer=False)
    except dns.resolver.NXDOMAIN:
        return None
    except dns.exception.DNSException as e:
        logging.warning("Query for %s %s failed: %s", name, rdtype, e)
        return None
    if answer.rrset is None or answer.rrset.name != dns.name.from_text(name):
        return None
    return answer.rrset


def scan_host(resolver, hostname):
    """Collect the records a hostname owns.

    Args:
        resolver: The resolver to ask.
        hostname: The hostname to scan.

    Returns:
        A list of RRsets. A CNAME is returned alone, because no other data may
        share its name; _dmarc names are only checked for TXT.
    """
    cname = query(resolver, hostname, "CNAME")
    if cname is not None:
        return [cname]
    rdtypes = ("TXT",) if hostname.startswith("_dmarc.") else RECORD_TYPES
    rrsets = (query(resolver, hostname, rdtype) for rdtype in rdtypes)
    return [rrset for rrset in rrsets if rrset is not None]


def write_bind_format(domain, rrsets, output_filename):
    """Write RRsets to a BIND zone file, with names relative to the domain.

    Args:
        domain: The zone apex, used as $ORIGIN.
        rrsets: The RRsets to write, in order.
        output_filename: Path of the zone file to write.
    """
    origin = dns.name.from_text(domain)
    with open(output_filename, "w") as f:
        f.write(f"$ORIGIN {origin.to_text()}\n")
        f.writelines(
            rrset.to_text(origin=origin, relativize=True) + "\n" for rrset in rrsets
        )
    logging.info("BIND format file written to %s.", output_filename)


def main():
    """Parse the command line, scan the hostnames, and write the zone file.

    Returns:
        The process exit status: 0 on success.
    """
    parser = argparse.ArgumentParser(
        description="Rebuild a BIND zone file from DNS answers for known hostnames."
    )
    parser.add_argument("domain", help="The zone apex, e.g. example.com")
    parser.add_argument(
        "hostnames", nargs="*", help="Hostnames to scan; the apex is always included"
    )
    parser.add_argument(
        "--hosts-file", help="A file of any format that mentions hostnames to scan"
    )
    parser.add_argument(
        "--server",
        help="Resolver IP to query (default: one of the zone's own nameservers)",
    )
    parser.add_argument(
        "-o", "--output", help="Output file (default: <domain>.scan.txt)"
    )
    args = parser.parse_args()

    domain = args.domain.lower().rstrip(".")
    text = " ".join(args.hostnames)
    if args.hosts_file:
        text += "\n" + Path(args.hosts_file).read_text()
    hostnames = extract_hostnames(domain, text) | {domain}
    names = sorted(
        hostnames | {f"_dmarc.{h}" for h in hostnames if not h.startswith("_")}
    )

    resolver = make_resolver(domain, args.server)
    rrsets = [
        rrset for rdtype in ("SOA", "NS") if (rrset := query(resolver, domain, rdtype))
    ]
    for name in names:
        rrsets.extend(scan_host(resolver, name))

    write_bind_format(domain, rrsets, args.output or f"{domain}.scan.txt")
    totals = Counter(dns.rdatatype.to_text(rrset.rdtype) for rrset in rrsets)
    logging.info("Total unique hostnames processed: %d", len(names))
    for rdtype, count in sorted(totals.items()):
        logging.info("Total %s record sets found: %d", rdtype, count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
