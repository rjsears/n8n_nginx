"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/settings.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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
    UpdateIPRangeRequest,
    ExternalRoute,
    ExternalRoutesResponse,
    AddExternalRouteRequest,
)
from api.schemas.common import SuccessResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


async def reset_tailscale_container():
    """
    Reset Tailscale container state when auth key changes.
    Uses shell commands to ensure proper cleanup:
    1. docker stop n8n_tailscale
    2. docker volume rm n8n_nginx_tailscale_data
    3. docker compose up -d tailscale
    """
    import subprocess
    import os

    # Get the host project directory (where docker-compose.yaml is)
    host_dir = "/app/host_project"

    try:
        # Step 1: Stop the container
        logger.info("Stopping Tailscale container...")
        stop_result = subprocess.run(
            ['docker', 'stop', 'n8n_tailscale'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if stop_result.returncode != 0:
            # Container might already be stopped, that's OK
            logger.info(f"Stop returned: {stop_result.stderr.strip() or 'container may already be stopped'}")

        # Step 2: Remove the volume (need to remove container first to release it)
        logger.info("Removing Tailscale container to release volume...")
        rm_container = subprocess.run(
            ['docker', 'rm', '-f', 'n8n_tailscale'],
            capture_output=True,
            text=True,
            timeout=30
        )
        logger.info(f"Container removal: {rm_container.stdout.strip() or rm_container.stderr.strip()}")

        # Step 3: Remove the volume
        logger.info("Removing Tailscale data volume...")
        # Try common volume name patterns
        volume_names = ['n8n_nginx_tailscale_data', 'n8n-nginx_tailscale_data', 'tailscale_data']
        volume_removed = False
        for vol_name in volume_names:
            vol_result = subprocess.run(
                ['docker', 'volume', 'rm', vol_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if vol_result.returncode == 0:
                logger.info(f"Removed volume: {vol_name}")
                volume_removed = True
                break
            else:
                logger.debug(f"Volume {vol_name} not found or already removed")

        if not volume_removed:
            logger.warning("Could not find/remove Tailscale volume - may already be removed")

        # Step 4: Recreate and start the container
        logger.info("Starting Tailscale container with new auth key...")

        # Try docker compose V2 first, fall back to docker-compose V1
        up_result = subprocess.run(
            ['docker', 'compose', 'up', '-d', 'tailscale'],
            cwd=host_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        # If V2 failed, try V1 (docker-compose)
        if up_result.returncode != 0 and 'unknown' in up_result.stderr.lower():
            logger.info("Docker Compose V2 not available, trying V1...")
            up_result = subprocess.run(
                ['docker-compose', 'up', '-d', 'tailscale'],
                cwd=host_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

        if up_result.returncode == 0:
            logger.info("Tailscale container started successfully")
            return {"success": True, "message": "Tailscale container restarted with new auth key"}
        else:
            logger.error(f"Failed to start Tailscale: {up_result.stderr}")
            return {"success": False, "message": f"Failed to start container: {up_result.stderr}"}

    except subprocess.TimeoutExpired:
        logger.error("Tailscale reset operation timed out")
        return {"success": False, "message": "Operation timed out"}
    except Exception as e:
        logger.error(f"Error resetting Tailscale container: {e}")
        return {"success": False, "message": str(e)}


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
# Protected IP ranges that cannot be removed (required for system functionality)
PROTECTED_IP_RANGES = ["127.0.0.1/32"]

# Default IP ranges shown as suggestions (user can choose to add these)
DEFAULT_IP_RANGES = [
    {"cidr": "127.0.0.1/32", "description": "Localhost (required)", "access_level": "internal", "protected": True},
    {"cidr": "172.17.0.0/16", "description": "Docker default bridge", "access_level": "internal", "protected": False},
    {"cidr": "100.64.0.0/10", "description": "Tailscale CGNAT", "access_level": "internal", "protected": False},
    {"cidr": "10.0.0.0/8", "description": "RFC1918 Class A (10.x.x.x)", "access_level": "internal", "protected": False},
    {"cidr": "172.16.0.0/12", "description": "RFC1918 Class B (172.16-31.x.x)", "access_level": "internal", "protected": False},
    {"cidr": "192.168.0.0/16", "description": "RFC1918 Class C (192.168.x.x)", "access_level": "internal", "protected": False},
]

# Paths to host files (mounted from host via ./:/app/host_project:rw)
NGINX_CONFIG_PATH = "/app/host_project/nginx.conf"
HOST_ENV_PATH = "/app/host_project/.env"


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
                "protected": cidr in PROTECTED_IP_RANGES,
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

    # Return empty config if nginx config doesn't exist (not mounted or not configured)
    if not os.path.exists(NGINX_CONFIG_PATH):
        return AccessControlResponse(
            enabled=False,
            ip_ranges=[],
            nginx_config_path=NGINX_CONFIG_PATH,
            last_updated=None,
        )

    try:
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
        # Log error but return empty config instead of 500
        import logging
        logging.getLogger(__name__).warning(f"Failed to read nginx config: {e}")
        return AccessControlResponse(
            enabled=False,
            ip_ranges=[],
            nginx_config_path=NGINX_CONFIG_PATH,
            last_updated=None,
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
        # Prevent deletion of protected IP ranges
        if cidr in PROTECTED_IP_RANGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete {cidr} - this IP range is required for system functionality",
            )

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


@router.put("/access-control/ip/{cidr:path}", response_model=SuccessResponse)
async def update_ip_range(
    cidr: str,
    update: UpdateIPRangeRequest,
    _=Depends(get_current_user),
):
    """Update an IP range's description."""
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

        # Find the range to update
        found = False
        for ip_range in ip_ranges:
            if ip_range["cidr"] == cidr:
                ip_range["description"] = update.description
                found = True
                break

        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"IP range {cidr} not found",
            )

        # Update config
        new_content = update_nginx_config_geo_block(content, ip_ranges)

        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(new_content)

        return SuccessResponse(message=f"IP range {cidr} updated.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update IP range: {str(e)}",
        )


@router.post("/access-control/reload-nginx", response_model=SuccessResponse)
async def reload_nginx(
    _=Depends(get_current_user),
):
    """Reload nginx to apply access control changes."""
    import subprocess
    import shutil
    import os

    try:
        # Check if docker is available
        docker_cmd = shutil.which("docker")
        if not docker_cmd:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Docker command not found",
            )

        # Get nginx container name from environment or use default
        nginx_container = os.environ.get("NGINX_CONTAINER", "n8n_nginx")

        # Try to reload nginx container
        result = subprocess.run(
            ["docker", "exec", nginx_container, "nginx", "-s", "reload"],
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


# Environment Variable Management
@router.get("/env/{key}")
async def get_env_variable(
    key: str,
    _=Depends(get_current_user),
):
    """Get environment variable status (masked value)."""
    import os

    # Only allow specific keys for security
    allowed_keys = ["N8N_API_KEY", "NTFY_TOKEN", "TAILSCALE_AUTH_KEY", "CLOUDFLARE_TUNNEL_TOKEN"]
    if key not in allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Key '{key}' is not allowed. Allowed keys: {', '.join(allowed_keys)}",
        )

    # Try to get from host .env file first, then from environment
    value = None

    # Check host .env file
    if os.path.exists(HOST_ENV_PATH):
        try:
            with open(HOST_ENV_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip() == key:
                            value = v.strip().strip('"').strip("'")
                            break
        except Exception as e:
            pass

    # Fall back to environment variable
    if value is None:
        value = os.environ.get(key)

    is_set = value is not None and len(value) > 0
    masked_value = ""
    if is_set and len(value) > 8:
        masked_value = f"{value[:4]}...{value[-4:]}"
    elif is_set:
        masked_value = "*" * len(value)

    return {
        "key": key,
        "is_set": is_set,
        "masked_value": masked_value,
    }


@router.put("/env/{key}")
async def update_env_variable(
    key: str,
    data: Dict[str, Any],
    _=Depends(get_current_user),
):
    """Update an environment variable in the host .env file."""
    import os

    # Only allow specific keys for security
    allowed_keys = ["N8N_API_KEY", "NTFY_TOKEN", "TAILSCALE_AUTH_KEY", "CLOUDFLARE_TUNNEL_TOKEN"]
    if key not in allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Key '{key}' is not allowed. Allowed keys: {', '.join(allowed_keys)}",
        )

    value = data.get("value", "")
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Value is required",
        )

    try:
        # Read existing .env content
        env_content = {}
        if os.path.exists(HOST_ENV_PATH):
            with open(HOST_ENV_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env_content[k.strip()] = v.strip()

        # Update or add the key
        env_content[key] = value

        # Write back to file
        with open(HOST_ENV_PATH, 'w') as f:
            for k, v in env_content.items():
                # Quote values with spaces or special characters
                if ' ' in v or '"' in v or "'" in v:
                    v = f'"{v}"'
                f.write(f"{k}={v}\n")

        # Also update os.environ so the change takes effect immediately
        # This allows services like n8n_api_service to see the new value
        # without requiring a container restart
        os.environ[key] = value

        # For Tailscale auth key, don't auto-reset - just inform that restart is needed
        # The frontend will call the separate reset endpoint after user confirmation
        if key == "TAILSCALE_AUTH_KEY":
            return SuccessResponse(
                message="Tailscale auth key saved. Container restart required to apply changes."
            )

        return SuccessResponse(message=f"Environment variable '{key}' updated successfully.")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update environment variable: {str(e)}",
        )


@router.post("/tailscale/reset")
async def reset_tailscale(
    _=Depends(get_current_user),
):
    """
    Reset the Tailscale container with fresh authentication state.
    This should be called after updating the Tailscale auth key.

    Steps performed:
    1. Stop the Tailscale container
    2. Remove the Tailscale data volume (clears auth state)
    3. Start the container with docker-compose (uses new key from .env)
    """
    logger.info("Manual Tailscale reset requested")
    result = await reset_tailscale_container()

    if result.get("success"):
        return SuccessResponse(message=result.get("message", "Tailscale reset successfully"))
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to reset Tailscale container")
        )


@router.get("/tailscale/status")
async def get_tailscale_status(
    _=Depends(get_current_user),
):
    """
    Get the current status of the Tailscale container.
    Returns running state and whether a restart is needed.
    """
    import subprocess

    try:
        # Check container status
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Status}}', 'n8n_tailscale'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            status = result.stdout.strip()
            return {
                "exists": True,
                "status": status,
                "running": status == "running",
                "action_label": "Restart" if status == "running" else "Start"
            }
        else:
            return {
                "exists": False,
                "status": "not found",
                "running": False,
                "action_label": "Start"
            }

    except Exception as e:
        logger.error(f"Error checking Tailscale status: {e}")
        return {
            "exists": False,
            "status": "error",
            "running": False,
            "action_label": "Start",
            "error": str(e)
        }


