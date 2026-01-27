# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/cloudflare.py
#
# Collects Cloudflare Tunnel status
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
import re
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
    - Version from cloudflared version command
    - Metrics from Prometheus endpoint (:2000/metrics)
    - Recent logs for connection status
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

            result = {
                "installed": True,
                "running": is_running,
                "container_name": container_name,
                "container_status": status,
                "container_health": health,
                "tunnel_status": "unknown",
                "connected": False,
                "connection_count": 0,
                "last_error": None,
                "healthy": False,
                "version": None,
                "tunnel_id": None,
                "connector_id": None,
                "edge_locations": [],
                "connections_per_location": {},
                "metrics": {},
            }

            if is_running:
                # Get version
                result["version"] = self._get_version(container)

                # Get tunnel info from environment
                self._get_tunnel_info(container, result)

                # Get metrics from Prometheus endpoint
                self._get_metrics(container, result)

                # Parse logs for additional status info
                tunnel_status, connection_count, last_error = self._parse_logs(container)
                result["tunnel_status"] = tunnel_status
                result["connection_count"] = connection_count
                result["last_error"] = last_error
                result["connected"] = tunnel_status == "connected"
                result["healthy"] = tunnel_status == "connected"

            return result

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

    def _get_version(self, container) -> Optional[str]:
        """Get cloudflared version."""
        try:
            exit_code, output = container.exec_run(
                "cloudflared version",
                demux=True
            )
            if exit_code == 0 and output[0]:
                version_output = output[0].decode("utf-8").strip()
                # Parse "cloudflared version 2024.1.0 (built 2024-01-15-1234)"
                match = re.search(r'version\s+([\d.]+)', version_output)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.debug(f"Failed to get cloudflared version: {e}")
        return None

    def _get_tunnel_info(self, container, result: dict):
        """Get tunnel info from environment variables."""
        try:
            env_vars = container.attrs.get("Config", {}).get("Env", [])
            for env in env_vars:
                if env.startswith("TUNNEL_TOKEN="):
                    result["has_token"] = True
                elif env.startswith("TUNNEL_NAME="):
                    result["tunnel_name"] = env.split("=", 1)[1]
        except Exception as e:
            logger.debug(f"Failed to get tunnel info: {e}")

    def _get_metrics(self, container, result: dict):
        """Get metrics from Prometheus endpoint."""
        try:
            # Try curl first, then wget
            exit_code, output = container.exec_run(
                "curl -s http://localhost:2000/metrics 2>/dev/null || wget -q -O- http://localhost:2000/metrics 2>/dev/null",
                demux=True
            )

            if exit_code != 0 or not output[0]:
                return

            metrics_text = output[0].decode("utf-8")
            if len(metrics_text) < 100:
                return

            metrics = result["metrics"]

            # Parse active streams
            match = re.search(r'cloudflared_tunnel_active_streams\s+(\d+)', metrics_text)
            if match:
                metrics["active_streams"] = int(match.group(1))

            # Parse total requests
            match = re.search(r'cloudflared_tunnel_total_requests\s+(\d+)', metrics_text)
            if match:
                metrics["total_requests"] = int(match.group(1))

            # Parse request errors
            match = re.search(r'cloudflared_tunnel_request_errors\s+(\d+)', metrics_text)
            if match:
                metrics["request_errors"] = int(match.group(1))

            # Parse HA connections
            match = re.search(r'cloudflared_tunnel_ha_connections\s+(\d+)', metrics_text)
            if match:
                metrics["ha_connections"] = int(match.group(1))

            # Parse timer retries
            match = re.search(r'cloudflared_tunnel_timer_retries\s+(\d+)', metrics_text)
            if match:
                metrics["timer_retries"] = int(match.group(1))

            # Parse response codes
            response_codes = {}
            for match in re.finditer(r'cloudflared_tunnel_response_by_code\{.*?status="(\d+)".*?\}\s+(\d+)', metrics_text):
                code = match.group(1)
                count = int(match.group(2))
                if count > 0:
                    response_codes[code] = count
            if response_codes:
                metrics["response_codes"] = response_codes

            # Parse server locations (edge locations)
            edge_locations = []
            connections_per_location = {}
            for match in re.finditer(r'cloudflared_tunnel_server_locations\{.*?location="([^"]+)".*?\}\s+(\d+)', metrics_text):
                location = match.group(1)
                count = int(match.group(2))
                if count > 0:
                    if location not in edge_locations:
                        edge_locations.append(location)
                    connections_per_location[location] = count

            if edge_locations:
                result["edge_locations"] = edge_locations
            if connections_per_location:
                result["connections_per_location"] = connections_per_location

            # Parse concurrent requests
            match = re.search(r'cloudflared_tunnel_concurrent_requests_per_tunnel\{.*?\}\s+(\d+)', metrics_text)
            if match:
                metrics["concurrent_requests"] = int(match.group(1))

        except Exception as e:
            logger.debug(f"Failed to get cloudflared metrics: {e}")

    def _parse_logs(self, container) -> tuple[str, int, Optional[str]]:
        """
        Parse cloudflared logs to determine tunnel status.

        Returns:
            (status, connection_count, last_error)
        """
        status = "unknown"
        connection_count = 0
        last_error = None

        try:
            logs = container.logs(tail=100, timestamps=False).decode("utf-8", errors="ignore")
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

        except Exception as e:
            logger.debug(f"Failed to parse cloudflared logs: {e}")

        return status, connection_count, last_error
