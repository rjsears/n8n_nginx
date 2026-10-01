"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/restore_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import contextlib
import re
import secrets
import subprocess
import tarfile
import tempfile
import json
import os
import shutil
import logging
import asyncio
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from api.services.backup_service import BackupService
from api.services.backup_archive import (
    BackupEncryptionError,
    chmod_quietly,
    make_private_dir,
    open_backup_archive,
    plaintext_archive,
    safe_extract,
)
from api.services.n8n_api_service import N8nApiService
from api.config import settings
from api.services import proc as _proc

logger = logging.getLogger(__name__)


# Container configuration
RESTORE_CONTAINER_NAME = "n8n_postgres_restore"
RESTORE_CONTAINER_IMAGE = "pgvector/pgvector:0.8.6-pg16"  # Use pgvector image to support vector extension
RESTORE_DB_USER = "restore_user"
RESTORE_DB_NAME = "n8n_restore"
# Every temporary restore container carries this label so leftovers (crash,
# restart while a backup was mounted) can be found and removed at startup.
RESTORE_CONTAINER_LABEL = "n8n_management.temporary=restore"

# Module-level state for mounted backup (database restore container)
_mounted_backup_id: Optional[int] = None
_mounted_backup_info: Optional[Dict[str, Any]] = None

# File path for caching mounted workflow data
MOUNTED_WORKFLOWS_CACHE = "/tmp/n8n_mounted_workflows.json"
MOUNTED_CREDENTIALS_CACHE = "/tmp/n8n_mounted_credentials.json"

# Module-level state for public website file mounting (separate from database mounting)
_public_website_mounted_backup_id: Optional[int] = None
_public_website_mount_dir: Optional[str] = None
_public_website_restore_lock = asyncio.Lock()

# Cache file for public website file list
PUBLIC_WEBSITE_FILES_CACHE = "/tmp/n8n_public_website_files.json"


def get_mounted_backup_status() -> Dict[str, Any]:
    """Get the current mounted backup status (module-level function for easy access)."""
    global _mounted_backup_id, _mounted_backup_info
    if _mounted_backup_id is not None and _mounted_backup_info is not None:
        return {
            "mounted": True,
            "backup_id": _mounted_backup_id,
            "backup_info": _mounted_backup_info,
        }
    return {"mounted": False, "backup_id": None, "backup_info": None}


def get_public_website_mount_status() -> Dict[str, Any]:
    """Get the current public website files mount status."""
    global _public_website_mounted_backup_id, _public_website_mount_dir
    if _public_website_mounted_backup_id is not None and _public_website_mount_dir is not None:
        return {
            "mounted": True,
            "backup_id": _public_website_mounted_backup_id,
            "mount_dir": _public_website_mount_dir,
        }
    return {"mounted": False, "backup_id": None, "mount_dir": None}


def _save_workflows_to_cache(workflows: List[Dict[str, Any]], backup_id: int) -> bool:
    """Save workflow data to cache file for later extraction."""
    try:
        cache_data = {
            "backup_id": backup_id,
            "workflows": {w["id"]: w for w in workflows},  # Index by ID for fast lookup
            "cached_at": datetime.now(UTC).isoformat(),
        }
        with open(MOUNTED_WORKFLOWS_CACHE, 'w') as f:
            json.dump(cache_data, f)
        logger.info(f"Cached {len(workflows)} workflows for backup {backup_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save workflow cache: {e}")
        return False


def _load_workflow_from_cache(workflow_id: str, backup_id: int) -> Optional[Dict[str, Any]]:
    """Load a specific workflow from the cache file."""
    try:
        if not os.path.exists(MOUNTED_WORKFLOWS_CACHE):
            logger.error("Workflow cache file not found")
            return None

        with open(MOUNTED_WORKFLOWS_CACHE, 'r') as f:
            cache_data = json.load(f)

        # Verify it's for the right backup
        if cache_data.get("backup_id") != backup_id:
            logger.warning(f"Cache is for backup {cache_data.get('backup_id')}, not {backup_id}")
            # Still try to load - the container might have the right data

        workflow = cache_data.get("workflows", {}).get(workflow_id)
        if workflow:
            logger.info(f"Found workflow {workflow_id} in cache")
            return workflow
        else:
            available = list(cache_data.get("workflows", {}).keys())
            logger.error(f"Workflow {workflow_id} not in cache. Available: {available}")
            return None
    except Exception as e:
        logger.error(f"Failed to load workflow from cache: {e}")
        return None


def _clear_workflow_cache() -> None:
    """Clear the workflow cache file."""
    try:
        if os.path.exists(MOUNTED_WORKFLOWS_CACHE):
            os.remove(MOUNTED_WORKFLOWS_CACHE)
            logger.info("Cleared workflow cache")
    except Exception as e:
        logger.warning(f"Failed to clear workflow cache: {e}")


def _save_credentials_to_cache(credentials: List[Dict[str, Any]], backup_id: int) -> bool:
    """Save credential data to cache file for later extraction."""
    try:
        cache_data = {
            "backup_id": backup_id,
            "credentials": {c["id"]: c for c in credentials},  # Index by ID for fast lookup
            "cached_at": datetime.now(UTC).isoformat(),
        }
        with open(MOUNTED_CREDENTIALS_CACHE, 'w') as f:
            json.dump(cache_data, f)
        logger.info(f"Cached {len(credentials)} credentials for backup {backup_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save credential cache: {e}")
        return False


def _load_credential_from_cache(credential_id: str, backup_id: int) -> Optional[Dict[str, Any]]:
    """Load a specific credential from the cache file."""
    try:
        if not os.path.exists(MOUNTED_CREDENTIALS_CACHE):
            logger.error("Credential cache file not found")
            return None

        with open(MOUNTED_CREDENTIALS_CACHE, 'r') as f:
            cache_data = json.load(f)

        # Verify it's for the right backup
        if cache_data.get("backup_id") != backup_id:
            logger.warning(f"Cache is for backup {cache_data.get('backup_id')}, not {backup_id}")

        credential = cache_data.get("credentials", {}).get(credential_id)
        if credential:
            logger.info(f"Found credential {credential_id} in cache")
            return credential
        else:
            available = list(cache_data.get("credentials", {}).keys())
            logger.error(f"Credential {credential_id} not in cache. Available: {available}")
            return None
    except Exception as e:
        logger.error(f"Failed to load credential from cache: {e}")
        return None


def _clear_credential_cache() -> None:
    """Clear the credential cache file."""
    try:
        if os.path.exists(MOUNTED_CREDENTIALS_CACHE):
            os.remove(MOUNTED_CREDENTIALS_CACHE)
            logger.info("Cleared credential cache")
    except Exception as e:
        logger.warning(f"Failed to clear credential cache: {e}")


# ============================================================================
# In-app database restore safety helpers
# ============================================================================

# Timeouts for subprocesses in the in-app restore path (seconds)
PG_LONG_TIMEOUT = 3 * 60 * 60   # pg_dump / pg_restore of a large database
PG_SHORT_TIMEOUT = 120          # psql admin statements, pg_restore --list
DOCKER_TIMEOUT = 180            # stopping / starting the n8n container

# Cap on stderr returned to API clients
_STDERR_LIMIT = 8000

_SAFE_DB_NAME = re.compile(r"^[A-Za-z0-9_]+$")

# certbot's configuration root as mounted in the management container
LETSENCRYPT_ROOT = "/etc/letsencrypt"

MANAGEMENT_DB_REFUSAL = (
    "The management database ({name}) cannot be restored from inside the management "
    "console, because the console itself is running on it. Use the bare-metal "
    "procedure instead: download the backup (Bare Metal > Download Recovery Archive), "
    "stop the stack, extract the archive and run ./restore.sh (see the Backup Guide, "
    "'Restoring the management database')."
)


def _database_name_from_url(url: str, default: str) -> str:
    try:
        from sqlalchemy.engine import make_url
        return make_url(url).database or default
    except Exception:
        return default


def management_database_name() -> str:
    """Name of the management console's own database (never restored in-app)."""
    return _database_name_from_url(settings.database_url, "n8n_management")


def n8n_database_name() -> str:
    """Name of the live n8n database (the only database restorable in-app)."""
    return _database_name_from_url(settings.n8n_database_url, "n8n")


def _exc_text(e: BaseException) -> str:
    """str(e), or the exception type when str() is empty (e.g. TimeoutError())."""
    return str(e) or repr(e)


def _tail(text: str, limit: int = _STDERR_LIMIT) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "...(truncated)...\n" + text[-limit:]


