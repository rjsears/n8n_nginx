"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/env_config.py

Environment Configuration Management API
Allows viewing and editing .env file variables

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Environment Configuration"])

# Path to .env file (mounted from host)
ENV_FILE_PATH = Path("/app/host_env/.env")

# Define variable groups and metadata
ENV_VARIABLE_GROUPS = {
    "required": {
        "label": "Required Settings",
        "description": "Core settings required for the system to function",
        "icon": "ExclamationCircleIcon",
        "color": "red",
        "variables": {
            "DOMAIN": {
                "label": "Domain Name",
                "description": "Your n8n domain (e.g., n8n.example.com). Used for SSL certificates and URLs.",
                "type": "string",
                "required": True,
                "sensitive": False,
                "editable": True,
                "validation": r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$",
            },
            "N8N_MANAGEMENT_HOST_IP": {
                "label": "Management Host IP",
                "description": "Local IP address of the Docker host. Used for backup/restore operations.",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "validation": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
            },
        },
    },
    "database": {
        "label": "Database Configuration",
        "description": "PostgreSQL database credentials and settings",
        "icon": "CircleStackIcon",
        "color": "blue",
        "variables": {
            "POSTGRES_USER": {
                "label": "PostgreSQL Username",
                "description": "Database username for n8n and management console",
                "type": "string",
                "required": True,
                "sensitive": False,
                "editable": True,
                "health_check": "postgres_connection",
            },
            "POSTGRES_PASSWORD": {
                "label": "PostgreSQL Password",
                "description": "Database password (changing this requires database migration)",
                "type": "password",
                "required": True,
                "sensitive": True,
                "editable": True,
                "health_check": "postgres_connection",
            },
            "POSTGRES_DB": {
                "label": "Database Name",
                "description": "Name of the PostgreSQL database",
                "type": "string",
                "required": True,
                "sensitive": False,
                "editable": True,
                "health_check": "postgres_connection",
            },
        },
    },
    "security": {
        "label": "Security & Authentication",
        "description": "Encryption keys and admin credentials",
        "icon": "ShieldCheckIcon",
        "color": "amber",
        "variables": {
            "N8N_ENCRYPTION_KEY": {
                "label": "n8n Encryption Key",
                "description": "Used to encrypt credentials in n8n. DO NOT CHANGE after initial setup!",
                "type": "password",
                "required": True,
                "sensitive": True,
                "editable": False,  # Should never be changed after setup
                "warning": "Changing this will make all stored credentials in n8n unreadable!",
            },
            "MGMT_SECRET_KEY": {
                "label": "Management Secret Key",
                "description": "Secret key for management console sessions",
                "type": "password",
                "required": True,
                "sensitive": True,
                "editable": True,
            },
            "ADMIN_USER": {
                "label": "Admin Username",
                "description": "Username for management console login",
                "type": "string",
                "required": True,
                "sensitive": False,
                "editable": True,
            },
            "ADMIN_PASS": {
                "label": "Admin Password",
                "description": "Password for management console login",
                "type": "password",
                "required": True,
                "sensitive": True,
                "editable": True,
            },
            "ADMIN_EMAIL": {
                "label": "Admin Email",
                "description": "Email address for admin notifications",
                "type": "email",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
        },
    },
    "management": {
        "label": "Management Console",
        "description": "Settings for the management console",
        "icon": "Cog6ToothIcon",
        "color": "purple",
        "variables": {
            "MGMT_PORT": {
                "label": "Management Port",
                "description": "Internal port for the management console",
                "type": "number",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "3333",
            },
            "MGMT_DB_USER": {
                "label": "Management DB User",
                "description": "Database user for management console (usually same as POSTGRES_USER)",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
            "MGMT_DB_PASSWORD": {
                "label": "Management DB Password",
                "description": "Database password for management console",
                "type": "password",
                "required": False,
                "sensitive": True,
                "editable": True,
            },
            "TIMEZONE": {
                "label": "Timezone",
                "description": "System timezone (e.g., America/Los_Angeles)",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "America/Los_Angeles",
            },
        },
    },
    "nfs": {
        "label": "NFS Backup Storage",
        "description": "Optional NFS mount for remote backup storage",
        "icon": "ServerIcon",
        "color": "emerald",
        "variables": {
            "NFS_SERVER": {
                "label": "NFS Server",
                "description": "Hostname or IP of NFS server",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
            "NFS_PATH": {
                "label": "NFS Path",
                "description": "Export path on NFS server (e.g., /exports/backups)",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
            "NFS_LOCAL_MOUNT": {
                "label": "Local Mount Point",
                "description": "Local path to mount NFS share",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
        },
    },
    "cloudflare": {
        "label": "Cloudflare Tunnel",
        "description": "Optional Cloudflare Tunnel for secure access",
        "icon": "CloudIcon",
        "color": "orange",
        "variables": {
            "CLOUDFLARE_TUNNEL_TOKEN": {
                "label": "Tunnel Token",
                "description": "Cloudflare Tunnel authentication token",
                "type": "password",
                "required": False,
                "sensitive": True,
                "editable": True,
            },
        },
    },
    "tailscale": {
        "label": "Tailscale VPN",
        "description": "Optional Tailscale VPN integration",
        "icon": "GlobeAltIcon",
        "color": "indigo",
        "variables": {
            "TAILSCALE_AUTH_KEY": {
                "label": "Auth Key",
                "description": "Tailscale authentication key",
                "type": "password",
                "required": False,
                "sensitive": True,
                "editable": True,
            },
            "TAILSCALE_ROUTES": {
                "label": "Advertised Routes",
                "description": "CIDR routes to advertise (e.g., 192.168.1.0/24)",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
        },
    },
    "containers": {
        "label": "Container Names",
        "description": "Docker container name configuration",
        "icon": "CubeIcon",
        "color": "gray",
        "variables": {
            "POSTGRES_CONTAINER": {
                "label": "PostgreSQL Container",
                "description": "Name of the PostgreSQL container",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "n8n_postgres",
            },
            "N8N_CONTAINER": {
                "label": "n8n Container",
                "description": "Name of the n8n container",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "n8n",
            },
            "NGINX_CONTAINER": {
                "label": "Nginx Container",
                "description": "Name of the Nginx container",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "n8n_nginx",
            },
            "CERTBOT_CONTAINER": {
                "label": "Certbot Container",
                "description": "Name of the Certbot container",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "n8n_certbot",
            },
            "MANAGEMENT_CONTAINER": {
                "label": "Management Container",
                "description": "Name of the management console container",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
                "default": "n8n_management",
            },
        },
    },
    "ntfy": {
        "label": "NTFY Notifications",
        "description": "NTFY push notification settings",
        "icon": "BellIcon",
        "color": "cyan",
        "variables": {
            "NTFY_BASE_URL": {
                "label": "NTFY Base URL",
                "description": "URL of your NTFY server",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
            "NTFY_PUBLIC_URL": {
                "label": "NTFY Public URL",
                "description": "Public URL for NTFY (for documentation/examples)",
                "type": "string",
                "required": False,
                "sensitive": False,
                "editable": True,
            },
        },
    },
    "n8n_api": {
        "label": "n8n API Integration",
        "description": "Settings for n8n API access",
        "icon": "CodeBracketIcon",
        "color": "pink",
        "variables": {
            "N8N_API_KEY": {
                "label": "n8n API Key",
                "description": "API key for n8n workflow management (generate in n8n Settings > API)",
                "type": "password",
                "required": False,
                "sensitive": True,
                "editable": True,
            },
        },
    },
    "custom": {
        "label": "Custom Variables",
        "description": "User-defined environment variables",
        "icon": "PlusCircleIcon",
        "color": "slate",
        "variables": {},  # Populated dynamically
    },
}

# System variables that should never be deleted
SYSTEM_VARIABLES = set()
for group in ENV_VARIABLE_GROUPS.values():
    SYSTEM_VARIABLES.update(group.get("variables", {}).keys())


# Pydantic models
class EnvVariable(BaseModel):
    key: str
    value: str
    group: str
    label: str
    description: str
    type: str = "string"
    required: bool = False
    sensitive: bool = False
    editable: bool = True
    warning: Optional[str] = None
    default: Optional[str] = None
    validation: Optional[str] = None
    health_check: Optional[str] = None
    is_custom: bool = False


class EnvGroup(BaseModel):
    key: str
    label: str
    description: str
    icon: str
    color: str
    variables: List[EnvVariable]


class EnvConfigResponse(BaseModel):
    groups: List[EnvGroup]
    last_modified: Optional[str] = None


class EnvUpdateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=10000)


class EnvAddRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    value: str = Field(..., max_length=10000)


class HealthCheckResult(BaseModel):
    check_type: str
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    overall_success: bool
    checks: List[HealthCheckResult]
    warnings: List[str] = []


def parse_env_file() -> Dict[str, str]:
    """Parse the .env file and return key-value pairs."""
    env_vars = {}

    if not ENV_FILE_PATH.exists():
        logger.warning(f".env file not found at {ENV_FILE_PATH}")
        return env_vars

    try:
        with open(ENV_FILE_PATH, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    env_vars[key] = value

    except Exception as e:
        logger.error(f"Error parsing .env file: {e}")

    return env_vars


def write_env_file(env_vars: Dict[str, str]) -> bool:
    """Write environment variables back to .env file with proper formatting."""
    try:
        # Read existing file to preserve comments and structure
        lines = []
        seen_keys = set()

        if ENV_FILE_PATH.exists():
            with open(ENV_FILE_PATH, "r") as f:
                for line in f:
                    stripped = line.strip()

                    # Keep comments and empty lines
                    if not stripped or stripped.startswith("#"):
                        lines.append(line.rstrip("\n"))
                        continue

                    # Update existing variables
                    if "=" in stripped:
                        key = stripped.split("=", 1)[0].strip()
                        if key in env_vars:
                            # Escape value if it contains special characters
                            value = env_vars[key]
                            if " " in value or '"' in value or "'" in value or "$" in value:
                                value = f'"{value}"'
                            lines.append(f"{key}={value}")
                            seen_keys.add(key)
                        else:
                            # Key was deleted, skip it
                            continue
                    else:
                        lines.append(line.rstrip("\n"))

        # Add any new variables at the end
        new_vars = []
        for key, value in env_vars.items():
            if key not in seen_keys:
                if " " in value or '"' in value or "'" in value or "$" in value:
                    value = f'"{value}"'
                new_vars.append(f"{key}={value}")

        if new_vars:
            if lines and lines[-1]:  # Add blank line before new vars
                lines.append("")
            lines.append("# Custom Variables")
            lines.extend(new_vars)

        # Write back
        with open(ENV_FILE_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")

        return True

    except Exception as e:
        logger.error(f"Error writing .env file: {e}")
        return False


def get_variable_metadata(key: str) -> Dict[str, Any]:
    """Get metadata for a variable from the group definitions."""
    for group_key, group_data in ENV_VARIABLE_GROUPS.items():
        if key in group_data.get("variables", {}):
            meta = group_data["variables"][key].copy()
            meta["group"] = group_key
            return meta

    # Not found in known groups - it's a custom variable
    return {
        "group": "custom",
        "label": key,
        "description": "User-defined environment variable",
        "type": "string",
        "required": False,
        "sensitive": False,
        "editable": True,
        "is_custom": True,
    }


@router.get("", response_model=EnvConfigResponse)
async def get_env_config(_=Depends(get_current_user)):
    """Get all environment variables organized by group."""
    env_vars = parse_env_file()

    # Build response grouped by category
    groups = []
    assigned_vars = set()

    for group_key, group_data in ENV_VARIABLE_GROUPS.items():
        if group_key == "custom":
            continue  # Handle custom vars separately

        variables = []
        for var_key, var_meta in group_data.get("variables", {}).items():
            value = env_vars.get(var_key, var_meta.get("default", ""))
            assigned_vars.add(var_key)

            variables.append(EnvVariable(
                key=var_key,
                value="" if var_meta.get("sensitive") else value,  # Hide sensitive values
                group=group_key,
                label=var_meta.get("label", var_key),
                description=var_meta.get("description", ""),
                type=var_meta.get("type", "string"),
                required=var_meta.get("required", False),
                sensitive=var_meta.get("sensitive", False),
                editable=var_meta.get("editable", True),
                warning=var_meta.get("warning"),
                default=var_meta.get("default"),
                validation=var_meta.get("validation"),
                health_check=var_meta.get("health_check"),
                is_custom=False,
            ))

        if variables:
            groups.append(EnvGroup(
                key=group_key,
                label=group_data["label"],
                description=group_data["description"],
                icon=group_data["icon"],
                color=group_data["color"],
                variables=variables,
            ))

    # Add custom variables (any not in known groups)
    custom_vars = []
    for key, value in env_vars.items():
        if key not in assigned_vars:
            custom_vars.append(EnvVariable(
                key=key,
                value=value,
                group="custom",
                label=key,
                description="User-defined environment variable",
                type="string",
                required=False,
                sensitive=False,
                editable=True,
                is_custom=True,
            ))

    if custom_vars:
        groups.append(EnvGroup(
            key="custom",
            label="Custom Variables",
            description="User-defined environment variables",
            icon="PlusCircleIcon",
            color="slate",
            variables=custom_vars,
        ))

    # Get last modified time
    last_modified = None
    if ENV_FILE_PATH.exists():
        mtime = ENV_FILE_PATH.stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime, UTC).isoformat()

    return EnvConfigResponse(groups=groups, last_modified=last_modified)


@router.put("/{key}")
async def update_env_variable(
    key: str,
    data: EnvUpdateRequest,
    _=Depends(get_current_user),
):
    """Update an environment variable."""
    if data.key != key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key in URL must match key in body",
        )

    # Get metadata
    meta = get_variable_metadata(key)

    # Check if editable
    if not meta.get("editable", True) and not meta.get("is_custom", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Variable '{key}' cannot be modified",
        )

    # Validate value if pattern provided
    if meta.get("validation"):
        if not re.match(meta["validation"], data.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value format for '{key}'",
            )

    # Read current values
    env_vars = parse_env_file()

    # Update
    env_vars[key] = data.value

    # Write back
    if not write_env_file(env_vars):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write .env file",
        )

    logger.info(f"Environment variable '{key}' updated")

    return {"status": "success", "message": f"Variable '{key}' updated"}


@router.post("")
async def add_env_variable(
    data: EnvAddRequest,
    _=Depends(get_current_user),
):
    """Add a new custom environment variable."""
    # Check if key already exists
    env_vars = parse_env_file()

    if data.key in env_vars:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Variable '{data.key}' already exists",
        )

    # Check if it's a system variable name
    if data.key in SYSTEM_VARIABLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{data.key}' is a reserved system variable name",
        )

    # Add the variable
    env_vars[data.key] = data.value

    if not write_env_file(env_vars):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write .env file",
        )

    logger.info(f"Custom environment variable '{data.key}' added")

    return {"status": "success", "message": f"Variable '{data.key}' added"}


@router.delete("/{key}")
async def delete_env_variable(
    key: str,
    _=Depends(get_current_user),
):
    """Delete a custom environment variable."""
    # Check if it's a system variable
    if key in SYSTEM_VARIABLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"System variable '{key}' cannot be deleted",
        )

    env_vars = parse_env_file()

    if key not in env_vars:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variable '{key}' not found",
        )

    del env_vars[key]

    if not write_env_file(env_vars):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write .env file",
        )

    logger.info(f"Custom environment variable '{key}' deleted")

    return {"status": "success", "message": f"Variable '{key}' deleted"}


