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
from typing import AsyncIterator, Optional, List, Dict, Any, Tuple
import contextlib
from contextlib import asynccontextmanager
import subprocess
import asyncio
import gzip
import tarfile
import tempfile
import shutil
import json
import hashlib
import secrets
import os
import logging
from zlib import error as zlib_error

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
from api.services import proc as _proc
from api.services.operation_jobs import report_progress as report_job_progress
from api.services.notification_service import dispatch_notification
from api.services.backup_archive import (
    ENCRYPTED_SUFFIX,
    BackupEncryptionError,
    EncryptingWriter,
    chmod_quietly,
    get_encryption_passphrase,
    make_private_dir,
    open_private_file,
    plaintext_archive,
    tighten_backup_tree_once,
)
from api.services.backup_storage import (
    BackupStorageUnavailableError,
    inspect_storage_target_async,
    notify_storage_unavailable,
)

logger = logging.getLogger(__name__)

# Layout of complete archives. 2 = project/ tree, volumes/, images and
# workflow checksums in metadata.json, optional gpg encryption.
ARCHIVE_FORMAT_VERSION = 2

# Per-workflow checksum computed by PostgreSQL from the stored JSON text, so
# the value taken from the live database at backup time and the one taken
# from a restored copy at verification time are computed identically.
# Columns: id, sha256, updatedAt as epoch milliseconds.
WORKFLOW_CHECKSUM_SQL = (
    'SELECT id::text, '
    "encode(sha256(convert_to(COALESCE(nodes::text, '') || '|' || COALESCE(connections::text, ''), 'UTF8')), 'hex'), "
    'floor(extract(epoch FROM "updatedAt") * 1000)::bigint '
    'FROM workflow_entity ORDER BY id'
)