# External Routes Management (Public paths in nginx.conf)
# Protected routes that cannot be removed
PROTECTED_EXTERNAL_ROUTES = ["/webhook/", "/webhook-test/"]


def parse_nginx_external_routes(config_content: str) -> List[Dict[str, Any]]:
    """Parse nginx.conf to find ALL location blocks and their access status."""
    import re

    routes = []

    # Known services with metadata for icons and descriptions
    known_services = {
        "webhook": {"icon": "webhook", "color": "green", "default_desc": "n8n Webhook endpoint"},
        "webhook-test": {"icon": "flask", "color": "amber", "default_desc": "n8n Test webhook endpoint"},
        "portainer": {"icon": "cube", "color": "blue", "default_desc": "Docker container management"},
        "adminer": {"icon": "database", "color": "purple", "default_desc": "Database administration"},
        "logs": {"icon": "document-text", "color": "emerald", "default_desc": "Dozzle log viewer"},
        "dozzle": {"icon": "document-text", "color": "emerald", "default_desc": "Dozzle log viewer"},
        "grafana": {"icon": "chart-bar", "color": "orange", "default_desc": "Monitoring dashboard"},
        "prometheus": {"icon": "fire", "color": "red", "default_desc": "Metrics collection"},
        "management": {"icon": "cog", "color": "cyan", "default_desc": "Management console"},
        "healthz": {"icon": "heart", "color": "green", "default_desc": "Health check endpoint"},
        "n8n": {"icon": "bolt", "color": "rose", "default_desc": "n8n workflow automation"},
        "ntfy": {"icon": "bell", "color": "purple", "default_desc": "NTFY push notification server"},
        "n8n_ntfy": {"icon": "bell", "color": "purple", "default_desc": "NTFY push notification server"},
    }

    def extract_location_blocks(content):
        """Extract location blocks with proper brace matching."""
        blocks = []
        i = 0
        while i < len(content):
            match = re.search(r'location\s+(/[a-zA-Z0-9_/-]*)\s*\{', content[i:])
            if not match:
                break

            path = match.group(1)
            start = i + match.start()
            brace_start = i + match.end() - 1

            brace_count = 1
            j = brace_start + 1
            while j < len(content) and brace_count > 0:
                if content[j] == '{':
                    brace_count += 1
                elif content[j] == '}':
                    brace_count -= 1
                j += 1

            if brace_count == 0:
                block_content = content[brace_start + 1:j - 1]
                blocks.append((path, block_content, start))

            i = j if brace_count == 0 else i + match.end()

        return blocks

    location_blocks = extract_location_blocks(config_content)

    # Skip internal/nginx-specific paths
    skip_paths = ['/api/', '/api/auth/verify', '/api/ws/', '/api/backups/download/']

    seen_paths = set()

    for path, block_content, start_pos in location_blocks:
        # Skip internal paths
        if path in skip_paths:
            continue

        # Clean up path
        clean_path = path.rstrip('/') + '/' if path != '/' and not path.endswith('/') else path

        # Skip duplicates
        if clean_path in seen_paths:
            continue
        seen_paths.add(clean_path)

        # Determine access level
        has_trusted_check = '$is_trusted' in block_content or '$access_level' in block_content
        has_auth_request = 'auth_request' in block_content
        is_public = not has_trusted_check and not has_auth_request

        # Determine proxy target and port
        # Match patterns like: proxy_pass http://n8n; or proxy_pass http://n8n:5678; or proxy_pass http://n8n_ntfy:8085/;
        proxy_match = re.search(r'proxy_pass\s+http://([a-zA-Z0-9_]+)(?::(\d+))?(/[^;]*)?;', block_content)
        proxy_target = proxy_match.group(1) if proxy_match else None
        proxy_port = int(proxy_match.group(2)) if proxy_match and proxy_match.group(2) else None

        # Also handle variable-based proxy_pass like: set $var http://upstream:port; proxy_pass $var;
        if not proxy_target:
            # Look for set $variable http://upstream:port pattern
            var_match = re.search(r'set\s+\$\w+\s+http://([a-zA-Z0-9_]+)(?::(\d+))?', block_content)
            if var_match:
                proxy_target = var_match.group(1)
                proxy_port = int(var_match.group(2)) if var_match.group(2) else None

        # Skip if no proxy (static content or internal)
        if not proxy_target:
            continue

        # Get service info based on path or proxy target
        path_key = clean_path.strip('/').split('/')[0] if clean_path != '/' else ''

        # Try path key first, then proxy target
        service_info = known_services.get(path_key) or known_services.get(proxy_target, {})

        # Try to extract description from comment
        description = ""
        pre_context = config_content[:start_pos]
        comment_match = re.search(r'#\s*(?:PUBLIC:|RESTRICTED:)?\s*([^\n]+)\s*$', pre_context)
        if comment_match:
            desc_text = comment_match.group(1).strip()
            # Skip separator comments
            if not desc_text.startswith('==='):
                description = desc_text

        if not description:
            port_info = f":{proxy_port}" if proxy_port else ""
            description = service_info.get("default_desc", f"Proxied to {proxy_target}{port_info}")

        routes.append({
            "path": clean_path,
            "description": description,
            "is_public": is_public,
            "has_auth": has_auth_request,
            "proxy_target": proxy_target,
            "proxy_port": proxy_port,
            "icon": service_info.get("icon", "link"),
            "color": service_info.get("color", "gray"),
            "protected": clean_path in PROTECTED_EXTERNAL_ROUTES,
            "manageable": True,  # All routes can be managed
        })

    # Sort: public first, then by path
    routes.sort(key=lambda r: (not r["is_public"], r["path"]))

    return routes


