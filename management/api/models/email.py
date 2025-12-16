"""
Email system models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, UTC

from api.database import Base


class EmailTemplate(Base):
    """Email template storage."""

    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    template_key = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Template content
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)  # Plain text fallback

    # Template metadata
    variables = Column(JSONB, nullable=True)  # Expected variables: {"backup_name": "string", ...}
    category = Column(String(50), default="system")
    enabled = Column(Boolean, default=True)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<EmailTemplate(key='{self.template_key}', name='{self.name}')>"


class EmailTestHistory(Base):
    """History of email test sends."""

    __tablename__ = "email_test_history"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    provider_config = Column(JSONB, nullable=True)  # Sanitized (no passwords)
    recipient = Column(String(255), nullable=False)
    template_key = Column(String(100), nullable=True)

    # Result
    status = Column(String(20), nullable=False)  # 'success', 'failed'
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    smtp_response = Column(Text, nullable=True)

    # Who tested
    tested_by = Column(Integer, ForeignKey("admin_user.id"), nullable=True)
    tested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<EmailTestHistory(id={self.id}, provider='{self.provider}', status='{self.status}')>"
