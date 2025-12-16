"""
Backups API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import os

from api.database import get_db
from api.dependencies import get_current_user
from api.services.backup_service import BackupService
from api.schemas.backups import (
    BackupScheduleCreate,
    BackupScheduleUpdate,
    BackupScheduleResponse,
    RetentionPolicyUpdate,
    RetentionPolicyResponse,
    BackupHistoryResponse,
    BackupRunRequest,
    BackupRunResponse,
    VerificationScheduleUpdate,
    VerificationScheduleResponse,
    VerificationRunResponse,
    BackupStatsResponse,
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
