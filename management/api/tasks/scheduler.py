"""
APScheduler setup and management.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
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

    # Convert async database URL to sync for SQLAlchemy job store
    sync_db_url = settings.database_url.replace("+asyncpg", "")

    jobstores = {
        "default": SQLAlchemyJobStore(url=sync_db_url, tablename="apscheduler_jobs")
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
        timezone="UTC",
    )

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

    # Host metrics collection (from metrics-agent) - run every minute
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

    logger.info("Maintenance jobs added")


async def _sync_backup_schedules() -> None:
    """Sync backup schedules from database to APScheduler."""
    from api.database import async_session_maker
    from api.models.backups import BackupSchedule
    from sqlalchemy import select

    async with async_session_maker() as db:
        result = await db.execute(
            select(BackupSchedule).where(BackupSchedule.enabled == True)
        )
        schedules = result.scalars().all()

        for schedule in schedules:
            await add_backup_job(schedule)

    logger.info(f"Synced {len(schedules)} backup schedules")


async def add_backup_job(schedule) -> None:
    """Add or update a backup job from schedule."""
    global scheduler

    if scheduler is None:
        return

    job_id = f"backup_{schedule.id}"

    # Build trigger based on frequency
    if schedule.frequency == "hourly":
        trigger = CronTrigger(minute=schedule.minute)
    elif schedule.frequency == "daily":
        trigger = CronTrigger(hour=schedule.hour, minute=schedule.minute)
    elif schedule.frequency == "weekly":
        trigger = CronTrigger(
            day_of_week=schedule.day_of_week,
            hour=schedule.hour,
            minute=schedule.minute,
        )
    elif schedule.frequency == "monthly":
        trigger = CronTrigger(
            day=schedule.day_of_month,
            hour=schedule.hour,
            minute=schedule.minute,
        )
    else:
        logger.warning(f"Unknown frequency: {schedule.frequency}")
        return

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
    from api.database import async_session_maker
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

        # Run backup
        service = BackupService(db)
        try:
            await service.run_backup(
                backup_type=schedule.backup_type,
                schedule_id=schedule_id,
                compression=schedule.compression,
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
                "container.unhealthy",
                {"container": container},
                severity="critical",
            )

        # Alert for stopped containers (that should be running)
        for container in health.get("stopped", []):
            # Skip optional containers
            if container not in ["n8n_cloudflared", "n8n_tailscale"]:
                await dispatch_notification(
                    "container.stopped",
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


async def _collect_host_metrics() -> None:
    """
    Collect metrics from the metrics-agent and store in HostMetricsSnapshot table.
    This runs every minute and provides instant data for the dashboard.
    """
    import httpx
    from api.database import async_session_maker
    from api.models.audit import HostMetricsSnapshot

    # Check if metrics agent is enabled
    if not settings.metrics_agent_enabled:
        return

    try:
        # Fetch metrics from the metrics-agent
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if settings.metrics_agent_api_key:
                headers["X-API-Key"] = settings.metrics_agent_api_key

            response = await client.get(
                f"{settings.metrics_agent_url}/metrics",
                headers=headers,
                params={"include_container_stats": True},
            )
            response.raise_for_status()
            data = response.json()

        # Extract and flatten metrics for database storage
        system = data.get("system", {})
        cpu = data.get("cpu", {})
        memory = data.get("memory", {})
        disks = data.get("disks", [])
        network = data.get("network", [])
        containers = data.get("containers", [])

        # Find primary disk (/)
        primary_disk = next((d for d in disks if d.get("mount_point") == "/"), disks[0] if disks else {})

        # Calculate network totals
        network_rx = sum(iface.get("bytes_recv", 0) for iface in network)
        network_tx = sum(iface.get("bytes_sent", 0) for iface in network)

        # Calculate container health summary
        containers_running = sum(1 for c in containers if c.get("status") == "running")
        containers_stopped = sum(1 for c in containers if c.get("status") != "running")
        containers_healthy = sum(1 for c in containers if c.get("health") == "healthy")
        containers_unhealthy = sum(1 for c in containers if c.get("health") == "unhealthy")

        # Create snapshot
        snapshot = HostMetricsSnapshot(
            # System info
            hostname=system.get("hostname"),
            platform=system.get("platform"),
            uptime_seconds=int(system.get("uptime_seconds", 0)),
            # CPU
            cpu_percent=cpu.get("percent"),
            cpu_core_count=cpu.get("core_count"),
            load_avg_1m=cpu.get("load_avg_1m"),
            load_avg_5m=cpu.get("load_avg_5m"),
            load_avg_15m=cpu.get("load_avg_15m"),
            # Memory
            memory_percent=memory.get("percent"),
            memory_used_bytes=memory.get("used_bytes"),
            memory_total_bytes=memory.get("total_bytes"),
            swap_percent=memory.get("swap_percent"),
            swap_used_bytes=memory.get("swap_used_bytes"),
            swap_total_bytes=memory.get("swap_total_bytes"),
            # Primary disk
            disk_percent=primary_disk.get("percent"),
            disk_used_bytes=primary_disk.get("used_bytes"),
            disk_total_bytes=primary_disk.get("total_bytes"),
            disk_free_bytes=primary_disk.get("free_bytes"),
            # Network
            network_rx_bytes=network_rx,
            network_tx_bytes=network_tx,
            # Containers
            containers_total=len(containers),
            containers_running=containers_running,
            containers_stopped=containers_stopped,
            containers_healthy=containers_healthy,
            containers_unhealthy=containers_unhealthy,
            # Additional disk details as JSON
            disks_detail=[{
                "mount_point": d.get("mount_point"),
                "percent": d.get("percent"),
                "total_bytes": d.get("total_bytes"),
                "used_bytes": d.get("used_bytes"),
                "free_bytes": d.get("free_bytes"),
            } for d in disks],
        )

        async with async_session_maker() as db:
            db.add(snapshot)
            await db.commit()

    except httpx.HTTPStatusError as e:
        logger.warning(f"Host metrics collection failed (HTTP {e.response.status_code}): {e}")
    except httpx.RequestError as e:
        logger.warning(f"Host metrics collection failed (connection error): {e}")
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