def get_domain_from_nginx_config(config_content: str) -> str:
    """Extract domain from nginx.conf server_name directive."""
    import re

    # Look for server_name in the 443 server block
    match = re.search(r'server_name\s+([a-zA-Z0-9.-]+);', config_content)
    if match and match.group(1) != '_':
        return match.group(1)
    return None


def generate_external_route_block(
    path: str,
    description: str = "",
    upstream: str = "n8n",
    upstream_port: int = None,
    is_public: bool = True
) -> str:
    """Generate nginx location block for an external route.

    Args:
        path: URL path (e.g., /ntfy/, /webhook-custom/)
        description: Description for the comment
        upstream: Upstream server name (e.g., n8n, n8n_ntfy)
        upstream_port: Optional port number (e.g., 8085)
        is_public: If True, route is public. If False, adds $is_trusted check.
    """
    # Build comment
    access_type = "PUBLIC" if is_public else "RESTRICTED"
    comment = f"# {access_type}: {description}\n        " if description else f"# {access_type}\n        "

    # Build proxy_pass URL
    if upstream_port:
        proxy_url = f"http://{upstream}:{upstream_port}"
    else:
        proxy_url = f"http://{upstream}"

    # Build the trusted check if restricted
    trusted_check = ""
    if not is_public:
        trusted_check = """
            if ($is_trusted = 0) {
                return 403;
            }
"""

    return f'''{comment}location {path} {{{trusted_check}
            add_header X-Frame-Options "SAMEORIGIN" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header X-XSS-Protection "1; mode=block" always;

            proxy_pass {proxy_url};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_buffering off;
        }}'''


