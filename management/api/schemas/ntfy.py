"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/schemas/ntfy.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum


class NtfyPriority(int, Enum):
    """NTFY priority levels."""
    MIN = 1
    LOW = 2
    DEFAULT = 3
    HIGH = 4
    URGENT = 5


class NtfyActionType(str, Enum):
    """NTFY action button types."""
    VIEW = "view"
    HTTP = "http"
    BROADCAST = "broadcast"


# =============================================================================
# Health & Status
# =============================================================================

class NtfyHealthResponse(BaseModel):
    """NTFY server health status."""
    healthy: bool
    status: str  # 'connected', 'disconnected', 'error'
    message: str
    details: Optional[Dict[str, Any]] = None
    last_check: datetime = Field(default_factory=lambda: datetime.now())


class NtfyStatusResponse(BaseModel):
    """Full NTFY service status."""
    server_healthy: bool
    server_url: str
    topics_count: int
    templates_count: int
    messages_today: int
    last_message_at: Optional[datetime] = None


# =============================================================================
# Message Sending
# =============================================================================

class NtfyActionButton(BaseModel):
    """Action button definition for NTFY messages."""
    action: NtfyActionType
    label: str = Field(..., min_length=1, max_length=40)
    url: Optional[str] = Field(None, max_length=2048)
    method: str = "POST"
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    intent: Optional[str] = None  # For broadcast
    extras: Optional[Dict[str, str]] = None  # For broadcast
    clear: bool = False


class NtfyMessageRequest(BaseModel):
    """Request to send an NTFY message."""
    topic: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=500)
    priority: NtfyPriority = NtfyPriority.DEFAULT
    tags: List[str] = Field(default_factory=list)
    click: Optional[str] = Field(None, max_length=2048)
    attach: Optional[str] = Field(None, max_length=2048)
    icon: Optional[str] = Field(None, max_length=2048)
    actions: List[NtfyActionButton] = Field(default_factory=list)
    delay: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    markdown: bool = False

    # Optional: save this message as a template
    save_as_template: Optional[str] = None

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v):
        """Validate topic name."""
        if not v or not v.strip():
            raise ValueError("Topic cannot be empty")
        # NTFY topic restrictions
        if len(v) > 64:
            raise ValueError("Topic name too long (max 64 characters)")
        return v.strip()

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags list."""
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return [tag.strip() for tag in v if tag.strip()]


class NtfyMessageResponse(BaseModel):
    """Response from sending an NTFY message."""
    success: bool
    message_id: Optional[str] = None
    topic: Optional[str] = None
    scheduled: bool = False
    error: Optional[str] = None
    response: Optional[Dict[str, Any]] = None


class NtfyTemplatedMessageRequest(BaseModel):
    """Send a message using a template."""
    topic: str = Field(..., min_length=1, max_length=100)
    template_name: str = Field(..., min_length=1, max_length=100)
    data: Dict[str, Any] = Field(default_factory=dict)
    priority: Optional[NtfyPriority] = None
    extra_tags: List[str] = Field(default_factory=list)


# =============================================================================
# Templates
# =============================================================================

class NtfyTemplateCreate(BaseModel):
    """Create a new NTFY template."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    template_type: str = "custom"
    based_on: Optional[str] = None

    # Template content
    title_template: Optional[str] = None
    message_template: Optional[str] = None

    # Default settings
    default_priority: NtfyPriority = NtfyPriority.DEFAULT
    default_tags: List[str] = Field(default_factory=list)
    default_click_url: Optional[str] = None
    default_icon_url: Optional[str] = None

    # Actions
    actions_template: Optional[List[NtfyActionButton]] = None

    # Formatting
    use_markdown: bool = False

    # Sample for preview
    sample_json: Optional[Dict[str, Any]] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate template name."""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Template name can only contain letters, numbers, underscores, and hyphens")
        return v


class NtfyTemplateUpdate(BaseModel):
    """Update an existing NTFY template."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    title_template: Optional[str] = None
    message_template: Optional[str] = None
    default_priority: Optional[NtfyPriority] = None
    default_tags: Optional[List[str]] = None
    default_click_url: Optional[str] = None
    default_icon_url: Optional[str] = None
    actions_template: Optional[List[NtfyActionButton]] = None
    use_markdown: Optional[bool] = None
    sample_json: Optional[Dict[str, Any]] = None


class NtfyTemplateResponse(BaseModel):
    """NTFY template response."""
    id: int
    name: str
    description: Optional[str] = None
    template_type: str
    based_on: Optional[str] = None
    title_template: Optional[str] = None
    message_template: Optional[str] = None
    default_priority: int
    default_tags: List[str] = []
    default_click_url: Optional[str] = None
    default_icon_url: Optional[str] = None
    actions_template: Optional[List[Dict[str, Any]]] = None
    use_markdown: bool = False
    sample_json: Optional[Dict[str, Any]] = None
    use_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NtfyTemplatePreviewRequest(BaseModel):
    """Preview a template with sample data."""
    title_template: Optional[str] = None
    message_template: Optional[str] = None
    sample_json: Dict[str, Any] = Field(default_factory=dict)


