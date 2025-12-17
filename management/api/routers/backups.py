"""
Backups API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import os

from api.database import get_db, get_n8n_db
from api.dependencies import get_current_user
from api.services.backup_service import BackupService
from api.schemas.backups import (
    BackupScheduleCreate,
    BackupScheduleUpdate,
    BackupScheduleResponse,
    RetentionPolicyUpdate,
    RetentionPolicyResponse,
    BackupHistoryResponse,
    BackupHistoryExtendedResponse,
    BackupRunRequest,
    BackupRunResponse,
    VerificationScheduleUpdate,
    VerificationScheduleResponse,
    VerificationRunResponse,
    BackupStatsResponse,
    BackupContentsResponse,
    BackupProtectRequest,
    BackupPruningSettingsUpdate,
    BackupPruningSettingsResponse,
)
from api.schemas.common import SuccessResponse

router = APIRouter()


# Schedules

@router.get("/schedules", response_model=List[BackupScheduleResponse])
async def list_schedules(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all backup schedules."""
    service = BackupService(db)
    schedules = await service.get_schedules()
    return [BackupScheduleResponse.model_validate(s) for s in schedules]


@router.post("/schedules", response_model=BackupScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    data: BackupScheduleCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a backup schedule."""
    service = BackupService(db)

    kwargs = data.model_dump()
    kwargs["backup_type"] = kwargs["backup_type"].value
    kwargs["frequency"] = kwargs["frequency"].value
    kwargs["compression"] = kwargs["compression"].value

    created = await service.create_schedule(**kwargs)
    return BackupScheduleResponse.model_validate(created)


@router.get("/schedules/{schedule_id}", response_model=BackupScheduleResponse)
async def get_schedule(
    schedule_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a backup schedule."""
    service = BackupService(db)
    schedule = await service.get_schedule(schedule_id)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    return BackupScheduleResponse.model_validate(schedule)


@router.put("/schedules/{schedule_id}", response_model=BackupScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: BackupScheduleUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a backup schedule."""
    service = BackupService(db)

    updates = data.model_dump(exclude_unset=True)
    for key in ["frequency", "compression"]:
        if key in updates and hasattr(updates[key], "value"):
            updates[key] = updates[key].value

    updated = await service.update_schedule(schedule_id, **updates)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    return BackupScheduleResponse.model_validate(updated)


@router.delete("/schedules/{schedule_id}", response_model=SuccessResponse)
async def delete_schedule(
    schedule_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a backup schedule."""
    service = BackupService(db)
    deleted = await service.delete_schedule(schedule_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    return SuccessResponse(message="Schedule deleted")


# Manual backup

@router.post("/run", response_model=BackupRunResponse)
async def run_backup(
    data: BackupRunRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual backup."""
    service = BackupService(db)

    try:
        history = await service.run_backup(
            backup_type=data.backup_type.value,
            compression=data.compression.value,
        )

        return BackupRunResponse(
            backup_id=history.id,
            status=history.status,
            message=f"Backup {history.status}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# History

@router.get("/history", response_model=List[BackupHistoryResponse])
async def list_history(
    backup_type: str = None,
    backup_status: str = None,
    limit: int = 50,
    offset: int = 0,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get backup history."""
    service = BackupService(db)
    history = await service.get_history(
        limit=limit,
        offset=offset,
        backup_type=backup_type,
        status=backup_status,
    )
    return [BackupHistoryResponse.model_validate(h) for h in history]


@router.get("/history/{backup_id}", response_model=BackupHistoryResponse)
async def get_backup_history(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get backup details."""
    service = BackupService(db)
    backup = await service.get_backup(backup_id)

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found",
        )

    return BackupHistoryResponse.model_validate(backup)


@router.get("/download/{backup_id}")
async def download_backup(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a backup file."""
    service = BackupService(db)
    backup = await service.get_backup(backup_id)

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found",
        )

    if not os.path.exists(backup.filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup file not found on disk",
        )

    return FileResponse(
        path=backup.filepath,
        filename=backup.filename,
        media_type="application/octet-stream",
    )


@router.delete("/{backup_id}", response_model=SuccessResponse)
async def delete_backup(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a backup."""
    service = BackupService(db)
    deleted = await service.delete_backup(backup_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found",
        )

    return SuccessResponse(message="Backup deleted")


# Retention Policies

@router.get("/retention", response_model=List[RetentionPolicyResponse])
async def list_retention_policies(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all retention policies."""
    service = BackupService(db)
    policies = await service.get_retention_policies()
    return [RetentionPolicyResponse.model_validate(p) for p in policies]


@router.put("/retention/{backup_type}", response_model=RetentionPolicyResponse)
async def update_retention_policy(
    backup_type: str,
    data: RetentionPolicyUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update retention policy for a backup type."""
    service = BackupService(db)
    policy = await service.update_retention_policy(
        backup_type=backup_type,
        **data.model_dump(),
    )
    return RetentionPolicyResponse.model_validate(policy)


# Verification

@router.get("/verification/schedule", response_model=VerificationScheduleResponse)
async def get_verification_schedule(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get verification schedule."""
    service = BackupService(db)
    schedule = await service.get_verification_schedule()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification schedule not configured",
        )

    return VerificationScheduleResponse.model_validate(schedule)


@router.put("/verification/schedule", response_model=VerificationScheduleResponse)
async def update_verification_schedule(
    data: VerificationScheduleUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update verification schedule."""
    service = BackupService(db)
    schedule = await service.update_verification_schedule(**data.model_dump())
    return VerificationScheduleResponse.model_validate(schedule)


@router.post("/verification/run/{backup_id}", response_model=VerificationRunResponse)
async def run_verification(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually verify a backup."""
    service = BackupService(db)
    result = await service.verify_backup(backup_id)
    return VerificationRunResponse(
        backup_id=backup_id,
        status=result["status"],
        details=result,
    )


# Statistics

@router.get("/stats", response_model=BackupStatsResponse)
async def get_backup_stats(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get backup statistics."""
    service = BackupService(db)
    stats = await service.get_stats()
    return BackupStatsResponse(**stats)


# ============================================================================
# Phase 1: Backup Contents & Browsing
# ============================================================================

@router.get("/contents/{backup_id}", response_model=BackupContentsResponse)
async def get_backup_contents(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get backup contents metadata for browsing without loading the backup."""
    service = BackupService(db)
    contents = await service.get_backup_contents(backup_id)

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup contents not found. This backup may not have metadata.",
        )

    return BackupContentsResponse.model_validate(contents)


@router.get("/contents/{backup_id}/workflows")
async def get_backup_workflows(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of workflows in a backup."""
    service = BackupService(db)
    workflows = await service.get_workflow_list_from_backup(backup_id)
    return {"backup_id": backup_id, "workflows": workflows}


@router.get("/contents/{backup_id}/config-files")
async def get_backup_config_files(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of config files in a backup."""
    service = BackupService(db)
    config_files = await service.get_config_files_from_backup(backup_id)
    return {"backup_id": backup_id, "config_files": config_files}


# ============================================================================
# Enhanced Backup with Metadata
# ============================================================================

@router.post("/run-full", response_model=BackupRunResponse)
async def run_full_backup(
    data: BackupRunRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    n8n_db: AsyncSession = Depends(get_n8n_db),
):
    """
    Trigger a full backup with metadata capture.
    This creates a complete archive with workflow manifest, config files,
    database schemas, and an embedded restore.sh script.
    """
    service = BackupService(db)

    try:
        history = await service.run_backup_with_metadata(
            backup_type=data.backup_type.value,
            compression=data.compression.value,
            n8n_db=n8n_db,
        )

        return BackupRunResponse(
            backup_id=history.id,
            status=history.status,
            message=f"Full backup {history.status} - {history.filename}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# Backup Protection (Phase 7)
# ============================================================================

@router.post("/{backup_id}/protect", response_model=BackupHistoryExtendedResponse)
async def protect_backup(
    backup_id: int,
    data: BackupProtectRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Protect or unprotect a backup from automatic deletion."""
    service = BackupService(db)
    backup = await service.protect_backup(
        backup_id=backup_id,
        protected=data.protected,
        reason=data.reason,
    )

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found",
        )

    return BackupHistoryExtendedResponse.model_validate(backup)


@router.get("/protected", response_model=List[BackupHistoryExtendedResponse])
async def list_protected_backups(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all protected backups."""
    service = BackupService(db)
    backups = await service.get_protected_backups()
    return [BackupHistoryExtendedResponse.model_validate(b) for b in backups]


# ============================================================================
# Pruning Settings (Phase 7)
# ============================================================================

@router.get("/pruning/settings", response_model=BackupPruningSettingsResponse)
async def get_pruning_settings(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get backup pruning settings."""
    service = BackupService(db)
    settings = await service.get_pruning_settings()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pruning settings not configured",
        )

    return BackupPruningSettingsResponse.model_validate(settings)


@router.put("/pruning/settings", response_model=BackupPruningSettingsResponse)
async def update_pruning_settings(
    data: BackupPruningSettingsUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update backup pruning settings."""
    service = BackupService(db)
    settings = await service.update_pruning_settings(**data.model_dump(exclude_unset=True))
    return BackupPruningSettingsResponse.model_validate(settings)


# ============================================================================
# Phase 3: Selective Workflow Restore
# ============================================================================

from api.services.restore_service import RestoreService
from pydantic import BaseModel, Field
from typing import Optional as Opt


class WorkflowRestoreRequest(BaseModel):
    """Request to restore a workflow from backup."""
    workflow_id: str
    rename_format: str = Field(default="{name}_backup_{date}")


class WorkflowRestoreResponse(BaseModel):
    """Response from workflow restore."""
    status: str
    original_name: Opt[str] = None
    new_name: Opt[str] = None
    new_workflow_id: Opt[str] = None
    message: Opt[str] = None
    error: Opt[str] = None


@router.post("/{backup_id}/restore/workflow", response_model=WorkflowRestoreResponse)
async def restore_workflow_from_backup(
    backup_id: int,
    data: WorkflowRestoreRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    n8n_db: AsyncSession = Depends(get_n8n_db),
):
    """
    Restore a specific workflow from a backup to the running n8n instance.

    This will:
    1. Spin up a temporary PostgreSQL container
    2. Load the backup
    3. Extract the specified workflow
    4. Push it to n8n via API with a new name
    """
    service = RestoreService(db, n8n_db)

    try:
        result = await service.restore_workflow_to_n8n(
            backup_id=backup_id,
            workflow_id=data.workflow_id,
            rename_format=data.rename_format,
        )
        return WorkflowRestoreResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{backup_id}/restore/workflows")
async def list_restorable_workflows(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List workflows available for restore from a backup.

    This spins up a restore container if needed and queries the backup's workflow list.
    """
    service = RestoreService(db)

    try:
        # Spin up container and load backup
        if not await service.spin_up_restore_container():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start restore container",
            )

        if not await service.load_backup_to_restore_container(backup_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load backup",
            )

        # List workflows
        workflows = await service.list_workflows_in_restore_db()
        return {"backup_id": backup_id, "workflows": workflows}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{backup_id}/workflows/{workflow_id}/download")
async def download_workflow_from_backup(
    backup_id: int,
    workflow_id: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a workflow from a backup as a JSON file.

    This extracts the workflow from the backup and returns it as JSON
    suitable for importing into n8n.
    """
    service = RestoreService(db)

    try:
        workflow = await service.download_workflow_as_json(backup_id, workflow_id)

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found in backup",
            )

        # Return as JSON with download headers
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=workflow,
            headers={
                "Content-Disposition": f'attachment; filename="{workflow["name"]}.json"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/restore/cleanup")
async def cleanup_restore_container(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually clean up the restore container.

    Call this after you're done with restore operations to free resources.
    """
    service = RestoreService(db)

    try:
        success = await service.teardown_restore_container()
        return {"success": success, "message": "Restore container cleaned up" if success else "No container to clean up"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/restore/status")
async def get_restore_container_status(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the restore container is currently running."""
    service = RestoreService(db)

    try:
        is_running = await service.is_container_running()
        return {"running": is_running}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# Phase 4: Full System Restore
# ============================================================================

class FullRestoreRequest(BaseModel):
    """Request for full system restore."""
    restore_databases: bool = True
    restore_configs: bool = True
    restore_ssl: bool = True
    database_names: Opt[List[str]] = None
    config_files: Opt[List[str]] = None
    create_backups: bool = True


@router.get("/{backup_id}/restore/preview")
async def get_restore_preview(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a preview of what would be restored from a backup.

    Returns lists of databases, config files, SSL certificates, and workflow count.
    """
    service = RestoreService(db)

    try:
        preview = await service.get_restore_preview(backup_id)
        if preview.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=preview.get("error", "Failed to get preview"),
            )
        return preview
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{backup_id}/restore/config-files")
async def list_config_files_in_backup(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all config files available in a backup."""
    service = RestoreService(db)

    try:
        config_files = await service.list_config_files_in_backup(backup_id)
        return {"backup_id": backup_id, "config_files": config_files}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class ConfigRestoreRequest(BaseModel):
    """Request to restore a specific config file."""
    config_path: str
    target_path: Opt[str] = None
    create_backup: bool = True


@router.post("/{backup_id}/restore/config")
async def restore_config_file(
    backup_id: int,
    data: ConfigRestoreRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore a specific config file from backup.

    WARNING: This will overwrite the existing file!
    """
    service = RestoreService(db)

    try:
        result = await service.restore_config_file(
            backup_id=backup_id,
            config_path=data.config_path,
            target_path=data.target_path,
            create_backup=data.create_backup,
        )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Restore failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class DatabaseRestoreRequest(BaseModel):
    """Request to restore a database."""
    database_name: str
    target_database: Opt[str] = None


@router.post("/{backup_id}/restore/database")
async def restore_database(
    backup_id: int,
    data: DatabaseRestoreRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore a database from backup.

    WARNING: This will OVERWRITE the target database!
    """
    service = RestoreService(db)

    try:
        result = await service.restore_database(
            backup_id=backup_id,
            database_name=data.database_name,
            target_database=data.target_database,
        )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Restore failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{backup_id}/restore/full")
async def full_system_restore(
    backup_id: int,
    data: FullRestoreRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform a full system restore from a backup.

    This can restore:
    - Databases (n8n, n8n_management)
    - Config files (.env, docker-compose.yaml, nginx.conf)
    - SSL certificates

    WARNING: This will OVERWRITE existing data! Use with caution.

    By default, existing files are backed up before overwriting (create_backups=true).
    """
    service = RestoreService(db)

    try:
        result = await service.full_system_restore(
            backup_id=backup_id,
            restore_databases=data.restore_databases,
            restore_configs=data.restore_configs,
            restore_ssl=data.restore_ssl,
            database_names=data.database_names,
            config_files=data.config_files,
            create_backups=data.create_backups,
        )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Restore failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# Phase 5: Comprehensive Backup Verification
# ============================================================================

from api.services.verification_service import VerificationService


class VerifyBackupRequest(BaseModel):
    """Request for backup verification."""
    verify_all_workflows: bool = False
    workflow_sample_size: int = 10


class VerifyBackupResponse(BaseModel):
    """Response from backup verification."""
    backup_id: int
    status: str
    overall_status: Opt[str] = None
    checks: Opt[Dict] = None
    errors: Opt[List[str]] = None
    warnings: Opt[List[str]] = None
    duration_seconds: Opt[float] = None


@router.post("/{backup_id}/verify", response_model=VerifyBackupResponse)
async def verify_backup_comprehensive(
    backup_id: int,
    data: VerifyBackupRequest = None,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform comprehensive verification of a backup.

    This will:
    1. Verify archive integrity (checksum, structure)
    2. Spin up a temporary PostgreSQL container
    3. Load the backup into the container
    4. Verify all expected tables exist
    5. Verify row counts match the stored manifest
    6. Verify workflow checksums (sampled or all)
    7. Verify config file checksums

    This operation takes 1-5 minutes depending on backup size.
    """
    if data is None:
        data = VerifyBackupRequest()

    service = VerificationService(db)

    try:
        result = await service.verify_backup(
            backup_id=backup_id,
            verify_all_workflows=data.verify_all_workflows,
            workflow_sample_size=data.workflow_sample_size,
        )

        return VerifyBackupResponse(
            backup_id=backup_id,
            status=result.get("overall_status", "unknown"),
            overall_status=result.get("overall_status"),
            checks=result.get("checks"),
            errors=result.get("errors"),
            warnings=result.get("warnings"),
            duration_seconds=result.get("duration_seconds"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{backup_id}/verify/quick")
async def verify_backup_quick(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform quick verification of a backup.

    Quick verification only checks:
    - File exists on disk
    - Checksum matches stored value
    - Archive is valid and extractable

    This does NOT spin up a container or verify data integrity.
    Much faster but less comprehensive.
    """
    service = VerificationService(db)

    try:
        result = await service.quick_verify(backup_id)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{backup_id}/verification/status")
async def get_verification_status(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the verification status of a backup.

    Returns the last verification status and details if available.
    """
    from api.services.backup_service import BackupService

    backup_service = BackupService(db)
    backup = await backup_service.get_backup(backup_id)

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found",
        )

    return {
        "backup_id": backup_id,
        "verification_status": backup.verification_status,
        "verification_date": backup.verification_date.isoformat() if backup.verification_date else None,
        "verification_details": backup.verification_details,
    }


@router.post("/verification/cleanup")
async def cleanup_verify_container(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually clean up the verification container.

    Call this if verification was interrupted and the container is still running.
    """
    service = VerificationService(db)

    try:
        success = await service.teardown_verify_container()
        return {
            "success": success,
            "message": "Verification container cleaned up" if success else "No container to clean up"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/verification/container/status")
async def get_verify_container_status(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the verification container is currently running."""
    service = VerificationService(db)

    try:
        is_running = await service.is_container_running()
        return {"running": is_running}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# Phase 7: Pruning & Retention
# ============================================================================

from api.services.pruning_service import PruningService


@router.get("/storage/usage")
async def get_storage_usage(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current storage usage for backup directories.
    Returns information about local and NFS storage, total backup size, etc.
    """
    service = PruningService(db)
    return service.get_storage_usage()


@router.get("/pruning/candidates")
async def get_pruning_candidates(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a preview of backups that would be affected by current pruning settings.
    Does not actually delete anything.
    """
    service = PruningService(db)
    settings = await service.get_settings()

    if not settings:
        return {"message": "No pruning settings configured", "candidates": []}

    result = {
        "settings": {
            "time_based_enabled": settings.time_based_enabled,
            "max_age_days": settings.max_age_days,
            "space_based_enabled": settings.space_based_enabled,
            "min_free_space_percent": settings.min_free_space_percent,
            "size_based_enabled": settings.size_based_enabled,
            "max_total_size_gb": settings.max_total_size_gb,
        },
        "candidates": {
            "time_based": [],
            "oldest_unprotected": [],
        },
        "storage": service.get_storage_usage(),
    }

    if settings.time_based_enabled:
        time_candidates = await service.get_time_based_candidates(settings.max_age_days)
        result["candidates"]["time_based"] = [
            {"id": b.id, "filename": b.filename, "created_at": b.created_at.isoformat()}
            for b in time_candidates[:10]
        ]

    oldest = await service.get_oldest_unprotected_backups(limit=5)
    result["candidates"]["oldest_unprotected"] = [
        {"id": b.id, "filename": b.filename, "created_at": b.created_at.isoformat(), "size_bytes": b.file_size}
        for b in oldest
    ]

    return result


@router.get("/pruning/pending")
async def get_pending_deletions(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of backups pending deletion."""
    service = PruningService(db)
    pending = await service.get_pending_deletions()

    return {
        "count": len(pending),
        "backups": [
            {
                "id": b.id,
                "filename": b.filename,
                "scheduled_deletion_at": b.scheduled_deletion_at.isoformat() if b.scheduled_deletion_at else None,
                "deletion_reason": b.deletion_reason,
            }
            for b in pending
        ]
    }


@router.post("/{backup_id}/cancel-deletion")
async def cancel_backup_deletion(
    backup_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a pending deletion for a backup.
    Can only cancel if the backup is in 'pending' deletion status.
    """
    service = PruningService(db)
    backup = await service.cancel_deletion(backup_id)

    if backup:
        return {"success": True, "message": f"Cancelled deletion for backup {backup_id}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup not found or not pending deletion"
        )


@router.post("/pruning/run")
async def run_pruning_manually(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger all pruning checks.
    This will:
    1. Execute any pending deletions that are past their scheduled time
    2. Check space-based pruning conditions
    3. Check size-based pruning conditions
    4. Check time-based pruning conditions
    """
    service = PruningService(db)

    try:
        results = await service.run_all_pruning_checks()
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/pruning/execute-pending")
async def execute_pending_deletions(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute all pending deletions that have passed their scheduled time.
    """
    service = PruningService(db)

    try:
        results = await service.execute_pending_deletions()
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
