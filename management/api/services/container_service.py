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
        # Include containers that start with prefix OR are exactly the base name (e.g., "n8n")
        prefix = settings.container_prefix.rstrip("_")  # "n8n_" -> "n8n"
        return name.startswith(settings.container_prefix) or name == prefix

    def _format_uptime(self, started_at: Optional[str]) -> Optional[str]:
        """Convert started_at datetime to human-readable uptime."""
        if not started_at:
            return None
        try:
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

            started_at = c.attrs.get("State", {}).get("StartedAt")
            uptime = self._format_uptime(started_at) if c.status == "running" else None

            result.append({
                "name": c.name,
                "id": c.short_id,
                "status": c.status,
                "health": health,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "created": c.attrs.get("Created"),
                "started_at": started_at,
                "uptime": uptime,
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

    async def recreate_container(self, name: str, pull: bool = False) -> bool:
        """Recreate a container using docker-compose.

        This stops, removes, and recreates the container with the same config.
        Optionally pulls the latest image first.
        """
        import subprocess

        if not self._is_project_container(name):
            raise ValueError("Can only manage project containers")

        # Get the service name from container name
        # Container names are typically "n8n_service" or just "n8n"
        prefix = settings.container_prefix.rstrip("_")
        if name.startswith(settings.container_prefix):
            service_name = name[len(settings.container_prefix):]
        elif name == prefix:
            service_name = name
        else:
            service_name = name

        # Find docker-compose.yaml in the project root
        compose_file = settings.project_root / "docker-compose.yaml"
        if not compose_file.exists():
            compose_file = settings.project_root / "docker-compose.yml"

        if not compose_file.exists():
            raise ValueError("docker-compose.yaml not found")

        try:
            # Build the docker-compose command
            cmd = [
                "docker-compose",
                "-f", str(compose_file),
                "up", "-d",
                "--force-recreate",
                "--no-deps",
            ]

            if pull:
                # Pull latest image first
                pull_cmd = [
                    "docker-compose",
                    "-f", str(compose_file),
                    "pull",
                    service_name,
                ]
                pull_result = await asyncio.to_thread(
                    subprocess.run,
                    pull_cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(settings.project_root),
                )
                if pull_result.returncode != 0:
                    logger.warning(f"Failed to pull image for {service_name}: {pull_result.stderr}")

            # Add service name to recreate command
            cmd.append(service_name)

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                cwd=str(settings.project_root),
            )

            if result.returncode != 0:
                raise Exception(f"docker-compose failed: {result.stderr}")

            await dispatch_notification("container.recreated", {"container": name, "pulled": pull})
            logger.info(f"Recreated container: {name} (pull={pull})")
            return True
        except Exception as e:
            logger.error(f"Failed to recreate container {name}: {e}")
            raise

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
