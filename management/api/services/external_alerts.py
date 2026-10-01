"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/external_alerts.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Alerting that does not depend on the management database.

Every configured notification channel lives in PostgreSQL, so the outages
most worth hearing about (Postgres down, this container down, the host
down) are exactly the ones the normal path cannot report. Two
database-free mechanisms cover them:

* **Heartbeat** (``HEARTBEAT_URL``): while the stack is healthy (management
  database reachable, n8n answering its health check) the scheduler GETs
  this URL every ``HEARTBEAT_INTERVAL_MINUTES`` (default 5). Point it at a
  healthchecks.io check or an Uptime Kuma "push" monitor; the external
  service alerts when the pings stop, whatever the reason: Postgres, n8n,
  this container, Docker or the whole host.
* **Fallback alert** (``ALERT_FALLBACK_URL``): when a notification cannot be
  dispatched because the database is unreachable, a plain-text POST goes
  here instead. An ntfy topic URL (``https://ntfy.sh/my-topic``) works as is;
  any endpoint that accepts a text POST will do. ``scripts/health_check.sh
  --alert`` posts to the same URL from the host, so it also covers this
  container being down.

Both settings are read from the process environment first, then from the
project's ``.env`` (mounted at /app/host_project), at the moment they are
used: adding them to ``.env`` needs no restart.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HOST_ENV_FILE = "/app/host_project/.env"

HEARTBEAT_URL_KEY = "HEARTBEAT_URL"
HEARTBEAT_INTERVAL_KEY = "HEARTBEAT_INTERVAL_MINUTES"
FALLBACK_URL_KEY = "ALERT_FALLBACK_URL"

DEFAULT_HEARTBEAT_INTERVAL_MINUTES = 5
HTTP_TIMEOUT_SECONDS = 10.0

# The same failure (event + target) reaches the fallback at most this often.
FALLBACK_REPEAT_SECONDS = 15 * 60
_fallback_last_sent: Dict[str, float] = {}

_PRIORITY_NUMBER = {"low": "2", "normal": "3", "high": "4", "critical": "5"}


def read_setting(key: str, env_file: Optional[str] = None) -> Optional[str]:
    """A setting from the environment, else from the project's .env; None when unset or empty."""
    value = os.environ.get(key)
    if not value:
        try:
            from api.services.env_file import read_env_value

            value = read_env_value(env_file or HOST_ENV_FILE, key)
        except Exception as e:  # unreadable .env must not break the caller
            logger.debug(f"Could not read {key} from .env: {e}")
            value = None
    value = (value or "").strip()
    return value or None


def heartbeat_interval_minutes() -> int:
    raw = read_setting(HEARTBEAT_INTERVAL_KEY)
    try:
        minutes = int(raw) if raw else DEFAULT_HEARTBEAT_INTERVAL_MINUTES
    except ValueError:
        logger.warning(f"Ignoring invalid {HEARTBEAT_INTERVAL_KEY}={raw!r}")
        minutes = DEFAULT_HEARTBEAT_INTERVAL_MINUTES
    return max(1, minutes)


def _host_label() -> str:
    from api.config import settings

    return getattr(settings, "domain", None) or os.environ.get("HOSTNAME") or "n8n host"


async def send_fallback_alert(
    title: str,
    message: str,
    priority: str = "critical",
    dedup_key: Optional[str] = None,
) -> bool:
    """
    POST a plain-text alert to ALERT_FALLBACK_URL. Never raises. Returns True
    when the endpoint accepted it. Repeats of one ``dedup_key`` within
    FALLBACK_REPEAT_SECONDS are dropped so an outage does not flood.
    """
    url = read_setting(FALLBACK_URL_KEY)
    if not url:
        return False

    key = dedup_key or title
    now = time.monotonic()
    last = _fallback_last_sent.get(key)
    if last is not None and now - last < FALLBACK_REPEAT_SECONDS:
        return False

    try:
        import httpx

        headers = {
            # ntfy reads these; other endpoints ignore them
            "Title": title.encode("ascii", "replace").decode("ascii"),
            "Priority": _PRIORITY_NUMBER.get(priority, "5"),
            "Tags": "rotating_light",
            "Content-Type": "text/plain; charset=utf-8",
        }
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(url, content=message.encode("utf-8"), headers=headers)
        if 200 <= response.status_code < 300:
            _fallback_last_sent[key] = now
            logger.warning(f"Fallback alert sent to {FALLBACK_URL_KEY}: {title}")
            return True
        logger.error(f"Fallback alert rejected: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Fallback alert could not be sent: {e}")
    return False


async def notify_dispatch_failure(event_type: str, event_data: Dict[str, Any], error: BaseException) -> bool:
    """Route a notification that could not be dispatched to the fallback URL."""
    try:
        from api.services.notification_service import _build_notification_message

        body = _build_notification_message(event_type, event_data)
    except Exception:
        body = f"Event: {event_type}\n{event_data}"
    message = (
        f"{body}\n\n"
        f"This alert could not go through the configured notification channels: {error}"
    )
    target = event_data.get("container") or event_data.get("target_id") or "global"
    return await send_fallback_alert(
        f"[{_host_label()}] {event_type.replace('_', ' ')} (fallback)",
        message,
        "critical",
        dedup_key=f"{event_type}:{target}",
    )


async def stack_health() -> Dict[str, Any]:
    """
    What the heartbeat vouches for: the management database answers a query
    and n8n's /healthz answers 2xx/3xx. Returns {"healthy": bool, "checks": {...}}.
    """
    import httpx
    from sqlalchemy import text

    from api.config import settings
    from api.database import async_session_maker

    checks: Dict[str, str] = {}

    try:
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    n8n_base = settings.n8n_api_url.split("/api/")[0].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{n8n_base}/healthz")
        checks["n8n"] = "ok" if response.status_code < 400 else f"HTTP {response.status_code}"
    except Exception as e:
        checks["n8n"] = f"error: {e}"

    return {"healthy": all(v == "ok" for v in checks.values()), "checks": checks}


_last_heartbeat: Optional[float] = None


async def send_heartbeat(force: bool = False) -> Optional[bool]:
    """
    Ping HEARTBEAT_URL when the stack is healthy. Returns None when no URL is
    configured or the interval has not elapsed, False when unhealthy or the
    ping failed (so the external monitor sees silence), True when pinged.
    The scheduler calls this every minute; the interval is enforced here so
    a change to HEARTBEAT_INTERVAL_MINUTES needs no restart.
    """
    global _last_heartbeat

    url = read_setting(HEARTBEAT_URL_KEY)
    if not url:
        return None
    now = time.monotonic()
    if not force and _last_heartbeat is not None and now - _last_heartbeat < heartbeat_interval_minutes() * 60 - 5:
        return None
    _last_heartbeat = now

    health = await stack_health()
    if not health["healthy"]:
        logger.error(f"Heartbeat withheld, stack unhealthy: {health['checks']}")
        return False

    try:
        import httpx

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
        if response.status_code < 400:
            logger.debug(f"Heartbeat sent at {datetime.now(UTC).isoformat()}")
            return True
        logger.error(f"Heartbeat ping rejected: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Heartbeat ping failed: {e}")
    return False
