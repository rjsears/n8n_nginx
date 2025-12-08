"""
Email system schemas.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class EmailProvider(str, Enum):
    """Supported email providers."""
    GMAIL_RELAY = "gmail_relay"
    GMAIL_APP_PASSWORD = "gmail_app_password"
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    AWS_SES = "aws_ses"


class EmailConfigUpdate(BaseModel):
    """Update email configuration."""
    provider: EmailProvider
    from_email: EmailStr
    from_name: str = Field(default="n8n Management", max_length=100)
    # Provider-specific config
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    use_tls: bool = True
    # API-based providers
    api_key: Optional[str] = None


class EmailConfigResponse(BaseModel):
    """Email configuration response (passwords redacted)."""
    provider: str
    from_email: str
    from_name: str
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    use_tls: bool = True
    configured: bool = False
    last_test: Optional[datetime] = None
    last_test_status: Optional[str] = None


class EmailTemplateUpdate(BaseModel):
    """Update email template."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    subject: Optional[str] = Field(None, max_length=500)
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    enabled: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    """Email template response."""
    id: int
    template_key: str
    name: str
    description: Optional[str] = None
    subject: str
    html_body: str
    text_body: Optional[str] = None
    variables: Optional[Dict[str, str]] = None
    category: str
    enabled: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailTestRequest(BaseModel):
    """Email test request."""
    recipient: EmailStr
    template_key: Optional[str] = None


class EmailTestResponse(BaseModel):
    """Email test response."""
    status: str  # 'success', 'failed'
    response_time_ms: int
    error_message: Optional[str] = None
    smtp_response: Optional[str] = None


class EmailTestHistoryResponse(BaseModel):
    """Email test history response."""
    id: int
    provider: str
    recipient: str
    template_key: Optional[str] = None
    status: str
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    tested_at: datetime

    class Config:
        from_attributes = True


class EmailSendRequest(BaseModel):
    """Send email request."""
    recipient: EmailStr
    subject: str = Field(..., max_length=500)
    html_body: str
    text_body: Optional[str] = None


class EmailTemplatePreviewRequest(BaseModel):
    """Preview email template with variables."""
    template_key: str
    variables: Dict[str, Any]


class EmailTemplatePreviewResponse(BaseModel):
    """Email template preview response."""
    subject: str
    html_body: str
    text_body: Optional[str] = None
