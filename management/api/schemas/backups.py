"""
Backup system schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


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
    timezone: str = "UTC"
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
    verification_status: str
    verification_date: Optional[datetime] = None
    retention_category: Optional[str] = None
    expires_at: Optional[datetime] = None
    postgres_version: Optional[str] = None
    database_name: Optional[str] = None
    table_count: Optional[int] = None
    row_counts: Optional[Dict[str, int]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BackupRunRequest(BaseModel):
    """Manual backup run request."""
    backup_type: BackupType
    compression: BackupCompression = BackupCompression.GZIP


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