class NtfyTemplatePreviewResponse(BaseModel):
    """Template preview result."""
    success: bool
    rendered_title: Optional[str] = None
    rendered_message: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Topics
# =============================================================================

class NtfyTopicCreate(BaseModel):
    """Create a new NTFY topic."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    access_level: str = "read-write"
    requires_auth: bool = False
    default_priority: NtfyPriority = NtfyPriority.DEFAULT
    default_tags: List[str] = Field(default_factory=list)


class NtfyTopicUpdate(BaseModel):
    """Update an NTFY topic."""
    description: Optional[str] = None
    access_level: Optional[str] = None
    requires_auth: Optional[bool] = None
    default_priority: Optional[NtfyPriority] = None
    default_tags: Optional[List[str]] = None
    enabled: Optional[bool] = None


class NtfyTopicResponse(BaseModel):
    """NTFY topic response."""
    id: int
    name: str
    description: Optional[str] = None
    access_level: str
    requires_auth: bool
    default_priority: int
    default_tags: List[str] = []
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    enabled: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Saved Messages
# =============================================================================

class NtfySavedMessageCreate(BaseModel):
    """Create a saved message."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    topic: str = Field(..., min_length=1, max_length=100)
    title: Optional[str] = None
    message: str = Field(..., min_length=1)
    priority: NtfyPriority = NtfyPriority.DEFAULT
    tags: List[str] = Field(default_factory=list)
    click_url: Optional[str] = None
    icon_url: Optional[str] = None
    attach_url: Optional[str] = None
    actions: Optional[List[NtfyActionButton]] = None
    use_markdown: bool = False
    delay: Optional[str] = None
    email: Optional[str] = None


class NtfySavedMessageResponse(BaseModel):
    """Saved message response."""
    id: int
    name: str
    description: Optional[str] = None
    topic: str
    title: Optional[str] = None
    message: str
    priority: int
    tags: List[str] = []
    click_url: Optional[str] = None
    icon_url: Optional[str] = None
    attach_url: Optional[str] = None
    actions: Optional[List[Dict[str, Any]]] = None
    use_markdown: bool = False
    delay: Optional[str] = None
    email: Optional[str] = None
    use_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Message History
# =============================================================================

class NtfyMessageHistoryResponse(BaseModel):
    """Message history entry response."""
    id: int
    topic: str
    title: Optional[str] = None
    message: str
    priority: int
    tags: List[str] = []
    status: str
    error_message: Optional[str] = None
    source: str
    template_id: Optional[int] = None
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Server Configuration
# =============================================================================

class NtfyServerConfigUpdate(BaseModel):
    """Update NTFY server configuration."""
    base_url: Optional[str] = None
    upstream_base_url: Optional[str] = None
    default_access: Optional[str] = None
    enable_login: Optional[bool] = None
    enable_signup: Optional[bool] = None
    cache_duration: Optional[str] = None
    attachment_total_size_limit: Optional[str] = None
    attachment_file_size_limit: Optional[str] = None
    attachment_expiry_duration: Optional[str] = None
    visitor_message_daily_limit: Optional[int] = None
    smtp_sender_addr: Optional[str] = None
    smtp_sender_user: Optional[str] = None
    smtp_sender_pass: Optional[str] = None
    smtp_sender_from: Optional[str] = None


class NtfyServerConfigResponse(BaseModel):
    """NTFY server configuration response."""
    base_url: Optional[str] = None
    upstream_base_url: str = "https://ntfy.sh"
    default_access: str = "read-write"
    enable_login: bool = True
    enable_signup: bool = False
    cache_duration: str = "24h"
    attachment_total_size_limit: str = "100M"
    attachment_file_size_limit: str = "15M"
    attachment_expiry_duration: str = "24h"
    visitor_message_daily_limit: int = 0
    smtp_configured: bool = False
    web_push_configured: bool = False
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Emoji Reference
# =============================================================================

class EmojiCategory(BaseModel):
    """Emoji category with shortcodes."""
    name: str
    emojis: List[Dict[str, str]]  # [{"shortcode": "warning", "emoji": "⚠️"}, ...]


class EmojiSearchResponse(BaseModel):
    """Emoji search results."""
    query: str
    results: List[Dict[str, str]]
    total: int


# =============================================================================
# Integration Examples
# =============================================================================

class IntegrationExample(BaseModel):
    """Example integration configuration."""
    name: str
    description: str
    category: str  # 'n8n', 'curl', 'python', 'webhook'
    code: str
    variables: Optional[Dict[str, str]] = None


class WebhookUrlResponse(BaseModel):
    """Generated webhook URL for integrations."""
    url: str
    topic: str
    example_curl: str
    example_json: Dict[str, Any]
