# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/cloudflare.py
#
# Collects Cloudflare Tunnel status
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
import re
from typing import Any, Optional

import docker
import httpx
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

                # Get metrics from Prometheus endpoint (if available)
                self._get_metrics(container, result)

                # Parse logs for status, edge locations, tunnel/connector IDs
                # This also serves as fallback when metrics endpoint is unavailable
                self._parse_logs(container, result)

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

    def _get_container_ip(self, container) -> Optional[str]:
        """Get the container's IP address on the Docker network."""
        try:
            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            # Try common network names first
            for network_name in ["n8n_nginx_default", "n8n_nginx", "bridge"]:
                if network_name in networks:
                    ip = networks[network_name].get("IPAddress")
                    if ip:
                        return ip
            # Fall back to first available network
            for network_data in networks.values():
                ip = network_data.get("IPAddress")
                if ip:
                    return ip
        except Exception as e:
            logger.debug(f"Failed to get container IP: {e}")
        return None

    def _get_metrics(self, container, result: dict):
        """Get metrics from Prometheus endpoint."""
        try:
            # Get container IP to fetch metrics from outside the container
            # (cloudflared container doesn't have curl/wget)
            container_ip = self._get_container_ip(container)
            if not container_ip:
                logger.debug("Could not determine cloudflared container IP for metrics")
                return

            # Fetch metrics using httpx
            metrics_url = f"http://{container_ip}:2000/metrics"
            with httpx.Client(timeout=5.0) as client:
                response = client.get(metrics_url)
                if response.status_code != 200:
                    logger.debug(f"Metrics endpoint returned {response.status_code}")
                    return
                metrics_text = response.text
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

    def _parse_logs(self, container, result: dict):
        """
        Parse cloudflared logs to determine tunnel status, edge locations, and IDs.

        Updates result dict with:
        - tunnel_status, connection_count, last_error
        - edge_locations, connections_per_location (from log parsing)
        - tunnel_id, connector_id
        """
        status = "unknown"
        connection_count = 0
        last_error = None
        edge_locations = []
        connections_per_location = {}

        try:
            logs = container.logs(tail=100, timestamps=False).decode("utf-8", errors="ignore")
            lines = logs.strip().split("\n")

            # Skip common non-error warnings
            skip_patterns = [
                "cert.pem",
                "Cannot determine default origin certificate",
                "Update check",
                "failed to sufficiently increase receive buffer size",
            ]

            for line in lines:
                line_lower = line.lower()

                # Extract tunnel ID (format: tunnelID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
                if not result.get("tunnel_id"):
                    tunnel_id_match = re.search(r'tunnelID=([a-f0-9-]{36})', line)
                    if tunnel_id_match:
                        result["tunnel_id"] = tunnel_id_match.group(1)

                # Extract connector ID
                if not result.get("connector_id"):
                    connector_match = re.search(r'connectorID=([a-f0-9-]{36})', line)
                    if connector_match:
                        result["connector_id"] = connector_match.group(1)

                # Extract edge locations from connection registration lines
                if "registered tunnel connection" in line_lower or "connection registered" in line_lower:
                    loc_match = re.search(r'location=(\w+)', line, re.IGNORECASE)
                    if loc_match:
                        location = loc_match.group(1).upper()
                        if location not in edge_locations:
                            edge_locations.append(location)
                        connections_per_location[location] = connections_per_location.get(location, 0) + 1
                    connection_count += 1
                    status = "connected"

            # Second pass for status and errors (reversed for most recent)
            for line in reversed(lines):
                line_lower = line.lower()

                # Check for connection established
                if "registered" in line_lower and "connector" in line_lower:
                    status = "connected"

                # Check for tunnel connection
                elif "connection" in line_lower and "registered" in line_lower:
                    status = "connected"

                # Check for successful tunnel start
                elif "tunnel" in line_lower and "connected" in line_lower:
                    status = "connected"

                # Check for errors (skip common warnings)
                elif ("error" in line_lower or "failed" in line_lower) and not last_error:
                    if not any(skip in line for skip in skip_patterns):
                        last_error = line.strip()[-200:]

                # Check for reconnection attempts
                elif "reconnect" in line_lower or "retrying" in line_lower:
                    if status == "unknown":
                        status = "reconnecting"

            # If we found connections, it's connected
            if connection_count > 0:
                status = "connected"

            # Update result with parsed data
            result["tunnel_status"] = status
            result["connection_count"] = connection_count
            result["last_error"] = last_error
            result["connected"] = status == "connected"
            result["healthy"] = status == "connected"

            # Only update edge_locations if we found some from logs
            # (don't overwrite if metrics already populated them)
            if edge_locations and not result.get("edge_locations"):
                result["edge_locations"] = edge_locations
            if connections_per_location and not result.get("connections_per_location"):
                result["connections_per_location"] = connections_per_location

        except Exception as e:
            logger.debug(f"Failed to parse cloudflared logs: {e}")
