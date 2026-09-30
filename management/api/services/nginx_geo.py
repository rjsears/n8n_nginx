"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/nginx_geo.py

Pure helpers (standard library only) for the `geo $access_level { ... }` block
in nginx.conf that classifies clients as "internal" or "external".

setup.sh writes the block (see generate_nginx_conf_v3) and tags the entries it
maintains with "# [managed] ...": the pinned Docker network as "external" and
localhost / the Tailscale container as "internal". Those entries keep traffic
arriving through a Docker hop (Cloudflare Tunnel, docker-proxy, other
containers) from being treated as internal, so the management UI must never
drop, change or undercut them.

Every value that ends up in the block is validated here: a CIDR or description
that is not strictly checked can inject geo lines (e.g. a newline followed by
`172.30.0.0/25 "internal";`) or break the block's braces, and with them every
later read and write of nginx.conf.

Part of the "n8n_nginx/n8n_management" suite
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import ipaddress
import re
from typing import Any, Dict, List, Optional, Tuple

MANAGED_IP_RANGE_MARKER = "[managed]"

# Protected IP ranges that cannot be removed (required for system functionality)
PROTECTED_IP_RANGES = ["127.0.0.1/32"]

ACCESS_LEVELS = ("internal", "external")

DESCRIPTION_MAX_LENGTH = 100
_DESCRIPTION_FORBIDDEN = re.compile(r'[{};#"\\\x00-\x1f\x7f-\x9f  ]')

# Shortest prefix accepted for an "internal" range: anything broader (e.g.
# 0.0.0.0/0) would make the whole internet internal.
MIN_INTERNAL_PREFIX = {4: 8, 6: 16}

# Directives inside a geo block that are not "<network> <value>" entries
_GEO_DIRECTIVES = {"default", "proxy", "proxy_recursive", "ranges", "delete", "include"}

# "geo $access_level {" at the start of a line (so a commented-out copy is ignored)
_GEO_OPEN = re.compile(r"^([ \t]*)geo[ \t]+\$access_level[ \t]*\{", re.MULTILINE)


class GeoConfigError(ValueError):
    """Invalid access-control input or nginx.conf geo block (maps to HTTP 400)."""


def normalize_cidr(value: Any) -> str:
    """Return the canonical network for value, or raise ValueError.

    Surrounding whitespace is stripped and host bits are cleared
    (192.168.1.5/24 -> 192.168.1.0/24, which is how nginx's geo module treats
    them anyway); a bare address becomes a /32 (or /128).
    """
    if not isinstance(value, str):
        raise ValueError("CIDR must be a string")
    candidate = value.strip()
    if not candidate:
        raise ValueError("CIDR must not be empty")
    try:
        net = ipaddress.ip_network(candidate, strict=False)
    except ValueError:
        raise ValueError(f"Invalid CIDR notation: {value!r}")
    return str(net)