def add_external_route_to_config(
    config_content: str,
    path: str,
    description: str = "",
    upstream: str = "n8n",
    upstream_port: int = None,
    is_public: bool = True
) -> str:
    """Add a new external route to nginx.conf."""
    import re

    # Find a good insertion point - after the last webhook location block
    # or before the RESTRICTED section

    # Look for the RESTRICTED comment which marks where restricted routes start
    restricted_match = re.search(r'(\s*#\s*=+\s*\n\s*#\s*RESTRICTED)', config_content)

    if restricted_match:
        # Insert before the RESTRICTED section
        insert_pos = restricted_match.start()
        new_block = generate_external_route_block(path, description, upstream, upstream_port, is_public)
        return config_content[:insert_pos] + "\n\n        " + new_block + "\n" + config_content[insert_pos:]

    # Fallback: look for "location / {" with $is_trusted check
    main_location_match = re.search(r'(\s*location\s+/\s*\{[^}]*\$is_trusted)', config_content, re.DOTALL)
    if main_location_match:
        insert_pos = main_location_match.start()
        new_block = generate_external_route_block(path, description, upstream, upstream_port, is_public)
        return config_content[:insert_pos] + "\n\n        " + new_block + "\n" + config_content[insert_pos:]

    # Last fallback: insert before the last location / block
    return config_content


