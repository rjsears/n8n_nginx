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

from api.dependencies import get_current_user

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
                "description": "Internal IP Address of Docker Management Host. Critical for Cloudflare Tunnels and Tailscale to operate properly. This MUST internally resolve to the hostname entered above.",
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
                "description": "CIDR routes to advertise (see current value below for your configured route)",
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
    Run comprehensive health checks to validate environment and system configuration.
    Checks all containers, network services, database, and required variables.
    """
    checks = []
    warnings = []

    # Get current env vars and merge with pending changes
    env_vars = parse_env_file()
    if pending_changes:
        test_env = {**env_vars, **pending_changes}
    else:
        test_env = env_vars

    # Check 1: All Containers (with categorization)
    container_check = await _check_all_containers()
    checks.append(container_check)

    # Check 2: PostgreSQL Connection
    postgres_check = await _check_postgres_connection(test_env)
    checks.append(postgres_check)

    # Check 3: Domain Resolution
    domain_check = await _check_domain_resolution(test_env)
    checks.append(domain_check)

    # Check 4: Required Variables
    required_check = _check_required_variables(test_env)
    checks.append(required_check)

    # Check 5: Cloudflare Tunnel (if configured)
    cloudflare_check = await _check_cloudflare_tunnel()
    checks.append(cloudflare_check)

    # Check 6: Tailscale VPN (if configured)
    tailscale_check = await _check_tailscale()
    checks.append(tailscale_check)

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


async def _check_all_containers() -> HealthCheckResult:
    """Check all containers from docker-compose.yaml with categorization."""
    try:
        import docker
        import yaml

        client = docker.from_env()

        # Define container categories and expected containers
        container_categories = {
            "core": {
                "label": "Core Services",
                "color": "blue",
                "containers": {
                    "n8n_postgres": {"display": "PostgreSQL", "required": True},
                    "n8n": {"display": "n8n Automation", "required": True},
                    "n8n_nginx": {"display": "Nginx Proxy", "required": True},
                    "n8n_management": {"display": "Management Console", "required": True},
                    "n8n_certbot": {"display": "Certbot SSL", "required": True},
                }
            },
            "optional": {
                "label": "Optional Services",
                "color": "purple",
                "containers": {
                    "n8n_adminer": {"display": "Adminer DB", "required": False},
                    "n8n_dozzle": {"display": "Dozzle Logs", "required": False},
                    "n8n_portainer": {"display": "Portainer", "required": False},
                    "n8n_ntfy": {"display": "NTFY Notifications", "required": False},
                }
            },
            "network": {
                "label": "Network Services",
                "color": "emerald",
                "containers": {
                    "n8n_cloudflared": {"display": "Cloudflare Tunnel", "required": False},
                    "n8n_tailscale": {"display": "Tailscale VPN", "required": False},
                }
            },
        }

        # Get all running containers
        all_containers = client.containers.list(all=True)
        container_map = {c.name: c for c in all_containers}

        categories_result = {}
        total_found = 0
        total_running = 0
        total_missing_required = 0

        for cat_key, cat_data in container_categories.items():
            cat_result = {
                "label": cat_data["label"],
                "color": cat_data["color"],
                "containers": [],
            }

            for container_name, container_info in cat_data["containers"].items():
                container = container_map.get(container_name)
                status = "not_found"
                health = None

                if container:
                    status = container.status
                    total_found += 1
                    if status == "running":
                        total_running += 1
                        # Check health if available
                        try:
                            health_state = container.attrs.get("State", {}).get("Health", {})
                            if health_state:
                                health = health_state.get("Status", "unknown")
                        except Exception:
                            pass
                elif container_info["required"]:
                    total_missing_required += 1

                cat_result["containers"].append({
                    "name": container_name,
                    "display": container_info["display"],
                    "status": status,
                    "health": health,
                    "required": container_info["required"],
                })

            categories_result[cat_key] = cat_result

        success = total_missing_required == 0
        message = f"{total_running}/{total_found} containers running"
        if total_missing_required > 0:
            message = f"{total_missing_required} required container(s) missing"

        return HealthCheckResult(
            check_type="containers",
            success=success,
            message=message,
            details={
                "categories": categories_result,
                "total_found": total_found,
                "total_running": total_running,
                "missing_required": total_missing_required,
            },
        )

    except Exception as e:
        return HealthCheckResult(
            check_type="containers",
            success=False,
            message=f"Container check failed: {str(e)}",
            details={"error": str(e)},
        )


async def _check_cloudflare_tunnel() -> HealthCheckResult:
    """Check Cloudflare Tunnel status."""
    try:
        import docker
        import re

        client = docker.from_env()

        # Find cloudflared container
        cf_container = None
        for container in client.containers.list(all=True):
            if "cloudflare" in container.name.lower():
                cf_container = container
                break

        if not cf_container:
            return HealthCheckResult(
                check_type="cloudflare_tunnel",
                success=True,  # Not a failure if not configured
                message="Cloudflare Tunnel not configured",
                details={"installed": False},
            )

        if cf_container.status != "running":
            return HealthCheckResult(
                check_type="cloudflare_tunnel",
                success=False,
                message=f"Cloudflare Tunnel container is {cf_container.status}",
                details={"installed": True, "running": False, "status": cf_container.status},
            )

        # Check if tunnel is connected by examining logs
        try:
            logs = cf_container.logs(tail=50).decode("utf-8")
            connected = "registered" in logs.lower() or "connection" in logs.lower()

            # Try to get metrics
            metrics = {}
            try:
                exit_code, output = cf_container.exec_run(
                    "wget -q -O- http://localhost:2000/metrics 2>/dev/null",
                    demux=True
                )
                if exit_code == 0 and output[0]:
                    metrics_text = output[0].decode("utf-8")
                    # Extract HA connections count
                    match = re.search(r'cloudflared_tunnel_ha_connections\s+(\d+)', metrics_text)
                    if match:
                        metrics["ha_connections"] = int(match.group(1))
            except Exception:
                pass

            return HealthCheckResult(
                check_type="cloudflare_tunnel",
                success=True,
                message="Cloudflare Tunnel connected" if connected else "Cloudflare Tunnel running",
                details={
                    "installed": True,
                    "running": True,
                    "connected": connected,
                    "container": cf_container.name,
                    "metrics": metrics,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                check_type="cloudflare_tunnel",
                success=True,
                message="Cloudflare Tunnel running (status unknown)",
                details={"installed": True, "running": True, "error": str(e)},
            )

    except Exception as e:
        return HealthCheckResult(
            check_type="cloudflare_tunnel",
            success=False,
            message=f"Cloudflare check failed: {str(e)}",
            details={"error": str(e)},
        )


async def _check_tailscale() -> HealthCheckResult:
    """Check Tailscale VPN status."""
    try:
        import docker
        import json as json_module

        client = docker.from_env()

        # Find tailscale container
        ts_container = None
        for container in client.containers.list(all=True):
            if "tailscale" in container.name.lower():
                ts_container = container
                break

        if not ts_container:
            return HealthCheckResult(
                check_type="tailscale",
                success=True,  # Not a failure if not configured
                message="Tailscale not configured",
                details={"installed": False},
            )

        if ts_container.status != "running":
            return HealthCheckResult(
                check_type="tailscale",
                success=False,
                message=f"Tailscale container is {ts_container.status}",
                details={"installed": True, "running": False, "status": ts_container.status},
            )

        # Get tailscale status
        try:
            exit_code, output = ts_container.exec_run(
                "tailscale status --json",
                demux=True
            )

            if exit_code == 0 and output[0]:
                ts_status = json_module.loads(output[0].decode("utf-8"))
                logged_in = ts_status.get("BackendState") == "Running"
                self_info = ts_status.get("Self", {})

                tailscale_ip = None
                hostname = None
                if self_info:
                    ts_ips = self_info.get("TailscaleIPs", [])
                    if ts_ips:
                        tailscale_ip = ts_ips[0]
                    hostname = self_info.get("HostName")

                peer_count = len(ts_status.get("Peer", {}))
                tailnet = ts_status.get("CurrentTailnet", {}).get("Name")

                return HealthCheckResult(
                    check_type="tailscale",
                    success=logged_in,
                    message=f"Tailscale connected to {tailnet}" if logged_in else "Tailscale not logged in",
                    details={
                        "installed": True,
                        "running": True,
                        "logged_in": logged_in,
                        "tailscale_ip": tailscale_ip,
                        "hostname": hostname,
                        "tailnet": tailnet,
                        "peer_count": peer_count,
                        "container": ts_container.name,
                    },
                )
        except Exception as e:
            return HealthCheckResult(
                check_type="tailscale",
                success=True,
                message="Tailscale running (status unknown)",
                details={"installed": True, "running": True, "error": str(e)},
            )

    except Exception as e:
        return HealthCheckResult(
            check_type="tailscale",
            success=False,
            message=f"Tailscale check failed: {str(e)}",
            details={"error": str(e)},
        )


# ============================================
# BACKUP/RESTORE FUNCTIONALITY
# ============================================

DOCKER_COMPOSE_PATH = Path("/app/host_config/docker-compose.yaml")

# Mapping of env variables to container services (parsed from docker-compose.yaml)
# This maps each env var to the services that use it
ENV_VAR_TO_CONTAINERS = {
    # PostgreSQL container
    "POSTGRES_USER": ["postgres", "n8n", "n8n_management"],
    "POSTGRES_PASSWORD": ["postgres", "n8n", "n8n_management"],
    "POSTGRES_DB": ["postgres", "n8n", "n8n_management"],
    "POSTGRES_CONTAINER": ["postgres", "n8n_management", "adminer"],
    # Domain/URL settings
    "DOMAIN": ["n8n", "n8n_management", "ntfy"],
    # Timezone
    "TIMEZONE": ["n8n", "n8n_management", "ntfy"],
    # n8n specific
    "N8N_ENCRYPTION_KEY": ["n8n", "n8n_management"],
    "N8N_CONTAINER": ["n8n"],
    # Management console
    "MGMT_PORT": ["nginx"],
    "MGMT_SECRET_KEY": ["n8n_management"],
    "MGMT_ENCRYPTION_KEY": ["n8n_management"],
    "MGMT_DB_USER": ["n8n_management"],
    "MGMT_DB_PASSWORD": ["n8n_management"],
    "ADMIN_USER": ["n8n_management"],
    "ADMIN_PASS": ["n8n_management"],
    "ADMIN_EMAIL": ["n8n_management"],
    "MANAGEMENT_CONTAINER": ["n8n_management"],
    # NFS settings
    "NFS_SERVER": ["n8n_management"],
    "NFS_PATH": ["n8n_management"],
    "NFS_LOCAL_MOUNT": ["n8n_management"],
    # Cloudflare
    "CLOUDFLARE_TUNNEL_TOKEN": ["cloudflared"],
    # Tailscale
    "TAILSCALE_AUTH_KEY": ["tailscale"],
    "TAILSCALE_ROUTES": ["tailscale"],
    # Nginx
    "NGINX_CONTAINER": ["nginx", "certbot"],
    # Certbot
    "CERTBOT_CONTAINER": ["certbot"],
    "DNS_CERTBOT_IMAGE": ["certbot"],
    "DNS_CERTBOT_FLAGS": ["certbot"],
    "DNS_CREDENTIALS_FILE": ["certbot"],
    # NTFY
    "NTFY_BASE_URL": ["ntfy"],
    "NTFY_PUBLIC_URL": ["n8n_management"],
    "NTFY_AUTH_DEFAULT_ACCESS": ["ntfy"],
    "NTFY_ENABLE_LOGIN": ["ntfy"],
    "NTFY_ENABLE_SIGNUP": ["ntfy"],
    "NTFY_CACHE_DURATION": ["ntfy"],
    "NTFY_ATTACHMENT_TOTAL_SIZE_LIMIT": ["ntfy"],
    "NTFY_ATTACHMENT_FILE_SIZE_LIMIT": ["ntfy"],
    "NTFY_ATTACHMENT_EXPIRY_DURATION": ["ntfy"],
    "NTFY_KEEPALIVE_INTERVAL": ["ntfy"],
    "NTFY_SMTP_SENDER_ADDR": ["ntfy"],
    "NTFY_SMTP_SENDER_USER": ["ntfy"],
    "NTFY_SMTP_SENDER_PASS": ["ntfy"],
    "NTFY_SMTP_SENDER_FROM": ["ntfy"],
    # n8n API
    "N8N_API_KEY": ["n8n_management"],
    "N8N_EDITOR_BASE_URL": ["n8n_management"],
}

# Service name to container name mapping
SERVICE_TO_CONTAINER = {
    "postgres": "${POSTGRES_CONTAINER:-n8n_postgres}",
    "n8n": "${N8N_CONTAINER:-n8n}",
    "nginx": "${NGINX_CONTAINER:-n8n_nginx}",
    "certbot": "${CERTBOT_CONTAINER:-n8n_certbot}",
    "n8n_management": "${MANAGEMENT_CONTAINER:-n8n_management}",
    "adminer": "n8n_adminer",
    "dozzle": "n8n_dozzle",
    "cloudflared": "n8n_cloudflared",
    "tailscale": "n8n_tailscale",
    "portainer": "n8n_portainer",
    "ntfy": "n8n_ntfy",
}


class EnvBackup(BaseModel):
    filename: str
    created_at: str
    size: int


class EnvBackupListResponse(BaseModel):
    backups: List[EnvBackup]


class EnvRestoreRequest(BaseModel):
    filename: str


class ContainerRestartRequest(BaseModel):
    containers: List[str]


class AffectedContainersResponse(BaseModel):
    variable: str
    affected_containers: List[str]
    container_display_names: Dict[str, str]


def get_backup_dir() -> Path:
    """Get the directory where .env backups are stored."""
    return ENV_FILE_PATH.parent


def create_env_backup() -> str:
    """Create a backup of the current .env file."""
    if not ENV_FILE_PATH.exists():
        raise ValueError(".env file does not exist")

    backup_dir = get_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_filename = f".env_backup_{timestamp}"
    backup_path = backup_dir / backup_filename

    # Copy the file
    import shutil
    shutil.copy2(ENV_FILE_PATH, backup_path)

    logger.info(f"Created .env backup: {backup_filename}")
    return backup_filename


def list_env_backups() -> List[EnvBackup]:
    """List all available .env backup files."""
    backup_dir = get_backup_dir()
    backups = []

    for f in backup_dir.glob(".env_backup_*"):
        if f.is_file():
            stat = f.stat()
            # Parse timestamp from filename
            try:
                timestamp_str = f.name.replace(".env_backup_", "")
                created_dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                created_at = created_dt.isoformat()
            except ValueError:
                created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()

            backups.append(EnvBackup(
                filename=f.name,
                created_at=created_at,
                size=stat.st_size,
            ))

    # Sort by created_at descending (newest first)
    backups.sort(key=lambda x: x.created_at, reverse=True)
    return backups


def get_container_name(service: str, env_vars: Dict[str, str]) -> str:
    """Resolve a service name to its container name using env vars."""
    template = SERVICE_TO_CONTAINER.get(service, service)

    # Handle ${VAR:-default} pattern
    import re
    pattern = r'\$\{([A-Z_]+):-([^}]+)\}'
    match = re.match(pattern, template)
    if match:
        var_name, default = match.groups()
        return env_vars.get(var_name, default)

    # Handle ${VAR} pattern
    pattern = r'\$\{([A-Z_]+)\}'
    match = re.match(pattern, template)
    if match:
        var_name = match.group(1)
        return env_vars.get(var_name, service)

    return template


def get_affected_containers(variable: str, env_vars: Dict[str, str]) -> List[str]:
    """Get list of container names that would be affected by changing a variable."""
    services = ENV_VAR_TO_CONTAINERS.get(variable, [])

    # Convert service names to container names
    containers = []
    for service in services:
        container_name = get_container_name(service, env_vars)
        if container_name not in containers:
            containers.append(container_name)

    return containers


@router.post("/backup")
async def create_backup(_=Depends(get_current_user)):
    """Create a backup of the current .env file."""
    try:
        filename = create_env_backup()
        return {
            "status": "success",
            "message": f"Backup created: {filename}",
            "filename": filename,
        }
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {str(e)}",
        )


@router.get("/backups", response_model=EnvBackupListResponse)
async def get_backups(_=Depends(get_current_user)):
    """List all available .env backup files."""
    try:
        backups = list_env_backups()
        return EnvBackupListResponse(backups=backups)
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backups: {str(e)}",
        )


@router.post("/restore")
async def restore_backup(
    data: EnvRestoreRequest,
    _=Depends(get_current_user),
):
    """Restore a .env file from backup. Creates a backup of current .env first."""
    backup_dir = get_backup_dir()
    backup_path = backup_dir / data.filename

    # Validate filename format for security
    if not data.filename.startswith(".env_backup_") or "/" in data.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid backup filename",
        )

    if not backup_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {data.filename}",
        )

    try:
        # Create backup of current .env before restoring
        current_backup = create_env_backup()
        logger.info(f"Created backup of current .env before restore: {current_backup}")

        # Restore from backup
        import shutil
        shutil.copy2(backup_path, ENV_FILE_PATH)

        logger.info(f"Restored .env from backup: {data.filename}")

        return {
            "status": "success",
            "message": f"Restored from {data.filename}. Previous .env backed up as {current_backup}",
            "restored_from": data.filename,
            "previous_backup": current_backup,
        }

    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore backup: {str(e)}",
        )


@router.delete("/backups/{filename}")
async def delete_backup(
    filename: str,
    _=Depends(get_current_user),
):
    """Delete a specific .env backup file."""
    backup_dir = get_backup_dir()
    backup_path = backup_dir / filename

    # Validate filename format for security
    if not filename.startswith(".env_backup_") or "/" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid backup filename",
        )

    if not backup_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {filename}",
        )

    try:
        backup_path.unlink()
        logger.info(f"Deleted .env backup: {filename}")

        return {
            "status": "success",
            "message": f"Backup {filename} deleted",
        }

    except Exception as e:
        logger.error(f"Failed to delete backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete backup: {str(e)}",
        )


@router.get("/affected-containers/{variable}")
async def get_variable_affected_containers(
    variable: str,
    _=Depends(get_current_user),
) -> AffectedContainersResponse:
    """Get list of containers that would be affected by changing a variable."""
    env_vars = parse_env_file()
    affected = get_affected_containers(variable, env_vars)

    # Build display name mapping
    display_names = {}
    for container in affected:
        # Create friendly display name
        display_names[container] = container.replace("n8n_", "").replace("_", " ").title()

    return AffectedContainersResponse(
        variable=variable,
        affected_containers=affected,
        container_display_names=display_names,
    )


@router.post("/restart-containers")
async def restart_containers(
    data: ContainerRestartRequest,
    _=Depends(get_current_user),
):
    """Restart specified containers to apply environment changes."""
    try:
        import docker
        client = docker.from_env()

        results = {}
        errors = []

        for container_name in data.containers:
            try:
                container = client.containers.get(container_name)
                container.restart(timeout=30)
                results[container_name] = "restarted"
                logger.info(f"Restarted container: {container_name}")
            except docker.errors.NotFound:
                results[container_name] = "not_found"
                errors.append(f"Container not found: {container_name}")
            except Exception as e:
                results[container_name] = f"error: {str(e)}"
                errors.append(f"Failed to restart {container_name}: {str(e)}")

        success_count = sum(1 for r in results.values() if r == "restarted")

        return {
            "status": "success" if not errors else "partial",
            "message": f"Restarted {success_count} of {len(data.containers)} containers",
            "results": results,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"Failed to restart containers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart containers: {str(e)}",
        )


@router.get("/all-affected-containers")
async def get_all_affected_containers(_=Depends(get_current_user)):
    """Get mapping of all variables to their affected containers."""
    env_vars = parse_env_file()

    result = {}
    for var_name in ENV_VAR_TO_CONTAINERS.keys():
        affected = get_affected_containers(var_name, env_vars)
        if affected:
            result[var_name] = affected

    return {"mapping": result}
