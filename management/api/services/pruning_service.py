"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/pruning_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import os
import shutil
import logging
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_

from api.models.backups import BackupHistory, BackupPruningSettings, BackupConfiguration
from api.services.notification_service import dispatch_notification
from api.services.operation_lock import exclusive_operation, OperationBusyError
from api.services.retention import RetentionConfig, select_gfs_retention
from api.config import settings

# deletion_reason prefix for deletions scheduled by GFS retention. Used to
# cancel a pending GFS deletion if a later run decides to keep the backup.
GFS_DELETION_REASON = "gfs_retention"

logger = logging.getLogger(__name__)


class PruningService:
    """Service for automatic backup pruning and retention management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.backup_dir = os.environ.get("BACKUP_DIR", "/app/backups")
        self.nfs_backup_dir = os.environ.get("NFS_BACKUP_DIR", "/mnt/backups")

    # ============================================================================
    # Settings Management
    # ============================================================================

    async def get_settings(self) -> Optional[BackupPruningSettings]:
        """Get the current pruning settings (singleton)."""
        stmt = select(BackupPruningSettings).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_settings(self) -> BackupPruningSettings:
        """Get or create the pruning settings."""
        settings = await self.get_settings()
        if not settings:
            settings = BackupPruningSettings()
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)
        return settings

    async def update_settings(self, **updates) -> BackupPruningSettings:
        """Update pruning settings."""
        settings = await self.get_or_create_settings()

        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    # ============================================================================
    # Storage Analysis
    # ============================================================================

    def get_storage_usage(self) -> Dict[str, Any]:
        """
        Get current storage usage for backup directories.
        Returns info about local and NFS backup storage.
        """
        result = {
            "local": self._get_dir_storage_info(self.backup_dir),
            "nfs": self._get_dir_storage_info(self.nfs_backup_dir),
            "total_backup_size_bytes": 0,
            "backup_count": 0,
        }

        # Calculate total backup size
        for dir_path in [self.backup_dir, self.nfs_backup_dir]:
            if os.path.exists(dir_path):
                for f in os.listdir(dir_path):
                    filepath = os.path.join(dir_path, f)
                    if os.path.isfile(filepath) and f.endswith('.tar.gz'):
                        result["total_backup_size_bytes"] += os.path.getsize(filepath)
                        result["backup_count"] += 1

        result["total_backup_size_gb"] = round(result["total_backup_size_bytes"] / (1024**3), 2)

        return result

    def _get_dir_storage_info(self, dir_path: str) -> Dict[str, Any]:
        """Get storage information for a directory."""
        if not os.path.exists(dir_path):
            return {
                "exists": False,
                "path": dir_path,
            }

        try:
            stat = os.statvfs(dir_path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            used = total - free

            return {
                "exists": True,
                "path": dir_path,
                "total_bytes": total,
                "free_bytes": free,
                "used_bytes": used,
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_percent": round((free / total) * 100, 1) if total > 0 else 0,
                "used_percent": round((used / total) * 100, 1) if total > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error getting storage info for {dir_path}: {e}")
            return {
                "exists": True,
                "path": dir_path,
                "error": str(e),
            }

    async def get_total_backup_size(self) -> int:
        """Get total size of all backups in bytes."""
        stmt = select(func.sum(BackupHistory.file_size)).where(
            BackupHistory.status == "success",
            BackupHistory.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        total = result.scalar()
        return total or 0

    # ============================================================================
    # Candidate Selection
    # ============================================================================

    async def get_time_based_candidates(self, max_age_days: int) -> List[BackupHistory]:
        """
        Get backups older than the specified age that are candidates for deletion.
        Excludes protected backups.
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        stmt = select(BackupHistory).where(
            and_(
                BackupHistory.status == "success",
                BackupHistory.deleted_at.is_(None),
                BackupHistory.created_at < cutoff_date,
                or_(
                    BackupHistory.is_protected == False,
                    BackupHistory.is_protected.is_(None)
                )
            )
        ).order_by(BackupHistory.created_at.asc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_oldest_unprotected_backups(self, limit: int = 10) -> List[BackupHistory]:
        """
        Get the oldest unprotected backups (candidates for space-based pruning).
        """
        stmt = select(BackupHistory).where(
            and_(
                BackupHistory.status == "success",
                BackupHistory.deleted_at.is_(None),
                or_(
                    BackupHistory.is_protected == False,
                    BackupHistory.is_protected.is_(None)
                ),
                or_(
                    BackupHistory.deletion_status.is_(None),
                    BackupHistory.deletion_status != "pending"
                )
            )
        ).order_by(BackupHistory.created_at.asc()).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_deletions(self) -> List[BackupHistory]:
        """Get backups that are pending deletion."""
        stmt = select(BackupHistory).where(
            BackupHistory.deletion_status == "pending"
        ).order_by(BackupHistory.scheduled_deletion_at.asc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================================
    # Deletion Operations
    # ============================================================================

    async def mark_for_deletion(
        self,
        backup: BackupHistory,
        hours_until_deletion: int = 24,
        reason: str = "automatic_pruning"
    ) -> BackupHistory:
        """
        Mark a backup for pending deletion.
        Sets the scheduled deletion time and status.
        """
        backup.deletion_status = "pending"
        backup.scheduled_deletion_at = datetime.now(UTC) + timedelta(hours=hours_until_deletion)
        backup.deletion_reason = reason

        await self.db.commit()
        await self.db.refresh(backup)

        logger.info(
            f"Backup {backup.id} marked for deletion at {backup.scheduled_deletion_at}"
        )

        return backup

    async def cancel_deletion(self, backup_id: int) -> Optional[BackupHistory]:
        """Cancel a pending deletion."""
        stmt = select(BackupHistory).where(BackupHistory.id == backup_id)
        result = await self.db.execute(stmt)
        backup = result.scalar_one_or_none()

        if backup and backup.deletion_status == "pending":
            backup.deletion_status = None
            backup.scheduled_deletion_at = None
            backup.deletion_reason = None

            await self.db.commit()
            await self.db.refresh(backup)

            logger.info(f"Cancelled deletion for backup {backup_id}")
            return backup

        return None

    async def execute_deletion(self, backup: BackupHistory, deleted_by: str = "pruning") -> bool:
        """
        Actually delete a backup file and update the database record.
        A file that is already missing is treated as deleted.
        Returns True if successful.
        """
        try:
            # Delete the file
            if backup.filepath and os.path.exists(backup.filepath):
                os.remove(backup.filepath)
                logger.info(f"Deleted backup file: {backup.filepath}")
            elif backup.filepath:
                logger.warning(f"Backup file already missing, marking record deleted: {backup.filepath}")

            # Update status. deleted_at is what the history views filter on,
            # so it must be set for the record to disappear from the UI.
            backup.deletion_status = "deleted"
            backup.status = "deleted"
            backup.deleted_at = datetime.now(UTC)
            backup.deleted_by = deleted_by

            await self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to delete backup {backup.id}: {e}")
            backup.deletion_status = "failed"
            await self.db.commit()
            return False

    async def delete_backup_immediately(self, backup_id: int) -> Dict[str, Any]:
        """
        Delete a backup immediately (for manual deletion).
        Checks if backup is protected first.
        """
        stmt = select(BackupHistory).where(BackupHistory.id == backup_id)
        result = await self.db.execute(stmt)
        backup = result.scalar_one_or_none()

        if not backup:
            return {"success": False, "error": "Backup not found"}

        if backup.is_protected:
            return {"success": False, "error": "Backup is protected. Unprotect it first."}

        success = await self.execute_deletion(backup)

        if success:
            return {"success": True, "message": f"Backup {backup_id} deleted"}
        else:
            return {"success": False, "error": "Failed to delete backup file"}

    # ============================================================================
    # Pruning Execution
    # ============================================================================

    async def run_time_based_pruning(self) -> Dict[str, Any]:
        """
        Run time-based pruning based on current settings.
        Marks old backups for deletion (with notification period).
        """
        settings = await self.get_settings()
        if not settings or not settings.time_based_enabled:
            return {"status": "skipped", "reason": "Time-based pruning disabled"}

        candidates = await self.get_time_based_candidates(settings.max_age_days)

        if not candidates:
            return {"status": "ok", "message": "No backups to prune", "count": 0}

        marked = []
        if settings.notify_before_delete:
            # Mark for pending deletion with notification
            for backup in candidates:
                if backup.deletion_status != "pending":
                    await self.mark_for_deletion(
                        backup,
                        hours_until_deletion=settings.notify_hours_before,
                        reason=f"older than {settings.max_age_days} days"
                    )
                    marked.append(backup.id)

            # Send notification
            if marked:
                await dispatch_notification("backup_pending_deletion", {
                    "count": len(marked),
                    "backup_ids": marked,
                    "reason": "time_based_pruning",
                    "hours_until_deletion": settings.notify_hours_before,
                })
        else:
            # Delete immediately
            for backup in candidates:
                await self.execute_deletion(backup)
                marked.append(backup.id)

        return {
            "status": "ok",
            "action": "marked_pending" if settings.notify_before_delete else "deleted",
            "count": len(marked),
            "backup_ids": marked,
        }

    async def run_space_based_pruning(self) -> Dict[str, Any]:
        """
        Run space-based pruning when free space is low.
        """
        settings = await self.get_settings()
        if not settings or not settings.space_based_enabled:
            return {"status": "skipped", "reason": "Space-based pruning disabled"}

        storage = self.get_storage_usage()

        # Check local storage
        local_info = storage.get("local", {})
        nfs_info = storage.get("nfs", {})

        # Use whichever storage is primary
        if nfs_info.get("exists") and nfs_info.get("free_percent") is not None:
            free_percent = nfs_info["free_percent"]
            is_critical = free_percent < settings.critical_space_threshold
            is_low = free_percent < settings.min_free_space_percent
        elif local_info.get("exists") and local_info.get("free_percent") is not None:
            free_percent = local_info["free_percent"]
            is_critical = free_percent < settings.critical_space_threshold
            is_low = free_percent < settings.min_free_space_percent
        else:
            return {"status": "error", "reason": "Could not determine storage usage"}

        if not is_low and not is_critical:
            return {
                "status": "ok",
                "message": "Sufficient free space",
                "free_percent": free_percent,
            }

        # Handle critical space
        if is_critical:
            return await self._handle_critical_space(settings, free_percent)

        # Handle low space - mark oldest backups for deletion
        candidates = await self.get_oldest_unprotected_backups(limit=5)

        if not candidates:
            return {
                "status": "warning",
                "message": "Low space but no backups available for pruning",
                "free_percent": free_percent,
            }

        marked = []
        for backup in candidates:
            await self.mark_for_deletion(
                backup,
                hours_until_deletion=settings.notify_hours_before if settings.notify_before_delete else 0,
                reason=f"low disk space ({free_percent}% free)"
            )
            marked.append(backup.id)

        await dispatch_notification("backup_pending_deletion", {
            "count": len(marked),
            "backup_ids": marked,
            "reason": "space_based_pruning",
            "free_percent": free_percent,
        })

        return {
            "status": "ok",
            "action": "marked_pending",
            "count": len(marked),
            "free_percent": free_percent,
        }

    async def run_size_based_pruning(self) -> Dict[str, Any]:
        """
        Run size-based pruning when total backup size exceeds limit.
        """
        settings = await self.get_settings()
        if not settings or not settings.size_based_enabled:
            return {"status": "skipped", "reason": "Size-based pruning disabled"}

        max_size_bytes = settings.max_total_size_gb * (1024**3)
        current_size = await self.get_total_backup_size()

        if current_size <= max_size_bytes:
            return {
                "status": "ok",
                "message": "Total backup size within limit",
                "current_gb": round(current_size / (1024**3), 2),
                "max_gb": settings.max_total_size_gb,
            }

        # Calculate how much needs to be freed
        excess_bytes = current_size - max_size_bytes

        # Get candidates and mark enough for deletion
        candidates = await self.get_oldest_unprotected_backups(limit=20)

        marked = []
        freed_bytes = 0

        for backup in candidates:
            if freed_bytes >= excess_bytes:
                break

            await self.mark_for_deletion(
                backup,
                hours_until_deletion=settings.notify_hours_before if settings.notify_before_delete else 0,
                reason=f"total size exceeds {settings.max_total_size_gb} GB"
            )
            marked.append(backup.id)
            freed_bytes += backup.file_size or 0

        if marked:
            await dispatch_notification("backup_pending_deletion", {
                "count": len(marked),
                "backup_ids": marked,
                "reason": "size_based_pruning",
                "current_gb": round(current_size / (1024**3), 2),
                "max_gb": settings.max_total_size_gb,
            })

        return {
            "status": "ok",
            "action": "marked_pending",
            "count": len(marked),
            "bytes_to_free": freed_bytes,
        }

    async def _handle_critical_space(
        self,
        settings: BackupPruningSettings,
        free_percent: float
    ) -> Dict[str, Any]:
        """Handle critically low disk space."""

        if settings.critical_space_action == "stop_and_alert":
            # Send emergency notification
            await dispatch_notification("backup_critical_space", {
                "free_percent": free_percent,
                "threshold": settings.critical_space_threshold,
                "action": "stopped",
                "message": "Backups stopped due to critical disk space",
            })

            return {
                "status": "critical",
                "action": "stopped",
                "message": "Backups stopped due to critical space",
                "free_percent": free_percent,
            }

        else:  # delete_oldest
            # Emergency deletion - skip notification period
            candidates = await self.get_oldest_unprotected_backups(limit=3)

            deleted = []
            for backup in candidates:
                if await self.execute_deletion(backup):
                    deleted.append(backup.id)

            await dispatch_notification("backup_critical_space", {
                "free_percent": free_percent,
                "threshold": settings.critical_space_threshold,
                "action": "emergency_deletion",
                "deleted_count": len(deleted),
                "message": f"Emergency deleted {len(deleted)} backup(s)",
            })

            return {
                "status": "critical",
                "action": "emergency_deletion",
                "deleted_count": len(deleted),
                "free_percent": free_percent,
            }

    # ============================================================================
    # GFS Retention (BackupConfiguration.retention_*)
    # ============================================================================

    async def _get_backup_configuration(self) -> Optional[BackupConfiguration]:
        stmt = select(BackupConfiguration).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _retention_timezone():
        try:
            return ZoneInfo(settings.timezone)
        except Exception:
            logger.warning(f"Invalid timezone '{settings.timezone}' for retention, using UTC")
            return ZoneInfo("UTC")

    async def apply_gfs_retention(
        self,
        config: Optional[BackupConfiguration] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply the tiered GFS retention configured on the Backup Settings >
        Retention tab (BackupConfiguration.retention_*).

        Only successful, not-deleted, unprotected backups are considered, and
        each backup type is evaluated independently. Selection rules live in
        api.services.retention.select_gfs_retention.

        Deletions honour the pruning "notify before delete" setting: when it is
        on (the default) backups are marked pending and removed by
        execute_pending_deletions() after the notice period; when it is off
        they are deleted immediately.

        Callers other than dry runs must hold the operation lock.
        """
        if config is None:
            config = await self._get_backup_configuration()

        # No configuration row yet: the model defaults apply (enabled, 7/4/6/3),
        # which is also what the settings UI shows before first save.
        enabled = True if config is None or config.retention_enabled is None else bool(config.retention_enabled)
        if not enabled:
            return {"status": "skipped", "reason": "GFS retention disabled"}

        retention = RetentionConfig.from_values(
            getattr(config, "retention_daily_count", None),
            getattr(config, "retention_weekly_count", None),
            getattr(config, "retention_monthly_count", None),
            getattr(config, "retention_min_count", None),
        )
        tz = self._retention_timezone()

        stmt = select(BackupHistory).where(
            and_(
                BackupHistory.status == "success",
                BackupHistory.deleted_at.is_(None),
                or_(
                    BackupHistory.is_protected == False,
                    BackupHistory.is_protected.is_(None)
                ),
            )
        ).order_by(BackupHistory.backup_type, BackupHistory.created_at.desc(), BackupHistory.id.desc())
        result = await self.db.execute(stmt)
        eligible = list(result.scalars().all())

        by_type: Dict[str, List[BackupHistory]] = {}
        for backup in eligible:
            by_type.setdefault(backup.backup_type, []).append(backup)

        pruning_settings = await self.get_settings()
        notify = True if pruning_settings is None or pruning_settings.notify_before_delete is None \
            else bool(pruning_settings.notify_before_delete)
        notify_hours = 24 if pruning_settings is None or pruning_settings.notify_hours_before is None \
            else int(pruning_settings.notify_hours_before)

        summary: Dict[str, Any] = {
            "status": "ok",
            "dry_run": dry_run,
            "config": {
                "daily": retention.daily,
                "weekly": retention.weekly,
                "monthly": retention.monthly,
                "min_count": retention.min_count,
                "timezone": str(tz),
            },
            "action": "marked_pending" if notify else "deleted",
            "kept": 0,
            "to_delete": [],
            "marked": [],
            "deleted": [],
            "failed": [],
            "cancelled": [],
        }

        for backup_type, backups in sorted(by_type.items()):
            keep_ids, delete_ids = select_gfs_retention(
                [(b.id, b.created_at) for b in backups], retention, tz
            )
            summary["kept"] += len(keep_ids)

            for backup in backups:
                if backup.id in keep_ids:
                    # A later run may keep something an earlier run scheduled for
                    # deletion (e.g. newer backups were deleted manually).
                    if (
                        not dry_run
                        and backup.deletion_status == "pending"
                        and (backup.deletion_reason or "").startswith(GFS_DELETION_REASON)
                    ):
                        await self.cancel_deletion(backup.id)
                        summary["cancelled"].append(backup.id)
                    continue

                summary["to_delete"].append({
                    "id": backup.id,
                    "backup_type": backup_type,
                    "filename": backup.filename,
                    "created_at": backup.created_at.isoformat() if backup.created_at else None,
                    "size_bytes": backup.file_size,
                })
                if dry_run:
                    continue

                if notify:
                    if backup.deletion_status == "pending":
                        continue  # already scheduled (by GFS or another rule)
                    logger.info(
                        f"GFS retention: scheduling deletion of backup {backup.id} "
                        f"({backup_type}, {backup.filename}, created {backup.created_at}) in {notify_hours}h"
                    )
                    await self.mark_for_deletion(
                        backup,
                        hours_until_deletion=notify_hours,
                        reason=f"{GFS_DELETION_REASON} (daily={retention.daily}, weekly={retention.weekly}, "
                               f"monthly={retention.monthly}, min={retention.min_count})",
                    )
                    summary["marked"].append(backup.id)
                else:
                    logger.info(
                        f"GFS retention: deleting backup {backup.id} "
                        f"({backup_type}, {backup.filename}, created {backup.created_at})"
                    )
                    if await self.execute_deletion(backup, deleted_by="retention_policy"):
                        summary["deleted"].append(backup.id)
                    else:
                        summary["failed"].append(backup.id)

        if summary["marked"]:
            await dispatch_notification("backup_pending_deletion", {
                "count": len(summary["marked"]),
                "backup_ids": summary["marked"],
                "reason": "gfs_retention",
                "hours_until_deletion": notify_hours,
            })

        if not dry_run:
            logger.info(
                f"GFS retention: kept {summary['kept']}, marked {len(summary['marked'])}, "
                f"deleted {len(summary['deleted'])}, failed {len(summary['failed'])}, "
                f"cancelled {len(summary['cancelled'])}"
            )
        return summary

    async def execute_pending_deletions(self) -> Dict[str, Any]:
        """
        Execute deletions for backups that have passed their scheduled deletion time.
        Called by scheduler task.
        """
        now = datetime.now(UTC)

        # Get all pending deletions that are past their scheduled time
        stmt = select(BackupHistory).where(
            and_(
                BackupHistory.deletion_status == "pending",
                BackupHistory.deleted_at.is_(None),
                BackupHistory.scheduled_deletion_at <= now
            )
        )
        result = await self.db.execute(stmt)
        pending = list(result.scalars().all())

        if not pending:
            return {"status": "ok", "message": "No pending deletions to execute", "count": 0}

        deleted = []
        failed = []

        for backup in pending:
            # Double-check not protected
            if backup.is_protected:
                await self.cancel_deletion(backup.id)
                continue

            if await self.execute_deletion(backup):
                deleted.append(backup.id)
            else:
                failed.append(backup.id)

        return {
            "status": "ok",
            "deleted": deleted,
            "failed": failed,
            "total_deleted": len(deleted),
            "total_failed": len(failed),
        }

    async def run_all_pruning_checks(self) -> Dict[str, Any]:
        """
        Run all pruning checks in order of priority.
        Called by hourly scheduler task.
        """
        results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {},
        }

        # 1. Execute any pending deletions first
        results["checks"]["pending_deletions"] = await self.execute_pending_deletions()

        # 2. Space-based pruning (highest priority)
        results["checks"]["space_based"] = await self.run_space_based_pruning()

        # 3. Size-based pruning
        results["checks"]["size_based"] = await self.run_size_based_pruning()

        # 4. Time-based pruning (lowest priority)
        results["checks"]["time_based"] = await self.run_time_based_pruning()

        # 5. Get current storage status
        results["storage"] = self.get_storage_usage()

        return results


async def run_retention_maintenance(source: str) -> Optional[Dict[str, Any]]:
    """
    Run GFS retention followed by the pruning checks (pending deletions,
    space/size/time based) under the global operation lock.

    Used by the hourly "maintenance_pruning" scheduler job and after every
    successful backup. If another operation (backup, restore, verification)
    holds the lock this run is skipped; the next hourly run catches up.
    Never raises.
    """
    from api.database import async_session_maker

    try:
        async with exclusive_operation("pruning", wait=False):
            async with async_session_maker() as db:
                service = PruningService(db)
                results: Dict[str, Any] = {"source": source}
                try:
                    results["gfs_retention"] = await service.apply_gfs_retention()
                except Exception as e:
                    logger.exception(f"GFS retention failed ({source}): {e}")
                    await db.rollback()
                    results["gfs_retention"] = {"status": "error", "error": str(e)}
                results["pruning"] = await service.run_all_pruning_checks()
                return results
    except OperationBusyError as e:
        logger.info(f"Skipping retention/pruning ({source}): {e}")
        return None
    except Exception as e:
        logger.exception(f"Retention/pruning run failed ({source}): {e}")
        return None
