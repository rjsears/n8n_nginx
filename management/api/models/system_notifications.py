"""
System Notification models for event-based alerting with advanced features:
- Configurable event types with severity, frequency, thresholds
- Rate limiting with cooldown and flapping detection
- L1/L2 escalation support
- Per-container monitoring configuration
- Global settings (maintenance mode, quiet hours, digest)
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

from api.database import Base


class SystemNotificationEvent(Base):
    """
    Configuration for each system notification event type.
    Examples: backup_success, container_unhealthy, disk_space_low
    """

    __tablename__ = "system_notification_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)  # Heroicon name for UI
    category = Column(String(50), nullable=False)  # 'backup', 'container', 'system', 'security'

    # Enable/disable this event type
    enabled = Column(Boolean, default=True)

    # Severity level (affects ntfy priority)
    severity = Column(String(20), default='warning')  # 'info', 'warning', 'critical'

    # Frequency settings
    # Options: 'every_time', 'once_per_15m', 'once_per_30m', 'once_per_hour',
    #          'once_per_4h', 'once_per_12h', 'once_per_day', 'once_per_week'
    frequency = Column(String(30), default='every_time')

    # Rate limiting for "every_time" events
    cooldown_minutes = Column(Integer, default=5)

    # Flapping detection settings
    flapping_enabled = Column(Boolean, default=True)
    flapping_threshold_count = Column(Integer, default=3)  # Events in window to trigger flapping
    flapping_threshold_minutes = Column(Integer, default=10)  # Window size
    flapping_summary_interval = Column(Integer, default=15)  # Minutes between summary notifications
    notify_on_recovery = Column(Boolean, default=True)  # Send notification when stable again

    # Thresholds (JSON for flexibility based on event type)
    # Examples: {"percent": 90}, {"days": 14}, {"duration_minutes": 5}
    thresholds = Column(JSONB, nullable=True)

    # Escalation settings
    escalation_enabled = Column(Boolean, default=False)
    escalation_timeout_minutes = Column(Integer, default=30)

    # Daily digest inclusion
    include_in_digest = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    targets = relationship("SystemNotificationTarget", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SystemNotificationEvent(event_type='{self.event_type}', enabled={self.enabled})>"


class SystemNotificationTarget(Base):
    """
    Maps events to notification channels/groups.
    Supports L1 (primary) and L2 (escalation) levels.
    """

    __tablename__ = "system_notification_targets"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("system_notification_events.id", ondelete="CASCADE"), nullable=False, index=True)

    # Target can be a channel or group
    target_type = Column(String(20), nullable=False)  # 'channel', 'group'
    channel_id = Column(Integer, ForeignKey("notification_services.id", ondelete="CASCADE"), nullable=True)
    group_id = Column(Integer, ForeignKey("notification_groups.id", ondelete="CASCADE"), nullable=True)

    # Escalation level: 1 = primary (L1), 2 = escalation (L2)
    escalation_level = Column(Integer, default=1)

    # Per-target escalation timeout (for L2 targets)
    # If set, overrides the event's default escalation_timeout_minutes
    escalation_timeout_minutes = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    event = relationship("SystemNotificationEvent", back_populates="targets")
    channel = relationship("NotificationService", foreign_keys=[channel_id])
    group = relationship("NotificationGroup", foreign_keys=[group_id])

    __table_args__ = (
        Index("idx_system_notification_targets_event_id", "event_id"),
    )

    def __repr__(self):
        target = f"channel:{self.channel_id}" if self.target_type == 'channel' else f"group:{self.group_id}"
        return f"<SystemNotificationTarget(event_id={self.event_id}, {target}, level={self.escalation_level})>"


class SystemNotificationContainerConfig(Base):
    """
    Per-container monitoring configuration.
    Allows enabling/disabling monitoring and custom channel overrides for specific containers.
    """

    __tablename__ = "system_notification_container_configs"

    id = Column(Integer, primary_key=True)
    container_name = Column(String(100), nullable=False, unique=True, index=True)

    # Which events to monitor for this container
    monitor_unhealthy = Column(Boolean, default=True)
    monitor_restart = Column(Boolean, default=True)
    monitor_stopped = Column(Boolean, default=True)

    # Custom targets override (optional, JSON array of {type, id} objects)
    # If null, uses default targets from the event configuration
    # Example: [{"type": "channel", "id": 1}, {"type": "group", "id": 2}]
    custom_targets = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<SystemNotificationContainerConfig(container='{self.container_name}', unhealthy={self.monitor_unhealthy}, restart={self.monitor_restart}, stopped={self.monitor_stopped})>"


class SystemNotificationState(Base):
    """
    Runtime state tracking for notifications.
    Used for cooldown enforcement and flapping detection.
    """

    __tablename__ = "system_notification_state"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False, index=True)
    target_id = Column(String(100), nullable=True)  # e.g., container name for per-target tracking

    # Cooldown tracking
    last_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Flapping detection
    event_count_in_window = Column(Integer, default=0)
    window_start = Column(DateTime(timezone=True), nullable=True)
    is_flapping = Column(Boolean, default=False)
    flapping_started_at = Column(DateTime(timezone=True), nullable=True)
    last_summary_at = Column(DateTime(timezone=True), nullable=True)

    # Escalation tracking
    escalation_triggered_at = Column(DateTime(timezone=True), nullable=True)
    escalation_sent = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint('event_type', 'target_id', name='uq_event_target'),
        Index("idx_system_notification_state_event_type", "event_type"),
        Index("idx_system_notification_state_target_id", "target_id"),
    )

    def __repr__(self):
        return f"<SystemNotificationState(event='{self.event_type}', target='{self.target_id}', flapping={self.is_flapping})>"


class SystemNotificationGlobalSettings(Base):
    """
    Global settings for the notification system.
    Only one row should exist (singleton pattern).
    """

    __tablename__ = "system_notification_global_settings"

    id = Column(Integer, primary_key=True)

    # Maintenance mode - quick mute all notifications
    maintenance_mode = Column(Boolean, default=False)
    maintenance_until = Column(DateTime(timezone=True), nullable=True)
    maintenance_reason = Column(String(255), nullable=True)

    # Quiet hours - reduce priority instead of muting
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(5), default="22:00")  # HH:MM format
    quiet_hours_end = Column(String(5), default="07:00")
    quiet_hours_reduce_priority = Column(Boolean, default=True)  # True = reduce priority, False = mute

    # Blackout hours - full mute during specified time
    blackout_enabled = Column(Boolean, default=False)
    blackout_start = Column(String(5), nullable=True)
    blackout_end = Column(String(5), nullable=True)

    # Global rate limit protection
    max_notifications_per_hour = Column(Integer, default=50)
    notifications_this_hour = Column(Integer, default=0)
    hour_started_at = Column(DateTime(timezone=True), nullable=True)
    emergency_contact_id = Column(Integer, ForeignKey("notification_services.id", ondelete="SET NULL"), nullable=True)

    # Daily digest settings
    digest_enabled = Column(Boolean, default=False)
    digest_time = Column(String(5), default="08:00")  # When to send digest (HH:MM)
    digest_severity_levels = Column(JSONB, default=["info"])  # Which severity levels to batch
    last_digest_sent = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    emergency_contact = relationship("NotificationService", foreign_keys=[emergency_contact_id])

    def __repr__(self):
        return f"<SystemNotificationGlobalSettings(maintenance={self.maintenance_mode}, quiet_hours={self.quiet_hours_enabled})>"


class SystemNotificationHistory(Base):
    """
    History of system notifications sent.
    Extends the general NotificationHistory with system-specific fields.
    """

    __tablename__ = "system_notification_history"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("system_notification_events.id", ondelete="SET NULL"), nullable=True)

    # Target information
    target_id = Column(String(100), nullable=True)  # e.g., container name
    target_label = Column(String(255), nullable=True)  # Human-readable label

    # Event details
    severity = Column(String(20), nullable=True)
    event_data = Column(JSONB, nullable=True)  # Full event payload

    # Delivery information
    channels_sent = Column(JSONB, nullable=True)  # List of channels/groups notified
    escalation_level = Column(Integer, default=1)

    # Status
    status = Column(String(20), nullable=False, default='sent')  # 'sent', 'failed', 'suppressed', 'batched'
    suppression_reason = Column(String(100), nullable=True)  # 'cooldown', 'flapping', 'maintenance', etc.
    error_message = Column(Text, nullable=True)

    # Timestamps
    triggered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    event = relationship("SystemNotificationEvent")

    __table_args__ = (
        Index("idx_system_notification_history_event_type", "event_type"),
        Index("idx_system_notification_history_triggered_at", "triggered_at"),
        Index("idx_system_notification_history_status", "status"),
    )

    def __repr__(self):
        return f"<SystemNotificationHistory(event='{self.event_type}', target='{self.target_id}', status='{self.status}')>"


# Default event configurations to seed on first run
DEFAULT_SYSTEM_EVENTS = [
    {
        "event_type": "backup_success",
        "display_name": "Backup Success",
        "description": "Notification when a backup completes successfully",
        "icon": "CheckCircleIcon",
        "category": "backup",
        "severity": "info",
        "frequency": "every_time",
        "cooldown_minutes": 0,
        "flapping_enabled": False,
        "include_in_digest": True,
    },
    {
        "event_type": "backup_failure",
        "display_name": "Backup Failure",
        "description": "Notification when a backup fails",
        "icon": "XCircleIcon",
        "category": "backup",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 60,
        "flapping_enabled": True,
        "flapping_threshold_count": 2,
        "flapping_threshold_minutes": 120,
    },
    {
        "event_type": "disk_space_low",
        "display_name": "Disk Space Low",
        "description": "Notification when disk usage exceeds threshold. Configure the percentage threshold (default: 90% used).",
        "icon": "CircleStackIcon",
        "category": "system",
        "severity": "warning",
        "frequency": "once_per_4h",
        "thresholds": {"percent": 90},
    },
    {
        "event_type": "container_unhealthy",
        "display_name": "Container Unhealthy",
        "description": "Notification when a container health check fails",
        "icon": "HeartIcon",
        "category": "container",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 15,
        "flapping_enabled": True,
        "flapping_threshold_count": 3,
        "flapping_threshold_minutes": 15,
    },
    {
        "event_type": "container_restart",
        "display_name": "Container Restart",
        "description": "Notification when a container restarts",
        "icon": "ArrowPathIcon",
        "category": "container",
        "severity": "warning",
        "frequency": "every_time",
        "cooldown_minutes": 5,
        "flapping_enabled": True,
        "flapping_threshold_count": 3,
        "flapping_threshold_minutes": 10,
        "flapping_summary_interval": 15,
    },
    {
        "event_type": "container_stopped",
        "display_name": "Container Stopped",
        "description": "Notification when a container stops or exits unexpectedly",
        "icon": "XCircleIcon",
        "category": "container",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 5,
        "flapping_enabled": True,
        "flapping_threshold_count": 2,
        "flapping_threshold_minutes": 15,
    },
    {
        "event_type": "high_memory",
        "display_name": "High Memory Usage",
        "description": "Notification when system memory usage exceeds threshold. Configure the percentage threshold (default: 90%).",
        "icon": "CpuChipIcon",
        "category": "system",
        "severity": "warning",
        "frequency": "once_per_hour",
        "thresholds": {"percent": 90},
    },
    {
        "event_type": "high_cpu",
        "display_name": "High CPU Usage",
        "description": "Notification when CPU usage is sustained above threshold. Configure percentage and duration (default: 90% for 5 minutes).",
        "icon": "FireIcon",
        "category": "system",
        "severity": "warning",
        "frequency": "once_per_hour",
        "thresholds": {"percent": 90, "duration_minutes": 5},
    },
    {
        "event_type": "certificate_expiring",
        "display_name": "Certificate Expiring",
        "description": "Notification when SSL certificates are about to expire. Only applies if using Let's Encrypt/certbot. Configure days before expiration (default: 14 days).",
        "icon": "ShieldCheckIcon",
        "category": "ssl",
        "severity": "warning",
        "frequency": "once_per_day",
        "thresholds": {"days": 14},
    },
    {
        "event_type": "security_event",
        "display_name": "Security Event",
        "description": "Notification for security-related events like failed logins",
        "icon": "ShieldExclamationIcon",
        "category": "security",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 1,
        "flapping_enabled": True,
        "flapping_threshold_count": 5,
        "flapping_threshold_minutes": 5,
    },
    {
        "event_type": "update_available",
        "display_name": "Update Available",
        "description": "Notification when software updates are available",
        "icon": "ArrowDownTrayIcon",
        "category": "system",
        "severity": "info",
        "frequency": "once_per_day",
        "include_in_digest": True,
    },
    # Additional backup events
    {
        "event_type": "backup_started",
        "display_name": "Backup Started",
        "description": "Notification when a backup begins",
        "icon": "PlayIcon",
        "category": "backup",
        "severity": "info",
        "frequency": "every_time",
        "cooldown_minutes": 0,
        "flapping_enabled": False,
    },
    {
        "event_type": "backup_pending_deletion",
        "display_name": "Backup Pending Deletion",
        "description": "Notification when backups are scheduled for deletion due to retention policy. Retention rules are configured in Backup Settings → Pruning.",
        "icon": "TrashIcon",
        "category": "backup",
        "severity": "warning",
        "frequency": "every_time",
        "cooldown_minutes": 60,
        "flapping_enabled": False,
    },
    {
        "event_type": "backup_critical_space",
        "display_name": "Backup Critical Space",
        "description": "Emergency notification when disk space is critically low for backups. Threshold is configured in Backup Settings → Pruning (default: 5% free space).",
        "icon": "ExclamationTriangleIcon",
        "category": "backup",
        "severity": "critical",
        "frequency": "every_time",
        "cooldown_minutes": 30,
        "flapping_enabled": False,
    },
    # Additional container events
    {
        "event_type": "container_started",
        "display_name": "Container Started",
        "description": "Notification when a container starts",
        "icon": "PlayCircleIcon",
        "category": "container",
        "severity": "info",
        "frequency": "every_time",
        "cooldown_minutes": 0,
        "flapping_enabled": False,
    },
    {
        "event_type": "container_removed",
        "display_name": "Container Removed",
        "description": "Notification when a container is removed",
        "icon": "TrashIcon",
        "category": "container",
        "severity": "warning",
        "frequency": "every_time",
        "cooldown_minutes": 0,
        "flapping_enabled": False,
    },
]
