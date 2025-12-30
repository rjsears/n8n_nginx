"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/models/ntfy.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, UTC

from api.database import Base


class NtfyTemplate(Base):
    """
    NTFY message templates for reusable notification formats.
    Supports Go template syntax for dynamic content.
    """

    __tablename__ = "ntfy_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Template type: 'custom', 'github', 'grafana', 'alertmanager'
    template_type = Column(String(50), default="custom")

    # Based on pre-defined template (if any)
    based_on = Column(String(50), nullable=True)

    # Template content with Go template syntax support
    title_template = Column(Text, nullable=True)
    message_template = Column(Text, nullable=True)

    # Default message settings
    default_priority = Column(Integer, default=3)  # 1-5
    default_tags = Column(JSONB, default=list)  # Array of tag strings
    default_click_url = Column(String(2048), nullable=True)
    default_icon_url = Column(String(2048), nullable=True)

    # Action buttons template
    actions_template = Column(JSONB, nullable=True)  # Array of action definitions

    # Markdown support
    use_markdown = Column(Boolean, default=False)

    # Sample JSON for preview
    sample_json = Column(JSONB, nullable=True)

    # Usage tracking
    use_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    created_by = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<NtfyTemplate(id={self.id}, name='{self.name}')>"


class NtfyTopic(Base):
    """
    NTFY topics for organizing notifications.
    """

    __tablename__ = "ntfy_topics"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Access control
    access_level = Column(String(20), default="read-write")  # read-write, read-only, write-only
    requires_auth = Column(Boolean, default=False)

    # Default settings for messages to this topic
    default_priority = Column(Integer, default=3)
    default_tags = Column(JSONB, default=list)

    # Statistics
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("idx_ntfy_topics_name", "name"),
    )

    def __repr__(self):
        return f"<NtfyTopic(id={self.id}, name='{self.name}')>"


class NtfySavedMessage(Base):
    """
    Saved NTFY messages for quick re-sending or as templates.
    """

    __tablename__ = "ntfy_saved_messages"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Target
    topic = Column(String(100), nullable=False)

    # Message content
    title = Column(String(500), nullable=True)
    message = Column(Text, nullable=False)
    priority = Column(Integer, default=3)  # 1-5
    tags = Column(JSONB, default=list)

    # Actions
    click_url = Column(String(2048), nullable=True)
    icon_url = Column(String(2048), nullable=True)
    attach_url = Column(String(2048), nullable=True)
    actions = Column(JSONB, nullable=True)  # Action buttons

    # Formatting
    use_markdown = Column(Boolean, default=False)

    # Scheduling
    delay = Column(String(100), nullable=True)  # e.g., "30m", "tomorrow 10am"

    # Email forwarding
    email = Column(String(255), nullable=True)

    # Usage
    use_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    created_by = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<NtfySavedMessage(id={self.id}, name='{self.name}')>"


class NtfyMessageHistory(Base):
    """
    History of sent NTFY messages.
    """

    __tablename__ = "ntfy_message_history"

    id = Column(Integer, primary_key=True)

    # Target
    topic = Column(String(100), nullable=False, index=True)

    # Message content (copy of what was sent)
    title = Column(String(500), nullable=True)
    message = Column(Text, nullable=False)
    priority = Column(Integer, default=3)
    tags = Column(JSONB, default=list)

    # Full request payload
    request_payload = Column(JSONB, nullable=True)

    # Response
    status = Column(String(20), nullable=False, index=True)  # 'sent', 'failed', 'scheduled'
    response_id = Column(String(100), nullable=True)  # NTFY message ID if returned
    error_message = Column(Text, nullable=True)

    # Source
    source = Column(String(50), default="manual")  # 'manual', 'template', 'api', 'workflow'
    template_id = Column(Integer, nullable=True)

    # Timing
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("idx_ntfy_message_history_topic", "topic"),
        Index("idx_ntfy_message_history_status", "status"),
        Index("idx_ntfy_message_history_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<NtfyMessageHistory(id={self.id}, topic='{self.topic}', status='{self.status}')>"


class NtfyServerConfig(Base):
    """
    NTFY server configuration stored in database.
    Allows UI-based configuration management.
    """

    __tablename__ = "ntfy_server_config"

    id = Column(Integer, primary_key=True)

    # Connection
    base_url = Column(String(500), nullable=True)  # Uses default if not set
    upstream_base_url = Column(String(500), default="https://ntfy.sh")

    # Authentication
    default_access = Column(String(20), default="read-write")
    enable_login = Column(Boolean, default=True)
    enable_signup = Column(Boolean, default=False)

    # Cache settings
    cache_duration = Column(String(20), default="24h")

    # Attachment settings
    attachment_total_size_limit = Column(String(20), default="100M")
    attachment_file_size_limit = Column(String(20), default="15M")
    attachment_expiry_duration = Column(String(20), default="24h")

    # Rate limiting
    visitor_message_daily_limit = Column(Integer, default=0)  # 0 = unlimited

    # SMTP settings (for email notifications)
    smtp_sender_addr = Column(String(255), nullable=True)
    smtp_sender_user = Column(String(255), nullable=True)
    smtp_sender_pass = Column(String(255), nullable=True)  # Encrypted
    smtp_sender_from = Column(String(255), nullable=True)

    # Web Push (optional)
    web_push_public_key = Column(Text, nullable=True)
    web_push_private_key = Column(Text, nullable=True)  # Encrypted
    web_push_email = Column(String(255), nullable=True)

    # Status
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(20), default="unknown")  # 'healthy', 'unhealthy', 'unknown'

    # Timestamps
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<NtfyServerConfig(id={self.id}, status='{self.health_status}')>"