def remove_external_route_from_config(config_content: str, path: str) -> str:
    """Remove an external route from nginx.conf."""
    import re

    # Match the location block with optional preceding comment
    # Pattern: optional comment line + location /path/ { ... }
    pattern = rf'(\s*#[^\n]*\n)?\s*location\s+{re.escape(path)}\s*\{{[^}}]+\}}\s*'

    return re.sub(pattern, '\n', config_content)


@router.get("/external-routes", response_model=ExternalRoutesResponse)
async def get_external_routes(
    _=Depends(get_current_user),
):
    """Get all externally accessible routes from nginx.conf."""
    import os

    routes = []
    domain = None
    last_updated = None

    if not os.path.exists(NGINX_CONFIG_PATH):
        return ExternalRoutesResponse(
            routes=[],
            domain=None,
            last_updated=None,
        )

    try:
        with open(NGINX_CONFIG_PATH, 'r') as f:
            content = f.read()

        routes = parse_nginx_external_routes(content)
        domain = get_domain_from_nginx_config(content)

        stat = os.stat(NGINX_CONFIG_PATH)
        last_updated = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to read nginx config for external routes: {e}")

    return ExternalRoutesResponse(
        routes=[ExternalRoute(**r) for r in routes],
        domain=domain,
        last_updated=last_updated,
    )


