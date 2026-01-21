"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/cache.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import httpx
import logging
from datetime import datetime, UTC
from typing import Any, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException

from api.config import settings
from api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def get_redis_client() -> Optional[redis.Redis]:
    """Get a Redis client connection."""
    if not settings.redis_enabled:
        return None

    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        # Test connection
        client.ping()
        return client
    except redis.ConnectionError as e:
        logger.warning(f"Failed to connect to Redis: {e}")
        return None


@router.get("/status")
async def get_cache_status(
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get comprehensive cache status including Redis connection,
    n8n_status collector health, and cached data.
    """
    result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "redis": {
            "enabled": settings.redis_enabled,
            "connected": False,
            "host": settings.redis_host,
            "port": settings.redis_port,
            "info": {},
            "error": None,
        },
        "collector": {
            "available": False,
            "healthy": False,
            "uptime_seconds": 0,
            "collectors": {},
            "scheduler": {},
            "error": None,
        },
        "cached_data": {
            "keys": [],
            "total_keys": 0,
            "categories": {},
        },
    }

    # Check Redis connection and get info
    client = get_redis_client()
    if client:
        result["redis"]["connected"] = True
        try:
            info = client.info()
            result["redis"]["info"] = {
                "version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak_human": info.get("used_memory_peak_human"),
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }

            # Calculate hit rate
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            if total > 0:
                result["redis"]["info"]["hit_rate_percent"] = round((hits / total) * 100, 2)
            else:
                result["redis"]["info"]["hit_rate_percent"] = 0

            # Get all keys and their TTLs
            keys = client.keys("*")
            result["cached_data"]["total_keys"] = len(keys)

            categories = {}
            key_details = []

            for key in keys[:100]:  # Limit to first 100 keys
                ttl = client.ttl(key)
                key_type = client.type(key)
                size = client.memory_usage(key) if hasattr(client, 'memory_usage') else None

                # Categorize by prefix
                category = key.split(":")[0] if ":" in key else "other"
                if category not in categories:
                    categories[category] = {"count": 0, "keys": []}
                categories[category]["count"] += 1
                categories[category]["keys"].append(key)

                # Get value preview for string types
                preview = None
                if key_type == "string":
                    try:
                        value = client.get(key)
                        if value:
                            # Try to parse as JSON for pretty preview
                            import json
                            try:
                                parsed = json.loads(value)
                                if isinstance(parsed, dict):
                                    # Show collected_at if available
                                    collected_at = parsed.get("collected_at")
                                    data_keys = list(parsed.get("data", {}).keys()) if isinstance(parsed.get("data"), dict) else []
                                    preview = {
                                        "collected_at": collected_at,
                                        "data_fields": data_keys[:5],  # First 5 fields
                                    }
                            except json.JSONDecodeError:
                                preview = value[:100] if len(value) > 100 else value
                    except Exception:
                        pass

                key_details.append({
                    "key": key,
                    "type": key_type,
                    "ttl": ttl if ttl >= 0 else None,  # -1 means no TTL, -2 means key doesn't exist
                    "size_bytes": size,
                    "category": category,
                    "preview": preview,
                })

            result["cached_data"]["keys"] = key_details
            result["cached_data"]["categories"] = {
                cat: {"count": data["count"]}
                for cat, data in categories.items()
            }

        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            result["redis"]["error"] = str(e)
    else:
        result["redis"]["error"] = "Unable to connect to Redis"

    # Check n8n_status collector health
    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            # n8n_status runs on host network at port 8080
            response = await http_client.get("http://127.0.0.1:8080/health")
            if response.status_code == 200:
                collector_data = response.json()
                result["collector"]["available"] = True
                result["collector"]["healthy"] = collector_data.get("status") == "healthy"
                result["collector"]["uptime_seconds"] = collector_data.get("uptime_seconds", 0)
                result["collector"]["collectors"] = collector_data.get("collectors", {})
                result["collector"]["scheduler"] = collector_data.get("scheduler", {})
                result["collector"]["redis_connected"] = collector_data.get("redis", {}).get("connected", False)
            else:
                result["collector"]["error"] = f"HTTP {response.status_code}"
    except httpx.ConnectError:
        result["collector"]["error"] = "n8n_status service not reachable"
    except Exception as e:
        result["collector"]["error"] = str(e)

    return result


@router.get("/keys")
async def get_cache_keys(
    pattern: str = "*",
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Get all cache keys matching a pattern."""
    client = get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Redis not available")

    try:
        keys = client.keys(pattern)
        return {
            "pattern": pattern,
            "count": len(keys),
            "keys": keys[:500],  # Limit to 500 keys
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/key/{key_name:path}")
async def get_cache_key(
    key_name: str,
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific cache key's value and metadata."""
    client = get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Redis not available")

    try:
        if not client.exists(key_name):
            raise HTTPException(status_code=404, detail="Key not found")

        key_type = client.type(key_name)
        ttl = client.ttl(key_name)

        value = None
        if key_type == "string":
            value = client.get(key_name)
            # Try to parse as JSON
            import json
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
        elif key_type == "list":
            value = client.lrange(key_name, 0, -1)
        elif key_type == "set":
            value = list(client.smembers(key_name))
        elif key_type == "hash":
            value = client.hgetall(key_name)
        elif key_type == "zset":
            value = client.zrange(key_name, 0, -1, withscores=True)

        return {
            "key": key_name,
            "type": key_type,
            "ttl": ttl if ttl >= 0 else None,
            "value": value,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/key/{key_name:path}")
async def delete_cache_key(
    key_name: str,
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a specific cache key."""
    client = get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Redis not available")

    try:
        deleted = client.delete(key_name)
        return {
            "key": key_name,
            "deleted": deleted > 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flush")
async def flush_cache(
    pattern: str = None,
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Flush cache keys.
    If pattern is provided, only delete matching keys.
    Otherwise, flush all keys (dangerous!).
    """
    client = get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Redis not available")

    try:
        if pattern:
            keys = client.keys(pattern)
            if keys:
                deleted = client.delete(*keys)
                return {
                    "pattern": pattern,
                    "deleted_count": deleted,
                }
            return {"pattern": pattern, "deleted_count": 0}
        else:
            # Flush all - requires confirmation
            client.flushdb()
            return {"flushed": True, "message": "All keys deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collector/metrics")
async def get_collector_metrics(
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Get current metrics from n8n_status collector via its /metrics endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            response = await http_client.get("http://127.0.0.1:8080/metrics")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to get collector metrics"
                )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="n8n_status collector not reachable"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
