"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/schemas/system_notifications.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FrequencyOption(str, Enum):
    EVERY_TIME = "every_time"
    ONCE_PER_15M = "once_per_15m"
    ONCE_PER_30M = "once_per_30m"
    ONCE_PER_HOUR = "once_per_hour"
    ONCE_PER_4H = "once_per_4h"
    ONCE_PER_12H = "once_per_12h"
    ONCE_PER_DAY = "once_per_day"
    ONCE_PER_WEEK = "once_per_week"


class EventCategory(str, Enum):
    BACKUP = "backup"
    CONTAINER = "container"
    SYSTEM = "system"
    SECURITY = "security"


class TargetType(str, Enum):
    CHANNEL = "channel"
    GROUP = "group"


# Target schemas
class TargetBase(BaseModel):
    target_type: TargetType
    channel_id: Optional[int] = None
    group_id: Optional[int] = None
    escalation_level: int = Field(default=1, ge=1, le=2)


class TargetCreate(TargetBase):
    pass


class TargetResponse(TargetBase):
    id: int
    event_id: int
    channel_name: Optional[str] = None
    channel_slug: Optional[str] = None
    group_name: Optional[str] = None
    group_slug: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Event schemas
class EventBase(BaseModel):
    enabled: Optional[bool] = True
    severity: Optional[SeverityLevel] = SeverityLevel.WARNING
    frequency: Optional[FrequencyOption] = FrequencyOption.EVERY_TIME
    cooldown_minutes: Optional[int] = Field(default=5, ge=0)
    flapping_enabled: Optional[bool] = True
    flapping_threshold_count: Optional[int] = Field(default=3, ge=2)
    flapping_threshold_minutes: Optional[int] = Field(default=10, ge=1)
    flapping_summary_interval: Optional[int] = Field(default=15, ge=1)
    notify_on_recovery: Optional[bool] = True
    thresholds: Optional[Dict[str, Any]] = None
    escalation_enabled: Optional[bool] = False
    escalation_timeout_minutes: Optional[int] = Field(default=30, ge=1)
    include_in_digest: Optional[bool] = False


class EventUpdate(EventBase):
    pass


class EventResponse(BaseModel):
    id: int
    event_type: str
    display_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    category: str
    enabled: bool
    severity: str
    frequency: str
    cooldown_minutes: int
    flapping_enabled: bool
    flapping_threshold_count: int
    flapping_threshold_minutes: int
    flapping_summary_interval: int
    notify_on_recovery: bool
    thresholds: Optional[Dict[str, Any]] = None
    escalation_enabled: bool
    escalation_timeout_minutes: int
    include_in_digest: bool
    created_at: datetime
    updated_at: datetime
    targets: List[TargetResponse] = []

    class Config:
        from_attributes = True


# Container config schemas
class ContainerConfigBase(BaseModel):
    enabled: Optional[bool] = True
    monitor_unhealthy: Optional[bool] = True
    monitor_restart: Optional[bool] = True
    monitor_stopped: Optional[bool] = True
    monitor_high_cpu: Optional[bool] = False
    cpu_threshold: Optional[int] = Field(default=80, ge=1, le=100)
    monitor_high_memory: Optional[bool] = False
    memory_threshold: Optional[int] = Field(default=80, ge=1, le=100)
    custom_targets: Optional[List[Dict[str, Any]]] = None


class ContainerConfigCreate(ContainerConfigBase):
    container_name: str = Field(..., min_length=1, max_length=100)


class ContainerConfigUpdate(ContainerConfigBase):
    pass


class ContainerConfigResponse(BaseModel):
    id: int
    container_name: str
    enabled: bool
    monitor_unhealthy: bool
    monitor_restart: bool
    monitor_stopped: bool
    monitor_high_cpu: bool
    cpu_threshold: int
    monitor_high_memory: bool
    memory_threshold: int
    custom_targets: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Global settings schemas
class GlobalSettingsBase(BaseModel):
    maintenance_mode: Optional[bool] = False
    maintenance_until: Optional[datetime] = None
    maintenance_reason: Optional[str] = Field(default=None, max_length=255)
    quiet_hours_enabled: Optional[bool] = False
    quiet_hours_start: Optional[str] = Field(default="22:00", pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: Optional[str] = Field(default="07:00", pattern=r"^\d{2}:\d{2}$")
    quiet_hours_reduce_priority: Optional[bool] = True
    blackout_enabled: Optional[bool] = False
    blackout_start: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    blackout_end: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    max_notifications_per_hour: Optional[int] = Field(default=50, ge=1)
    emergency_contact_id: Optional[int] = None
    digest_enabled: Optional[bool] = False
    digest_time: Optional[str] = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    digest_severity_levels: Optional[List[str]] = None


class GlobalSettingsUpdate(GlobalSettingsBase):
    pass


class GlobalSettingsResponse(BaseModel):
    id: int
    maintenance_mode: bool
    maintenance_until: Optional[datetime] = None
    maintenance_reason: Optional[str] = None
    quiet_hours_enabled: bool
    quiet_hours_start: str
    quiet_hours_end: str
    quiet_hours_reduce_priority: bool
    blackout_enabled: bool
    blackout_start: Optional[str] = None
    blackout_end: Optional[str] = None
    max_notifications_per_hour: int
    notifications_this_hour: int
    hour_started_at: Optional[datetime] = None
    emergency_contact_id: Optional[int] = None
    emergency_contact_name: Optional[str] = None
    digest_enabled: bool
    digest_time: str
    digest_severity_levels: Optional[List[str]] = None
    last_digest_sent: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# History schemas
class HistoryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    BATCHED = "batched"


class HistoryResponse(BaseModel):
    id: int
    event_type: str
    event_id: Optional[int] = None
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    severity: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None
    channels_sent: Optional[List[Dict[str, Any]]] = None
    escalation_level: int
    status: str
    suppression_reason: Optional[str] = None
    error_message: Optional[str] = None
    triggered_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HistoryListResponse(BaseModel):
    items: List[HistoryResponse]
    total: int
    limit: int
    offset: int


# State schemas (for debugging/monitoring)
class StateResponse(BaseModel):
    id: int
    event_type: str
    target_id: Optional[str] = None
    last_sent_at: Optional[datetime] = None
    event_count_in_window: int
    window_start: Optional[datetime] = None
    is_flapping: bool
    flapping_started_at: Optional[datetime] = None
    last_summary_at: Optional[datetime] = None
    escalation_triggered_at: Optional[datetime] = None
    escalation_sent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Quick action schemas
class MaintenanceModeRequest(BaseModel):
    enabled: bool
    until: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=255)


class TestEventRequest(BaseModel):
    event_type: str
    target_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
