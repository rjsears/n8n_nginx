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
    IPRange,
    AccessControlConfig,
    AccessControlResponse,
    AddIPRangeRequest,
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


# Access Control Configuration
# Default IP ranges for common networks
DEFAULT_IP_RANGES = [
    {"cidr": "127.0.0.1/32", "description": "Localhost", "access_level": "internal"},
    {"cidr": "10.0.0.0/8", "description": "Private Class A", "access_level": "internal"},
    {"cidr": "172.16.0.0/12", "description": "Private Class B", "access_level": "internal"},
    {"cidr": "192.168.0.0/16", "description": "Private Class C", "access_level": "internal"},
    {"cidr": "100.64.0.0/10", "description": "Tailscale CGNAT", "access_level": "internal"},
]

# Path to nginx config (mounted from host)
NGINX_CONFIG_PATH = "/app/host_config/nginx.conf"
HOST_ENV_PATH = "/app/host_env/.env"


def parse_nginx_geo_block(config_content: str) -> List[Dict[str, Any]]:
    """Parse the geo block from nginx.conf to extract IP ranges."""
    import re

    ip_ranges = []

    # Find the geo block
    geo_match = re.search(r'geo\s+\$access_level\s*\{([^}]+)\}', config_content, re.DOTALL)
    if not geo_match:
        return ip_ranges

    geo_content = geo_match.group(1)

    # Parse each line in the geo block
    for line in geo_content.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Check for comment at end of line (description)
        comment = ""
        if '#' in line:
            parts = line.split('#', 1)
            line = parts[0].strip()
            comment = parts[1].strip()

        # Skip default directive
        if line.startswith('default'):
            continue

        # Parse CIDR and access level
        parts = line.rstrip(';').split()
        if len(parts) >= 2:
            cidr = parts[0]
            access_level = parts[1].strip('"').strip("'")
            ip_ranges.append({
                "cidr": cidr,
                "description": comment,
                "access_level": access_level,
            })

    return ip_ranges


def generate_nginx_geo_block(ip_ranges: List[Dict[str, Any]]) -> str:
    """Generate nginx geo block from IP ranges."""
    lines = ['geo $access_level {', '    default          "external";']

    for ip_range in ip_ranges:
        cidr = ip_range.get("cidr", "")
        access_level = ip_range.get("access_level", "internal")
        description = ip_range.get("description", "")

        # Format the line with proper alignment
        line = f'    {cidr:<20} "{access_level}";'
        if description:
            line += f'  # {description}'
        lines.append(line)

    lines.append('}')
    return '\n'.join(lines)


def update_nginx_config_geo_block(config_content: str, ip_ranges: List[Dict[str, Any]]) -> str:
    """Update the geo block in nginx.conf content."""
    import re

    new_geo_block = generate_nginx_geo_block(ip_ranges)

    # Try to replace existing geo block
    pattern = r'geo\s+\$access_level\s*\{[^}]+\}'
    if re.search(pattern, config_content, re.DOTALL):
        return re.sub(pattern, new_geo_block, config_content, flags=re.DOTALL)

    # If no geo block exists, add it at the beginning of http block
    http_match = re.search(r'(http\s*\{)', config_content)
    if http_match:
        insert_pos = http_match.end()
        return config_content[:insert_pos] + '\n    ' + new_geo_block + '\n' + config_content[insert_pos:]

    # Fallback: add at the beginning
    return new_geo_block + '\n\n' + config_content


@router.get("/access-control", response_model=AccessControlResponse)
async def get_access_control(
    _=Depends(get_current_user),
):
    """Get current access control configuration."""
    import os

    ip_ranges = []
    last_updated = None
    enabled = False

    try:
        if os.path.exists(NGINX_CONFIG_PATH):
            with open(NGINX_CONFIG_PATH, 'r') as f:
                content = f.read()

            # Check if geo block exists
            if 'geo $access_level' in content:
                enabled = True
                ip_ranges = parse_nginx_geo_block(content)

            # Get last modified time
            stat = os.stat(NGINX_CONFIG_PATH)
            last_updated = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read nginx config: {str(e)}",
        )

    return AccessControlResponse(
        enabled=enabled,
        ip_ranges=[IPRange(**r) for r in ip_ranges],
        nginx_config_path=NGINX_CONFIG_PATH,
        last_updated=last_updated,
    )


