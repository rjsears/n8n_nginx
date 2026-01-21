# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/config.py
#
# Configuration management from environment variables
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Redis connection
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    # Polling intervals (seconds)
    poll_interval_metrics: int = int(os.getenv("POLL_INTERVAL_METRICS", "5"))
    poll_interval_network: int = int(os.getenv("POLL_INTERVAL_NETWORK", "30"))
    poll_interval_containers: int = int(os.getenv("POLL_INTERVAL_CONTAINERS", "5"))
    poll_interval_external: int = int(os.getenv("POLL_INTERVAL_EXTERNAL", "15"))

    # Container names for external service checks
    cloudflare_container: str = os.getenv("CLOUDFLARE_CONTAINER", "n8n_cloudflared")
    tailscale_container: str = os.getenv("TAILSCALE_CONTAINER", "n8n_tailscale")
    ntfy_container: str = os.getenv("NTFY_CONTAINER", "n8n_ntfy")

    # Service URLs
    ntfy_url: str = os.getenv("NTFY_URL", "http://ntfy:80")

    # Health server
    health_port: int = int(os.getenv("HEALTH_PORT", "8080"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Container prefix for filtering project containers
    container_prefix: str = os.getenv("CONTAINER_PREFIX", "n8n")


# Global config instance
config = Config()
