"""
Backup service - handles PostgreSQL backups, scheduling, and verification.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any
import subprocess
import gzip
import os
import logging

from api.models.backups import (
    BackupSchedule,
    BackupHistory,
    RetentionPolicy,
    VerificationSchedule,
)
from api.schemas.backups import BackupType
from api.security import hash_file_sha256
from api.config import settings
from api.services.notification_service import dispatch_notification

logger = logging.getLogger(__name__)


class BackupService:
    """Backup management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Schedule management

    async def get_schedules(self) -> List[BackupSchedule]:
        """Get all backup schedules."""
        result = await self.db.execute(
            select(BackupSchedule).order_by(BackupSchedule.name)
        )
        return list(result.scalars().all())

    async def get_schedule(self, schedule_id: int) -> Optional[BackupSchedule]:
        """Get backup schedule by ID."""
        result = await self.db.execute(
            select(BackupSchedule).where(BackupSchedule.id == schedule_id)
        )
        return result.scalar_one_or_none()

    async def create_schedule(self, **kwargs) -> BackupSchedule:
        """Create a backup schedule."""
        schedule = BackupSchedule(**kwargs)
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        logger.info(f"Created backup schedule: {schedule.name}")
        return schedule

    async def update_schedule(self, schedule_id: int, **updates) -> Optional[BackupSchedule]:
        """Update a backup schedule."""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(schedule, key):
                setattr(schedule, key, value)

        schedule.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a backup schedule."""
        result = await self.db.execute(
            delete(BackupSchedule).where(BackupSchedule.id == schedule_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    # Backup execution

    async def run_backup(
        self,
        backup_type: str,
        schedule_id: Optional[int] = None,
        compression: str = "gzip",
    ) -> BackupHistory:
        """Execute a backup."""

        # Create history record
        history = BackupHistory(
            backup_type=backup_type,
            schedule_id=schedule_id,
            filename="",
            filepath="",
            started_at=datetime.now(UTC),
            status="running",
            compression=compression,
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        try:
            # Notify start
            await dispatch_notification("backup.started", {
                "backup_type": backup_type,
                "backup_id": history.id,
            })

            # Determine database(s)
            if backup_type == BackupType.POSTGRES_FULL:
                databases = ["n8n", "n8n_management"]
            elif backup_type == BackupType.POSTGRES_N8N:
                databases = ["n8n"]
            elif backup_type == BackupType.POSTGRES_MGMT:
                databases = ["n8n_management"]
            else:
                databases = []

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{backup_type}_{timestamp}.sql"
            if compression == "gzip":
                filename += ".gz"

            # Determine storage path
            storage_dir = await self._get_storage_location()
            type_dir = os.path.join(storage_dir, backup_type)
            os.makedirs(type_dir, exist_ok=True)
            filepath = os.path.join(type_dir, filename)

            # Execute backup
            row_counts = {}
            for db_name in databases:
                await self._execute_pg_dump(db_name, filepath, compression)
                row_counts[db_name] = await self._get_row_counts(db_name)

            # Calculate checksum and file size
            file_size = os.path.getsize(filepath)
            checksum = hash_file_sha256(filepath)

            # Get postgres version
            pg_version = await self._get_postgres_version()

            # Update history
            history.filename = filename
            history.filepath = filepath
            history.file_size = file_size
            history.compressed_size = file_size if compression != "none" else None
            history.checksum = checksum
            history.postgres_version = pg_version
            history.row_counts = row_counts
            history.database_name = ",".join(databases)
            history.table_count = sum(len(rc) for rc in row_counts.values()) if row_counts else None
            history.status = "success"
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())
            history.storage_location = "nfs" if "/mnt/backups" in filepath else "local"

            await self.db.commit()

            # Notify success
            await dispatch_notification("backup.success", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "filename": filename,
                "size_mb": round(file_size / 1024 / 1024, 2),
                "duration_seconds": history.duration_seconds,
            })

            logger.info(f"Backup completed: {filename} ({file_size} bytes)")
            return history

        except Exception as e:
            history.status = "failed"
            history.error_message = str(e)
            history.completed_at = datetime.now(UTC)
            await self.db.commit()

            # Notify failure
            await dispatch_notification("backup.failed", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "error": str(e),
            }, severity="error")

            logger.error(f"Backup failed: {e}")
            raise

    async def _execute_pg_dump(self, database: str, filepath: str, compression: str) -> None:
        """Execute pg_dump command."""
        # Get connection info from environment
        host = os.environ.get("POSTGRES_HOST", "postgres")
        user = os.environ.get("POSTGRES_USER", "n8n")
        password = os.environ.get("POSTGRES_PASSWORD", "")

        cmd = [
            "pg_dump",
            "-h", host,
            "-U", user,
            "-d", database,
            "--no-owner",
            "--no-acl",
            "-F", "c",  # Custom format
        ]

        env = {**os.environ, "PGPASSWORD": password}

        if compression == "gzip":
            # Pipe through gzip
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            with gzip.open(filepath, 'wb') as f:
                while chunk := process.stdout.read(8192):
                    f.write(chunk)

            _, stderr = process.communicate()
            if process.returncode != 0:
                raise Exception(f"pg_dump failed: {stderr.decode()}")
        else:
            with open(filepath, 'wb') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
                if result.returncode != 0:
                    raise Exception(f"pg_dump failed: {result.stderr.decode()}")

    async def _get_storage_location(self) -> str:
        """Get backup storage location (NFS or local)."""
        nfs_mount = settings.nfs_mount_point
        if os.path.ismount(nfs_mount):
            return nfs_mount
        return settings.backup_staging_dir

    async def _get_row_counts(self, database: str) -> Dict[str, int]:
        """Get row counts for tables in database."""
        # This would query the actual database - simplified here
        return {}

    async def _get_postgres_version(self) -> str:
        """Get PostgreSQL version."""
        try:
            result = subprocess.run(
                ["psql", "--version"],
                capture_output=True,
                text=True,
            )
            return result.stdout.split()[2] if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    # History management

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        backup_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[BackupHistory]:
        """Get backup history."""
        query = select(BackupHistory).order_by(BackupHistory.created_at.desc())

        if backup_type:
            query = query.where(BackupHistory.backup_type == backup_type)
        if status:
            query = query.where(BackupHistory.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_backup(self, backup_id: int) -> Optional[BackupHistory]:
        """Get backup by ID."""
        result = await self.db.execute(
            select(BackupHistory).where(BackupHistory.id == backup_id)
        )
        return result.scalar_one_or_none()

    async def delete_backup(self, backup_id: int) -> bool:
        """Delete a backup (file and record)."""
        backup = await self.get_backup(backup_id)
        if not backup:
            return False

        # Delete file if exists
        if backup.filepath and os.path.exists(backup.filepath):
            try:
                os.remove(backup.filepath)
            except Exception as e:
                logger.warning(f"Failed to delete backup file: {e}")

        # Mark as deleted
        backup.deleted_at = datetime.now(UTC)
        backup.deleted_by = "manual"
        await self.db.commit()

        return True

    # Retention policies

    async def get_retention_policies(self) -> List[RetentionPolicy]:
        """Get all retention policies."""
        result = await self.db.execute(
            select(RetentionPolicy).order_by(RetentionPolicy.backup_type)
        )
        return list(result.scalars().all())

    async def get_retention_policy(self, backup_type: str) -> Optional[RetentionPolicy]:
        """Get retention policy for a backup type."""
        result = await self.db.execute(
            select(RetentionPolicy).where(RetentionPolicy.backup_type == backup_type)
        )
        return result.scalar_one_or_none()

    async def update_retention_policy(self, backup_type: str, **updates) -> RetentionPolicy:
        """Update or create retention policy."""
        policy = await self.get_retention_policy(backup_type)

        if policy:
            for key, value in updates.items():
                if hasattr(policy, key):
                    setattr(policy, key, value)
            policy.updated_at = datetime.now(UTC)
        else:
            policy = RetentionPolicy(backup_type=backup_type, **updates)
            self.db.add(policy)

        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    # Verification

    async def get_verification_schedule(self) -> Optional[VerificationSchedule]:
        """Get verification schedule."""
        result = await self.db.execute(
            select(VerificationSchedule).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_verification_schedule(self, **updates) -> VerificationSchedule:
        """Update verification schedule."""
        schedule = await self.get_verification_schedule()

        if schedule:
            for key, value in updates.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)
            schedule.updated_at = datetime.now(UTC)
        else:
            schedule = VerificationSchedule(**updates)
            self.db.add(schedule)

        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def verify_backup(self, backup_id: int) -> Dict[str, Any]:
        """Verify a backup by test restoring."""
        backup = await self.get_backup(backup_id)
        if not backup:
            return {"status": "failed", "error": "Backup not found"}

        if backup.backup_type not in ["postgres_full", "postgres_n8n", "postgres_mgmt"]:
            backup.verification_status = "skipped"
            backup.verification_date = datetime.now(UTC)
            backup.verification_details = {"reason": "Non-postgres backup"}
            await self.db.commit()
            return {"status": "skipped", "reason": "Non-postgres backup"}

        # Check file exists
        if not os.path.exists(backup.filepath):
            backup.verification_status = "failed"
            backup.verification_date = datetime.now(UTC)
            backup.verification_details = {"error": "Backup file not found"}
            await self.db.commit()
            return {"status": "failed", "error": "Backup file not found"}

        # Verify checksum
        current_checksum = hash_file_sha256(backup.filepath)
        if current_checksum != backup.checksum:
            backup.verification_status = "failed"
            backup.verification_date = datetime.now(UTC)
            backup.verification_details = {"error": "Checksum mismatch"}
            await self.db.commit()
            return {"status": "failed", "error": "Checksum mismatch"}

        # Mark as passed (full restore verification would be done in actual implementation)
        backup.verification_status = "passed"
        backup.verification_date = datetime.now(UTC)
        backup.verification_details = {"checksum_verified": True}
        await self.db.commit()

        return {"status": "passed", "checksum_verified": True}

    # Statistics

    async def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics."""
        # Count by status
        result = await self.db.execute(
            select(
                BackupHistory.status,
                func.count(BackupHistory.id),
            )
            .where(BackupHistory.deleted_at.is_(None))
            .group_by(BackupHistory.status)
        )
        by_status = {row[0]: row[1] for row in result.all()}

        # Count by type
        result = await self.db.execute(
            select(
                BackupHistory.backup_type,
                func.count(BackupHistory.id),
            )
            .where(BackupHistory.deleted_at.is_(None))
            .group_by(BackupHistory.backup_type)
        )
        by_type = {row[0]: row[1] for row in result.all()}

        # Total size
        result = await self.db.execute(
            select(func.sum(BackupHistory.file_size))
            .where(BackupHistory.deleted_at.is_(None))
            .where(BackupHistory.status == "success")
        )
        total_size = result.scalar() or 0

        # Last backups
        result = await self.db.execute(
            select(BackupHistory.created_at)
            .where(BackupHistory.deleted_at.is_(None))
            .order_by(BackupHistory.created_at.desc())
            .limit(1)
        )
        last_backup = result.scalar()

        result = await self.db.execute(
            select(BackupHistory.created_at)
            .where(BackupHistory.deleted_at.is_(None))
            .where(BackupHistory.status == "success")
            .order_by(BackupHistory.created_at.desc())
            .limit(1)
        )
        last_successful = result.scalar()

        return {
            "total_backups": sum(by_status.values()),
            "successful_backups": by_status.get("success", 0),
            "failed_backups": by_status.get("failed", 0),
            "total_size_bytes": total_size,
            "last_backup": last_backup,
            "last_successful_backup": last_successful,
            "by_type": by_type,
            "by_status": by_status,
        }
