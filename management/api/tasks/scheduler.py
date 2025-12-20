"""
APScheduler setup and management.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, UTC
from typing import Optional
import logging

from api.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


async def init_scheduler() -> None:
    """Initialize and start the APScheduler."""
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return

    # Use MemoryJobStore - jobs are re-added on startup anyway
    # This avoids compatibility issues with SQLAlchemy async drivers
    jobstores = {
        "default": MemoryJobStore()
    }

    executors = {
        "default": AsyncIOExecutor()
    }

    job_defaults = {
        "coalesce": True,  # Combine missed runs into single execution
        "max_instances": 1,  # Only one instance of a job at a time
        "misfire_grace_time": 3600,  # 1 hour grace period for missed jobs
    }

    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=settings.timezone,
    )
    logger.info(f"Scheduler configured with timezone: {settings.timezone}")

    # Add built-in maintenance jobs
    await _add_maintenance_jobs()

    # Sync backup schedules from database
    await _sync_backup_schedules()

    scheduler.start()
    logger.info("Scheduler started")


async def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("Scheduler shutdown complete")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the scheduler instance."""
    return scheduler


async def _add_maintenance_jobs() -> None:
    """Add built-in maintenance jobs."""
    global scheduler

    # Session cleanup - run hourly
    scheduler.add_job(
        _cleanup_sessions,
        CronTrigger(minute=0),
        id="maintenance_session_cleanup",
        name="Session Cleanup",
        replace_existing=True,
    )

    # Metrics collection (container-local) - run every 5 minutes
    scheduler.add_job(
        _collect_metrics,
        CronTrigger(minute="*/5"),
        id="maintenance_metrics_collection",
        name="Metrics Collection",
        replace_existing=True,
    )

    # Host metrics collection (psutil + Docker API) - run every minute
    scheduler.add_job(
        _collect_host_metrics,
        CronTrigger(minute="*"),
        id="maintenance_host_metrics_collection",
        name="Host Metrics Collection",
        replace_existing=True,
    )

    # Host metrics cleanup - run daily at 4 AM
    scheduler.add_job(
        _cleanup_host_metrics,
        CronTrigger(hour=4, minute=0),
        id="maintenance_host_metrics_cleanup",
        name="Host Metrics Cleanup",
        replace_existing=True,
    )

    # Container health check - run every minute
    scheduler.add_job(
        _check_container_health,
        CronTrigger(minute="*"),
        id="maintenance_container_health",
        name="Container Health Check",
        replace_existing=True,
    )

    # Retention policy enforcement - run daily at 2 AM
    scheduler.add_job(
        _enforce_retention,
        CronTrigger(hour=2, minute=0),
        id="maintenance_retention_enforcement",
        name="Retention Policy Enforcement",
        replace_existing=True,
    )

    # Notification history cleanup - run daily at 3 AM
    scheduler.add_job(
        _cleanup_notification_history,
        CronTrigger(hour=3, minute=0),
        id="maintenance_notification_cleanup",
        name="Notification History Cleanup",
        replace_existing=True,
    )

    # Orphaned alpine container cleanup - run every 10 minutes
    scheduler.add_job(
        _cleanup_orphaned_alpine_containers,
        CronTrigger(minute="*/10"),
        id="maintenance_alpine_cleanup",
        name="Orphaned Alpine Container Cleanup",
        replace_existing=True,
    )

    logger.info("Maintenance jobs added")


