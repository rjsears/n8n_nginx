"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/models/notifications.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import re
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

from api.database import Base


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    # Convert to lowercase
    slug = name.lower()
    # Replace spaces and special characters with underscores
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    # Remove leading/trailing underscores
    slug = slug.strip('_')
    # Collapse multiple underscores
    slug = re.sub(r'_+', '_', slug)
    return slug


class NotificationService(Base):
    """
    Notification service configuration.
    Service types: 'apprise', 'ntfy', 'email', 'webhook'
    """

    __tablename__ = "notification_services"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)  # URL-friendly identifier for targeting
    service_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    config = Column(JSONB, nullable=False)  # Service-specific config (encrypted if contains secrets)
    priority = Column(Integer, default=0)  # Higher = preferred

    # Webhook routing - when enabled, this service receives messages from the webhook endpoint
    webhook_enabled = Column(Boolean, default=False)

    # Testing status
    last_test = Column(DateTime(timezone=True), nullable=True)
    last_test_result = Column(String(20), nullable=True)  # 'success', 'failed', 'pending'
    last_test_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    rules = relationship("NotificationRule", back_populates="service", cascade="all, delete-orphan")
    group_memberships = relationship("NotificationGroupMembership", back_populates="service", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NotificationService(id={self.id}, name='{self.name}', slug='{self.slug}', type='{self.service_type}')>"


class NotificationGroup(Base):
    """
    Group of notification channels for targeted routing.
    Allows sending notifications to multiple channels via a single target.
    """

    __tablename__ = "notification_groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)  # URL-friendly identifier for targeting
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    memberships = relationship("NotificationGroupMembership", back_populates="group", cascade="all, delete-orphan")

    @property
    def channels(self):
        """Get all channels in this group."""
        return [m.service for m in self.memberships]

    def __repr__(self):
        return f"<NotificationGroup(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class NotificationGroupMembership(Base):
    """
    Join table for notification groups and services.
    A channel can belong to multiple groups.
    """

    __tablename__ = "notification_group_memberships"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("notification_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("notification_services.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    group = relationship("NotificationGroup", back_populates="memberships")
    service = relationship("NotificationService", back_populates="group_memberships")

    __table_args__ = (
        UniqueConstraint('group_id', 'service_id', name='uq_group_service'),
        Index("idx_group_membership_group_id", "group_id"),
        Index("idx_group_membership_service_id", "service_id"),
    )

    def __repr__(self):
        return f"<NotificationGroupMembership(group_id={self.group_id}, service_id={self.service_id})>"


class NotificationRule(Base):
    """
    Rule for when to send notifications.
    Maps event types to notification services.
    """

    __tablename__ = "notification_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)

    # Event matching
    event_type = Column(String(100), nullable=False, index=True)  # e.g., 'backup.failed'
    event_pattern = Column(String(255), nullable=True)  # Optional regex for sub-matching

    # Target service
    service_id = Column(Integer, ForeignKey("notification_services.id", ondelete="CASCADE"), nullable=False, index=True)
    priority = Column(String(20), default="normal")  # 'low', 'normal', 'high', 'critical'

    # Additional conditions
    conditions = Column(JSONB, nullable=True)  # time_range, cooldown, severity_threshold

    # Custom message templates
    custom_title = Column(String(500), nullable=True)
    custom_message = Column(Text, nullable=True)
    include_details = Column(Boolean, default=True)

    # Rate limiting
    cooldown_minutes = Column(Integer, default=0)
    last_triggered = Column(DateTime(timezone=True), nullable=True)

    # Ordering
    sort_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    service = relationship("NotificationService", back_populates="rules")

    __table_args__ = (
        Index("idx_notification_rules_event_type", "event_type"),
        Index("idx_notification_rules_service_id", "service_id"),
    )

    def __repr__(self):
        return f"<NotificationRule(id={self.id}, name='{self.name}', event='{self.event_type}')>"


class NotificationHistory(Base):
    """History of sent notifications."""

    __tablename__ = "notification_history"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSONB, nullable=True)
    severity = Column(String(20), nullable=True)  # 'info', 'warning', 'error', 'critical'

    # Service info (denormalized for history)
    service_id = Column(Integer, ForeignKey("notification_services.id", ondelete="SET NULL"), nullable=True)
    service_name = Column(String(100), nullable=True)
    rule_id = Column(Integer, ForeignKey("notification_rules.id", ondelete="SET NULL"), nullable=True)

    # Delivery status
    status = Column(String(20), nullable=False, index=True)  # 'pending', 'sent', 'failed', 'skipped'
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Retry handling
    retry_count = Column(Integer, default=0)
    next_retry = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("idx_notification_history_event_type", "event_type"),
        Index("idx_notification_history_status", "status"),
        Index("idx_notification_history_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<NotificationHistory(id={self.id}, event='{self.event_type}', status='{self.status}')>"


class NotificationBatch(Base):
    """Batch similar notifications to avoid spam."""

    __tablename__ = "notification_batch"

    id = Column(Integer, primary_key=True)
    batch_key = Column(String(255), nullable=False, index=True)  # Grouping key
    event_type = Column(String(100), nullable=False)
    event_count = Column(Integer, default=1)
    first_event = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_event = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    events_data = Column(JSONB, nullable=True)  # Array of event details
    status = Column(String(20), default="collecting")  # 'collecting', 'sent', 'failed'
    sent_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<NotificationBatch(id={self.id}, key='{self.batch_key}', count={self.event_count})>"
