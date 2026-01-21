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
from api.services.n8n_api_service import N8nApiService
from api.config import settings

logger = logging.getLogger(__name__)


# Container configuration
RESTORE_CONTAINER_NAME = "n8n_postgres_restore"
RESTORE_CONTAINER_IMAGE = "pgvector/pgvector:pg16"  # Use pgvector image to support vector extension
RESTORE_DB_PORT = 5433  # Different port to avoid conflict
RESTORE_DB_USER = "restore_user"
RESTORE_DB_PASSWORD = "restore_temp_password"
RESTORE_DB_NAME = "n8n_restore"

# Module-level state for mounted backup
_mounted_backup_id: Optional[int] = None
_mounted_backup_info: Optional[Dict[str, Any]] = None

# File path for caching mounted workflow data
MOUNTED_WORKFLOWS_CACHE = "/tmp/n8n_mounted_workflows.json"
MOUNTED_CREDENTIALS_CACHE = "/tmp/n8n_mounted_credentials.json"


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
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                network = result.stdout.strip()
                logger.info(f"Found network from postgres container: {network}")
                return network
        except Exception as e:
            logger.warning(f"Failed to get network from postgres container: {e}")

        # Fallback: try to find network with n8n in the name
        try:
            cmd = ["docker", "network", "ls", "--format", "{{.Name}}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
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
        """
        logger.info("Starting restore container...")

        try:
            # Always remove existing container and create fresh
            check_cmd = ["docker", "ps", "-a", "--filter", f"name={RESTORE_CONTAINER_NAME}", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)

            if RESTORE_CONTAINER_NAME in result.stdout:
                logger.info("Removing existing restore container...")
                rm_result = subprocess.run(["docker", "rm", "-f", RESTORE_CONTAINER_NAME], capture_output=True, text=True)
                if rm_result.returncode != 0:
                    logger.warning(f"Failed to remove container: {rm_result.stderr}")

            # Get the correct Docker network
            docker_network = self._get_postgres_network()
            logger.info(f"Using Docker network: {docker_network}")

            # Create new container (no port binding needed - we use docker exec)
            logger.info("Creating new restore container...")
            create_cmd = [
                "docker", "run", "-d",
                "--name", RESTORE_CONTAINER_NAME,
                "-e", f"POSTGRES_USER={RESTORE_DB_USER}",
                "-e", f"POSTGRES_PASSWORD={RESTORE_DB_PASSWORD}",
                "-e", f"POSTGRES_DB={RESTORE_DB_NAME}",
                "--network", docker_network,
                RESTORE_CONTAINER_IMAGE,
            ]
            logger.info(f"Running: {' '.join(create_cmd)}")
            result = subprocess.run(create_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Docker run failed (exit code {result.returncode}): stdout={result.stdout}, stderr={result.stderr}")
                return False
            logger.info(f"Container created: {result.stdout.strip()}")

            # Wait for PostgreSQL to be ready
            await self._wait_for_postgres_ready()
            self._container_ready = True
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

    async def _wait_for_postgres_ready(self, timeout: int = 30) -> None:
        """Wait for PostgreSQL to accept connections."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            # First check if container is still running
            check_running = subprocess.run(
                ["docker", "ps", "--filter", f"name={RESTORE_CONTAINER_NAME}", "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            if RESTORE_CONTAINER_NAME not in check_running.stdout:
                # Container stopped - get logs to see why
                logs_result = subprocess.run(
                    ["docker", "logs", "--tail", "50", RESTORE_CONTAINER_NAME],
                    capture_output=True, text=True
                )
                logger.error(f"Restore container stopped unexpectedly. Logs:\n{logs_result.stdout}\n{logs_result.stderr}")
                raise Exception(f"Restore container stopped unexpectedly. Check logs for details.")

            try:
                check_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "pg_isready", "-U", RESTORE_DB_USER
                ]
                result = subprocess.run(check_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return
            except Exception as e:
                logger.debug(f"pg_isready check failed: {e}")
            await asyncio.sleep(1)

        # Timeout - get container status and logs
        logs_result = subprocess.run(
            ["docker", "logs", "--tail", "50", RESTORE_CONTAINER_NAME],
            capture_output=True, text=True
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
                subprocess.run, stop_cmd, capture_output=True, text=True
            )
            if stop_result.returncode != 0:
                logger.warning(f"Failed to stop container: {stop_result.stderr}")

            # Remove container (force to ensure cleanup)
            rm_cmd = ["docker", "rm", "-f", RESTORE_CONTAINER_NAME]
            rm_result = await asyncio.to_thread(
                subprocess.run, rm_cmd, capture_output=True, text=True
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
            result = subprocess.run(check_cmd, capture_output=True, text=True)
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
            result = subprocess.run(check_cmd, capture_output=True, text=True)
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
            # Reset the database before loading (use separate commands to avoid transaction block error)
            logger.info("Resetting restore database...")
            try:
                drop_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "psql", "-U", RESTORE_DB_USER, "-d", "postgres",
                    "-c", f"DROP DATABASE IF EXISTS {RESTORE_DB_NAME};"
                ]
                result = subprocess.run(drop_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"DROP DATABASE warning: {result.stderr}")

                create_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "psql", "-U", RESTORE_DB_USER, "-d", "postgres",
                    "-c", f"CREATE DATABASE {RESTORE_DB_NAME};"
                ]
                result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to reset restore database: {e.stderr if hasattr(e, 'stderr') else e}")
                return False

            # Check if it's a tar archive or a legacy gzipped SQL file
            is_tar_archive = False
            try:
                with tarfile.open(backup.filepath, "r:gz") as tar:
                    # Check if it has our expected structure
                    members = tar.getnames()
                    is_tar_archive = True
                    logger.info(f"Backup archive contains: {members[:10]}...")  # Log first 10 members
            except tarfile.TarError:
                logger.info("Not a tar archive, trying legacy format")
                is_tar_archive = False

            if not is_tar_archive:
                # Legacy format: gzipped SQL file
                logger.info("Legacy backup format detected")
                return await self._load_legacy_backup(backup.filepath)

            # Extract backup archive to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract tar.gz
                with tarfile.open(backup.filepath, "r:gz") as tar:
                    tar.extractall(temp_dir)

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
                result = subprocess.run(copy_cmd, capture_output=True, text=True)
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

                result = subprocess.run(restore_cmd, capture_output=True, text=True)
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
                verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
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
                with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
                    with gzip.open(filepath, 'rb') as f_in:
                        tmp.write(f_in.read())
                    sql_path = tmp.name
            else:
                sql_path = filepath

            # Copy to container
            copy_cmd = ["docker", "cp", sql_path, f"{RESTORE_CONTAINER_NAME}:/tmp/backup.sql"]
            subprocess.run(copy_cmd, capture_output=True, check=True)

            # Restore
            restore_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-f", "/tmp/backup.sql"
            ]
            subprocess.run(restore_cmd, capture_output=True, check=True)

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
            result = subprocess.run(query_cmd, capture_output=True, text=True)

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
            result = subprocess.run(query_cmd, capture_output=True, text=True)

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
            result = subprocess.run(query_cmd, capture_output=True, text=True)

            if not result.stdout.strip():
                # Log available IDs for debugging
                list_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                    "-t", "-A", "-c",
                    "SELECT id FROM workflow_entity"
                ]
                list_result = subprocess.run(list_cmd, capture_output=True, text=True)
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
            result = subprocess.run(query_cmd, capture_output=True, text=True)

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
            result = subprocess.run(query_cmd, capture_output=True, text=True)

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
            result = subprocess.run(query_cmd, capture_output=True, text=True)

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
            if not self.is_backup_mounted(backup_id):
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
            if not self.is_backup_mounted(backup_id):
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
            if not self.is_backup_mounted(backup_id):
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
        """
        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return None, {"error": "Backup not found"}

        if not os.path.exists(backup.filepath):
            return None, {"error": f"Backup file not found: {backup.filepath}"}

        try:
            temp_dir = tempfile.mkdtemp(prefix="n8n_restore_")

            with tarfile.open(backup.filepath, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Read metadata
            metadata_path = os.path.join(temp_dir, "metadata.json")
            metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

            return temp_dir, metadata

        except Exception as e:
            logger.error(f"Failed to extract backup: {e}")
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
            source_path = os.path.join(temp_dir, config_path)
            if not os.path.exists(source_path):
                return {"status": "failed", "error": f"Config file not found in backup: {config_path}"}

            # Determine target path
            if not target_path:
                # Map backup paths to host paths
                # Using /app/host_project/ which is a directory mount (more reliable than file mounts)
                path_mappings = {
                    # Core config files
                    "config/.env": "/app/host_project/.env",
                    "config/docker-compose.yaml": "/app/host_project/docker-compose.yaml",
                    "config/nginx.conf": "/app/host_project/nginx.conf",
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
                }
                target_path = path_mappings.get(config_path)

                # Handle SSL paths - map to /etc/letsencrypt/live/
                if config_path.startswith("ssl/"):
                    # ssl/domain/file.pem -> /etc/letsencrypt/live/domain/file.pem
                    ssl_relative = config_path[4:]  # Remove "ssl/" prefix
                    target_path = f"/etc/letsencrypt/live/{ssl_relative}"

                if not target_path:
                    return {"status": "failed", "error": f"No target path for: {config_path}"}

            # Create backup of existing file
            # NOTE: Config files are bind-mounted as individual files, not directories.
            # So we must save backups to /app/backups/config_backups/ (which IS mounted)
            # rather than alongside the original file (which would go to container FS)
            backup_created = None
            if create_backup and os.path.exists(target_path):
                # Save to mounted backup volume
                config_backup_dir = "/app/backups/config_backups"
                os.makedirs(config_backup_dir, exist_ok=True)

                # Create backup filename: original_name.bak.TIMESTAMP
                original_filename = os.path.basename(target_path)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"{original_filename}.bak.{timestamp}"
                backup_path = os.path.join(config_backup_dir, backup_filename)

                shutil.copy2(target_path, backup_path)
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
                return {"status": "failed", "error": f"File not found after restore: {target_path}"}

            return {
                "status": "success",
                "config_path": config_path,
                "target_path": target_path,
                "backup_created": backup_created,
                "message": f"Restored {os.path.basename(config_path)}",
            }

        except Exception as e:
            logger.error(f"Failed to restore config file: {e}")
            return {"status": "failed", "error": str(e)}

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def restore_database(
        self,
        backup_id: int,
        database_name: str,
        target_database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Restore a database from backup to the running PostgreSQL.

        WARNING: This overwrites the target database!

        Args:
            backup_id: The backup to restore from
            database_name: Database name in backup (e.g., "n8n")
            target_database: Target database (defaults to same name)

        Returns:
            Dict with status and details
        """
        if not target_database:
            target_database = database_name

        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return {"status": "failed", "error": metadata.get("error", "Extract failed")}

        try:
            dump_path = os.path.join(temp_dir, "databases", f"{database_name}.dump")
            if not os.path.exists(dump_path):
                return {"status": "failed", "error": f"Database dump not found: {database_name}"}

            # Get connection info
            host = os.environ.get("POSTGRES_HOST", "postgres")
            user = os.environ.get("POSTGRES_USER", "n8n")
            password = os.environ.get("POSTGRES_PASSWORD", "")

            env = {**os.environ, "PGPASSWORD": password}

            # Restore the dump
            restore_cmd = [
                "pg_restore",
                "-h", host,
                "-U", user,
                "-d", target_database,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                dump_path,
            ]

            result = subprocess.run(restore_cmd, capture_output=True, text=True, env=env)

            # pg_restore may return non-zero even for warnings
            if result.returncode != 0 and "ERROR" in result.stderr:
                logger.warning(f"pg_restore had errors: {result.stderr}")
                return {
                    "status": "partial",
                    "database": database_name,
                    "target": target_database,
                    "warnings": result.stderr,
                    "message": f"Restored {database_name} with warnings",
                }

            logger.info(f"Database restored: {database_name} -> {target_database}")
            return {
                "status": "success",
                "database": database_name,
                "target": target_database,
                "message": f"Restored database {database_name}",
            }

        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return {"status": "failed", "error": str(e)}

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
            }

            # Check databases
            db_dir = os.path.join(temp_dir, "databases")
            if os.path.exists(db_dir):
                for filename in os.listdir(db_dir):
                    if filename.endswith(".dump"):
                        db_name = filename[:-5]  # Remove .dump
                        dump_path = os.path.join(db_dir, filename)
                        stat = os.stat(dump_path)
                        preview["databases"].append({
                            "name": db_name,
                            "size": stat.st_size,
                            "row_counts": metadata.get("row_counts", {}).get(db_name, {}),
                        })

            # Check config files
            config_dir = os.path.join(temp_dir, "config")
            if os.path.exists(config_dir):
                for filename in os.listdir(config_dir):
                    filepath = os.path.join(config_dir, filename)
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        preview["config_files"].append({
                            "name": filename,
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

        This is a comprehensive restore that can restore:
        - Databases (n8n, n8n_management)
        - Config files (.env, docker-compose.yaml, nginx.conf)
        - SSL certificates

        WARNING: This will overwrite existing data!

        Args:
            backup_id: The backup to restore from
            restore_databases: Whether to restore databases
            restore_configs: Whether to restore config files
            restore_ssl: Whether to restore SSL certificates
            database_names: Specific databases to restore (None = all)
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

        temp_dir, metadata = await self.extract_backup_archive(backup_id)
        if not temp_dir:
            return {"status": "failed", "error": metadata.get("error", "Extract failed")}

        try:
            # Restore databases
            if restore_databases:
                db_dir = os.path.join(temp_dir, "databases")
                if os.path.exists(db_dir):
                    for filename in os.listdir(db_dir):
                        if filename.endswith(".dump"):
                            db_name = filename[:-5]
                            if database_names and db_name not in database_names:
                                continue

                            result = await self.restore_database(backup_id, db_name)
                            results["databases"].append(result)
                            if result["status"] == "failed":
                                results["errors"].append(f"Database {db_name}: {result.get('error')}")
                            elif result["status"] == "partial":
                                results["warnings"].append(f"Database {db_name}: {result.get('warnings')}")

            # Restore config files
            if restore_configs:
                config_dir = os.path.join(temp_dir, "config")
                if os.path.exists(config_dir):
                    for filename in os.listdir(config_dir):
                        if config_files and filename not in config_files:
                            continue

                        config_path = f"config/{filename}"
                        result = await self.restore_config_file(
                            backup_id, config_path, create_backup=create_backups
                        )
                        results["config_files"].append(result)
                        if result["status"] == "failed":
                            results["errors"].append(f"Config {filename}: {result.get('error')}")

            # Restore SSL certificates
            if restore_ssl:
                ssl_dir = os.path.join(temp_dir, "ssl")
                if os.path.exists(ssl_dir):
                    for domain in os.listdir(ssl_dir):
                        domain_path = os.path.join(ssl_dir, domain)
                        if os.path.isdir(domain_path):
                            for cert_file in os.listdir(domain_path):
                                cert_path = f"ssl/{domain}/{cert_file}"
                                result = await self.restore_config_file(
                                    backup_id, cert_path, create_backup=create_backups
                                )
                                results["ssl_certificates"].append(result)
                                if result["status"] == "failed":
                                    results["errors"].append(f"SSL {domain}/{cert_file}: {result.get('error')}")

            # Determine overall status
            if results["errors"]:
                results["status"] = "partial" if (results["databases"] or results["config_files"]) else "failed"
            else:
                results["status"] = "success"

            results["message"] = f"Restored {len(results['databases'])} databases, {len(results['config_files'])} config files, {len(results['ssl_certificates'])} SSL certs"
            logger.info(f"Full system restore completed: {results['message']}")

            return results

        except Exception as e:
            logger.error(f"Full system restore failed: {e}")
            return {"status": "failed", "error": str(e)}

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
