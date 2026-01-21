"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/schemas/backups.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


def _get_default_timezone() -> str:
    """Get the default timezone from settings."""
    from api.config import settings
    return settings.timezone


class BackupType(str, Enum):
    """Backup types."""
    POSTGRES_FULL = "postgres_full"
    POSTGRES_N8N = "postgres_n8n"
    POSTGRES_MGMT = "postgres_mgmt"
    N8N_CONFIG = "n8n_config"
    FLOWS = "flows"


class BackupFrequency(str, Enum):
    """Backup schedule frequencies."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BackupCompression(str, Enum):
    """Backup compression types."""
    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"


class BackupScheduleCreate(BaseModel):
    """Create backup schedule."""
    name: str = Field(..., min_length=1, max_length=100)
    backup_type: BackupType
    enabled: bool = True
    frequency: BackupFrequency
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)  # 0=Monday
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    timezone: str = Field(default_factory=_get_default_timezone)
    compression: BackupCompression = BackupCompression.GZIP


class BackupScheduleUpdate(BaseModel):
    """Update backup schedule."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    frequency: Optional[BackupFrequency] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    timezone: Optional[str] = None
    compression: Optional[BackupCompression] = None


class BackupScheduleResponse(BaseModel):
    """Backup schedule response."""
    id: int
    name: str
    backup_type: str
    enabled: bool
    frequency: str
    hour: Optional[int] = None
    minute: int
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    timezone: str
    compression: str
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RetentionPolicyUpdate(BaseModel):
    """Update retention policy."""
    keep_hourly: int = Field(default=24, ge=0, le=168)
    keep_daily: int = Field(default=7, ge=0, le=90)
    keep_weekly: int = Field(default=4, ge=0, le=52)
    keep_monthly: int = Field(default=12, ge=0, le=60)
    max_total_size_gb: Optional[int] = Field(None, ge=1)


class RetentionPolicyResponse(BaseModel):
    """Retention policy response."""
    id: int
    backup_type: str
    keep_hourly: int
    keep_daily: int
    keep_weekly: int
    keep_monthly: int
    max_total_size_gb: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class BackupHistoryResponse(BaseModel):
    """Backup history response."""
    id: int
    backup_type: str
    schedule_id: Optional[int] = None
    filename: str
    filepath: str
    storage_location: str
    file_size: Optional[int] = None
    compressed_size: Optional[int] = None
    compression: Optional[str] = None
    checksum: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    progress: Optional[int] = 0
    progress_message: Optional[str] = None
    verification_status: str
    verification_date: Optional[datetime] = None
    verification_details: Optional[Dict[str, Any]] = None
    retention_category: Optional[str] = None
    expires_at: Optional[datetime] = None
    postgres_version: Optional[str] = None
    database_name: Optional[str] = None
    table_count: Optional[int] = None
    row_counts: Optional[Dict[str, Any]] = None  # {db_name: {table_name: row_count}}
    created_at: datetime

    class Config:
        from_attributes = True


class BackupRunRequest(BaseModel):
    """Manual backup run request."""
    backup_type: BackupType
    compression: BackupCompression = BackupCompression.GZIP
    skip_auto_verify: bool = False  # If True, skip auto-verification even if system-wide enabled


class BackupRunResponse(BaseModel):
    """Backup run response."""
    backup_id: int
    status: str
    message: str


class VerificationScheduleUpdate(BaseModel):
    """Update verification schedule."""
    enabled: bool = True
    frequency: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")
    day_of_week: int = Field(default=0, ge=0, le=6)
    hour: int = Field(default=3, ge=0, le=23)
    verify_latest_count: int = Field(default=5, ge=1, le=20)


class VerificationScheduleResponse(BaseModel):
    """Verification schedule response."""
    id: int
    enabled: bool
    frequency: str
    day_of_week: int
    hour: int
    verify_latest_count: int
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class VerificationRunResponse(BaseModel):
    """Verification run response."""
    backup_id: int
    status: str  # 'passed', 'failed', 'skipped'
    details: Optional[Dict[str, Any]] = None


