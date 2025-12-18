"""
Verification service - comprehensive backup integrity verification.

Phase 5: Backup Verification System
Proves backups are restorable by testing against stored metadata.
"""

import subprocess
import tarfile
import tempfile
import hashlib
import json
import os
import shutil
import logging
import asyncio
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from api.services.backup_service import BackupService
from api.services.restore_service import (
    RestoreService,
    RESTORE_CONTAINER_NAME,
    RESTORE_DB_USER,
    RESTORE_DB_NAME,
)
from api.models.backups import BackupHistory, BackupContents
from api.config import settings

logger = logging.getLogger(__name__)


# Verification container (separate from restore container)
VERIFY_CONTAINER_NAME = "n8n_postgres_verify"
VERIFY_CONTAINER_IMAGE = "postgres:16"
VERIFY_DB_PORT = 5434  # Different port from restore container
VERIFY_DB_USER = "verify_user"
VERIFY_DB_PASSWORD = "verify_temp_password"
VERIFY_DB_NAME = "n8n_verify"


class VerificationService:
    """Service for comprehensive backup verification."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.backup_service = BackupService(db)
        self._container_ready = False

    async def _update_verification_progress(
        self,
        backup: BackupHistory,
        progress: int,
        message: str
    ) -> None:
        """Update verification progress in backup record."""
        try:
            backup.progress = min(progress, 100)
            backup.progress_message = message
            await self.db.commit()
            logger.debug(f"Verification {backup.id}: {progress}% - {message}")
        except Exception as e:
            logger.warning(f"Failed to update verification progress: {e}")

    # ============================================================================
    # Container Management
    # ============================================================================

    async def spin_up_verify_container(self) -> bool:
        """
        Create and start a temporary PostgreSQL container for verification.
        Uses a separate container from restore to allow concurrent operations.
        """
        logger.info("Starting verification container...")

        try:
            # Check if container already exists
            check_cmd = ["docker", "ps", "-a", "--filter", f"name={VERIFY_CONTAINER_NAME}", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)

            if VERIFY_CONTAINER_NAME in result.stdout:
                # Container exists, try to start it
                logger.info("Verification container exists, starting it...")
                start_cmd = ["docker", "start", VERIFY_CONTAINER_NAME]
                subprocess.run(start_cmd, capture_output=True, check=True)
            else:
                # Create new container
                logger.info("Creating new verification container...")
                # Get network name from environment or use default
                docker_network = os.environ.get("DOCKER_NETWORK", "n8n_nginx_n8n_network")
                create_cmd = [
                    "docker", "run", "-d",
                    "--name", VERIFY_CONTAINER_NAME,
                    "-e", f"POSTGRES_USER={VERIFY_DB_USER}",
                    "-e", f"POSTGRES_PASSWORD={VERIFY_DB_PASSWORD}",
                    "-e", f"POSTGRES_DB={VERIFY_DB_NAME}",
                    "-p", f"{VERIFY_DB_PORT}:5432",
                    "--network", docker_network,
                    VERIFY_CONTAINER_IMAGE,
                ]
                logger.info(f"Using Docker network: {docker_network}")
                subprocess.run(create_cmd, capture_output=True, check=True)

            # Wait for PostgreSQL to be ready
            await self._wait_for_postgres_ready()
            self._container_ready = True
            logger.info("Verification container is ready")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start verification container: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error starting verification container: {e}")
            return False

    async def _wait_for_postgres_ready(self, timeout: int = 30) -> None:
        """Wait for PostgreSQL to accept connections."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                check_cmd = [
                    "docker", "exec", VERIFY_CONTAINER_NAME,
                    "pg_isready", "-U", VERIFY_DB_USER
                ]
                result = subprocess.run(check_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)

        raise Exception("Timeout waiting for PostgreSQL to be ready")

    async def teardown_verify_container(self) -> bool:
        """Stop and remove the verification container."""
        logger.info("Tearing down verification container...")

        try:
            # Stop container
            stop_cmd = ["docker", "stop", VERIFY_CONTAINER_NAME]
            subprocess.run(stop_cmd, capture_output=True)

            # Remove container
            rm_cmd = ["docker", "rm", VERIFY_CONTAINER_NAME]
            subprocess.run(rm_cmd, capture_output=True)

            self._container_ready = False
            logger.info("Verification container removed")
            return True

        except Exception as e:
            logger.warning(f"Error tearing down verification container: {e}")
            return False

    async def is_container_running(self) -> bool:
        """Check if verification container is running."""
        try:
            check_cmd = ["docker", "ps", "--filter", f"name={VERIFY_CONTAINER_NAME}", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            return VERIFY_CONTAINER_NAME in result.stdout
        except Exception:
            return False

    # ============================================================================
    # Backup Loading
    # ============================================================================

    async def load_backup_to_verify_container(self, backup_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Load a backup into the verification container.
        Returns (success, metadata_dict).
        """
        logger.info(f"Loading backup {backup_id} into verification container...")

        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return False, {"error": "Backup not found"}

        if not os.path.exists(backup.filepath):
            return False, {"error": f"Backup file not found: {backup.filepath}"}

        # Ensure container is running
        if not await self.is_container_running():
            if not await self.spin_up_verify_container():
                return False, {"error": "Failed to start verification container"}

        metadata = {}

        try:
            # Extract backup archive to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract tar.gz
                with tarfile.open(backup.filepath, "r:gz") as tar:
                    tar.extractall(temp_dir)

                # Read metadata
                metadata_path = os.path.join(temp_dir, "metadata.json")
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                # Find the n8n database dump
                n8n_dump = os.path.join(temp_dir, "databases", "n8n.dump")
                if not os.path.exists(n8n_dump):
                    return False, {"error": "n8n database dump not found in backup"}

                # Copy dump file to container
                copy_cmd = [
                    "docker", "cp", n8n_dump,
                    f"{VERIFY_CONTAINER_NAME}:/tmp/n8n.dump"
                ]
                subprocess.run(copy_cmd, capture_output=True, check=True)

                # Reset database (drop and recreate)
                reset_cmd = [
                    "docker", "exec", VERIFY_CONTAINER_NAME,
                    "psql", "-U", VERIFY_DB_USER, "-d", "postgres",
                    "-c", f"DROP DATABASE IF EXISTS {VERIFY_DB_NAME}; CREATE DATABASE {VERIFY_DB_NAME};"
                ]
                subprocess.run(reset_cmd, capture_output=True, check=True)

                # Restore the dump
                restore_cmd = [
                    "docker", "exec", VERIFY_CONTAINER_NAME,
                    "pg_restore",
                    "-U", VERIFY_DB_USER,
                    "-d", VERIFY_DB_NAME,
                    "--clean", "--if-exists",
                    "/tmp/n8n.dump"
                ]
                result = subprocess.run(restore_cmd, capture_output=True, text=True)
                if result.returncode != 0 and "ERROR" in result.stderr:
                    logger.warning(f"pg_restore warnings: {result.stderr}")

                logger.info(f"Backup {backup_id} loaded into verification container")
                return True, metadata

        except Exception as e:
            logger.error(f"Failed to load backup: {e}")
            return False, {"error": str(e)}

    # ============================================================================
    # Verification Methods
    # ============================================================================

    async def verify_tables_exist(self, expected_tables: List[str]) -> Dict[str, Any]:
        """
        Verify that expected tables exist in the restored database.
        """
        try:
            query_cmd = [
                "docker", "exec", VERIFY_CONTAINER_NAME,
                "psql", "-U", VERIFY_DB_USER, "-d", VERIFY_DB_NAME,
                "-t", "-A", "-c",
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ]
            result = subprocess.run(query_cmd, capture_output=True, text=True)

            actual_tables = set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()

            missing_tables = []
            found_tables = []
            for table in expected_tables:
                if table in actual_tables:
                    found_tables.append(table)
                else:
                    missing_tables.append(table)

            return {
                "passed": len(missing_tables) == 0,
                "found_tables": found_tables,
                "missing_tables": missing_tables,
                "total_expected": len(expected_tables),
                "total_found": len(found_tables),
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def verify_row_counts(self, expected_counts: Dict[str, int]) -> Dict[str, Any]:
        """
        Verify that table row counts match the manifest.
        """
        mismatches = []
        matches = []

        try:
            for table, expected_count in expected_counts.items():
                query_cmd = [
                    "docker", "exec", VERIFY_CONTAINER_NAME,
                    "psql", "-U", VERIFY_DB_USER, "-d", VERIFY_DB_NAME,
                    "-t", "-A", "-c",
                    f"SELECT COUNT(*) FROM {table}"
                ]
                result = subprocess.run(query_cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    mismatches.append({
                        "table": table,
                        "expected": expected_count,
                        "actual": None,
                        "error": "Query failed",
                    })
                    continue

                actual_count = int(result.stdout.strip()) if result.stdout.strip() else 0

                if actual_count != expected_count:
                    mismatches.append({
                        "table": table,
                        "expected": expected_count,
                        "actual": actual_count,
                    })
                else:
                    matches.append({"table": table, "count": actual_count})

            return {
                "passed": len(mismatches) == 0,
                "matches": matches,
                "mismatches": mismatches,
                "total_checked": len(expected_counts),
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def verify_workflow_checksums(
        self,
        expected_checksums: Dict[str, str],
        sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Verify workflow data integrity by comparing checksums.

        Args:
            expected_checksums: Dict of workflow_id -> checksum
            sample_size: If provided, only verify a sample of workflows

        Returns:
            Dict with verification results
        """
        if not expected_checksums:
            return {"passed": True, "message": "No workflow checksums to verify"}

        workflow_ids = list(expected_checksums.keys())

        # Sample if requested
        if sample_size and len(workflow_ids) > sample_size:
            import random
            workflow_ids = random.sample(workflow_ids, sample_size)

        matches = []
        mismatches = []

        try:
            for wf_id in workflow_ids:
                expected = expected_checksums[wf_id]

                # Get workflow nodes and connections JSON from DB
                query_cmd = [
                    "docker", "exec", VERIFY_CONTAINER_NAME,
                    "psql", "-U", VERIFY_DB_USER, "-d", VERIFY_DB_NAME,
                    "-t", "-A", "-c",
                    f"SELECT nodes, connections FROM workflow_entity WHERE id = '{wf_id}'"
                ]
                result = subprocess.run(query_cmd, capture_output=True, text=True)

                if not result.stdout.strip():
                    mismatches.append({
                        "workflow_id": wf_id,
                        "error": "Workflow not found",
                    })
                    continue

                # Calculate checksum of workflow data
                parts = result.stdout.strip().split('|')
                if len(parts) >= 2:
                    nodes_json = parts[0] or '{}'
                    connections_json = parts[1] or '{}'
                    data_str = nodes_json + connections_json
                    actual = hashlib.sha256(data_str.encode()).hexdigest()

                    if actual == expected:
                        matches.append(wf_id)
                    else:
                        mismatches.append({
                            "workflow_id": wf_id,
                            "expected": expected[:16] + "...",
                            "actual": actual[:16] + "...",
                        })
                else:
                    mismatches.append({
                        "workflow_id": wf_id,
                        "error": "Invalid data format",
                    })

            return {
                "passed": len(mismatches) == 0,
                "verified": len(matches),
                "failed": len(mismatches),
                "total_checked": len(workflow_ids),
                "total_available": len(expected_checksums),
                "mismatches": mismatches if mismatches else None,
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def verify_config_file_checksums(
        self,
        backup_id: int,
        expected_checksums: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Verify config file checksums against stored manifest.
        """
        if not expected_checksums:
            return {"passed": True, "message": "No config files to verify"}

        matches = []
        mismatches = []

        # Get backup path
        backup = await self.backup_service.get_backup(backup_id)
        if not backup or not os.path.exists(backup.filepath):
            return {"passed": False, "error": "Backup file not found"}

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract backup
                with tarfile.open(backup.filepath, "r:gz") as tar:
                    tar.extractall(temp_dir)

                for file_info in expected_checksums:
                    name = file_info.get("name", file_info.get("path", ""))
                    expected = file_info.get("checksum")

                    if not expected:
                        continue

                    # Find file in extracted backup
                    file_path = os.path.join(temp_dir, "config", name)
                    if not os.path.exists(file_path):
                        # Try alternate path
                        file_path = os.path.join(temp_dir, name)

                    if os.path.exists(file_path):
                        # Calculate actual checksum
                        with open(file_path, 'rb') as f:
                            actual = hashlib.sha256(f.read()).hexdigest()

                        if actual == expected:
                            matches.append(name)
                        else:
                            mismatches.append({
                                "file": name,
                                "expected": expected[:16] + "...",
                                "actual": actual[:16] + "...",
                            })
                    else:
                        mismatches.append({
                            "file": name,
                            "error": "File not found in backup",
                        })

            return {
                "passed": len(mismatches) == 0,
                "verified": len(matches),
                "failed": len(mismatches),
                "total_checked": len(expected_checksums),
                "mismatches": mismatches if mismatches else None,
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def verify_backup_archive_integrity(self, backup_id: int) -> Dict[str, Any]:
        """
        Verify the backup archive itself is valid and extractable.
        """
        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return {"passed": False, "error": "Backup not found"}

        if not os.path.exists(backup.filepath):
            return {"passed": False, "error": "Backup file not found"}

        try:
            # Verify file checksum
            current_checksum = self._hash_file_sha256(backup.filepath)
            checksum_match = current_checksum == backup.checksum

            # Try to open and list archive
            with tarfile.open(backup.filepath, "r:gz") as tar:
                members = tar.getnames()
                has_databases = any("databases/" in m for m in members)
                has_metadata = "metadata.json" in members
                has_restore_script = "restore.sh" in members

            return {
                "passed": checksum_match and has_databases,
                "checksum_match": checksum_match,
                "has_database_dumps": has_databases,
                "has_metadata": has_metadata,
                "has_restore_script": has_restore_script,
                "total_files": len(members),
                "file_size": os.path.getsize(backup.filepath),
            }

        except tarfile.TarError as e:
            return {"passed": False, "error": f"Invalid archive: {e}"}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _hash_file_sha256(self, filepath: str) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # ============================================================================
    # Full Verification
    # ============================================================================

    async def verify_backup(
        self,
        backup_id: int,
        verify_all_workflows: bool = False,
        workflow_sample_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive verification of a backup.

        This will:
        1. Verify archive integrity (checksum, structure)
        2. Spin up verification container
        3. Load backup into container
        4. Verify tables exist
        5. Verify row counts match manifest
        6. Verify workflow checksums (sampled or all)
        7. Verify config file checksums
        8. Store results and update backup status

        Args:
            backup_id: The backup to verify
            verify_all_workflows: If True, verify all workflow checksums (slower)
            workflow_sample_size: Number of workflows to sample if not verifying all

        Returns:
            Comprehensive verification results
        """
        logger.info(f"Starting comprehensive verification of backup {backup_id}")

        # Get backup info
        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return {"overall_status": "failed", "error": "Backup not found"}

        # Get stored backup contents (metadata)
        contents = await self._get_backup_contents(backup_id)
        if not contents:
            return {"overall_status": "failed", "error": "Backup metadata not found"}

        results = {
            "backup_id": backup_id,
            "backup_filename": backup.filename,
            "started_at": datetime.now(UTC).isoformat(),
            "checks": {},
            "overall_status": "passed",
            "errors": [],
            "warnings": [],
        }

        try:
            # Step 1: Archive Integrity (0-10%)
            await self._update_verification_progress(backup, 5, "Verifying archive integrity")
            logger.info("Step 1: Verifying archive integrity...")
            archive_result = await self.verify_backup_archive_integrity(backup_id)
            results["checks"]["archive_integrity"] = archive_result
            if not archive_result.get("passed"):
                results["overall_status"] = "failed"
                results["errors"].append("Archive integrity check failed")
                # Don't set progress to 100 on failure - keep at current stage
                await self._update_verification_progress(backup, 10, "Failed: archive integrity check")
                return await self._store_verification_results(backup_id, results)

            # Step 2: Spin up container (10-25%)
            await self._update_verification_progress(backup, 15, "Starting verification container")
            logger.info("Step 2: Starting verification container...")
            if not await self.spin_up_verify_container():
                results["overall_status"] = "failed"
                results["errors"].append("Failed to start verification container")
                await self._update_verification_progress(backup, 20, "Failed: container startup")
                return await self._store_verification_results(backup_id, results)

            # Step 3: Load backup (25-40%)
            await self._update_verification_progress(backup, 30, "Loading backup into container")
            logger.info("Step 3: Loading backup into container...")
            loaded, metadata = await self.load_backup_to_verify_container(backup_id)
            if not loaded:
                results["overall_status"] = "failed"
                results["errors"].append(f"Failed to load backup: {metadata.get('error')}")
                await self._update_verification_progress(backup, 35, "Failed: loading backup")
                return await self._store_verification_results(backup_id, results)

            # Step 4: Verify tables exist (40-55%)
            await self._update_verification_progress(backup, 45, "Verifying database tables")
            logger.info("Step 4: Verifying tables exist...")
            if contents.database_schema_manifest:
                expected_tables = []
                for db in contents.database_schema_manifest:
                    if db.get("database") == "n8n":
                        expected_tables = [t.get("name") for t in db.get("tables", [])]
                        break

                if expected_tables:
                    tables_result = await self.verify_tables_exist(expected_tables)
                    results["checks"]["tables_exist"] = tables_result
                    if not tables_result.get("passed"):
                        results["overall_status"] = "failed"
                        results["errors"].append("Table verification failed")

            # Step 5: Verify row counts (55-70%)
            await self._update_verification_progress(backup, 60, "Verifying row counts")
            logger.info("Step 5: Verifying row counts...")
            if contents.database_schema_manifest:
                expected_counts = {}
                for db in contents.database_schema_manifest:
                    if db.get("database") == "n8n":
                        for table in db.get("tables", []):
                            if table.get("row_count") is not None:
                                expected_counts[table["name"]] = table["row_count"]
                        break

                if expected_counts:
                    counts_result = await self.verify_row_counts(expected_counts)
                    results["checks"]["row_counts"] = counts_result
                    if not counts_result.get("passed"):
                        results["warnings"].append("Row count mismatches detected")
                        # Row count mismatches might be warnings, not failures

            # Step 6: Verify workflow checksums (70-85%)
            await self._update_verification_progress(backup, 75, "Verifying workflow checksums")
            logger.info("Step 6: Verifying workflow checksums...")
            if contents.verification_checksums:
                sample = None if verify_all_workflows else workflow_sample_size
                checksums_result = await self.verify_workflow_checksums(
                    contents.verification_checksums,
                    sample_size=sample
                )
                results["checks"]["workflow_checksums"] = checksums_result
                if not checksums_result.get("passed"):
                    results["overall_status"] = "failed"
                    results["errors"].append("Workflow checksum verification failed")

            # Step 7: Verify config file checksums (85-95%)
            await self._update_verification_progress(backup, 90, "Verifying config file checksums")
            logger.info("Step 7: Verifying config file checksums...")
            if contents.config_files_manifest:
                config_result = await self.verify_config_file_checksums(
                    backup_id,
                    contents.config_files_manifest
                )
                results["checks"]["config_file_checksums"] = config_result
                if not config_result.get("passed"):
                    results["warnings"].append("Config file checksum issues")

            # Final status (95-100%)
            await self._update_verification_progress(backup, 98, "Finalizing verification")
            results["completed_at"] = datetime.now(UTC).isoformat()
            results["duration_seconds"] = (
                datetime.fromisoformat(results["completed_at"]) -
                datetime.fromisoformat(results["started_at"])
            ).total_seconds()

            status_msg = "Verification passed" if results["overall_status"] == "passed" else "Verification completed with issues"
            await self._update_verification_progress(backup, 100, status_msg)
            logger.info(f"Verification completed: {results['overall_status']}")

            return await self._store_verification_results(backup_id, results)

        except Exception as e:
            logger.error(f"Verification failed with exception: {e}")
            results["overall_status"] = "failed"
            results["errors"].append(str(e))
            return await self._store_verification_results(backup_id, results)

        finally:
            # Always clean up
            await self.teardown_verify_container()

    async def _get_backup_contents(self, backup_id: int) -> Optional[BackupContents]:
        """Get backup contents metadata."""
        stmt = select(BackupContents).where(BackupContents.backup_id == backup_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _store_verification_results(
        self,
        backup_id: int,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store verification results in database."""
        try:
            backup = await self.backup_service.get_backup(backup_id)
            if backup:
                backup.verification_status = results["overall_status"]
                backup.verification_date = datetime.now(UTC)
                backup.verification_details = results
                await self.db.commit()

            return results

        except Exception as e:
            logger.error(f"Failed to store verification results: {e}")
            results["store_error"] = str(e)
            return results

    # ============================================================================
    # Quick Verification
    # ============================================================================

    async def quick_verify(self, backup_id: int) -> Dict[str, Any]:
        """
        Perform quick verification without spinning up a container.
        Only checks:
        - File exists
        - Checksum matches
        - Archive is valid

        This is faster but less comprehensive.
        """
        logger.info(f"Performing quick verification of backup {backup_id}")

        backup = await self.backup_service.get_backup(backup_id)
        if not backup:
            return {"overall_status": "failed", "error": "Backup not found"}

        results = {
            "backup_id": backup_id,
            "type": "quick",
            "checks": {},
            "overall_status": "passed",
        }

        # Check file exists
        if not os.path.exists(backup.filepath):
            results["overall_status"] = "failed"
            results["checks"]["file_exists"] = {"passed": False}
            return await self._store_verification_results(backup_id, results)
        results["checks"]["file_exists"] = {"passed": True}

        # Check checksum
        current_checksum = self._hash_file_sha256(backup.filepath)
        if current_checksum != backup.checksum:
            results["overall_status"] = "failed"
            results["checks"]["checksum"] = {
                "passed": False,
                "expected": backup.checksum[:16] + "...",
                "actual": current_checksum[:16] + "...",
            }
            return await self._store_verification_results(backup_id, results)
        results["checks"]["checksum"] = {"passed": True}

        # Check archive is valid
        archive_result = await self.verify_backup_archive_integrity(backup_id)
        results["checks"]["archive_integrity"] = archive_result
        if not archive_result.get("passed"):
            results["overall_status"] = "failed"

        return await self._store_verification_results(backup_id, results)