@router.put("/access-control", response_model=SuccessResponse)
async def update_access_control(
    config: AccessControlConfig,
    _=Depends(get_current_user),
):
    """Update access control configuration (replace all IP ranges)."""
    import os

    try:
        if not os.path.exists(NGINX_CONFIG_PATH):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nginx config file not found",
            )

        with open(NGINX_CONFIG_PATH, 'r') as f:
            content = f.read()

        # Convert IP ranges to dict format
        ip_ranges = [r.model_dump() for r in config.ip_ranges]

        # Update the geo block
        new_content = update_nginx_config_geo_block(content, ip_ranges)

        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(new_content)

        return SuccessResponse(message="Access control configuration updated. Reload nginx to apply changes.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update access control: {str(e)}",
        )


@router.post("/access-control/ip", response_model=SuccessResponse)
async def add_ip_range(
    ip_range: AddIPRangeRequest,
    _=Depends(get_current_user),
):
    """Add a new IP range to access control."""
    import os

    try:
        if not os.path.exists(NGINX_CONFIG_PATH):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nginx config file not found",
            )

        with open(NGINX_CONFIG_PATH, 'r') as f:
            content = f.read()

        # Get existing ranges
        ip_ranges = parse_nginx_geo_block(content)

        # Check for duplicate
        for existing in ip_ranges:
            if existing["cidr"] == ip_range.cidr:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"IP range {ip_range.cidr} already exists",
                )

        # Add new range
        ip_ranges.append({
            "cidr": ip_range.cidr,
            "description": ip_range.description,
            "access_level": ip_range.access_level,
        })

        # Update config
        new_content = update_nginx_config_geo_block(content, ip_ranges)

        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(new_content)

        return SuccessResponse(message=f"IP range {ip_range.cidr} added. Reload nginx to apply changes.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add IP range: {str(e)}",
        )


@router.delete("/access-control/ip/{cidr:path}", response_model=SuccessResponse)
async def delete_ip_range(
    cidr: str,
    _=Depends(get_current_user),
):
    """Delete an IP range from access control."""
    import os

    try:
        if not os.path.exists(NGINX_CONFIG_PATH):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nginx config file not found",
            )

        with open(NGINX_CONFIG_PATH, 'r') as f:
            content = f.read()

        # Get existing ranges
        ip_ranges = parse_nginx_geo_block(content)

        # Find and remove the range
        original_count = len(ip_ranges)
        ip_ranges = [r for r in ip_ranges if r["cidr"] != cidr]

        if len(ip_ranges) == original_count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"IP range {cidr} not found",
            )

        # Update config
        new_content = update_nginx_config_geo_block(content, ip_ranges)

        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(new_content)

        return SuccessResponse(message=f"IP range {cidr} deleted. Reload nginx to apply changes.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete IP range: {str(e)}",
        )


@router.post("/access-control/reload-nginx", response_model=SuccessResponse)
async def reload_nginx(
    _=Depends(get_current_user),
):
    """Reload nginx to apply access control changes."""
    import subprocess
    import shutil

    try:
        # Check if docker is available
        docker_cmd = shutil.which("docker")
        if not docker_cmd:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Docker command not found",
            )

        # Try to reload nginx container
        result = subprocess.run(
            ["docker", "exec", "nginx", "nginx", "-s", "reload"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reload nginx: {error_msg}",
            )

        return SuccessResponse(message="Nginx reloaded successfully")

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nginx reload timed out",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload nginx: {str(e)}",
        )


@router.get("/access-control/defaults", response_model=List[IPRange])
async def get_default_ip_ranges(
    _=Depends(get_current_user),
):
    """Get default IP ranges for common networks."""
    return [IPRange(**r) for r in DEFAULT_IP_RANGES]
