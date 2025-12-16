"""
Network metrics collector using psutil.
"""

import psutil
from typing import List
import logging

from n8n_metrics_agent.models import NetworkInterfaceMetrics
from n8n_metrics_agent.config import config

logger = logging.getLogger(__name__)

# Virtual/internal interface prefixes to exclude by default
VIRTUAL_INTERFACE_PREFIXES = (
    "lo",       # Loopback
    "docker",   # Docker bridge
    "br-",      # Docker bridge networks
    "veth",     # Docker veth pairs
    "virbr",    # Libvirt bridges
    "vnet",     # Virtual network
    "tun",      # VPN tunnels
    "tap",      # TAP devices
)


class NetworkCollector:
    """Collects network interface metrics."""

    def __init__(self):
        self._last_io_counters = {}

    def _is_physical_interface(self, name: str) -> bool:
        """Check if interface is likely a physical one."""
        # If specific interfaces are configured, only check those
        if config.network_interfaces:
            return name in config.network_interfaces

        # Otherwise, exclude known virtual interfaces
        return not name.startswith(VIRTUAL_INTERFACE_PREFIXES)

    def get_network_metrics(self) -> List[NetworkInterfaceMetrics]:
        """Get network interface metrics."""
        interfaces = []

        try:
            # Get I/O counters
            io_counters = psutil.net_io_counters(pernic=True)

            # Get interface stats (up/down status)
            try:
                if_stats = psutil.net_if_stats()
            except Exception:
                if_stats = {}

            for name, counters in io_counters.items():
                # Filter to physical interfaces only
                if not self._is_physical_interface(name):
                    continue

                # Check if interface is up
                stats = if_stats.get(name, None)
                is_up = stats.isup if stats else False

                interfaces.append(NetworkInterfaceMetrics(
                    name=name,
                    bytes_sent=counters.bytes_sent,
                    bytes_recv=counters.bytes_recv,
                    packets_sent=counters.packets_sent,
                    packets_recv=counters.packets_recv,
                    errors_in=counters.errin,
                    errors_out=counters.errout,
                    is_up=is_up,
                ))

        except Exception as e:
            logger.error(f"Failed to get network metrics: {e}")

        return interfaces

    def get_total_bandwidth(self) -> dict:
        """Get total bandwidth across all physical interfaces."""
        total = {
            "bytes_sent": 0,
            "bytes_recv": 0,
            "packets_sent": 0,
            "packets_recv": 0,
        }

        try:
            io_counters = psutil.net_io_counters(pernic=True)

            for name, counters in io_counters.items():
                if self._is_physical_interface(name):
                    total["bytes_sent"] += counters.bytes_sent
                    total["bytes_recv"] += counters.bytes_recv
                    total["packets_sent"] += counters.packets_sent
                    total["packets_recv"] += counters.packets_recv

        except Exception as e:
            logger.error(f"Failed to get total bandwidth: {e}")

        return total
