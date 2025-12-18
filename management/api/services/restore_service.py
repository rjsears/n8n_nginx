"""
Restore service - handles selective workflow restoration from backups.

Phase 3: Selective workflow restore using temporary PostgreSQL containers.
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
                logger.info(f"Found network from postgres container: {result.stdout.strip()}")
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Failed to get network from postgres container: {e}")

        # Fallback: try to find network with n8n in the name
        try:
            cmd = ["docker", "network", "ls", "--format", "{{.Name}}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            for network in result.stdout.strip().split('\n'):
                if 'n8n' in network.lower() and 'network' in network.lower():
                    logger.info(f"Found n8n network by search: {network}")
                    return network
        except Exception:
            pass

        # Final fallback
        logger.warning("Using fallback network name: n8n_nginx_n8n_network")
        return "n8n_nginx_n8n_network"

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

            # Create new container
            logger.info("Creating new restore container...")
            create_cmd = [
                "docker", "run", "-d",
                "--name", RESTORE_CONTAINER_NAME,
                "-e", f"POSTGRES_USER={RESTORE_DB_USER}",
                "-e", f"POSTGRES_PASSWORD={RESTORE_DB_PASSWORD}",
                "-e", f"POSTGRES_DB={RESTORE_DB_NAME}",
                "-p", f"{RESTORE_DB_PORT}:5432",
                "--network", docker_network,
                RESTORE_CONTAINER_IMAGE,
            ]
            result = subprocess.run(create_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Docker run failed: stdout={result.stdout}, stderr={result.stderr}")
                return False

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
                path_mappings = {
                    "config/.env": "/app/host_env/.env",
                    "config/docker-compose.yaml": "/app/host_config/docker-compose.yaml",
                    "config/nginx.conf": "/app/host_config/nginx.conf",
                    "config/cloudflare.ini": "/app/host_config/cloudflare.ini",
                }
                target_path = path_mappings.get(config_path)

                # Handle SSL paths
                if config_path.startswith("ssl/"):
                    ssl_relative = config_path[4:]  # Remove "ssl/" prefix
                    target_path = f"/etc/letsencrypt/live/{ssl_relative}"

                if not target_path:
                    return {"status": "failed", "error": f"No target path for: {config_path}"}

            # Create backup of existing file
            backup_created = None
            if create_backup and os.path.exists(target_path):
                backup_path = f"{target_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(target_path, backup_path)
                backup_created = backup_path
                logger.info(f"Created backup: {backup_created}")

            # Ensure target directory exists
            target_dir = os.path.dirname(target_path)
            os.makedirs(target_dir, exist_ok=True)

            # Copy file
            shutil.copy2(source_path, target_path)
            logger.info(f"Restored config file: {config_path} -> {target_path}")

            return {
                "status": "success",
                "config_path": config_path,
                "target_path": target_path,
                "backup_created": backup_created,
                "message": f"Restored {config_path}",
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
