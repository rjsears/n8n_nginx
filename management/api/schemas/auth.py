"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/schemas/auth.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request payload."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    totp_code: Optional[str] = Field(None, min_length=6, max_length=6)


class LoginResponse(BaseModel):
    """Login response with session token."""
    token: str
    expires_at: datetime
    user: "UserInfo"

    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    """User information (public)."""
    id: int
    username: str
    email: Optional[str] = None
    totp_enabled: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionInfo(BaseModel):
    """Current session information."""
    token: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class SubnetCreate(BaseModel):
    """Create allowed subnet."""
    cidr: str = Field(..., pattern=r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$")
    description: Optional[str] = Field(None, max_length=255)
    enabled: bool = True


class SubnetResponse(BaseModel):
    """Allowed subnet response."""
    id: int
    cidr: str
    description: Optional[str] = None
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Create new admin user."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[EmailStr] = None


class UserUpdate(BaseModel):
    """Update user profile."""
    email: Optional[EmailStr] = None


class TOTPSetupResponse(BaseModel):
    """TOTP setup response with secret and QR code."""
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    """Verify TOTP code to enable 2FA."""
    code: str = Field(..., min_length=6, max_length=6)
