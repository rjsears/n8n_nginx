"""
Pydantic schemas for API request/response validation.
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
