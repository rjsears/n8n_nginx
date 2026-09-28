"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/system_monitors.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Producers for the system-notification events that come from sampling rather
than from an action: host resource thresholds, per-container resource
thresholds, container recovery, certificate expiry, and security events.

Each function takes already-sampled data (so it is testable without Docker
or psutil), reads the event's thresholds from the registry, and calls
``dispatch_notification``. Throttling (frequency, cooldown, quiet hours ...)
is the gate's job, not theirs.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select

logger = logging.getLogger(__name__)

# Fallbacks when an event row has no thresholds JSON (match the seed values).
DEFAULT_PERCENT_THRESHOLD = 90
DEFAULT_CPU_DURATION_MINUTES = 5
DEFAULT_CERT_DAYS = 14

# _collect_metrics samples every 5 minutes; a sustained-CPU window of N
# minutes therefore needs N / 5 consecutive samples over the threshold.
HOST_METRICS_INTERVAL_MINUTES = 5

# Events whose state row marks an open "problem" episode for a container.
CONTAINER_PROBLEM_EVENTS = ("container_unhealthy", "container_stopped")


async def _event(db, event_type: str):
    from api.models.system_notifications import SystemNotificationEvent

    result = await db.execute(
        select(SystemNotificationEvent).where(SystemNotificationEvent.event_type == event_type)
    )
    return result.scalar_one_or_none()


def _threshold(event, key: str, default):
    thresholds = getattr(event, "thresholds", None) or {}
    value = thresholds.get(key)
    return default if value is None else value


# --- host resources: disk_space_low, high_memory, high_cpu ---------------------------------

