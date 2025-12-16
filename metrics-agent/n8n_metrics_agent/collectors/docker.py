"""
Docker container metrics collector.

Collects container status, health, resource usage, and detects state changes.
"""

import docker
from docker.errors import DockerException, NotFound
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import logging
import fnmatch

from n8n_metrics_agent.models import ContainerMetrics, ContainerEvent
from n8n_metrics_agent.config import config

logger = logging.getLogger(__name__)


class DockerCollector:
    """Collects Docker container metrics and detects state changes."""

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._last_container_states: Dict[str, Dict[str, Any]] = {}
        self._available = False
        self._connect()

    def _connect(self) -> bool:
        """Connect to Docker daemon."""
        try:
            self._client = docker.DockerClient(base_url=f"unix://{config.docker_socket}")
            self._client.ping()
            self._available = True
            logger.info("Connected to Docker daemon")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Docker: {e}")
            self._client = None
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if Docker is available."""
        if not self._available or not self._client:
            return self._connect()

        try:
            self._client.ping()
            return True
        except Exception:
            self._available = False
            return False

    def _matches_filter(self, container_name: str) -> bool:
        """Check if container name matches the configured filter."""
        if not config.container_filter:
            return True  # No filter = include all

        for pattern in config.container_filter:
            if fnmatch.fnmatch(container_name, pattern):
                return True
        return False

    def _get_container_stats(self, container) -> Dict[str, Any]:
        """Get resource stats for a container (non-blocking)."""
        try:
            # Use stream=False for a single snapshot
            stats = container.stats(stream=False)

            # Calculate CPU percentage
            cpu_percent = 0.0
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})

            cpu_usage = cpu_stats.get("cpu_usage", {})
            precpu_usage = precpu_stats.get("cpu_usage", {})

            cpu_delta = cpu_usage.get("total_usage", 0) - precpu_usage.get("total_usage", 0)
            system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)

            if system_delta > 0 and cpu_delta > 0:
                cpu_count = len(cpu_usage.get("percpu_usage", [])) or 1
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0

            # Memory stats
            memory_stats = stats.get("memory_stats", {})
            memory_usage = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 0)
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0.0

            # Network stats
            networks = stats.get("networks", {})
            rx_bytes = sum(n.get("rx_bytes", 0) for n in networks.values())
            tx_bytes = sum(n.get("tx_bytes", 0) for n in networks.values())

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage_bytes": memory_usage,
                "memory_limit_bytes": memory_limit,
                "memory_percent": round(memory_percent, 2),
                "network_rx_bytes": rx_bytes,
                "network_tx_bytes": tx_bytes,
            }
        except Exception as e:
            logger.debug(f"Failed to get stats for container: {e}")
            return {}

    def get_container_metrics(self, include_stats: bool = False) -> List[ContainerMetrics]:
        """Get metrics for all containers."""
        containers = []

        if not self.is_available:
            return containers

        try:
            for container in self._client.containers.list(all=True):
                try:
                    name = container.name

                    # Apply filter
                    if not self._matches_filter(name):
                        continue

                    # Get container attributes
                    attrs = container.attrs
                    state = attrs.get("State", {})

                    # Get health status
                    health = None
                    if "Health" in state:
                        health = state["Health"].get("Status", "none")

                    # Get restart count
                    restart_count = state.get("RestartCount", 0)

                    # Build container metrics
                    metrics = ContainerMetrics(
                        id=container.short_id,
                        name=name,
                        image=container.image.tags[0] if container.image.tags else container.image.short_id,
                        status=container.status,
                        state=state.get("Status", "unknown"),
                        health=health,
                        created_at=attrs.get("Created"),
                        started_at=state.get("StartedAt"),
                        restart_count=restart_count,
                        labels=container.labels,
                    )

                    # Get resource stats if requested and container is running
                    if include_stats and container.status == "running":
                        stats = self._get_container_stats(container)
                        metrics.cpu_percent = stats.get("cpu_percent")
                        metrics.memory_usage_bytes = stats.get("memory_usage_bytes")
                        metrics.memory_limit_bytes = stats.get("memory_limit_bytes")
                        metrics.memory_percent = stats.get("memory_percent")
                        metrics.network_rx_bytes = stats.get("network_rx_bytes")
                        metrics.network_tx_bytes = stats.get("network_tx_bytes")

                    containers.append(metrics)

                except Exception as e:
                    logger.debug(f"Error processing container {container.name}: {e}")

        except Exception as e:
            logger.error(f"Failed to list containers: {e}")

        return containers

    def detect_state_changes(self) -> List[ContainerEvent]:
        """Detect container state changes since last check."""
        events = []

        if not self.is_available:
            return events

        current_states: Dict[str, Dict[str, Any]] = {}

        try:
            for container in self._client.containers.list(all=True):
                try:
                    name = container.name

                    if not self._matches_filter(name):
                        continue

                    attrs = container.attrs
                    state = attrs.get("State", {})

                    # Get health status
                    health = None
                    if "Health" in state:
                        health = state["Health"].get("Status", "none")

                    current_state = {
                        "status": container.status,
                        "state": state.get("Status", "unknown"),
                        "health": health,
                        "restart_count": state.get("RestartCount", 0),
                    }

                    current_states[name] = current_state

                    # Check for changes if we have previous state
                    if name in self._last_container_states:
                        last = self._last_container_states[name]

                        # Check health change
                        if last.get("health") != current_state["health"]:
                            events.append(ContainerEvent(
                                container_id=container.short_id,
                                container_name=name,
                                event_type="health_changed",
                                old_value=last.get("health"),
                                new_value=current_state["health"],
                                timestamp=datetime.now(timezone.utc),
                                details={"status": current_state["status"]},
                            ))

                        # Check status change
                        if last.get("status") != current_state["status"]:
                            events.append(ContainerEvent(
                                container_id=container.short_id,
                                container_name=name,
                                event_type="status_changed",
                                old_value=last.get("status"),
                                new_value=current_state["status"],
                                timestamp=datetime.now(timezone.utc),
                                details={"health": current_state["health"]},
                            ))

                        # Check for restart
                        if current_state["restart_count"] > last.get("restart_count", 0):
                            events.append(ContainerEvent(
                                container_id=container.short_id,
                                container_name=name,
                                event_type="restart",
                                old_value=str(last.get("restart_count", 0)),
                                new_value=str(current_state["restart_count"]),
                                timestamp=datetime.now(timezone.utc),
                                details={
                                    "status": current_state["status"],
                                    "health": current_state["health"],
                                },
                            ))

                except Exception as e:
                    logger.debug(f"Error checking state for container: {e}")

            # Update last known states
            self._last_container_states = current_states

        except Exception as e:
            logger.error(f"Failed to detect container state changes: {e}")

        return events

    def get_container_by_name(self, name: str) -> Optional[ContainerMetrics]:
        """Get metrics for a specific container by name."""
        if not self.is_available:
            return None

        try:
            container = self._client.containers.get(name)
            attrs = container.attrs
            state = attrs.get("State", {})

            health = None
            if "Health" in state:
                health = state["Health"].get("Status", "none")

            return ContainerMetrics(
                id=container.short_id,
                name=container.name,
                image=container.image.tags[0] if container.image.tags else container.image.short_id,
                status=container.status,
                state=state.get("Status", "unknown"),
                health=health,
                created_at=attrs.get("Created"),
                started_at=state.get("StartedAt"),
                restart_count=state.get("RestartCount", 0),
                labels=container.labels,
            )
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get container {name}: {e}")
            return None
