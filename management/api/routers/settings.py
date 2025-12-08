"""
Settings API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any
from datetime import datetime, UTC

from api.database import get_db
from api.dependencies import get_current_user
from api.models.settings import Settings as SettingsModel, SystemConfig
from api.schemas.settings import (
    SettingValue,
    SettingUpdate,
    SettingsByCategoryResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
    NFSConfigUpdate,
    NFSStatusResponse,
)
from api.schemas.common import SuccessResponse

router = APIRouter()


@router.get("/", response_model=List[SettingValue])
async def list_settings(
    category: str = None,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all settings, optionally filtered by category."""
    query = select(SettingsModel).order_by(SettingsModel.category, SettingsModel.key)
    if category:
        query = query.where(SettingsModel.category == category)

    result = await db.execute(query)
    settings = result.scalars().all()

    return [SettingValue.model_validate(s) for s in settings]


@router.get("/categories", response_model=List[str])
async def list_categories(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all setting categories."""
    result = await db.execute(
        select(SettingsModel.category).distinct().order_by(SettingsModel.category)
    )
    return [row[0] for row in result.all()]


@router.get("/{key}", response_model=SettingValue)
async def get_setting(
    key: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific setting."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == key)
    )
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )

    return SettingValue.model_validate(setting)


@router.put("/{key}", response_model=SettingValue)
async def update_setting(
    key: str,
    update: SettingUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a setting."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == key)
    )
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )

    setting.value = update.value
    if update.description is not None:
        setting.description = update.description
    setting.updated_at = datetime.now(UTC)
    setting.updated_by = user.id

    await db.commit()
    await db.refresh(setting)

    return SettingValue.model_validate(setting)


# System Configuration

@router.get("/config/{config_type}", response_model=SystemConfigResponse)
async def get_system_config(
    config_type: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get system configuration by type."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_type == config_type)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration '{config_type}' not found",
        )

    return SystemConfigResponse.model_validate(config)


@router.put("/config/{config_type}", response_model=SystemConfigResponse)
async def update_system_config(
    config_type: str,
    update: SystemConfigUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update system configuration."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_type == config_type)
    )
    config = result.scalar_one_or_none()

    if config:
        config.config = update.config
        config.updated_at = datetime.now(UTC)
    else:
        config = SystemConfig(
            config_type=config_type,
            config=update.config,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    return SystemConfigResponse.model_validate(config)


# NFS Configuration

@router.get("/nfs/status", response_model=NFSStatusResponse)
async def get_nfs_status(
    _=Depends(get_current_user),
):
    """Get NFS mount status."""
    import os
    from api.config import settings

    nfs_server = settings.nfs_server
    nfs_path = settings.nfs_path
    mount_point = settings.nfs_mount_point

    if not nfs_server:
        return NFSStatusResponse(
            status="disabled",
            message="NFS not configured",
        )

    is_mounted = os.path.ismount(mount_point)

    if is_mounted:
        # Test write capability
        try:
            test_file = os.path.join(mount_point, ".health_check")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            status_str = "connected"
            message = "NFS mounted and writable"
        except Exception as e:
            status_str = "degraded"
            message = f"NFS mounted but not writable: {e}"
    else:
        status_str = "disconnected"
        message = "NFS not mounted"

    return NFSStatusResponse(
        status=status_str,
        message=message,
        server=nfs_server,
        path=nfs_path,
        mount_point=mount_point,
        is_mounted=is_mounted,
        last_check=datetime.now(UTC),
    )


@router.put("/nfs/config", response_model=SuccessResponse)
async def update_nfs_config(
    config: NFSConfigUpdate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update NFS configuration."""
    # Store NFS config
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_type == "nfs")
    )
    existing = result.scalar_one_or_none()

    nfs_config = {
        "enabled": config.enabled,
        "server": config.server,
        "path": config.path,
        "mount_point": config.mount_point,
        "mount_options": config.mount_options,
    }

    if existing:
        existing.config = nfs_config
        existing.updated_at = datetime.now(UTC)
    else:
        new_config = SystemConfig(
            config_type="nfs",
            config=nfs_config,
        )
        db.add(new_config)

    await db.commit()

    return SuccessResponse(message="NFS configuration updated. Restart container to apply changes.")