async def schedule_l2_escalation(
    event_type: str,
    event_data: dict,
    event_id: int,
    target_id: str,
    timeout_minutes: int,
) -> None:
    """
    Schedule an L2 escalation notification to be sent after a timeout.

    Args:
        event_type: The notification event type
        event_data: The original event data
        event_id: The SystemNotificationEvent ID
        target_id: Target identifier (e.g., container name)
        timeout_minutes: Minutes to wait before escalating
    """
    from apscheduler.triggers.date import DateTrigger
    from datetime import timedelta

    if scheduler is None:
        logger.error("Cannot schedule L2 escalation - scheduler not initialized")
        return

    run_at = datetime.now(UTC) + timedelta(minutes=timeout_minutes)
    job_id = f"l2_escalation_{event_type}_{target_id}_{int(datetime.now(UTC).timestamp())}"

    scheduler.add_job(
        _send_l2_escalation,
        trigger=DateTrigger(run_date=run_at),
        id=job_id,
        name=f"L2 Escalation: {event_type}",
        kwargs={
            "event_type": event_type,
            "event_data": event_data,
            "event_id": event_id,
            "target_id": target_id,
        },
        replace_existing=False,
    )

    logger.info(f"Scheduled L2 escalation for '{event_type}' in {timeout_minutes} minutes (job: {job_id})")


async def _send_l2_escalation(
    event_type: str,
    event_data: dict,
    event_id: int,
    target_id: str,
) -> None:
    """
    Send L2 escalation notifications.
    Called by the scheduler after the escalation timeout.
    """
    from api.database import async_session_maker
    from api.models.system_notifications import (
        SystemNotificationEvent,
        SystemNotificationTarget,
        SystemNotificationState,
        SystemNotificationHistory,
    )
    from api.services.notification_service import NotificationService, _build_notification_message
    from sqlalchemy import select

    logger.info(f"Executing L2 escalation for '{event_type}' (target: {target_id})")

    async with async_session_maker() as db:
        # Check if escalation was already sent (e.g., by critical event trigger)
        state_result = await db.execute(
            select(SystemNotificationState).where(
                SystemNotificationState.event_type == event_type,
                SystemNotificationState.target_id == target_id
            )
        )
        state = state_result.scalar_one_or_none()

        if state and state.escalation_sent:
            logger.debug(f"L2 escalation already sent for '{event_type}', skipping")
            return

        # Get the event
        event_result = await db.execute(
            select(SystemNotificationEvent).where(SystemNotificationEvent.id == event_id)
        )
        event = event_result.scalar_one_or_none()

        if not event:
            logger.error(f"Event {event_id} not found for L2 escalation")
            return

        # Get L2 targets
        targets_result = await db.execute(
            select(SystemNotificationTarget).where(
                SystemNotificationTarget.event_id == event_id,
                SystemNotificationTarget.escalation_level == 2
            )
        )
        l2_targets = targets_result.scalars().all()

        if not l2_targets:
            logger.debug(f"No L2 targets for event {event_id}")
            return

        # Build notification
        title = f"[ESCALATED] {event.display_name}"
        message = _build_notification_message(event_type, event_data)

        notification_service = NotificationService(db)
        sent_count = 0
        channels_sent = []

        for target in l2_targets:
            try:
                if target.target_type == "channel" and target.channel_id:
                    result = await notification_service.send_to_service(
                        target.channel_id, title, message, "critical"
                    )
                    if result.get("success"):
                        sent_count += 1
                        channels_sent.append({"type": "channel", "id": target.channel_id, "level": 2})
                        logger.info(f"L2 escalation sent to channel {target.channel_id}")

                elif target.target_type == "group" and target.group_id:
                    result = await notification_service.send_to_group(
                        target.group_id, title, message, "critical"
                    )
                    if result.get("success"):
                        sent_count += result.get("sent_count", 1)
                        channels_sent.append({"type": "group", "id": target.group_id, "level": 2})
                        logger.info(f"L2 escalation sent to group {target.group_id}")

            except Exception as e:
                logger.error(f"Failed to send L2 escalation to target {target.id}: {e}")

        # Update state
        if state:
            state.escalation_sent = True
            state.escalation_triggered_at = datetime.now(UTC)
        else:
            state = SystemNotificationState(
                event_type=event_type,
                target_id=target_id,
                escalation_sent=True,
                escalation_triggered_at=datetime.now(UTC),
            )
            db.add(state)

        # Log to history
        now = datetime.now(UTC)
        history = SystemNotificationHistory(
            event_type=event_type,
            event_id=event_id,
            target_id=target_id,
            target_label=f"L2 Escalation: {event_data.get('container', event_type)}",
            severity="critical",
            event_data=event_data,
            channels_sent=channels_sent,
            escalation_level=2,
            status="sent" if sent_count > 0 else "failed",
            triggered_at=now,
            sent_at=now if sent_count > 0 else None,
        )
        db.add(history)

        await db.commit()
        logger.info(f"L2 escalation completed for '{event_type}' - sent to {sent_count} channel(s)")