@router.post("/reload")
async def reload_env_variables(_=Depends(get_current_user)):
    """
    Force reload of environment variables.
    Note: This only reloads os.environ, containers need restart for changes.
    """
    try:
        env_vars = parse_env_file()

        # Update os.environ
        for key, value in env_vars.items():
            os.environ[key] = value

        logger.info("Environment variables reloaded into current process")

        return {
            "status": "success",
            "message": "Environment variables reloaded. Note: Containers must be restarted for changes to take effect.",
            "reloaded_count": len(env_vars),
        }

    except Exception as e:
        logger.error(f"Failed to reload environment variables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload: {str(e)}",
        )


@router.post("/health-check", response_model=HealthCheckResponse)
async def run_health_checks(
    pending_changes: Optional[Dict[str, str]] = None,
    _=Depends(get_current_user),
):
    """
    Run health checks to validate environment configuration.
    Optionally pass pending_changes to validate before applying.
    """
    checks = []
    warnings = []

    # Get current env vars and merge with pending changes
    env_vars = parse_env_file()
    if pending_changes:
        test_env = {**env_vars, **pending_changes}
    else:
        test_env = env_vars

    # Check 1: PostgreSQL Connection
    postgres_check = await _check_postgres_connection(test_env)
    checks.append(postgres_check)

    # Check 2: Domain Resolution
    domain_check = await _check_domain_resolution(test_env)
    checks.append(domain_check)

    # Check 3: Required Variables
    required_check = _check_required_variables(test_env)
    checks.append(required_check)

    # Check 4: Container Names
    container_check = await _check_container_names(test_env)
    checks.append(container_check)

    # Generate warnings for sensitive changes
    if pending_changes:
        if "POSTGRES_PASSWORD" in pending_changes:
            warnings.append("Changing POSTGRES_PASSWORD requires updating the database password manually")
        if "POSTGRES_USER" in pending_changes:
            warnings.append("Changing POSTGRES_USER requires recreating the database with new ownership")
        if "N8N_ENCRYPTION_KEY" in pending_changes:
            warnings.append("CRITICAL: Changing N8N_ENCRYPTION_KEY will make all stored credentials unreadable!")

    overall_success = all(c.success for c in checks)

    return HealthCheckResponse(
        overall_success=overall_success,
        checks=checks,
        warnings=warnings,
    )


