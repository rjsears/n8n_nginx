# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /management/api/services/redis_cache_service.py
#
# Redis cache service for reading status data
# cached by the n8n_status collector service
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 2026
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import json
import logging
from datetime import datetime, UTC
from typing import Any, Optional

import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError

from api.config import settings

logger = logging.getLogger(__name__)


class RedisCacheService:
    """
    Async Redis client for reading cached status data.

    The n8n_status service writes system metrics to Redis.
    This service provides read-only access to that cached data.
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False
        self._last_error: Optional[str] = None

    async def connect(self) -> bool:
        """Establish async connection to Redis."""
        if not settings.redis_enabled:
            logger.info("Redis caching is disabled")
            return False

        try:
            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            await self._client.ping()
            self._connected = True
            self._last_error = None
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
            return True

        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self._connected = False
            self._last_error = str(e)
            return False

    async def is_connected(self) -> bool:
        """Check if connected to Redis."""
        if not settings.redis_enabled or not self._client:
            return False
        try:
            await self._client.ping()
            self._connected = True
            return True
        except (ConnectionError, TimeoutError, OSError):
            self._connected = False
            return False

    async def get_cached(self, key: str) -> Optional[dict]:
        """
        Get cached data from Redis.

        Args:
            key: Redis key (e.g., "system:network", "containers:stats")

        Returns:
            Dict with "data" and "collected_at" keys, or None if not found
        """
        if not settings.redis_enabled or not self._client:
            return None

        try:
            data = await self._client.get(key)
            if data:
                parsed = json.loads(data)
                # Add cache age
                if "collected_at" in parsed:
                    try:
                        collected = datetime.fromisoformat(parsed["collected_at"].replace("Z", "+00:00"))
                        age_seconds = (datetime.now(UTC) - collected).total_seconds()
                        parsed["age_seconds"] = round(age_seconds, 1)
                    except (ValueError, TypeError):
                        pass
                return parsed
            return None

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis connection error getting {key}: {e}")
            self._connected = False
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in Redis key {key}: {e}")
            return None

    async def get_cached_data(self, key: str) -> Optional[Any]:
        """
        Get just the data portion from cached entry.

        Args:
            key: Redis key

        Returns:
            The "data" field from cached entry, or None
        """
        cached = await self.get_cached(key)
        if cached and "data" in cached:
            return cached["data"]
        return None

    async def get_all_keys(self, pattern: str = "*") -> list[str]:
        """Get all keys matching a pattern."""
        if not settings.redis_enabled or not self._client:
            return []
        try:
            return await self._client.keys(pattern)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis error getting keys: {e}")
            return []

    async def get_info(self) -> dict:
        """Get Redis server info."""
        if not settings.redis_enabled or not self._client:
            return {"enabled": False}

        try:
            info = await self._client.info()
            return {
                "enabled": True,
                "connected": True,
                "version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
            }
        except (ConnectionError, TimeoutError) as e:
            return {
                "enabled": True,
                "connected": False,
                "error": str(e),
            }

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._connected = False


# Global service instance
_redis_cache: Optional[RedisCacheService] = None


async def get_redis_cache() -> RedisCacheService:
    """Get or create the Redis cache service instance."""
    global _redis_cache

    if _redis_cache is None:
        _redis_cache = RedisCacheService()
        await _redis_cache.connect()

    return _redis_cache


async def init_redis_cache():
    """Initialize Redis cache on startup."""
    global _redis_cache
    _redis_cache = RedisCacheService()
    connected = await _redis_cache.connect()
    if not connected and settings.redis_enabled:
        logger.warning("Redis cache not available - will fall back to direct collection")


async def close_redis_cache():
    """Close Redis cache on shutdown."""
    global _redis_cache
    if _redis_cache:
        await _redis_cache.close()
        _redis_cache = None
