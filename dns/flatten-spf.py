"""Flatten an SPF record into the ip4/ip6 ranges it currently authorizes.

Flattening replaces include:, a, and mx mechanisms with the addresses they resolve
to, which keeps a record under SPF's limit of 10 DNS lookups. Providers change those
addresses without notice, so run --check regularly (from cron, for example) to learn
when a published, flattened record has drifted from its source.

Typical usage example:

    uv run dns/flatten-spf.py example.com
    uv run dns/flatten-spf.py example.com --source "v=spf1 include:_spf.example.net ~all"
    uv run dns/flatten-spf.py example.com --source _spf-source.example.com --check

Attributes:
    LOOKUP_TERMS: SPF terms that each cost a DNS lookup (RFC 7208, section 4.6.4).
"""

import argparse
import re
import sys

import dns.exception
import dns.resolver

LOOKUP_TERMS = ("include", "a", "mx", "ptr", "exists", "redirect")


def resolve_spf(domain):
    """Return the SPF record published at a domain.

    Args:
        domain: The domain to look up.

    Returns:
        The record text, or None if the domain publishes no SPF record. A long record
        arrives as several strings, which are joined (RFC 7208, section 3.3).

    Raises:
        dns.exception.DNSException: If the lookup fails for any other reason.
    """
    try:
        answers = dns.resolver.resolve(domain, "TXT")
    except dns.resolver.NXDOMAIN, dns.resolver.NoAnswer:
        return None
    for rdata in answers:
        record = b"".join(rdata.strings).decode()
        if record.lower() == "v=spf1" or record.lower().startswith("v=spf1 "):
            return record
    return None


def split_term(term):
    """Split an SPF term into its qualifier, name, and value.

    Args:
        term: One term, such as "~all", "include:_spf.example.net", or "a/24".

    Returns:
        A (qualifier, name, value) tuple; for "a/24" the value keeps its "/24".

    Example:
        >>> split_term("-include:_spf.example.net")
        ('-', 'include', '_spf.example.net')
    """
    qualifier = term[0] if term[0] in "+-~?" else ""
    name, separator, value = re.match(
        r"([A-Za-z][\w.-]*)([:=/]?)(.*)", term[len(qualifier) :]
    ).groups()
    return qualifier, name.lower(), "/" + value if separator == "/" else value


def lookup_count(record):
    """Count the terms in an SPF record that cost a DNS lookup (receivers allow 10).

    Args:
        record: The SPF record text.

    Returns:
        The number of lookup-costing terms.
    """
    return sum(split_term(term)[1] in LOOKUP_TERMS for term in record.split()[1:])


def addresses(host, cidr4=None, cidr6=None):
    """Resolve a host's A and AAAA records into ip4/ip6 terms.

    Args:
        host: The hostname to resolve.
        cidr4: Optional IPv4 prefix length to apply.
        cidr6: Optional IPv6 prefix length to apply.

    Returns:
        A list of terms such as "ip4:192.0.2.1" or "ip6:2001:db8::/64".
    """
    terms = []
    for rdtype, prefix, cidr in (("A", "ip4", cidr4), ("AAAA", "ip6", cidr6)):
        try:
            for rdata in dns.resolver.resolve(host, rdtype):
                terms.append(f"{prefix}:{rdata.address}" + (f"/{cidr}" if cidr else ""))
        except dns.resolver.NXDOMAIN, dns.resolver.NoAnswer:
            pass
    return terms


def mx_hosts(host):
    """Return the mail exchangers for a host.

    Args:
        host: The domain whose MX records to read.

    Returns:
        A list of exchange hostnames.
    """
    try:
        return [rdata.exchange.to_text() for rdata in dns.resolver.resolve(host, "MX")]
    except dns.resolver.NXDOMAIN, dns.resolver.NoAnswer:
        return []


def expand_domain(target, seen, warnings, top_level=False):
    """Flatten the SPF record of an include: or redirect= target.

    Args:
        target: The domain whose record to expand.
        seen: Domains already expanded, to stop include loops.
        warnings: A list collecting notes about terms that could not be flattened.
        top_level: True for a top-level redirect, whose `all` still applies.

    Returns:
        The flattened terms of the target's record.
    """
    if target in seen:
        warnings.append(f"skipped repeated {target}")
        return []
    seen.add(target)
    record = resolve_spf(target)
    if record is None:
        warnings.append(
            f"{target} publishes no SPF record (receivers treat that as an error)"
        )
        return []
    return flatten_terms(target, record, seen, warnings, top_level)


