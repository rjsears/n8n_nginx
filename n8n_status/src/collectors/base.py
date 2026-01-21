# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/collectors/base.py
#
# Base collector class for all data collectors
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import logging
from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Any, Optional

from ..redis_client import redis_client

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Base class for all data collectors.

    Subclasses must implement:
    - key: Redis key to store data under
    - interval: Polling interval in seconds
    - ttl: Time-to-live for cached data (default: 2x interval)
    - collect(): Method that returns the data to cache
    """

    key: str = ""
    interval: int = 60
    ttl: Optional[int] = None

    def __init__(self):
        self.name = self.__class__.__name__
        self.last_run: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.run_count: int = 0
        self.error_count: int = 0
        self._enabled = True

        # Default TTL to 2x interval if not specified
        if self.ttl is None:
            self.ttl = self.interval * 2

    @abstractmethod
    def collect(self) -> Any:
        """
        Collect data to be cached.

        Returns:
            Data to store in Redis (must be JSON-serializable)
        """
        pass

    def run(self) -> bool:
        """
        Execute the collector and store results in Redis.

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            logger.debug(f"{self.name} is disabled, skipping")
            return False

        try:
            logger.debug(f"Running {self.name}")
            data = self.collect()

            if data is not None:
                success = redis_client.set_json(self.key, data, self.ttl)
                if success:
                    self.last_run = datetime.now(UTC)
                    self.last_error = None
                    self.run_count += 1
                    logger.debug(f"{self.name} completed successfully")
                    return True
                else:
                    self.last_error = "Failed to store in Redis"
                    self.error_count += 1
                    return False
            else:
                self.last_error = "Collector returned None"
                self.error_count += 1
                logger.warning(f"{self.name} returned None")
                return False

        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            return False

    def enable(self):
        """Enable the collector."""
        self._enabled = True
        logger.info(f"{self.name} enabled")

    def disable(self):
        """Disable the collector."""
        self._enabled = False
        logger.info(f"{self.name} disabled")

    def is_enabled(self) -> bool:
        """Check if collector is enabled."""
        return self._enabled

    def get_status(self) -> dict:
        """Get collector status for health endpoint."""
        return {
            "name": self.name,
            "key": self.key,
            "interval": self.interval,
            "ttl": self.ttl,
            "enabled": self._enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_error": self.last_error,
            "run_count": self.run_count,
            "error_count": self.error_count,
        }
