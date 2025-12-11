"""
Notification system schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum


class NotificationEventType(str, Enum):
    """All supported notification event types."""
    # Backup events
    BACKUP_STARTED = "backup.started"
    BACKUP_SUCCESS = "backup.success"
    BACKUP_FAILED = "backup.failed"
    BACKUP_WARNING = "backup.warning"

    # Verification events
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"

    # Container events
    CONTAINER_STARTED = "container.started"
    CONTAINER_STOPPED = "container.stopped"
    CONTAINER_RESTARTED = "container.restarted"
    CONTAINER_UNHEALTHY = "container.unhealthy"
    CONTAINER_RECOVERED = "container.recovered"

    # System events
    SYSTEM_HIGH_CPU = "system.high_cpu"
    SYSTEM_HIGH_MEMORY = "system.high_memory"
    SYSTEM_DISK_WARNING = "system.disk_warning"
    SYSTEM_DISK_CRITICAL = "system.disk_critical"
    SYSTEM_NFS_CONNECTED = "system.nfs_connected"
    SYSTEM_NFS_DISCONNECTED = "system.nfs_disconnected"
    SYSTEM_NFS_ERROR = "system.nfs_error"

    # Security events
    SECURITY_LOGIN_SUCCESS = "security.login_success"
    SECURITY_LOGIN_FAILED = "security.login_failed"
    SECURITY_ACCOUNT_LOCKED = "security.account_locked"

    # Management events
    MGMT_SETTINGS_CHANGED = "management.settings_changed"
    MGMT_USER_CREATED = "management.user_created"
    MGMT_BACKUP_DELETED = "management.backup_deleted"

    # Flow events
    FLOW_EXTRACTED = "flow.extracted"
    FLOW_RESTORED = "flow.restored"


class ServiceType(str, Enum):
    """Notification service types."""
    APPRISE = "apprise"
    NTFY = "ntfy"
    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationServiceCreate(BaseModel):
    """Create notification service."""
    name: str = Field(..., min_length=1, max_length=100)
    service_type: ServiceType
    enabled: bool = True
    webhook_enabled: bool = False
    config: Dict[str, Any]
    priority: int = Field(default=0, ge=0, le=100)


class NotificationServiceUpdate(BaseModel):
    """Update notification service."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=0, le=100)


class NotificationServiceResponse(BaseModel):
    """Notification service response."""
    id: int
    name: str
    service_type: str
    enabled: bool
    webhook_enabled: bool = False
    config: Dict[str, Any]  # Sensitive fields redacted
    priority: int
    last_test: Optional[datetime] = None
    last_test_result: Optional[str] = None
    last_test_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationRuleCreate(BaseModel):
    """Create notification rule."""
    name: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    event_type: str = Field(..., min_length=1, max_length=100)
    event_pattern: Optional[str] = Field(None, max_length=255)
    service_id: int
    priority: NotificationPriority = NotificationPriority.NORMAL
    conditions: Optional[Dict[str, Any]] = None
    custom_title: Optional[str] = Field(None, max_length=500)
    custom_message: Optional[str] = None
    include_details: bool = True
    cooldown_minutes: int = Field(default=0, ge=0, le=1440)
    sort_order: int = 0


class NotificationRuleUpdate(BaseModel):
    """Update notification rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    event_type: Optional[str] = Field(None, min_length=1, max_length=100)
    event_pattern: Optional[str] = Field(None, max_length=255)
    service_id: Optional[int] = None
    priority: Optional[NotificationPriority] = None
    conditions: Optional[Dict[str, Any]] = None
    custom_title: Optional[str] = Field(None, max_length=500)
    custom_message: Optional[str] = None
    include_details: Optional[bool] = None
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    sort_order: Optional[int] = None


class NotificationRuleResponse(BaseModel):
    """Notification rule response."""
    id: int
    name: str
    enabled: bool
    event_type: str
    event_pattern: Optional[str] = None
    service_id: int
    priority: str
    conditions: Optional[Dict[str, Any]] = None
    custom_title: Optional[str] = None
    custom_message: Optional[str] = None
    include_details: bool
    cooldown_minutes: int
    last_triggered: Optional[datetime] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationHistoryResponse(BaseModel):
    """Notification history response."""
    id: int
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    rule_id: Optional[int] = None
    status: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationTestRequest(BaseModel):
    """Test notification request."""
    title: str = "Test Notification"
    message: str = "This is a test notification from n8n Management."


class EventTypeInfo(BaseModel):
    """Information about an event type."""
    event_type: str
    category: str
    description: str
    default_priority: str


class WebhookNotificationRequest(BaseModel):
    """Webhook notification request from n8n or external sources."""
    title: str = Field(default="Notification", max_length=500)
    message: str = Field(..., min_length=1)
    priority: NotificationPriority = NotificationPriority.NORMAL
    tags: Optional[List[str]] = None  # Future: route to specific channel groups


class WebhookNotificationResponse(BaseModel):
    """Response from webhook notification endpoint."""
    success: bool
    channels_notified: int
    channels: List[str] = []
    errors: List[str] = []