async def _sync_backup_schedules() -> None:
    """Sync backup schedules from database to APScheduler."""
    from api.database import async_session_maker
    from api.models.backups import BackupSchedule, BackupConfiguration
    from sqlalchemy import select

    try:
        async with async_session_maker() as db:
            # First check if we have any schedules (including disabled ones to detect duplicates)
            all_result = await db.execute(select(BackupSchedule))
            all_schedules = all_result.scalars().all()

            # Warn if there are duplicate schedules with same frequency/time
            if len(all_schedules) > 1:
                # Group by frequency+hour+minute to find true duplicates
                schedule_keys = {}
                for s in all_schedules:
                    key = f"{s.frequency}_{s.hour}_{s.minute}"
                    if key not in schedule_keys:
                        schedule_keys[key] = []
                    schedule_keys[key].append(s)

                for key, dups in schedule_keys.items():
                    if len(dups) > 1 and all(d.enabled for d in dups):
                        logger.warning(
                            f"WARNING: Found {len(dups)} duplicate backup schedules with same timing ({key}). "
                            f"Schedule IDs: {[d.id for d in dups]}. This will cause multiple backups at the same time. "
                            f"Please disable or delete duplicate schedules via the UI or API."
                        )

            # Get only enabled schedules
            result = await db.execute(
                select(BackupSchedule).where(BackupSchedule.enabled == True)
            )
            schedules = result.scalars().all()

            # If no schedules, check BackupConfiguration and create one
            if not schedules:
                config_result = await db.execute(select(BackupConfiguration).limit(1))
                config = config_result.scalar_one_or_none()

                if config and config.schedule_enabled:
                    # Parse time from "HH:MM" format
                    hour, minute = 2, 0
                    if config.schedule_time:
                        try:
                            parts = config.schedule_time.split(':')
                            hour = int(parts[0])
                            minute = int(parts[1]) if len(parts) > 1 else 0
                        except (ValueError, IndexError):
                            pass

                    # Create default schedule from configuration
                    schedule = BackupSchedule(
                        name="Default Schedule",
                        backup_type=config.default_backup_type or "postgres_full",
                        enabled=True,
                        frequency=config.schedule_frequency or "daily",
                        hour=hour,
                        minute=minute,
                        day_of_week=config.schedule_day_of_week,
                        day_of_month=config.schedule_day_of_month,
                        compression=config.compression_algorithm or "gzip",
                        timezone=settings.timezone,
                    )
                    db.add(schedule)
                    await db.commit()
                    await db.refresh(schedule)
                    schedules = [schedule]
                    logger.info(f"Created default schedule from configuration: {config.schedule_frequency} at {hour}:{minute:02d}")

            for schedule in schedules:
                await add_backup_job(schedule)

            logger.info(f"Synced {len(schedules)} backup schedules")
    except Exception as e:
        logger.error(f"Failed to sync backup schedules: {e}")


