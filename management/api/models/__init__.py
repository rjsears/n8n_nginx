"""
SQLAlchemy models for n8n Management System.
"""

from api.models.auth import AdminUser, Session, AllowedSubnet
from api.models.settings import Settings, SystemConfig, EncryptionKey
from api.models.notifications import NotificationService, NotificationRule, NotificationHistory, NotificationBatch
from api.models.backups import BackupSchedule, RetentionPolicy, BackupHistory, VerificationSchedule
from api.models.email import EmailTemplate, EmailTestHistory
from api.models.audit import AuditLog, ContainerStatusCache, SystemMetricsCache
from api.models.ntfy import NtfyTemplate, NtfyTopic, NtfySavedMessage, NtfyMessageHistory, NtfyServerConfig

__all__ = [
    # Auth
    "AdminUser",
    "Session",
    "AllowedSubnet",
    # Settings
    "Settings",
    "SystemConfig",
    "EncryptionKey",
    # Notifications
    "NotificationService",
    "NotificationRule",
    "NotificationHistory",
    "NotificationBatch",
    # Backups
    "BackupSchedule",
    "RetentionPolicy",
    "BackupHistory",
    "VerificationSchedule",
    # Email
    "EmailTemplate",
    "EmailTestHistory",
    # Audit
    "AuditLog",
    "ContainerStatusCache",
    "SystemMetricsCache",
    # NTFY
    "NtfyTemplate",
    "NtfyTopic",
    "NtfySavedMessage",
    "NtfyMessageHistory",
    "NtfyServerConfig",
]
