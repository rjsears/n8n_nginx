"""
System settings and configuration models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, LargeBinary, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, UTC

from api.database import Base


class Settings(Base):
    """Key-value settings storage."""

    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)
    category = Column(String(50), nullable=False, default="general", index=True)
    description = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False)  # If true, value is encrypted
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    updated_by = Column(Integer, ForeignKey("admin_user.id"), nullable=True)

    def __repr__(self):
        return f"<Settings(key='{self.key}', category='{self.category}')>"


class SystemConfig(Base):
    """
    System configuration storage for complex config objects.
    Config types: 'nfs', 'docker', 'email', 'management', 'security'
    """

    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True)
    config_type = Column(String(50), unique=True, nullable=False)
    config = Column(JSONB, nullable=False)
    encrypted_fields = Column(ARRAY(Text), nullable=True)  # List of JSONB paths that are encrypted
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<SystemConfig(id={self.id}, config_type='{self.config_type}')>"


class EncryptionKey(Base):
    """Encryption key storage for key rotation."""

    __tablename__ = "encryption_keys"

    id = Column(Integer, primary_key=True)
    key_id = Column(String(50), unique=True, nullable=False)
    encrypted_key = Column(LargeBinary, nullable=False)  # Encrypted with master key
    algorithm = Column(String(20), default="AES-256-GCM")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    rotated_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<EncryptionKey(id={self.id}, key_id='{self.key_id}')>"