async def add_backup_job(schedule) -> None:
    """Add or update a backup job from schedule."""
    global scheduler

    if scheduler is None:
        return

    job_id = f"backup_{schedule.id}"

    # Use schedule's timezone (default to system timezone if not set)
    schedule_tz = schedule.timezone or settings.timezone

    # Build trigger based on frequency
    if schedule.frequency == "hourly":
        trigger = CronTrigger(minute=schedule.minute, timezone=schedule_tz)
    elif schedule.frequency == "daily":
        trigger = CronTrigger(hour=schedule.hour, minute=schedule.minute, timezone=schedule_tz)
    elif schedule.frequency == "weekly":
        trigger = CronTrigger(
            day_of_week=schedule.day_of_week,
            hour=schedule.hour,
            minute=schedule.minute,
            timezone=schedule_tz,
        )
    elif schedule.frequency == "monthly":
        trigger = CronTrigger(
            day=schedule.day_of_month,
            hour=schedule.hour,
            minute=schedule.minute,
            timezone=schedule_tz,
        )
    else:
        logger.warning(f"Unknown frequency: {schedule.frequency}")
        return

    logger.info(f"Adding backup job {job_id}: {schedule.frequency} at {schedule.hour}:{schedule.minute:02d} ({schedule_tz})")

    scheduler.add_job(
        _run_scheduled_backup,
        trigger=trigger,
        args=[schedule.id],
        id=job_id,
        name=f"Backup: {schedule.name}",
        replace_existing=True,
    )

    # Update next run time in database
    job = scheduler.get_job(job_id)
    if job and job.next_run_time:
        from api.database import async_session_maker
        from api.models.backups import BackupSchedule
        from sqlalchemy import update

        async with async_session_maker() as db:
            await db.execute(
                update(BackupSchedule)
                .where(BackupSchedule.id == schedule.id)
                .values(
                    apscheduler_job_id=job_id,
                    next_run=job.next_run_time,
                )
            )
            await db.commit()


async def remove_backup_job(schedule_id: int) -> None:
    """Remove a backup job."""
    global scheduler

    if scheduler is None:
        return

    job_id = f"backup_{schedule_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed backup job: {job_id}")
    except Exception:
        pass  # Job may not exist


# Scheduled task implementations