async def _run_subprocess(
    cmd: List[str],
    env: Optional[Dict[str, str]] = None,
    timeout: float = PG_SHORT_TIMEOUT,
) -> Tuple[int, str, str]:
    """
    Run a command without blocking the event loop.

    Returns (returncode, stdout, stderr). A timeout kills the process and is
    reported as returncode -1.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", f"{cmd[0]} timed out after {int(timeout)}s and was killed"
    return (
        proc.returncode,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def _extract_tar_sync(archive_path: str, dest_dir: str) -> None:
    """
    Extract a backup archive (decrypting it first if it is encrypted),
    refusing absolute paths / path traversal where supported.
    """
    with open_backup_archive(archive_path) as tar:
        safe_extract(tar, dest_dir)


def _extract_plain_tar_sync(archive_path: str, dest_dir: str) -> None:
    """Extract an already-decrypted .tar.gz, refusing path traversal."""
    with tarfile.open(archive_path, "r:gz") as tar:
        safe_extract(tar, dest_dir)


def _remove_restore_containers_sync() -> int:
    """
    Remove (with their anonymous volumes) every temporary restore container:
    those carrying RESTORE_CONTAINER_LABEL, plus one named
    RESTORE_CONTAINER_NAME created before the label existed.
    """
    ids = set()
    for filt in (f"label={RESTORE_CONTAINER_LABEL}", f"name=^/?{RESTORE_CONTAINER_NAME}$"):
        result = subprocess.run(["docker", "ps", "-aq", "--filter", filt], capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
        if result.returncode == 0:
            ids.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    removed = 0
    for cid in sorted(ids):
        result = subprocess.run(["docker", "rm", "-f", "-v", cid], capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
        if result.returncode == 0:
            removed += 1
        else:
            logger.warning(f"Could not remove restore container {cid}: {result.stderr.strip()}")
    return removed


async def cleanup_leftover_restore_containers() -> int:
    """
    Startup hook: remove temporary restore containers left behind by a crash
    or restart (nothing can be mounted right after startup). Returns how many
    were removed; never raises.
    """
    try:
        removed = await asyncio.to_thread(_remove_restore_containers_sync)
    except Exception as e:
        logger.warning(f"Could not clean up leftover restore containers: {e}")
        return 0
    if removed:
        logger.info(f"Removed {removed} leftover temporary restore container(s)")
    return removed


def _remove_path_sync(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _replace_entry_sync(src: str, dst: str) -> None:
    """
    Replace dst with a copy of src (symlinks preserved) without a window in
    which a failed copy leaves dst missing: copy to dst.new, move dst to
    dst.old, move dst.new into place, then remove dst.old. On failure the
    original dst is put back.
    """
    new = dst + ".new"
    old = dst + ".old"
    for leftover in (new, old):
        if os.path.lexists(leftover):
            _remove_path_sync(leftover)

    try:
        if os.path.isdir(src) and not os.path.islink(src):
            shutil.copytree(src, new, symlinks=True)
        else:
            shutil.copy2(src, new, follow_symlinks=False)
    except Exception:
        if os.path.lexists(new):
            _remove_path_sync(new)
        raise

    had_old = os.path.lexists(dst)
    if had_old:
        os.rename(dst, old)
    try:
        os.rename(new, dst)
    except Exception:
        if had_old:
            os.rename(old, dst)
        if os.path.lexists(new):
            _remove_path_sync(new)
        raise
    if had_old:
        try:
            _remove_path_sync(old)
        except OSError as e:
            logger.warning(f"Could not remove {old}: {e}")


def _restore_letsencrypt_tree_sync(src_root: str, dest_root: str, backup_dir: Optional[str]) -> Dict[str, Any]:
    """
    Replace each top-level entry of dest_root (/etc/letsencrypt) with the
    archive's copy, preserving symlinks, so live/ keeps pointing into archive/
    and certbot can still renew the restored lineages.
    """
    backup_created = None
    if backup_dir and os.path.isdir(dest_root):
        os.makedirs(backup_dir, exist_ok=True)
        backup_created = os.path.join(
            backup_dir, f"letsencrypt.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copytree(dest_root, backup_created, symlinks=True)

    os.makedirs(dest_root, exist_ok=True)
    for entry in sorted(os.listdir(src_root)):
        _replace_entry_sync(os.path.join(src_root, entry), os.path.join(dest_root, entry))

    return {
        "status": "success",
        "config_path": "letsencrypt/",
        "target_path": dest_root,
        "backup_created": backup_created,
        "message": "Restored the complete certificate tree (symlinks preserved)",
    }


def _find_n8n_container_sync():
    """Return the n8n docker container object, or None if it cannot be identified."""
    import docker
    from docker.errors import NotFound

    client = docker.from_env()
    for name in (os.environ.get("N8N_CONTAINER"), "n8n"):
        if not name:
            continue
        try:
            return client.containers.get(name)
        except NotFound:
            continue
    matches = client.containers.list(all=True, filters={"label": "com.docker.compose.service=n8n"})
    if len(matches) == 1:
        return matches[0]
    return None


def _container_running_sync(container) -> bool:
    """Return True if the container is currently running."""
    container.reload()
    return container.status == "running"


def _stop_container_sync(container) -> None:
    container.stop(timeout=60)


def _start_container_sync(container) -> None:
    container.start()


class RestoreService:
    """Service for restoring workflows from backups."""

    def __init__(self, db: AsyncSession, n8n_db: Optional[AsyncSession] = None):
        self.db = db
        self.n8n_db = n8n_db
        self.backup_service = BackupService(db)
        self._container_ready = False

    # ============================================================================
    # Container Management
    # ============================================================================

    def _get_postgres_network(self) -> str:
        """Get the Docker network name from the postgres container."""
        try:
            # Get network from POSTGRES_HOST container (e.g., n8n_postgres)
            postgres_host = os.environ.get("POSTGRES_HOST", "n8n_postgres")
            cmd = [
                "docker", "inspect", postgres_host,
                "--format", "{{range $key, $value := .NetworkSettings.Networks}}{{$key}}{{end}}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
            if result.returncode == 0 and result.stdout.strip():
                network = result.stdout.strip()
                logger.info(f"Found network from postgres container: {network}")
                return network
        except Exception as e:
            logger.warning(f"Failed to get network from postgres container: {e}")

        # Fallback: try to find network with n8n in the name
        try:
            cmd = ["docker", "network", "ls", "--format", "{{.Name}}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
            for network in result.stdout.strip().split('\n'):
                if 'n8n' in network.lower():
                    logger.info(f"Found n8n network by search: {network}")
                    return network
        except Exception:
            pass

        # Final fallback: use bridge network (restore container doesn't need to connect to anything)
        logger.warning("No n8n network found, using bridge network. This should still work since restore container is standalone.")
        return "bridge"

    async def spin_up_restore_container(self) -> bool:
        """
        Create and start a temporary PostgreSQL container for restore operations.
        Always removes existing container and creates fresh to avoid stale state.
        Returns True if successful.

        The container has no network (all access is `docker exec`), a random
        per-run superuser password passed through the environment (never on
        the command line), and RESTORE_CONTAINER_LABEL. If it does not become
        ready it is removed together with its anonymous data volume.
        """
        logger.info("Starting restore container...")
        created = False
        ready = False
        try:
            # Always remove existing container and create fresh
            await asyncio.to_thread(_remove_restore_containers_sync)

            # Create new container (no network, no ports: we use docker exec)
            logger.info("Creating new restore container...")
            create_cmd = [
                "docker", "run", "-d",
                "--name", RESTORE_CONTAINER_NAME,
                "--label", RESTORE_CONTAINER_LABEL,
                "--network", "none",
                "--security-opt", "apparmor=unconfined",
                "-e", f"POSTGRES_USER={RESTORE_DB_USER}",
                "-e", "POSTGRES_PASSWORD",
                "-e", f"POSTGRES_DB={RESTORE_DB_NAME}",
                RESTORE_CONTAINER_IMAGE,
            ]
            env = {**os.environ, "POSTGRES_PASSWORD": secrets.token_urlsafe(24)}
            logger.info(f"Running: {' '.join(create_cmd)}")
            result = await _proc.run(create_cmd, capture_output=True, text=True, env=env, timeout=_proc.DOCKER_RUN_TIMEOUT)
            created = True  # a failed run can still leave a created container behind
            if result.returncode != 0:
                logger.error(f"Docker run failed (exit code {result.returncode}): stdout={result.stdout}, stderr={result.stderr}")
                return False
            logger.info(f"Container created: {result.stdout.strip()}")

            # Wait for PostgreSQL to be ready
            await self._wait_for_postgres_ready()
            self._container_ready = True
            ready = True
            logger.info("Restore container is ready")
            return True

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            logger.error(f"Failed to start restore container: {stderr}")
            return False
        except Exception as e:
            logger.error(f"Error starting restore container: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            if created and not ready:
                await asyncio.to_thread(_remove_restore_containers_sync)

    async def _wait_for_postgres_ready(self, timeout: int = 30) -> None:
        """Wait for PostgreSQL to accept connections."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            # First check if container is still running
            check_running = await _proc.run(
                ["docker", "ps", "--filter", f"name={RESTORE_CONTAINER_NAME}", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT
            )
            if RESTORE_CONTAINER_NAME not in check_running.stdout:
                # Container stopped - get logs to see why
                logs_result = await _proc.run(
                    ["docker", "logs", "--tail", "50", RESTORE_CONTAINER_NAME],
                    capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT
                )
                logger.error(f"Restore container stopped unexpectedly. Logs:\n{logs_result.stdout}\n{logs_result.stderr}")
                raise Exception(f"Restore container stopped unexpectedly. Check logs for details.")

            try:
                check_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "pg_isready", "-U", RESTORE_DB_USER
                ]
                result = await _proc.run(check_cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
                if result.returncode == 0:
                    return
            except Exception as e:
                logger.debug(f"pg_isready check failed: {e}")
            await asyncio.sleep(1)

        # Timeout - get container status and logs
        logs_result = await _proc.run(
            ["docker", "logs", "--tail", "50", RESTORE_CONTAINER_NAME],
            capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT
        )
        logger.error(f"Timeout waiting for PostgreSQL. Container logs:\n{logs_result.stdout}\n{logs_result.stderr}")
        raise Exception("Timeout waiting for PostgreSQL to be ready")

    async def teardown_restore_container(self) -> bool:
        """Stop and remove the restore container."""
        logger.info("Tearing down restore container...")

        try:
            # Stop container (with timeout)
            stop_cmd = ["docker", "stop", "-t", "10", RESTORE_CONTAINER_NAME]
            stop_result = await asyncio.to_thread(
                subprocess.run, stop_cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT
            )
            if stop_result.returncode != 0:
                logger.warning(f"Failed to stop container: {stop_result.stderr}")

            # Remove container and its anonymous data volume (force to ensure cleanup)
            rm_cmd = ["docker", "rm", "-f", "-v", RESTORE_CONTAINER_NAME]
            rm_result = await asyncio.to_thread(
                subprocess.run, rm_cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT
            )
            if rm_result.returncode != 0:
                logger.warning(f"Failed to remove container: {rm_result.stderr}")
                # If the container doesn't exist, that's fine
                if "No such container" not in rm_result.stderr:
                    return False

            self._container_ready = False
            logger.info("Restore container removed")
            return True

        except Exception as e:
            logger.warning(f"Error tearing down restore container: {e}")
            return False

    async def is_container_running(self) -> bool:
        """Check if restore container is running."""
        try:
            check_cmd = ["docker", "ps", "--filter", f"name={RESTORE_CONTAINER_NAME}", "--format", "{{.Names}}"]
            result = await _proc.run(check_cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
            return RESTORE_CONTAINER_NAME in result.stdout
        except Exception:
            return False

    # ============================================================================
    # Mount/Unmount Operations
    # ============================================================================

    async def mount_backup(self, backup_id: int) -> Dict[str, Any]:
        """
        Mount a backup for browsing and selective restore.

        This spins up the restore container, loads the backup ONCE,
        and keeps it available until unmounted.
        """
        global _mounted_backup_id, _mounted_backup_info

        logger.info(f"Mounting backup {backup_id}...")

        # Check if already mounted
        if _mounted_backup_id is not None:
            if _mounted_backup_id == backup_id:
                # Same backup already mounted
                return {
                    "status": "success",
                    "message": "Backup already mounted",
                    "backup_id": backup_id,
                    "backup_info": _mounted_backup_info,
                }
            else:
                # Different backup mounted - unmount first
                logger.info(f"Unmounting previous backup {_mounted_backup_id} before mounting {backup_id}")
                await self.unmount_backup()

        # Get backup info
        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return {"status": "failed", "error": f"Backup {backup_id} not found"}

        if not os.path.exists(backup.filepath):
            return {"status": "failed", "error": f"Backup file not found: {backup.filepath}"}

        try:
            # Spin up container
            if not await self.spin_up_restore_container():
                return {"status": "failed", "error": "Failed to start restore container"}

            # Load the backup
            if not await self.load_backup_to_restore_container(backup_id):
                await self.teardown_restore_container()
                return {"status": "failed", "error": "Failed to load backup into container"}

            # Load FULL workflow data and save to cache
            full_workflows = await self.load_all_workflows_full_data()
            if full_workflows:
                _save_workflows_to_cache(full_workflows, backup_id)
                logger.info(f"Cached {len(full_workflows)} workflows for backup {backup_id}")
            else:
                logger.warning("No workflows found or failed to load workflow data")

            # Load FULL credential data and save to cache
            full_credentials = await self.load_all_credentials_full_data()
            if full_credentials:
                _save_credentials_to_cache(full_credentials, backup_id)
                logger.info(f"Cached {len(full_credentials)} credentials for backup {backup_id}")
            else:
                logger.warning("No credentials found or failed to load credential data")

            # Prepare workflow metadata for UI (don't include nodes/connections)
            workflows_for_ui = [
                {
                    "id": w["id"],
                    "name": w["name"],
                    "active": w.get("active", False),
                    "archived": w.get("archived", False),
                    "created_at": w.get("created_at"),
                    "updated_at": w.get("updated_at"),
                }
                for w in full_workflows
            ]

            # Prepare credential metadata for UI (no sensitive data field)
            credentials_for_ui = [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "type": c["type"],
                    "created_at": c.get("created_at"),
                    "updated_at": c.get("updated_at"),
                }
                for c in full_credentials
            ]

            # Store mounted state
            _mounted_backup_id = backup_id
            _mounted_backup_info = {
                "backup_id": backup_id,
                "filename": backup.filename,
                "created_at": backup.created_at.isoformat() if backup.created_at else None,
                "backup_type": backup.backup_type,
                "workflow_count": len(full_workflows),
                "credential_count": len(full_credentials),
                "mounted_at": datetime.now(UTC).isoformat(),
            }

            logger.info(f"Backup {backup_id} mounted successfully with {len(full_workflows)} workflows and {len(full_credentials)} credentials")

            return {
                "status": "success",
                "message": f"Backup mounted with {len(full_workflows)} workflows and {len(full_credentials)} credentials",
                "backup_id": backup_id,
                "backup_info": _mounted_backup_info,
                "workflows": workflows_for_ui,
                "credentials": credentials_for_ui,
            }

        except Exception as e:
            logger.error(f"Failed to mount backup: {e}")
            await self.teardown_restore_container()
            _mounted_backup_id = None
            _mounted_backup_info = None
            return {"status": "failed", "error": str(e)}

    async def unmount_backup(self) -> Dict[str, Any]:
        """
        Unmount the currently mounted backup.

        Tears down the restore container and cleans up.
        Always attempts to stop the container regardless of memory state.
        """
        global _mounted_backup_id, _mounted_backup_info

        backup_id = _mounted_backup_id
        container_was_running = await self.is_container_running()

        # If no memory state AND no container running, nothing to do
        if _mounted_backup_id is None and not container_was_running:
            return {"status": "success", "message": "No backup was mounted"}

        logger.info(f"Unmounting backup {backup_id or 'unknown'}...")

        try:
            # Always try to tear down the container if it exists
            if container_was_running:
                await self.teardown_restore_container()

            # Clear mounted state
            _mounted_backup_id = None
            _mounted_backup_info = None

            # Clear workflow and credential caches
            _clear_workflow_cache()
            _clear_credential_cache()

            logger.info(f"Backup {backup_id or 'unknown'} unmounted successfully")
            return {"status": "success", "message": f"Backup unmounted and container stopped"}

        except Exception as e:
            logger.error(f"Failed to unmount backup: {e}")
            # Clear state and cache anyway
            _clear_workflow_cache()
            _clear_credential_cache()
            _mounted_backup_id = None
            _mounted_backup_info = None
            return {"status": "failed", "error": str(e)}

    def get_mount_status(self) -> Dict[str, Any]:
        """Get current mount status."""
        return get_mounted_backup_status()

    def is_backup_mounted(self, backup_id: int) -> bool:
        """Check if a specific backup is currently mounted."""
        global _mounted_backup_id
        # First check memory state
        if _mounted_backup_id == backup_id:
            return True
        # If memory state doesn't match, check if container is actually running
        # This handles cases where state was lost (worker restart, etc.)
        try:
            check_cmd = ["docker", "ps", "--filter", f"name={RESTORE_CONTAINER_NAME}", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT)
            if RESTORE_CONTAINER_NAME in result.stdout:
                # Container is running - update memory state and allow operation
                # We can't know for sure which backup was loaded, but if container is running
                # with data, we should allow operations
                logger.info(f"Restore container is running, allowing operations for backup {backup_id}")
                return True
        except Exception as e:
            logger.warning(f"Failed to check container status: {e}")
        return False

    # ============================================================================
    # Backup Loading
    # ============================================================================

    async def load_backup_to_restore_container(self, backup_id: int) -> bool:
        """
        Load a backup into the restore container.
        Returns True if successful.
        """
        logger.info(f"Loading backup {backup_id} into restore container...")

        # Get backup info
        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            logger.error(f"Backup {backup_id} not found")
            return False

        if not os.path.exists(backup.filepath):
            logger.error(f"Backup file not found: {backup.filepath}")
            return False

        # Ensure container is running
        if not await self.is_container_running():
            if not await self.spin_up_restore_container():
                return False

        try:
            archive_ctx = plaintext_archive(backup.filepath)
            # decrypting a large archive takes a while: keep it off the event loop
            archive_file = await asyncio.to_thread(archive_ctx.__enter__)
        except BackupEncryptionError as e:
            logger.error(f"Cannot open backup {backup_id}: {e}")
            return False
        with contextlib.ExitStack() as stack:
            # removes the decrypted temporary copy (if any) on every return path
            stack.push(archive_ctx)
            try:
                # Reset the database before loading (use separate commands to avoid transaction block error)
                logger.info("Resetting restore database...")
                try:
                    drop_cmd = [
                        "docker", "exec", RESTORE_CONTAINER_NAME,
                        "psql", "-U", RESTORE_DB_USER, "-d", "postgres",
                        "-c", f"DROP DATABASE IF EXISTS {RESTORE_DB_NAME};"
                    ]
                    result = await _proc.run(drop_cmd, capture_output=True, text=True, timeout=_proc.PSQL_TIMEOUT)
                    if result.returncode != 0:
                        logger.warning(f"DROP DATABASE warning: {result.stderr}")

                    create_cmd = [
                        "docker", "exec", RESTORE_CONTAINER_NAME,
                        "psql", "-U", RESTORE_DB_USER, "-d", "postgres",
                        "-c", f"CREATE DATABASE {RESTORE_DB_NAME};"
                    ]
                    result = await _proc.run(create_cmd, capture_output=True, text=True, check=True, timeout=_proc.PSQL_TIMEOUT)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to reset restore database: {e.stderr if hasattr(e, 'stderr') else e}")
                    return False

                # Check if it's a tar archive or a legacy gzipped SQL file
                def archive_members() -> Optional[List[str]]:
                    try:
                        with tarfile.open(archive_file, "r:gz") as tar:
                            return tar.getnames()
                    except tarfile.TarError:
                        return None

                members = await asyncio.to_thread(archive_members)
                is_tar_archive = members is not None
                if is_tar_archive:
                    logger.info(f"Backup archive contains: {members[:10]}...")  # Log first 10 members
                else:
                    logger.info("Not a tar archive, trying legacy format")

                if not is_tar_archive:
                    # Legacy format: gzipped SQL file
                    logger.info("Legacy backup format detected")
                    return await self._load_legacy_backup(backup.filepath)

                # Extract backup archive to temp directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extract tar.gz (in a worker thread)
                    await asyncio.to_thread(_extract_plain_tar_sync, archive_file, temp_dir)

                    # Find the n8n database dump - check multiple possible locations
                    n8n_dump = None
                    possible_paths = [
                        os.path.join(temp_dir, "databases", "n8n.dump"),
                        os.path.join(temp_dir, "n8n.dump"),
                        os.path.join(temp_dir, "databases", "n8n.sql"),
                    ]
                    for path in possible_paths:
                        if os.path.exists(path):
                            n8n_dump = path
                            logger.info(f"Found database dump at: {path}")
                            break

                    if not n8n_dump:
                        # List what we actually found
                        for root, dirs, files in os.walk(temp_dir):
                            for f in files:
                                logger.info(f"Found in archive: {os.path.join(root, f)}")
                        logger.error("No database dump found in backup archive")
                        return False

                    # Copy dump file to container
                    copy_cmd = [
                        "docker", "cp", n8n_dump,
                        f"{RESTORE_CONTAINER_NAME}:/tmp/n8n.dump"
                    ]
                    result = await _proc.run(copy_cmd, capture_output=True, text=True, timeout=_proc.PG_RESTORE_TIMEOUT)
                    if result.returncode != 0:
                        logger.error(f"Failed to copy dump to container: {result.stderr}")
                        return False

                    # Restore the dump using pg_restore (for custom format) or psql (for SQL)
                    if n8n_dump.endswith('.sql'):
                        restore_cmd = [
                            "docker", "exec", RESTORE_CONTAINER_NAME,
                            "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                            "-f", "/tmp/n8n.dump"
                        ]
                    else:
                        restore_cmd = [
                            "docker", "exec", RESTORE_CONTAINER_NAME,
                            "pg_restore",
                            "-U", RESTORE_DB_USER,
                            "-d", RESTORE_DB_NAME,
                            "--clean", "--if-exists",
                            "--no-owner", "--no-acl",
                            "/tmp/n8n.dump"
                        ]

                    result = await _proc.run(restore_cmd, capture_output=True, text=True, timeout=_proc.PG_RESTORE_TIMEOUT)
                    logger.info(f"Restore command output: stdout={result.stdout[:500] if result.stdout else 'none'}, stderr={result.stderr[:500] if result.stderr else 'none'}")

                    # pg_restore often returns non-zero for warnings, only fail on actual errors
                    if result.returncode != 0:
                        if "ERROR" in result.stderr and "already exists" not in result.stderr:
                            logger.error(f"pg_restore failed: {result.stderr}")
                            return False
                        else:
                            logger.warning(f"pg_restore completed with warnings: {result.stderr[:200] if result.stderr else 'none'}")

                    # Verify the restore worked by checking for workflow_entity table
                    verify_cmd = [
                        "docker", "exec", RESTORE_CONTAINER_NAME,
                        "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                        "-t", "-c", "SELECT COUNT(*) FROM workflow_entity;"
                    ]
                    verify_result = await _proc.run(verify_cmd, capture_output=True, text=True, timeout=_proc.PSQL_TIMEOUT)
                    if verify_result.returncode != 0:
                        logger.error(f"Verification failed - workflow_entity table not found: {verify_result.stderr}")
                        return False

                    workflow_count = verify_result.stdout.strip()
                    logger.info(f"Backup {backup_id} loaded successfully. Found {workflow_count} workflows.")
                    return True

            except Exception as e:
                logger.error(f"Failed to load backup: {e}")
                return False

    async def _load_legacy_backup(self, filepath: str) -> bool:
        """Load a legacy (non-archive) backup format."""
        import gzip

        try:
            # Decompress if gzipped
            if filepath.endswith('.gz'):
                def decompress() -> str:
                    with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
                        with gzip.open(filepath, 'rb') as f_in:
                            shutil.copyfileobj(f_in, tmp)
                        return tmp.name

                sql_path = await asyncio.to_thread(decompress)
            else:
                sql_path = filepath

            # Copy to container
            copy_cmd = ["docker", "cp", sql_path, f"{RESTORE_CONTAINER_NAME}:/tmp/backup.sql"]
            await _proc.run(copy_cmd, capture_output=True, check=True, timeout=_proc.PG_RESTORE_TIMEOUT)

            # Restore
            restore_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-f", "/tmp/backup.sql"
            ]
            await _proc.run(restore_cmd, capture_output=True, check=True, timeout=_proc.PG_RESTORE_TIMEOUT)

            return True
        except Exception as e:
            logger.error(f"Failed to load legacy backup: {e}")
            return False

    # ============================================================================
    # Workflow Extraction
    # ============================================================================

    async def list_workflows_in_restore_db(self) -> List[Dict[str, Any]]:
        """
        List all workflows in the restore database.
        Returns list of workflow metadata.
        """
        if not await self.is_container_running():
            logger.error("Restore container not running")
            return []

        try:
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                'SELECT id, name, active, "createdAt", "updatedAt", COALESCE("isArchived", false) FROM workflow_entity ORDER BY name'
            ]
            result = await _proc.run(query_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)

            workflows = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    workflows.append({
                        "id": parts[0],
                        "name": parts[1],
                        "active": parts[2] == 't' if len(parts) > 2 else False,
                        "created_at": parts[3] if len(parts) > 3 else None,
                        "updated_at": parts[4] if len(parts) > 4 else None,
                        "archived": parts[5] == 't' if len(parts) > 5 else False,
                    })

            return workflows

        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return []

    async def load_all_workflows_full_data(self) -> List[Dict[str, Any]]:
        """
        Load ALL workflows with FULL data (nodes, connections, settings) from restore database.
        Used during mount to cache all workflow data.
        """
        if not await self.is_container_running():
            logger.error("Restore container not running")
            return []

        try:
            # Use row_to_json to output each row as JSON - avoids delimiter issues
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                '''SELECT row_to_json(t) FROM (
                    SELECT id, name, active, COALESCE("isArchived", false) as "isArchived",
                           nodes, connections, settings,
                           "staticData", "createdAt", "updatedAt"
                    FROM workflow_entity ORDER BY name
                ) t'''
            ]
            result = await _proc.run(query_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)

            if result.returncode != 0:
                logger.error(f"Failed to query workflows: {result.stderr}")
                return []

            workflows = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    workflows.append({
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "active": row.get("active", False),
                        "archived": row.get("isArchived", False),
                        "nodes": row.get("nodes") or [],
                        "connections": row.get("connections") or {},
                        "settings": row.get("settings") or {},
                        "staticData": row.get("staticData"),
                        "created_at": row.get("createdAt"),
                        "updated_at": row.get("updatedAt"),
                    })
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse workflow JSON: {e}, line: {line[:100]}...")
                    continue

            logger.info(f"Loaded full data for {len(workflows)} workflows")
            return workflows

        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")
            return []

    async def extract_workflow_from_restore_db(self, workflow_id: str, backup_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Extract a specific workflow from the mounted backup.
        First tries cache (populated during mount), falls back to database query.
        """
        # Try to load from cache first (most reliable)
        if backup_id:
            cached = _load_workflow_from_cache(workflow_id, backup_id)
            if cached:
                logger.info(f"Loaded workflow {workflow_id} from cache")
                return cached

        # Fallback: try to load from database if container is running
        if not await self.is_container_running():
            logger.error("Restore container not running and no cache available")
            return None

        logger.info(f"Cache miss for workflow {workflow_id}, querying database...")

        try:
            # Use row_to_json to output as JSON - avoids delimiter issues
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                f'''SELECT row_to_json(t) FROM (
                    SELECT id, name, active, COALESCE("isArchived", false) as "isArchived",
                           nodes, connections, settings,
                           "staticData", "createdAt", "updatedAt"
                    FROM workflow_entity WHERE id = '{workflow_id}'
                ) t'''
            ]
            result = await _proc.run(query_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)

            if not result.stdout.strip():
                # Log available IDs for debugging
                list_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                    "-t", "-A", "-c",
                    "SELECT id FROM workflow_entity"
                ]
                list_result = await _proc.run(list_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)
                available_ids = [id.strip() for id in list_result.stdout.strip().split('\n') if id.strip()]
                logger.error(f"Workflow {workflow_id} not found in database. Available IDs: {available_ids}")
                return None

            # Parse JSON output
            row = json.loads(result.stdout.strip())
            workflow = {
                "id": row.get("id"),
                "name": row.get("name"),
                "active": row.get("active", False),
                "archived": row.get("isArchived", False),
                "nodes": row.get("nodes") or [],
                "connections": row.get("connections") or {},
                "settings": row.get("settings") or {},
                "staticData": row.get("staticData"),
                "createdAt": row.get("createdAt"),
                "updatedAt": row.get("updatedAt"),
            }

            return workflow

        except Exception as e:
            logger.error(f"Failed to extract workflow {workflow_id}: {e}")
            return None

    # ============================================================================
    # Credential Extraction
    # ============================================================================

    async def list_credentials_in_restore_db(self) -> List[Dict[str, Any]]:
        """
        List all credentials in the restore database.
        Returns list of credential metadata (no sensitive data field).
        """
        if not await self.is_container_running():
            logger.error("Restore container not running")
            return []

        try:
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                'SELECT id, name, type, "createdAt", "updatedAt" FROM credentials_entity ORDER BY name'
            ]
            result = await _proc.run(query_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)

            credentials = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    credentials.append({
                        "id": parts[0],
                        "name": parts[1],
                        "type": parts[2] if len(parts) > 2 else None,
                        "created_at": parts[3] if len(parts) > 3 else None,
                        "updated_at": parts[4] if len(parts) > 4 else None,
                    })

            return credentials

        except Exception as e:
            logger.error(f"Failed to list credentials: {e}")
            return []

    async def load_all_credentials_full_data(self) -> List[Dict[str, Any]]:
        """
        Load ALL credentials with FULL data from restore database.
        Used during mount to cache all credential data.
        NOTE: The 'data' field contains encrypted credential values.
        """
        if not await self.is_container_running():
            logger.error("Restore container not running")
            return []

        try:
            # Use row_to_json to output each row as JSON
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                '''SELECT row_to_json(t) FROM (
                    SELECT id, name, type, data, "createdAt", "updatedAt"
                    FROM credentials_entity ORDER BY name
                ) t'''
            ]
            result = await _proc.run(query_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)

            if result.returncode != 0:
                logger.error(f"Failed to query credentials: {result.stderr}")
                return []

            credentials = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    credentials.append({
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "type": row.get("type"),
                        "data": row.get("data"),  # Encrypted credential data
                        "created_at": row.get("createdAt"),
                        "updated_at": row.get("updatedAt"),
                    })
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse credential JSON: {e}, line: {line[:100]}...")
                    continue

            logger.info(f"Loaded full data for {len(credentials)} credentials")
            return credentials

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return []

    async def extract_credential_from_restore_db(self, credential_id: str, backup_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Extract a specific credential from the mounted backup.
        First tries cache (populated during mount), falls back to database query.
        """
        # Try to load from cache first (most reliable)
        if backup_id:
            cached = _load_credential_from_cache(credential_id, backup_id)
            if cached:
                logger.info(f"Loaded credential {credential_id} from cache")
                return cached

        # Fallback: try to load from database if container is running
        if not await self.is_container_running():
            logger.error("Restore container not running and no cache available")
            return None

        logger.info(f"Cache miss for credential {credential_id}, querying database...")

        try:
            # Use row_to_json to output as JSON
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                f'''SELECT row_to_json(t) FROM (
                    SELECT id, name, type, data, "createdAt", "updatedAt"
                    FROM credentials_entity WHERE id = '{credential_id}'
                ) t'''
            ]
            result = await _proc.run(query_cmd, capture_output=True, text=True, timeout=_proc.QUERY_TIMEOUT)

            if not result.stdout.strip():
                logger.error(f"Credential {credential_id} not found in database")
                return None

            # Parse JSON output
            row = json.loads(result.stdout.strip())
            credential = {
                "id": row.get("id"),
                "name": row.get("name"),
                "type": row.get("type"),
                "data": row.get("data"),
                "created_at": row.get("createdAt"),
                "updated_at": row.get("updatedAt"),
            }

            return credential

        except Exception as e:
            logger.error(f"Failed to extract credential {credential_id}: {e}")
            return None

    async def download_credential_as_json(
        self,
        backup_id: int,
        credential_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract a credential from backup and return it as JSON for download.
        Requires the backup to be mounted first.

        NOTE: The returned data contains encrypted credential values.
        To use this credential, you may need to re-enter the actual values in n8n.
        """
        try:
            # Check if the correct backup is mounted
            if not await asyncio.to_thread(self.is_backup_mounted, backup_id):
                logger.error(f"Backup {backup_id} is not mounted")
                return None

            # Verify container is running
            if not await self.is_container_running():
                logger.error("Restore container is not running")
                return None

            # Extract credential (uses cache from mount)
            credential = await self.extract_credential_from_restore_db(credential_id, backup_id)
            if not credential:
                return None

            # Prepare for export
            # Note: 'data' field is encrypted - user will need to reconfigure in n8n
            export_credential = {
                "name": credential["name"],
                "type": credential["type"],
                "data": credential.get("data", {}),
                "_note": "The 'data' field contains encrypted values from the backup. You may need to reconfigure these credentials after import.",
            }

            return export_credential

        except Exception as e:
            logger.error(f"Failed to download credential: {e}")
            return None

    # ============================================================================
    # Workflow Restoration
    # ============================================================================

    async def restore_workflow_to_n8n(
        self,
        backup_id: int,
        workflow_id: str,
        rename_format: str = "{name}_backup_{date}",
    ) -> Dict[str, Any]:
        """
        Restore a specific workflow from a backup to the running n8n instance.

        Args:
            backup_id: The backup to restore from
            workflow_id: The workflow ID to restore
            rename_format: Format for the new workflow name
                          Placeholders: {name}, {date}, {id}

        Returns:
            Dict with status and details
        """
        global _mounted_backup_id
        logger.info(f"Restoring workflow {workflow_id} from backup {backup_id}")

        try:
            # Check if the correct backup is mounted
            if not await asyncio.to_thread(self.is_backup_mounted, backup_id):
                return {
                    "status": "failed",
                    "error": f"Backup {backup_id} is not mounted. Please mount the backup first.",
                }

            # Verify container is running
            if not await self.is_container_running():
                return {
                    "status": "failed",
                    "error": "Restore container is not running. Please remount the backup.",
                }

            # Step 3: Extract the workflow (uses cache from mount)
            workflow = await self.extract_workflow_from_restore_db(workflow_id, backup_id)
            if not workflow:
                return {"status": "failed", "error": f"Workflow {workflow_id} not found in backup"}

            # Step 4: Get backup date for naming
            backup = await self.backup_service.get_backup(backup_id)
            backup_date = backup.created_at.strftime("%Y%m%d") if backup else datetime.now().strftime("%Y%m%d")

            # Step 5: Rename workflow
            original_name = workflow["name"]
            new_name = rename_format.format(
                name=original_name,
                date=backup_date,
                id=workflow_id[:8],
            )
            workflow["name"] = new_name

            # Step 6: Prepare workflow for import (remove ID, dates, etc.)
            # Note: Don't include 'active' field - n8n API treats it as read-only
            import_workflow = {
                "name": new_name,
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow.get("settings", {}),
            }

            # Step 7: Push to n8n via API
            n8n_service = N8nApiService()
            result = await n8n_service.create_workflow(import_workflow)

            # Check for success - the API returns workflow_id, not id
            if result.get("success") and result.get("workflow_id"):
                logger.info(f"Workflow restored successfully as '{new_name}' with ID {result['workflow_id']}")
                return {
                    "status": "success",
                    "original_name": original_name,
                    "new_name": new_name,
                    "new_workflow_id": result["workflow_id"],
                    "message": f"Workflow restored as '{new_name}'",
                }
            else:
                error_msg = result.get("error", "n8n API did not return workflow ID")
                logger.error(f"n8n API error: {error_msg}")
                return {"status": "failed", "error": error_msg}

        except Exception as e:
            logger.error(f"Failed to restore workflow: {e}")
            return {"status": "failed", "error": str(e)}

        finally:
            # Note: We don't teardown immediately - allow multiple restores from same backup
            pass

    async def download_workflow_as_json(
        self,
        backup_id: int,
        workflow_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract a workflow from backup and return it as JSON for download.
        Requires the backup to be mounted first.
        """
        try:
            # Check if the correct backup is mounted
            if not await asyncio.to_thread(self.is_backup_mounted, backup_id):
                logger.error(f"Backup {backup_id} is not mounted")
                return None

            # Verify container is running
            if not await self.is_container_running():
                logger.error("Restore container is not running")
                return None

            # Extract workflow (uses cache from mount)
            workflow = await self.extract_workflow_from_restore_db(workflow_id, backup_id)
            if not workflow:
                return None

            # Prepare for export (n8n-compatible format)
            export_workflow = {
                "name": workflow["name"],
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow.get("settings", {}),
                "active": False,
            }

            return export_workflow

        except Exception as e:
            logger.error(f"Failed to download workflow: {e}")
            return None

    # ============================================================================
    # Batch Operations
    # ============================================================================

    async def restore_multiple_workflows(
        self,
        backup_id: int,
        workflow_ids: List[str],
        rename_format: str = "{name}_backup_{date}",
    ) -> Dict[str, Any]:
        """
        Restore multiple workflows from a backup.
        """
        results = {
            "total": len(workflow_ids),
            "successful": 0,
            "failed": 0,
            "workflows": [],
        }

        try:
            # Setup once
            if not await self.is_container_running():
                if not await self.spin_up_restore_container():
                    return {"status": "failed", "error": "Failed to start restore container"}

            if not await self.load_backup_to_restore_container(backup_id):
                return {"status": "failed", "error": "Failed to load backup"}

            # Restore each workflow
            for workflow_id in workflow_ids:
                result = await self.restore_workflow_to_n8n(backup_id, workflow_id, rename_format)
                results["workflows"].append({
                    "workflow_id": workflow_id,
                    **result,
                })
                if result["status"] == "success":
                    results["successful"] += 1
                else:
                    results["failed"] += 1

            results["status"] = "success" if results["failed"] == 0 else "partial"
            return results

        except Exception as e:
            logger.error(f"Failed batch restore: {e}")
            return {"status": "failed", "error": str(e)}

        finally:
            # Cleanup after batch
            await self.teardown_restore_container()

    # ============================================================================
    # Session Management
    # ============================================================================

    async def cleanup_if_idle(self, idle_minutes: int = 10) -> bool:
        """
        Clean up restore container if it's been idle.
        Called periodically by scheduler.
        """
        # Implementation would track last activity time
        # For now, just check if container is running and tear down
        if await self.is_container_running():
            logger.info("Cleaning up idle restore container")
            return await self.teardown_restore_container()
        return True

    # ============================================================================
    # Phase 4: Full System Restore
    # ============================================================================

    async def extract_backup_archive(self, backup_id: int) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Extract a backup archive to a temp directory.
        Returns (temp_dir_path, metadata_dict) or (None, error_dict).

        The request's DB transaction is ended before extracting, and the
        extraction runs in a worker thread, so a long extraction neither holds
        locks on the management database nor blocks the event loop.
        """
        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return None, {"error": "Backup not found"}
        filepath = backup.filepath

        # Release the snapshot/locks taken by the lookup above.
        await self.db.commit()

        if not filepath or not os.path.exists(filepath):
            return None, {"error": f"Backup file not found: {filepath}"}

        temp_dir = tempfile.mkdtemp(prefix="n8n_restore_")
        try:
            await asyncio.to_thread(_extract_tar_sync, filepath, temp_dir)

            # Read metadata
            metadata_path = os.path.join(temp_dir, "metadata.json")
            metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

            return temp_dir, metadata

        except Exception as e:
            logger.error(f"Failed to extract backup: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, {"error": str(e)}

    async def list_config_files_in_backup(self, backup_id: int) -> List[Dict[str, Any]]:
        """
        List config files available in a backup.
        """
        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return []

        try:
            config_files = []
            config_dir = os.path.join(temp_dir, "config")

            if os.path.exists(config_dir):
                for filename in os.listdir(config_dir):
                    filepath = os.path.join(config_dir, filename)
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        config_files.append({
                            "name": filename,
                            "path": f"config/{filename}",
                            "size": stat.st_size,
                            "exists_in_backup": True,
                        })

            # Check SSL certificates
            ssl_dir = os.path.join(temp_dir, "ssl")
            if os.path.exists(ssl_dir):
                for domain in os.listdir(ssl_dir):
                    domain_path = os.path.join(ssl_dir, domain)
                    if os.path.isdir(domain_path):
                        for cert_file in os.listdir(domain_path):
                            cert_path = os.path.join(domain_path, cert_file)
                            if os.path.isfile(cert_path):
                                stat = os.stat(cert_path)
                                config_files.append({
                                    "name": f"{domain}/{cert_file}",
                                    "path": f"ssl/{domain}/{cert_file}",
                                    "size": stat.st_size,
                                    "exists_in_backup": True,
                                    "is_ssl": True,
                                })

            return config_files

        finally:
            # Cleanup temp dir
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def extract_config_file_content(
        self,
        backup_id: int,
        config_path: str,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Extract a specific config file's content from a backup archive.

        Args:
            backup_id: The backup to extract from
            config_path: Path within backup (e.g., "config/.env" or "config/nginx.conf")

        Returns:
            Tuple of (file_content_bytes, filename) or (None, None) if not found
        """
        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            logger.error(f"Failed to extract backup archive: {metadata}")
            return None, None

        try:
            # The config_path should be relative to the archive root
            source_path = os.path.join(temp_dir, config_path)
            logger.info(f"Looking for config file at: {source_path}")

            if not os.path.exists(source_path):
                logger.error(f"Config file not found: {source_path}")
                # List what we have for debugging
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        logger.debug(f"Available in archive: {os.path.join(root, f)}")
                return None, None

            # Read the file content
            with open(source_path, 'rb') as f:
                content = f.read()

            # Get just the filename for the download
            filename = os.path.basename(config_path)
            logger.info(f"Extracted config file: {filename} ({len(content)} bytes)")

            return content, filename

        except Exception as e:
            logger.error(f"Failed to extract config file content: {e}")
            return None, None

        finally:
            # Cleanup temp dir
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def restore_config_file(
        self,
        backup_id: int,
        config_path: str,
        target_path: Optional[str] = None,
        create_backup: bool = True,
    ) -> Dict[str, Any]:
        """
        Restore a specific config file from backup.

        Args:
            backup_id: The backup to restore from
            config_path: Path within backup (e.g., "config/.env")
            target_path: Where to restore (if None, uses default location)
            create_backup: If True, backs up existing file before overwriting

        Returns:
            Dict with status and details
        """
        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return {"status": "failed", "error": metadata.get("error", "Extract failed")}

        try:
            return self._restore_config_from_dir(temp_dir, config_path, target_path, create_backup)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _restore_config_from_dir(
        self,
        temp_dir: str,
        config_path: str,
        target_path: Optional[str] = None,
        create_backup: bool = True,
    ) -> Dict[str, Any]:
        """Restore one config/SSL file from an already-extracted archive directory."""
        try:
            source_path = os.path.realpath(os.path.join(temp_dir, config_path))
            if not source_path.startswith(os.path.realpath(temp_dir) + os.sep):
                return {"status": "failed", "config_path": config_path, "error": f"Invalid config path: {config_path}"}
            if not os.path.exists(source_path):
                return {"status": "failed", "config_path": config_path, "error": f"Config file not found in backup: {config_path}"}

            # Determine target path
            if not target_path:
                # Map backup paths to host paths
                # Using /app/host_project/ which is a directory mount (more reliable than file mounts)
                path_mappings = {
                    # Core config files
                    "config/.env": "/app/host_project/.env",
                    "config/docker-compose.yaml": "/app/host_project/docker-compose.yaml",
                    "config/nginx.conf": "/app/host_project/nginx.conf",
                    "config/nginx-router.conf": "/app/host_project/nginx-router.conf",
                    "config/nginx-public.conf": "/app/host_project/nginx-public.conf",
                    "config/.filebrowser.json": "/app/host_project/.filebrowser.json",
                    "config/init-db.sh": "/app/host_project/init-db.sh",
                    # DNS credential files
                    "config/cloudflare.ini": "/app/host_project/cloudflare.ini",
                    "config/route53.ini": "/app/host_project/route53.ini",
                    "config/digitalocean.ini": "/app/host_project/digitalocean.ini",
                    "config/google.json": "/app/host_project/google.json",
                    # Optional service configs
                    "config/tailscale-serve.json": "/app/host_project/tailscale-serve.json",
                    "config/dozzle/users.yml": "/app/host_project/dozzle/users.yml",
                    "config/ntfy/server.yml": "/app/host_project/ntfy/server.yml",
                    "config/filebrowser.db": "/app/host_project/filebrowser.db",
                }
                target_path = path_mappings.get(config_path)

                # Handle SSL paths - map to /etc/letsencrypt/live/
                if config_path.startswith("ssl/"):
                    # ssl/domain/file.pem -> /etc/letsencrypt/live/domain/file.pem
                    ssl_relative = config_path[4:]  # Remove "ssl/" prefix
                    target_path = f"/etc/letsencrypt/live/{ssl_relative}"

                if not target_path:
                    return {"status": "failed", "config_path": config_path, "error": f"No target path for: {config_path}"}

            # Create backup of existing file
            # NOTE: Config files are bind-mounted as individual files, not directories.
            # So we must save backups to /app/backups/config_backups/ (which IS mounted)
            # rather than alongside the original file (which would go to container FS)
            backup_created = None
            if create_backup and os.path.exists(target_path):
                # Save to mounted backup volume
                config_backup_dir = make_private_dir("/app/backups/config_backups")

                # Create backup filename: original_name.bak.TIMESTAMP
                original_filename = os.path.basename(target_path)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"{original_filename}.bak.{timestamp}"
                backup_path = os.path.join(config_backup_dir, backup_filename)

                shutil.copy2(target_path, backup_path)
                chmod_quietly(backup_path, 0o600)
                backup_created = backup_path
                logger.info(f"Created backup: {backup_created}")

            # Ensure the target directory exists (for SSL, dozzle/, ntfy/, etc.)
            target_dir = os.path.dirname(target_path)
            os.makedirs(target_dir, exist_ok=True)

            # Copy file - for bind mounts, write directly to the mounted file
            # Use open() with write mode to ensure we write to the bind mount
            # instead of potentially creating a new file in the overlay
            with open(source_path, 'rb') as src:
                content = src.read()
            with open(target_path, 'wb') as dst:
                dst.write(content)
            # Copy metadata (permissions, timestamps)
            shutil.copystat(source_path, target_path)

            # Verify the file was written correctly
            if os.path.exists(target_path):
                stat_info = os.stat(target_path)
                logger.info(f"Restored config file: {config_path} -> {target_path} "
                           f"(size: {stat_info.st_size} bytes, inode: {stat_info.st_ino})")
            else:
                logger.error(f"File not found after restore: {target_path}")
                return {"status": "failed", "config_path": config_path, "error": f"File not found after restore: {target_path}"}

            return {
                "status": "success",
                "config_path": config_path,
                "target_path": target_path,
                "backup_created": backup_created,
                "message": f"Restored {os.path.basename(config_path)}",
            }

        except Exception as e:
            logger.error(f"Failed to restore config file: {e}")
            return {"status": "failed", "config_path": config_path, "error": str(e)}

    # ------------------------------------------------------------------
    # In-app database restore (n8n database only)
    # ------------------------------------------------------------------

    @staticmethod
    def _pg_conn() -> Tuple[str, str, Dict[str, str]]:
        """Return (host, user, env) for the live PostgreSQL server."""
        host = os.environ.get("POSTGRES_HOST", "postgres")
        user = os.environ.get("POSTGRES_USER", "n8n")
        env = {
            **os.environ,
            "PGPASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "PGCONNECT_TIMEOUT": "15",
            # Never queue forever behind another session's lock.
            "PGOPTIONS": "-c lock_timeout=30s",
        }
        return host, user, env

    async def _psql(self, sql: str, database: str = "postgres") -> Tuple[int, str, str]:
        host, user, env = self._pg_conn()
        cmd = [
            "psql", "-h", host, "-U", user, "-d", database,
            "-v", "ON_ERROR_STOP=1", "-X", "-q", "-t", "-A",
            "-c", sql,
        ]
        return await _run_subprocess(cmd, env=env, timeout=PG_SHORT_TIMEOUT)

    async def _database_exists(self, name: str) -> bool:
        rc, out, err = await self._psql(f"SELECT 1 FROM pg_database WHERE datname = '{name}'")
        if rc != 0:
            raise RuntimeError(f"Could not query PostgreSQL: {_tail(err)}")
        return out.strip() == "1"

    async def _terminate_connections(self, name: str) -> None:
        await self._psql(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{name}' AND pid <> pg_backend_pid()"
        )

    def check_database_restorable(self, database_name: str, target_database: Optional[str] = None) -> Optional[str]:
        """Return None if the in-app restore is allowed, otherwise the reason it is refused."""
        target = target_database or database_name
        mgmt_db = management_database_name()
        if database_name == mgmt_db or target == mgmt_db:
            return MANAGEMENT_DB_REFUSAL.format(name=mgmt_db)
        n8n_db = n8n_database_name()
        if target != n8n_db:
            return (
                f"Only the n8n database ({n8n_db}) can be restored from the management console; "
                f"'{target}' is not supported. Use the bare-metal restore.sh for other databases."
            )
        if not _SAFE_DB_NAME.match(database_name) or not _SAFE_DB_NAME.match(target):
            return "Invalid database name"
        return None

    async def _safety_dump_dir(self) -> str:
        try:
            base = await self.backup_service._get_storage_location()
        except Exception as e:
            logger.warning(f"Could not determine backup storage location, using staging dir: {e}")
            base = settings.backup_staging_dir
        return os.path.join(base, "pre_restore")

    async def _restore_n8n_database_from_dump(
        self,
        dump_path: str,
        database_name: str,
        safety_dir: str,
    ) -> Dict[str, Any]:
        """
        Restore the live n8n database from a pg_dump custom-format file.

        Steps (anything failing before step 5 leaves the live database and n8n
        untouched):
          1. Validate the dump (pg_restore --list).
          2. Safety dump of the live database (pg_dump -Fc) into safety_dir.
          3. Create an empty temporary database <target>_restore_tmp.
          4. pg_restore --exit-on-error --single-transaction into the temp DB.
          5. Stop n8n, terminate remaining connections, rename the live DB to
             <target>_pre_restore_<ts> and the temp DB to <target>.
          6. Start n8n again (always, in a finally block, if it was running).

        The previous database is kept as <target>_pre_restore_<ts> for instant
        rollback; the operator drops it once satisfied (see the Backup Guide).
        """
        target = n8n_database_name()
        tmp_db = f"{target}_restore_tmp"
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        old_db = f"{target}_pre_restore_{ts}"
        host, user, env = self._pg_conn()

        result: Dict[str, Any] = {
            "status": "failed",
            "database": database_name,
            "target": target,
            "safety_dump": None,
            "previous_database": None,
            "n8n_restarted": None,
        }

        def fail(message: str, stderr: str = "") -> Dict[str, Any]:
            result["error"] = message
            if stderr:
                result["stderr"] = _tail(stderr)
            logger.error(f"Database restore of {database_name} failed: {message} {_tail(stderr, 2000)}")
            return result

        # 1. Validate the dump before touching anything
        rc, _, err = await _run_subprocess(["pg_restore", "--list", dump_path], timeout=PG_SHORT_TIMEOUT)
        if rc != 0:
            return fail("The database dump in this backup is unreadable; nothing was changed.", err)

        try:
            target_exists = await self._database_exists(target)
            suffix = 1
            while await self._database_exists(old_db):
                suffix += 1
                old_db = f"{target}_pre_restore_{ts}_{suffix}"
        except RuntimeError as e:
            return fail(str(e))

        # 2. Safety dump of the live database
        if target_exists:
            make_private_dir(safety_dir)
            safety_path = os.path.join(safety_dir, f"{old_db}.dump")
            rc, _, err = await _run_subprocess(
                ["pg_dump", "-h", host, "-U", user, "-d", target,
                 "--no-owner", "--no-acl", "-F", "c", "-f", safety_path],
                env=env, timeout=PG_LONG_TIMEOUT,
            )
            if rc != 0:
                with contextlib.suppress(OSError):
                    os.remove(safety_path)
                return fail("Could not take a safety dump of the current database; nothing was changed.", err)
            chmod_quietly(safety_path, 0o600)
            result["safety_dump"] = safety_path
            logger.info(f"Safety dump of {target} written to {safety_path}")

        # 3. Fresh temporary database
        rc, _, err = await self._psql(f'DROP DATABASE IF EXISTS "{tmp_db}" WITH (FORCE)')
        if rc == 0:
            rc, _, err = await self._psql(f'CREATE DATABASE "{tmp_db}" TEMPLATE template0')
        if rc != 0:
            return fail(f"Could not create temporary database {tmp_db}; nothing was changed.", err)

        async def drop_tmp() -> None:
            drc, _, derr = await self._psql(f'DROP DATABASE IF EXISTS "{tmp_db}" WITH (FORCE)')
            if drc != 0:
                logger.warning(f"Could not drop {tmp_db}: {derr}")

        # 4. Restore into the temporary database (all-or-nothing)
        rc, _, err = await _run_subprocess(
            ["pg_restore", "-h", host, "-U", user, "-d", tmp_db,
             "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl",
             dump_path],
            env=env, timeout=PG_LONG_TIMEOUT,
        )
        if rc != 0:
            await drop_tmp()
            return fail(
                "pg_restore failed; the live database and n8n were not touched.",
                err or f"pg_restore exited with code {rc}",
            )

        # 5. Stop n8n and swap databases
        try:
            container = await asyncio.wait_for(
                asyncio.to_thread(_find_n8n_container_sync), timeout=DOCKER_TIMEOUT
            )
        except Exception as e:
            container = None
            logger.error(f"Docker lookup of the n8n container failed: {e}")
        if container is None:
            await drop_tmp()
            return fail(
                "Could not identify the n8n container to stop it; the live database was not touched. "
                "Set N8N_CONTAINER for the management container or use the bare-metal restore.sh."
            )

        # was_running is read in its own call BEFORE stopping, so the finally
        # block restarts n8n even if the stop call times out (the worker thread
        # may still stop the container) or raises after the container stopped.
        was_running = False
        stop_future: Optional[asyncio.Future] = None
        renamed_old = False
        swap_error: Optional[str] = None
        swap_stderr = ""
        try:
            was_running = await asyncio.wait_for(
                asyncio.to_thread(_container_running_sync, container), timeout=DOCKER_TIMEOUT
            )
            if was_running:
                # Shielded so a timeout does not lose track of the stop still
                # running in its worker thread (awaited again before restart).
                stop_future = asyncio.ensure_future(asyncio.to_thread(_stop_container_sync, container))
                await asyncio.wait_for(asyncio.shield(stop_future), timeout=DOCKER_TIMEOUT)
            logger.info(f"n8n container stopped for restore (was running: {was_running})")

            for attempt in range(1, 4):
                await self._terminate_connections(target)
                if target_exists and not renamed_old:
                    rc, _, err = await self._psql(f'ALTER DATABASE "{target}" RENAME TO "{old_db}"')
                    if rc != 0:
                        swap_stderr = err
                        if "being accessed by other users" in err and attempt < 3:
                            await asyncio.sleep(2)
                            continue
                        swap_error = f"Could not rename {target} out of the way; the live database is unchanged."
                        break
                    renamed_old = True
                rc, _, err = await self._psql(f'ALTER DATABASE "{tmp_db}" RENAME TO "{target}"')
                if rc != 0:
                    swap_stderr = err
                    swap_error = f"Could not rename {tmp_db} to {target}."
                    break
                if target_exists:
                    result["previous_database"] = old_db
                result["status"] = "success"
                result["message"] = f"Restored database {database_name} into {target}"
                break
        except Exception as e:
            swap_error = f"Restore aborted while stopping n8n / swapping databases: {_exc_text(e)}"
        finally:
            if result["status"] != "success" and renamed_old:
                try:
                    brc, _, berr = await self._psql(f'ALTER DATABASE "{old_db}" RENAME TO "{target}"')
                except Exception as e:
                    brc, berr = 1, _exc_text(e)
                if brc == 0:
                    swap_error = (swap_error or "Swap failed.") + " The previous database was put back; nothing changed."
                else:
                    swap_error = (swap_error or "Swap failed.") + (
                        f" ROLLBACK ALSO FAILED - the previous database is named {old_db}; "
                        f"rename it back to {target} manually. ({_tail(berr, 1000)})"
                    )
            if was_running:
                try:
                    if stop_future is not None and not stop_future.done():
                        # Let a timed-out stop finish first, or it could stop
                        # n8n again right after the restart below.
                        await asyncio.wait({stop_future}, timeout=DOCKER_TIMEOUT)
                    await asyncio.shield(asyncio.wait_for(
                        asyncio.to_thread(_start_container_sync, container), timeout=DOCKER_TIMEOUT
                    ))
                    result["n8n_restarted"] = True
                except Exception as e:
                    result["n8n_restarted"] = False
                    restart_msg = (
                        f"n8n could not be restarted automatically: {_exc_text(e)}. "
                        f"Start it with 'docker compose up -d n8n'."
                    )
                    result.setdefault("warnings", []).append(restart_msg)
                    # Also surface it in the failure message if the swap failed.
                    if result["status"] != "success":
                        swap_error = (swap_error or "Database swap failed.") + " " + restart_msg
                    logger.error(f"Failed to restart n8n after restore: {_exc_text(e)}")

        if result["status"] != "success":
            await drop_tmp()
            return fail(swap_error or "Database swap failed.", swap_stderr)

        # Drop pooled connections of the API's own n8n engine to the old database.
        try:
            from api.database import n8n_engine
            await n8n_engine.dispose()
        except Exception as e:
            logger.debug(f"Could not dispose n8n engine pool: {e}")

        logger.info(
            f"Database restored: {database_name} -> {target}; previous database kept as "
            f"{result['previous_database']}; safety dump {result['safety_dump']}"
        )
        return result

    async def restore_database(
        self,
        backup_id: int,
        database_name: str,
        target_database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Restore the n8n database from a backup into the running PostgreSQL.

        Only the n8n database can be restored in-app; the management database
        is refused (use the bare-metal restore.sh). See
        _restore_n8n_database_from_dump for the safety procedure.

        Callers must hold the operation lock (see api.services.operation_lock).
        """
        refusal = self.check_database_restorable(database_name, target_database)
        if refusal:
            return {"status": "failed", "database": database_name, "error": refusal, "refused": True}

        safety_dir = await self._safety_dump_dir()
        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return {"status": "failed", "database": database_name, "error": metadata.get("error", "Extract failed")}

        try:
            dump_path = os.path.join(temp_dir, "databases", f"{database_name}.dump")
            if not os.path.exists(dump_path):
                return {"status": "failed", "database": database_name,
                        "error": f"Database dump not found in backup: {database_name}"}
            return await self._restore_n8n_database_from_dump(dump_path, database_name, safety_dir)

        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return {"status": "failed", "database": database_name, "error": str(e)}

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def get_restore_preview(self, backup_id: int) -> Dict[str, Any]:
        """
        Get a preview of what would be restored from a backup.
        Returns lists of databases, config files, and workflows.
        """
        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return {"status": "failed", "error": metadata.get("error", "Extract failed")}

        try:
            preview = {
                "backup_id": backup_id,
                "backup_type": metadata.get("backup_type", "unknown"),
                "created_at": metadata.get("created_at"),
                "databases": [],
                "config_files": [],
                "ssl_certificates": [],
                "workflow_count": metadata.get("workflow_count", 0),
                "credential_count": metadata.get("credential_count", 0),
                "restore_script_version": metadata.get("restore_script_version"),
                "letsencrypt_tree": os.path.isdir(os.path.join(temp_dir, "letsencrypt", "live")),
            }

            # Check databases
            db_dir = os.path.join(temp_dir, "databases")
            if os.path.exists(db_dir):
                for filename in os.listdir(db_dir):
                    if filename.endswith(".dump"):
                        db_name = filename[:-5]  # Remove .dump
                        dump_path = os.path.join(db_dir, filename)
                        stat = os.stat(dump_path)
                        blocked_reason = self.check_database_restorable(db_name)
                        preview["databases"].append({
                            "name": db_name,
                            "size": stat.st_size,
                            "row_counts": metadata.get("row_counts", {}).get(db_name, {}),
                            "restorable": blocked_reason is None,
                            "restore_blocked_reason": blocked_reason,
                        })

            # Check config files
            config_dir = os.path.join(temp_dir, "config")
            if os.path.isdir(config_dir):
                for root, _dirs, files in os.walk(config_dir):
                    for filename in sorted(files):
                        filepath = os.path.join(root, filename)
                        stat = os.stat(filepath)
                        preview["config_files"].append({
                            "name": os.path.relpath(filepath, config_dir),
                            "size": stat.st_size,
                        })

            # Check SSL certificates
            ssl_dir = os.path.join(temp_dir, "ssl")
            if os.path.exists(ssl_dir):
                for domain in os.listdir(ssl_dir):
                    domain_path = os.path.join(ssl_dir, domain)
                    if os.path.isdir(domain_path):
                        certs = os.listdir(domain_path)
                        preview["ssl_certificates"].append({
                            "domain": domain,
                            "certificates": certs,
                        })

            preview["status"] = "success"
            return preview

        except Exception as e:
            logger.error(f"Failed to get restore preview: {e}")
            return {"status": "failed", "error": str(e)}

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def full_system_restore(
        self,
        backup_id: int,
        restore_databases: bool = True,
        restore_configs: bool = True,
        restore_ssl: bool = True,
        database_names: Optional[List[str]] = None,
        config_files: Optional[List[str]] = None,
        create_backups: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform a full system restore from a backup.

        This can restore:
        - The n8n database (the management database is refused - it can only be
          restored with the bare-metal restore.sh)
        - Config files (.env, docker-compose.yaml, nginx.conf, ...)
        - SSL certificates

        The archive is extracted once. Any failure is reported in "errors" and
        makes the overall status "partial" or "failed" - never "success".

        Callers must hold the operation lock (see api.services.operation_lock).

        Args:
            backup_id: The backup to restore from
            restore_databases: Whether to restore databases
            restore_configs: Whether to restore config files
            restore_ssl: Whether to restore SSL certificates
            database_names: Specific databases to restore (None = the n8n database, [] = none)
            config_files: Specific config files to restore (None = all)
            create_backups: Create backups of existing files before overwriting

        Returns:
            Dict with comprehensive status
        """
        logger.info(f"Starting full system restore from backup {backup_id}")

        results = {
            "status": "in_progress",
            "backup_id": backup_id,
            "databases": [],
            "config_files": [],
            "ssl_certificates": [],
            "errors": [],
            "warnings": [],
        }

        # Refuse disallowed databases before doing any work
        if restore_databases and database_names:
            for db_name in database_names:
                refusal = self.check_database_restorable(db_name)
                if refusal:
                    results["databases"].append(
                        {"status": "failed", "database": db_name, "error": refusal, "refused": True}
                    )
                    results["errors"].append(f"Database {db_name}: {refusal}")
            if results["errors"]:
                results["status"] = "failed"
                results["error"] = "; ".join(results["errors"])
                return results

        safety_dir = await self._safety_dump_dir() if restore_databases else ""
        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return {"status": "failed", "error": metadata.get("error", "Extract failed")}

        attempted = 0
        try:
            # Restore databases
            if restore_databases:
                db_dir = os.path.join(temp_dir, "databases")
                available = sorted(
                    f[:-5] for f in os.listdir(db_dir) if f.endswith(".dump")
                ) if os.path.isdir(db_dir) else []

                if database_names is not None:
                    wanted = list(database_names)
                else:
                    # Default: only the n8n database. The management DB is never
                    # restored in-app.
                    wanted = [n for n in available if self.check_database_restorable(n) is None]
                    for n in available:
                        if n not in wanted:
                            results["warnings"].append(
                                f"Database {n} skipped: "
                                + (self.check_database_restorable(n) or "not restorable in-app")
                            )

                for db_name in wanted:
                    attempted += 1
                    dump_path = os.path.join(db_dir, f"{db_name}.dump")
                    if not os.path.exists(dump_path):
                        result = {"status": "failed", "database": db_name,
                                  "error": f"Database dump not found in backup: {db_name}"}
                    else:
                        result = await self._restore_n8n_database_from_dump(dump_path, db_name, safety_dir)
                    results["databases"].append(result)
                    if result["status"] != "success":
                        detail = result.get("error", "unknown error")
                        if result.get("stderr"):
                            detail += f" | {result['stderr']}"
                        results["errors"].append(f"Database {db_name}: {detail}")
                    for warning in result.get("warnings", []):
                        results["warnings"].append(f"Database {db_name}: {warning}")

            # Restore config files (including files in sub-directories)
            if restore_configs:
                config_dir = os.path.join(temp_dir, "config")
                if os.path.isdir(config_dir):
                    for root, _dirs, files in os.walk(config_dir):
                        for filename in sorted(files):
                            rel = os.path.relpath(os.path.join(root, filename), config_dir)
                            if config_files and rel not in config_files and filename not in config_files:
                                continue
                            attempted += 1
                            config_path = f"config/{rel}"
                            result = self._restore_config_from_dir(
                                temp_dir, config_path, create_backup=create_backups
                            )
                            results["config_files"].append(result)
                            if result["status"] == "failed":
                                results["errors"].append(f"Config {rel}: {result.get('error')}")

            # Restore SSL certificates
            if restore_ssl:
                le_dir = os.path.join(temp_dir, "letsencrypt")
                ssl_dir = os.path.join(temp_dir, "ssl")
                if os.path.isdir(os.path.join(le_dir, "live")):
                    # Full certbot tree: keeps live/ symlinks so renewal keeps working.
                    attempted += 1
                    try:
                        result = await asyncio.to_thread(
                            _restore_letsencrypt_tree_sync,
                            le_dir,
                            LETSENCRYPT_ROOT,
                            "/app/backups/config_backups" if create_backups else None,
                        )
                    except Exception as e:
                        result = {"status": "failed", "config_path": "letsencrypt/", "error": str(e)}
                    results["ssl_certificates"].append(result)
                    if result["status"] == "failed":
                        results["errors"].append(f"SSL certificate tree: {result.get('error')}")
                elif os.path.isdir(ssl_dir):
                    results["warnings"].append(
                        "This backup predates full certificate-tree backups: certificates were restored "
                        "as plain files and certbot may be unable to renew them. Re-issue the certificate "
                        "if renewal fails."
                    )
                    for domain in os.listdir(ssl_dir):
                        domain_path = os.path.join(ssl_dir, domain)
                        if os.path.isdir(domain_path):
                            for cert_file in os.listdir(domain_path):
                                attempted += 1
                                cert_path = f"ssl/{domain}/{cert_file}"
                                result = self._restore_config_from_dir(
                                    temp_dir, cert_path, create_backup=create_backups
                                )
                                results["ssl_certificates"].append(result)
                                if result["status"] == "failed":
                                    results["errors"].append(f"SSL {domain}/{cert_file}: {result.get('error')}")

            # Determine overall status - any error means not "success"
            succeeded = sum(
                1 for r in results["databases"] + results["config_files"] + results["ssl_certificates"]
                if r.get("status") == "success"
            )
            if results["errors"]:
                results["status"] = "partial" if succeeded else "failed"
                results["error"] = "; ".join(results["errors"])
            elif attempted == 0:
                results["status"] = "failed"
                results["error"] = "Nothing was restored: no matching items in this backup"
            else:
                results["status"] = "success"

            db_ok = sum(1 for r in results["databases"] if r.get("status") == "success")
            cfg_ok = sum(1 for r in results["config_files"] if r.get("status") == "success")
            ssl_ok = sum(1 for r in results["ssl_certificates"] if r.get("status") == "success")
            results["message"] = (
                f"Restored {db_ok}/{len(results['databases'])} databases, "
                f"{cfg_ok}/{len(results['config_files'])} config files, "
                f"{ssl_ok}/{len(results['ssl_certificates'])} SSL files"
            )
            logger.info(f"Full system restore finished ({results['status']}): {results['message']}")

            return results

        except Exception as e:
            logger.error(f"Full system restore failed: {e}")
            results["status"] = "failed"
            results["error"] = str(e)
            results["errors"].append(str(e))
            return results

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ============================================================================
    # Public Website File Restore Functions
    # ============================================================================

    async def mount_public_website_files(self, backup_id: int) -> Dict[str, Any]:
        """
        Mount a backup's public website files by extracting them to a temp directory.
        This is separate from the database mounting system.

        Args:
            backup_id: The backup ID to mount

        Returns:
            Dict with mount status and file count
        """
        global _public_website_mounted_backup_id, _public_website_mount_dir

        # Check if already mounted
        if _public_website_mounted_backup_id == backup_id and _public_website_mount_dir:
            if os.path.exists(_public_website_mount_dir):
                return {
                    "status": "already_mounted",
                    "backup_id": backup_id,
                    "mount_dir": _public_website_mount_dir,
                    "message": "Public website files are already mounted",
                }

        # Clean up any existing mount
        if _public_website_mount_dir and os.path.exists(_public_website_mount_dir):
            try:
                shutil.rmtree(_public_website_mount_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up existing mount: {e}")

        try:
            # Get backup record
            backup_service = BackupService(self.db)
            backup = await backup_service.get_backup(backup_id)
            if not backup:
                return {"status": "failed", "error": f"Backup {backup_id} not found"}

            if backup.status != "success":
                return {"status": "failed", "error": f"Backup {backup_id} is not successful"}

            # Create temp directory for mounting
            mount_dir = settings.public_website_mount_dir
            os.makedirs(mount_dir, exist_ok=True)

            # Extract public_website directory from archive
            archive_path = backup.filepath
            if not os.path.exists(archive_path):
                return {"status": "failed", "error": f"Backup file not found: {archive_path}"}

            def extract_public_website() -> int:
                file_count = 0
                with open_backup_archive(archive_path) as tar:
                    # Find and extract only the public_website directory
                    for member in tar.getmembers():
                        if member.name.startswith("public_website/"):
                            # Adjust the extraction path to remove the public_website prefix
                            member_copy = tarfile.TarInfo(member.name)
                            member_copy.size = member.size
                            member_copy.mode = member.mode
                            member_copy.mtime = member.mtime

                            if member.isfile():
                                # Extract file
                                rel_path = member.name[len("public_website/"):]
                                if rel_path:  # Skip the directory itself
                                    dest_path = os.path.join(mount_dir, rel_path)
                                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                    with tar.extractfile(member) as src:
                                        if src:
                                            with open(dest_path, 'wb') as dst:
                                                shutil.copyfileobj(src, dst)
                                            file_count += 1
                            elif member.isdir():
                                rel_path = member.name[len("public_website/"):]
                                if rel_path:
                                    os.makedirs(os.path.join(mount_dir, rel_path), exist_ok=True)
                return file_count

            # Decrypting and reading the archive can take minutes: not on the event loop
            file_count = await asyncio.to_thread(extract_public_website)

            if file_count == 0:
                # Clean up empty mount
                shutil.rmtree(mount_dir, ignore_errors=True)
                return {
                    "status": "failed",
                    "error": "No public website files found in backup",
                }

            # Update global state
            _public_website_mounted_backup_id = backup_id
            _public_website_mount_dir = mount_dir

            logger.info(f"Mounted public website files from backup {backup_id}: {file_count} files")
            return {
                "status": "success",
                "backup_id": backup_id,
                "mount_dir": mount_dir,
                "file_count": file_count,
                "message": f"Mounted {file_count} public website files",
            }

        except Exception as e:
            logger.error(f"Failed to mount public website files: {e}")
            return {"status": "failed", "error": str(e)}

    async def unmount_public_website_files(self) -> Dict[str, Any]:
        """
        Unmount (clean up) the public website files mount.
        """
        global _public_website_mounted_backup_id, _public_website_mount_dir

        if not _public_website_mounted_backup_id:
            return {"status": "not_mounted", "message": "No public website files are mounted"}

        backup_id = _public_website_mounted_backup_id

        try:
            # Clean up mount directory
            if _public_website_mount_dir and os.path.exists(_public_website_mount_dir):
                shutil.rmtree(_public_website_mount_dir)

            # Clean up cache file
            if os.path.exists(PUBLIC_WEBSITE_FILES_CACHE):
                os.remove(PUBLIC_WEBSITE_FILES_CACHE)

            # Reset state
            _public_website_mounted_backup_id = None
            _public_website_mount_dir = None

            logger.info(f"Unmounted public website files from backup {backup_id}")
            return {
                "status": "success",
                "backup_id": backup_id,
                "message": "Public website files unmounted",
            }

        except Exception as e:
            logger.error(f"Failed to unmount public website files: {e}")
            return {"status": "failed", "error": str(e)}

    def is_public_website_mounted(self, backup_id: int = None) -> bool:
        """
        Check if public website files are mounted.

        Args:
            backup_id: If provided, check if this specific backup is mounted

        Returns:
            True if mounted (and matches backup_id if provided)
        """
        global _public_website_mounted_backup_id, _public_website_mount_dir

        if _public_website_mounted_backup_id is None or _public_website_mount_dir is None:
            return False

        if not os.path.exists(_public_website_mount_dir):
            return False

        if backup_id is not None:
            return _public_website_mounted_backup_id == backup_id

        return True

    async def list_public_website_files(
        self,
        backup_id: int,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List files from mounted public website backup with pagination.

        Args:
            backup_id: The backup ID to list files from
            limit: Maximum number of files to return
            offset: Number of files to skip
            search: Optional search filter for filenames

        Returns:
            Dict with files list, total count, and pagination info
        """
        global _public_website_mounted_backup_id, _public_website_mount_dir

        # Check if mounted
        if not self.is_public_website_mounted(backup_id):
            return {
                "status": "failed",
                "error": "Public website files not mounted for this backup",
                "files": [],
                "total": 0,
            }

        try:
            all_files = []
            mount_dir = _public_website_mount_dir

            # Walk the directory and collect file info
            for root, dirs, files in os.walk(mount_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, mount_dir)

                    # Apply search filter
                    if search and search.lower() not in rel_path.lower():
                        continue

                    try:
                        stat = os.stat(file_path)
                        all_files.append({
                            "name": filename,
                            "path": rel_path,
                            "size": stat.st_size,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                        })
                    except Exception as e:
                        logger.warning(f"Failed to stat file {rel_path}: {e}")

            # Sort by path for consistent ordering
            all_files.sort(key=lambda x: x["path"])

            # Apply pagination
            total = len(all_files)
            paginated_files = all_files[offset:offset + limit]

            return {
                "status": "success",
                "files": paginated_files,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            }

        except Exception as e:
            logger.error(f"Failed to list public website files: {e}")
            return {"status": "failed", "error": str(e), "files": [], "total": 0}

    async def preview_public_website_file(
        self,
        backup_id: int,
        file_path: str,
        max_size: int = 1024 * 1024,  # 1MB default for text
        max_image_size: int = 10 * 1024 * 1024,  # 10MB for images
    ) -> Dict[str, Any]:
        """
        Preview a public website file content.

        Args:
            backup_id: The backup ID
            file_path: Relative path to the file
            max_size: Maximum size to read for text files (default 1MB)
            max_image_size: Maximum size for image files (default 10MB)

        Returns:
            Dict with file content (base64 for binary, text for text files)
        """
        global _public_website_mount_dir

        if not self.is_public_website_mounted(backup_id):
            return {"status": "failed", "error": "Public website files not mounted"}

        try:
            full_path = os.path.join(_public_website_mount_dir, file_path)

            # Security check - prevent path traversal
            if not os.path.realpath(full_path).startswith(os.path.realpath(_public_website_mount_dir)):
                return {"status": "failed", "error": "Invalid file path"}

            if not os.path.exists(full_path):
                return {"status": "failed", "error": "File not found"}

            # Determine mime type first to set appropriate size limit
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
            is_image = mime_type and mime_type.startswith("image/")
            effective_max_size = max_image_size if is_image else max_size

            stat = os.stat(full_path)
            if stat.st_size > effective_max_size:
                return {
                    "status": "failed",
                    "error": f"File too large ({stat.st_size} bytes, max {effective_max_size})",
                }
            is_text = mime_type and mime_type.startswith("text/")

            if is_text:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                return {
                    "status": "success",
                    "path": file_path,
                    "size": stat.st_size,
                    "mime_type": mime_type,
                    "is_text": True,
                    "content": content,
                }
            else:
                import base64
                with open(full_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('ascii')
                return {
                    "status": "success",
                    "path": file_path,
                    "size": stat.st_size,
                    "mime_type": mime_type or "application/octet-stream",
                    "is_text": False,
                    "content_base64": content,
                }

        except Exception as e:
            logger.error(f"Failed to preview public website file: {e}")
            return {"status": "failed", "error": str(e)}

    async def get_public_website_file_path(self, backup_id: int, file_path: str) -> Optional[str]:
        """
        Get the full filesystem path to a mounted public website file.
        Used for downloading files.

        Args:
            backup_id: The backup ID
            file_path: Relative path to the file

        Returns:
            Full path to the file, or None if not found/not mounted
        """
        global _public_website_mount_dir

        if not self.is_public_website_mounted(backup_id):
            return None

        full_path = os.path.join(_public_website_mount_dir, file_path)

        # Security check
        if not os.path.realpath(full_path).startswith(os.path.realpath(_public_website_mount_dir)):
            return None

        if not os.path.exists(full_path):
            return None

        return full_path

    async def check_public_website_restore(self, backup_id: int) -> Dict[str, Any]:
        """
        Dry-run check for public website restore.
        Compares backup files against current live volume to identify:
        - Files that will be added (new)
        - Files that will be overwritten (different checksum)
        - Files that are unchanged (same checksum)

        Args:
            backup_id: The backup ID to check

        Returns:
            Dict with comparison results
        """
        global _public_website_mount_dir

        if not self.is_public_website_mounted(backup_id):
            return {"status": "failed", "error": "Public website files not mounted"}

        try:
            from api.services.backup_service import calculate_file_checksum, PUBLIC_WEBSITE_VOLUME

            def checksum_tree(base: str) -> Dict[str, Dict[str, Any]]:
                found = {}
                for root, dirs, files in os.walk(base):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        found[os.path.relpath(file_path, base)] = {
                            "size": os.path.getsize(file_path),
                            "checksum": calculate_file_checksum(file_path),
                        }
                return found

            # Get list of files from mounted backup (hashing in a worker thread)
            backup_files = await asyncio.to_thread(checksum_tree, _public_website_mount_dir)

            # Create temp directory to extract current volume contents
            live_files = {}
            with tempfile.TemporaryDirectory() as live_temp:
                # Extract current volume contents using Docker
                result = await _proc.run(
                    [
                        "docker", "run", "--rm",
                        "--security-opt", "apparmor=unconfined",
                        "-v", f"{PUBLIC_WEBSITE_VOLUME}:/source:ro",
                        "-v", f"{live_temp}:/dest",
                        settings.helper_image,
                        "sh", "-c", "cp -r /source/. /dest/"
                    ],
                    capture_output=True,
                    text=True, timeout=_proc.COPY_TIMEOUT
                )

                if result.returncode == 0:
                    live_files = await asyncio.to_thread(checksum_tree, live_temp)

            # Compare
            to_add = []
            to_overwrite = []
            unchanged = []

            for path, info in backup_files.items():
                if path not in live_files:
                    to_add.append({"path": path, "size": info["size"]})
                elif live_files[path]["checksum"] != info["checksum"]:
                    to_overwrite.append({
                        "path": path,
                        "backup_size": info["size"],
                        "live_size": live_files[path]["size"],
                    })
                else:
                    unchanged.append({"path": path, "size": info["size"]})

            return {
                "status": "success",
                "backup_id": backup_id,
                "total_backup_files": len(backup_files),
                "total_live_files": len(live_files),
                "to_add": to_add,
                "to_overwrite": to_overwrite,
                "unchanged": unchanged,
                "summary": {
                    "new_files": len(to_add),
                    "overwrite_files": len(to_overwrite),
                    "unchanged_files": len(unchanged),
                },
            }

        except Exception as e:
            logger.error(f"Failed to check public website restore: {e}")
            return {"status": "failed", "error": str(e)}

    async def restore_public_website_files(
        self,
        backup_id: int,
        file_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Restore public website files from backup to the live Docker volume.
        Uses batched processing with a single Docker container for efficiency.

        Args:
            backup_id: The backup ID to restore from
            file_paths: Optional list of specific files to restore. If None, restores all.

        Returns:
            Dict with restore results
        """
        global _public_website_mount_dir, _public_website_restore_lock

        if not self.is_public_website_mounted(backup_id):
            return {"status": "failed", "error": "Public website files not mounted"}

        # Use lock to prevent concurrent restore operations
        async with _public_website_restore_lock:
            try:
                from api.services.backup_service import PUBLIC_WEBSITE_VOLUME

                mount_dir = _public_website_mount_dir
                batch_size = settings.public_website_batch_size

                # Determine files to restore
                if file_paths:
                    files_to_restore = []
                    for path in file_paths:
                        full_path = os.path.join(mount_dir, path)
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            files_to_restore.append(path)
                else:
                    # Restore all files
                    files_to_restore = []
                    for root, dirs, files in os.walk(mount_dir):
                        for filename in files:
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, mount_dir)
                            files_to_restore.append(rel_path)

                if not files_to_restore:
                    return {"status": "failed", "error": "No files to restore"}

                total_files = len(files_to_restore)
                restored_count = 0
                failed_files = []

                # Process in batches using single Docker container with shell script
                for i in range(0, total_files, batch_size):
                    batch = files_to_restore[i:i + batch_size]

                    # Create shell script for batch copy
                    script_lines = ["#!/bin/sh", "set -e"]
                    for file_path in batch:
                        # Ensure destination directory exists and copy file
                        dest_dir = os.path.dirname(file_path)
                        if dest_dir:
                            script_lines.append(f'mkdir -p "/dest/{dest_dir}"')
                        script_lines.append(f'cp "/source/{file_path}" "/dest/{file_path}"')

                    script_content = "\n".join(script_lines)

                    # Run batch restore via Docker
                    result = await _proc.run(
                        [
                            "docker", "run", "--rm",
                            "--security-opt", "apparmor=unconfined",
                            "-v", f"{mount_dir}:/source:ro",
                            "-v", f"{PUBLIC_WEBSITE_VOLUME}:/dest",
                            settings.helper_image,
                            "sh", "-c", script_content,
                        ],
                        capture_output=True,
                        text=True, timeout=_proc.COPY_TIMEOUT
                    )

                    if result.returncode == 0:
                        restored_count += len(batch)
                        logger.info(f"Restored batch of {len(batch)} files ({restored_count}/{total_files})")
                    else:
                        # If batch fails, try individual files
                        for file_path in batch:
                            dest_dir = os.path.dirname(file_path)
                            mkdir_cmd = f'mkdir -p "/dest/{dest_dir}" && ' if dest_dir else ""
                            individual_result = await _proc.run(
                                [
                                    "docker", "run", "--rm",
                                    "--security-opt", "apparmor=unconfined",
                                    "-v", f"{mount_dir}:/source:ro",
                                    "-v", f"{PUBLIC_WEBSITE_VOLUME}:/dest",
                                    settings.helper_image,
                                    "sh", "-c", f'{mkdir_cmd}cp "/source/{file_path}" "/dest/{file_path}"',
                                ],
                                capture_output=True,
                                text=True, timeout=_proc.COPY_TIMEOUT
                            )
                            if individual_result.returncode == 0:
                                restored_count += 1
                            else:
                                failed_files.append({
                                    "path": file_path,
                                    "error": individual_result.stderr,
                                })

                status = "success" if not failed_files else ("partial" if restored_count > 0 else "failed")

                return {
                    "status": status,
                    "backup_id": backup_id,
                    "restored_count": restored_count,
                    "total_files": total_files,
                    "failed_files": failed_files,
                    "message": f"Restored {restored_count}/{total_files} files",
                }

            except Exception as e:
                logger.error(f"Failed to restore public website files: {e}")
                return {"status": "failed", "error": str(e)}
