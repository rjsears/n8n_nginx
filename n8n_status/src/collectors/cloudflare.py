# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/cloudflare.py
#
# Collects Cloudflare Tunnel status
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
from typing import Any, Optional

import docker
from docker.errors import NotFound, DockerException

from .base import BaseCollector
from ..config import config

logger = logging.getLogger(__name__)


class CloudflareCollector(BaseCollector):
    """
    Collects Cloudflare Tunnel status by checking the cloudflared container.

    Checks:
    - Container running status
    - Recent logs for connection status
    - Tunnel health indicators
    """

    key = "system:cloudflare"
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
        """Collect Cloudflare tunnel status."""
        container_name = config.cloudflare_container

        try:
            container = self.docker_client.containers.get(container_name)

            # Get container status
            status = container.status
            health = container.attrs.get("State", {}).get("Health", {}).get("Status", "none")

            # Check if running
            is_running = status == "running"

            # Get recent logs to check tunnel status
            tunnel_status = "unknown"
            connection_count = 0
            last_error = None

            if is_running:
                try:
                    logs = container.logs(tail=100, timestamps=False).decode("utf-8", errors="ignore")
                    tunnel_status, connection_count, last_error = self._parse_cloudflared_logs(logs)
                except Exception as e:
                    logger.debug(f"Failed to get cloudflared logs: {e}")

            return {
                "installed": True,
                "running": is_running,
                "container_name": container_name,
                "container_status": status,
                "container_health": health,
                "tunnel_status": tunnel_status,
                "connected": tunnel_status == "connected",
                "connection_count": connection_count,
                "last_error": last_error,
                "healthy": is_running and tunnel_status == "connected",
            }

        except NotFound:
            return {
                "installed": False,
                "running": False,
                "container_name": container_name,
                "error": "Container not found",
                "healthy": False,
            }
        except DockerException as e:
            logger.error(f"Docker error checking Cloudflare: {e}")
            return {
                "installed": False,
                "running": False,
                "container_name": container_name,
                "error": str(e),
                "healthy": False,
            }

    def _parse_cloudflared_logs(self, logs: str) -> tuple[str, int, Optional[str]]:
        """
        Parse cloudflared logs to determine tunnel status.

        Returns:
            (status, connection_count, last_error)
        """
        status = "unknown"
        connection_count = 0
        last_error = None

        lines = logs.strip().split("\n")

        for line in reversed(lines):
            line_lower = line.lower()

            # Check for connection established
            if "registered" in line_lower and "connector" in line_lower:
                status = "connected"
                connection_count += 1

            # Check for tunnel connection
            elif "connection" in line_lower and "registered" in line_lower:
                status = "connected"

            # Check for successful tunnel start
            elif "tunnel" in line_lower and "connected" in line_lower:
                status = "connected"

            # Check for errors
            elif "error" in line_lower or "failed" in line_lower:
                if not last_error:
                    last_error = line.strip()[-200:]  # Truncate long errors

            # Check for reconnection attempts
            elif "reconnect" in line_lower or "retrying" in line_lower:
                if status == "unknown":
                    status = "reconnecting"

        # If we found connections, it's connected
        if connection_count > 0:
            status = "connected"

        return status, connection_count, last_error
