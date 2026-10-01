"""Unit tests for the access-control geo block helpers (api/services/nginx_geo.py)."""

import importlib.util
import ipaddress
import sys
from pathlib import Path

import pytest

# Load nginx_geo.py by path: it only uses the standard library, and going
# through the api.services package would pull in the whole application.
_GEO_PATH = Path(__file__).resolve().parents[1] / "api" / "services" / "nginx_geo.py"
_spec = importlib.util.spec_from_file_location("nginx_geo_under_test", _GEO_PATH)
geo = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = geo
_spec.loader.exec_module(geo)

# Shape of the block generate_nginx_conf_v3 in setup.sh writes
SETUP_CONF = """events {
    worker_connections 1024;
}

http {
    # Entries tagged [managed] are maintained by setup.sh - do not remove them.
    geo $access_level {
        default          "external";
        127.0.0.1/32     "internal";  # [managed] Localhost (healthchecks)
        10.0.0.0/8    "internal";
        192.168.0.0/16    "internal";
        172.30.0.0/24    "external";  # [managed] Docker network n8n_network (proxied traffic)
        172.30.0.2/32    "internal";  # [managed] Tailscale container (tailnet users via Tailscale Serve)
    }

    map $access_level $is_trusted {
        default 0;
        internal 1;
    }

    server {
        listen 80;
        location / { return 200; }
    }
}
"""


def _user(cidr, description="", access_level="internal"):
    return {"cidr": cidr, "description": description, "access_level": access_level}


def _user_ranges(content):
    return [r for r in geo.parse_geo_block(content) if not geo.is_managed_ip_range(r)]


def _managed(content):
    return [(r["cidr"], r["access_level"]) for r in geo.parse_geo_block(content) if geo.is_managed_ip_range(r)]


def _level_for(content, address):
    """Longest-prefix match over the geo entries, like nginx's geo module."""
    ip = ipaddress.ip_address(address)
    best = None
    for r in geo.parse_geo_block(content):
        net = ipaddress.ip_network(r["cidr"], strict=False)
        if ip in net and (best is None or net.prefixlen > best[0]):
            best = (net.prefixlen, r["access_level"])
    return best[1] if best else "external"


# --- validators -------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("10.0.0.0/8", "10.0.0.0/8"),
    (" 172.30.0.0/25 ", "172.30.0.0/25"),
    ("\t192.168.1.5/24\n", "192.168.1.0/24"),
    ("10.1.2.3", "10.1.2.3/32"),
    ("fd00::/8", "fd00::/8"),
])
def test_normalize_cidr(raw, expected):
    assert geo.normalize_cidr(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "10.0.0.0/33", "abc", "10.0.0.0/8 x", '1.2.3.4/32 "internal";', None, 5])
def test_normalize_cidr_rejects(raw):
    with pytest.raises(ValueError):
        geo.normalize_cidr(raw)


@pytest.mark.parametrize("desc", ["", "Office LAN", "  VPN (site-2) ", "[managed] Localhost (healthchecks)", "x" * 100])
def test_description_ok(desc):
    assert geo.validate_description(desc) == desc.strip()


@pytest.mark.parametrize("desc", [
    "a}b", "a{b", "a;b", "a#b", 'a"b', "a\\b", "x\n 172.30.0.0/25 \"internal\";", "tab\there",
    "c\rr", "nul\x00", "a\x85b", "a\u2028b", "x" * 101,
])
def test_description_rejects(desc):
    with pytest.raises(ValueError):
        geo.validate_description(desc)


# --- parse ------------------------------------------------------------------

def test_parse_setup_block():
    ranges = geo.parse_geo_block(SETUP_CONF)
    assert [(r["cidr"], r["access_level"]) for r in ranges] == [
        ("127.0.0.1/32", "internal"),
        ("10.0.0.0/8", "internal"),
        ("192.168.0.0/16", "internal"),
        ("172.30.0.0/24", "external"),
        ("172.30.0.2/32", "internal"),
    ]
    assert _managed(SETUP_CONF) == [
        ("127.0.0.1/32", "internal"), ("172.30.0.0/24", "external"), ("172.30.0.2/32", "internal"),
    ]
    assert all(r["protected"] for r in ranges if geo.is_managed_ip_range(r))


def test_parse_brace_in_comment_does_not_end_block():
    content = SETUP_CONF.replace('"internal";\n        192.168', '"internal";  # legacy } note\n        192.168')
    cidrs = [r["cidr"] for r in geo.parse_geo_block(content)]
    assert "192.168.0.0/16" in cidrs and "172.30.0.0/24" in cidrs


def test_parse_ignores_commented_out_geo():
    content = "# geo $access_level { 1.2.3.4/32 \"internal\"; }\n" + SETUP_CONF
    assert geo.parse_geo_block(content)[0]["cidr"] == "127.0.0.1/32"


def test_find_geo_block_malformed():
    with pytest.raises(geo.GeoConfigError):
        geo.find_geo_block('http {\n    geo $access_level {\n        10.0.0.0/8 "internal";\n')


# --- merge / validation of user input --------------------------------------

def test_internal_inside_managed_external_rejected():
    with pytest.raises(geo.GeoConfigError, match="Docker network"):
        geo.update_geo_block(SETUP_CONF, _user_ranges(SETUP_CONF) + [_user("172.30.0.0/25")])


def test_whitespace_cidr_cannot_bypass_docker_check():
    # " 172.30.0.0/25" used to hit `except ValueError: continue` and be written as-is
    with pytest.raises(geo.GeoConfigError, match="Docker network"):
        geo.update_geo_block(SETUP_CONF, _user_ranges(SETUP_CONF) + [_user(" 172.30.0.0/25")])


