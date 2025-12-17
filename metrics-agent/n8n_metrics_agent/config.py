"""
Configuration for the n8n Metrics Agent.
"""

import os
from pydantic import BaseModel
from typing import Optional, List


class AgentConfig(BaseModel):
    """Agent configuration with sensible defaults."""

    # Server settings
    host: str = "127.0.0.1"  # Only localhost by default for security
    port: int = 9100

    # API key for authentication (optional but recommended)
    api_key: Optional[str] = None

    # Docker settings
    docker_socket: str = "/var/run/docker.sock"

    # Disk monitoring - which mount points to monitor
    # Empty list means monitor all non-virtual filesystems
    disk_mount_points: List[str] = []

    # Excluded filesystem types (virtual filesystems)
    excluded_fs_types: List[str] = [
        "tmpfs", "devtmpfs", "devfs", "squashfs", "overlay",
        "aufs", "proc", "sysfs", "cgroup", "cgroup2"
    ]

    # Network interfaces to monitor (empty = all physical interfaces)
    network_interfaces: List[str] = []

    # Container name filter - only monitor containers matching these patterns
    # Empty list means monitor all containers
    container_filter: List[str] = []

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("METRICS_AGENT_HOST", "127.0.0.1"),
            port=int(os.getenv("METRICS_AGENT_PORT", "9100")),
            api_key=os.getenv("METRICS_AGENT_API_KEY"),
            docker_socket=os.getenv("DOCKER_SOCKET", "/var/run/docker.sock"),
            disk_mount_points=os.getenv("METRICS_DISK_MOUNTS", "").split(",") if os.getenv("METRICS_DISK_MOUNTS") else [],
            network_interfaces=os.getenv("METRICS_NETWORK_INTERFACES", "").split(",") if os.getenv("METRICS_NETWORK_INTERFACES") else [],
            container_filter=os.getenv("METRICS_CONTAINER_FILTER", "").split(",") if os.getenv("METRICS_CONTAINER_FILTER") else [],
            log_level=os.getenv("METRICS_LOG_LEVEL", "INFO"),
            log_file=os.getenv("METRICS_LOG_FILE"),
        )


# Global config instance
config = AgentConfig.from_env()