@router.post("/external-routes", response_model=SuccessResponse)
async def add_external_route(
    request: AddExternalRouteRequest,
    _=Depends(get_current_user),
):
    """Add a new externally accessible route.

    Routes can be any valid path (e.g., /ntfy/, /webhook-custom/, /myservice/).
    You can configure:
    - upstream: The backend service name (e.g., n8n, n8n_ntfy)
    - upstream_port: Optional port number (e.g., 8085)
    - is_public: If true (default), route is publicly accessible.
                 If false, route requires IP restriction ($is_trusted check).
    """
    import os

    # Validate path format
    path = request.path.strip()
    if not path.startswith('/'):
        path = '/' + path
    if not path.endswith('/'):
        path = path + '/'

    # Basic security: disallow some dangerous paths
    dangerous_paths = ['/api/', '/admin/', '/config/', '/.']
    for dangerous in dangerous_paths:
        if path.startswith(dangerous) or dangerous in path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path '{path}' is not allowed for security reasons.",
            )

    try:
        if not os.path.exists(NGINX_CONFIG_PATH):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nginx configuration not found",
            )

        with open(NGINX_CONFIG_PATH, 'r') as f:
            content = f.read()

        # Check if route already exists
        existing_routes = parse_nginx_external_routes(content)
        for route in existing_routes:
            if route["path"] == path:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Route {path} already exists",
                )

        # Add the route with all parameters
        new_content = add_external_route_to_config(
            content,
            path,
            request.description,
            request.upstream,
            request.upstream_port,
            request.is_public
        )

        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(new_content)

        access_type = "public" if request.is_public else "restricted"
        return SuccessResponse(message=f"External route {path} added ({access_type}). Reload nginx to apply changes.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add external route: {str(e)}",
        )


@router.delete("/external-routes/{path:path}", response_model=SuccessResponse)
async def delete_external_route(
    path: str,
    _=Depends(get_current_user),
):
    """Remove an externally accessible route."""
    import os

    # Normalize path
    if not path.startswith('/'):
        path = '/' + path
    if not path.endswith('/'):
        path = path + '/'

    # Check if protected
    if path in PROTECTED_EXTERNAL_ROUTES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Route {path} is protected and cannot be removed",
        )

    try:
        if not os.path.exists(NGINX_CONFIG_PATH):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nginx configuration not found",
            )

        with open(NGINX_CONFIG_PATH, 'r') as f:
            content = f.read()

        # Verify route exists
        existing_routes = parse_nginx_external_routes(content)
        route_exists = any(r["path"] == path for r in existing_routes)
        if not route_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route {path} not found",
            )

        # Remove the route
        new_content = remove_external_route_from_config(content, path)

        with open(NGINX_CONFIG_PATH, 'w') as f:
            f.write(new_content)

        return SuccessResponse(message=f"External route {path} removed. Reload nginx to apply changes.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove external route: {str(e)}",
        )


# Debug Mode Management
@router.get("/debug")
async def get_debug_mode(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get debug mode status."""
    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == "debug_mode")
    )
    setting = result.scalar_one_or_none()

    return {
        "enabled": setting.value if setting else False,
    }


@router.put("/debug")
async def set_debug_mode(
    data: Dict[str, Any],
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set debug mode."""
    enabled = data.get("enabled", False)

    result = await db.execute(
        select(SettingsModel).where(SettingsModel.key == "debug_mode")
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = enabled
        setting.updated_at = datetime.now(UTC)
    else:
        setting = SettingsModel(
            key="debug_mode",
            value=enabled,
            category="debug",
            description="Enable debug mode for verbose logging",
        )
        db.add(setting)

    await db.commit()

    return {"enabled": enabled, "message": f"Debug mode {'enabled' if enabled else 'disabled'}"}


# Generic Setting Routes (MUST BE LAST - catch-all routes)
# These must be at the end to not interfere with specific routes above

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
    update_data: SettingUpdate,
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

    setting.value = update_data.value
    if update_data.description is not None:
        setting.description = update_data.description
    setting.updated_at = datetime.now(UTC)
    setting.updated_by = user.id

    await db.commit()
    await db.refresh(setting)

    return SettingValue.model_validate(setting)