# Config files to include in backups
# Using /app/host_project/ which is a directory mount (more reliable than individual file mounts)
# Files that don't exist are skipped (e.g., dozzle/ntfy only if those services are installed)
CONFIG_FILES = [
    # Core config files
    {"name": ".env", "host_path": "/app/host_project/.env", "archive_path": "config/.env"},
    {"name": "docker-compose.yaml", "host_path": "/app/host_project/docker-compose.yaml", "archive_path": "config/docker-compose.yaml"},
    {"name": "nginx.conf", "host_path": "/app/host_project/nginx.conf", "archive_path": "config/nginx.conf"},
    {"name": "nginx-router.conf", "host_path": "/app/host_project/nginx-router.conf", "archive_path": "config/nginx-router.conf"},
    {"name": "nginx-public.conf", "host_path": "/app/host_project/nginx-public.conf", "archive_path": "config/nginx-public.conf"},
    {"name": ".filebrowser.json", "host_path": "/app/host_project/.filebrowser.json", "archive_path": "config/.filebrowser.json"},
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


# Free-space pre-check (see BackupService._check_free_space_for_backup)
BACKUP_SIZE_GROWTH_FACTOR = 1.2
STORAGE_STAT_TIMEOUT = 30


def _backup_min_free_bytes() -> int:
    """Headroom to leave free on the backup disk (env BACKUP_MIN_FREE_MB, default 1024)."""
    try:
        return max(int(os.environ.get("BACKUP_MIN_FREE_MB", "1024")), 0) * 1024 * 1024
    except ValueError:
        return 1024 * 1024 * 1024


class InsufficientBackupSpaceError(Exception):
    """Raised before a backup starts when the destination lacks free space."""


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

def backup_archive_basename(backup_id: Optional[int] = None, now: Optional[datetime] = None) -> str:
    """
    Archive file name (before any encryption suffix), unique per backup:
    backup_<UTC yyyymmddThhmmssZ>_<history id>.n8n_backup.tar.gz. Without a
    history id a random suffix keeps two backups in the same second apart.
    UTC avoids the repeated local hour at the end of daylight saving time.
    """
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    unique = str(backup_id) if backup_id is not None else secrets.token_hex(4)
    return f"backup_{stamp}_{unique}.n8n_backup.tar.gz"


@asynccontextmanager
async def _async_temp_dir(prefix: str = "n8n_backup_stage_") -> AsyncIterator[str]:
    """TemporaryDirectory whose creation and (possibly large) removal run off the event loop."""
    path = await asyncio.to_thread(tempfile.mkdtemp, prefix=prefix)
    try:
        yield path
    finally:
        await asyncio.to_thread(shutil.rmtree, path, True)


def _log_staging_tree(temp_dir: str) -> None:
    """Log what is about to go into the archive."""
    logger.info("Temp directory contents before archive creation:")
    for root, dirs, files in os.walk(temp_dir):
        level = root.replace(temp_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        logger.info(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            logger.info(f"{sub_indent}{file} ({os.path.getsize(file_path)} bytes)")


PG_RESTORE_LIST_TIMEOUT = 600


def pg_restore_list(dump_path: str) -> Dict[str, Any]:
    """Run `pg_restore --list` on a custom-format dump. ok is False on any non-zero exit."""
    try:
        proc = subprocess.run(
            ["pg_restore", "--list", dump_path],
            capture_output=True, text=True, timeout=PG_RESTORE_LIST_TIMEOUT,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "pg_restore not found (postgresql-client not installed)"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"pg_restore --list timed out after {PG_RESTORE_LIST_TIMEOUT}s"}
    entries = [ln for ln in (proc.stdout or "").splitlines() if ln and not ln.startswith(";")]
    if proc.returncode != 0:
        return {"ok": False, "error": f"pg_restore --list exited {proc.returncode}: {(proc.stderr or '').strip()[-500:]}"}
    if not entries:
        return {"ok": False, "error": "dump contains no objects"}
    return {"ok": True, "toc_entries": len(entries)}


def inspect_backup_archive(path: str, expected_databases: List[str]) -> Dict[str, Any]:
    """
    Decrypt (if needed) and read a complete backup archive end to end.

    Every member is read in full, so a truncated or corrupted gzip stream
    fails here; metadata.json must parse; every expected database must have
    databases/<db>.dump, and every dump must pass pg_restore --list.
    """
    result: Dict[str, Any] = {
        "passed": False,
        "encrypted": path.endswith(ENCRYPTED_SUFFIX),
        "total_files": 0,
        "has_metadata": False,
        "has_restore_script": False,
        "dumps": {},
        "errors": [],
    }
    errors = result["errors"]
    try:
        with plaintext_archive(path) as plain, tempfile.TemporaryDirectory(prefix="n8n_verify_") as tmp:
            with tarfile.open(plain, "r:gz") as tar:
                for member in tar:
                    result["total_files"] += 1
                    if not member.isfile():
                        continue
                    src = tar.extractfile(member)
                    if src is None:
                        continue
                    name = member.name
                    if name.startswith("databases/") and name.endswith(".dump") and "/" not in name[len("databases/"):]:
                        db = os.path.basename(name)[:-len(".dump")]
                        dump_path = os.path.join(tmp, f"{db}.dump")
                        with open(dump_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        result["dumps"][db] = pg_restore_list(dump_path)
                        os.remove(dump_path)
                    elif name == "metadata.json":
                        try:
                            json.loads(src.read().decode("utf-8"))
                            result["has_metadata"] = True
                        except ValueError as e:
                            errors.append(f"metadata.json is not valid JSON: {e}")
                    else:
                        if name == "restore.sh":
                            result["has_restore_script"] = True
                        while src.read(1024 * 1024):
                            pass
    except BackupEncryptionError as e:
        errors.append(str(e))
        return result
    except (tarfile.TarError, OSError, EOFError, zlib_error) as e:
        errors.append(f"Archive is unreadable or truncated: {e}")
        return result

    if not result["has_metadata"]:
        errors.append("metadata.json missing from archive")
    for db in expected_databases:
        if db not in result["dumps"]:
            errors.append(f"databases/{db}.dump missing from archive")
    for db, info in result["dumps"].items():
        if not info.get("ok"):
            errors.append(f"{db}.dump: {info.get('error')}")
    result["passed"] = not errors
    return result


def inspect_legacy_dump(path: str) -> Dict[str, Any]:
    """Archive check for single-file .sql(.gz) backups written by the legacy path."""
    result: Dict[str, Any] = {"passed": False, "dumps": {}, "errors": []}
    try:
        with tempfile.TemporaryDirectory(prefix="n8n_verify_") as tmp:
            dump_path = os.path.join(tmp, "dump")
            opener = gzip.open if path.endswith(".gz") else open
            with opener(path, "rb") as src, open(dump_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            result["dumps"]["dump"] = pg_restore_list(dump_path)
    except (OSError, EOFError, zlib_error) as e:
        result["errors"].append(f"Backup file is unreadable or truncated: {e}")
        return result
    if not result["dumps"]["dump"].get("ok"):
        result["errors"].append(result["dumps"]["dump"].get("error"))
    result["passed"] = not result["errors"]
    return result


# Leftovers of a crash/restart: *.partial archives and safety dumps in the
# backup directories, and staging/decryption temp dirs. Nothing runs at
# startup, and the age limit spares anything a long-running job could own.
STALE_LEFTOVER_AGE_SECONDS = 6 * 3600
_STALE_TEMP_PREFIXES = ("n8n_backup_stage_", "n8n_backup_plain_", "n8n_safety_", "n8n_gpg_")


def _sweep_stale_temp_dirs(max_age_seconds: float, tmp_root: Optional[str] = None) -> int:
    import time

    tmp_root = tmp_root or tempfile.gettempdir()
    now = time.time()
    removed = 0
    try:
        names = os.listdir(tmp_root)
    except OSError:
        return 0
    for name in names:
        if not name.startswith(_STALE_TEMP_PREFIXES):
            continue
        path = os.path.join(tmp_root, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if os.path.isdir(path) and not os.path.islink(path) and now - st.st_mtime > max_age_seconds:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


async def cleanup_stale_backup_files(max_age_seconds: float = STALE_LEFTOVER_AGE_SECONDS) -> int:
    """
    Startup sweep of stale *.partial files under every configured backup root
    (network roots only when they answer the storage probe) and of stale
    temp dirs. Returns the number of entries removed.
    """
    from api.database import async_session_maker
    from api.services.backup_archive import sweep_stale_partials
    from api.services.backup_storage import inspect_storage_target_async

    candidates = [settings.backup_staging_dir, settings.nfs_mount_point]
    try:
        async with async_session_maker() as db:
            config = (await db.execute(select(BackupConfiguration).limit(1))).scalar_one_or_none()
        if config is not None:
            candidates += [config.primary_storage_path, config.nfs_storage_path]
    except Exception as e:
        logger.debug(f"Stale partial sweep: no backup configuration ({e})")
    roots: List[str] = []
    for path in dict.fromkeys(p for p in candidates if p):
        if (await inspect_storage_target_async(path)).exists:
            roots.append(path)
    try:
        removed = await asyncio.wait_for(
            asyncio.to_thread(sweep_stale_partials, roots, max_age_seconds), timeout=60
        )
    except asyncio.TimeoutError:
        logger.warning("Stale partial sweep did not finish within 60s (slow backup storage?)")
        removed = 0
    removed += await asyncio.to_thread(_sweep_stale_temp_dirs, max_age_seconds)
    return removed


# SSL certificate paths
SSL_CERT_PATH = "/etc/letsencrypt/live"


class BackupService:
    """Backup management service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._storage_fallback_notified = False

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
        report_job_progress(progress, message, backup_id=history.id)
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
            type_dir = make_private_dir(os.path.join(storage_dir, backup_type))
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
            history.error_message = None  # e.g. "Marked failed by the backup monitor" before it completed
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())
            history.storage_location = await self._storage_label(filepath)

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
                    # Throttle per backup type and schedule, not globally
                    "target_id": f"{backup_type}:{history.schedule_id or 'manual'}",
                    "backup_type": backup_type,
                    "backup_id": history.id,
                    "error": str(e),
                    "failed_at": history.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
                })
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

        # Owner-only from the first byte (opening below truncates, keeping the mode)
        os.close(os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600))
        chmod_quietly(filepath, 0o600)

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
        """
        Get backup storage location based on configuration.

        An NFS/off-host target is only used when it really is a network
        filesystem (see api.services.backup_storage); a bind-mounted host
        directory without the share mounted is the local disk. With
        storage_preference 'nfs' that fails closed
        (BackupStorageUnavailableError) instead of silently writing to local
        storage; with 'both' the backup falls back to local storage and a
        backup_storage_unavailable notification is sent.
        """
        config = await self._get_backup_configuration()

        if config:
            if config.storage_preference in ('nfs', 'both') and config.nfs_enabled:
                nfs_path = config.nfs_storage_path or settings.nfs_mount_point
                target = await inspect_storage_target_async(nfs_path)
                if target.offsite:
                    return nfs_path
                if config.storage_preference == 'nfs':
                    raise BackupStorageUnavailableError(
                        f"Backup storage is set to NFS only, but {target.reason}. "
                        "Refusing to write the backup to local storage. Mount the share on the host "
                        "(then restart the management container), or change Storage to Local/Both.",
                        target,
                    )
                logger.error(f"NFS backup target unavailable, using local storage: {target.reason}")
                if not self._storage_fallback_notified:
                    self._storage_fallback_notified = True
                    await notify_storage_unavailable(nfs_path, target, "backup fell back to local storage")

            # Use primary storage path from config
            primary_path = config.primary_storage_path
            if primary_path and os.path.exists(primary_path):
                return primary_path

        # Fallback to environment settings
        nfs_mount = settings.nfs_mount_point
        if (await inspect_storage_target_async(nfs_mount)).offsite:
            return nfs_mount
        return settings.backup_staging_dir

    @staticmethod
    async def _storage_label(filepath: str) -> str:
        """'nfs' only when the file really sits on a network share."""
        try:
            return "nfs" if (await inspect_storage_target_async(os.path.dirname(filepath))).offsite else "local"
        except Exception:
            return "local"

    async def _get_row_counts(self, database: str) -> Dict[str, int]:
        """Get row counts for tables in database."""
        # This would query the actual database - simplified here
        return {}

    async def _get_postgres_version(self) -> str:
        """Get PostgreSQL version."""
        try:
            result = await _proc.run(
                ["psql", "--version"],
                capture_output=True,
                text=True, timeout=_proc.PSQL_TIMEOUT
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
        current_checksum = await asyncio.to_thread(hash_file_sha256, backup.filepath)
        if current_checksum != backup.checksum:
            backup.verification_status = "failed"
            backup.verification_date = datetime.now(UTC)
            backup.verification_details = {"error": "Checksum mismatch"}
            await self.db.commit()
            return {"status": "failed", "error": "Checksum mismatch"}

        # Archive-level verification: decrypt, read every member (gzip CRC +
        # tar structure), and check every database dump with pg_restore --list.
        # This proves the archive is complete and each dump is a readable
        # pg_dump archive; it does not load the data (that is the
        # comprehensive verification, VerificationService.verify_backup).
        expected = [d for d in (backup.database_name or "").split(",") if d]
        if backup.filename and ".n8n_backup." in backup.filename:
            inspection = await asyncio.to_thread(inspect_backup_archive, backup.filepath, expected)
        else:
            inspection = await asyncio.to_thread(inspect_legacy_dump, backup.filepath)
        details = {
            "method": "archive",
            "checksum_verified": True,
            **inspection,
        }
        status = "passed" if inspection.get("passed") else "failed"
        backup.verification_status = status
        backup.verification_date = datetime.now(UTC)
        backup.verification_details = details
        await self.db.commit()

        result = {"status": status, **details}
        if status == "failed":
            result["error"] = "; ".join(inspection.get("errors") or ["archive verification failed"])
        return result

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
        """Config file manifest with checksums (hashing runs in a worker thread)."""
        return await asyncio.to_thread(self._capture_config_file_manifest_sync)

    def _capture_config_file_manifest_sync(self) -> Tuple[int, List[Dict[str, Any]]]:
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
                result = await _proc.run(cmd, capture_output=True, text=True, env=env, timeout=_proc.PSQL_TIMEOUT)

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
                        count_result = await _proc.run(count_cmd, capture_output=True, text=True, env=env, timeout=_proc.QUERY_TIMEOUT)
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
                        col_result = await _proc.run(col_cmd, capture_output=True, text=True, env=env, timeout=_proc.PSQL_TIMEOUT)
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
        """Public website manifest with checksums (hashing runs in a worker thread)."""
        return await asyncio.to_thread(self._capture_public_website_manifest_sync, public_website_dir)

    def _capture_public_website_manifest_sync(self, public_website_dir: str) -> Tuple[int, List[Dict[str, Any]]]:
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
        archive_name = backup_archive_basename(history.id if history is not None else None)

        # Resolve the passphrase before any work: a configured but unusable
        # passphrase fails the backup instead of writing plaintext.
        passphrase = get_encryption_passphrase()
        if passphrase:
            archive_name += ENCRYPTED_SUFFIX
        else:
            logger.warning(
                "BACKUP_ENCRYPTION_PASSPHRASE is not set: the backup archive (which contains .env, "
                "TLS private keys and the databases) is written UNENCRYPTED (mode 0600)."
            )

        storage_dir = await self._get_storage_location()
        # Archives written by older versions were world-readable: tighten the
        # backup system's own files once per storage root and process (never
        # the root itself or unrelated files on a shared export).
        await asyncio.to_thread(tighten_backup_tree_once, storage_dir)
        type_dir = make_private_dir(os.path.join(storage_dir, backup_type))
        archive_path = os.path.join(type_dir, archive_name)

        # Progress update helper
        async def update_progress(pct: int, msg: str):
            if history:
                await self._update_progress(history, pct, msg)

        await update_progress(5, "Initializing backup")

        # Create temp directory for staging
        async with _async_temp_dir() as temp_dir:
            metadata = {
                "backup_type": backup_type,
                "created_at": datetime.now(UTC).isoformat(),
                "databases": databases,
                "n8n_version": await self._get_n8n_version(),
                "postgres_version": await self._get_postgres_version(),
                "archive_format_version": ARCHIVE_FORMAT_VERSION,
                "encrypted": bool(passphrase),
                "encryption": (
                    {"tool": "gpg", "mode": "symmetric", "cipher": "AES256",
                     "passphrase_source": "BACKUP_ENCRYPTION_PASSPHRASE"}
                    if passphrase else None
                ),
            }

            # Workflow checksums are taken for the comprehensive verification
            # to compare with the restored copy (see WORKFLOW_CHECKSUM_SQL).
            # When possible they are read in an exported snapshot that pg_dump
            # then dumps (--snapshot), so both see exactly the same data.
            row_counts = {}
            async with self._n8n_dump_snapshot(n8n_db, "n8n" in databases) as (snapshot_id, checksums):
                if "n8n" in databases:
                    metadata["workflow_checksums"] = checksums
                    metadata["workflow_checksums_same_snapshot"] = False

                # 1. Dump databases (5-40%)
                await update_progress(10, "Dumping databases")
                db_dir = os.path.join(temp_dir, "databases")
                os.makedirs(db_dir)

                db_count = len(databases)
                for idx, db_name in enumerate(databases):
                    progress = 10 + int((idx / max(db_count, 1)) * 30)
                    await update_progress(progress, f"Dumping database: {db_name}")
                    db_file = os.path.join(db_dir, f"{db_name}.dump")
                    used_snapshot = await self._execute_pg_dump_to_file(
                        db_name, db_file, snapshot=snapshot_id if db_name == "n8n" else None
                    )
                    if db_name == "n8n":
                        metadata["workflow_checksums_same_snapshot"] = used_snapshot
                    row_counts[db_name] = await self._get_row_counts(db_name)

            metadata["row_counts"] = row_counts

            # 2. Copy config files (40-50%)
            await update_progress(45, "Copying config files")
            config_dir = os.path.join(temp_dir, "config")
            os.makedirs(config_dir)

            def copy_config_and_certs() -> None:
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
                if os.path.exists(SSL_CERT_PATH):
                    ssl_dir = os.path.join(temp_dir, "ssl")
                    shutil.copytree(SSL_CERT_PATH, ssl_dir)
                # Full certbot tree (archive/, live/, renewal/, accounts/, ...) with
                # symlinks preserved, so a restored lineage can still be renewed.
                # ssl/ above is kept for browsing, verification and older restore.sh.
                letsencrypt_root = os.path.dirname(SSL_CERT_PATH)
                metadata["letsencrypt_tree_included"] = False
                if os.path.isdir(os.path.join(letsencrypt_root, "live")):
                    try:
                        shutil.copytree(letsencrypt_root, os.path.join(temp_dir, "letsencrypt"), symlinks=True)
                        metadata["letsencrypt_tree_included"] = True
                    except Exception as e:
                        logger.error(f"Failed to copy {letsencrypt_root} tree into backup: {e}")

            await asyncio.to_thread(copy_config_and_certs)

            # 3.2 Everything else a bare-metal restore needs (H-6): the project
            # directory (bind-mounted configs, scripts, build contexts), the
            # images each service ran, and the state volumes outside Postgres.
            await update_progress(51, "Copying project directory and volume snapshots")
            await self._add_stack_inventory(temp_dir, metadata)

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
            from api.services.restore_script import RESTORE_SCRIPT_VERSION
            try:
                restore_script = self._generate_restore_script()
                metadata["restore_script_version"] = RESTORE_SCRIPT_VERSION
            except (OSError, ValueError) as e:
                # Never fail the backup over this: the data is still restorable and
                # the current restore.sh can be downloaded separately.
                logger.error(f"Could not render restore.sh, archive will not include it: {e}")
                restore_script = None
                metadata["restore_script_version"] = None
            metadata_path = os.path.join(temp_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)

            # 6. Write restore.sh (80-85%)
            await update_progress(80, "Writing restore script")
            if restore_script is not None:
                restore_path = os.path.join(temp_dir, "restore.sh")
                with open(restore_path, 'w') as f:
                    f.write(restore_script)
                os.chmod(restore_path, 0o755)

            # 7. Create tar.gz archive (85-95%)
            await update_progress(85, "Creating archive")

            await asyncio.to_thread(_log_staging_tree, temp_dir)
            await asyncio.to_thread(self._write_archive, temp_dir, archive_path, passphrase)

            await update_progress(95, "Finalizing")
            logger.info(f"Created complete archive: {archive_path}")

        return archive_path, metadata

    @asynccontextmanager
    async def _n8n_dump_snapshot(self, n8n_db: AsyncSession, wanted: bool):
        """
        Yield (snapshot_id, workflow_checksums). With a PostgreSQL n8n engine
        bound to the "n8n" database, the checksums are read inside a
        REPEATABLE READ transaction whose snapshot is exported
        (pg_export_snapshot) and kept open until the block exits, so pg_dump
        --snapshot dumps exactly the data the checksums describe. Otherwise
        snapshot_id is None and the checksums come from the session as before.
        """
        if not wanted:
            yield None, {}
            return
        engine = getattr(n8n_db, "bind", None)
        conn = None
        snapshot_id: Optional[str] = None
        checksums: Optional[Dict[str, Dict[str, Any]]] = None
        try:
            usable = (
                engine is not None
                and engine.dialect.name == "postgresql"
                and engine.url.database == "n8n"
            )
        except Exception:
            usable = False
        if usable:
            try:
                conn = await engine.connect()
                await conn.execution_options(isolation_level="REPEATABLE READ")
                await conn.begin()
                snapshot_id = (await conn.execute(text("SELECT pg_export_snapshot()"))).scalar()
                rows = (await conn.execute(text(WORKFLOW_CHECKSUM_SQL))).fetchall()
                checksums = {
                    str(r[0]): {"sha256": r[1], "updated_at_ms": int(r[2]) if r[2] is not None else None}
                    for r in rows
                }
                logger.info(f"Captured checksums for {len(checksums)} workflows in snapshot {snapshot_id}")
            except Exception as e:
                logger.warning(f"Could not export a snapshot for the n8n dump ({e}); dumping without one")
                snapshot_id, checksums = None, None
                if conn is not None:
                    with contextlib.suppress(Exception):
                        await conn.close()
                    conn = None
        if checksums is None:
            checksums = await self.capture_workflow_checksums(n8n_db)
        try:
            yield snapshot_id, checksums
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    await conn.rollback()
                with contextlib.suppress(Exception):
                    await conn.close()

    async def _execute_pg_dump_to_file(self, database: str, filepath: str, snapshot: Optional[str] = None) -> bool:
        """
        Execute pg_dump to a file (custom format, no compression). With
        snapshot, dump in that exported snapshot; if pg_dump rejects it, dump
        again without. Returns True when the dump used the snapshot.
        """
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
            # Fail instead of waiting forever behind a lock (e.g. an n8n migration)
            f"--lock-wait-timeout={_proc.PG_LOCK_WAIT_TIMEOUT}",
            "-F", "c",  # Custom format
            "-f", filepath,
        ]

        env = {**os.environ, "PGPASSWORD": password}

        async def dump(args: List[str]) -> subprocess.CompletedProcess:
            try:
                return await _proc.run(args, capture_output=True, env=env, timeout=_proc.PG_DUMP_TIMEOUT)
            except subprocess.TimeoutExpired:
                raise Exception(f"pg_dump of {database} timed out after {_proc.PG_DUMP_TIMEOUT}s")

        if snapshot:
            result = await dump(cmd + [f"--snapshot={snapshot}"])
            if result.returncode == 0:
                return True
            stderr = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else str(result.stderr)
            logger.warning(f"pg_dump of {database} in snapshot {snapshot} failed ({stderr.strip()[-300:]}); retrying without")

        result = await dump(cmd)
        if result.returncode != 0:
            raise Exception(f"pg_dump failed for {database}: {result.stderr.decode()}")
        return False

    @staticmethod
    def _write_archive(source_dir: str, archive_path: str, passphrase: Optional[str]) -> None:
        """
        Write source_dir as a .tar.gz at archive_path (mode 0600), piped
        through gpg when a passphrase is given so no plaintext copy reaches
        the backup disk. Written to <archive>.partial and renamed on success.
        """
        if os.path.exists(archive_path):
            # Names are unique per backup; never overwrite an existing archive.
            raise FileExistsError(f"Backup archive already exists: {archive_path}")
        partial = archive_path + ".partial"
        if os.path.exists(partial):
            os.remove(partial)
        sink = None
        try:
            if passphrase:
                sink = EncryptingWriter(partial, passphrase)
                with tarfile.open(fileobj=sink, mode="w|gz") as tar:
                    for item in sorted(os.listdir(source_dir)):
                        tar.add(os.path.join(source_dir, item), arcname=item)
                sink.close()
            else:
                with open_private_file(partial) as raw:
                    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
                        for item in sorted(os.listdir(source_dir)):
                            tar.add(os.path.join(source_dir, item), arcname=item)
            chmod_quietly(partial, 0o600)
            os.replace(partial, archive_path)
        except BaseException:
            if sink is not None:
                sink.abort()
            try:
                os.remove(partial)
            except OSError:
                pass
            raise

    async def capture_workflow_checksums(self, n8n_db: AsyncSession) -> Dict[str, Dict[str, Any]]:
        """{workflow_id: {"sha256": ..., "updated_at_ms": ...}} from the live n8n database."""
        try:
            result = await n8n_db.execute(text(WORKFLOW_CHECKSUM_SQL))
            checksums = {
                str(row[0]): {"sha256": row[1], "updated_at_ms": int(row[2]) if row[2] is not None else None}
                for row in result.fetchall()
            }
            logger.info(f"Captured checksums for {len(checksums)} workflows")
            return checksums
        except Exception as e:
            logger.warning(f"Failed to capture workflow checksums: {e}")
            try:
                await n8n_db.rollback()
            except Exception:
                pass
            return {}

    async def _add_stack_inventory(self, temp_dir: str, metadata: Dict[str, Any]) -> None:
        """project/ tree, volumes/*.tar, image references and compose project in metadata."""
        from api.services import stack_inventory as inv

        try:
            count, skipped = await asyncio.to_thread(inv.copy_project_tree, os.path.join(temp_dir, "project"))
            metadata["project_tree_included"] = count > 0
            metadata["project_file_count"] = count
            if skipped:
                metadata["project_files_skipped"] = skipped[:50]
        except inv.ProjectTreeTooLargeError:
            raise  # fail the backup loudly rather than archive a partial project tree
        except Exception as e:
            logger.error(f"Could not copy the project directory into the backup: {e}")
            metadata["project_tree_included"] = False
        metadata["project_git_commit"] = await asyncio.to_thread(inv.read_git_commit)

        try:
            client = await asyncio.to_thread(inv._docker_client)
            project = await asyncio.to_thread(inv.find_compose_project, client)
            metadata["compose_project"] = project
            metadata["images"] = await asyncio.to_thread(inv.collect_service_images, client, project)
            metadata["volumes"] = await asyncio.to_thread(
                inv.snapshot_volumes, os.path.join(temp_dir, "volumes"), client, project
            )
        except Exception as e:
            logger.error(f"Could not record images / snapshot volumes (Docker API): {e}")
            metadata.setdefault("images", [])
            metadata.setdefault("volumes", [])
        missing = [v["volume"] for v in metadata.get("volumes", []) if not v.get("included")]
        if missing:
            logger.error(f"Volume snapshot(s) missing from this backup: {missing}")

    async def _get_n8n_version(self) -> str:
        """Get n8n version from container or environment."""
        try:
            # Try to get from n8n container
            result = await _proc.run(
                ["docker", "exec", "n8n", "n8n", "--version"],
                capture_output=True,
                text=True, timeout=_proc.DOCKER_TIMEOUT
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return os.environ.get("N8N_VERSION", "unknown")

    def _is_public_website_installed(self) -> bool:
        """Check if public website feature is enabled via PUBLIC_SITE_ENABLE env var."""
        return settings.public_site_enable

    async def _backup_public_website_volume(self, temp_dir: str) -> Tuple[bool, int]:
        """Copy the public website files into the staging dir (in a worker thread)."""
        return await asyncio.to_thread(self._backup_public_website_volume_sync, temp_dir)

    def _backup_public_website_volume_sync(self, temp_dir: str) -> Tuple[bool, int]:
        """
        Back up public_web_root Docker volume contents.
        The volume is mounted directly at settings.public_website_source_dir.
        Returns (success, file_count).
        """
        try:
            # The public_web_root volume is mounted directly in the container
            source_dir = settings.public_website_source_dir

            # Check if the source directory exists and has files
            if not os.path.exists(source_dir):
                logger.warning(f"Public website source directory does not exist: {source_dir}")
                return False, 0

            if not os.path.isdir(source_dir):
                logger.warning(f"Public website source path is not a directory: {source_dir}")
                return False, 0

            # Check if there are any files to backup
            source_files = list(os.listdir(source_dir))
            if not source_files:
                logger.info("Public website volume is empty, nothing to backup")
                return False, 0

            # Create destination directory
            public_website_dir = os.path.join(temp_dir, "public_website")
            os.makedirs(public_website_dir, exist_ok=True)

            # Copy files directly using shutil (no Docker-in-Docker needed)
            file_count = 0
            for item in source_files:
                src_path = os.path.join(source_dir, item)
                dst_path = os.path.join(public_website_dir, item)
                try:
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path)
                    else:
                        shutil.copy2(src_path, dst_path)
                except Exception as copy_error:
                    logger.warning(f"Failed to copy {item}: {copy_error}")

            # Count total files copied
            file_count = sum(len(files) for _, _, files in os.walk(public_website_dir))
            logger.info(f"Backed up public website volume: {file_count} files from {source_dir}")
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
        """
        Return the bare-metal restore.sh embedded in every archive.

        The script body lives in management/scripts/restore.sh.tpl so that it
        can be shellchecked; see api/services/restore_script.py.
        """
        from api.services.restore_script import render_restore_script
        return render_restore_script()

    async def _estimate_backup_size(self, backup_type: str) -> int:
        """Size of the most recent successful backup of this type (or any type), in bytes."""
        for type_filter in (backup_type, None):
            stmt = select(BackupHistory.file_size).where(
                BackupHistory.status == "success",
                BackupHistory.file_size.is_not(None),
            )
            if type_filter:
                stmt = stmt.where(BackupHistory.backup_type == type_filter)
            stmt = stmt.order_by(BackupHistory.created_at.desc()).limit(1)
            result = await self.db.execute(stmt)
            size = result.scalar()
            if size:
                return int(size)
        return 0

    async def _check_free_space_for_backup(self, backup_type: str) -> None:
        """
        Raise InsufficientBackupSpaceError if the backup destination (or the
        temp staging directory) does not have room for the next backup.

        Estimate for the archive on the destination: the larger of the last
        successful backup x BACKUP_SIZE_GROWTH_FACTOR and the current project
        tree + state volumes (the floor matters when the last backup predates
        project/ and volumes/). The temp staging directory needs the archive
        estimate (database dumps) plus an uncompressed copy of the project
        tree plus twice the volumes (raw `docker cp` stream and the rewritten
        snapshot exist side by side). Both are summed when on the same
        filesystem, plus BACKUP_MIN_FREE_MB of headroom so the disk is never
        filled to the last byte (Postgres needs room for WAL).

        Also raises ProjectTreeTooLargeError (before any dump) when the
        project directory is over BACKUP_PROJECT_MAX_MB.
        """
        from api.services import stack_inventory as inv

        storage_dir = await self._get_storage_location()
        staging_dir = tempfile.gettempdir()
        last_size = await self._estimate_backup_size(backup_type)
        project_bytes = await asyncio.to_thread(inv.check_project_tree_size)
        try:
            volume_bytes = await asyncio.wait_for(asyncio.to_thread(inv.estimate_snapshot_bytes), timeout=60)
        except Exception as e:
            logger.warning(f"Free-space pre-check: volume size unknown ({e!r})")
            volume_bytes = 0
        archive_estimate = max(int(last_size * BACKUP_SIZE_GROWTH_FACTOR), project_bytes + volume_bytes)
        staging_estimate = archive_estimate + project_bytes + 2 * volume_bytes
        headroom = _backup_min_free_bytes()

        def stat_paths() -> List[Tuple[str, Optional[int], int]]:
            out = []
            for path in (storage_dir, staging_dir):
                try:
                    vfs = os.statvfs(path)
                    out.append((path, os.stat(path).st_dev, vfs.f_bavail * vfs.f_frsize))
                except OSError as e:
                    logger.warning(f"Free-space pre-check: cannot stat {path}: {e}; skipping check for it")
            return out

        try:
            # The destination may be a network mount that hangs (see backup_storage).
            stats = await asyncio.wait_for(asyncio.to_thread(stat_paths), timeout=STORAGE_STAT_TIMEOUT)
        except asyncio.TimeoutError:
            raise BackupStorageUnavailableError(
                f"Backup storage {storage_dir} did not respond within {STORAGE_STAT_TIMEOUT}s "
                "(network share unreachable?); backup aborted."
            )

        required: Dict[int, int] = {}
        paths: Dict[int, List[str]] = {}
        available: Dict[int, int] = {}
        for path, st_dev, free_bytes in stats:
            need = archive_estimate if path == storage_dir else staging_estimate
            required[st_dev] = required.get(st_dev, 0) + need
            paths.setdefault(st_dev, []).append(path)
            available[st_dev] = free_bytes

        for st_dev, need in required.items():
            need += headroom
            free = available[st_dev]
            where = ", ".join(paths[st_dev])
            logger.info(
                f"Free-space pre-check: {where}: free {free / 1024**2:.0f} MiB, need ~{need / 1024**2:.0f} MiB"
            )
            if free < need:
                raise InsufficientBackupSpaceError(
                    f"Insufficient disk space for backup on {where}: "
                    f"{free / 1024**2:.0f} MiB free, ~{need / 1024**2:.0f} MiB needed "
                    f"(last backup {last_size / 1024**2:.0f} MiB x {BACKUP_SIZE_GROWTH_FACTOR}, "
                    f"project files {project_bytes / 1024**2:.0f} MiB, volumes "
                    f"{volume_bytes / 1024**2:.0f} MiB, + {headroom / 1024**2:.0f} MiB headroom). "
                    f"Backup aborted to avoid filling the disk. Free up space, reduce the "
                    f"retention settings, or move backup storage to another disk."
                )

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
        report_job_progress(1, "Starting backup", backup_id=history.id)

        try:
            # Fail fast (recorded as a failed backup + failure notification
            # below) instead of filling the disk that Postgres also lives on.
            await self._check_free_space_for_backup(backup_type)

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
            checksum = await asyncio.to_thread(hash_file_sha256, filepath)
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
            history.error_message = None  # e.g. "Marked failed by the backup monitor" before it completed
            history.progress = 100
            history.progress_message = "Backup completed"
            history.completed_at = datetime.now(UTC)
            history.duration_seconds = int((history.completed_at - history.started_at).total_seconds())
            history.storage_location = await self._storage_label(filepath)

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
                        "encrypted": bool(metadata.get("encrypted")),
                        "workflow_checksums": metadata.get("workflow_checksums") or {},
                        "workflow_checksums_same_snapshot": bool(
                            metadata.get("workflow_checksums_same_snapshot")
                        ),
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
                    # Throttle per backup type and schedule, not globally
                    "target_id": f"{backup_type}:{history.schedule_id or 'manual'}",
                    "backup_type": backup_type,
                    "backup_id": history.id,
                    "error": str(e),
                    "failed_at": history.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
                })
            except Exception as notif_error:
                logger.error(f"Failed to send failure notification: {notif_error}")

            if isinstance(e, BackupStorageUnavailableError) and e.status is not None:
                await notify_storage_unavailable(e.status.path, e.status, "backup refused")

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
        type_dir = make_private_dir(os.path.join(storage_dir, backup_type))
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
