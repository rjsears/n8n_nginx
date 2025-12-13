"""
Settings and configuration schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime


class SettingValue(BaseModel):
    """Individual setting value."""
    key: str
    value: Any
    category: str = "general"
    description: Optional[str] = None
    is_secret: bool = False
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SettingUpdate(BaseModel):
    """Update a setting."""
    value: Any
    description: Optional[str] = None


class SettingsByCategoryResponse(BaseModel):
    """Settings grouped by category."""
    category: str
    settings: List[SettingValue]


class SystemConfigResponse(BaseModel):
    """System configuration response."""
    id: int
    config_type: str
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    """Update system configuration."""
    config: Dict[str, Any]


class NFSConfigUpdate(BaseModel):
    """NFS configuration update."""
    enabled: bool = True
    server: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    mount_point: str = "/mnt/backups"
    mount_options: str = "rw,nolock,soft,timeo=30"


class NFSStatusResponse(BaseModel):
    """NFS status response."""
    status: str  # 'connected', 'disconnected', 'error', 'disabled'
    message: str
    server: Optional[str] = None
    path: Optional[str] = None
    mount_point: Optional[str] = None
    is_mounted: bool = False
    last_check: Optional[datetime] = None


class SecurityConfigUpdate(BaseModel):
    """Security configuration update."""
    session_expire_hours: int = Field(default=24, ge=1, le=168)
    max_failed_attempts: int = Field(default=5, ge=1, le=20)
    lockout_minutes: int = Field(default=30, ge=5, le=1440)
    require_subnet_restriction: bool = False


class GeneralConfigUpdate(BaseModel):
    """General configuration update."""
    timezone: str = "America/Los_Angeles"
    backup_compression: str = Field(default="gzip", pattern="^(none|gzip|zstd)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")


class EnvVariableUpdate(BaseModel):
    """Update an environment variable in the .env file."""
    key: str = Field(..., min_length=1, description="Environment variable name")
    value: str = Field(..., description="Environment variable value")


class EnvVariableResponse(BaseModel):
    """Response for environment variable operations."""
    key: str
    is_set: bool
    masked_value: Optional[str] = None
    requires_restart: bool = False
    affected_containers: List[str] = []


class DebugModeUpdate(BaseModel):
    """Update debug mode setting."""
    enabled: bool = Field(..., description="Enable or disable debug mode")


class DebugModeResponse(BaseModel):
    """Debug mode status response."""
    enabled: bool
    log_level: str


class ContainerRestartRequest(BaseModel):
    """Request to restart a container."""
    container_name: str = Field(..., min_length=1)
    reason: Optional[str] = None


class ContainerRestartResponse(BaseModel):
    """Response for container restart operation."""
    success: bool
    message: str
    container_name: str
