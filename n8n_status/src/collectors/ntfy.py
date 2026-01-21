# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/ntfy.py
#
# Collects NTFY push notification service status
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
from typing import Any, Optional

import httpx
import docker
from docker.errors import NotFound, DockerException

from .base import BaseCollector
from ..config import config

logger = logging.getLogger(__name__)


class NtfyCollector(BaseCollector):
    """
    Collects NTFY service status.

    Checks:
    - Container running status
    - HTTP health endpoint
    - Service availability
    """

    key = "services:ntfy"
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
        """Collect NTFY status."""
        container_name = config.ntfy_container
        ntfy_url = config.ntfy_url

        # First check container status
        container_info = self._check_container(container_name)

        # If container is running, check HTTP health
        http_health = None
        if container_info.get("is_running"):
            http_health = self._check_http_health(ntfy_url)

        return {
            **container_info,
            "http_health": http_health,
            "healthy": (
                container_info.get("is_running", False)
                and http_health is not None
                and http_health.get("healthy", False)
            ),
        }

    def _check_container(self, container_name: str) -> dict:
        """Check NTFY container status."""
        try:
            container = self.docker_client.containers.get(container_name)

            status = container.status
            health = container.attrs.get("State", {}).get("Health", {}).get("Status", "none")

            return {
                "available": True,
                "container_name": container_name,
                "container_status": status,
                "container_health": health,
                "is_running": status == "running",
            }

        except NotFound:
            return {
                "available": False,
                "container_name": container_name,
                "error": "Container not found",
                "is_running": False,
            }
        except DockerException as e:
            logger.error(f"Docker error checking NTFY container: {e}")
            return {
                "available": False,
                "container_name": container_name,
                "error": str(e),
                "is_running": False,
            }

    def _check_http_health(self, ntfy_url: str) -> Optional[dict]:
        """Check NTFY HTTP health endpoint."""
        try:
            health_url = f"{ntfy_url.rstrip('/')}/v1/health"

            with httpx.Client(timeout=5.0) as client:
                response = client.get(health_url)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        return {
                            "healthy": data.get("healthy", False),
                            "status_code": response.status_code,
                            "response": data,
                        }
                    except Exception:
                        # Response wasn't JSON, but 200 is still good
                        return {
                            "healthy": True,
                            "status_code": response.status_code,
                        }
                else:
                    return {
                        "healthy": False,
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}",
                    }

        except httpx.TimeoutException:
            return {
                "healthy": False,
                "error": "Connection timeout",
            }
        except httpx.ConnectError as e:
            return {
                "healthy": False,
                "error": f"Connection failed: {e}",
            }
        except Exception as e:
            logger.warning(f"Failed to check NTFY health: {e}")
            return {
                "healthy": False,
                "error": str(e),
            }
