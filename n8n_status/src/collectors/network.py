# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/network.py
#
# Collects network information (interfaces, gateway, DNS)
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
import re
import socket
import subprocess
from typing import Any, Optional

import psutil

from .base import BaseCollector
from ..config import config

logger = logging.getLogger(__name__)


class NetworkCollector(BaseCollector):
    """
    Collects network configuration information.

    Includes:
    - Hostname and FQDN
    - Network interfaces and IP addresses
    - Default gateway
    - DNS servers
    """

    key = "system:network"
    interval = config.poll_interval_network
    ttl = 120  # Network info changes infrequently

    def collect(self) -> Any:
        """Collect network information."""
        try:
            return {
                "hostname": self._get_hostname(),
                "fqdn": self._get_fqdn(),
                "interfaces": self._get_interfaces(),
                "gateway": self._get_default_gateway(),
                "dns_servers": self._get_dns_servers(),
            }
        except Exception as e:
            logger.error(f"Failed to collect network info: {e}")
            raise

    def _get_hostname(self) -> str:
        """Get system hostname."""
        try:
            return socket.gethostname()
        except Exception as e:
            logger.warning(f"Failed to get hostname: {e}")
            return "unknown"

    def _get_fqdn(self) -> str:
        """Get fully qualified domain name."""
        try:
            return socket.getfqdn()
        except Exception as e:
            logger.warning(f"Failed to get FQDN: {e}")
            return self._get_hostname()

    def _get_interfaces(self) -> list[dict]:
        """Get network interfaces and their addresses."""
        interfaces = []

        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            for iface_name, addr_list in addrs.items():
                # Skip loopback
                if iface_name == "lo":
                    continue

                iface_info = {
                    "name": iface_name,
                    "addresses": [],
                    "is_up": False,
                    "speed": None,
                    "mtu": None,
                }

                # Get interface stats
                if iface_name in stats:
                    iface_stats = stats[iface_name]
                    iface_info["is_up"] = iface_stats.isup
                    iface_info["speed"] = iface_stats.speed
                    iface_info["mtu"] = iface_stats.mtu

                # Get addresses
                for addr in addr_list:
                    addr_info = {}

                    if addr.family == socket.AF_INET:
                        addr_info = {
                            "type": "ipv4",
                            "address": addr.address,
                            "netmask": addr.netmask,
                            "broadcast": addr.broadcast,
                        }
                    elif addr.family == socket.AF_INET6:
                        addr_info = {
                            "type": "ipv6",
                            "address": addr.address,
                            "netmask": addr.netmask,
                        }
                    elif addr.family == psutil.AF_LINK:
                        addr_info = {
                            "type": "mac",
                            "address": addr.address,
                        }

                    if addr_info:
                        iface_info["addresses"].append(addr_info)

                # Only include interfaces with at least one IP address
                if any(a["type"] in ("ipv4", "ipv6") for a in iface_info["addresses"]):
                    interfaces.append(iface_info)

        except Exception as e:
            logger.warning(f"Failed to get interfaces: {e}")

        return interfaces

    def _get_default_gateway(self) -> Optional[str]:
        """Get the default gateway IP address."""
        try:
            # Try using ip route command
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse: "default via 192.168.1.1 dev eth0"
                match = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.debug(f"ip route failed: {e}")

        # Fallback: try reading /proc/net/route
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:  # Skip header
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == "00000000":
                        # Gateway is in hex, little-endian
                        gateway_hex = fields[2]
                        gateway_bytes = bytes.fromhex(gateway_hex)
                        gateway_ip = ".".join(str(b) for b in reversed(gateway_bytes))
                        return gateway_ip
        except Exception as e:
            logger.debug(f"Failed to read /proc/net/route: {e}")

        return None

    def _get_dns_servers(self) -> list[str]:
        """Get DNS server addresses from resolv.conf."""
        dns_servers = []

        try:
            # Try multiple locations
            resolv_paths = [
                "/etc/resolv.conf",
                "/host/resolv.conf",  # Mounted from host
            ]

            for resolv_path in resolv_paths:
                try:
                    with open(resolv_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("nameserver"):
                                parts = line.split()
                                if len(parts) >= 2:
                                    dns_servers.append(parts[1])
                    if dns_servers:
                        break
                except FileNotFoundError:
                    continue

        except Exception as e:
            logger.warning(f"Failed to get DNS servers: {e}")

        return dns_servers
