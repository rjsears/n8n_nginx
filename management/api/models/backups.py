"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/models/backups.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

from api.database import Base


class BackupSchedule(Base):
    """Backup schedule configuration."""

    __tablename__ = "backup_schedules"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    backup_type = Column(String(50), nullable=False)  # 'postgres_full', 'postgres_n8n', 'n8n_config', 'flows'
    enabled = Column(Boolean, default=True)

    # Schedule timing
    frequency = Column(String(20), nullable=False)  # 'hourly', 'daily', 'weekly', 'monthly'
    hour = Column(Integer, nullable=True)
    minute = Column(Integer, default=0)
    day_of_week = Column(Integer, nullable=True)  # 0=Monday
    day_of_month = Column(Integer, nullable=True)
    timezone = Column(String(50), default="UTC")

    # Compression
    compression = Column(String(20), default="gzip")  # 'none', 'gzip', 'zstd'

    # APScheduler integration
    apscheduler_job_id = Column(String(200), nullable=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    history = relationship("BackupHistory", back_populates="schedule")

    __table_args__ = (
        CheckConstraint("hour >= 0 AND hour <= 23", name="check_hour_range"),
        CheckConstraint("minute >= 0 AND minute <= 59", name="check_minute_range"),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="check_dow_range"),
        CheckConstraint("day_of_month >= 1 AND day_of_month <= 28", name="check_dom_range"),
    )

    def __repr__(self):
        return f"<BackupSchedule(id={self.id}, name='{self.name}', type='{self.backup_type}')>"


class RetentionPolicy(Base):
    """Backup retention policy per backup type."""

    __tablename__ = "retention_policies"

    id = Column(Integer, primary_key=True)
    backup_type = Column(String(50), unique=True, nullable=False)

    # Keep counts
    keep_hourly = Column(Integer, default=24)
    keep_daily = Column(Integer, default=7)
    keep_weekly = Column(Integer, default=4)
    keep_monthly = Column(Integer, default=12)

    # Optional storage limit
    max_total_size_gb = Column(Integer, nullable=True)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<RetentionPolicy(backup_type='{self.backup_type}')>"


class BackupHistory(Base):
    """History of backup operations."""

    __tablename__ = "backup_history"

    id = Column(Integer, primary_key=True)
    backup_type = Column(String(50), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("backup_schedules.id", ondelete="SET NULL"), nullable=True)

    # File info
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    storage_location = Column(String(50), default="local")  # 'local', 'nfs'
    file_size = Column(BigInteger, nullable=True)
    compressed_size = Column(BigInteger, nullable=True)
    compression = Column(String(20), nullable=True)

    # Integrity
    checksum = Column(String(64), nullable=True)  # SHA-256
    checksum_algorithm = Column(String(20), default="sha256")

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Status
    status = Column(String(20), nullable=False, index=True)  # 'running', 'success', 'failed', 'partial'
    error_message = Column(Text, nullable=True)

    # Progress tracking (0-100)
    progress = Column(Integer, default=0)
    progress_message = Column(String(200), nullable=True)

    # Verification
    verification_status = Column(String(20), default="pending")  # 'pending', 'passed', 'failed', 'skipped'
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verification_details = Column(JSONB, nullable=True)

    # Retention
    retention_category = Column(String(20), nullable=True)  # 'hourly', 'daily', 'weekly', 'monthly'
    expires_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(50), nullable=True)  # 'retention_policy', 'manual', 'storage_limit'

    # Protection and pending deletion (Phase 7)
    is_protected = Column(Boolean, default=False)  # Protected from automatic deletion
    protected_at = Column(DateTime(timezone=True), nullable=True)
    protected_reason = Column(String(200), nullable=True)  # User-provided reason for protection
    deletion_status = Column(String(20), nullable=True)  # 'pending', 'cancelled', None
    scheduled_deletion_at = Column(DateTime(timezone=True), nullable=True)
    deletion_reason = Column(String(100), nullable=True)  # 'time_based', 'space_based', 'size_based'

    # Database metadata
    postgres_version = Column(String(20), nullable=True)
    database_name = Column(String(100), nullable=True)
    table_count = Column(Integer, nullable=True)
    row_counts = Column(JSONB, nullable=True)  # {"workflow": 150, "credentials": 25, ...}

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    # Relationships
    schedule = relationship("BackupSchedule", back_populates="history")
    contents = relationship("BackupContents", back_populates="backup", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_backup_history_type", "backup_type"),
        Index("idx_backup_history_status", "status"),
        Index("idx_backup_history_created_at", "created_at"),
        Index("idx_backup_history_expires_at", "expires_at", postgresql_where="deleted_at IS NULL"),
    )

    def __repr__(self):
        return f"<BackupHistory(id={self.id}, type='{self.backup_type}', status='{self.status}')>"


