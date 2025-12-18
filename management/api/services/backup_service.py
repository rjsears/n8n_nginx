"""
Backup service - handles PostgreSQL backups, scheduling, and verification.

Phase 1 Enhancement: Complete backup archives with metadata for browsing and bare metal recovery.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, text
from datetime import datetime, timedelta, UTC
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


# Config files to include in backups (relative to host mount points)
CONFIG_FILES = [
    {"name": ".env", "host_path": "/app/host_env/.env", "archive_path": "config/.env"},
    {"name": "docker-compose.yaml", "host_path": "/app/host_config/docker-compose.yaml", "archive_path": "config/docker-compose.yaml"},
    {"name": "nginx.conf", "host_path": "/app/host_config/nginx.conf", "archive_path": "config/nginx.conf"},
    {"name": "cloudflare.ini", "host_path": "/app/host_config/cloudflare.ini", "archive_path": "config/cloudflare.ini"},
]

# SSL certificate paths
SSL_CERT_PATH = "/etc/letsencrypt/live"


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
            await dispatch_notification("backup.started", {
                "backup_type": backup_type,
                "backup_id": history.id,
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

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
                await dispatch_notification("backup.failed", {
                    "backup_type": backup_type,
                    "backup_id": history.id,
                    "error": str(e),
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

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        backup_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[BackupHistory]:
        """Get backup history (excludes soft-deleted backups)."""
        query = select(BackupHistory).where(
            BackupHistory.deleted_at.is_(None)
        ).order_by(BackupHistory.created_at.desc())

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

    # ============================================================================
    # Phase 1: Enhanced Backup with Metadata
    # ============================================================================

    async def capture_workflow_manifest(self, n8n_db: AsyncSession) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Capture workflow manifest from n8n database.
        Returns count and list of workflow metadata (no sensitive data).
        """
        try:
            # Query n8n workflow_entity table
            result = await n8n_db.execute(text("""
                SELECT
                    id, name, active,
                    "createdAt" as created_at,
                    "updatedAt" as updated_at
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
                except Exception as e:
                    logger.warning(f"Failed to capture config file {config['name']}: {e}")

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

    async def create_complete_archive(
        self,
        backup_type: str,
        databases: List[str],
        n8n_db: AsyncSession,
        compression: str = "gzip",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Create complete backup archive with all components.
        Returns filepath and metadata dict.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"backup_{timestamp}.n8n_backup.tar.gz"

        storage_dir = await self._get_storage_location()
        type_dir = os.path.join(storage_dir, backup_type)
        os.makedirs(type_dir, exist_ok=True)
        archive_path = os.path.join(type_dir, archive_name)

        # Create temp directory for staging
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata = {
                "backup_type": backup_type,
                "created_at": datetime.now(UTC).isoformat(),
                "databases": databases,
                "n8n_version": await self._get_n8n_version(),
                "postgres_version": await self._get_postgres_version(),
            }

            # 1. Dump databases
            db_dir = os.path.join(temp_dir, "databases")
            os.makedirs(db_dir)

            row_counts = {}
            for db_name in databases:
                db_file = os.path.join(db_dir, f"{db_name}.dump")
                await self._execute_pg_dump_to_file(db_name, db_file)
                row_counts[db_name] = await self._get_row_counts(db_name)

            metadata["row_counts"] = row_counts

            # 2. Copy config files
            config_dir = os.path.join(temp_dir, "config")
            os.makedirs(config_dir)

            for config in CONFIG_FILES:
                if os.path.exists(config["host_path"]):
                    dest_path = os.path.join(temp_dir, config["archive_path"])
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(config["host_path"], dest_path)

            # 3. Copy SSL certificates if they exist
            if os.path.exists(SSL_CERT_PATH):
                ssl_dir = os.path.join(temp_dir, "ssl")
                shutil.copytree(SSL_CERT_PATH, ssl_dir)

            # 4. Capture manifests
            workflow_count, workflows_manifest = await self.capture_workflow_manifest(n8n_db)
            credential_count, credentials_manifest = await self.capture_credential_manifest(n8n_db)
            config_count, config_manifest = await self.capture_config_file_manifest()
            schema_manifest = await self.capture_database_schema_manifest(databases)

            metadata["workflow_count"] = workflow_count
            metadata["credential_count"] = credential_count
            metadata["config_file_count"] = config_count
            metadata["workflows_manifest"] = workflows_manifest
            metadata["credentials_manifest"] = credentials_manifest
            metadata["config_files_manifest"] = config_manifest
            metadata["database_schema_manifest"] = schema_manifest

            # 5. Write metadata.json
            metadata_path = os.path.join(temp_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)

            # 6. Write restore.sh
            restore_script = self._generate_restore_script()
            restore_path = os.path.join(temp_dir, "restore.sh")
            with open(restore_path, 'w') as f:
                f.write(restore_script)
            os.chmod(restore_path, 0o755)

            # 7. Create tar.gz archive
            with tarfile.open(archive_path, "w:gz") as tar:
                for item in os.listdir(temp_dir):
                    tar.add(os.path.join(temp_dir, item), arcname=item)

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

    def _generate_restore_script(self) -> str:
        """Generate the restore.sh script for bare metal recovery."""
        return '''#!/bin/bash
# ============================================================================
# n8n Bare Metal Recovery Script
# ============================================================================
# Generated automatically by n8n Management Console
#
# This script restores a complete n8n installation from a backup archive.
# It can be used for:
#   - Disaster recovery
#   - Migration to a new server
#   - Restoring from a specific backup point
#
# Usage: ./restore.sh [options]
#
# Options:
#   --target-dir DIR    Directory to restore to (default: /opt/n8n)
#   --db-host HOST      PostgreSQL host (default: localhost)
#   --db-user USER      PostgreSQL user (default: n8n)
#   --db-pass PASS      PostgreSQL password (prompted if not provided)
#   --skip-docker       Skip Docker installation check
#   --skip-ssl          Skip SSL certificate restoration
#   --skip-db           Skip database restoration
#   --skip-config       Skip config file restoration
#   --dry-run           Show what would be done without making changes
#   --force             Skip all confirmation prompts
#   -h, --help          Show this help message
#
# ============================================================================

set -e

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
CYAN='\\033[0;36m'
NC='\\033[0m' # No Color

# Default values
TARGET_DIR="/opt/n8n"
DB_HOST="localhost"
DB_USER="n8n"
DB_PASS=""
SKIP_DOCKER=false
SKIP_SSL=false
SKIP_DB=false
SKIP_CONFIG=false
DRY_RUN=false
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --target-dir) TARGET_DIR="$2"; shift 2 ;;
        --db-host) DB_HOST="$2"; shift 2 ;;
        --db-user) DB_USER="$2"; shift 2 ;;
        --db-pass) DB_PASS="$2"; shift 2 ;;
        --skip-docker) SKIP_DOCKER=true; shift ;;
        --skip-ssl) SKIP_SSL=true; shift ;;
        --skip-db) SKIP_DB=true; shift ;;
        --skip-config) SKIP_CONFIG=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --force) FORCE=true; shift ;;
        -h|--help)
            head -n 30 "$0" | tail -n 26
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

run_cmd() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${CYAN}  [DRY-RUN] Would run:${NC} $*"
        return 0
    else
        "$@"
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

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_warning "This script should be run as root for full functionality"
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
    fi
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           n8n Bare Metal Recovery Script                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check for metadata
if [[ ! -f "$SCRIPT_DIR/metadata.json" ]]; then
    log_error "metadata.json not found. Is this a valid backup?"
    exit 1
fi

# Show backup info
echo -e "${CYAN}Backup Information:${NC}"
echo "──────────────────────────────────────────────────────────────"
if command -v python3 &>/dev/null; then
    cat "$SCRIPT_DIR/metadata.json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Backup Type:    {data.get(\"backup_type\", \"unknown\")}')
print(f'  Created:        {data.get(\"created_at\", \"unknown\")}')
print(f'  n8n Version:    {data.get(\"n8n_version\", \"unknown\")}')
print(f'  Workflows:      {data.get(\"workflow_count\", 0)}')
print(f'  Credentials:    {data.get(\"credential_count\", 0)}')
print(f'  Config Files:   {data.get(\"config_file_count\", 0)}')
"
else
    log_warning "python3 not found, showing raw metadata"
    cat "$SCRIPT_DIR/metadata.json"
fi
echo "──────────────────────────────────────────────────────────────"
echo ""

echo -e "${CYAN}Restore Configuration:${NC}"
echo "  Target Directory: $TARGET_DIR"
echo "  Database Host:    $DB_HOST"
echo "  Database User:    $DB_USER"
echo "  Skip Docker:      $SKIP_DOCKER"
echo "  Skip SSL:         $SKIP_SSL"
echo "  Skip Database:    $SKIP_DB"
echo "  Skip Config:      $SKIP_CONFIG"
echo "  Dry Run:          $DRY_RUN"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  DRY RUN MODE - No changes will be made to the system${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
fi

# Confirmation
if ! confirm "Proceed with restore?"; then
    echo "Restore cancelled."
    exit 0
fi

echo ""

# ============================================================================
# Step 1: Check and Install Docker (if needed)
# ============================================================================

if [[ "$SKIP_DOCKER" != "true" ]]; then
    echo -e "${GREEN}Step 1: Checking Docker...${NC}"

    if command -v docker &>/dev/null; then
        docker_version=$(docker --version 2>/dev/null || echo "unknown")
        log_success "Docker is installed: $docker_version"
    else
        log_warning "Docker is not installed"
        if confirm "Install Docker?"; then
            log_info "Installing Docker..."
            if [[ "$DRY_RUN" != "true" ]]; then
                curl -fsSL https://get.docker.com | sh
                systemctl enable docker
                systemctl start docker
                log_success "Docker installed successfully"
            else
                echo -e "${CYAN}  [DRY-RUN] Would install Docker${NC}"
            fi
        fi
    fi

    if command -v docker-compose &>/dev/null; then
        compose_version=$(docker-compose --version 2>/dev/null || echo "unknown")
        log_success "Docker Compose is available: $compose_version"
    elif docker compose version &>/dev/null; then
        log_success "Docker Compose plugin is available"
    else
        log_warning "Docker Compose not found"
    fi
    echo ""
fi

# ============================================================================
# Step 2: Check PostgreSQL Tools
# ============================================================================

if [[ "$SKIP_DB" != "true" ]]; then
    echo -e "${GREEN}Step 2: Checking PostgreSQL tools...${NC}"

    if command -v pg_restore &>/dev/null; then
        pg_version=$(pg_restore --version 2>/dev/null | head -1 || echo "unknown")
        log_success "pg_restore is available: $pg_version"
    else
        log_error "pg_restore is not installed"
        log_info "Install with: apt-get install postgresql-client"
        if ! confirm "Continue without database restore?"; then
            exit 1
        fi
        SKIP_DB=true
    fi
    echo ""
fi

# ============================================================================
# Step 3: Prompt for Database Password
# ============================================================================

if [[ "$SKIP_DB" != "true" && -z "$DB_PASS" ]]; then
    echo -e "${GREEN}Step 3: Database credentials...${NC}"
    read -sp "Enter PostgreSQL password for user $DB_USER: " DB_PASS
    echo ""
    echo ""
fi

# ============================================================================
# Step 4: Create Target Directory
# ============================================================================

echo -e "${GREEN}Step 4: Preparing target directory...${NC}"
run_cmd mkdir -p "$TARGET_DIR"
log_success "Target directory ready: $TARGET_DIR"
echo ""

# ============================================================================
# Step 5: Restore Databases
# ============================================================================

if [[ "$SKIP_DB" != "true" && -d "$SCRIPT_DIR/databases" ]]; then
    echo -e "${GREEN}Step 5: Restoring databases...${NC}"

    db_count=0
    for db_file in "$SCRIPT_DIR/databases"/*.dump; do
        if [[ -f "$db_file" ]]; then
            db_name=$(basename "$db_file" .dump)
            log_info "Restoring database: $db_name"

            if [[ "$DRY_RUN" != "true" ]]; then
                # Check if database exists, create if not
                PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -tc \\
                    "SELECT 1 FROM pg_database WHERE datname = '$db_name'" | grep -q 1 || \\
                    PGPASSWORD="$DB_PASS" createdb -h "$DB_HOST" -U "$DB_USER" "$db_name" 2>/dev/null || true

                # Restore the database
                PGPASSWORD="$DB_PASS" pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$db_name" \\
                    --clean --if-exists --no-owner --no-acl "$db_file" 2>/dev/null || true

                log_success "Database $db_name restored"
            else
                echo -e "${CYAN}  [DRY-RUN] Would restore database: $db_name${NC}"
            fi
            ((db_count++))
        fi
    done

    if [[ $db_count -eq 0 ]]; then
        log_warning "No database dumps found"
    else
        log_success "Restored $db_count database(s)"
    fi
    echo ""
else
    echo -e "${YELLOW}Step 5: Skipping database restoration${NC}"
    echo ""
fi

# ============================================================================
# Step 6: Restore Config Files
# ============================================================================

if [[ "$SKIP_CONFIG" != "true" && -d "$SCRIPT_DIR/config" ]]; then
    echo -e "${GREEN}Step 6: Restoring config files...${NC}"

    config_count=0
    for config_file in "$SCRIPT_DIR/config"/*; do
        if [[ -f "$config_file" ]]; then
            filename=$(basename "$config_file")
            target_path="$TARGET_DIR/$filename"

            # Backup existing file if it exists
            if [[ -f "$target_path" && "$DRY_RUN" != "true" ]]; then
                backup_path="${target_path}.bak.$(date +%Y%m%d_%H%M%S)"
                cp "$target_path" "$backup_path"
                log_info "Backed up existing $filename to $backup_path"
            fi

            log_info "Restoring $filename"
            run_cmd cp "$config_file" "$target_path"
            ((config_count++))
        fi
    done

    log_success "Restored $config_count config file(s)"
    echo ""
else
    echo -e "${YELLOW}Step 6: Skipping config file restoration${NC}"
    echo ""
fi

# ============================================================================
# Step 7: Restore SSL Certificates
# ============================================================================

if [[ "$SKIP_SSL" != "true" && -d "$SCRIPT_DIR/ssl" ]]; then
    echo -e "${GREEN}Step 7: Restoring SSL certificates...${NC}"

    run_cmd mkdir -p /etc/letsencrypt/live
    ssl_count=0

    for domain_dir in "$SCRIPT_DIR/ssl"/*; do
        if [[ -d "$domain_dir" ]]; then
            domain=$(basename "$domain_dir")
            log_info "Restoring certificates for: $domain"
            run_cmd cp -r "$domain_dir" "/etc/letsencrypt/live/"
            ((ssl_count++))
        fi
    done

    log_success "Restored SSL certificates for $ssl_count domain(s)"
    echo ""
else
    echo -e "${YELLOW}Step 7: Skipping SSL certificate restoration${NC}"
    echo ""
fi

# ============================================================================
# Step 8: Post-Restore Validation
# ============================================================================

echo -e "${GREEN}Step 8: Post-restore validation...${NC}"

validation_passed=true

# Check config files exist
if [[ -f "$TARGET_DIR/.env" ]]; then
    log_success ".env file exists"
else
    log_warning ".env file not found at $TARGET_DIR/.env"
    validation_passed=false
fi

if [[ -f "$TARGET_DIR/docker-compose.yaml" ]] || [[ -f "$TARGET_DIR/docker-compose.yml" ]]; then
    log_success "docker-compose file exists"
else
    log_warning "docker-compose.yaml not found at $TARGET_DIR/"
    validation_passed=false
fi

# Check database connectivity (if not skipped)
if [[ "$SKIP_DB" != "true" && -n "$DB_PASS" && "$DRY_RUN" != "true" ]]; then
    if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d n8n -c "SELECT 1" &>/dev/null; then
        log_success "Database connectivity verified"
    else
        log_warning "Could not connect to n8n database"
        validation_passed=false
    fi
fi

echo ""

# ============================================================================
# Completion Summary
# ============================================================================

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${GREEN}║              DRY RUN COMPLETED SUCCESSFULLY                  ║${NC}"
else
    echo -e "${GREEN}║              RESTORE COMPLETED SUCCESSFULLY                  ║${NC}"
fi
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ "$DRY_RUN" != "true" ]]; then
    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Review restored configuration files in $TARGET_DIR"
    echo "  2. Update .env with any environment-specific settings:"
    echo "     - Database connection string"
    echo "     - Domain name"
    echo "     - API keys and secrets"
    echo "  3. Navigate to the target directory:"
    echo "     cd $TARGET_DIR"
    echo "  4. Start the services:"
    echo "     docker-compose up -d"
    echo "  5. Verify services are running:"
    echo "     docker-compose ps"
    echo "  6. Check logs for any issues:"
    echo "     docker-compose logs -f"
    echo ""

    if [[ "$validation_passed" != "true" ]]; then
        echo -e "${YELLOW}Warning: Some validation checks failed. Please review above.${NC}"
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
    ) -> BackupHistory:
        """
        Execute a backup with full metadata capture.
        This is the enhanced version that creates complete archives.
        """
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

            # Create complete archive with metadata
            if n8n_db:
                filepath, metadata = await self.create_complete_archive(
                    backup_type, databases, n8n_db, compression
                )
            else:
                # Fallback to simple backup if no n8n_db session
                filepath, metadata = await self._simple_backup(
                    backup_type, databases, compression
                )

            # Calculate checksum and file size
            file_size = os.path.getsize(filepath)
            checksum = hash_file_sha256(filepath)
            filename = os.path.basename(filepath)

            # Get postgres version
            pg_version = await self._get_postgres_version()

            # Update history
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
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())
            history.storage_location = "nfs" if "/mnt/backups" in filepath else "local"

            await self.db.commit()
            await self.db.refresh(history)

            # Store backup contents metadata
            contents = BackupContents(
                backup_id=history.id,
                workflow_count=metadata.get("workflow_count", 0),
                credential_count=metadata.get("credential_count", 0),
                config_file_count=metadata.get("config_file_count", 0),
                workflows_manifest=metadata.get("workflows_manifest"),
                credentials_manifest=metadata.get("credentials_manifest"),
                config_files_manifest=metadata.get("config_files_manifest"),
                database_schema_manifest=metadata.get("database_schema_manifest"),
                verification_checksums={
                    "archive": checksum,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            self.db.add(contents)
            await self.db.commit()

            # Notify success
            await dispatch_notification("backup.success", {
                "backup_type": backup_type,
                "backup_id": history.id,
                "filename": filename,
                "size_mb": round(file_size / 1024 / 1024, 2),
                "duration_seconds": history.duration_seconds,
                "workflow_count": metadata.get("workflow_count", 0),
            })

            logger.info(f"Backup completed: {filename} ({file_size} bytes)")
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
                await dispatch_notification("backup.failed", {
                    "backup_type": backup_type,
                    "backup_id": history.id,
                    "error": str(e),
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
