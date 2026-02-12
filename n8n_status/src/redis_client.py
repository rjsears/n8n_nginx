# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/src/redis_client.py
#
# Redis connection and operations
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import json
import logging
from datetime import datetime, UTC
from typing import Any, Optional

import redis

from .config import config

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with JSON serialization."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to Redis."""
        try:
            self._client = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {config.redis_host}:{config.redis_port}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        if not self._client:
            return False
        try:
            self._client.ping()
            self._connected = True
            return True
        except redis.ConnectionError:
            self._connected = False
            return False

    def set_json(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """
        Store JSON data in Redis.

        Args:
            key: Redis key
            data: Data to serialize as JSON
            ttl: Optional TTL in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            logger.warning("Redis client not initialized")
            return False

        try:
            # Wrap data with metadata
            payload = {
                "data": data,
                "collected_at": datetime.now(UTC).isoformat(),
                "key": key,
            }
            serialized = json.dumps(payload)

            if ttl:
                self._client.setex(key, ttl, serialized)
            else:
                self._client.set(key, serialized)

            logger.debug(f"Stored {key} ({len(serialized)} bytes)")
            return True

        except redis.RedisError as e:
            logger.error(f"Failed to store {key}: {e}")
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize {key}: {e}")
            return False

    def get_json(self, key: str) -> Optional[dict]:
        """
        Retrieve JSON data from Redis.

        Args:
            key: Redis key

        Returns:
            Deserialized data or None if not found
        """
        if not self._client:
            return None

        try:
            data = self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to retrieve {key}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize {key}: {e}")
            return None

    def get_all_keys(self, pattern: str = "*") -> list[str]:
        """Get all keys matching a pattern."""
        if not self._client:
            return []
        try:
            return self._client.keys(pattern)
        except redis.RedisError as e:
            logger.error(f"Failed to get keys: {e}")
            return []

    def get_info(self) -> dict:
        """Get Redis server info."""
        if not self._client:
            return {}
        try:
            info = self._client.info()
            return {
                "connected": True,
                "version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
            }
        except redis.RedisError as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {"connected": False, "error": str(e)}


# Global Redis client instance
redis_client = RedisClient()
