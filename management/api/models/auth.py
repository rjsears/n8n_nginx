"""
Authentication and authorization models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

from api.database import Base


class AdminUser(Base):
    """Admin user account."""

    __tablename__ = "admin_user"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)

    # Optional 2FA
    totp_secret = Column(String(32), nullable=True)
    totp_enabled = Column(Boolean, default=False)

    # Account security
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AdminUser(id={self.id}, username='{self.username}')>"


class Session(Base):
    """User session for authentication."""

    __tablename__ = "sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_user.id", ondelete="CASCADE"), nullable=False)

    # Session metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("AdminUser", back_populates="sessions")

    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
        Index("idx_sessions_expires_at", "expires_at"),
    )

    def __repr__(self):
        return f"<Session(token='{self.token[:8]}...', user_id={self.user_id})>"


class AllowedSubnet(Base):
    """IP subnet allowed to access the management interface."""

    __tablename__ = "allowed_subnets"

    id = Column(Integer, primary_key=True)
    cidr = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<AllowedSubnet(id={self.id}, cidr='{self.cidr}')>"
