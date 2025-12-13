"""
Settings API routes.

IMPORTANT: Route order matters in FastAPI!
Specific routes (like /debug, /env, /nfs) must come BEFORE
catch-all routes like /{key} to be matched correctly.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any
from datetime import datetime, UTC
import os
import re
import logging

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
    EnvVariableUpdate,
    EnvVariableResponse,
    DebugModeUpdate,
    DebugModeResponse,
    ContainerRestartRequest,
    ContainerRestartResponse,
)
from api.schemas.common import SuccessResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Path to host .env file (mounted in docker-compose)
HOST_ENV_FILE = "/app/host_env/.env"

# Allowed environment variable keys for security
ALLOWED_ENV_KEYS = {
    "N8N_API_KEY": {
        "requires_restart": False,
        "affected_containers": [],
        "description": "n8n REST API key for workflow management",
    },
    "CLOUDFLARE_TUNNEL_TOKEN": {
        "requires_restart": True,
        "affected_containers": ["n8n_cloudflared"],
        "description": "Cloudflare Tunnel authentication token",
    },
    "TAILSCALE_AUTH_KEY": {
        "requires_restart": True,
        "affected_containers": ["n8n_tailscale"],
        "description": "Tailscale authentication key",
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def _read_env_file() -> Dict[str, str]:
    """Read the host .env file and return as dict."""
    env_vars = {}
    if os.path.exists(HOST_ENV_FILE):
        try:
            with open(HOST_ENV_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Parse KEY=VALUE
                    if '=' in line:
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value and value[0] in ('"', "'") and value[-1] == value[0]:
                            value = value[1:-1]
                        env_vars[key] = value
        except Exception as e:
            logger.error(f"Error reading .env file: {e}")
    return env_vars


def _write_env_file(env_vars: Dict[str, str], key: str, value: str) -> bool:
    """
    Update a specific key in the .env file.
    Preserves comments and formatting.
    """
    if not os.path.exists(HOST_ENV_FILE):
        logger.error(f".env file not found at {HOST_ENV_FILE}")
        return False

    try:
        # Read current file content
        with open(HOST_ENV_FILE, 'r') as f:
            lines = f.readlines()

        # Update or add the key
        key_found = False
        new_lines = []
        pattern = re.compile(rf'^{re.escape(key)}\s*=')

        for line in lines:
            if pattern.match(line.strip()):
                # Replace this line with new value
                new_lines.append(f"{key}={value}\n")
                key_found = True
            else:
                new_lines.append(line)

        # If key wasn't found, add it at the end
        if not key_found:
            # Add a newline if file doesn't end with one
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append(f"{key}={value}\n")

        # Write back
        with open(HOST_ENV_FILE, 'w') as f:
            f.writelines(new_lines)

        logger.info(f"Updated environment variable: {key}")
        return True
    except Exception as e:
        logger.error(f"Error writing to .env file: {e}")
        return False


def _mask_value(value: str) -> str:
    """Mask sensitive value for display, showing only first/last few chars."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


# =============================================================================
# Root and Categories Routes (no path parameters)
# =============================================================================

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


# =============================================================================
# Debug Mode Management (MUST come before /{key} catch-all)
# =============================================================================

@router.get("/debug", response_model=DebugModeResponse)
async def get_debug_mode(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current debug mode status."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == "debug_mode")
    )
    setting = result.scalar_one_or_none()

    enabled = setting.value if setting else False
    log_level = "DEBUG" if enabled else "INFO"

    return DebugModeResponse(enabled=enabled, log_level=log_level)


@router.put("/debug", response_model=DebugModeResponse)
async def update_debug_mode(
    update: DebugModeUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable debug mode."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == "debug_mode")
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = update.enabled
        setting.updated_at = datetime.now(UTC)
        setting.updated_by = user.id
    else:
        # Create the setting if it doesn't exist
        setting = SettingsModel(
            key="debug_mode",
            value=update.enabled,
            category="system",
            description="Enable verbose logging and debug information",
            is_secret=False,
            updated_by=user.id,
        )
        db.add(setting)

    await db.commit()

    # Update the logging level in the current process
    import logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if update.enabled else logging.INFO)

    log_level = "DEBUG" if update.enabled else "INFO"
    logger.info(f"Debug mode {'enabled' if update.enabled else 'disabled'} by user {user.username}")

    return DebugModeResponse(enabled=update.enabled, log_level=log_level)


