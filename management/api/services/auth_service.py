"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/auth_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime, timedelta, UTC
from typing import Optional, List
import logging

from api.models.auth import AdminUser, Session, AllowedSubnet
from api.models.audit import AuditLog
from api.security import (
    hash_password,
    verify_password,
    generate_session_token,
    is_ip_allowed,
    calculate_lockout_expiry,
)
from api.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and session management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_username(self, username: str) -> Optional[AdminUser]:
        """Get user by username."""
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[AdminUser]:
        """Get user by ID."""
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
    ) -> AdminUser:
        """Create a new admin user."""
        user = AdminUser(
            username=username,
            password_hash=hash_password(password),
            email=email,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info(f"Created user: {username}")
        return user

    async def authenticate(
        self,
        username: str,
        password: str,
        client_ip: str,
        user_agent: Optional[str] = None,
    ) -> tuple[Optional[AdminUser], Optional[Session], Optional[str]]:
        """
        Authenticate user and create session.
        Returns (user, session, error_message).
        """
        # Get user
        user = await self.get_user_by_username(username)
        if not user:
            await self._log_action(None, "login_failed", {"username": username, "reason": "user_not_found"}, client_ip, user_agent)
            return None, None, "Invalid credentials"

        # Check lockout
        if user.locked_until and user.locked_until > datetime.now(UTC):
            await self._log_action(user.id, "login_blocked", {"reason": "account_locked"}, client_ip, user_agent)
            return None, None, "Account is locked. Please try again later."

        # Verify password
        if not verify_password(password, user.password_hash):
            await self._increment_failed_attempts(user)
            await self._log_action(user.id, "login_failed", {"reason": "invalid_password"}, client_ip, user_agent)
            return None, None, "Invalid credentials"

        # Reset failed attempts on successful login
        if user.failed_attempts > 0:
            user.failed_attempts = 0
            user.locked_until = None

        # Create session
        session = await self._create_session(user, client_ip, user_agent)

        # Update last login
        user.last_login = datetime.now(UTC)
        await self.db.commit()

        await self._log_action(user.id, "login_success", None, client_ip, user_agent)
        logger.info(f"User {username} logged in from {client_ip}")

        return user, session, None

    async def _create_session(
        self,
        user: AdminUser,
        client_ip: str,
        user_agent: Optional[str],
    ) -> Session:
        """Create a new session for user."""
        token = generate_session_token()
        expires_at = datetime.now(UTC) + timedelta(hours=settings.session_expire_hours)

        session = Session(
            token=token,
            user_id=user.id,
            expires_at=expires_at,
            ip_address=client_ip,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def _increment_failed_attempts(self, user: AdminUser) -> None:
        """Increment failed login attempts and lock if necessary."""
        user.failed_attempts += 1

        # Check if should lock
        lockout_until = calculate_lockout_expiry(user.failed_attempts)
        if lockout_until:
            user.locked_until = lockout_until
            logger.warning(f"User {user.username} locked until {lockout_until}")

        await self.db.commit()

    async def logout(self, token: str) -> bool:
        """Invalidate a session."""
        result = await self.db.execute(
            update(Session)
            .where(Session.token == token)
            .values(is_active=False)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def logout_all(self, user_id: int) -> int:
        """Invalidate all sessions for a user."""
        result = await self.db.execute(
            update(Session)
            .where(Session.user_id == user_id)
            .values(is_active=False)
        )
        await self.db.commit()
        return result.rowcount

    async def get_session(self, token: str) -> Optional[Session]:
        """Get active session by token."""
        result = await self.db.execute(
            select(Session)
            .where(Session.token == token)
            .where(Session.is_active == True)
            .where(Session.expires_at > datetime.now(UTC))
        )
        return result.scalar_one_or_none()

    async def get_user_sessions(self, user_id: int) -> List[Session]:
        """Get all active sessions for a user."""
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .where(Session.is_active == True)
            .where(Session.expires_at > datetime.now(UTC))
            .order_by(Session.created_at.desc())
        )
        return list(result.scalars().all())

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> tuple[bool, Optional[str]]:
        """Change user password. Returns (success, error_message)."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False, "User not found"

        if not verify_password(current_password, user.password_hash):
            return False, "Current password is incorrect"

        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(UTC)
        await self.db.commit()

        # Invalidate all other sessions for security
        await self.logout_all(user_id)

        await self._log_action(user_id, "password_changed", None, None, None)
        logger.info(f"Password changed for user {user.username}")

        return True, None

    # Subnet management

    async def get_allowed_subnets(self) -> List[AllowedSubnet]:
        """Get all allowed subnets."""
        result = await self.db.execute(
            select(AllowedSubnet).order_by(AllowedSubnet.created_at)
        )
        return list(result.scalars().all())

    async def add_allowed_subnet(
        self,
        cidr: str,
        description: Optional[str] = None,
        enabled: bool = True,
    ) -> AllowedSubnet:
        """Add an allowed subnet."""
        subnet = AllowedSubnet(
            cidr=cidr,
            description=description,
            enabled=enabled,
        )
        self.db.add(subnet)
        await self.db.commit()
        await self.db.refresh(subnet)
        logger.info(f"Added allowed subnet: {cidr}")
        return subnet

    async def delete_allowed_subnet(self, subnet_id: int) -> bool:
        """Delete an allowed subnet."""
        result = await self.db.execute(
            delete(AllowedSubnet).where(AllowedSubnet.id == subnet_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed based on configured subnets."""
        subnets = await self.get_allowed_subnets()
        enabled_subnets = [s for s in subnets if s.enabled]

        if not enabled_subnets:
            return True  # No restrictions

        cidrs = [s.cidr for s in enabled_subnets]
        return is_ip_allowed(ip, cidrs)

    # Audit logging

    async def _log_action(
        self,
        user_id: Optional[int],
        action: str,
        details: Optional[dict],
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Log an action to audit log."""
        user = await self.get_user_by_id(user_id) if user_id else None

        log = AuditLog(
            user_id=user_id,
            username=user.username if user else None,
            action=action,
            resource_type="auth",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self.db.add(log)
        await self.db.commit()

    # Session cleanup

    async def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions. Returns count of deleted sessions."""
        result = await self.db.execute(
            delete(Session).where(Session.expires_at < datetime.now(UTC))
        )
        await self.db.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        return count
