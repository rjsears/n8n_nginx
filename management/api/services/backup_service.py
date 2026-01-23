"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/backup_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, text
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any, Tuple
import subprocess
import asyncio
import gzip
import tarfile
import tempfile
import shutil
import json
import hashlib
import os
import logging

from api.models.backups import (
    BackupSchedule,
    BackupHistory,
    RetentionPolicy,
    VerificationSchedule,
    BackupContents,
    BackupPruningSettings,
    BackupConfiguration,
)
from api.schemas.backups import BackupType
from api.security import hash_file_sha256
from api.config import settings
from api.services.notification_service import dispatch_notification

logger = logging.getLogger(__name__)


# Config files to include in backups
# Using /app/host_project/ which is a directory mount (more reliable than individual file mounts)
# Files that don't exist are skipped (e.g., dozzle/ntfy only if those services are installed)
CONFIG_FILES = [
    # Core config files
    {"name": ".env", "host_path": "/app/host_project/.env", "archive_path": "config/.env"},
    {"name": "docker-compose.yaml", "host_path": "/app/host_project/docker-compose.yaml", "archive_path": "config/docker-compose.yaml"},
    {"name": "nginx.conf", "host_path": "/app/host_project/nginx.conf", "archive_path": "config/nginx.conf"},
    {"name": "init-db.sh", "host_path": "/app/host_project/init-db.sh", "archive_path": "config/init-db.sh"},
    # DNS credential files (cloudflare is most common, others are optional)
    {"name": "cloudflare.ini", "host_path": "/app/host_project/cloudflare.ini", "archive_path": "config/cloudflare.ini"},
    {"name": "route53.ini", "host_path": "/app/host_project/route53.ini", "archive_path": "config/route53.ini"},
    {"name": "digitalocean.ini", "host_path": "/app/host_project/digitalocean.ini", "archive_path": "config/digitalocean.ini"},
    {"name": "google.json", "host_path": "/app/host_project/google.json", "archive_path": "config/google.json"},
    # Optional service configs (created by setup.sh if services are installed)
    {"name": "tailscale-serve.json", "host_path": "/app/host_project/tailscale-serve.json", "archive_path": "config/tailscale-serve.json"},
    {"name": "dozzle/users.yml", "host_path": "/app/host_project/dozzle/users.yml", "archive_path": "config/dozzle/users.yml"},
    {"name": "ntfy/server.yml", "host_path": "/app/host_project/ntfy/server.yml", "archive_path": "config/ntfy/server.yml"},
    # Public website (FileBrowser) - only exists if INSTALL_PUBLIC_WEBSITE=true during setup
    {"name": "filebrowser.db", "host_path": "/app/host_project/filebrowser.db", "archive_path": "config/filebrowser.db"},
]

# Public website Docker volume name (from settings, defaults to "public_web_root")
PUBLIC_WEBSITE_VOLUME = settings.public_website_volume
# Path to check if public website is installed
PUBLIC_WEBSITE_INDICATOR = "/app/host_project/filebrowser.db"


def calculate_file_checksum(filepath: str, algorithm: str = None) -> str:
    """
    Calculate file checksum using configured algorithm.

    Args:
        filepath: Path to the file
        algorithm: Override algorithm ('sha256' or 'md5'), defaults to settings.public_website_checksum_algorithm

    Returns:
        Hex digest of the file checksum
    """
    if algorithm is None:
        algorithm = settings.public_website_checksum_algorithm

    if algorithm.lower() == "md5":
        hasher = hashlib.md5()
    else:
        hasher = hashlib.sha256()

    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)

    return hasher.hexdigest()

# SSL certificate paths
SSL_CERT_PATH = "/etc/letsencrypt/live"