# =============================================================================
# Environment Variable Management (MUST come before /{key} catch-all)
# =============================================================================

@router.get("/env", response_model=List[EnvVariableResponse])
async def list_env_variables(
    _=Depends(get_current_user),
):
    """List all manageable environment variables."""
    env_vars = _read_env_file()
    results = []

    for key, config in ALLOWED_ENV_KEYS.items():
        # First check runtime environment variable (from docker-compose)
        value = os.environ.get(key, "")
        # If not in runtime env, check the .env file
        if not value:
            value = env_vars.get(key, "")

        results.append(EnvVariableResponse(
            key=key,
            is_set=bool(value),
            masked_value=_mask_value(value) if value else None,
            requires_restart=config["requires_restart"],
            affected_containers=config["affected_containers"],
        ))

    return results


@router.get("/env/{key}", response_model=EnvVariableResponse)
async def get_env_variable(
    key: str,
    _=Depends(get_current_user),
):
    """Get an environment variable status (value is masked)."""
    if key not in ALLOWED_ENV_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access to '{key}' is not allowed",
        )

    # First check runtime environment variable (from docker-compose)
    value = os.environ.get(key, "")

    # If not in runtime env, check the .env file
    if not value:
        env_vars = _read_env_file()
        value = env_vars.get(key, "")

    config = ALLOWED_ENV_KEYS[key]

    return EnvVariableResponse(
        key=key,
        is_set=bool(value),
        masked_value=_mask_value(value) if value else None,
        requires_restart=config["requires_restart"],
        affected_containers=config["affected_containers"],
    )


@router.put("/env/{key}", response_model=EnvVariableResponse)
async def update_env_variable(
    key: str,
    update: EnvVariableUpdate,
    _=Depends(get_current_user),
):
    """Update an environment variable in the .env file."""
    if key not in ALLOWED_ENV_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access to '{key}' is not allowed",
        )

    if update.key != key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key in URL must match key in body",
        )

    env_vars = _read_env_file()
    success = _write_env_file(env_vars, key, update.value)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update .env file",
        )

    config = ALLOWED_ENV_KEYS[key]
    return EnvVariableResponse(
        key=key,
        is_set=True,
        masked_value=_mask_value(update.value),
        requires_restart=config["requires_restart"],
        affected_containers=config["affected_containers"],
    )


# =============================================================================
# NFS Configuration (MUST come before /{key} catch-all)
# =============================================================================

@router.get("/nfs/status", response_model=NFSStatusResponse)
async def get_nfs_status(
    _=Depends(get_current_user),
):
    """Get NFS mount status."""
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


# =============================================================================
# System Configuration (MUST come before /{key} catch-all)
# =============================================================================

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


# =============================================================================
# Container Restart (MUST come before /{key} catch-all)
# =============================================================================

@router.post("/container/restart", response_model=ContainerRestartResponse)
async def restart_container(
    request: ContainerRestartRequest,
    _=Depends(get_current_user),
):
    """Restart a specific Docker container."""
    import docker

    # Only allow restarting specific containers for security
    allowed_containers = {
        "n8n_cloudflared": "Cloudflare Tunnel",
        "n8n_tailscale": "Tailscale VPN",
        "n8n": "n8n",
        "n8n_nginx": "Nginx",
    }

    if request.container_name not in allowed_containers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Restarting '{request.container_name}' is not allowed",
        )

    try:
        client = docker.from_env()
        container = client.containers.get(request.container_name)
        container.restart(timeout=30)

        logger.info(f"Restarted container '{request.container_name}'" +
                    (f" - Reason: {request.reason}" if request.reason else ""))

        return ContainerRestartResponse(
            success=True,
            message=f"Container '{allowed_containers[request.container_name]}' restarted successfully",
            container_name=request.container_name,
        )
    except docker.errors.NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container '{request.container_name}' not found",
        )
    except docker.errors.APIError as e:
        logger.error(f"Docker API error restarting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart container: {str(e)}",
        )


# =============================================================================
# Generic Settings CRUD (MUST be LAST - catch-all routes)
# =============================================================================

@router.get("/{key}", response_model=SettingValue)
async def get_setting(
    key: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific setting by key."""
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
    """Update a setting by key."""
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
