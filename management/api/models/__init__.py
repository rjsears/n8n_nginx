"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/models/__init__.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from api.models.auth import AdminUser, Session, AllowedSubnet
from api.models.settings import Settings, SystemConfig, EncryptionKey
from api.models.notifications import (
    NotificationService,
    NotificationGroup,
    NotificationGroupMembership,
    NotificationRule,
    NotificationHistory,
    NotificationBatch,
)
from api.models.backups import (
    BackupSchedule,
    RetentionPolicy,
    BackupHistory,
    VerificationSchedule,
    BackupContents,
    BackupPruningSettings,
    BackupConfiguration,
)
from api.models.email import EmailTemplate, EmailTestHistory
from api.models.audit import AuditLog, ContainerStatusCache, SystemMetricsCache
from api.models.ntfy import NtfyTemplate, NtfyTopic, NtfySavedMessage, NtfyMessageHistory, NtfyServerConfig
from api.models.system_notifications import (
    SystemNotificationEvent,
    SystemNotificationTarget,
    SystemNotificationContainerConfig,
    SystemNotificationState,
    SystemNotificationGlobalSettings,
    SystemNotificationHistory,
    DEFAULT_SYSTEM_EVENTS,
)

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
    "NotificationGroup",
    "NotificationGroupMembership",
    "NotificationRule",
    "NotificationHistory",
    "NotificationBatch",
    # System Notifications
    "SystemNotificationEvent",
    "SystemNotificationTarget",
    "SystemNotificationContainerConfig",
    "SystemNotificationState",
    "SystemNotificationGlobalSettings",
    "SystemNotificationHistory",
    "DEFAULT_SYSTEM_EVENTS",
    # Backups
    "BackupSchedule",
    "RetentionPolicy",
    "BackupHistory",
    "VerificationSchedule",
    "BackupContents",
    "BackupPruningSettings",
    "BackupConfiguration",
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
