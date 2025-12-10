"""
Container service - handles Docker container management via socket.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
from dateutil import parser as dateutil_parser
import logging
import asyncio

from api.models.audit import ContainerStatusCache
from api.config import settings
from api.services.notification_service import dispatch_notification

logger = logging.getLogger(__name__)


class ContainerInfo:
    """Container information."""
    def __init__(
        self,
        name: str,
        id: str,
        status: str,
        health: str,
        image: str,
        created: str,
        started_at: Optional[str] = None,
    ):
        self.name = name
        self.id = id
        self.status = status
        self.health = health
        self.image = image
        self.created = created
        self.started_at = started_at


class ContainerStats:
    """Container resource usage stats."""
    def __init__(
        self,
        name: str,
        cpu_percent: float,
        memory_usage: int,
        memory_limit: int,
        memory_percent: float,
        network_rx: int = 0,
        network_tx: int = 0,
    ):
        self.name = name
        self.cpu_percent = cpu_percent
        self.memory_usage = memory_usage
        self.memory_limit = memory_limit
        self.memory_percent = memory_percent
        self.network_rx = network_rx
        self.network_tx = network_tx


class ContainerService:
    """Docker container management service."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self._client = None

    @property
    def client(self):
        """Lazy-load Docker client."""
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    def _is_project_container(self, name: str) -> bool:
        """Check if container belongs to this project."""
        return name.startswith(settings.container_prefix)

    async def list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        """List all project containers."""
        containers = await asyncio.to_thread(self.client.containers.list, all=all)

        result = []
        for c in containers:
            if not self._is_project_container(c.name):
                continue

            health = "none"
            if c.attrs.get("State", {}).get("Health"):
                health = c.attrs["State"]["Health"].get("Status", "none")

            result.append({
                "name": c.name,
                "id": c.short_id,
                "status": c.status,
                "health": health,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "created": c.attrs.get("Created"),
                "started_at": c.attrs.get("State", {}).get("StartedAt"),
            })

        # Update cache if db available
        if self.db:
            await self._update_cache(result)

        return result

    async def get_container(self, name: str) -> Optional[Dict[str, Any]]:
        """Get container details."""
        if not self._is_project_container(name):
            return None

        try:
            container = await asyncio.to_thread(self.client.containers.get, name)

            health = "none"
            if container.attrs.get("State", {}).get("Health"):
                health = container.attrs["State"]["Health"].get("Status", "none")

            return {
                "name": container.name,
                "id": container.short_id,
                "status": container.status,
                "health": health,
                "image": container.image.tags[0] if container.image.tags else container.image.short_id,
                "created": container.attrs.get("Created"),
                "started_at": container.attrs.get("State", {}).get("StartedAt"),
                "ports": container.ports,
                "labels": container.labels,
                "environment": [e for e in container.attrs.get("Config", {}).get("Env", [])
                               if not any(s in e for s in ["PASSWORD", "SECRET", "KEY", "TOKEN"])],
            }
        except Exception as e:
            logger.error(f"Failed to get container {name}: {e}")
            return None

    async def get_stats(self) -> List[Dict[str, Any]]:
        """Get resource usage stats for all containers."""
        containers = await asyncio.to_thread(self.client.containers.list)

        stats = []
        for c in containers:
            if not self._is_project_container(c.name):
                continue

            try:
                s = await asyncio.to_thread(c.stats, stream=False)

                # Calculate CPU percentage
                cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - \
                           s["precpu_stats"]["cpu_usage"]["total_usage"]
                system_delta = s["cpu_stats"]["system_cpu_usage"] - \
                              s["precpu_stats"]["system_cpu_usage"]
                cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0

                # Memory
                memory_usage = s["memory_stats"].get("usage", 0)
                memory_limit = s["memory_stats"].get("limit", 0)

                # Network
                network_rx = sum(
                    net.get("rx_bytes", 0)
                    for net in s.get("networks", {}).values()
                )
                network_tx = sum(
                    net.get("tx_bytes", 0)
                    for net in s.get("networks", {}).values()
                )

                stats.append({
                    "name": c.name,
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_usage": memory_usage,
                    "memory_limit": memory_limit,
                    "memory_percent": round((memory_usage / memory_limit) * 100, 2) if memory_limit else 0,
                    "network_rx": network_rx,
                    "network_tx": network_tx,
                })
            except Exception as e:
                logger.warning(f"Failed to get stats for {c.name}: {e}")

        return stats

    async def start_container(self, name: str) -> bool:
        """Start a container."""
        if not self._is_project_container(name):
            raise ValueError("Can only manage project containers")

        try:
            container = await asyncio.to_thread(self.client.containers.get, name)
            await asyncio.to_thread(container.start)

            await dispatch_notification("container.started", {"container": name})
            logger.info(f"Started container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to start container {name}: {e}")
            raise

    async def stop_container(self, name: str, timeout: int = 30) -> bool:
        """Stop a container."""
        if not self._is_project_container(name):
            raise ValueError("Can only manage project containers")

        try:
            container = await asyncio.to_thread(self.client.containers.get, name)
            await asyncio.to_thread(container.stop, timeout=timeout)

            await dispatch_notification("container.stopped", {"container": name})
            logger.info(f"Stopped container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {name}: {e}")
            raise

    async def restart_container(self, name: str, timeout: int = 30) -> bool:
        """Restart a container."""
        if not self._is_project_container(name):
            raise ValueError("Can only manage project containers")

        try:
            container = await asyncio.to_thread(self.client.containers.get, name)
            await asyncio.to_thread(container.restart, timeout=timeout)

            await dispatch_notification("container.restarted", {"container": name})
            logger.info(f"Restarted container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to restart container {name}: {e}")
            raise

    async def get_logs(
        self,
        name: str,
        tail: int = 100,
        since: Optional[int] = None,
        timestamps: bool = True,
    ) -> str:
        """Get container logs."""
        if not self._is_project_container(name):
            raise ValueError("Can only manage project containers")

        try:
            container = await asyncio.to_thread(self.client.containers.get, name)

            kwargs = {
                "tail": tail,
                "timestamps": timestamps,
            }
            if since:
                kwargs["since"] = since

            logs = await asyncio.to_thread(container.logs, **kwargs)
            return logs.decode() if isinstance(logs, bytes) else logs
        except Exception as e:
            logger.error(f"Failed to get logs for {name}: {e}")
            raise

    def _parse_docker_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse Docker's ISO datetime string to datetime object."""
        if not dt_str:
            return None
        try:
            return dateutil_parser.isoparse(dt_str)
        except (ValueError, TypeError):
            return None

    async def _update_cache(self, containers: List[Dict[str, Any]]) -> None:
        """Update container status cache."""
        if not self.db:
            return

        from sqlalchemy import delete

        # Clear old cache
        await self.db.execute(delete(ContainerStatusCache))

        # Insert new cache
        for c in containers:
            cache = ContainerStatusCache(
                container_name=c["name"],
                container_id=c["id"],
                status=c["status"],
                health=c["health"],
                image=c["image"],
                started_at=self._parse_docker_datetime(c.get("started_at")),
                last_updated=datetime.now(UTC),
            )
            self.db.add(cache)

        await self.db.commit()

    async def check_health(self) -> Dict[str, Any]:
        """Check health of all project containers."""
        containers = await self.list_containers()

        healthy = []
        unhealthy = []
        stopped = []

        for c in containers:
            if c["status"] != "running":
                stopped.append(c["name"])
            elif c["health"] == "unhealthy":
                unhealthy.append(c["name"])
            else:
                healthy.append(c["name"])

        return {
            "total": len(containers),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "stopped": stopped,
            "all_healthy": len(unhealthy) == 0 and len(stopped) == 0,
        }
