"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/email_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
import asyncio
import smtplib
import ssl
import time
import logging

from api.models.email import EmailTemplate, EmailTestHistory
from api.models.settings import SystemConfig
from api.security import encrypt_value, decrypt_value
from api.config import settings

logger = logging.getLogger(__name__)

# Socket timeout for every SMTP connection (connect, TLS handshake, each
# command). Without one a mail server that accepts the TCP connection and then
# says nothing hangs the sender forever.
SMTP_TIMEOUT_SECONDS = 15

SMTPS_PORT = 465


def wants_implicit_tls(port: Any, use_ssl: Optional[bool] = None) -> bool:
    """
    SMTPS (TLS from the first byte) instead of plain SMTP + STARTTLS.
    An explicit ``use_ssl`` wins; otherwise port 465 means SMTPS.
    """
    if use_ssl is not None:
        return bool(use_ssl)
    try:
        return int(port) == SMTPS_PORT
    except (TypeError, ValueError):
        return False


def tls_context() -> ssl.SSLContext:
    """
    Verifying TLS context for SMTP: certificate chain and host name are
    checked against the system CA store. smtplib's own default for STARTTLS
    (and for SMTP_SSL without a context) does not verify the certificate, so
    a man-in-the-middle could read the SMTP credentials and every alert.
    There is deliberately no switch to turn this off; a server with a
    self-signed certificate needs its CA added to the container's trust store.
    """
    return ssl.create_default_context()


class VerifiedSMTP(smtplib.SMTP):
    """smtplib.SMTP whose STARTTLS verifies the server certificate by default."""

    def starttls(self, keyfile=None, certfile=None, context=None):  # noqa: D401
        return super().starttls(context=context or tls_context())


def build_email_sender(
    host: str,
    port: Any,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_starttls: bool = True,
    use_ssl: Optional[bool] = None,
    timeout: float = SMTP_TIMEOUT_SECONDS,
):
    """
    A red-mail EmailSender with a socket timeout, using SMTP_SSL for implicit
    TLS (port 465) and SMTP (+ optional STARTTLS) otherwise. Either way the
    server certificate is verified (see tls_context).
    """
    from redmail import EmailSender

    port = int(port) if port not in (None, "") else 587
    implicit_tls = wants_implicit_tls(port, use_ssl)
    kwargs: Dict[str, Any] = {
        "host": host,
        "port": port,
        "cls_smtp": smtplib.SMTP_SSL if implicit_tls else VerifiedSMTP,
        # STARTTLS on an already-encrypted SMTPS connection is an error.
        "use_starttls": False if implicit_tls else bool(use_starttls),
        "timeout": timeout,
    }
    if implicit_tls:
        # red-mail passes extra keywords to the SMTP class constructor.
        kwargs["context"] = tls_context()
    if username or password:
        kwargs["username"] = username
        kwargs["password"] = password
    return EmailSender(**kwargs)


