"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/schemas/__init__.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from api.schemas.common import (
    PaginatedResponse,
    SuccessResponse,
    ErrorResponse,
    HealthResponse,
)
from api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    SessionInfo,
    SubnetCreate,
    SubnetResponse,
    UserInfo,
)
from api.schemas.settings import (
    SettingValue,
    SettingUpdate,
    SystemConfigResponse,
    SystemConfigUpdate,
)
from api.schemas.notifications import (
    NotificationServiceCreate,
    NotificationServiceUpdate,
    NotificationServiceResponse,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationRuleResponse,
    NotificationHistoryResponse,
    NotificationEventType,
)
from api.schemas.backups import (
    BackupScheduleCreate,
    BackupScheduleUpdate,
    BackupScheduleResponse,
    RetentionPolicyUpdate,
    RetentionPolicyResponse,
    BackupHistoryResponse,
    BackupRunRequest,
    VerificationScheduleUpdate,
    VerificationScheduleResponse,
)
from api.schemas.email import (
    EmailConfigUpdate,
    EmailConfigResponse,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTestRequest,
    EmailTestResponse,
)
from api.schemas.system_notifications import (
    EventResponse,
    EventUpdate,
    TargetCreate,
    TargetResponse,
    ContainerConfigCreate,
    ContainerConfigUpdate,
    ContainerConfigResponse,
    GlobalSettingsResponse,
    GlobalSettingsUpdate,
    HistoryResponse as SystemNotificationHistoryResponse,
    HistoryListResponse,
    StateResponse,
    MaintenanceModeRequest,
    TestEventRequest,
)

__all__ = [
    # Common
    "PaginatedResponse",
    "SuccessResponse",
    "ErrorResponse",
    "HealthResponse",
    # Auth
    "LoginRequest",
    "LoginResponse",
    "PasswordChangeRequest",
    "SessionInfo",
    "SubnetCreate",
    "SubnetResponse",
    "UserInfo",
    # Settings
    "SettingValue",
    "SettingUpdate",
    "SystemConfigResponse",
    "SystemConfigUpdate",
    # Notifications
    "NotificationServiceCreate",
    "NotificationServiceUpdate",
    "NotificationServiceResponse",
    "NotificationRuleCreate",
    "NotificationRuleUpdate",
    "NotificationRuleResponse",
    "NotificationHistoryResponse",
    "NotificationEventType",
    # Backups
    "BackupScheduleCreate",
    "BackupScheduleUpdate",
    "BackupScheduleResponse",
    "RetentionPolicyUpdate",
    "RetentionPolicyResponse",
    "BackupHistoryResponse",
    "BackupRunRequest",
    "VerificationScheduleUpdate",
    "VerificationScheduleResponse",
    # Email
    "EmailConfigUpdate",
    "EmailConfigResponse",
    "EmailTemplateUpdate",
    "EmailTemplateResponse",
    "EmailTestRequest",
    "EmailTestResponse",
    # System Notifications
    "EventResponse",
    "EventUpdate",
    "TargetCreate",
    "TargetResponse",
    "ContainerConfigCreate",
    "ContainerConfigUpdate",
    "ContainerConfigResponse",
    "GlobalSettingsResponse",
    "GlobalSettingsUpdate",
    "SystemNotificationHistoryResponse",
    "HistoryListResponse",
    "StateResponse",
    "MaintenanceModeRequest",
    "TestEventRequest",
]