def test_invalid_cidr_rejected():
    with pytest.raises(geo.GeoConfigError, match="Invalid CIDR"):
        geo.update_geo_block(SETUP_CONF, [_user("172.30.0.0/25 garbage")])


@pytest.mark.parametrize("cidr", ["0.0.0.0/0", "0.0.0.0/1", "8.0.0.0/7", "::/0", "2000::/8"])
def test_too_broad_internal_rejected(cidr):
    with pytest.raises(geo.GeoConfigError, match="too broad"):
        geo.update_geo_block(SETUP_CONF, [_user(cidr)])


def test_too_broad_external_allowed():
    out = geo.update_geo_block(SETUP_CONF, [_user("0.0.0.0/0", access_level="external")])
    assert ("0.0.0.0/0", "external") in [(r["cidr"], r["access_level"]) for r in geo.parse_geo_block(out)]


def test_managed_marker_reserved():
    with pytest.raises(geo.GeoConfigError, match="reserved"):
        geo.update_geo_block(SETUP_CONF, [_user("10.9.0.0/16", "[managed] sneaky")])


@pytest.mark.parametrize("entry", [
    _user("172.30.0.0/24", "mine", "internal"),
    _user("172.30.0.0/24", "[managed] Docker network n8n_network (proxied traffic)", "internal"),
    _user("172.30.0.2/32", "renamed"),
])
def test_changing_managed_entry_rejected(entry):
    with pytest.raises(geo.GeoConfigError, match="managed by setup.sh"):
        geo.update_geo_block(SETUP_CONF, [entry])


def test_unchanged_managed_entries_pass_through():
    # The UI's full-replace PUT sends every entry back, managed ones included
    out = geo.update_geo_block(SETUP_CONF, geo.parse_geo_block(SETUP_CONF))
    def key(r):
        return r["cidr"]

    assert sorted(geo.parse_geo_block(out), key=key) == sorted(geo.parse_geo_block(SETUP_CONF), key=key)


def test_duplicate_rejected():
    with pytest.raises(geo.GeoConfigError, match="more than once"):
        geo.update_geo_block(SETUP_CONF, [_user("10.0.0.0/8"), _user(" 10.0.0.0/8 ")])


def test_managed_entries_survive_being_dropped():
    out = geo.update_geo_block(SETUP_CONF, [])
    assert _managed(out) == _managed(SETUP_CONF)
    assert _level_for(out, "172.30.0.5") == "external"
    assert _level_for(out, "172.30.0.2") == "internal"


# --- write ------------------------------------------------------------------

def test_update_preserves_rest_of_file_and_indent():
    out = geo.update_geo_block(SETUP_CONF, _user_ranges(SETUP_CONF) + [_user("100.64.0.0/10", "Tailscale CGNAT")])
    before, after = SETUP_CONF.split("    geo $access_level {")[0], SETUP_CONF.split("    }\n\n    map")[1]
    assert out.startswith(before + "    geo $access_level {\n        default")
    assert out.endswith("    }\n\n    map" + after)
    assert '        100.64.0.0/10        "internal";  # Tailscale CGNAT' in out
    assert _level_for(out, "100.64.1.1") == "internal"


def test_round_trip_is_stable():
    once = geo.update_geo_block(SETUP_CONF, _user_ranges(SETUP_CONF))
    twice = geo.update_geo_block(once, _user_ranges(once))
    assert once == twice
    assert once.count("geo $access_level") == 1


def test_backslash_sequences_are_not_template_expanded():
    # re.sub would have turned \1 / \n in the replacement into group refs / newlines
    legacy = SETUP_CONF.replace('10.0.0.0/8    "internal";', '10.0.0.0/8    "internal";  # C:\\1\\n')
    out = geo.update_geo_block(legacy, _user_ranges(legacy))
    assert _level_for(out, "10.1.1.1") == "internal"
    assert out.count("geo $access_level") == 1
    line = next(ln for ln in out.splitlines() if "10.0.0.0/8" in ln)
    assert line.endswith("# C: 1 n")


def test_legacy_unsafe_description_is_sanitized_not_fatal():
    legacy = SETUP_CONF.replace('10.0.0.0/8    "internal";', '10.0.0.0/8    "internal";  # say "hi"; ok')
    out = geo.update_geo_block(legacy, _user_ranges(legacy))
    line = next(ln for ln in out.splitlines() if "10.0.0.0/8" in ln)
    assert line.strip() == '10.0.0.0/8           "internal";  # say hi ok'


def test_injected_geo_line_cannot_be_written():
    evil = _user("10.8.0.0/16", 'x\n        172.30.0.0/25 "internal";')
    # Rejected by the request schema; if it ever reaches the merge it is neutralized
    out = geo.update_geo_block(SETUP_CONF, _user_ranges(SETUP_CONF) + [evil])
    assert _level_for(out, "172.30.0.5") == "external"
    assert all(r["cidr"] != "172.30.0.0/25" for r in geo.parse_geo_block(out))


def test_insert_when_no_geo_block():
    content = "events {}\nhttp {\n    server { listen 80; }\n}\n"
    out = geo.update_geo_block(content, [_user("10.0.0.0/8", "LAN")])
    assert geo.parse_geo_block(out)[0]["cidr"] == "10.0.0.0/8"
    assert out.startswith("events {}\nhttp {\n    geo $access_level {")