def flatten_terms(domain, record, seen, warnings, top_level):
    """Expand an SPF record's terms into ip4/ip6 terms wherever possible.

    Args:
        domain: The domain the record belongs to; the default target of a and mx.
        record: The SPF record text.
        seen: Domains already expanded, to stop include loops.
        warnings: A list collecting notes about terms that could not be flattened.
        top_level: True for the record being flattened. Inside an include, `all`,
            modifiers, and non-pass terms are dropped because they don't carry over.

    Returns:
        The resulting terms, in their original order.
    """
    terms = []
    redirect = None
    has_all = False
    for term in record.split()[1:]:
        qualifier, name, value = split_term(term)
        passing = qualifier in ("", "+")
        if name == "all":
            has_all = True
            if top_level:
                terms.append(term)
        elif name == "redirect":
            redirect = value
        elif not passing and name in (
            "ip4",
            "ip6",
            "include",
            "a",
            "mx",
            "exists",
            "ptr",
        ):
            if top_level:
                terms.append(term)
                if name in ("include", "a", "mx"):
                    warnings.append(f"kept {term}: only pass terms can be flattened")
            else:
                warnings.append(
                    f"dropped {term} from {domain}: non-pass terms don't carry over"
                )
        elif name in ("ip4", "ip6"):
            terms.append(f"{name}:{value}")
        elif name in ("exists", "ptr") or "%" in value:
            warnings.append(f"kept {term}: it can't be flattened")
            terms.append(term)
        elif name == "include":
            terms.extend(expand_domain(value, seen, warnings))
        elif name in ("a", "mx"):
            host, cidr4, cidr6 = re.fullmatch(
                r"([^/]*)(?:/(\d+))?(?://(\d+))?", value
            ).groups()
            hosts = [host or domain] if name == "a" else mx_hosts(host or domain)
            for exchange in hosts:
                terms.extend(addresses(exchange, cidr4, cidr6))
        elif top_level:
            terms.append(term)  # modifiers such as exp=
    if redirect and not has_all:
        # redirect= only applies when the record has no `all` (RFC 7208, section 6.1).
        terms.extend(expand_domain(redirect, seen, warnings, top_level))
    return list(dict.fromkeys(terms))


def flatten_spf(domain, record):
    """Flatten an SPF record.

    Args:
        domain: The domain the record is (or will be) published at.
        record: The SPF record text to flatten.

    Returns:
        A (flattened_record, warnings) tuple.
    """
    warnings = []
    terms = flatten_terms(domain, record, {domain}, warnings, top_level=True)
    return " ".join(["v=spf1", *terms]), warnings


def main():
    """Parse the command line, then print a flattened record or check it for drift.

    Returns:
        The process exit status: 0 on success, 1 if no record exists or the published
        record has drifted from its source, 2 if a DNS lookup failed.
    """
    parser = argparse.ArgumentParser(
        description="Flatten an SPF record for a given domain."
    )
    parser.add_argument(
        "domain", type=str, help="The domain to flatten the SPF record for"
    )
    parser.add_argument(
        "--source",
        help='Record to flatten instead of the published one: "v=spf1 ..." text, '
        "or a hostname whose TXT record holds it",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the published record against the flattened --source; exit 1 if they differ",
    )
    args = parser.parse_args()
    if args.check and not args.source:
        parser.error("--check needs --source")

    domain = args.domain
    try:
        published = resolve_spf(domain)
        source = published
        if args.source:
            source = (
                args.source
                if args.source.lower().startswith("v=spf1")
                else resolve_spf(args.source)
            )
        if not source:
            print(f"No SPF record found for {args.source or domain}")
            return 1

        flattened, warnings = flatten_spf(domain, source)

        if args.check:
            if not published:
                print(f"No SPF record found for {domain}")
                return 1
            current, _ = flatten_spf(domain, published)
            missing = set(flattened.split()) - set(current.split())
            extra = set(current.split()) - set(flattened.split())
            if not missing and not extra:
                print(f"OK: the SPF record published at {domain} matches its source.")
                return 0
            print(
                f"DRIFT: the SPF record published at {domain} no longer matches its source."
            )
            for term in sorted(missing):
                print(f"  missing: {term}")
            for term in sorted(extra):
                print(f"  extra:   {term}")
            print(f"\nUp-to-date flattened record:\n{flattened}")
            return 1
    except dns.exception.DNSException as e:
        print(f"DNS lookup failed: {e}", file=sys.stderr)
        return 2

    def lookups(record):
        count = lookup_count(record)
        return f"{count} DNS lookup{'' if count == 1 else 's'}"

    print(f"Original SPF record for {domain} ({lookups(source)}):\n{source}")
    print(
        f"\nFlattened SPF record for {domain} ({lookups(flattened)}, "
        f"{len(flattened)} characters):\n{flattened}"
    )
    if len(flattened) > 255:
        print(
            "\nNote: longer than 255 characters, so it must be published as several strings"
        )
        print("(most DNS dashboards split it for you).")
    if len(flattened) > 450:
        print(
            "Warning: answers this large can exceed 512 bytes; consider splitting it across"
        )
        print("include: records.")
    for warning in warnings:
        print(f"Note: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