async def _run_scheduled_backup(schedule_id: int) -> None:
    """Execute a scheduled backup."""
    from api.database import async_session_maker, n8n_session_maker
    from api.services.backup_service import BackupService
    from api.models.backups import BackupSchedule
    from sqlalchemy import select, update

    logger.info(f"Running scheduled backup {schedule_id}")

    async with async_session_maker() as db:
        # Get schedule
        result = await db.execute(
            select(BackupSchedule).where(BackupSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()

        if not schedule or not schedule.enabled:
            logger.warning(f"Schedule {schedule_id} not found or disabled")
            return

        # Run backup with metadata (same as manual backup)
        service = BackupService(db)
        try:
            # Get n8n database session for metadata capture
            async with n8n_session_maker() as n8n_db:
                await service.run_backup_with_metadata(
                    backup_type=schedule.backup_type,
                    schedule_id=schedule_id,
                    compression=schedule.compression,
                    n8n_db=n8n_db,
                )

            # Update last run
            await db.execute(
                update(BackupSchedule)
                .where(BackupSchedule.id == schedule_id)
                .values(last_run=datetime.now(UTC))
            )
            await db.commit()

        except Exception as e:
            logger.error(f"Scheduled backup {schedule_id} failed: {e}")


async def _cleanup_sessions() -> None:
    """Clean up expired sessions."""
    from api.database import async_session_maker
    from api.services.auth_service import AuthService

    async with async_session_maker() as db:
        service = AuthService(db)
        count = await service.cleanup_expired_sessions()
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")


async def _collect_metrics() -> None:
    """Collect and cache system metrics."""
    from api.database import async_session_maker
    from api.models.audit import SystemMetricsCache
    import psutil

    try:
        metrics = {
            "cpu": {
                "percent": psutil.cpu_percent(),
                "count": psutil.cpu_count(),
            },
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "available": psutil.virtual_memory().available,
            },
            "disk": {
                "percent": psutil.disk_usage("/").percent,
                "free": psutil.disk_usage("/").free,
            },
        }

        async with async_session_maker() as db:
            for metric_type, data in metrics.items():
                cache = SystemMetricsCache(
                    metric_type=metric_type,
                    metric_data=data,
                )
                db.add(cache)
            await db.commit()

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")


async def _check_container_health() -> None:
    """Check container health and send alerts if needed."""
    from api.services.container_service import ContainerService
    from api.services.notification_service import dispatch_notification

    try:
        service = ContainerService()
        health = await service.check_health()

        # Alert for unhealthy containers
        for container in health.get("unhealthy", []):
            await dispatch_notification(
                "container_unhealthy",
                {"container": container},
                severity="critical",
            )

        # Alert for stopped containers (that should be running)
        for container in health.get("stopped", []):
            # Skip optional containers
            if container not in ["n8n_cloudflared", "n8n_tailscale"]:
                await dispatch_notification(
                    "container_stopped",
                    {"container": container},
                    severity="warning",
                )

    except Exception as e:
        logger.error(f"Container health check failed: {e}")


async def _enforce_retention() -> None:
    """Enforce backup retention policies."""
    from api.database import async_session_maker
    from api.models.backups import BackupHistory, RetentionPolicy
    from sqlalchemy import select, delete
    from datetime import timedelta
    import os

    logger.info("Enforcing retention policies")

    async with async_session_maker() as db:
        # Get all retention policies
        result = await db.execute(select(RetentionPolicy))
        policies = result.scalars().all()

        for policy in policies:
            # Get backups of this type
            result = await db.execute(
                select(BackupHistory)
                .where(BackupHistory.backup_type == policy.backup_type)
                .where(BackupHistory.deleted_at.is_(None))
                .where(BackupHistory.status == "success")
                .order_by(BackupHistory.created_at.desc())
            )
            backups = list(result.scalars().all())

            # Categorize and mark for deletion
            now = datetime.now(UTC)
            to_delete = []

            for backup in backups:
                age = now - backup.created_at

                # Determine retention category
                if age < timedelta(hours=24):
                    if len([b for b in backups if (now - b.created_at) < timedelta(hours=24)]) > policy.keep_hourly:
                        to_delete.append(backup)
                elif age < timedelta(days=7):
                    if len([b for b in backups if timedelta(hours=24) <= (now - b.created_at) < timedelta(days=7)]) > policy.keep_daily:
                        to_delete.append(backup)
                elif age < timedelta(days=30):
                    if len([b for b in backups if timedelta(days=7) <= (now - b.created_at) < timedelta(days=30)]) > policy.keep_weekly:
                        to_delete.append(backup)
                else:
                    if len([b for b in backups if (now - b.created_at) >= timedelta(days=30)]) > policy.keep_monthly:
                        to_delete.append(backup)

            # Delete old backups
            for backup in to_delete:
                try:
                    if os.path.exists(backup.filepath):
                        os.remove(backup.filepath)
                    backup.deleted_at = now
                    backup.deleted_by = "retention_policy"
                    logger.info(f"Deleted backup: {backup.filename}")
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup.filename}: {e}")

            await db.commit()


async def _cleanup_notification_history() -> None:
    """Clean up old notification history (older than 30 days)."""
    from api.database import async_session_maker
    from api.models.notifications import NotificationHistory
    from sqlalchemy import delete
    from datetime import timedelta

    async with async_session_maker() as db:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        result = await db.execute(
            delete(NotificationHistory).where(NotificationHistory.created_at < cutoff)
        )
        await db.commit()

        if result.rowcount > 0:
            logger.info(f"Cleaned up {result.rowcount} old notification records")


