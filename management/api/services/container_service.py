"""
Container service - handles Docker container management via socket.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
from dateutil import parser as dateutil_parser
import logging
import asyncio
import subprocess
import os

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
        """List all containers on the system with is_project flag."""
        containers = await asyncio.to_thread(self.client.containers.list, all=all)

        result = []
        for c in containers:
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
                "is_project": self._is_project_container(c.name),
            })

        # Update cache if db available (only project containers)
        if self.db:
            project_containers = [c for c in result if c["is_project"]]
            await self._update_cache(project_containers)

        return result

    async def get_container(self, name: str) -> Optional[Dict[str, Any]]:
        """Get container details for any container."""
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
                "is_project": self._is_project_container(container.name),
            }
        except Exception as e:
            logger.error(f"Failed to get container {name}: {e}")
            return None

    async def get_stats(self) -> List[Dict[str, Any]]:
        """Get resource usage stats for all running containers."""
        containers = await asyncio.to_thread(self.client.containers.list)

        stats = []
        for c in containers:
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
                    "is_project": self._is_project_container(c.name),
                })
            except Exception as e:
                logger.warning(f"Failed to get stats for {c.name}: {e}")

        return stats

    async def start_container(self, name: str) -> bool:
        """Start a container."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, name)
            await asyncio.to_thread(container.start)

            # Only send notifications for project containers
            if self._is_project_container(name):
                await dispatch_notification("container_started", {"container": name})
            logger.info(f"Started container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to start container {name}: {e}")
            raise

    async def stop_container(self, name: str, timeout: int = 30) -> bool:
        """Stop a container."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, name)
            await asyncio.to_thread(container.stop, timeout=timeout)

            # Only send notifications for project containers
            if self._is_project_container(name):
                await dispatch_notification("container_stopped", {"container": name})
            logger.info(f"Stopped container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {name}: {e}")
            raise

    async def restart_container(self, name: str, timeout: int = 30) -> bool:
        """Restart a container."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, name)
            await asyncio.to_thread(container.restart, timeout=timeout)

            # Only send notifications for project containers
            if self._is_project_container(name):
                await dispatch_notification("container_restart", {"container": name})
            logger.info(f"Restarted container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to restart container {name}: {e}")
            raise

    async def remove_container(self, name: str, force: bool = False) -> bool:
        """Remove a stopped container."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, name)

            # Check if container is running (unless force=True)
            if container.status == "running" and not force:
                raise ValueError(f"Container {name} is still running. Stop it first or use force=True")

            await asyncio.to_thread(container.remove, force=force)

            # Only send notifications for project containers
            if self._is_project_container(name):
                await dispatch_notification("container_removed", {"container": name})
            logger.info(f"Removed container: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container {name}: {e}")
            raise

    async def get_logs(
        self,
        name: str,
        tail: int = 100,
        since: Optional[int] = None,
        timestamps: bool = True,
    ) -> str:
        """Get container logs."""
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

    def _get_service_name_from_container(self, container_name: str) -> str:
        """
        Get the docker-compose service name from a container name.
        Container names are typically: n8n_postgres, n8n_nginx, n8n, etc.
        Service names are: postgres, nginx, n8n, etc.
        """
        try:
            container = self.client.containers.get(container_name)
            # Docker Compose sets labels on containers with the service name
            labels = container.labels
            service_name = labels.get("com.docker.compose.service")
            if service_name:
                return service_name
        except Exception as e:
            logger.warning(f"Could not get service name from labels for {container_name}: {e}")

        # Fallback: strip the prefix
        prefix = settings.container_prefix  # e.g., "n8n_"
        if container_name.startswith(prefix):
            return container_name[len(prefix):]
        return container_name

    async def recreate_container(self, name: str, pull: bool = False) -> Dict[str, Any]:
        """
        Recreate a container using docker compose.

        Args:
            name: Container name
            pull: If True, pull the latest image before recreating

        Returns:
            Dict with success status and output
        """
        service_name = self._get_service_name_from_container(name)
        compose_dir = "/app/host_config"  # Directory with docker-compose.yaml

        # Build the docker compose command
        if pull:
            cmd = [
                "docker", "compose",
                "-f", f"{compose_dir}/docker-compose.yaml",
                "up", "-d", "--no-deps", "--force-recreate", "--pull", "always",
                service_name
            ]
        else:
            cmd = [
                "docker", "compose",
                "-f", f"{compose_dir}/docker-compose.yaml",
                "up", "-d", "--no-deps", "--force-recreate",
                service_name
            ]

        logger.info(f"Recreating container {name} (service: {service_name}), pull={pull}")
        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            # Run docker compose command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=compose_dir,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Failed to recreate {name}: {error_msg}")
                raise Exception(f"docker compose failed: {error_msg}")

            output = stdout.decode() if stdout else ""
            if stderr:
                output += "\n" + stderr.decode()

            # Send notification for project containers
            if self._is_project_container(name):
                action = "pulled and recreated" if pull else "recreated"
                await dispatch_notification("container_recreated", {
                    "container": name,
                    "action": action,
                    "pulled": pull,
                })

            logger.info(f"Successfully recreated container {name}")
            return {
                "success": True,
                "container": name,
                "service": service_name,
                "pulled": pull,
                "output": output.strip(),
            }

        except Exception as e:
            logger.error(f"Failed to recreate container {name}: {e}")
            raise