def validate_description(value: Any) -> str:
    """Return the stripped description, or raise ValueError if unsafe for nginx.conf.

    The description is written as a trailing "# ..." comment on the geo line,
    so it must be a single line, and must not contain characters that could
    confuse nginx or the geo block parser.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Description must be a string")
    value = value.strip()
    if len(value) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(f"Description must be at most {DESCRIPTION_MAX_LENGTH} characters")
    if _DESCRIPTION_FORBIDDEN.search(value):
        raise ValueError(
            'Description must be a single line without control characters or any of { } ; # " \\'
        )
    return value


def sanitize_description(value: Any) -> str:
    """Best-effort cleanup of a description read back from an existing nginx.conf."""
    text = _DESCRIPTION_FORBIDDEN.sub(" ", str(value or ""))
    return " ".join(text.split())[:DESCRIPTION_MAX_LENGTH]


def is_managed_ip_range(ip_range: Dict[str, Any]) -> bool:
    return str(ip_range.get("description") or "").startswith(MANAGED_IP_RANGE_MARKER)


def cidr_key(cidr: Any) -> str:
    """Canonical form of cidr for comparisons (the raw string if it does not parse)."""
    try:
        return normalize_cidr(cidr)
    except ValueError:
        return str(cidr).strip()


def find_geo_block(content: str) -> Optional[Tuple[int, int, str, List[str]]]:
    """Locate the geo $access_level block.

    Returns (start, end, indent, body_lines): content[start:end] spans from
    "geo" through the closing "}", indent is the whitespace before "geo" and
    body_lines are the raw lines between the braces. Returns None when there is
    no geo block. Comments are skipped when looking for the closing brace, so a
    "}" in a description cannot end the block early. Raises GeoConfigError for
    an unterminated or nested block.
    """
    match = _GEO_OPEN.search(content)
    if not match:
        return None
    start = match.start() + len(match.group(1))
    pos = match.end()
    body: List[str] = []
    while True:
        newline = content.find("\n", pos)
        line_end = len(content) if newline == -1 else newline
        line = content[pos:line_end]
        code = line.split("#", 1)[0]
        if "{" in code:
            raise GeoConfigError("nginx.conf geo $access_level block contains a nested '{'")
        brace = code.find("}")
        if brace != -1:
            body.append(line[:brace])
            return start, pos + brace + 1, match.group(1), body
        body.append(line)
        if newline == -1:
            raise GeoConfigError("nginx.conf geo $access_level block is not terminated")
        pos = newline + 1


def parse_geo_block(content: str) -> List[Dict[str, Any]]:
    """Return the entries of the geo block as dicts (cidr, description, access_level, protected)."""
    try:
        found = find_geo_block(content)
    except GeoConfigError:
        return []
    if not found:
        return []

    ip_ranges = []
    for line in found[3]:
        code, _, comment = line.partition("#")
        comment = comment.strip()
        for statement in code.split(";"):
            parts = statement.split()
            if len(parts) < 2 or parts[0] in _GEO_DIRECTIVES:
                continue
            cidr = parts[0]
            ip_ranges.append({
                "cidr": cidr,
                "description": comment,
                "access_level": parts[1].strip('"').strip("'"),
                "protected": cidr in PROTECTED_IP_RANGES or comment.startswith(MANAGED_IP_RANGE_MARKER),
            })
    return ip_ranges


def merge_managed_ip_ranges(config_content: str, ip_ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate the user's ranges and append the setup.sh-managed entries unchanged.

    Raises GeoConfigError when a user entry:
      * has an invalid CIDR, access level or description,
      * tries to change a [managed] entry or claims the [managed] marker,
      * duplicates another entry,
      * is an "internal" range broader than /8 (IPv6: /16), or
      * is an "internal" range inside a managed "external" range (e.g.
        172.30.0.0/25 inside the Docker network): geo is longest-prefix match,
        so it would make proxied traffic internal again.
    Managed entries passed back unchanged (the UI sends the full list) are fine.
    """
    managed = [r for r in parse_geo_block(config_content) if is_managed_ip_range(r)]
    managed_by_key = {cidr_key(r["cidr"]): r for r in managed}
    managed_external = []
    for r in managed:
        if r["access_level"] == "external":
            try:
                managed_external.append(ipaddress.ip_network(r["cidr"].strip(), strict=False))
            except ValueError:
                pass

    user_ranges: List[Dict[str, Any]] = []
    seen = set()
    for r in ip_ranges:
        raw_cidr = r.get("cidr", "")
        try:
            cidr = normalize_cidr(raw_cidr)
        except ValueError as e:
            raise GeoConfigError(str(e))
        net = ipaddress.ip_network(cidr)
        access_level = r.get("access_level") or "internal"
        if access_level not in ACCESS_LEVELS:
            raise GeoConfigError(f"Invalid access level {access_level!r} for {cidr}")
        description = str(r.get("description") or "").strip()

        managed_entry = managed_by_key.get(cidr)
        if managed_entry is not None:
            if access_level == managed_entry["access_level"] and description == managed_entry["description"]:
                continue  # unchanged managed entry, re-added below
            raise GeoConfigError(f"{cidr} is managed by setup.sh and cannot be changed")
        if description.startswith(MANAGED_IP_RANGE_MARKER):
            raise GeoConfigError(f"Descriptions starting with {MANAGED_IP_RANGE_MARKER} are reserved for setup.sh")

        try:
            description = validate_description(description)
        except ValueError:
            # Only reachable for entries read back from an existing nginx.conf
            # (API input is validated by the request schemas).
            description = sanitize_description(description)

        if cidr in seen:
            raise GeoConfigError(f"IP range {cidr} is listed more than once")
        seen.add(cidr)

        if access_level == "internal":
            if net.prefixlen < MIN_INTERNAL_PREFIX[net.version]:
                raise GeoConfigError(
                    f"{cidr} is too broad to mark internal (prefix must be at least "
                    f"/{MIN_INTERNAL_PREFIX[net.version]})"
                )
            for ext in managed_external:
                if net.version == ext.version and net.subnet_of(ext):
                    raise GeoConfigError(
                        f"{cidr} is inside the Docker network {ext} used for proxied "
                        "traffic (Cloudflare Tunnel, docker-proxy) and cannot be marked internal"
                    )

        user_ranges.append({"cidr": cidr, "description": description, "access_level": access_level})

    return user_ranges + managed


def generate_geo_block(ip_ranges: List[Dict[str, Any]], indent: str = "") -> str:
    """Generate the geo block text. The first line carries no indent (it replaces "geo" in place)."""
    inner = indent + "    "
    lines = ["geo $access_level {", f'{inner}default          "external";']
    for ip_range in ip_ranges:
        cidr = ip_range.get("cidr", "")
        access_level = ip_range.get("access_level", "internal")
        description = ip_range.get("description", "")
        line = f'{inner}{cidr:<20} "{access_level}";'
        if description:
            line += f"  # {description}"
        lines.append(line)
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def update_geo_block(config_content: str, ip_ranges: List[Dict[str, Any]]) -> str:
    """Return config_content with the geo block rebuilt from ip_ranges (plus managed entries).

    Uses plain slicing, never re.sub, so nothing in the new block is
    interpreted as a replacement template.
    """
    ip_ranges = merge_managed_ip_ranges(config_content, ip_ranges)

    found = find_geo_block(config_content)
    if found:
        start, end, indent, _ = found
        return config_content[:start] + generate_geo_block(ip_ranges, indent) + config_content[end:]

    new_block = generate_geo_block(ip_ranges, "    ")
    http_match = re.search(r"http\s*\{", config_content)
    if http_match:
        insert_pos = http_match.end()
        return config_content[:insert_pos] + "\n    " + new_block + "\n" + config_content[insert_pos:]

    return new_block + "\n\n" + config_content