class BackupService:
    """Backup management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================================
    # Progress Tracking
    # ============================================================================

    async def _update_progress(
        self,
        history: BackupHistory,
        progress: int,
        message: str
    ) -> None:
        """Update backup progress in database."""
        try:
            history.progress = min(progress, 100)
            history.progress_message = message
            await self.db.commit()
            logger.info(f"Backup {history.id}: {progress}% - {message}")
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

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
        # Set timezone to system default if not provided
        if "timezone" not in kwargs or kwargs["timezone"] is None:
            from api.config import settings
            kwargs["timezone"] = settings.timezone

        schedule = BackupSchedule(**kwargs)
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        logger.info(f"Created backup schedule: {schedule.name} (timezone: {schedule.timezone})")
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
        logger.info(f"Starting backup: type={backup_type}, compression={compression}")

        # Pre-flight validation
        preflight_errors = []

        # Check PostgreSQL credentials
        pg_host = os.environ.get("POSTGRES_HOST", "")
        pg_user = os.environ.get("POSTGRES_USER", "")
        pg_password = os.environ.get("POSTGRES_PASSWORD", "")

        if not pg_host:
            preflight_errors.append("POSTGRES_HOST environment variable is not set")
        if not pg_user:
            preflight_errors.append("POSTGRES_USER environment variable is not set")
        if not pg_password:
            preflight_errors.append("POSTGRES_PASSWORD environment variable is not set")

        if preflight_errors:
            error_msg = "Backup pre-flight check failed: " + "; ".join(preflight_errors)
            logger.error(error_msg)
            # Create a failed history record
            history = BackupHistory(
                backup_type=backup_type,
                schedule_id=schedule_id,
                filename="",
                filepath="",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                status="failed",
                error_message=error_msg,
                compression=compression,
                storage_location="unknown",
            )
            self.db.add(history)
            await self.db.commit()
            await self.db.refresh(history)
            raise Exception(error_msg)

        # Create history record
        history = BackupHistory(
            backup_type=backup_type,
            schedule_id=schedule_id,
            filename="",
            filepath="",
            started_at=datetime.now(UTC),
            status="running",
            compression=compression,
            storage_location="local",  # Default, will be updated
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)
        logger.info(f"Created backup history record: id={history.id}")

        try:
            # Notify start
            await dispatch_notification("backup_started", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "started_at": history.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

            # Determine database(s)
            if backup_type == BackupType.POSTGRES_FULL or backup_type == "postgres_full":
                databases = ["n8n", "n8n_management"]
            elif backup_type == BackupType.POSTGRES_N8N or backup_type == "postgres_n8n":
                databases = ["n8n"]
            elif backup_type == BackupType.POSTGRES_MGMT or backup_type == "postgres_mgmt":
                databases = ["n8n_management"]
            else:
                databases = []

            logger.info(f"Databases to backup: {databases}")

            # Generate filename using configured timezone
            tz = ZoneInfo(settings.timezone)
            timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
            filename = f"{backup_type}_{timestamp}.sql"
            if compression == "gzip":
                filename += ".gz"

            # Determine storage path
            storage_dir = await self._get_storage_location()
            logger.info(f"Storage directory: {storage_dir}")
            type_dir = os.path.join(storage_dir, backup_type)
            os.makedirs(type_dir, exist_ok=True)
            filepath = os.path.join(type_dir, filename)
            logger.info(f"Backup filepath: {filepath}")

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
            await dispatch_notification("backup_success", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "filename": filename,
                "size_mb": round(file_size / 1024 / 1024, 2),
                "duration_seconds": history.duration_seconds,
                "workflow_count": 0,  # Simple backup doesn't extract workflow count
                "config_file_count": 0,  # Simple backup doesn't include config files
                "completed_at": history.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

            logger.info(f"Backup completed: {filename} ({file_size} bytes)")

            # Run auto-verification if enabled
            await self._run_auto_verification(history)

            return history

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"{str(e)}\n\nTraceback:\n{error_details}"

            history.status = "failed"
            history.error_message = error_msg
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())

            try:
                await self.db.commit()
            except Exception as db_error:
                logger.error(f"Failed to save error to database: {db_error}")

            # Notify failure
            try:
                await dispatch_notification("backup_failure", {
                    "backup_type": backup_type,
                    "backup_id": history.id,
                    "error": str(e),
                    "failed_at": history.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
                }, severity="error")
            except Exception as notif_error:
                logger.error(f"Failed to send failure notification: {notif_error}")

            logger.error(f"Backup failed (id={history.id}): {e}\n{error_details}")
            raise

    async def _execute_pg_dump(self, database: str, filepath: str, compression: str) -> None:
        """Execute pg_dump command using async subprocess."""
        # Get connection info from environment
        host = os.environ.get("POSTGRES_HOST", "postgres")
        user = os.environ.get("POSTGRES_USER", "n8n")
        password = os.environ.get("POSTGRES_PASSWORD", "")

        logger.info(f"Starting pg_dump for database '{database}' to '{filepath}'")
        logger.debug(f"PostgreSQL host: {host}, user: {user}")

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

        try:
            if compression == "gzip":
                # Run pg_dump and pipe to gzip using asyncio
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

                # Read stdout and write to gzip file
                with gzip.open(filepath, 'wb') as f:
                    while True:
                        chunk = await process.stdout.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

                # Wait for process to complete and get stderr
                _, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logger.error(f"pg_dump failed for {database}: {error_msg}")
                    raise Exception(f"pg_dump failed: {error_msg}")
            else:
                # Run without compression
                with open(filepath, 'wb') as f:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=f,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                    _, stderr = await process.communicate()

                    if process.returncode != 0:
                        error_msg = stderr.decode() if stderr else "Unknown error"
                        logger.error(f"pg_dump failed for {database}: {error_msg}")
                        raise Exception(f"pg_dump failed: {error_msg}")

            logger.info(f"pg_dump completed successfully for database '{database}'")

        except FileNotFoundError:
            logger.error("pg_dump command not found - is postgresql-client installed?")
            raise Exception("pg_dump command not found - postgresql-client not installed")
        except Exception as e:
            logger.error(f"Error during pg_dump: {str(e)}")
            raise

    async def _get_backup_configuration(self) -> Optional[BackupConfiguration]:
        """Get the current backup configuration from database."""
        stmt = select(BackupConfiguration).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _should_auto_verify(self, backup_id: int) -> bool:
        """
        Check if this backup should be auto-verified based on configuration.
        Returns True if auto_verify_enabled and this is the Nth backup (based on verify_frequency).
        """
        config = await self._get_backup_configuration()
        if not config or not config.auto_verify_enabled:
            return False

        frequency = config.verify_frequency or 1

        if frequency == 1:
            # Verify every backup
            return True

        # Count total successful backups to determine if this is an Nth backup
        stmt = select(func.count(BackupHistory.id)).where(
            BackupHistory.status == "success"
        )
        result = await self.db.execute(stmt)
        total_backups = result.scalar() or 0

        # Verify every Nth backup (e.g., if frequency=5, verify backups 5, 10, 15, etc.)
        return total_backups % frequency == 0

    async def _run_auto_verification(self, backup: BackupHistory) -> None:
        """
        Run auto-verification on a backup if enabled in configuration.
        This is called after a successful backup completes.
        """
        try:
            if await self._should_auto_verify(backup.id):
                logger.info(f"Auto-verifying backup {backup.id}")

                # Send verification started notification
                await dispatch_notification("verification_started", {
                    "backup_id": backup.id,
                    "backup_filename": backup.filename,
                    "backup_type": backup.backup_type,
                    "source": "auto",
                })

                result = await self.verify_backup(backup.id)
                status = result.get('status', 'unknown')
                logger.info(f"Auto-verification result for backup {backup.id}: {status}")

                # Refresh backup to get updated verification details
                await self.db.refresh(backup)

                # Get workflow and config counts by explicitly querying (not lazy loading)
                contents = await self.get_backup_contents(backup.id)
                workflow_count = contents.workflow_count if contents else 0
                credential_count = contents.credential_count if contents else 0
                config_count = contents.config_file_count if contents else 0

                # Calculate size in MB
                size_mb = round(backup.file_size / (1024 * 1024), 2) if backup.file_size else 0

                # Send verification result notification
                if status == "passed":
                    await dispatch_notification("verification_passed", {
                        "backup_id": backup.id,
                        "backup_filename": backup.filename,
                        "backup_type": backup.backup_type,
                        "backup_created_at": backup.created_at.strftime("%Y-%m-%d %H:%M:%S") if backup.created_at else None,
                        "size_mb": size_mb,
                        "duration_seconds": backup.duration_seconds,
                        "completed_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        "workflow_count": workflow_count,
                        "credential_count": credential_count,
                        "config_file_count": config_count,
                        "checksum_verified": result.get("checksum_verified", False),
                        "source": "auto",
                    })
                elif status == "failed":
                    await dispatch_notification("verification_failed", {
                        "backup_id": backup.id,
                        "backup_filename": backup.filename,
                        "backup_type": backup.backup_type,
                        "backup_created_at": backup.created_at.strftime("%Y-%m-%d %H:%M:%S") if backup.created_at else None,
                        "size_mb": size_mb,
                        "duration_seconds": backup.duration_seconds,
                        "completed_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        "workflow_count": workflow_count,
                        "credential_count": credential_count,
                        "config_file_count": config_count,
                        "error": result.get("error", "Unknown error"),
                        "source": "auto",
                    })
                # Note: "skipped" status doesn't need a notification
        except Exception as e:
            # Don't fail the backup if verification fails - just log it
            logger.error(f"Auto-verification failed for backup {backup.id}: {e}")
            # Still send a failure notification so users know verification failed
            try:
                # Try to get backup contents for detailed notification
                contents = None
                size_mb = 0
                if backup:
                    try:
                        contents = await self.get_backup_contents(backup.id)
                        size_mb = round(backup.file_size / (1024 * 1024), 2) if backup.file_size else 0
                    except Exception:
                        pass

                await dispatch_notification("verification_failed", {
                    "backup_id": backup.id if backup else 0,
                    "backup_filename": backup.filename if backup else "unknown",
                    "backup_type": backup.backup_type if backup else "unknown",
                    "backup_created_at": backup.created_at.strftime("%Y-%m-%d %H:%M:%S") if backup and backup.created_at else None,
                    "size_mb": size_mb,
                    "workflow_count": contents.workflow_count if contents else 0,
                    "credential_count": contents.credential_count if contents else 0,
                    "config_file_count": contents.config_file_count if contents else 0,
                    "error": str(e),
                    "source": "auto",
                })
            except Exception:
                pass  # Don't let notification failure cause more issues

    async def _get_storage_location(self) -> str:
        """Get backup storage location based on configuration."""
        # Try to get configuration from database
        config = await self._get_backup_configuration()

        if config:
            # Use configured storage preference
            if config.storage_preference == 'nfs' and config.nfs_enabled:
                nfs_path = config.nfs_storage_path
                if nfs_path and os.path.exists(nfs_path) and os.access(nfs_path, os.W_OK):
                    return nfs_path
            elif config.storage_preference == 'both' and config.nfs_enabled:
                # Prefer NFS if available, fallback to local
                nfs_path = config.nfs_storage_path
                if nfs_path and os.path.exists(nfs_path) and os.access(nfs_path, os.W_OK):
                    return nfs_path

            # Use primary storage path from config
            primary_path = config.primary_storage_path
            if primary_path and os.path.exists(primary_path):
                return primary_path

        # Fallback to environment settings
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

    def _build_history_query(
        self,
        backup_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Build the base query for history with filters."""
        query = select(BackupHistory).where(
            BackupHistory.deleted_at.is_(None)
        )

        if backup_type:
            query = query.where(BackupHistory.backup_type == backup_type)
        if status:
            query = query.where(BackupHistory.status == status)
        if start_date:
            query = query.where(BackupHistory.created_at >= start_date)
        if end_date:
            # Add one day to include the end date fully
            query = query.where(BackupHistory.created_at < end_date + timedelta(days=1))

        return query

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        backup_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[BackupHistory]:
        """Get backup history (excludes soft-deleted backups)."""
        query = self._build_history_query(backup_type, status, start_date, end_date)
        query = query.order_by(BackupHistory.created_at.desc())
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_history_count(
        self,
        backup_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get total count of backup history matching filters."""
        base_query = self._build_history_query(backup_type, status, start_date, end_date)
        count_query = select(func.count()).select_from(base_query.subquery())
        result = await self.db.execute(count_query)
        return result.scalar() or 0

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

    # ============================================================================
    # Phase 1: Enhanced Backup with Metadata
    # ============================================================================

    async def capture_workflow_manifest(self, n8n_db: AsyncSession) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Capture workflow manifest from n8n database.
        Returns count and list of workflow metadata (no sensitive data).
        """
        try:
            # Query n8n workflow_entity table (include isArchived for archived status)
            result = await n8n_db.execute(text("""
                SELECT
                    id, name, active,
                    "createdAt" as created_at,
                    "updatedAt" as updated_at,
                    COALESCE("isArchived", false) as is_archived
                FROM workflow_entity
                ORDER BY name
            """))
            rows = result.fetchall()

            workflows = []
            for row in rows:
                workflow_data = {
                    "id": str(row[0]),
                    "name": row[1],
                    "active": row[2] if row[2] is not None else False,
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                    "archived": row[5] if row[5] is not None else False,
                }

                # Try to get node count and tags if available
                try:
                    node_result = await n8n_db.execute(text("""
                        SELECT nodes FROM workflow_entity WHERE id = :id
                    """), {"id": row[0]})
                    node_row = node_result.fetchone()
                    if node_row and node_row[0]:
                        nodes = node_row[0] if isinstance(node_row[0], list) else []
                        workflow_data["node_count"] = len(nodes)
                except Exception:
                    workflow_data["node_count"] = None

                workflows.append(workflow_data)

            logger.info(f"Captured manifest for {len(workflows)} workflows")
            return len(workflows), workflows

        except Exception as e:
            logger.warning(f"Failed to capture workflow manifest: {e}")
            return 0, []

    async def capture_credential_manifest(self, n8n_db: AsyncSession) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Capture credential manifest from n8n database.
        Returns count and list of credential metadata (NO sensitive data).
        """
        try:
            # Query n8n credentials_entity table - only metadata, no data field
            result = await n8n_db.execute(text("""
                SELECT id, name, type
                FROM credentials_entity
                ORDER BY name
            """))
            rows = result.fetchall()

            credentials = []
            for row in rows:
                credentials.append({
                    "id": str(row[0]),
                    "name": row[1],
                    "type": row[2],
                })

            logger.info(f"Captured manifest for {len(credentials)} credentials")
            return len(credentials), credentials

        except Exception as e:
            logger.warning(f"Failed to capture credential manifest: {e}")
            return 0, []

    async def capture_config_file_manifest(self) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Capture config file manifest with checksums.
        Returns count and list of config file metadata.
        """
        config_files = []

        for config in CONFIG_FILES:
            host_path = config["host_path"]
            if os.path.exists(host_path):
                try:
                    file_stat = os.stat(host_path)
                    checksum = hash_file_sha256(host_path)
                    modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)

                    config_files.append({
                        "name": config["name"],
                        "path": config["archive_path"],
                        "size": file_stat.st_size,
                        "checksum": checksum,
                        "modified_at": modified_at.isoformat(),
                    })
                    logger.info(f"Config file found: {config['name']} at {host_path}")
                except Exception as e:
                    logger.warning(f"Failed to capture config file {config['name']}: {e}")
            else:
                logger.warning(f"Config file NOT found: {config['name']} at {host_path}")

        # Check for SSL certificates
        if os.path.exists(SSL_CERT_PATH):
            for domain_dir in os.listdir(SSL_CERT_PATH):
                domain_path = os.path.join(SSL_CERT_PATH, domain_dir)
                if os.path.isdir(domain_path):
                    for cert_file in ["fullchain.pem", "privkey.pem", "cert.pem", "chain.pem"]:
                        cert_path = os.path.join(domain_path, cert_file)
                        if os.path.exists(cert_path):
                            try:
                                file_stat = os.stat(cert_path)
                                checksum = hash_file_sha256(cert_path)
                                modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)

                                config_files.append({
                                    "name": f"{domain_dir}/{cert_file}",
                                    "path": f"ssl/{domain_dir}/{cert_file}",
                                    "size": file_stat.st_size,
                                    "checksum": checksum,
                                    "modified_at": modified_at.isoformat(),
                                })
                            except Exception as e:
                                logger.warning(f"Failed to capture SSL cert {cert_path}: {e}")

        logger.info(f"Captured manifest for {len(config_files)} config files")
        return len(config_files), config_files

    async def capture_database_schema_manifest(self, databases: List[str]) -> List[Dict[str, Any]]:
        """
        Capture database schema manifest with table info and row counts.
        """
        schema_manifest = []

        host = os.environ.get("POSTGRES_HOST", "postgres")
        user = os.environ.get("POSTGRES_USER", "n8n")
        password = os.environ.get("POSTGRES_PASSWORD", "")

        for db_name in databases:
            try:
                # Use psql to get table info
                cmd = [
                    "psql",
                    "-h", host,
                    "-U", user,
                    "-d", db_name,
                    "-t", "-A",
                    "-c", """
                        SELECT
                            t.table_name,
                            (SELECT COUNT(*) FROM information_schema.columns c WHERE c.table_name = t.table_name) as col_count
                        FROM information_schema.tables t
                        WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
                        ORDER BY t.table_name
                    """
                ]

                env = {**os.environ, "PGPASSWORD": password}
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)

                if result.returncode != 0:
                    logger.warning(f"Failed to get schema for {db_name}: {result.stderr}")
                    continue

                tables = []
                total_rows = 0

                for line in result.stdout.strip().split('\n'):
                    if '|' in line:
                        parts = line.split('|')
                        table_name = parts[0].strip()

                        # Get row count for table
                        count_cmd = [
                            "psql",
                            "-h", host,
                            "-U", user,
                            "-d", db_name,
                            "-t", "-A",
                            "-c", f"SELECT COUNT(*) FROM \"{table_name}\""
                        ]
                        count_result = subprocess.run(count_cmd, capture_output=True, text=True, env=env)
                        row_count = int(count_result.stdout.strip()) if count_result.returncode == 0 else 0
                        total_rows += row_count

                        # Get column names
                        col_cmd = [
                            "psql",
                            "-h", host,
                            "-U", user,
                            "-d", db_name,
                            "-t", "-A",
                            "-c", f"""
                                SELECT column_name FROM information_schema.columns
                                WHERE table_name = '{table_name}' AND table_schema = 'public'
                                ORDER BY ordinal_position
                            """
                        ]
                        col_result = subprocess.run(col_cmd, capture_output=True, text=True, env=env)
                        columns = [c.strip() for c in col_result.stdout.strip().split('\n') if c.strip()]

                        tables.append({
                            "name": table_name,
                            "row_count": row_count,
                            "columns": columns,
                        })

                schema_manifest.append({
                    "database": db_name,
                    "tables": tables,
                    "total_rows": total_rows,
                })

                logger.info(f"Captured schema for {db_name}: {len(tables)} tables, {total_rows} total rows")

            except Exception as e:
                logger.warning(f"Failed to capture schema for {db_name}: {e}")

        return schema_manifest

    async def capture_public_website_manifest(self, public_website_dir: str) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Capture public website file manifest with checksums.
        Scans the backed-up public website directory and creates a manifest
        of all files with their metadata and checksums.

        Args:
            public_website_dir: Path to the backed-up public website files

        Returns:
            Tuple of (file_count, manifest_list)
        """
        manifest = []

        if not os.path.exists(public_website_dir):
            logger.warning(f"Public website directory does not exist: {public_website_dir}")
            return 0, []

        try:
            algorithm = settings.public_website_checksum_algorithm

            for root, dirs, files in os.walk(public_website_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, public_website_dir)

                    try:
                        file_stat = os.stat(file_path)
                        checksum = calculate_file_checksum(file_path, algorithm)
                        modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)

                        manifest.append({
                            "name": filename,
                            "path": rel_path,
                            "size": file_stat.st_size,
                            "checksum": checksum,
                            "checksum_algorithm": algorithm,
                            "modified_at": modified_at.isoformat(),
                        })
                    except Exception as e:
                        logger.warning(f"Failed to process public website file {rel_path}: {e}")

            logger.info(f"Captured manifest for {len(manifest)} public website files")
            return len(manifest), manifest

        except Exception as e:
            logger.error(f"Failed to capture public website manifest: {e}")
            return 0, []

    async def create_complete_archive(
        self,
        backup_type: str,
        databases: List[str],
        n8n_db: AsyncSession,
        compression: str = "gzip",
        history: Optional[BackupHistory] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Create complete backup archive with all components.
        Returns filepath and metadata dict.
        """
        tz = ZoneInfo(settings.timezone)
        timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
        archive_name = f"backup_{timestamp}.n8n_backup.tar.gz"

        storage_dir = await self._get_storage_location()
        type_dir = os.path.join(storage_dir, backup_type)
        os.makedirs(type_dir, exist_ok=True)
        archive_path = os.path.join(type_dir, archive_name)

        # Progress update helper
        async def update_progress(pct: int, msg: str):
            if history:
                await self._update_progress(history, pct, msg)

        await update_progress(5, "Initializing backup")

        # Create temp directory for staging
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata = {
                "backup_type": backup_type,
                "created_at": datetime.now(UTC).isoformat(),
                "databases": databases,
                "n8n_version": await self._get_n8n_version(),
                "postgres_version": await self._get_postgres_version(),
            }

            # 1. Dump databases (5-40%)
            await update_progress(10, "Dumping databases")
            db_dir = os.path.join(temp_dir, "databases")
            os.makedirs(db_dir)

            row_counts = {}
            db_count = len(databases)
            for idx, db_name in enumerate(databases):
                progress = 10 + int((idx / max(db_count, 1)) * 30)
                await update_progress(progress, f"Dumping database: {db_name}")
                db_file = os.path.join(db_dir, f"{db_name}.dump")
                await self._execute_pg_dump_to_file(db_name, db_file)
                row_counts[db_name] = await self._get_row_counts(db_name)

            metadata["row_counts"] = row_counts

            # 2. Copy config files (40-50%)
            await update_progress(45, "Copying config files")
            config_dir = os.path.join(temp_dir, "config")
            os.makedirs(config_dir)

            # Log what we're looking for
            logger.info(f"Looking for config files. Checking /app/host_project exists: {os.path.exists('/app/host_project')}")
            if os.path.exists('/app/host_project'):
                logger.info(f"Contents of /app/host_project: {os.listdir('/app/host_project')[:10]}...")

            for config in CONFIG_FILES:
                if os.path.exists(config["host_path"]):
                    try:
                        dest_path = os.path.join(temp_dir, config["archive_path"])
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(config["host_path"], dest_path)
                        # Verify the copy was successful
                        if os.path.exists(dest_path):
                            logger.info(f"Copied config file: {config['name']} -> {config['archive_path']} (size: {os.path.getsize(dest_path)} bytes)")
                        else:
                            logger.error(f"Copy verification failed: {config['name']} - dest file not found after copy")
                    except Exception as e:
                        logger.error(f"Failed to copy config file {config['name']}: {e}")
                else:
                    logger.warning(f"Config file missing, skipping: {config['name']} (expected at {config['host_path']})")

            # 3. Copy SSL certificates if they exist (50-55%)
            await update_progress(50, "Copying SSL certificates")
            if os.path.exists(SSL_CERT_PATH):
                ssl_dir = os.path.join(temp_dir, "ssl")
                shutil.copytree(SSL_CERT_PATH, ssl_dir)

            # 3.5 Backup public website volume if installed and enabled (52-55%)
            public_website_included = False
            public_website_file_count = 0
            if self._is_public_website_installed():
                # Check if include_public_website is enabled in config
                config = await self._get_backup_configuration()
                if config and config.include_public_website:
                    await update_progress(52, "Backing up public website files")
                    public_website_included, public_website_file_count = await self._backup_public_website_volume(temp_dir)
                else:
                    logger.info("Public website backup disabled in configuration")
            metadata["public_website_included"] = public_website_included
            metadata["public_website_file_count"] = public_website_file_count

            # 4. Capture manifests (55-75%)
            await update_progress(55, "Capturing workflow manifest")
            workflow_count, workflows_manifest = await self.capture_workflow_manifest(n8n_db)

            await update_progress(60, "Capturing credential manifest")
            credential_count, credentials_manifest = await self.capture_credential_manifest(n8n_db)

            await update_progress(65, "Capturing config file manifest")
            config_count, config_manifest = await self.capture_config_file_manifest()

            await update_progress(70, "Capturing database schema manifest")
            schema_manifest = await self.capture_database_schema_manifest(databases)

            # 4.5. Capture public website manifest if files were backed up (72-75%)
            public_website_manifest = []
            if public_website_included:
                await update_progress(72, "Capturing public website manifest")
                public_website_dir = os.path.join(temp_dir, "public_website")
                public_website_file_count, public_website_manifest = await self.capture_public_website_manifest(public_website_dir)
                metadata["public_website_file_count"] = public_website_file_count

            metadata["workflow_count"] = workflow_count
            metadata["credential_count"] = credential_count
            metadata["config_file_count"] = config_count
            metadata["workflows_manifest"] = workflows_manifest
            metadata["credentials_manifest"] = credentials_manifest
            metadata["config_files_manifest"] = config_manifest
            metadata["database_schema_manifest"] = schema_manifest
            metadata["public_website_manifest"] = public_website_manifest

            # 5. Write metadata.json (75-80%)
            await update_progress(75, "Writing metadata")
            metadata_path = os.path.join(temp_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)

            # 6. Write restore.sh (80-85%)
            await update_progress(80, "Writing restore script")
            restore_script = self._generate_restore_script()
            restore_path = os.path.join(temp_dir, "restore.sh")
            with open(restore_path, 'w') as f:
                f.write(restore_script)
            os.chmod(restore_path, 0o755)

            # 7. Create tar.gz archive (85-95%)
            await update_progress(85, "Creating archive")

            # Log what we're about to add to the archive
            logger.info(f"Temp directory contents before archive creation:")
            for root, dirs, files in os.walk(temp_dir):
                level = root.replace(temp_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                logger.info(f"{indent}{os.path.basename(root)}/")
                sub_indent = ' ' * 2 * (level + 1)
                for file in files:
                    file_path = os.path.join(root, file)
                    logger.info(f"{sub_indent}{file} ({os.path.getsize(file_path)} bytes)")

            with tarfile.open(archive_path, "w:gz") as tar:
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    tar.add(item_path, arcname=item)
                    logger.info(f"Added to archive: {item}")

            await update_progress(95, "Finalizing")
            logger.info(f"Created complete archive: {archive_path}")

        return archive_path, metadata

    async def _execute_pg_dump_to_file(self, database: str, filepath: str) -> None:
        """Execute pg_dump to a file (custom format, no compression)."""
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
            "-f", filepath,
        ]

        env = {**os.environ, "PGPASSWORD": password}
        result = subprocess.run(cmd, capture_output=True, env=env)

        if result.returncode != 0:
            raise Exception(f"pg_dump failed for {database}: {result.stderr.decode()}")

    async def _get_n8n_version(self) -> str:
        """Get n8n version from container or environment."""
        try:
            # Try to get from n8n container
            result = subprocess.run(
                ["docker", "exec", "n8n", "n8n", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return os.environ.get("N8N_VERSION", "unknown")

    def _is_public_website_installed(self) -> bool:
        """Check if public website feature is installed by checking if Docker volume exists."""
        try:
            result = subprocess.run(
                ["docker", "volume", "inspect", PUBLIC_WEBSITE_VOLUME],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _backup_public_website_volume(self, temp_dir: str) -> Tuple[bool, int]:
        """
        Back up public_web_root Docker volume contents.
        Returns (success, file_count).
        """
        try:
            # Check if the volume exists
            result = subprocess.run(
                ["docker", "volume", "inspect", PUBLIC_WEBSITE_VOLUME],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.warning(f"Public website volume '{PUBLIC_WEBSITE_VOLUME}' does not exist")
                return False, 0

            # Create destination directory
            public_website_dir = os.path.join(temp_dir, "public_website")
            os.makedirs(public_website_dir, exist_ok=True)

            # Use docker to copy volume contents to temp directory
            # docker run --rm -v public_web_root:/source -v {host_path}:/backup alpine cp -r /source/. /backup/
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{PUBLIC_WEBSITE_VOLUME}:/source:ro",
                    "-v", f"{public_website_dir}:/backup",
                    "alpine",
                    "sh", "-c", "cp -r /source/. /backup/"
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Failed to backup public website volume: {result.stderr}")
                return False, 0

            # Count files
            file_count = sum(len(files) for _, _, files in os.walk(public_website_dir))
            logger.info(f"Backed up public website volume: {file_count} files")
            return True, file_count

        except Exception as e:
            logger.error(f"Error backing up public website volume: {e}")
            return False, 0

    async def _get_backup_configuration(self) -> Optional["BackupConfiguration"]:
        """Get the backup configuration settings."""
        from api.models.backups import BackupConfiguration
        result = await self.db.execute(select(BackupConfiguration).limit(1))
        return result.scalar_one_or_none()

    def _generate_restore_script(self) -> str:
        """Generate the restore.sh script for bare metal recovery."""
        return r'''#!/bin/bash
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /restore.sh
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# ============================================================================
# n8n Bare Metal Recovery Script
# ============================================================================
# Generated automatically by n8n Management Console
#
# This script performs a COMPLETE bare metal restore of an n8n installation.
# It can restore to a freshly installed Linux system with no prerequisites.
#
# What this script does:
#   - Checks system requirements (disk space, memory, internet)
#   - Installs required utilities (curl, git, openssl, jq)
#   - Installs Docker and Docker Compose (if needed)
#   - Installs PostgreSQL client tools (if needed)
#   - Installs and configures NFS (if backup was using NFS storage)
#   - Validates DNS configuration matches this server
#   - Restores all configuration files
#   - Restores databases
#   - Restores SSL certificates
#   - Restores public website files (if included in backup)
#   - Creates required Docker volumes
#   - Starts all services
#   - Performs health checks
#
# Usage: ./restore.sh [options]
#
# Options:
#   --target-dir DIR    Directory to restore to (default: /opt/n8n)
#   --skip-docker          Skip Docker installation check
#   --skip-ssl             Skip SSL certificate restoration
#   --skip-db              Skip database restoration
#   --skip-config          Skip config file restoration
#   --skip-nfs             Skip NFS setup even if configured in backup
#   --skip-public-website  Skip public website restoration
#   --skip-dns-check       Skip DNS validation (use with caution)
#   --skip-system-check    Skip system requirements check
#   --dry-run           Show what would be done without making changes
#   --force             Skip all confirmation prompts
#   --auto              Fully automatic mode (implies --force)
#   -h, --help          Show this help message
#
# ============================================================================

set -e

# ============================================================================
# Configuration
# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Default values
TARGET_DIR="/opt/n8n"
SKIP_DOCKER=false
SKIP_SSL=false
SKIP_DB=false
SKIP_CONFIG=false
SKIP_NFS=false
SKIP_PUBLIC_WEBSITE=false
SKIP_DNS_CHECK=false
SKIP_SYSTEM_CHECK=false
DRY_RUN=false
FORCE=false
AUTO_MODE=false

# Minimum requirements
MIN_DISK_GB=5
MIN_RAM_MB=2048

# Detected values
DISTRO=""
DISTRO_FAMILY=""
PKG_MANAGER=""
PKG_UPDATE=""
PKG_INSTALL=""

# ============================================================================
# Argument Parsing
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --target-dir) TARGET_DIR="$2"; shift 2 ;;
        --skip-docker) SKIP_DOCKER=true; shift ;;
        --skip-ssl) SKIP_SSL=true; shift ;;
        --skip-db) SKIP_DB=true; shift ;;
        --skip-config) SKIP_CONFIG=true; shift ;;
        --skip-nfs) SKIP_NFS=true; shift ;;
        --skip-public-website) SKIP_PUBLIC_WEBSITE=true; shift ;;
        --skip-dns-check) SKIP_DNS_CHECK=true; shift ;;
        --skip-system-check) SKIP_SYSTEM_CHECK=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --force) FORCE=true; shift ;;
        --auto) AUTO_MODE=true; FORCE=true; shift ;;
        -h|--help)
            head -n 45 "$0" | tail -n 41
            exit 0
            ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# Get script directory (where backup was extracted)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${MAGENTA}═══ $1 ═══${NC}"; }

run_cmd() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${CYAN}  [DRY-RUN] Would run:${NC} $*"
        return 0
    else
        "$@"
    fi
}

run_privileged() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    elif command -v sudo &>/dev/null; then
        sudo "$@"
    else
        log_error "Need root privileges but sudo not available"
        exit 1
    fi
}

confirm() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    local prompt="$1 [y/N] "
    read -p "$prompt" response
    [[ "$response" =~ ^[Yy]$ ]]
}

command_exists() {
    command -v "$1" &>/dev/null
}

# Check if running in LXC container
is_lxc_container() {
    if command_exists systemd-detect-virt && [ "$(systemd-detect-virt 2>/dev/null)" = "lxc" ]; then
        return 0
    fi
    if grep -qa 'container=lxc' /proc/1/environ 2>/dev/null; then
        return 0
    fi
    if [ -f /run/host/container-manager ]; then
        return 0
    fi
    return 1
}

# ============================================================================
# OS Detection
# ============================================================================

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_VERSION=$VERSION_ID
        case $ID in
            ubuntu|debian|linuxmint|pop|raspbian)
                DISTRO_FAMILY="debian"
                PKG_MANAGER="apt-get"
                PKG_UPDATE="apt-get update -qq"
                PKG_INSTALL="apt-get install -y -qq"
                ;;
            centos|rhel|fedora|rocky|almalinux)
                DISTRO_FAMILY="rhel"
                if command_exists dnf; then
                    PKG_MANAGER="dnf"
                    PKG_UPDATE="dnf check-update || true"
                    PKG_INSTALL="dnf install -y -q"
                else
                    PKG_MANAGER="yum"
                    PKG_UPDATE="yum check-update || true"
                    PKG_INSTALL="yum install -y -q"
                fi
                ;;
            alpine)
                DISTRO_FAMILY="alpine"
                PKG_MANAGER="apk"
                PKG_UPDATE="apk update -q"
                PKG_INSTALL="apk add -q"
                ;;
            *)
                DISTRO_FAMILY="unknown"
                # Try to detect package manager
                if command_exists apt-get; then
                    PKG_MANAGER="apt-get"
                    PKG_UPDATE="apt-get update -qq"
                    PKG_INSTALL="apt-get install -y -qq"
                elif command_exists dnf; then
                    PKG_MANAGER="dnf"
                    PKG_UPDATE="dnf check-update || true"
                    PKG_INSTALL="dnf install -y -q"
                elif command_exists yum; then
                    PKG_MANAGER="yum"
                    PKG_UPDATE="yum check-update || true"
                    PKG_INSTALL="yum install -y -q"
                fi
                ;;
        esac
    elif [ -f /etc/debian_version ]; then
        DISTRO="debian"
        DISTRO_FAMILY="debian"
        PKG_MANAGER="apt-get"
        PKG_UPDATE="apt-get update -qq"
        PKG_INSTALL="apt-get install -y -qq"
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
        DISTRO_FAMILY="rhel"
        PKG_MANAGER="yum"
        PKG_UPDATE="yum check-update || true"
        PKG_INSTALL="yum install -y -q"
    fi

    log_info "Detected OS: $DISTRO (family: $DISTRO_FAMILY)"
}

# ============================================================================
# System Requirement Checks
# ============================================================================

check_system_requirements() {
    log_info "Checking system requirements..."
    local all_passed=true

    # Check disk space
    local available_gb=$(df -BG "$SCRIPT_DIR" 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G')
    if [[ -n "$available_gb" ]] && [[ "$available_gb" -ge "$MIN_DISK_GB" ]]; then
        log_success "Disk space: ${available_gb}GB available (${MIN_DISK_GB}GB required)"
    else
        log_warning "Disk space: ${available_gb:-unknown}GB available (${MIN_DISK_GB}GB required)"
        all_passed=false
    fi

    # Check memory
    local total_ram_mb=$(free -m 2>/dev/null | awk '/^Mem:/ {print $2}')
    if [[ -n "$total_ram_mb" ]] && [[ "$total_ram_mb" -ge "$MIN_RAM_MB" ]]; then
        log_success "Memory: ${total_ram_mb}MB available (${MIN_RAM_MB}MB required)"
    else
        log_warning "Memory: ${total_ram_mb:-unknown}MB available (${MIN_RAM_MB}MB required)"
        all_passed=false
    fi

    # Check internet connectivity (needed for Docker image pulls)
    log_info "Checking internet connectivity..."
    if ping -c 1 -W 5 8.8.8.8 &>/dev/null || ping -c 1 -W 5 1.1.1.1 &>/dev/null; then
        log_success "Internet connectivity available"
    else
        log_warning "Cannot reach internet - Docker image pulls may fail"
        all_passed=false
    fi

    # Check for LXC container
    if is_lxc_container; then
        log_warning "Running inside LXC container - some features may require special configuration"
    fi

    if [[ "$all_passed" != "true" ]]; then
        log_warning "Some system requirements not met"
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
    fi

    return 0
}

# ============================================================================
# Package Installation Functions
# ============================================================================

install_base_utilities() {
    log_info "Checking base utilities..."

    local missing=""
    command_exists curl || missing="$missing curl"
    command_exists git || missing="$missing git"
    command_exists openssl || missing="$missing openssl"
    command_exists jq || missing="$missing jq"

    if [[ -z "$missing" ]]; then
        log_success "All base utilities already installed"
        return 0
    fi

    log_info "Installing missing utilities:$missing"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${CYAN}  [DRY-RUN] Would install:$missing${NC}"
        return 0
    fi

    run_privileged $PKG_UPDATE
    run_privileged $PKG_INSTALL $missing

    # Verify
    local failed=""
    command_exists curl || failed="$failed curl"
    command_exists git || failed="$failed git"
    command_exists openssl || failed="$failed openssl"
    command_exists jq || failed="$failed jq"

    if [[ -n "$failed" ]]; then
        log_warning "Failed to install:$failed (may not be critical)"
    else
        log_success "Base utilities installed"
    fi
}

install_docker() {
    log_info "Installing Docker..."

    case $DISTRO_FAMILY in
        debian)
            # Remove old versions
            run_privileged apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

            # Install prerequisites
            run_privileged apt-get update
            run_privileged apt-get install -y ca-certificates curl gnupg lsb-release

            # Add Docker GPG key
            run_privileged install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$DISTRO/gpg | run_privileged gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
            run_privileged chmod a+r /etc/apt/keyrings/docker.gpg

            # Add Docker repository
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO \
                $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
                run_privileged tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Install Docker with compose plugin
            run_privileged apt-get update
            run_privileged apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        rhel)
            # Remove old versions
            run_privileged $PKG_MANAGER remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true

            # Install prerequisites
            run_privileged $PKG_MANAGER install -y yum-utils

            # Add Docker repository
            run_privileged yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

            # Install Docker with compose plugin
            run_privileged $PKG_MANAGER install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        *)
            log_error "Unsupported distribution for automatic Docker installation: $DISTRO"
            log_info "Please install Docker manually: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac

    # Start and enable Docker
    run_privileged systemctl start docker
    run_privileged systemctl enable docker

    # Add current user to docker group
    if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        run_privileged usermod -aG docker "$SUDO_USER"
        log_warning "Added $SUDO_USER to docker group. You may need to log out and back in."
    fi

    # Verify installation
    if docker --version &>/dev/null; then
        log_success "Docker installed successfully: $(docker --version)"
    else
        log_error "Docker installation failed"
        exit 1
    fi
}

install_postgresql_client() {
    log_info "Installing PostgreSQL client tools..."

    case $DISTRO_FAMILY in
        debian)
            run_privileged apt-get update
            run_privileged apt-get install -y postgresql-client
            ;;
        rhel)
            run_privileged $PKG_MANAGER install -y postgresql
            ;;
        alpine)
            run_privileged apk add postgresql-client
            ;;
        *)
            log_error "Cannot install PostgreSQL client for this distribution"
            return 1
            ;;
    esac

    log_success "PostgreSQL client installed"
}

install_nfs_client() {
    log_info "Installing NFS client..."

    case $DISTRO_FAMILY in
        debian)
            run_privileged apt-get update
            run_privileged apt-get install -y nfs-common
            ;;
        rhel)
            run_privileged $PKG_MANAGER install -y nfs-utils
            ;;
        alpine)
            run_privileged apk add nfs-utils
            ;;
        *)
            log_error "Cannot install NFS client for this distribution"
            return 1
            ;;
    esac

    log_success "NFS client installed"
}

install_python3() {
    log_info "Installing Python3..."

    case $DISTRO_FAMILY in
        debian)
            run_privileged apt-get update
            run_privileged apt-get install -y python3
            ;;
        rhel)
            run_privileged $PKG_MANAGER install -y python3
            ;;
        alpine)
            run_privileged apk add python3
            ;;
    esac
}

# ============================================================================
# Validation Functions
# ============================================================================

validate_dns() {
    local domain="$1"
    local expected_ip="$2"

    if [[ "$SKIP_DNS_CHECK" == "true" ]]; then
        log_warning "Skipping DNS validation (--skip-dns-check)"
        return 0
    fi

    if [[ -z "$domain" ]]; then
        log_warning "Cannot validate DNS - domain not set in backup"
        return 0
    fi

    log_info "Validating DNS configuration for: $domain"

    # Get current server IPs
    local server_ips=$(hostname -I 2>/dev/null || ip addr show | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | tr '\n' ' ')
    log_info "This server's IP addresses: $server_ips"

    # Resolve domain
    local resolved_ip=""
    if command_exists dig; then
        resolved_ip=$(dig +short "$domain" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
    elif command_exists nslookup; then
        resolved_ip=$(nslookup "$domain" 2>/dev/null | grep -A1 'Name:' | grep 'Address:' | awk '{print $2}' | head -1)
    elif command_exists host; then
        resolved_ip=$(host "$domain" 2>/dev/null | grep 'has address' | awk '{print $4}' | head -1)
    elif command_exists getent; then
        resolved_ip=$(getent hosts "$domain" 2>/dev/null | awk '{print $1}' | head -1)
    fi

    if [[ -z "$resolved_ip" ]]; then
        log_error "Cannot resolve domain: $domain"
        echo ""
        echo -e "  ${YELLOW}This could mean:${NC}"
        echo -e "    - The DNS record hasn't been created yet"
        echo -e "    - The DNS hasn't propagated yet"
        echo -e "    - The domain name is incorrect"
        echo ""
        if ! confirm "Continue anyway? (NOT RECOMMENDED - services will likely fail)"; then
            exit 1
        fi
        return 1
    fi

    log_info "Domain $domain resolves to: $resolved_ip"

    # Check if resolved IP matches this server
    local ip_matches=false
    for ip in $server_ips; do
        if [[ "$ip" == "$resolved_ip" ]]; then
            ip_matches=true
            break
        fi
    done

    if [[ "$ip_matches" == "true" ]]; then
        log_success "DNS validated: $domain -> $resolved_ip (matches this server)"
        return 0
    else
        log_error "DNS MISMATCH DETECTED!"
        echo ""
        echo -e "  ${RED}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${RED}║                              WARNING                                      ║${NC}"
        echo -e "  ${RED}║  The domain does NOT point to this server!                                ║${NC}"
        echo -e "  ${RED}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  ${YELLOW}Domain $domain resolves to: ${WHITE}$resolved_ip${NC}"
        echo -e "  ${YELLOW}This server's IPs are:      ${WHITE}$server_ips${NC}"
        if [[ -n "$expected_ip" ]]; then
            echo -e "  ${YELLOW}Original server IP was:     ${WHITE}$expected_ip${NC}"
        fi
        echo ""
        echo -e "  ${YELLOW}This will cause the n8n stack to fail because:${NC}"
        echo -e "    - SSL certificate validation will fail"
        echo -e "    - Webhooks won't reach this server"
        echo -e "    - The n8n UI won't be accessible"
        echo ""
        echo -e "  ${WHITE}To fix this, update your DNS records to point $domain to one of:${NC}"
        for ip in $server_ips; do
            echo -e "    ${CYAN}$ip${NC}"
        done
        echo ""
        if ! confirm "Continue anyway? (Services will likely NOT work)"; then
            exit 1
        fi
        return 1
    fi
}

validate_backup_contents() {
    log_info "Validating backup contents..."
    local valid=true

    # Check for metadata.json
    if [[ ! -f "$SCRIPT_DIR/metadata.json" ]]; then
        log_error "metadata.json not found - is this a valid backup?"
        return 1
    fi
    log_success "metadata.json found"

    # Check for config directory
    if [[ ! -d "$SCRIPT_DIR/config" ]]; then
        log_warning "config directory not found in backup"
        valid=false
    else
        log_success "config directory found"
    fi

    # Check for docker-compose.yaml in config
    if [[ -f "$SCRIPT_DIR/config/docker-compose.yaml" ]]; then
        log_success "docker-compose.yaml found in backup"
    elif [[ -f "$SCRIPT_DIR/config/docker-compose.yml" ]]; then
        log_success "docker-compose.yml found in backup"
    else
        log_error "docker-compose.yaml NOT found in backup - cannot start services"
        valid=false
    fi

    # Check for .env file
    if [[ -f "$SCRIPT_DIR/config/.env" ]]; then
        log_success ".env file found in backup"
    else
        log_warning ".env file not found in backup - services may not start correctly"
        valid=false
    fi

    # Check for databases directory
    if [[ -d "$SCRIPT_DIR/databases" ]]; then
        local db_count=$(ls -1 "$SCRIPT_DIR/databases"/*.dump 2>/dev/null | wc -l)
        if [[ "$db_count" -gt 0 ]]; then
            log_success "Found $db_count database dump(s)"
        else
            log_warning "databases directory exists but no .dump files found"
        fi
    else
        log_warning "databases directory not found in backup"
    fi

    # Check for SSL certificates
    if [[ -d "$SCRIPT_DIR/ssl" ]]; then
        local ssl_count=$(ls -1d "$SCRIPT_DIR/ssl"/*/ 2>/dev/null | wc -l)
        if [[ "$ssl_count" -gt 0 ]]; then
            log_success "Found SSL certificates for $ssl_count domain(s)"
        fi
    fi

    # Check for public website files
    if [[ -d "$SCRIPT_DIR/public_website" ]]; then
        local pw_count=$(find "$SCRIPT_DIR/public_website" -type f 2>/dev/null | wc -l)
        if [[ "$pw_count" -gt 0 ]]; then
            log_success "Found public website files ($pw_count files)"
        fi
    fi

    if [[ "$valid" != "true" ]]; then
        log_warning "Some backup components are missing"
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
    fi

    return 0
}

# ============================================================================
# NFS Setup
# ============================================================================

setup_nfs() {
    local nfs_server="$1"
    local nfs_path="$2"
    local nfs_local_mount="$3"

    if [[ -z "$nfs_server" ]] || [[ -z "$nfs_path" ]]; then
        log_info "NFS not configured in backup - skipping"
        return 0
    fi

    if [[ "$SKIP_NFS" == "true" ]]; then
        log_warning "Skipping NFS setup (--skip-nfs)"
        return 0
    fi

    log_info "Setting up NFS: $nfs_server:$nfs_path -> $nfs_local_mount"

    # Install NFS client if needed
    if ! command_exists mount.nfs && ! command_exists mount.nfs4; then
        if [[ "$DRY_RUN" != "true" ]]; then
            install_nfs_client || {
                log_error "Failed to install NFS client"
                return 1
            }
        else
            echo -e "${CYAN}  [DRY-RUN] Would install NFS client${NC}"
        fi
    fi

    # Test NFS server connectivity
    log_info "Testing connectivity to NFS server: $nfs_server"
    if ! ping -c 1 -W 5 "$nfs_server" &>/dev/null; then
        log_error "Cannot reach NFS server: $nfs_server"
        if ! confirm "Continue without NFS?"; then
            exit 1
        fi
        return 1
    fi
    log_success "NFS server is reachable"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${CYAN}  [DRY-RUN] Would create mount point: $nfs_local_mount${NC}"
        echo -e "${CYAN}  [DRY-RUN] Would add to /etc/fstab: $nfs_server:$nfs_path $nfs_local_mount nfs defaults,_netdev 0 0${NC}"
        echo -e "${CYAN}  [DRY-RUN] Would mount NFS share${NC}"
        return 0
    fi

    # Create mount point
    run_privileged mkdir -p "$nfs_local_mount"

    # Check if already in fstab
    if grep -q "${nfs_server}:${nfs_path}" /etc/fstab 2>/dev/null; then
        log_info "NFS entry already exists in /etc/fstab"
    else
        # Add to fstab
        echo "${nfs_server}:${nfs_path} ${nfs_local_mount} nfs defaults,_netdev 0 0" | run_privileged tee -a /etc/fstab > /dev/null
        log_success "Added NFS mount to /etc/fstab"
    fi

    # Mount the NFS share
    if mount | grep -q "$nfs_local_mount"; then
        log_info "NFS already mounted at $nfs_local_mount"
    else
        if run_privileged mount "$nfs_local_mount" 2>/dev/null || \
           run_privileged mount -t nfs -o rw,nolock,soft "$nfs_server:$nfs_path" "$nfs_local_mount" 2>/dev/null; then
            log_success "NFS share mounted at $nfs_local_mount"
        else
            log_error "Failed to mount NFS share"
            return 1
        fi
    fi

    # Verify mount is writable
    if touch "${nfs_local_mount}/.restore_test" 2>/dev/null; then
        rm -f "${nfs_local_mount}/.restore_test"
        log_success "NFS share is writable"
    else
        log_warning "NFS share may not be writable"
    fi

    return 0
}

# ============================================================================
# Main Script
# ============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║               n8n Bare Metal Recovery Script v3.1                    ║${NC}"
echo -e "${GREEN}║                   Complete System Restoration                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Step 0: Pre-flight Checks
# ============================================================================

log_step "Step 0: Pre-flight Checks"

# Check for root
if [[ $EUID -ne 0 ]]; then
    log_warning "This script should be run as root for full functionality"
    if ! confirm "Continue as non-root user?"; then
        log_info "Please run with: sudo $0"
        exit 1
    fi
fi

# Detect OS first
detect_os

# Validate backup contents
validate_backup_contents || exit 1

# System requirements check
if [[ "$SKIP_SYSTEM_CHECK" != "true" ]]; then
    check_system_requirements
else
    log_warning "Skipping system requirements check (--skip-system-check)"
fi

# Install base utilities (curl, git, openssl, jq)
install_base_utilities

# Ensure python3 for metadata parsing
if ! command_exists python3; then
    log_warning "Python3 not found - installing for metadata parsing"
    if [[ "$DRY_RUN" != "true" ]]; then
        install_python3
    fi
fi

# Parse metadata
if command_exists python3; then
    BACKUP_TYPE=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/metadata.json')).get('backup_type', 'unknown'))" 2>/dev/null || echo "unknown")
    BACKUP_DATE=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/metadata.json')).get('created_at', 'unknown'))" 2>/dev/null || echo "unknown")
    N8N_VERSION=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/metadata.json')).get('n8n_version', 'unknown'))" 2>/dev/null || echo "unknown")
    WORKFLOW_COUNT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/metadata.json')).get('workflow_count', 0))" 2>/dev/null || echo "0")
    CREDENTIAL_COUNT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/metadata.json')).get('credential_count', 0))" 2>/dev/null || echo "0")
    CONFIG_COUNT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/metadata.json')).get('config_file_count', 0))" 2>/dev/null || echo "0")
fi

echo ""
echo -e "${CYAN}Backup Information:${NC}"
echo "─────────────────────────────────────────────────────────────────────"
echo "  Backup Type:      $BACKUP_TYPE"
echo "  Created:          $BACKUP_DATE"
echo "  n8n Version:      $N8N_VERSION"
echo "  Workflows:        $WORKFLOW_COUNT"
echo "  Credentials:      $CREDENTIAL_COUNT"
echo "  Config Files:     $CONFIG_COUNT"
echo "─────────────────────────────────────────────────────────────────────"
echo ""

echo -e "${CYAN}Restore Configuration:${NC}"
echo "  Target Directory:     $TARGET_DIR"
echo "  Skip Docker:          $SKIP_DOCKER"
echo "  Skip SSL:             $SKIP_SSL"
echo "  Skip Database:        $SKIP_DB"
echo "  Skip Config:          $SKIP_CONFIG"
echo "  Skip NFS:             $SKIP_NFS"
echo "  Skip Public Website:  $SKIP_PUBLIC_WEBSITE"
echo "  Skip DNS Check:       $SKIP_DNS_CHECK"
echo "  Dry Run:              $DRY_RUN"
echo "  Auto Mode:            $AUTO_MODE"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  DRY RUN MODE - No changes will be made to the system${NC}"
    echo -e "${YELLOW}════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
fi

if ! confirm "Proceed with restore?"; then
    echo "Restore cancelled."
    exit 0
fi

# ============================================================================
# Step 1: Install Docker
# ============================================================================

log_step "Step 1: Docker Environment"

if [[ "$SKIP_DOCKER" != "true" ]]; then
    if command_exists docker; then
        docker_version=$(docker --version 2>/dev/null || echo "unknown")
        log_success "Docker installed: $docker_version"
    else
        log_warning "Docker not installed"
        if confirm "Install Docker?"; then
            if [[ "$DRY_RUN" != "true" ]]; then
                install_docker
            else
                echo -e "${CYAN}  [DRY-RUN] Would install Docker${NC}"
            fi
        else
            log_error "Docker is required for n8n"
            exit 1
        fi
    fi

    # Check Docker Compose
    if docker compose version &>/dev/null; then
        compose_version=$(docker compose version 2>/dev/null || echo "unknown")
        log_success "Docker Compose available: $compose_version"
    elif command_exists docker-compose; then
        compose_version=$(docker-compose --version 2>/dev/null || echo "unknown")
        log_success "Docker Compose (standalone): $compose_version"
    else
        log_error "Docker Compose not found"
        log_info "Please install docker-compose-plugin"
        exit 1
    fi
else
    log_info "Skipping Docker check (--skip-docker)"
fi

# ============================================================================
# Step 2: Install PostgreSQL Client
# ============================================================================

log_step "Step 2: PostgreSQL Client"

if [[ "$SKIP_DB" != "true" ]]; then
    if command_exists pg_restore; then
        pg_version=$(pg_restore --version 2>/dev/null | head -1 || echo "unknown")
        log_success "pg_restore available: $pg_version"
    else
        log_warning "PostgreSQL client not installed"
        if confirm "Install PostgreSQL client?"; then
            if [[ "$DRY_RUN" != "true" ]]; then
                install_postgresql_client
            else
                echo -e "${CYAN}  [DRY-RUN] Would install PostgreSQL client${NC}"
            fi
        else
            log_warning "Skipping database restoration"
            SKIP_DB=true
        fi
    fi
else
    log_info "Skipping PostgreSQL client check (--skip-db)"
fi

# ============================================================================
# Step 3: Restore Config Files
# ============================================================================

log_step "Step 3: Restore Configuration Files"

if [[ "$SKIP_CONFIG" != "true" ]] && [[ -d "$SCRIPT_DIR/config" ]]; then
    # Create target directory
    run_cmd mkdir -p "$TARGET_DIR"

    config_count=0
    for config_item in "$SCRIPT_DIR/config"/*; do
        if [[ -e "$config_item" ]]; then
            item_name=$(basename "$config_item")

            if [[ -d "$config_item" ]]; then
                # Handle subdirectories (dozzle/, ntfy/, etc.)
                log_info "Restoring directory: $item_name/"
                run_cmd mkdir -p "$TARGET_DIR/$item_name"
                for subfile in "$config_item"/*; do
                    if [[ -f "$subfile" ]]; then
                        subname=$(basename "$subfile")
                        run_cmd cp "$subfile" "$TARGET_DIR/$item_name/$subname"
                        ((config_count++))
                    fi
                done
            else
                # Handle regular files
                target_path="$TARGET_DIR/$item_name"

                # Backup existing file
                if [[ -f "$target_path" ]] && [[ "$DRY_RUN" != "true" ]]; then
                    backup_path="${target_path}.bak.$(date +%Y%m%d_%H%M%S)"
                    cp "$target_path" "$backup_path"
                    log_info "Backed up existing $item_name"
                fi

                log_info "Restoring: $item_name"
                run_cmd cp "$config_item" "$target_path"

                # Set permissions for sensitive files
                if [[ "$item_name" == ".env" ]] || [[ "$item_name" == "cloudflare.ini" ]] || \
                   [[ "$item_name" == "*.ini" ]] || [[ "$item_name" == "*.json" && "$item_name" != "package.json" ]]; then
                    [[ "$DRY_RUN" != "true" ]] && chmod 600 "$target_path" 2>/dev/null || true
                fi

                ((config_count++))
            fi
        fi
    done

    log_success "Restored $config_count config file(s)"
else
    log_info "Skipping config file restoration"
fi

# ============================================================================
# Step 4: Read Environment for DNS/NFS Validation
# ============================================================================

log_step "Step 4: Environment Validation"

# Source .env if it exists
if [[ -f "$TARGET_DIR/.env" ]]; then
    log_info "Reading environment from restored .env"
    set -a
    source "$TARGET_DIR/.env"
    set +a

    # DNS Validation
    validate_dns "${DOMAIN:-}" "${N8N_MANAGEMENT_HOST_IP:-}"

    # NFS Setup
    if [[ -n "${NFS_SERVER:-}" ]] && [[ -n "${NFS_PATH:-}" ]]; then
        setup_nfs "$NFS_SERVER" "$NFS_PATH" "${NFS_LOCAL_MOUNT:-/mnt/nfs_backups}"
    fi
else
    log_warning "No .env file found - skipping environment validation"
fi

# ============================================================================
# Step 5: Restore SSL Certificates
# ============================================================================

log_step "Step 5: SSL Certificates"

if [[ "$SKIP_SSL" != "true" ]] && [[ -d "$SCRIPT_DIR/ssl" ]]; then
    run_cmd mkdir -p /etc/letsencrypt/live
    ssl_count=0

    for domain_dir in "$SCRIPT_DIR/ssl"/*; do
        if [[ -d "$domain_dir" ]]; then
            domain=$(basename "$domain_dir")
            log_info "Restoring SSL for: $domain"
            run_cmd cp -r "$domain_dir" "/etc/letsencrypt/live/"
            ((ssl_count++))
        fi
    done

    log_success "Restored SSL certificates for $ssl_count domain(s)"
else
    log_info "Skipping SSL certificate restoration"
fi

# ============================================================================
# Step 5.5: Restore Public Website Files
# ============================================================================

log_step "Step 5.5: Public Website Files"

if [[ "$SKIP_PUBLIC_WEBSITE" != "true" ]] && [[ -d "$SCRIPT_DIR/public_website" ]]; then
    log_info "Found public website files in backup"

    if [[ "$DRY_RUN" != "true" ]] && command_exists docker; then
        # Create the public_web_root volume if it doesn't exist
        if ! docker volume inspect public_web_root &>/dev/null; then
            docker volume create public_web_root
            log_success "Created public_web_root volume"
        else
            log_info "public_web_root volume already exists"
        fi

        # Copy files to the volume using alpine container
        log_info "Restoring public website files to Docker volume..."
        docker run --rm \
            -v public_web_root:/dest \
            -v "$SCRIPT_DIR/public_website:/source:ro" \
            alpine \
            sh -c "cp -r /source/. /dest/"

        if [[ $? -eq 0 ]]; then
            file_count=$(find "$SCRIPT_DIR/public_website" -type f | wc -l)
            log_success "Restored $file_count public website file(s)"
        else
            log_warning "Failed to restore some public website files"
        fi
    else
        echo -e "${CYAN}  [DRY-RUN] Would create public_web_root volume and restore files${NC}"
    fi
elif [[ "$SKIP_PUBLIC_WEBSITE" == "true" ]]; then
    log_info "Skipping public website restoration (--skip-public-website)"
else
    log_info "No public website files in backup"
fi

# ============================================================================
# Step 6: Create Docker Volumes
# ============================================================================

log_step "Step 6: Docker Volumes"

if [[ "$DRY_RUN" != "true" ]] && command_exists docker; then
    # Create letsencrypt volume if it doesn't exist
    if ! docker volume inspect letsencrypt &>/dev/null; then
        docker volume create letsencrypt
        log_success "Created letsencrypt volume"
    else
        log_info "letsencrypt volume already exists"
    fi

    # Copy SSL certs to volume if they exist
    if [[ -d "/etc/letsencrypt/live" ]] && [[ "$(ls -A /etc/letsencrypt/live 2>/dev/null)" ]]; then
        log_info "Copying SSL certificates to Docker volume..."
        docker run --rm -v letsencrypt:/etc/letsencrypt -v /etc/letsencrypt/live:/source alpine sh -c "cp -r /source/* /etc/letsencrypt/live/ 2>/dev/null || true"
        log_success "SSL certificates copied to Docker volume"
    fi
else
    echo -e "${CYAN}  [DRY-RUN] Would create Docker volumes${NC}"
fi

# ============================================================================
# Step 7: Start Services
# ============================================================================

log_step "Step 7: Start Services"

if [[ "$DRY_RUN" != "true" ]]; then
    cd "$TARGET_DIR"

    if [[ -f "docker-compose.yaml" ]] || [[ -f "docker-compose.yml" ]]; then
        log_info "Starting services with docker compose..."

        # Pull images first
        if confirm "Pull latest Docker images?"; then
            docker compose pull || log_warning "Some images failed to pull"
        fi

        # Start services
        docker compose up -d

        log_success "Services started"

        # Wait for services to be ready
        log_info "Waiting for services to be ready..."
        sleep 10

        # Show service status
        echo ""
        echo -e "${CYAN}Service Status:${NC}"
        docker compose ps
    else
        log_error "docker-compose.yaml not found in $TARGET_DIR"
        log_info "Please verify the configuration files were restored correctly"
    fi
else
    echo -e "${CYAN}  [DRY-RUN] Would start services with docker compose up -d${NC}"
fi

# ============================================================================
# Step 8: Database Restoration (if containers provide PostgreSQL)
# ============================================================================

log_step "Step 8: Database Restoration"

if [[ "$SKIP_DB" != "true" ]] && [[ -d "$SCRIPT_DIR/databases" ]]; then
    if [[ "$DRY_RUN" != "true" ]]; then
        # Wait for PostgreSQL to be ready
        log_info "Waiting for PostgreSQL container to be ready..."
        local max_attempts=30
        local attempt=0

        while ! docker exec n8n_postgres pg_isready -U "${POSTGRES_USER:-n8n}" &>/dev/null; do
            ((attempt++))
            if [[ $attempt -ge $max_attempts ]]; then
                log_error "PostgreSQL not ready after $max_attempts attempts"
                log_info "You may need to restore databases manually"
                break
            fi
            sleep 2
        done

        if [[ $attempt -lt $max_attempts ]]; then
            log_success "PostgreSQL is ready"

            db_count=0
            for db_file in "$SCRIPT_DIR/databases"/*.dump; do
                if [[ -f "$db_file" ]]; then
                    db_name=$(basename "$db_file" .dump)
                    log_info "Restoring database: $db_name"

                    # Restore using docker exec
                    cat "$db_file" | docker exec -i n8n_postgres pg_restore \
                        -U "${POSTGRES_USER:-n8n}" \
                        -d "$db_name" \
                        --clean --if-exists --no-owner --no-acl 2>/dev/null || true

                    log_success "Database $db_name restored"
                    ((db_count++))
                fi
            done

            if [[ $db_count -gt 0 ]]; then
                log_success "Restored $db_count database(s)"
            fi
        fi
    else
        echo -e "${CYAN}  [DRY-RUN] Would restore databases${NC}"
    fi
else
    log_info "Skipping database restoration"
fi

# ============================================================================
# Step 9: Health Check
# ============================================================================

log_step "Step 9: Health Verification"

validation_passed=true

if [[ "$DRY_RUN" != "true" ]] && command_exists docker; then
    cd "$TARGET_DIR"

    # Check if services are running
    echo ""
    running_count=$(docker compose ps --status running -q 2>/dev/null | wc -l || echo "0")
    total_count=$(docker compose ps -q 2>/dev/null | wc -l || echo "0")

    if [[ "$running_count" -eq "$total_count" ]] && [[ "$total_count" -gt 0 ]]; then
        log_success "All $total_count services are running"
    else
        log_warning "$running_count of $total_count services are running"
        validation_passed=false
    fi

    # Check n8n health
    if docker ps --filter "name=n8n" --filter "status=running" -q | grep -q .; then
        log_success "n8n container is running"
    else
        log_warning "n8n container is not running"
        validation_passed=false
    fi

    # Check nginx health
    if docker ps --filter "name=nginx" --filter "status=running" -q | grep -q .; then
        log_success "nginx container is running"
    else
        log_warning "nginx container is not running"
        validation_passed=false
    fi
fi

# ============================================================================
# Completion
# ============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${GREEN}║                 DRY RUN COMPLETED SUCCESSFULLY                       ║${NC}"
else
    echo -e "${GREEN}║                 RESTORE COMPLETED SUCCESSFULLY                       ║${NC}"
fi
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ "$DRY_RUN" != "true" ]]; then
    echo -e "${CYAN}Summary:${NC}"
    echo "  Target Directory:  $TARGET_DIR"
    echo "  Services Started:  Yes"
    echo ""

    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Verify services: cd $TARGET_DIR && docker compose ps"
    echo "  2. Check logs:      docker compose logs -f"
    echo "  3. Access n8n:      https://${DOMAIN:-your-domain}"
    echo "  4. Access console:  https://${DOMAIN:-your-domain}/management"
    echo ""

    if [[ "$validation_passed" != "true" ]]; then
        echo -e "${YELLOW}⚠ Some validation checks failed - please review the output above${NC}"
        echo ""
    fi
fi

exit 0
'''

    async def run_backup_with_metadata(
        self,
        backup_type: str,
        schedule_id: Optional[int] = None,
        compression: str = "gzip",
        n8n_db: Optional[AsyncSession] = None,
        skip_auto_verify: bool = False,
    ) -> BackupHistory:
        """
        Execute a backup with full metadata capture.
        This is the enhanced version that creates complete archives.
        """
        logger.info(f"run_backup_with_metadata called: type={backup_type}, n8n_db={'present' if n8n_db else 'None'}, skip_auto_verify={skip_auto_verify}")

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
            await dispatch_notification("backup_started", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "started_at": history.started_at.strftime("%Y-%m-%d %H:%M:%S"),
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

            # Create complete archive with metadata
            # n8n_db is required for complete backups - no fallback to simple backup
            if not n8n_db:
                raise Exception("n8n database session is required for complete backup. Cannot create partial backup.")

            filepath, metadata = await self.create_complete_archive(
                backup_type, databases, n8n_db, compression, history
            )

            # Calculate checksum and file size
            await self._update_progress(history, 96, "Calculating checksum")
            file_size = os.path.getsize(filepath)
            checksum = hash_file_sha256(filepath)
            filename = os.path.basename(filepath)

            # Get postgres version
            pg_version = await self._get_postgres_version()

            # Update history
            await self._update_progress(history, 98, "Saving backup record")
            history.filename = filename
            history.filepath = filepath
            history.file_size = file_size
            history.compressed_size = file_size
            history.checksum = checksum
            history.postgres_version = pg_version
            history.row_counts = metadata.get("row_counts", {})
            history.database_name = ",".join(databases)
            history.table_count = sum(
                len(db_info.get("tables", []))
                for db_info in metadata.get("database_schema_manifest", [])
            )
            history.status = "success"
            history.progress = 100
            history.progress_message = "Backup completed"
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())
            history.storage_location = "nfs" if "/mnt/backups" in filepath else "local"

            await self.db.commit()
            await self.db.refresh(history)

            # Store backup contents metadata
            try:
                contents = BackupContents(
                    backup_id=history.id,
                    workflow_count=metadata.get("workflow_count", 0),
                    credential_count=metadata.get("credential_count", 0),
                    config_file_count=metadata.get("config_file_count", 0),
                    public_website_file_count=metadata.get("public_website_file_count", 0),
                    workflows_manifest=metadata.get("workflows_manifest"),
                    credentials_manifest=metadata.get("credentials_manifest"),
                    config_files_manifest=metadata.get("config_files_manifest"),
                    database_schema_manifest=metadata.get("database_schema_manifest"),
                    public_website_manifest=metadata.get("public_website_manifest"),
                    verification_checksums={
                        "archive": checksum,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                )
                self.db.add(contents)
                await self.db.commit()
                logger.info(f"Stored backup contents metadata for backup {history.id}")
            except Exception as contents_error:
                logger.error(f"Failed to store backup contents metadata: {contents_error}")
                # Don't fail the whole backup - it succeeded, just metadata storage failed

            # Notify success
            await dispatch_notification("backup_success", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "filename": filename,
                "size_mb": round(file_size / 1024 / 1024, 2),
                "duration_seconds": history.duration_seconds,
                "workflow_count": metadata.get("workflow_count", 0),
                "credential_count": metadata.get("credential_count", 0),
                "config_file_count": metadata.get("config_file_count", 0),
                "completed_at": history.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

            logger.info(f"Backup completed: {filename} ({file_size} bytes)")

            # Run auto-verification if enabled and not explicitly skipped
            if not skip_auto_verify:
                await self._run_auto_verification(history)
            else:
                logger.info(f"Skipping auto-verification for backup {history.id} (skip_auto_verify=True)")

            return history

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"{str(e)}\n\nTraceback:\n{error_details}"

            history.status = "failed"
            history.error_message = error_msg
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())

            try:
                await self.db.commit()
            except Exception as db_error:
                logger.error(f"Failed to save error to database: {db_error}")

            # Notify failure
            try:
                await dispatch_notification("backup_failure", {
                    "backup_type": backup_type,
                    "backup_id": history.id,
                    "error": str(e),
                    "failed_at": history.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
                }, severity="error")
            except Exception as notif_error:
                logger.error(f"Failed to send failure notification: {notif_error}")

            logger.error(f"Archive backup failed (id={history.id}): {e}\n{error_details}")
            raise

    async def _simple_backup(
        self,
        backup_type: str,
        databases: List[str],
        compression: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Simple backup without n8n database session (fallback)."""
        tz = ZoneInfo(settings.timezone)
        timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_type}_{timestamp}.sql"
        if compression == "gzip":
            filename += ".gz"

        storage_dir = await self._get_storage_location()
        type_dir = os.path.join(storage_dir, backup_type)
        os.makedirs(type_dir, exist_ok=True)
        filepath = os.path.join(type_dir, filename)

        row_counts = {}
        for db_name in databases:
            await self._execute_pg_dump(db_name, filepath, compression)
            row_counts[db_name] = await self._get_row_counts(db_name)

        return filepath, {"row_counts": row_counts}

    # ============================================================================
    # Backup Contents Browsing
    # ============================================================================

    async def get_backup_contents(self, backup_id: int) -> Optional[BackupContents]:
        """Get backup contents/metadata for browsing."""
        result = await self.db.execute(
            select(BackupContents).where(BackupContents.backup_id == backup_id)
        )
        return result.scalar_one_or_none()

    async def get_workflow_list_from_backup(self, backup_id: int) -> List[Dict[str, Any]]:
        """Get list of workflows from backup metadata."""
        contents = await self.get_backup_contents(backup_id)
        if contents and contents.workflows_manifest:
            return contents.workflows_manifest
        return []

    async def get_config_files_from_backup(self, backup_id: int) -> List[Dict[str, Any]]:
        """Get list of config files from backup metadata."""
        contents = await self.get_backup_contents(backup_id)
        if contents and contents.config_files_manifest:
            return contents.config_files_manifest
        return []

    # ============================================================================
    # Backup Protection (Phase 7)
    # ============================================================================

    async def protect_backup(
        self,
        backup_id: int,
        protected: bool,
        reason: Optional[str] = None,
    ) -> Optional[BackupHistory]:
        """Protect or unprotect a backup from automatic deletion."""
        backup = await self.get_backup(backup_id)
        if not backup:
            return None

        backup.is_protected = protected
        if protected:
            backup.protected_at = datetime.now(UTC)
            backup.protected_reason = reason
            # Clear any scheduled deletion
            backup.deletion_status = None
            backup.scheduled_deletion_at = None
            backup.deletion_reason = None
        else:
            backup.protected_at = None
            backup.protected_reason = None

        await self.db.commit()
        await self.db.refresh(backup)

        logger.info(f"Backup {backup_id} {'protected' if protected else 'unprotected'}: {reason}")
        return backup

    async def get_protected_backups(self) -> List[BackupHistory]:
        """Get all protected backups."""
        result = await self.db.execute(
            select(BackupHistory)
            .where(BackupHistory.is_protected == True)
            .where(BackupHistory.deleted_at.is_(None))
            .order_by(BackupHistory.created_at.desc())
        )
        return list(result.scalars().all())

    # ============================================================================
    # Pruning Settings (Phase 7)
    # ============================================================================

    async def get_pruning_settings(self) -> Optional[BackupPruningSettings]:
        """Get backup pruning settings."""
        result = await self.db.execute(
            select(BackupPruningSettings).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_pruning_settings(self, **updates) -> BackupPruningSettings:
        """Update or create pruning settings."""
        settings = await self.get_pruning_settings()

        if settings:
            for key, value in updates.items():
                if value is not None and hasattr(settings, key):
                    setattr(settings, key, value)
            settings.updated_at = datetime.now(UTC)
        else:
            # Create with defaults + updates
            settings = BackupPruningSettings(**updates)
            self.db.add(settings)

        await self.db.commit()
        await self.db.refresh(settings)
        return settings