class EmailService:
    """Email sending and management service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._sender = None
        self._config = None

    async def get_config(self) -> Optional[Dict[str, Any]]:
        """Get email configuration."""
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.config_type == "email")
        )
        config = result.scalar_one_or_none()

        if not config:
            return None

        # Decrypt sensitive fields
        decrypted = dict(config.config)
        for field in config.encrypted_fields or []:
            if field in decrypted and decrypted[field]:
                try:
                    decrypted[field] = decrypt_value(decrypted[field])
                except Exception:
                    pass  # Keep encrypted if decryption fails

        return decrypted

    async def save_config(self, config: Dict[str, Any]) -> None:
        """Save email configuration."""
        # Encrypt sensitive fields
        encrypted = dict(config)
        encrypted_fields = []

        sensitive_fields = ["smtp_password", "api_key"]
        for field in sensitive_fields:
            if field in encrypted and encrypted[field]:
                encrypted[field] = encrypt_value(encrypted[field])
                encrypted_fields.append(field)

        # Get or create config
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.config_type == "email")
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.config = encrypted
            existing.encrypted_fields = encrypted_fields
            existing.updated_at = datetime.now(UTC)
        else:
            new_config = SystemConfig(
                config_type="email",
                config=encrypted,
                encrypted_fields=encrypted_fields,
            )
            self.db.add(new_config)

        await self.db.commit()
        self._config = None  # Clear cached config

    async def _get_sender(self):
        """Get configured email sender."""
        if self._sender is not None:
            return self._sender

        config = await self.get_config()
        if not config:
            raise RuntimeError("Email not configured")

        try:
            provider = config.get("provider")

            if provider == "gmail_relay":
                self._sender = build_email_sender("smtp-relay.gmail.com", 587, use_starttls=True)
            elif provider == "gmail_app_password":
                self._sender = build_email_sender(
                    "smtp.gmail.com",
                    587,
                    username=config.get("smtp_username"),
                    password=config.get("smtp_password"),
                    use_starttls=True,
                )
            elif provider == "smtp":
                self._sender = build_email_sender(
                    config["smtp_host"],
                    config.get("smtp_port", 587),
                    username=config.get("smtp_username"),
                    password=config.get("smtp_password"),
                    use_starttls=config.get("use_tls", True),
                    use_ssl=config.get("use_ssl"),
                )
            elif provider == "sendgrid":
                self._sender = build_email_sender(
                    "smtp.sendgrid.net",
                    587,
                    username="apikey",
                    password=config.get("api_key"),
                    use_starttls=True,
                )
            else:
                raise ValueError(f"Unsupported email provider: {provider}")

            self._config = config
            return self._sender

        except ImportError:
            raise RuntimeError("redmail package not installed")

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> bool:
        """Send an email."""
        sender = await self._get_sender()
        config = self._config

        from_email = config.get("from_email", "noreply@example.com")
        from_name = config.get("from_name", "n8n Management")

        try:
            # smtplib is blocking; keep it off the event loop
            await asyncio.to_thread(
                sender.send,
                sender=f"{from_name} <{from_email}>",
                receivers=[to],
                subject=subject,
                html=html,
                text=text,
            )
            logger.info(f"Email sent to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            raise

    async def test(self, recipient: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Send test email and record result."""
        config = await self.get_config()
        start_time = time.time()

        try:
            await self.send(
                to=recipient,
                subject="n8n Management - Test Email",
                html="""
                <h1>Test Email Successful</h1>
                <p>Your email configuration is working correctly.</p>
                <p>This is a test email from n8n Management System.</p>
                """,
                text="Test Email Successful\n\nYour email configuration is working correctly.",
            )

            response_time = int((time.time() - start_time) * 1000)

            # Record success
            history = EmailTestHistory(
                provider=config.get("provider", "unknown"),
                provider_config={
                    "host": config.get("smtp_host"),
                    "port": config.get("smtp_port"),
                },
                recipient=recipient,
                status="success",
                response_time_ms=response_time,
                tested_by=user_id,
            )
            self.db.add(history)
            await self.db.commit()

            return {
                "status": "success",
                "response_time_ms": response_time,
            }

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)

            # Record failure
            history = EmailTestHistory(
                provider=config.get("provider", "unknown") if config else "unknown",
                recipient=recipient,
                status="failed",
                response_time_ms=response_time,
                error_message=str(e),
                tested_by=user_id,
            )
            self.db.add(history)
            await self.db.commit()

            return {
                "status": "failed",
                "response_time_ms": response_time,
                "error_message": str(e),
            }

    # Template management

    async def get_templates(self) -> List[EmailTemplate]:
        """Get all email templates."""
        result = await self.db.execute(
            select(EmailTemplate).order_by(EmailTemplate.category, EmailTemplate.name)
        )
        return list(result.scalars().all())

    async def get_template(self, template_key: str) -> Optional[EmailTemplate]:
        """Get email template by key."""
        result = await self.db.execute(
            select(EmailTemplate).where(EmailTemplate.template_key == template_key)
        )
        return result.scalar_one_or_none()

    async def update_template(self, template_key: str, **updates) -> Optional[EmailTemplate]:
        """Update email template."""
        template = await self.get_template(template_key)
        if not template:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def send_template(
        self,
        to: str,
        template_key: str,
        variables: Dict[str, Any],
    ) -> bool:
        """Send email using template."""
        template = await self.get_template(template_key)
        if not template or not template.enabled:
            raise ValueError(f"Template '{template_key}' not found or disabled")

        # Render template
        subject = self._render(template.subject, variables)
        html = self._render(template.html_body, variables)
        text = self._render(template.text_body, variables) if template.text_body else None

        return await self.send(to, subject, html, text)

    def _render(self, template: str, variables: Dict[str, Any]) -> str:
        """Simple variable substitution in template."""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    async def preview_template(
        self,
        template_key: str,
        variables: Dict[str, Any],
    ) -> Dict[str, str]:
        """Preview rendered template."""
        template = await self.get_template(template_key)
        if not template:
            raise ValueError(f"Template '{template_key}' not found")

        return {
            "subject": self._render(template.subject, variables),
            "html_body": self._render(template.html_body, variables),
            "text_body": self._render(template.text_body, variables) if template.text_body else None,
        }

    async def get_test_history(self, limit: int = 20) -> List[EmailTestHistory]:
        """Get email test history."""
        result = await self.db.execute(
            select(EmailTestHistory)
            .order_by(EmailTestHistory.tested_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def create_default_templates(db: AsyncSession) -> None:
    """Create default email templates if they don't exist."""
    default_templates = [
        {
            "template_key": "backup_success",
            "name": "Backup Success",
            "category": "backup",
            "subject": "Backup Completed: {{backup_type}}",
            "html_body": """
            <h2>Backup Completed Successfully</h2>
            <p>A backup has completed successfully.</p>
            <ul>
                <li><strong>Type:</strong> {{backup_type}}</li>
                <li><strong>Filename:</strong> {{filename}}</li>
                <li><strong>Size:</strong> {{size_mb}} MB</li>
                <li><strong>Duration:</strong> {{duration_seconds}} seconds</li>
            </ul>
            """,
            "text_body": "Backup Completed: {{backup_type}}\nFilename: {{filename}}\nSize: {{size_mb}} MB",
            "variables": {"backup_type": "string", "filename": "string", "size_mb": "number", "duration_seconds": "number"},
        },
        {
            "template_key": "backup_failed",
            "name": "Backup Failed",
            "category": "backup",
            "subject": "Backup FAILED: {{backup_type}}",
            "html_body": """
            <h2 style="color: red;">Backup Failed</h2>
            <p>A backup has failed.</p>
            <ul>
                <li><strong>Type:</strong> {{backup_type}}</li>
                <li><strong>Error:</strong> {{error}}</li>
            </ul>
            <p>Please investigate immediately.</p>
            """,
            "text_body": "Backup FAILED: {{backup_type}}\nError: {{error}}",
            "variables": {"backup_type": "string", "error": "string"},
        },
        {
            "template_key": "container_alert",
            "name": "Container Alert",
            "category": "system",
            "subject": "Container Alert: {{container}}",
            "html_body": """
            <h2>Container Alert</h2>
            <p>A container status change has been detected.</p>
            <ul>
                <li><strong>Container:</strong> {{container}}</li>
                <li><strong>Status:</strong> {{status}}</li>
            </ul>
            """,
            "text_body": "Container Alert: {{container}} - {{status}}",
            "variables": {"container": "string", "status": "string"},
        },
        {
            "template_key": "test_email",
            "name": "Test Email",
            "category": "system",
            "subject": "n8n Management - Test Email",
            "html_body": """
            <h1>Test Email Successful</h1>
            <p>Your email configuration is working correctly.</p>
            """,
            "text_body": "Test Email Successful\nYour email configuration is working correctly.",
            "variables": {},
        },
    ]

    for template_data in default_templates:
        result = await db.execute(
            select(EmailTemplate).where(EmailTemplate.template_key == template_data["template_key"])
        )
        existing = result.scalar_one_or_none()

        if not existing:
            template = EmailTemplate(**template_data)
            db.add(template)

    await db.commit()
