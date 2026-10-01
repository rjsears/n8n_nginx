"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/backup_runner.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Entry point for creating a backup (scheduled or manual) under the global
operation lock.

Sequence:
  1. Acquire the operation lock as "backup" and run the archive backup
     (including the free-space pre-check) with auto-verification deferred.
  2. Release the lock, then run auto-verification if requested. Verification
     may take the lock itself; the lock is not reentrant, so it must not run
     while the backup still holds it.
  3. Run GFS retention + the automatic pruning checks (skipped if another
     operation is busy; the hourly maintenance job catches up). Automatic runs
     never delete for space/size reasons and always keep the newest
     max(retention_min_count, 1) backups of each type; see
     PruningService.run_all_pruning_checks().

BackupService.run_backup_with_metadata() itself does NOT take the lock, so code
that already holds it (e.g. a pre-restore safety backup) can call it directly.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.backups import BackupHistory
from api.services.backup_service import BackupService
from api.services.operation_lock import exclusive_operation
from api.services.pruning_service import run_retention_maintenance

logger = logging.getLogger(__name__)


async def run_backup_exclusive(
    db: AsyncSession,
    n8n_db: AsyncSession,
    backup_type: str,
    compression: str = "gzip",
    schedule_id: Optional[int] = None,
    skip_auto_verify: bool = False,
    wait: bool = True,
) -> BackupHistory:
    """
    Create a backup while holding the operation lock.

    Args:
        wait: False raises api.services.operation_lock.OperationBusyError
            immediately if a restore/verification/pruning/backup is running
            (used by the API so the caller gets HTTP 409); True waits (used by
            scheduled backups).

    Raises whatever run_backup_with_metadata raises on failure (the failed
    history record and failure notification are handled there).
    """
    service = BackupService(db)

    async with exclusive_operation("backup", wait=wait):
        history = await service.run_backup_with_metadata(
            backup_type=backup_type,
            schedule_id=schedule_id,
            compression=compression,
            n8n_db=n8n_db,
            skip_auto_verify=True,  # run below, outside the lock
        )

    if not skip_auto_verify:
        await service._run_auto_verification(history)

    if history.status == "success":
        await run_retention_maintenance(source=f"post-backup {history.id}")

    return history