async def _check_postgres_connection(env_vars: Dict[str, str]) -> HealthCheckResult:
    """Test PostgreSQL connection with given credentials."""
    try:
        import asyncpg

        user = env_vars.get("POSTGRES_USER", "n8n")
        password = env_vars.get("POSTGRES_PASSWORD", "")
        db = env_vars.get("POSTGRES_DB", "n8n")
        container = env_vars.get("POSTGRES_CONTAINER", "n8n_postgres")

        # Try connecting to postgres container
        conn = await asyncio.wait_for(
            asyncpg.connect(
                host=container,
                port=5432,
                user=user,
                password=password,
                database=db,
            ),
            timeout=5.0,
        )
        await conn.close()

        return HealthCheckResult(
            check_type="postgres_connection",
            success=True,
            message="PostgreSQL connection successful",
            details={"host": container, "user": user, "database": db},
        )

    except asyncio.TimeoutError:
        return HealthCheckResult(
            check_type="postgres_connection",
            success=False,
            message="PostgreSQL connection timed out",
            details={"error": "Connection timeout after 5 seconds"},
        )
    except Exception as e:
        return HealthCheckResult(
            check_type="postgres_connection",
            success=False,
            message=f"PostgreSQL connection failed: {str(e)}",
            details={"error": str(e)},
        )