def _run_alpine_container(docker_client, command: list, **kwargs) -> bytes:
    """
    Run an alpine container with guaranteed cleanup.

    Uses detach mode with manual cleanup to ensure containers don't get orphaned
    even if remove=True fails due to exceptions or timeouts.
    """
    container = None
    try:
        # Don't use remove=True - we'll handle cleanup manually
        kwargs.pop("remove", None)

        container = docker_client.containers.run(
            "alpine:latest",
            command=command,
            detach=True,
            **kwargs
        )

        # Wait for container to complete (timeout after 30 seconds)
        result = container.wait(timeout=30)

        # Get logs before removing
        output = container.logs(stdout=True, stderr=False)

        return output

    except Exception as e:
        logger.debug(f"Alpine container error: {e}")
        raise

    finally:
        # Always try to clean up the container
        if container:
            try:
                container.remove(force=True)
            except Exception as cleanup_err:
                logger.debug(f"Failed to remove container {container.short_id}: {cleanup_err}")


async def _cleanup_orphaned_alpine_containers() -> None:
    """
    Clean up any orphaned alpine containers that weren't properly removed.
    This runs periodically to catch any containers that slipped through.
    """
    import docker

    try:
        client = docker.from_env()

        # Find exited alpine containers
        containers = client.containers.list(
            all=True,
            filters={
                "status": "exited",
                "ancestor": "alpine:latest"
            }
        )

        removed_count = 0
        for container in containers:
            try:
                # Check if it's been exited for more than 5 minutes
                # to avoid removing containers that are just finishing up
                attrs = container.attrs
                finished_at = attrs.get("State", {}).get("FinishedAt", "")
                if finished_at and "0001-01-01" not in finished_at:
                    from datetime import datetime, timezone
                    import re
                    # Parse Docker timestamp (e.g., "2024-01-15T10:30:00.123456789Z")
                    # Truncate nanoseconds to microseconds
                    finished_at_clean = re.sub(r'\.(\d{6})\d*Z', r'.\1Z', finished_at)
                    try:
                        finished_time = datetime.fromisoformat(finished_at_clean.replace("Z", "+00:00"))
                        age_seconds = (datetime.now(timezone.utc) - finished_time).total_seconds()

                        if age_seconds > 300:  # 5 minutes
                            container.remove(force=True)
                            removed_count += 1
                            logger.debug(f"Cleaned up orphaned alpine container: {container.short_id}")
                    except ValueError:
                        # If we can't parse the timestamp, remove it anyway if it's exited
                        container.remove(force=True)
                        removed_count += 1
            except Exception as e:
                logger.debug(f"Failed to clean up container {container.short_id}: {e}")

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} orphaned alpine container(s)")

    except Exception as e:
        logger.debug(f"Error during alpine container cleanup: {e}")