class VerificationSchedule(Base):
    """Schedule for automatic backup verification."""

    __tablename__ = "verification_schedule"

    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=True)
    frequency = Column(String(20), nullable=False, default="weekly")  # 'daily', 'weekly', 'monthly'
    day_of_week = Column(Integer, default=0)  # 0=Monday
    hour = Column(Integer, default=3)  # 3 AM
    verify_latest_count = Column(Integer, default=5)  # Verify N most recent backups

    # APScheduler integration
    apscheduler_job_id = Column(String(200), nullable=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<VerificationSchedule(id={self.id}, frequency='{self.frequency}')>"


class MigrationState(Base):
    """Track v2 to v3 migration state."""

    __tablename__ = "migration_state"

    id = Column(Integer, primary_key=True)
    version = Column(String(20), nullable=False)
    phase = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # 'pending', 'in_progress', 'completed', 'failed', 'rolled_back'
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    pre_migration_backup_id = Column(Integer, ForeignKey("backup_history.id"), nullable=True)
    details = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    rollback_available = Column(Boolean, default=True)
    rollback_expires = Column(DateTime(timezone=True), nullable=True)  # 30 days after migration

    def __repr__(self):
        return f"<MigrationState(id={self.id}, version='{self.version}', status='{self.status}')>"


class APSchedulerJob(Base):
    """APScheduler job store table."""

    __tablename__ = "apscheduler_jobs"

    id = Column(String(191), primary_key=True)
    next_run_time = Column(BigInteger, nullable=True, index=True)
    job_state = Column(Text, nullable=False)  # Pickled job state as base64

    def __repr__(self):
        return f"<APSchedulerJob(id='{self.id}')>"


class BackupContents(Base):
    """
    Stores metadata for each backup for browsing without loading.
    This enables instant viewing of backup contents (workflows, config files, etc.)
    without having to extract or restore the backup.
    """

    __tablename__ = "backup_contents"

    id = Column(Integer, primary_key=True)
    backup_id = Column(Integer, ForeignKey("backup_history.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Quick lookup counts
    workflow_count = Column(Integer, default=0)
    credential_count = Column(Integer, default=0)
    config_file_count = Column(Integer, default=0)

    # JSON manifests for detailed contents
    # workflows_manifest: [{id, name, active, created_at, updated_at, checksum, tags}, ...]
    workflows_manifest = Column(JSONB, nullable=True)
    # credentials_manifest: [{id, name, type}, ...] (no sensitive data!)
    credentials_manifest = Column(JSONB, nullable=True)
    # config_files_manifest: [{name, path, size, checksum, modified_at}, ...]
    config_files_manifest = Column(JSONB, nullable=True)
    # database_schema_manifest: [{database, tables: [{name, row_count, columns}]}, ...]
    database_schema_manifest = Column(JSONB, nullable=True)

    # Verification checksums for integrity validation
    # {workflow_id: checksum, ...}
    verification_checksums = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationship
    backup = relationship("BackupHistory", back_populates="contents")

    __table_args__ = (
        Index("idx_backup_contents_backup_id", "backup_id"),
    )

    def __repr__(self):
        return f"<BackupContents(id={self.id}, backup_id={self.backup_id}, workflows={self.workflow_count})>"


class BackupPruningSettings(Base):
    """
    Settings for automatic backup pruning and retention.
    Single row table (singleton pattern).
    """

    __tablename__ = "backup_pruning_settings"

    id = Column(Integer, primary_key=True)

    # Time-based pruning
    time_based_enabled = Column(Boolean, default=False)
    max_age_days = Column(Integer, default=90)  # Delete backups older than X days

    # Space-based pruning
    space_based_enabled = Column(Boolean, default=False)
    min_free_space_percent = Column(Integer, default=10)  # Trigger when free space below X%

    # Size-based pruning
    size_based_enabled = Column(Boolean, default=False)
    max_total_size_gb = Column(Integer, default=100)  # Keep total backup size under X GB

    # Pre-deletion notifications
    notify_before_delete = Column(Boolean, default=True)
    notify_hours_before = Column(Integer, default=24)  # Hours before deletion to notify
    notification_channel_id = Column(Integer, nullable=True)  # FK to notification service (optional)

    # Critical space handling
    critical_space_threshold = Column(Integer, default=5)  # Critical when below X%
    critical_space_action = Column(String(50), default="delete_oldest")  # 'delete_oldest' or 'stop_and_alert'
    critical_notification_channel_id = Column(Integer, nullable=True)  # Emergency notification channel

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<BackupPruningSettings(id={self.id})>"


class BackupConfiguration(Base):
    """
    Comprehensive backup configuration settings.
    Single row table (singleton pattern).
    """

    __tablename__ = "backup_configuration"

    id = Column(Integer, primary_key=True)

    # Storage Settings
    primary_storage_path = Column(String(500), default="/app/backups")
    nfs_storage_path = Column(String(500), nullable=True)
    nfs_enabled = Column(Boolean, default=False)
    storage_preference = Column(String(20), default="local")  # 'local', 'nfs', 'both'
    backup_workflow = Column(String(20), default="direct")  # 'direct', 'stage_then_copy'

    # Compression Settings
    compression_enabled = Column(Boolean, default=True)
    compression_algorithm = Column(String(20), default="gzip")  # 'gzip', 'zstd', 'none'
    compression_level = Column(Integer, default=6)  # 1-9 for gzip, 1-22 for zstd

    # Retention Settings - Tiered GFS (Grandfather-Father-Son) strategy
    retention_enabled = Column(Boolean, default=True)
    # Keep daily backups for X days (default: 7 days = last week of dailies)
    retention_daily_count = Column(Integer, default=7)
    # Keep weekly backups for X weeks (default: 4 weeks = ~1 month of weeklies)
    retention_weekly_count = Column(Integer, default=4)
    # Keep monthly backups for X months (default: 6 months of monthlies)
    retention_monthly_count = Column(Integer, default=6)
    # Minimum backups to always keep regardless of age (safety net)
    retention_min_count = Column(Integer, default=3)

    # NOTE: Schedule settings are managed via the BackupSchedule table.
    # Use the /api/backups/schedules endpoints for schedule management.

    # Backup Type Settings
    default_backup_type = Column(String(50), default="postgres_full")
    include_n8n_config = Column(Boolean, default=True)
    include_ssl_certs = Column(Boolean, default=True)
    include_env_files = Column(Boolean, default=True)

    # Notification Settings
    notify_on_success = Column(Boolean, default=False)
    notify_on_failure = Column(Boolean, default=True)
    notification_channel_id = Column(Integer, nullable=True)

    # Verification Settings
    auto_verify_enabled = Column(Boolean, default=False)
    verify_after_backup = Column(Boolean, default=False)
    # Verify every Nth backup (1 = every backup, 5 = every 5th backup, etc.)
    verify_frequency = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<BackupConfiguration(id={self.id})>"