class BackupStatsResponse(BaseModel):
    """Backup statistics."""
    total_backups: int
    successful_backups: int
    failed_backups: int
    total_size_bytes: int
    last_backup: Optional[datetime] = None
    last_successful_backup: Optional[datetime] = None
    by_type: Dict[str, int]
    by_status: Dict[str, int]


# ============================================================================
# Backup Contents Schemas (Phase 1)
# ============================================================================

class WorkflowManifestItem(BaseModel):
    """Individual workflow in backup manifest."""
    id: str
    name: str
    active: bool = False
    archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    checksum: Optional[str] = None
    tags: List[str] = []
    node_count: Optional[int] = None


class CredentialManifestItem(BaseModel):
    """Individual credential in backup manifest (no sensitive data)."""
    id: str
    name: str
    type: str


class ConfigFileManifestItem(BaseModel):
    """Individual config file in backup manifest."""
    name: str
    path: str
    size: int
    checksum: str
    modified_at: Optional[datetime] = None


class DatabaseTableInfo(BaseModel):
    """Database table information."""
    name: str
    row_count: int
    columns: List[str] = []


class DatabaseManifestItem(BaseModel):
    """Database schema manifest."""
    database: str
    tables: List[DatabaseTableInfo]
    total_rows: int = 0


class BackupContentsResponse(BaseModel):
    """Response for backup contents (browsing without loading)."""
    id: int
    backup_id: int
    workflow_count: int
    credential_count: int
    config_file_count: int
    workflows_manifest: Optional[List[WorkflowManifestItem]] = None
    credentials_manifest: Optional[List[CredentialManifestItem]] = None
    config_files_manifest: Optional[List[ConfigFileManifestItem]] = None
    database_schema_manifest: Optional[List[DatabaseManifestItem]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Backup Pruning Schemas (Phase 7)
# ============================================================================

class BackupPruningSettingsUpdate(BaseModel):
    """Update backup pruning settings."""
    # Time-based pruning
    time_based_enabled: Optional[bool] = None
    max_age_days: Optional[int] = Field(None, ge=1, le=365)

    # Space-based pruning
    space_based_enabled: Optional[bool] = None
    min_free_space_percent: Optional[int] = Field(None, ge=1, le=50)

    # Size-based pruning
    size_based_enabled: Optional[bool] = None
    max_total_size_gb: Optional[int] = Field(None, ge=1)

    # Pre-deletion notifications
    notify_before_delete: Optional[bool] = None
    notify_hours_before: Optional[int] = Field(None, ge=1, le=168)  # max 7 days
    notification_channel_id: Optional[int] = None

    # Critical space handling
    critical_space_threshold: Optional[int] = Field(None, ge=1, le=20)
    critical_space_action: Optional[str] = Field(None, pattern="^(delete_oldest|stop_and_alert)$")
    critical_notification_channel_id: Optional[int] = None


class BackupPruningSettingsResponse(BaseModel):
    """Backup pruning settings response."""
    id: int
    time_based_enabled: bool
    max_age_days: int
    space_based_enabled: bool
    min_free_space_percent: int
    size_based_enabled: bool
    max_total_size_gb: int
    notify_before_delete: bool
    notify_hours_before: int
    notification_channel_id: Optional[int] = None
    critical_space_threshold: int
    critical_space_action: str
    critical_notification_channel_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BackupProtectRequest(BaseModel):
    """Request to protect/unprotect a backup."""
    protected: bool
    reason: Optional[str] = Field(None, max_length=200)


class BackupHistoryExtendedResponse(BackupHistoryResponse):
    """Extended backup history response with protection and deletion status."""
    is_protected: bool = False
    protected_at: Optional[datetime] = None
    protected_reason: Optional[str] = None
    deletion_status: Optional[str] = None
    scheduled_deletion_at: Optional[datetime] = None
    deletion_reason: Optional[str] = None

    class Config:
        from_attributes = True


class BackupHistoryPaginatedResponse(BaseModel):
    """Paginated backup history response."""
    items: List[BackupHistoryExtendedResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class BackupHistoryCountResponse(BaseModel):
    """Backup history count response."""
    total: int


# ============================================================================
# Backup Configuration Schemas (Comprehensive Settings)
# ============================================================================

class BackupConfigurationUpdate(BaseModel):
    """Update backup configuration settings."""
    # Storage Settings
    primary_storage_path: Optional[str] = Field(None, max_length=500)
    nfs_storage_path: Optional[str] = Field(None, max_length=500)
    nfs_enabled: Optional[bool] = None
    storage_preference: Optional[str] = Field(None, pattern="^(local|nfs|both)$")
    backup_workflow: Optional[str] = Field(None, pattern="^(direct|stage_then_copy)$")

    # Compression Settings
    compression_enabled: Optional[bool] = None
    compression_algorithm: Optional[str] = Field(None, pattern="^(gzip|zstd|none)$")
    compression_level: Optional[int] = Field(None, ge=1, le=22)

    # Retention Settings - Tiered GFS (Grandfather-Father-Son) strategy
    retention_enabled: Optional[bool] = None
    retention_daily_count: Optional[int] = Field(None, ge=1, le=30)  # Keep daily backups for X days
    retention_weekly_count: Optional[int] = Field(None, ge=1, le=52)  # Keep weekly backups for X weeks
    retention_monthly_count: Optional[int] = Field(None, ge=1, le=24)  # Keep monthly backups for X months
    retention_min_count: Optional[int] = Field(None, ge=1, le=50)  # Safety net minimum

    # NOTE: Schedule settings have been moved to BackupSchedule.
    # Use /api/backups/schedules endpoints for schedule management.

    # Backup Type Settings
    default_backup_type: Optional[str] = None
    include_n8n_config: Optional[bool] = None
    include_ssl_certs: Optional[bool] = None
    include_env_files: Optional[bool] = None
    include_public_website: Optional[bool] = None

    # Notification Settings
    notify_on_success: Optional[bool] = None
    notify_on_failure: Optional[bool] = None
    notification_channel_id: Optional[int] = None

    # Verification Settings
    auto_verify_enabled: Optional[bool] = None
    verify_after_backup: Optional[bool] = None
    verify_frequency: Optional[int] = Field(None, ge=1, le=100)  # Verify every Nth backup


class BackupConfigurationResponse(BaseModel):
    """Backup configuration response."""
    id: int

    # Storage Settings
    primary_storage_path: str = "/app/backups"
    nfs_storage_path: Optional[str] = None
    nfs_enabled: bool = False
    storage_preference: str = "local"
    backup_workflow: Optional[str] = "direct"

    # Compression Settings
    compression_enabled: bool = True
    compression_algorithm: str = "gzip"
    compression_level: int = 6

    # Retention Settings - Tiered GFS (Grandfather-Father-Son) strategy
    retention_enabled: bool = True
    retention_daily_count: Optional[int] = 7
    retention_weekly_count: Optional[int] = 4
    retention_monthly_count: Optional[int] = 6
    retention_min_count: int = 3

    # NOTE: Schedule settings have been moved to BackupSchedule.
    # Use /api/backups/schedules endpoints for schedule management.

    # Backup Type Settings
    default_backup_type: str = "postgres_full"
    include_n8n_config: bool = True
    include_ssl_certs: bool = True
    include_env_files: bool = True
    include_public_website: bool = True

    # Notification Settings
    notify_on_success: bool = False
    notify_on_failure: bool = True
    notification_channel_id: Optional[int] = None

    # Verification Settings
    auto_verify_enabled: bool = False
    verify_after_backup: bool = False
    verify_frequency: Optional[int] = 1  # Verify every Nth backup

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