async def _collect_host_metrics() -> None:
    """
    Collect system metrics directly using psutil and Docker API.
    This runs every minute and provides instant data for the dashboard.
    Stores snapshots in PostgreSQL for historical charting.
    """
    import psutil
    import platform
    import socket
    import docker
    from api.database import async_session_maker
    from api.models.audit import HostMetricsSnapshot

    try:
        # ========================================
        # System Info
        # ========================================
        hostname = socket.gethostname()
        platform_name = platform.system().lower()

        # Get Docker HOST uptime (the LXC/VM running Docker, not the Proxmox hypervisor)
        # In LXC, /proc/uptime shows the Proxmox host uptime since LXC shares the kernel.
        # To get LXC container uptime, we calculate from PID 1's actual start time.
        uptime_seconds = 0
        docker_client = docker.from_env()

        try:
            # Method 1: Calculate PID 1 start time from /proc/1/stat and /proc/stat
            # This works in LXC because it measures when the LXC's init process started
            result = _run_alpine_container(
                docker_client,
                command=["sh", "-c", """
                    # Get boot time (btime) from /proc/stat
                    btime=$(grep -m1 '^btime ' /proc/stat | awk '{print $2}')
                    # Get PID 1 start time (field 22) from /proc/1/stat - in clock ticks since boot
                    starttime=$(cat /proc/1/stat | awk '{print $22}')
                    # Get clock ticks per second
                    clk_tck=$(getconf CLK_TCK)
                    # Calculate PID 1 start time as epoch seconds
                    echo $(( btime + starttime / clk_tck ))
                """],
                pid_mode="host",
            )
            pid1_start_epoch = int(result.decode("utf-8").strip())
            import time
            uptime_seconds = int(time.time() - pid1_start_epoch)
        except Exception as e:
            logger.debug(f"Could not calculate host PID 1 start time: {e}")

        # Fallback: try to get uptime from systemd if available
        if uptime_seconds <= 0 or uptime_seconds > 86400 * 365:  # Sanity check: > 1 year is suspicious
            try:
                result = _run_alpine_container(
                    docker_client,
                    command=["cat", "/proc/1/stat"],
                    pid_mode="host",
                )
                # Parse field 22 (starttime) - if we can at least get relative time
                stat_parts = result.decode("utf-8").strip().split()
                if len(stat_parts) >= 22:
                    # Field 22 is start time in jiffies since boot
                    # We can approximate using current /proc/uptime minus relative start
                    with open('/proc/uptime', 'r') as f:
                        kernel_uptime = float(f.read().split()[0])
                    start_jiffies = int(stat_parts[21])  # 0-indexed, so field 22 is index 21
                    # Assume 100 Hz (common value)
                    pid1_relative_start = start_jiffies / 100.0
                    uptime_seconds = int(kernel_uptime - pid1_relative_start)
            except Exception as e:
                logger.debug(f"Fallback PID 1 calculation failed: {e}")

        # Final fallback (will show Proxmox uptime in LXC - not ideal but better than 0)
        if uptime_seconds <= 0:
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = int(float(f.read().split()[0]))
            except Exception:
                uptime_seconds = 0

        # ========================================
        # CPU Metrics
        # ========================================
        cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking
        cpu_core_count = psutil.cpu_count() or 1
        try:
            load_avg = psutil.getloadavg()
            load_avg_1m, load_avg_5m, load_avg_15m = load_avg
        except (AttributeError, OSError):
            load_avg_1m = load_avg_5m = load_avg_15m = 0.0

        # ========================================
        # Memory Metrics
        # ========================================
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # ========================================
        # Disk Metrics
        # ========================================
        excluded_mounts = {'/tmp', '/var/tmp', '/dev', '/dev/shm', '/run', '/sys', '/proc'}
        excluded_fs_types = {'tmpfs', 'devtmpfs', 'sysfs', 'proc', 'devpts', 'cgroup', 'cgroup2', 'overlay', 'squashfs'}

        real_disks = []
        try:
            partitions = psutil.disk_partitions(all=False)
            for partition in partitions:
                # Skip virtual filesystems
                if partition.mountpoint in excluded_mounts:
                    continue
                if partition.fstype in excluded_fs_types:
                    continue
                if partition.mountpoint.startswith('/snap'):
                    continue
                if partition.mountpoint.startswith('/boot/efi'):
                    continue

                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    real_disks.append({
                        "mount_point": partition.mountpoint,
                        "percent": usage.percent,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                    })
                except PermissionError:
                    pass
        except Exception as e:
            logger.debug(f"Error getting disk partitions: {e}")

        # Find primary disk (/)
        primary_disk = next((d for d in real_disks if d.get("mount_point") == "/"), real_disks[0] if real_disks else {})

        # ========================================
        # Network Metrics (Docker HOST network, not container)
        # ========================================
        network_rx = 0
        network_tx = 0
        try:
            # Get host network stats by running alpine with host network namespace
            # This gives us the actual Docker host's network I/O, not the container's
            result = _run_alpine_container(
                docker_client,
                command=["cat", "/proc/net/dev"],
                network_mode="host",
            )
            net_dev = result.decode("utf-8")
            # Parse /proc/net/dev - format:
            # Inter-|   Receive                                                |  Transmit
            # face |bytes    packets errs drop fifo frame compressed multicast|bytes ...
            #  eth0: 123456  789 0 0 0 0 0 0   654321 ...
            for line in net_dev.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("lo:"):
                    # Skip loopback, docker0, veth interfaces
                    iface = line.split(":")[0].strip()
                    if iface.startswith("veth") or iface.startswith("docker") or iface.startswith("br-"):
                        continue
                    parts = line.split(":")[1].split()
                    if len(parts) >= 9:
                        network_rx += int(parts[0])  # bytes received
                        network_tx += int(parts[8])  # bytes transmitted
        except Exception as e:
            logger.debug(f"Could not get host network stats: {e}")
            # Fallback to container's own network stats
            try:
                net_io = psutil.net_io_counters()
                network_rx = net_io.bytes_recv
                network_tx = net_io.bytes_sent
            except Exception:
                pass

        # ========================================
        # Container Metrics (via Docker API)
        # Count ALL containers on the system
        # ========================================
        containers_total = 0
        containers_running = 0
        containers_stopped = 0
        containers_healthy = 0
        containers_unhealthy = 0

        try:
            docker_client = docker.from_env()
            all_containers = docker_client.containers.list(all=True)
            containers_total = len(all_containers)

            for container in all_containers:
                if container.status == "running":
                    containers_running += 1
                    # Check health status
                    health = container.attrs.get("State", {}).get("Health", {})
                    health_status = health.get("Status", "none")
                    if health_status == "healthy":
                        containers_healthy += 1
                    elif health_status == "unhealthy":
                        containers_unhealthy += 1
                else:
                    containers_stopped += 1
        except Exception as e:
            logger.debug(f"Error getting container stats: {e}")

        # ========================================
        # Create and Store Snapshot
        # ========================================
        snapshot = HostMetricsSnapshot(
            # System info
            hostname=hostname,
            platform=platform_name,
            uptime_seconds=uptime_seconds,
            # CPU
            cpu_percent=cpu_percent,
            cpu_core_count=cpu_core_count,
            load_avg_1m=load_avg_1m,
            load_avg_5m=load_avg_5m,
            load_avg_15m=load_avg_15m,
            # Memory
            memory_percent=mem.percent,
            memory_used_bytes=mem.used,
            memory_total_bytes=mem.total,
            swap_percent=swap.percent,
            swap_used_bytes=swap.used,
            swap_total_bytes=swap.total,
            # Primary disk
            disk_percent=primary_disk.get("percent"),
            disk_used_bytes=primary_disk.get("used_bytes"),
            disk_total_bytes=primary_disk.get("total_bytes"),
            disk_free_bytes=primary_disk.get("free_bytes"),
            # Network
            network_rx_bytes=network_rx,
            network_tx_bytes=network_tx,
            # Containers
            containers_total=containers_total,
            containers_running=containers_running,
            containers_stopped=containers_stopped,
            containers_healthy=containers_healthy,
            containers_unhealthy=containers_unhealthy,
            # Additional disk details as JSON
            disks_detail=real_disks,
        )

        async with async_session_maker() as db:
            db.add(snapshot)
            await db.commit()

    except Exception as e:
        logger.error(f"Host metrics collection failed: {e}")


async def _cleanup_host_metrics() -> None:
    """
    Clean up old host metrics snapshots.
    Default retention: 24 hours (1440 records at 1/minute collection rate).
    """
    from api.database import async_session_maker
    from api.models.audit import HostMetricsSnapshot
    from sqlalchemy import delete
    from datetime import timedelta

    # Keep 24 hours of data by default
    retention_hours = getattr(settings, "host_metrics_retention_hours", 24)

    async with async_session_maker() as db:
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
        result = await db.execute(
            delete(HostMetricsSnapshot).where(HostMetricsSnapshot.collected_at < cutoff)
        )
        await db.commit()

        if result.rowcount > 0:
            logger.info(f"Cleaned up {result.rowcount} old host metrics records")
