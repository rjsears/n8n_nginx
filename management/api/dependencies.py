"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/dependencies.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from fastapi import Depends, HTTPException, Header, Cookie, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, UTC
import logging

from api.database import get_db, get_n8n_db
from api.config import settings
from api.security import is_ip_allowed

logger = logging.getLogger(__name__)


async def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (from nginx)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    return request.client.host if request.client else "unknown"


async def get_current_session(
    request: Request,
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None, alias="session"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current authenticated session from token.
    Token can be in Authorization header or session cookie.
    """
    from api.models.auth import Session, AdminUser

    # Extract token from header or cookie
    token = None
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
    elif session_token:
        token = session_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up session
    result = await db.execute(
        select(Session)
        .where(Session.token == token)
        .where(Session.is_active == True)
        .where(Session.expires_at > datetime.now(UTC))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session


async def get_current_user(
    session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user from session."""
    from api.models.auth import AdminUser

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == session.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def verify_session_for_proxy(
    request: Request,
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None, alias="session"),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """
    Verify session for nginx auth_request.
    Returns True if valid, raises 401 if not.
    Used for SSO proxy to Adminer and Dozzle.
    """
    try:
        await get_current_session(request, authorization, session_token, db)
        return True
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


async def check_subnet_restriction(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> bool:
    """
    Check if client IP is allowed based on subnet restrictions.
    Used as a dependency for protected endpoints.
    """
    from api.models.auth import AllowedSubnet

    # Get allowed subnets
    result = await db.execute(
        select(AllowedSubnet).where(AllowedSubnet.enabled == True)
    )
    subnets = result.scalars().all()

    if not subnets:
        # No restrictions configured
        return True

    client_ip = await get_client_ip(request)
    allowed_cidrs = [s.cidr for s in subnets]

    if not is_ip_allowed(client_ip, allowed_cidrs):
        logger.warning(f"Access denied for IP {client_ip} - not in allowed subnets")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied from this network",
        )

    return True


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_second: int = 30):
        self.requests_per_second = requests_per_second
        self._requests: dict[str, list[float]] = {}

    async def check(self, key: str) -> bool:
        """Check if request is allowed. Returns True if allowed."""
        import time
        now = time.time()
        window = 1.0  # 1 second window

        if key not in self._requests:
            self._requests[key] = []

        # Remove old requests outside the window
        self._requests[key] = [
            t for t in self._requests[key]
            if now - t < window
        ]

        if len(self._requests[key]) >= self.requests_per_second:
            return False

        self._requests[key].append(now)
        return True


# Global rate limiters
api_rate_limiter = RateLimiter(settings.api_rate_limit)
login_rate_limiter = RateLimiter(settings.login_rate_limit)


async def rate_limit_api(request: Request):
    """Rate limit dependency for API endpoints."""
    client_ip = await get_client_ip(request)
    if not await api_rate_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )


async def rate_limit_login(request: Request):
    """Rate limit dependency for login endpoint."""
    client_ip = await get_client_ip(request)
    if not await login_rate_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )
