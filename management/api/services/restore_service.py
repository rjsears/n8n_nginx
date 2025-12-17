"""
Restore service - handles selective workflow restoration from backups.

Phase 3: Selective workflow restore using temporary PostgreSQL containers.
"""

import subprocess
import tarfile
import tempfile
import json
import os
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
RESTORE_CONTAINER_IMAGE = "postgres:16"
RESTORE_DB_PORT = 5433  # Different port to avoid conflict
RESTORE_DB_USER = "restore_user"
RESTORE_DB_PASSWORD = "restore_temp_password"
RESTORE_DB_NAME = "n8n_restore"


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

    async def spin_up_restore_container(self) -> bool:
        """
        Create and start a temporary PostgreSQL container for restore operations.
        Returns True if successful.
        """
        logger.info("Starting restore container...")

        try:
            # Check if container already exists
            check_cmd = ["docker", "ps", "-a", "--filter", f"name={RESTORE_CONTAINER_NAME}", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)

            if RESTORE_CONTAINER_NAME in result.stdout:
                # Container exists, try to start it
                logger.info("Restore container exists, starting it...")
                start_cmd = ["docker", "start", RESTORE_CONTAINER_NAME]
                subprocess.run(start_cmd, capture_output=True, check=True)
            else:
                # Create new container
                logger.info("Creating new restore container...")
                create_cmd = [
                    "docker", "run", "-d",
                    "--name", RESTORE_CONTAINER_NAME,
                    "-e", f"POSTGRES_USER={RESTORE_DB_USER}",
                    "-e", f"POSTGRES_PASSWORD={RESTORE_DB_PASSWORD}",
                    "-e", f"POSTGRES_DB={RESTORE_DB_NAME}",
                    "-p", f"{RESTORE_DB_PORT}:5432",
                    "--network", "n8n-network",  # Same network as other containers
                    RESTORE_CONTAINER_IMAGE,
                ]
                subprocess.run(create_cmd, capture_output=True, check=True)

            # Wait for PostgreSQL to be ready
            await self._wait_for_postgres_ready()
            self._container_ready = True
            logger.info("Restore container is ready")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start restore container: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error starting restore container: {e}")
            return False

    async def _wait_for_postgres_ready(self, timeout: int = 30) -> None:
        """Wait for PostgreSQL to accept connections."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                check_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "pg_isready", "-U", RESTORE_DB_USER
                ]
                result = subprocess.run(check_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)

        raise Exception("Timeout waiting for PostgreSQL to be ready")

    async def teardown_restore_container(self) -> bool:
        """Stop and remove the restore container."""
        logger.info("Tearing down restore container...")

        try:
            # Stop container
            stop_cmd = ["docker", "stop", RESTORE_CONTAINER_NAME]
            subprocess.run(stop_cmd, capture_output=True)

            # Remove container
            rm_cmd = ["docker", "rm", RESTORE_CONTAINER_NAME]
            subprocess.run(rm_cmd, capture_output=True)

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
            # Extract backup archive to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract tar.gz
                with tarfile.open(backup.filepath, "r:gz") as tar:
                    tar.extractall(temp_dir)

                # Find the n8n database dump
                n8n_dump = os.path.join(temp_dir, "databases", "n8n.dump")
                if not os.path.exists(n8n_dump):
                    # Try alternate path for older backups
                    n8n_dump = backup.filepath
                    if backup.filepath.endswith('.gz'):
                        # It's a gzipped SQL file, not our new format
                        logger.info("Legacy backup format detected")
                        return await self._load_legacy_backup(backup.filepath)

                # Copy dump file to container
                copy_cmd = [
                    "docker", "cp", n8n_dump,
                    f"{RESTORE_CONTAINER_NAME}:/tmp/n8n.dump"
                ]
                subprocess.run(copy_cmd, capture_output=True, check=True)

                # Restore the dump
                restore_cmd = [
                    "docker", "exec", RESTORE_CONTAINER_NAME,
                    "pg_restore",
                    "-U", RESTORE_DB_USER,
                    "-d", RESTORE_DB_NAME,
                    "--clean", "--if-exists",
                    "/tmp/n8n.dump"
                ]
                result = subprocess.run(restore_cmd, capture_output=True, text=True)
                # pg_restore may return warnings, check for actual errors
                if result.returncode != 0 and "ERROR" in result.stderr:
                    logger.warning(f"pg_restore warnings: {result.stderr}")

                logger.info(f"Backup {backup_id} loaded into restore container")
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
                'SELECT id, name, active, "createdAt", "updatedAt" FROM workflow_entity ORDER BY name'
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
                    })

            return workflows

        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return []

    async def extract_workflow_from_restore_db(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract a specific workflow from the restore database.
        Returns the complete workflow data as JSON.
        """
        if not await self.is_container_running():
            logger.error("Restore container not running")
            return None

        try:
            # Query workflow data
            query_cmd = [
                "docker", "exec", RESTORE_CONTAINER_NAME,
                "psql", "-U", RESTORE_DB_USER, "-d", RESTORE_DB_NAME,
                "-t", "-A", "-c",
                f"SELECT id, name, active, nodes, connections, settings, \"staticData\", \"createdAt\", \"updatedAt\" "
                f"FROM workflow_entity WHERE id = '{workflow_id}'"
            ]
            result = subprocess.run(query_cmd, capture_output=True, text=True)

            if not result.stdout.strip():
                logger.error(f"Workflow {workflow_id} not found in restore database")
                return None

            # Parse the result - columns are pipe-separated
            parts = result.stdout.strip().split('|')
            if len(parts) < 6:
                logger.error(f"Invalid workflow data format")
                return None

            # Parse JSON fields
            nodes = json.loads(parts[3]) if parts[3] else []
            connections = json.loads(parts[4]) if parts[4] else {}
            workflow_settings = json.loads(parts[5]) if parts[5] else {}
            static_data = json.loads(parts[6]) if parts[6] and parts[6] != '\\N' else None

            workflow = {
                "id": parts[0],
                "name": parts[1],
                "active": parts[2] == 't',
                "nodes": nodes,
                "connections": connections,
                "settings": workflow_settings,
                "staticData": static_data,
                "createdAt": parts[7] if len(parts) > 7 else None,
                "updatedAt": parts[8] if len(parts) > 8 else None,
            }

            return workflow

        except Exception as e:
            logger.error(f"Failed to extract workflow {workflow_id}: {e}")
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
        logger.info(f"Restoring workflow {workflow_id} from backup {backup_id}")

        try:
            # Step 1: Ensure container is ready
            if not await self.is_container_running():
                if not await self.spin_up_restore_container():
                    return {"status": "failed", "error": "Failed to start restore container"}

            # Step 2: Load backup into container
            if not await self.load_backup_to_restore_container(backup_id):
                return {"status": "failed", "error": "Failed to load backup"}

            # Step 3: Extract the workflow
            workflow = await self.extract_workflow_from_restore_db(workflow_id)
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
            import_workflow = {
                "name": new_name,
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow.get("settings", {}),
                "active": False,  # Always start inactive
            }

            # Step 7: Push to n8n via API
            n8n_service = N8nApiService()
            result = await n8n_service.create_workflow(import_workflow)

            if result.get("id"):
                logger.info(f"Workflow restored successfully as '{new_name}' with ID {result['id']}")
                return {
                    "status": "success",
                    "original_name": original_name,
                    "new_name": new_name,
                    "new_workflow_id": result["id"],
                    "message": f"Workflow restored as '{new_name}'",
                }
            else:
                return {"status": "failed", "error": "n8n API did not return workflow ID"}

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
        """
        try:
            # Ensure container is ready
            if not await self.is_container_running():
                if not await self.spin_up_restore_container():
                    return None

            # Load backup
            if not await self.load_backup_to_restore_container(backup_id):
                return None

            # Extract workflow
            workflow = await self.extract_workflow_from_restore_db(workflow_id)
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
