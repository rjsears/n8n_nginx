"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/verification_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import re
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

from api.services.backup_service import BackupService, WORKFLOW_CHECKSUM_SQL, inspect_backup_archive
from api.services.restore_service import (
    RestoreService,
    RESTORE_CONTAINER_NAME,
    RESTORE_DB_USER,
    RESTORE_DB_NAME,
    _extract_tar_sync,
)
from api.services.notification_service import dispatch_notification
from api.models.backups import BackupHistory, BackupContents
from api.config import settings

logger = logging.getLogger(__name__)


# Verification container (separate from restore container)
VERIFY_CONTAINER_NAME = "n8n_postgres_verify"
VERIFY_CONTAINER_IMAGE = "pgvector/pgvector:pg16"  # same image (and extensions) as the stack's postgres
VERIFY_DB_PORT = 5434  # Different port from restore container
VERIFY_DB_USER = "verify_user"
VERIFY_DB_PASSWORD = "verify_temp_password"
VERIFY_DB_NAME = "n8n_verify"

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def verify_db_name(source_db: str) -> str:
    """Database inside the verification container that holds the copy of source_db."""
    return VERIFY_DB_NAME if source_db == "n8n" else f"{source_db}_verify"


def _production_postgres_image() -> Optional[str]:
    """Image reference the stack's postgres container runs (None if unknown)."""
    try:
        result = subprocess.run(
            ["docker", "inspect", os.environ.get("POSTGRES_HOST", "n8n_postgres"), "--format", "{{.Config.Image}}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def parse_workflow_checksum_rows(output: str) -> Dict[str, Dict[str, Any]]:
    """Parse `psql -t -A -F <tab>` output of WORKFLOW_CHECKSUM_SQL."""
    rows: Dict[str, Dict[str, Any]] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        updated = parts[2].strip()
        rows[parts[0]] = {
            "sha256": parts[1].strip(),
            "updated_at_ms": int(updated) if updated.lstrip("-").isdigit() else None,
        }
    return rows


def compare_workflow_checksums(
    expected: Dict[str, Any],
    restored: Dict[str, Dict[str, Any]],
    workflow_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compare recorded workflow checksums with those of a restored copy."""
    matches: List[str] = []
    mismatches: List[Dict[str, Any]] = []
    changed_during_backup: List[str] = []
    ids = workflow_ids if workflow_ids is not None else list(expected)
    for wf_id in ids:
        want = expected[wf_id]
        if isinstance(want, str):  # plain checksum
            want = {"sha256": want, "updated_at_ms": None}
        got = restored.get(wf_id)
        if got is None:
            mismatches.append({"workflow_id": wf_id, "error": "Workflow missing from restored database"})
        elif got["sha256"] == want.get("sha256"):
            matches.append(wf_id)
        elif want.get("updated_at_ms") is not None and got.get("updated_at_ms") != want.get("updated_at_ms"):
            changed_during_backup.append(wf_id)
        else:
            mismatches.append({
                "workflow_id": wf_id,
                "expected": (want.get("sha256") or "")[:16] + "...",
                "actual": (got["sha256"] or "")[:16] + "...",
            })
    return {
        "passed": not mismatches,
        "verified": len(matches),
        "failed": len(mismatches),
        "changed_during_backup": changed_during_backup or None,
        "total_checked": len(ids),
        "total_available": len(expected),
        "mismatches": mismatches or None,
    }


class VerificationService:
    """Service for comprehensive backup verification."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.backup_service = BackupService(db)
        self._container_ready = False
        # source database -> database in the verification container
        self.loaded_databases: Dict[str, str] = {}

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
            logger.info(f"Verification {backup.id}: {progress}% - {message}")
        except Exception as e:
            logger.warning(f"Failed to update verification progress: {e}")

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
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Failed to get network from postgres container: {e}")

        # Fallback: try to find network with n8n in the name
        try:
            cmd = ["docker", "network", "ls", "--format", "{{.Name}}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            for network in result.stdout.strip().split('\n'):
                if 'n8n' in network.lower() and 'network' in network.lower():
                    return network
        except Exception:
            pass

        # Final fallback
        return "n8n_nginx_n8n_network"

    async def spin_up_verify_container(self) -> bool:
        """
        Create and start a temporary PostgreSQL container for verification.
        Always creates a fresh container to ensure clean state.
        """
        logger.info("Starting verification container...")

        try:
            # Always remove existing container first to ensure fresh state
            check_cmd = ["docker", "ps", "-a", "--filter", f"name={VERIFY_CONTAINER_NAME}", "--format", "{{.Names}}"]
            logger.info(f"Checking for existing container: {' '.join(check_cmd)}")
            result = subprocess.run(check_cmd, capture_output=True, text=True)

            if VERIFY_CONTAINER_NAME in result.stdout:
                # Remove existing container
                logger.info("Removing existing verification container for fresh start...")
                subprocess.run(["docker", "rm", "-f", VERIFY_CONTAINER_NAME], capture_output=True)

            # Create new container
            logger.info("Creating new verification container...")
            docker_network = self._get_postgres_network()
            logger.info(f"Using Docker network: {docker_network}")
            create_cmd = [
                "docker", "run", "-d",
                "--name", VERIFY_CONTAINER_NAME,
                "--security-opt", "apparmor=unconfined",
                "-e", f"POSTGRES_USER={VERIFY_DB_USER}",
                "-e", f"POSTGRES_PASSWORD={VERIFY_DB_PASSWORD}",
                "-e", f"POSTGRES_DB={VERIFY_DB_NAME}",
                "-p", f"{VERIFY_DB_PORT}:5432",
                "--network", docker_network,
                VERIFY_CONTAINER_IMAGE,
            ]
            logger.info(f"Running: {' '.join(create_cmd)}")
            create_result = subprocess.run(create_cmd, capture_output=True, text=True)
            logger.info(f"Create result - stdout: {create_result.stdout}, stderr: {create_result.stderr}, returncode: {create_result.returncode}")
            if create_result.returncode != 0:
                logger.error(f"Failed to create container: {create_result.stderr}")
                return False

            # Verify container is actually running
            await asyncio.sleep(2)  # Give container a moment to start
            check_running = subprocess.run(
                ["docker", "ps", "--filter", f"name={VERIFY_CONTAINER_NAME}", "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            if VERIFY_CONTAINER_NAME not in check_running.stdout:
                # Container exited - check logs
                logs_result = subprocess.run(
                    ["docker", "logs", "--tail", "20", VERIFY_CONTAINER_NAME],
                    capture_output=True, text=True
                )
                logger.error(f"Container exited immediately. Logs: {logs_result.stdout} {logs_result.stderr}")
                return False

            # Wait for PostgreSQL to be ready
            logger.info("Waiting for PostgreSQL to be ready...")
            await self._wait_for_postgres_ready()
            self._container_ready = True
            logger.info("Verification container is ready")
            return True

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
            logger.error(f"Failed to start verification container (CalledProcessError): {stderr}")
            return False
        except Exception as e:
            import traceback
            logger.error(f"Error starting verification container: {e}\n{traceback.format_exc()}")
            return False

    async def _wait_for_postgres_ready(self, timeout: int = 90) -> None:
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
            # Stop container (with timeout)
            stop_cmd = ["docker", "stop", "-t", "10", VERIFY_CONTAINER_NAME]
            stop_result = await asyncio.to_thread(
                subprocess.run, stop_cmd, capture_output=True, text=True
            )
            if stop_result.returncode != 0:
                logger.warning(f"Failed to stop verification container: {stop_result.stderr}")

            # Remove container (force to ensure cleanup)
            rm_cmd = ["docker", "rm", "-f", VERIFY_CONTAINER_NAME]
            rm_result = await asyncio.to_thread(
                subprocess.run, rm_cmd, capture_output=True, text=True
            )
            if rm_result.returncode != 0:
                logger.warning(f"Failed to remove verification container: {rm_result.stderr}")
                # If the container doesn't exist, that's fine
                if "No such container" not in rm_result.stderr:
                    return False

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
        self.loaded_databases = {}

        try:
            # Extract (decrypting if needed) to a private temp directory
            with tempfile.TemporaryDirectory(prefix="n8n_verify_") as temp_dir:
                await asyncio.to_thread(_extract_tar_sync, backup.filepath, temp_dir)

                # Read metadata
                metadata_path = os.path.join(temp_dir, "metadata.json")
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                db_dir = os.path.join(temp_dir, "databases")
                dumps = sorted(
                    f[:-len(".dump")] for f in (os.listdir(db_dir) if os.path.isdir(db_dir) else [])
                    if f.endswith(".dump")
                )
                expected = [d for d in (backup.database_name or "").split(",") if d]
                missing = [d for d in expected if d not in dumps]
                if missing:
                    return False, {"error": f"database dump(s) missing from backup: {', '.join(missing)}"}
                if not dumps:
                    return False, {"error": "no database dumps found in backup"}

                # Every dump is restored into its own fresh database and must
                # restore cleanly: any pg_restore error fails the verification.
                for db_name in dumps:
                    ok, error = self._restore_dump_into_verify_db(
                        os.path.join(db_dir, f"{db_name}.dump"), db_name, verify_db_name(db_name)
                    )
                    if not ok:
                        return False, {"error": error, "database": db_name}
                    self.loaded_databases[db_name] = verify_db_name(db_name)

                logger.info(f"Backup {backup_id} loaded into verification container: {self.loaded_databases}")
                return True, metadata

        except Exception as e:
            logger.error(f"Failed to load backup: {e}")
            return False, {"error": str(e)}

    def _restore_dump_into_verify_db(self, dump_path: str, db_name: str, target_db: str) -> Tuple[bool, str]:
        """pg_restore --exit-on-error into a freshly created database. Returns (ok, error)."""
        if not _SAFE_IDENTIFIER.match(target_db):
            return False, f"refusing to use database name {target_db!r}"
        in_container = f"/tmp/verify_{db_name}.dump"
        steps = [
            (["docker", "cp", dump_path, f"{VERIFY_CONTAINER_NAME}:{in_container}"], "copy dump into container"),
            (["docker", "exec", VERIFY_CONTAINER_NAME, "psql", "-v", "ON_ERROR_STOP=1", "-U", VERIFY_DB_USER,
              "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{target_db}"'], "drop verification database"),
            (["docker", "exec", VERIFY_CONTAINER_NAME, "psql", "-v", "ON_ERROR_STOP=1", "-U", VERIFY_DB_USER,
              "-d", "postgres", "-c", f'CREATE DATABASE "{target_db}" TEMPLATE template0'], "create verification database"),
            (["docker", "exec", VERIFY_CONTAINER_NAME, "pg_restore", "-U", VERIFY_DB_USER, "-d", target_db,
              "--no-owner", "--no-acl", "--exit-on-error", in_container], "pg_restore"),
        ]
        for cmd, what in steps:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                logger.error(f"Verification of {db_name}: {what} failed (exit {result.returncode}): {stderr[-2000:]}")
                return False, f"{db_name}: {what} failed (exit {result.returncode}): {stderr[-500:]}"
        subprocess.run(["docker", "exec", VERIFY_CONTAINER_NAME, "rm", "-f", in_container], capture_output=True)
        return True, ""

    # ============================================================================
    # Verification Methods
    # ============================================================================

    async def verify_tables_exist(self, expected_tables: List[str], database: str = VERIFY_DB_NAME) -> Dict[str, Any]:
        """
        Verify that expected tables exist in the restored database.
        """
        try:
            query_cmd = [
                "docker", "exec", VERIFY_CONTAINER_NAME,
                "psql", "-U", VERIFY_DB_USER, "-d", database,
                "-t", "-A", "-c",
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ]
            result = subprocess.run(query_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {"passed": False, "error": f"table query failed: {(result.stderr or '').strip()[-300:]}"}

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

    async def verify_row_counts(self, expected_counts: Dict[str, int], database: str = VERIFY_DB_NAME) -> Dict[str, Any]:
        """
        Verify that table row counts match the manifest.
        """
        mismatches = []
        matches = []

        try:
            for table, expected_count in expected_counts.items():
                if '"' in table:
                    mismatches.append({"table": table, "expected": expected_count, "actual": None,
                                       "error": "Invalid table name"})
                    continue
                query_cmd = [
                    "docker", "exec", VERIFY_CONTAINER_NAME,
                    "psql", "-U", VERIFY_DB_USER, "-d", database,
                    "-t", "-A", "-c",
                    f'SELECT COUNT(*) FROM "{table}"'
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
        expected_checksums: Dict[str, Any],
        sample_size: Optional[int] = None,
        database: str = VERIFY_DB_NAME,
    ) -> Dict[str, Any]:
        """
        Compare the workflow checksums recorded at backup time with the
        restored copy. Both sides are computed by PostgreSQL with
        WORKFLOW_CHECKSUM_SQL, so they agree byte for byte when the data
        survived the dump/restore.

        Args:
            expected_checksums: workflow_id -> {"sha256", "updated_at_ms"}
            sample_size: Accepted for API compatibility and ignored: every
                workflow is compared (one query, cheap).

        A workflow whose updatedAt in the restored copy differs from the one
        recorded was saved while the backup ran (the checksums are taken just
        before the dump); that is reported separately, not as a failure.
        """
        if not expected_checksums:
            return {"passed": True, "message": "No workflow checksums to verify"}

        workflow_ids = list(expected_checksums.keys())

        try:
            query_cmd = [
                "docker", "exec", VERIFY_CONTAINER_NAME,
                "psql", "-v", "ON_ERROR_STOP=1", "-U", VERIFY_DB_USER, "-d", database,
                "-t", "-A", "-F", "\t", "-c", WORKFLOW_CHECKSUM_SQL,
            ]
            result = subprocess.run(query_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {"passed": False, "error": f"workflow query failed: {(result.stderr or '').strip()[-300:]}"}
            restored = parse_workflow_checksum_rows(result.stdout)
        except Exception as e:
            return {"passed": False, "error": str(e)}

        return compare_workflow_checksums(expected_checksums, restored, workflow_ids)

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
            with tempfile.TemporaryDirectory(prefix="n8n_verify_") as temp_dir:
                # Extract backup (decrypting if needed)
                await asyncio.to_thread(_extract_tar_sync, backup.filepath, temp_dir)

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
            current_checksum = await asyncio.to_thread(self._hash_file_sha256, backup.filepath)
            checksum_match = current_checksum == backup.checksum

            # Decrypt, read every member and pg_restore --list every dump
            expected = [d for d in (backup.database_name or "").split(",") if d]
            inspection = await asyncio.to_thread(inspect_backup_archive, backup.filepath, expected)
            errors = list(inspection.get("errors") or [])
            if not checksum_match:
                errors.insert(0, "Checksum mismatch")

            return {
                "passed": checksum_match and inspection.get("passed", False),
                "checksum_match": checksum_match,
                "encrypted": inspection.get("encrypted"),
                "has_database_dumps": bool(inspection.get("dumps")),
                "dumps": inspection.get("dumps"),
                "has_metadata": inspection.get("has_metadata"),
                "has_restore_script": inspection.get("has_restore_script"),
                "total_files": inspection.get("total_files"),
                "file_size": os.path.getsize(backup.filepath),
                "error": "; ".join(errors) if errors else None,
            }

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

        # Dispatch verification started notification
        await dispatch_notification("verification_started", {
            "backup_id": backup_id,
            "backup_filename": backup.filename if backup else "unknown",
        })
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
            # Reset progress and status at the start of verification
            backup.verification_status = "running"
            await self._update_verification_progress(backup, 0, "Starting verification...")

            # Step 1: Archive Integrity (0-10%)
            await self._update_verification_progress(backup, 5, "Verifying archive integrity")
            logger.info("Step 1: Verifying archive integrity...")
            archive_result = await self.verify_backup_archive_integrity(backup_id)
            results["checks"]["archive_integrity"] = archive_result
            if not archive_result.get("passed"):
                results["overall_status"] = "failed"
                results["errors"].append(
                    f"Archive integrity check failed: {archive_result.get('error') or 'see details'}"
                )
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

            production_image = await asyncio.to_thread(_production_postgres_image)
            if production_image and production_image != VERIFY_CONTAINER_IMAGE:
                results["warnings"].append(
                    f"Verification ran on {VERIFY_CONTAINER_IMAGE} but production postgres runs {production_image}"
                )

            # Step 3: Load backup (25-40%)
            await self._update_verification_progress(backup, 30, "Loading backup into container")
            logger.info("Step 3: Loading backup into container...")
            loaded, metadata = await self.load_backup_to_verify_container(backup_id)
            if not loaded:
                results["overall_status"] = "failed"
                results["errors"].append(f"Failed to load backup: {metadata.get('error')}")
                await self._update_verification_progress(backup, 35, "Failed: loading backup")
                return await self._store_verification_results(backup_id, results)

            # Step 4: Verify tables exist in every restored database (40-55%)
            await self._update_verification_progress(backup, 45, "Verifying database tables")
            logger.info("Step 4: Verifying tables exist...")
            loaded_dbs = getattr(self, "loaded_databases", {}) or {"n8n": VERIFY_DB_NAME}
            manifest_by_db = {
                db.get("database"): db for db in (contents.database_schema_manifest or []) if db.get("database")
            }
            for source_db, verify_db in loaded_dbs.items():
                manifest = manifest_by_db.get(source_db)
                expected_tables = [t.get("name") for t in (manifest or {}).get("tables", []) if t.get("name")]
                if not expected_tables:
                    results["warnings"].append(f"No table manifest recorded for {source_db}")
                    continue
                tables_result = await self.verify_tables_exist(expected_tables, database=verify_db)
                key = "tables_exist" if source_db == "n8n" else f"tables_exist_{source_db}"
                results["checks"][key] = tables_result
                if not tables_result.get("passed"):
                    results["overall_status"] = "failed"
                    results["errors"].append(f"Table verification failed for {source_db}")

            # Step 5: Verify row counts (55-70%). The manifest is captured
            # after the dump, so live tables (executions) can legitimately
            # differ: mismatches are warnings.
            await self._update_verification_progress(backup, 60, "Verifying row counts")
            logger.info("Step 5: Verifying row counts...")
            for source_db, verify_db in loaded_dbs.items():
                manifest = manifest_by_db.get(source_db) or {}
                expected_counts = {
                    t["name"]: t["row_count"] for t in manifest.get("tables", [])
                    if t.get("name") and t.get("row_count") is not None
                }
                if not expected_counts:
                    continue
                counts_result = await self.verify_row_counts(expected_counts, database=verify_db)
                key = "row_counts" if source_db == "n8n" else f"row_counts_{source_db}"
                results["checks"][key] = counts_result
                if not counts_result.get("passed"):
                    results["warnings"].append(f"Row count mismatches detected in {source_db}")

            # Step 6: Verify workflow checksums (70-85%)
            await self._update_verification_progress(backup, 75, "Verifying workflow checksums")
            logger.info("Step 6: Verifying workflow checksums...")
            stored = contents.verification_checksums or {}
            workflow_checksums = stored.get("workflow_checksums")
            if "n8n" not in loaded_dbs:
                results["checks"]["workflow_checksums"] = {"passed": True, "message": "Backup has no n8n database"}
            elif workflow_checksums:
                sample = None if verify_all_workflows else workflow_sample_size
                checksums_result = await self.verify_workflow_checksums(
                    workflow_checksums,
                    sample_size=sample,
                    database=loaded_dbs["n8n"],
                )
                results["checks"]["workflow_checksums"] = checksums_result
                if not checksums_result.get("passed"):
                    results["overall_status"] = "failed"
                    results["errors"].append("Workflow checksum verification failed")
                elif checksums_result.get("changed_during_backup"):
                    results["warnings"].append(
                        f"{len(checksums_result['changed_during_backup'])} workflow(s) were saved while the backup ran"
                    )
            elif "workflow_checksums" in stored:
                # Recorded, but the n8n database had no workflows
                results["checks"]["workflow_checksums"] = {"passed": True, "message": "No workflows in backup"}
            else:
                results["checks"]["workflow_checksums"] = {
                    "passed": True,
                    "skipped": True,
                    "message": "Backup predates workflow checksums; not compared",
                }
                results["warnings"].append("Workflow checksums were not recorded for this (older) backup")

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

                # Get actual counts from backup contents metadata (more accurate than verification results)
                contents = await self._get_backup_contents(backup_id)
                workflow_count = contents.workflow_count if contents else 0
                config_count = contents.config_file_count if contents else 0
                credential_count = contents.credential_count if contents else 0

                # Calculate size in MB
                size_mb = round(backup.file_size / (1024 * 1024), 2) if backup.file_size else 0

                if results["overall_status"] == "passed":
                    await dispatch_notification("verification_passed", {
                        "backup_id": backup_id,
                        "backup_filename": backup.filename,
                        "backup_type": backup.backup_type,
                        "backup_created_at": backup.created_at.strftime("%Y-%m-%d %H:%M:%S") if backup.created_at else None,
                        "size_mb": size_mb,
                        "duration_seconds": results.get("duration_seconds"),
                        "completed_at": results.get("completed_at") or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        "workflow_count": workflow_count,
                        "credential_count": credential_count,
                        "config_file_count": config_count,
                    })
                else:
                    await dispatch_notification("verification_failed", {
                        "backup_id": backup_id,
                        "backup_filename": backup.filename,
                        "backup_type": backup.backup_type,
                        "backup_created_at": backup.created_at.strftime("%Y-%m-%d %H:%M:%S") if backup.created_at else None,
                        "size_mb": size_mb,
                        "duration_seconds": results.get("duration_seconds"),
                        "completed_at": results.get("completed_at") or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        "workflow_count": workflow_count,
                        "credential_count": credential_count,
                        "config_file_count": config_count,
                        "errors": results.get("errors", []),
                        "warnings": results.get("warnings", []),
                    })

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


# ============================================================================
# Scheduled verification (VerificationSchedule)
# ============================================================================

VERIFIABLE_BACKUP_TYPES = ("postgres_full", "postgres_n8n", "postgres_mgmt")


def verification_schedule_due(schedule, now: datetime, tz_name: str) -> bool:
    """
    True when the hourly scheduler tick at `now` falls in the configured slot
    (frequency / day_of_week / hour, in the configured timezone) and the
    schedule has not already run in this slot.
    """
    from zoneinfo import ZoneInfo

    if not schedule or not schedule.enabled:
        return False
    local = now.astimezone(ZoneInfo(tz_name))
    if local.hour != (schedule.hour if schedule.hour is not None else 3):
        return False
    frequency = (schedule.frequency or "weekly").lower()
    if frequency == "weekly" and local.weekday() != (schedule.day_of_week or 0):
        return False
    if frequency == "monthly" and local.day != 1:
        return False
    if frequency not in ("daily", "weekly", "monthly"):
        logger.warning(f"Unknown verification schedule frequency {schedule.frequency!r}")
        return False
    last_run = schedule.last_run
    if last_run is not None:
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=UTC)
        if (now - last_run).total_seconds() < 20 * 3600:
            return False
    return True


async def run_scheduled_verification(now: Optional[datetime] = None) -> Optional[List[int]]:
    """
    Scheduler entry point (hourly tick). When the VerificationSchedule slot is
    due, run the comprehensive verification on the verify_latest_count most
    recent successful database backups, one at a time under the operation
    lock. Returns the verified backup IDs, or None when nothing was due.
    """
    from api.database import async_session_maker
    from api.models.backups import VerificationSchedule
    from api.services.operation_lock import exclusive_operation

    now = now or datetime.now(UTC)
    async with async_session_maker() as db:
        schedule = (await db.execute(select(VerificationSchedule).limit(1))).scalar_one_or_none()
        if not verification_schedule_due(schedule, now, settings.timezone):
            return None
        rows = await db.execute(
            select(BackupHistory.id)
            .where(BackupHistory.status == "success")
            .where(BackupHistory.deleted_at.is_(None))
            .where(BackupHistory.backup_type.in_(VERIFIABLE_BACKUP_TYPES))
            .order_by(BackupHistory.created_at.desc())
            .limit(max(int(schedule.verify_latest_count or 1), 1))
        )
        backup_ids = [r[0] for r in rows.all()]
        schedule.last_run = now
        await db.commit()

    logger.info(f"Scheduled verification of backups {backup_ids}")
    verified: List[int] = []
    for backup_id in backup_ids:
        try:
            async with exclusive_operation("verification", wait=True):
                async with async_session_maker() as db:
                    result = await VerificationService(db).verify_backup(backup_id)
            logger.info(f"Scheduled verification of backup {backup_id}: {result.get('overall_status')}")
            verified.append(backup_id)
        except Exception as e:
            logger.error(f"Scheduled verification of backup {backup_id} failed: {e}")
    return verified