async def check_host_metrics(metrics: Dict[str, Dict[str, Any]], now: Optional[datetime] = None) -> List[str]:
    """
    Compare one host sample (the dict ``_collect_metrics`` builds:
    ``{"cpu": {"percent"}, "memory": {"percent"}, "disk": {"percent", "free"}}``)
    against the disk_space_low / high_memory / high_cpu thresholds.

    high_cpu is "sustained": every cached CPU sample within the event's
    ``duration_minutes`` must be over the threshold, and there must be enough
    samples to span that window. Returns the event types dispatched.
    """
    from api.database import async_session_maker
    from api.models.audit import SystemMetricsCache
    from api.services.notification_service import dispatch_notification

    now = now or datetime.now(UTC)
    fired: List[str] = []

    async with async_session_maker() as db:
        disk = await _event(db, "disk_space_low")
        disk_percent = (metrics.get("disk") or {}).get("percent")
        if disk and disk.enabled and disk_percent is not None:
            threshold = _threshold(disk, "percent", DEFAULT_PERCENT_THRESHOLD)
            if disk_percent >= threshold:
                await dispatch_notification("disk_space_low", {
                    "percent": disk_percent,
                    "threshold": threshold,
                    "path": "/",
                    "free_bytes": (metrics.get("disk") or {}).get("free"),
                })
                fired.append("disk_space_low")

        memory = await _event(db, "high_memory")
        memory_percent = (metrics.get("memory") or {}).get("percent")
        if memory and memory.enabled and memory_percent is not None:
            threshold = _threshold(memory, "percent", DEFAULT_PERCENT_THRESHOLD)
            if memory_percent >= threshold:
                await dispatch_notification("high_memory", {
                    "percent": memory_percent,
                    "threshold": threshold,
                })
                fired.append("high_memory")

        cpu = await _event(db, "high_cpu")
        cpu_percent = (metrics.get("cpu") or {}).get("percent")
        if cpu and cpu.enabled and cpu_percent is not None:
            threshold = _threshold(cpu, "percent", DEFAULT_PERCENT_THRESHOLD)
            duration = int(_threshold(cpu, "duration_minutes", DEFAULT_CPU_DURATION_MINUTES) or 0)
            if cpu_percent >= threshold:
                sustained = True
                needed = max(1, duration // HOST_METRICS_INTERVAL_MINUTES)
                if needed > 1:
                    # Earlier samples inside the window (the current one is not cached yet)
                    since = now - timedelta(minutes=duration)
                    result = await db.execute(
                        select(SystemMetricsCache)
                        .where(SystemMetricsCache.metric_type == "cpu", SystemMetricsCache.collected_at >= since)
                        .order_by(SystemMetricsCache.collected_at.desc())
                        .limit(needed - 1)
                    )
                    earlier = [row.metric_data.get("percent") for row in result.scalars().all()]
                    sustained = len(earlier) >= needed - 1 and all(
                        p is not None and p >= threshold for p in earlier
                    )
                if sustained:
                    await dispatch_notification("high_cpu", {
                        "percent": cpu_percent,
                        "threshold": threshold,
                        "duration_minutes": duration,
                    })
                    fired.append("high_cpu")

    return fired


# --- per-container resources: container_high_cpu, container_high_memory ---------------------

async def monitored_container_configs(db) -> list:
    """Container configs that ask for CPU or memory monitoring."""
    from api.models.system_notifications import SystemNotificationContainerConfig as Config

    result = await db.execute(
        select(Config).where(
            Config.enabled == True,  # noqa: E712
            (Config.monitor_high_cpu == True) | (Config.monitor_high_memory == True),  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def check_container_resources(stats: Iterable[Dict[str, Any]]) -> List[str]:
    """
    Compare per-container stats (``ContainerService.get_stats()`` rows:
    ``name``, ``cpu_percent``, ``memory_percent``) against each container's
    own thresholds from its SystemNotificationContainerConfig. Returns
    "<event>:<container>" for each dispatch.
    """
    from api.database import async_session_maker
    from api.services.notification_service import dispatch_notification

    fired: List[str] = []
    async with async_session_maker() as db:
        configs = {c.container_name: c for c in await monitored_container_configs(db)}
        if not configs:
            return fired
        cpu_event = await _event(db, "container_high_cpu")
        memory_event = await _event(db, "container_high_memory")

    for row in stats:
        config = configs.get(row.get("name"))
        if not config:
            continue
        name = config.container_name

        cpu_percent = row.get("cpu_percent")
        if config.monitor_high_cpu and cpu_event and cpu_event.enabled and cpu_percent is not None:
            threshold = config.cpu_threshold or DEFAULT_PERCENT_THRESHOLD
            if cpu_percent >= threshold:
                await dispatch_notification("container_high_cpu", {
                    "container": name, "percent": cpu_percent, "threshold": threshold,
                })
                fired.append(f"container_high_cpu:{name}")

        memory_percent = row.get("memory_percent")
        if config.monitor_high_memory and memory_event and memory_event.enabled and memory_percent is not None:
            threshold = config.memory_threshold or DEFAULT_PERCENT_THRESHOLD
            if memory_percent >= threshold:
                await dispatch_notification("container_high_memory", {
                    "container": name, "percent": memory_percent, "threshold": threshold,
                })
                fired.append(f"container_high_memory:{name}")

    return fired


# --- container recovery: container_healthy ----------------------------------------------------

async def check_container_recovery(health: Dict[str, Any]) -> List[str]:
    """
    A container that was announced unhealthy or stopped (it has a state row
    with last_sent_at for that event) and is now in ``health["healthy"]``
    has recovered. Dispatch ``container_healthy`` when the problem event's
    ``notify_on_recovery`` is on, then close the episode by clearing the
    problem state's last_sent_at so the next occurrence alerts immediately.
    """
    from api.database import async_session_maker
    from api.models.system_notifications import SystemNotificationState
    from api.services.notification_service import dispatch_notification

    healthy = set(health.get("healthy") or [])
    if not healthy:
        return []

    recovered: List[str] = []
    async with async_session_maker() as db:
        result = await db.execute(
            select(SystemNotificationState).where(
                SystemNotificationState.event_type.in_(CONTAINER_PROBLEM_EVENTS),
                SystemNotificationState.target_id.in_(healthy),
                SystemNotificationState.last_sent_at.is_not(None),
            )
        )
        open_episodes = list(result.scalars().all())
        if not open_episodes:
            return []

        notify_flags = {}
        for event_type in CONTAINER_PROBLEM_EVENTS:
            event = await _event(db, event_type)
            notify_flags[event_type] = bool(event and event.notify_on_recovery)

        announced = set()
        for state in open_episodes:
            name = state.target_id
            if notify_flags.get(state.event_type) and name not in announced:
                await dispatch_notification("container_healthy", {
                    "container": name,
                    "recovered_from": state.event_type.replace("container_", ""),
                })
                announced.add(name)
                recovered.append(name)
            state.last_sent_at = None
            state.updated_at = datetime.now(UTC)
        await db.commit()

    return recovered


# --- certificate expiry: certificate_expiring --------------------------------------------------

async def check_certificate_expiry(certificates: Iterable[Dict[str, Any]]) -> List[str]:
    """
    ``certificates`` is ``get_ssl_info()["certificates"]``. Dispatch
    ``certificate_expiring`` for each certificate whose days_until_expiry is
    at or under the event's ``days`` threshold (expired ones included; the
    message says EXPIRED). Returns the domains dispatched.
    """
    from api.database import async_session_maker
    from api.services.notification_service import dispatch_notification

    async with async_session_maker() as db:
        event = await _event(db, "certificate_expiring")
    if not event or not event.enabled:
        return []
    threshold_days = int(_threshold(event, "days", DEFAULT_CERT_DAYS))

    fired: List[str] = []
    for cert in certificates:
        days = cert.get("days_until_expiry")
        domain = cert.get("domain") or "unknown"
        if days is None or days > threshold_days:
            continue
        await dispatch_notification("certificate_expiring", {
            "target_id": domain,  # throttle per certificate, not globally
            "domain": domain,
            "days_until_expiry": days,
            "valid_until": cert.get("valid_until"),
            "threshold_days": threshold_days,
        })
        fired.append(domain)
    return fired


# --- security: security_event -----------------------------------------------------------------

async def report_security_event(kind: str, target_id: str, **details: Any) -> None:
    """
    Dispatch a ``security_event``. Never raises: a notification failure must
    not change the outcome of a login or an API call.
    """
    from api.services.notification_service import dispatch_notification

    try:
        await dispatch_notification("security_event", {"kind": kind, "target_id": target_id, **details})
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Failed to dispatch security_event '{kind}': {e}")
