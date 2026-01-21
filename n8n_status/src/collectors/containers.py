# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/containers.py
#
# Collects Docker container status and resource usage
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
from datetime import datetime, UTC
from typing import Any, Optional

import docker
from docker.errors import DockerException

from .base import BaseCollector
from ..config import config

logger = logging.getLogger(__name__)


class ContainerCollector(BaseCollector):
    """
    Collects Docker container information and resource statistics.

    Stores three separate keys:
    - containers:list - List of all containers with status
    - containers:stats - CPU/memory/network stats for running containers
    - containers:health - Health check summary
    """

    key = "containers:list"  # Primary key
    interval = config.poll_interval_containers
    ttl = 30

    def __init__(self):
        super().__init__()
        self._docker_client: Optional[docker.DockerClient] = None

    @property
    def docker_client(self) -> docker.DockerClient:
        """Lazy-load Docker client."""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def _is_project_container(self, name: str) -> bool:
        """Check if container belongs to this project."""
        prefix = config.container_prefix
        # Match containers that start with prefix or are exactly the prefix
        return name.startswith(f"{prefix}_") or name == prefix

    def collect(self) -> Any:
        """Collect container information."""
        try:
            containers = self.docker_client.containers.list(all=True)

            container_list = []
            stats_list = []
            healthy_containers = []
            unhealthy_containers = []
            stopped_containers = []

            for container in containers:
                # Get basic container info
                container_info = self._get_container_info(container)
                container_list.append(container_info)

                # Only process project containers for health summary
                if container_info["is_project"]:
                    if container_info["status"] != "running":
                        stopped_containers.append(container_info["name"])
                    elif container_info["health"] == "unhealthy":
                        unhealthy_containers.append(container_info["name"])
                    else:
                        healthy_containers.append(container_info["name"])

                # Get stats for running containers
                if container.status == "running":
                    stats = self._get_container_stats(container)
                    if stats:
                        stats_list.append(stats)

            # Store stats in separate key
            from ..redis_client import redis_client
            redis_client.set_json("containers:stats", stats_list, ttl=self.ttl)

            # Store health summary in separate key
            health_summary = {
                "total": len([c for c in container_list if c["is_project"]]),
                "healthy": healthy_containers,
                "unhealthy": unhealthy_containers,
                "stopped": stopped_containers,
                "all_healthy": len(unhealthy_containers) == 0 and len(stopped_containers) == 0,
            }
            redis_client.set_json("containers:health", health_summary, ttl=self.ttl)

            return container_list

        except DockerException as e:
            logger.error(f"Docker error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to collect container info: {e}")
            raise

    def _get_container_info(self, container) -> dict:
        """Get basic container information."""
        try:
            # Get health status
            health = "none"
            health_state = container.attrs.get("State", {}).get("Health")
            if health_state:
                health = health_state.get("Status", "none")

            # Get started_at and calculate uptime
            started_at = container.attrs.get("State", {}).get("StartedAt")
            uptime = self._format_uptime(started_at) if container.status == "running" else None

            # Get image name
            image = container.image.tags[0] if container.image.tags else container.image.short_id

            return {
                "name": container.name,
                "id": container.short_id,
                "status": container.status,
                "health": health,
                "image": image,
                "created": container.attrs.get("Created"),
                "started_at": started_at,
                "uptime": uptime,
                "restart_count": container.attrs.get("RestartCount", 0),
                "is_project": self._is_project_container(container.name),
            }
        except Exception as e:
            logger.warning(f"Failed to get info for {container.name}: {e}")
            return {
                "name": container.name,
                "id": container.short_id,
                "status": "unknown",
                "health": "unknown",
                "error": str(e),
                "is_project": self._is_project_container(container.name),
            }

    def _get_container_stats(self, container) -> Optional[dict]:
        """Get resource usage stats for a running container."""
        try:
            # Use stream=False for a single snapshot (faster)
            stats = container.stats(stream=False)

            # Calculate CPU percentage
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0

            # Memory stats
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 0)
            memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0

            # Network stats
            network_rx = sum(
                net.get("rx_bytes", 0)
                for net in stats.get("networks", {}).values()
            )
            network_tx = sum(
                net.get("tx_bytes", 0)
                for net in stats.get("networks", {}).values()
            )

            return {
                "name": container.name,
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage": memory_usage,
                "memory_limit": memory_limit,
                "memory_percent": round(memory_percent, 2),
                "memory_usage_human": self._bytes_to_human(memory_usage),
                "memory_limit_human": self._bytes_to_human(memory_limit),
                "network_rx": network_rx,
                "network_tx": network_tx,
                "network_rx_human": self._bytes_to_human(network_rx),
                "network_tx_human": self._bytes_to_human(network_tx),
                "is_project": self._is_project_container(container.name),
            }

        except Exception as e:
            logger.debug(f"Failed to get stats for {container.name}: {e}")
            return None

    def _format_uptime(self, started_at: Optional[str]) -> Optional[str]:
        """Convert started_at datetime to human-readable uptime."""
        if not started_at:
            return None
        try:
            from dateutil import parser as dateutil_parser
            start_time = dateutil_parser.isoparse(started_at)
            now = datetime.now(UTC)
            delta = now - start_time

            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            if days > 0:
                return f"{days}d {hours}h"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return None

    @staticmethod
    def _bytes_to_human(bytes_val: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(bytes_val) < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"
