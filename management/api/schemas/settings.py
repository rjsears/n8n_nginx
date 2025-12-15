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


# Access Control schemas
class IPRange(BaseModel):
    """IP range configuration."""
    cidr: str = Field(..., min_length=1, description="CIDR notation (e.g., 192.168.1.0/24)")
    description: str = Field(default="", description="Description of the IP range")
    access_level: str = Field(default="internal", pattern="^(internal|external)$")
    protected: bool = Field(default=False, description="If true, this range cannot be deleted")


class AccessControlConfig(BaseModel):
    """Access control configuration."""
    enabled: bool = True
    ip_ranges: List[IPRange] = []


class AccessControlResponse(BaseModel):
    """Access control configuration response."""
    enabled: bool
    ip_ranges: List[IPRange]
    nginx_config_path: str
    last_updated: Optional[datetime] = None


class AddIPRangeRequest(BaseModel):
    """Request to add an IP range."""
    cidr: str = Field(..., min_length=1, description="CIDR notation (e.g., 192.168.1.0/24)")
    description: str = Field(default="", description="Description of the IP range")
    access_level: str = Field(default="internal", pattern="^(internal|external)$")


class UpdateIPRangeRequest(BaseModel):
    """Request to update an IP range's description."""
    description: str = Field(..., description="New description for the IP range")


# External Routes schemas
class ExternalRoute(BaseModel):
    """A route configured in nginx with access status."""
    path: str = Field(..., min_length=1, description="URL path (e.g., /webhook/)")
    description: str = Field(default="", description="Description of what this route is for")
    is_public: bool = Field(default=False, description="True if publicly accessible (no IP/auth check)")
    has_auth: bool = Field(default=False, description="True if requires SSO authentication")
    proxy_target: str = Field(default="n8n", description="Upstream target (e.g., n8n, n8n_portainer)")
    proxy_port: Optional[int] = Field(default=None, description="Upstream port if specified in proxy_pass URL")
    icon: str = Field(default="link", description="Icon name for UI display")
    color: str = Field(default="gray", description="Color theme for UI display")
    protected: bool = Field(default=False, description="If true, this route cannot be removed")
    manageable: bool = Field(default=False, description="If true, can be added/removed via UI")


class ExternalRoutesResponse(BaseModel):
    """Response containing all external routes."""
    routes: List[ExternalRoute]
    domain: Optional[str] = None
    last_updated: Optional[datetime] = None


class AddExternalRouteRequest(BaseModel):
    """Request to add a new external route."""
    path: str = Field(..., min_length=1, description="URL path (e.g., /ntfy/, /webhook-custom/)")
    description: str = Field(default="", description="Description of what this route is for")
    upstream: str = Field(default="n8n", description="Upstream server name (e.g., n8n, n8n_ntfy)")
    upstream_port: Optional[int] = Field(default=None, description="Upstream server port (e.g., 8085). If None, uses upstream name only.")
    is_public: bool = Field(default=True, description="If true, route is publicly accessible. If false, requires IP restriction ($is_trusted check).")
