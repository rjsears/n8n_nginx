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
thresholds, container recovery, certificate expiry, security events, and
the backup dead-man's switch (overdue scheduled backups, stuck 'running'
backups).

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


# --- backup dead-man's switch: backup_overdue, backup_stuck ----------------------------------

# Longest gap between two runs of a schedule, by frequency. Monthly allows
# for the longest month.
SCHEDULE_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=31),
}
DEFAULT_BACKUP_GRACE_MINUTES = 60
DEFAULT_BACKUP_STUCK_HOURS = 6

# A schedule row edited this long after its last run was changed by a person
# (enabled, retimed), not by the scheduler stamping last_run.
_SCHEDULE_EDIT_SLACK = timedelta(minutes=1)


def _schedule_baseline(schedule, last_success: Optional[datetime]) -> Optional[datetime]:
    """
    The moment from which the schedule's next success is owed: its last
    successful backup, but never earlier than when the schedule was created
    or last edited (re-enabling a schedule that was off for a month must not
    alert at once).
    """
    candidates = [t for t in (last_success, schedule.created_at) if t is not None]
    updated = schedule.updated_at
    if updated is not None and (schedule.last_run is None or updated - schedule.last_run > _SCHEDULE_EDIT_SLACK):
        candidates.append(updated)
    return max(candidates) if candidates else None


async def check_backup_freshness(now: Optional[datetime] = None) -> List[str]:
    """
    Dead-man's switch for scheduled backups.

    * ``backup_overdue``: an enabled schedule whose last success (or creation /
      last edit) is older than its interval plus ``grace_minutes``. Catches
      runs the scheduler missed or skipped (the job store is in memory, so a
      restart across the run time loses that run), a scheduler that stopped,
      and runs that keep failing before they can record a failure.
    * ``backup_stuck``: a backup_history row still 'running' after
      ``stuck_hours``. The row is marked failed (nothing else would ever
      finish it) and the event fires once for it.

    Returns "<event>:<target_id>" for each dispatch.
    """
    from sqlalchemy import func

    from api.database import async_session_maker
    from api.models.backups import BackupHistory, BackupSchedule
    from api.services.notification_service import dispatch_notification

    now = now or datetime.now(UTC)
    fired: List[str] = []
    overdue: List[Dict[str, Any]] = []
    stuck: List[Dict[str, Any]] = []

    async with async_session_maker() as db:
        overdue_event = await _event(db, "backup_overdue")
        stuck_event = await _event(db, "backup_stuck")

        # Stuck 'running' rows are always closed out, alert or not.
        stuck_hours = float(_threshold(stuck_event, "stuck_hours", DEFAULT_BACKUP_STUCK_HOURS))
        result = await db.execute(
            select(BackupHistory).where(
                BackupHistory.status == "running",
                BackupHistory.started_at < now - timedelta(hours=stuck_hours),
            )
        )
        for row in result.scalars().all():
            started = row.started_at
            row.status = "failed"
            row.completed_at = now
            row.duration_seconds = int((now - started).total_seconds()) if started else None
            row.error_message = (
                f"Marked failed by the backup monitor: still 'running' after {stuck_hours:g} hours "
                "(the management container restarted or the backup hung)."
            )
            stuck.append({
                "target_id": f"backup:{row.id}",
                "backup_id": row.id,
                "backup_type": row.backup_type,
                "schedule_id": row.schedule_id,
                "started_at": started.strftime("%Y-%m-%d %H:%M:%S") if started else None,
                "stuck_hours": stuck_hours,
            })
        if stuck:
            await db.commit()

        if overdue_event is not None and overdue_event.enabled:
            grace = timedelta(minutes=float(_threshold(overdue_event, "grace_minutes", DEFAULT_BACKUP_GRACE_MINUTES)))
            schedules = (
                await db.execute(select(BackupSchedule).where(BackupSchedule.enabled == True))  # noqa: E712
            ).scalars().all()
            for schedule in schedules:
                interval = SCHEDULE_INTERVALS.get(schedule.frequency)
                if interval is None:
                    continue
                last_success = (
                    await db.execute(
                        select(func.max(BackupHistory.completed_at)).where(
                            BackupHistory.schedule_id == schedule.id,
                            BackupHistory.status == "success",
                        )
                    )
                ).scalar_one_or_none()
                baseline = _schedule_baseline(schedule, last_success)
                if baseline is None or now <= baseline + interval + grace:
                    continue
                overdue.append({
                    "target_id": f"schedule:{schedule.id}",
                    "schedule_id": schedule.id,
                    "schedule_name": schedule.name,
                    "backup_type": schedule.backup_type,
                    "frequency": schedule.frequency,
                    "last_success": last_success.strftime("%Y-%m-%d %H:%M:%S") if last_success else None,
                    "hours_since": round((now - baseline).total_seconds() / 3600, 1),
                    "grace_minutes": int(grace.total_seconds() // 60),
                })

    for data in stuck:
        logger.error(f"Backup {data['backup_id']} was stuck in 'running'; marked failed")
        if stuck_event is not None and stuck_event.enabled:
            await dispatch_notification("backup_stuck", data)
            fired.append(f"backup_stuck:{data['target_id']}")
    for data in overdue:
        logger.warning(f"Scheduled backup '{data['schedule_name']}' is overdue ({data['hours_since']}h)")
        await dispatch_notification("backup_overdue", data)
        fired.append(f"backup_overdue:{data['target_id']}")
    return fired