async def _check_domain_resolution(env_vars: Dict[str, str]) -> HealthCheckResult:
    """Check if domain resolves correctly."""
    import socket

    domain = env_vars.get("DOMAIN", "")
    if not domain:
        return HealthCheckResult(
            check_type="domain_resolution",
            success=False,
            message="DOMAIN is not set",
        )

    try:
        ip = socket.gethostbyname(domain)
        return HealthCheckResult(
            check_type="domain_resolution",
            success=True,
            message=f"Domain resolves to {ip}",
            details={"domain": domain, "ip": ip},
        )
    except socket.gaierror as e:
        return HealthCheckResult(
            check_type="domain_resolution",
            success=False,
            message=f"Cannot resolve domain: {domain}",
            details={"error": str(e)},
        )


def _check_required_variables(env_vars: Dict[str, str]) -> HealthCheckResult:
    """Check that all required variables are set."""
    missing = []

    for group_data in ENV_VARIABLE_GROUPS.values():
        for var_key, var_meta in group_data.get("variables", {}).items():
            if var_meta.get("required") and not env_vars.get(var_key):
                missing.append(var_key)

    if missing:
        return HealthCheckResult(
            check_type="required_variables",
            success=False,
            message=f"Missing required variables: {', '.join(missing)}",
            details={"missing": missing},
        )

    return HealthCheckResult(
        check_type="required_variables",
        success=True,
        message="All required variables are set",
    )


async def _check_container_names(env_vars: Dict[str, str]) -> HealthCheckResult:
    """Check that referenced containers exist."""
    try:
        import docker

        client = docker.from_env()

        container_vars = [
            "POSTGRES_CONTAINER",
            "N8N_CONTAINER",
            "NGINX_CONTAINER",
            "MANAGEMENT_CONTAINER",
        ]

        missing = []
        found = []

        for var in container_vars:
            container_name = env_vars.get(var)
            if container_name:
                try:
                    client.containers.get(container_name)
                    found.append(container_name)
                except docker.errors.NotFound:
                    missing.append(container_name)

        if missing:
            return HealthCheckResult(
                check_type="container_names",
                success=False,
                message=f"Containers not found: {', '.join(missing)}",
                details={"missing": missing, "found": found},
            )

        return HealthCheckResult(
            check_type="container_names",
            success=True,
            message=f"All {len(found)} configured containers found",
            details={"found": found},
        )

    except Exception as e:
        return HealthCheckResult(
            check_type="container_names",
            success=False,
            message=f"Container check failed: {str(e)}",
            details={"error": str(e)},
        )
