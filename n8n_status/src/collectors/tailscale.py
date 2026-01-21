# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/tailscale.py
#
# Collects Tailscale VPN status
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import json
import logging
from typing import Any, Optional

import docker
from docker.errors import NotFound, DockerException

from .base import BaseCollector
from ..config import config

logger = logging.getLogger(__name__)


class TailscaleCollector(BaseCollector):
    """
    Collects Tailscale VPN status by executing tailscale status inside the container.

    Checks:
    - Container running status
    - Tailscale connection status via `tailscale status --json`
    - IP address and peer count
    """

    key = "system:tailscale"
    interval = config.poll_interval_external
    ttl = 60

    def __init__(self):
        super().__init__()
        self._docker_client: Optional[docker.DockerClient] = None

    @property
    def docker_client(self) -> docker.DockerClient:
        """Lazy-load Docker client."""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def collect(self) -> Any:
        """Collect Tailscale status."""
        container_name = config.tailscale_container

        try:
            container = self.docker_client.containers.get(container_name)

            # Get container status
            status = container.status
            is_running = status == "running"

            if not is_running:
                return {
                    "installed": True,
                    "running": False,
                    "logged_in": False,
                    "container_name": container_name,
                    "container_status": status,
                    "healthy": False,
                }

            # Execute tailscale status --json inside the container
            try:
                exec_result = container.exec_run(
                    cmd=["tailscale", "status", "--json"],
                    demux=True,
                )
                stdout, stderr = exec_result.output

                if exec_result.exit_code == 0 and stdout:
                    ts_status = json.loads(stdout.decode("utf-8"))
                    return self._parse_tailscale_status(container_name, status, ts_status)
                else:
                    error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
                    return {
                        "installed": True,
                        "running": True,
                        "logged_in": False,
                        "container_name": container_name,
                        "container_status": status,
                        "error": error_msg,
                        "healthy": False,
                    }

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Tailscale status JSON: {e}")
                return {
                    "installed": True,
                    "running": True,
                    "logged_in": False,
                    "container_name": container_name,
                    "container_status": status,
                    "error": f"Invalid JSON: {e}",
                    "healthy": False,
                }

        except NotFound:
            return {
                "installed": False,
                "running": False,
                "logged_in": False,
                "container_name": container_name,
                "error": "Container not found",
                "healthy": False,
            }
        except DockerException as e:
            logger.error(f"Docker error checking Tailscale: {e}")
            return {
                "installed": False,
                "running": False,
                "logged_in": False,
                "container_name": container_name,
                "error": str(e),
                "healthy": False,
            }

    def _parse_tailscale_status(self, container_name: str, container_status: str, ts_status: dict) -> dict:
        """Parse the tailscale status --json output."""
        try:
            # Get self info
            self_info = ts_status.get("Self", {})
            tailscale_ips = self_info.get("TailscaleIPs", [])
            hostname = self_info.get("HostName", "")
            dns_name = self_info.get("DNSName", "")
            online = self_info.get("Online", False)

            # Get backend state
            backend_state = ts_status.get("BackendState", "Unknown")
            is_connected = backend_state == "Running"

            # Count peers
            peers = ts_status.get("Peer", {})
            peer_count = len(peers)
            online_peers = sum(1 for p in peers.values() if p.get("Online", False))

            # Get magicDNS suffix
            magic_dns_suffix = ts_status.get("MagicDNSSuffix", "")

            return {
                "installed": True,
                "running": True,
                "logged_in": is_connected and online,
                "container_name": container_name,
                "container_status": container_status,
                "backend_state": backend_state,
                "tailscale_ip": tailscale_ips[0] if tailscale_ips else None,
                "tailscale_ips": tailscale_ips,
                "hostname": hostname,
                "dns_name": dns_name,
                "online": online,
                "peer_count": peer_count,
                "online_peers": online_peers,
                "peers": [],  # Empty list, frontend populates from API if needed
                "magic_dns_suffix": magic_dns_suffix,
                "healthy": is_connected and online,
            }

        except Exception as e:
            logger.warning(f"Failed to parse Tailscale status: {e}")
            return {
                "installed": True,
                "running": True,
                "logged_in": False,
                "container_name": container_name,
                "container_status": container_status,
                "error": str(e),
                "healthy": False,
            }
