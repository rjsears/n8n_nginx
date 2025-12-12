"""
Notification service - handles sending notifications via multiple channels.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any
import logging
import asyncio

from api.models.notifications import (
    NotificationService as NotificationServiceModel,
    NotificationRule,
    NotificationHistory,
    NotificationBatch,
)
from api.schemas.notifications import NotificationEventType
from api.config import settings

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Handles sending notifications via various services."""

    async def send_apprise(self, config: Dict[str, Any], title: str, body: str, priority: str) -> bool:
        """Send notification via Apprise."""
        try:
            import apprise

            apobj = apprise.Apprise()
            apobj.add(config.get("url"))

            # Map priority to notify type
            notify_type_map = {
                "low": apprise.NotifyType.INFO,
                "normal": apprise.NotifyType.INFO,
                "high": apprise.NotifyType.WARNING,
                "critical": apprise.NotifyType.FAILURE,
            }
            notify_type = notify_type_map.get(priority, apprise.NotifyType.INFO)

            result = await asyncio.to_thread(
                apobj.notify,
                title=title,
                body=body,
                notify_type=notify_type,
            )
            return result

        except Exception as e:
            logger.error(f"Apprise notification failed: {e}")
            raise

    async def send_ntfy(self, config: Dict[str, Any], title: str, body: str, priority: str) -> bool:
        """Send notification via NTFY."""
        try:
            import httpx

            server = config.get("server", "https://ntfy.sh").rstrip("/")
            topic = config.get("topic", "").strip()

            if not topic:
                raise ValueError("NTFY topic is required")

            # Map priority
            priority_map = {
                "low": "low",
                "normal": "default",
                "high": "high",
                "critical": "urgent",
            }

            headers = {
                "Title": title,
                "Priority": priority_map.get(priority, "default"),
            }

            if config.get("tags"):
                headers["Tags"] = ",".join(config["tags"])

            if config.get("token"):
                headers["Authorization"] = f"Bearer {config['token']}"

            url = f"{server}/{topic}"
            logger.debug(f"Sending NTFY notification to {url}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    content=body,
                    headers=headers,
                    timeout=30.0,
                )

                # ntfy returns 200 on success
                if response.status_code == 200:
                    logger.info(f"NTFY notification sent successfully to {topic}")
                    return True
                else:
                    logger.error(f"NTFY notification failed: HTTP {response.status_code} - {response.text}")
                    raise ValueError(f"NTFY returned HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            logger.error(f"NTFY notification failed: {e}")
            raise

    async def send_webhook(self, config: Dict[str, Any], title: str, body: str, event_data: Dict[str, Any]) -> bool:
        """Send notification via webhook."""
        try:
            import httpx

            url = config["url"]
            method = config.get("method", "POST").upper()

            payload = {
                "title": title,
                "message": body,
                "timestamp": datetime.now(UTC).isoformat(),
                "event_data": event_data,
            }

            headers = config.get("headers", {})

            async with httpx.AsyncClient() as client:
                if method == "POST":
                    response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                else:
                    response = await client.get(url, params=payload, headers=headers, timeout=30.0)

                return 200 <= response.status_code < 300

        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            raise

    async def send_email(self, config: Dict[str, Any], title: str, body: str, priority: str) -> bool:
        """Send notification via SMTP email using red-mail."""
        try:
            from redmail import EmailSender

            smtp_server = config.get("smtp_server", "localhost")
            smtp_port = config.get("smtp_port", 587)
            smtp_user = config.get("smtp_user", "")
            smtp_password = config.get("smtp_password", "")
            use_tls = config.get("use_tls", True)
            use_starttls = config.get("use_starttls", True)
            from_email = config.get("from_email", smtp_user or f"n8n@{smtp_server}")
            to_emails = config.get("to_emails", [])

            if isinstance(to_emails, str):
                to_emails = [e.strip() for e in to_emails.split(",") if e.strip()]

            if not to_emails:
                raise ValueError("No recipient email addresses configured")

            # Determine if this is Gmail relay (no auth needed with IP whitelist)
            is_gmail_relay = "gmail" in smtp_server.lower() and not smtp_user

            # Create email sender with appropriate configuration
            if is_gmail_relay:
                # Gmail relay with IP whitelisting - no auth needed
                email = EmailSender(
                    host=smtp_server,
                    port=smtp_port,
                    use_starttls=use_starttls,
                )
            elif smtp_user and smtp_password:
                # Authenticated SMTP
                email = EmailSender(
                    host=smtp_server,
                    port=smtp_port,
                    username=smtp_user,
                    password=smtp_password,
                    use_starttls=use_starttls if use_tls else False,
                )
            else:
                # Unauthenticated SMTP (internal mail servers)
                email = EmailSender(
                    host=smtp_server,
                    port=smtp_port,
                    use_starttls=use_starttls if use_tls else False,
                )

            # Build HTML body with simple formatting
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">{title}</h2>
                <p style="color: #555; line-height: 1.6;">{body.replace(chr(10), '<br>')}</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">
                    This is an automated notification from n8n Management Console.
                </p>
            </body>
            </html>
            """

            # Set priority headers
            headers = {}
            if priority == "critical":
                headers["X-Priority"] = "1"
                headers["Importance"] = "high"
            elif priority == "high":
                headers["X-Priority"] = "2"
                headers["Importance"] = "high"

            # Send email using red-mail (blocking call wrapped in thread)
            def _send():
                email.send(
                    subject=title,
                    sender=from_email,
                    receivers=to_emails,
                    text=body,
                    html=html_body,
                    headers=headers if headers else None,
                )
                return True

            result = await asyncio.to_thread(_send)
            return result

        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            raise


class NotificationService:
    """Notification management service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.dispatcher = NotificationDispatcher()

    # Service management

    async def get_services(self) -> List[NotificationServiceModel]:
        """Get all notification services."""
        result = await self.db.execute(
            select(NotificationServiceModel).order_by(NotificationServiceModel.priority.desc())
        )
        return list(result.scalars().all())

    async def get_service(self, service_id: int) -> Optional[NotificationServiceModel]:
        """Get notification service by ID."""
        result = await self.db.execute(
            select(NotificationServiceModel).where(NotificationServiceModel.id == service_id)
        )
        return result.scalar_one_or_none()

    async def create_service(
        self,
        name: str,
        service_type: str,
        config: Dict[str, Any],
        enabled: bool = True,
        webhook_enabled: bool = False,
        priority: int = 0,
    ) -> NotificationServiceModel:
        """Create a notification service."""
        service = NotificationServiceModel(
            name=name,
            service_type=service_type,
            config=config,
            enabled=enabled,
            webhook_enabled=webhook_enabled,
            priority=priority,
        )
        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)
        logger.info(f"Created notification service: {name} ({service_type})")
        return service

    async def update_service(
        self,
        service_id: int,
        **updates,
    ) -> Optional[NotificationServiceModel]:
        """Update a notification service."""
        service = await self.get_service(service_id)
        if not service:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(service, key):
                setattr(service, key, value)

        service.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def delete_service(self, service_id: int) -> bool:
        """Delete a notification service."""
        result = await self.db.execute(
            delete(NotificationServiceModel).where(NotificationServiceModel.id == service_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def test_service(self, service_id: int, title: str, message: str) -> Dict[str, Any]:
        """Test a notification service."""
        service = await self.get_service(service_id)
        if not service:
            return {"success": False, "error": "Service not found"}

        try:
            if service.service_type == "apprise":
                success = await self.dispatcher.send_apprise(service.config, title, message, "normal")
            elif service.service_type == "ntfy":
                success = await self.dispatcher.send_ntfy(service.config, title, message, "normal")
            elif service.service_type == "webhook":
                success = await self.dispatcher.send_webhook(service.config, title, message, {})
            elif service.service_type == "email":
                success = await self.dispatcher.send_email(service.config, title, message, "normal")
            else:
                return {"success": False, "error": f"Unsupported service type: {service.service_type}"}

            # Update test status
            service.last_test = datetime.now(UTC)
            service.last_test_result = "success" if success else "failed"
            service.last_test_error = None if success else "Send returned false"
            await self.db.commit()

            return {"success": success}

        except Exception as e:
            service.last_test = datetime.now(UTC)
            service.last_test_result = "failed"
            service.last_test_error = str(e)
            await self.db.commit()

            return {"success": False, "error": str(e)}

    # Webhook routing

    async def get_webhook_enabled_services(self) -> List[NotificationServiceModel]:
        """Get all services with webhook routing enabled."""
        result = await self.db.execute(
            select(NotificationServiceModel)
            .where(NotificationServiceModel.webhook_enabled == True)
            .where(NotificationServiceModel.enabled == True)
            .order_by(NotificationServiceModel.priority.desc())
        )
        return list(result.scalars().all())

    async def send_webhook_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """
        Send notification to all webhook-enabled services.
        Used by n8n workflows to send notifications without configuring each channel.
        """
        services = await self.get_webhook_enabled_services()

        if not services:
            return {
                "success": False,
                "channels_notified": 0,
                "channels": [],
                "errors": ["No webhook-enabled notification channels configured"],
            }

        channels_notified = []
        errors = []

        for service in services:
            try:
                if service.service_type == "apprise":
                    success = await self.dispatcher.send_apprise(service.config, title, message, priority)
                elif service.service_type == "ntfy":
                    success = await self.dispatcher.send_ntfy(service.config, title, message, priority)
                elif service.service_type == "webhook":
                    success = await self.dispatcher.send_webhook(service.config, title, message, {"source": "n8n_webhook"})
                elif service.service_type == "email":
                    success = await self.dispatcher.send_email(service.config, title, message, priority)
                else:
                    success = False
                    errors.append(f"{service.name}: Unsupported service type")

                if success:
                    channels_notified.append(service.name)
                    # Log to history
                    history = NotificationHistory(
                        event_type="webhook.notification",
                        event_data={"title": title, "message": message[:500], "priority": priority},
                        severity=priority,
                        service_id=service.id,
                        service_name=service.name,
                        rule_id=None,
                        status="sent",
                        sent_at=datetime.now(UTC),
                    )
                    self.db.add(history)
                else:
                    errors.append(f"{service.name}: Send returned false")

            except Exception as e:
                logger.error(f"Webhook notification failed for {service.name}: {e}")
                errors.append(f"{service.name}: {str(e)}")
                # Log failure to history
                history = NotificationHistory(
                    event_type="webhook.notification",
                    event_data={"title": title, "message": message[:500], "priority": priority},
                    severity=priority,
                    service_id=service.id,
                    service_name=service.name,
                    rule_id=None,
                    status="failed",
                    error_message=str(e),
                )
                self.db.add(history)

        await self.db.commit()

        return {
            "success": len(channels_notified) > 0,
            "channels_notified": len(channels_notified),
            "channels": channels_notified,
            "errors": errors,
        }

    # Rule management

    async def get_rules(self, event_type: Optional[str] = None) -> List[NotificationRule]:
        """Get notification rules, optionally filtered by event type."""
        query = select(NotificationRule).order_by(NotificationRule.sort_order)
        if event_type:
            query = query.where(NotificationRule.event_type == event_type)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_rule(self, rule_id: int) -> Optional[NotificationRule]:
        """Get notification rule by ID."""
        result = await self.db.execute(
            select(NotificationRule).where(NotificationRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def create_rule(self, **kwargs) -> NotificationRule:
        """Create a notification rule."""
        rule = NotificationRule(**kwargs)
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update_rule(self, rule_id: int, **updates) -> Optional[NotificationRule]:
        """Update a notification rule."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: int) -> bool:
        """Delete a notification rule."""
        result = await self.db.execute(
            delete(NotificationRule).where(NotificationRule.id == rule_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    # Event dispatching

    async def dispatch(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        severity: str = "info",
    ) -> List[int]:
        """
        Dispatch notification for an event.
        Returns list of notification history IDs.
        """
        history_ids = []

        # Get matching rules
        rules = await self.get_rules(event_type)
        enabled_rules = [r for r in rules if r.enabled]

        for rule in enabled_rules:
            # Check cooldown
            if rule.cooldown_minutes > 0 and rule.last_triggered:
                cooldown_until = rule.last_triggered + timedelta(minutes=rule.cooldown_minutes)
                if datetime.now(UTC) < cooldown_until:
                    logger.debug(f"Rule {rule.id} in cooldown, skipping")
                    continue

            # Get service
            service = await self.get_service(rule.service_id)
            if not service or not service.enabled:
                continue

            # Build message
            title = rule.custom_title or self._get_default_title(event_type)
            body = rule.custom_message or self._get_default_message(event_type, event_data)

            if rule.include_details:
                body += self._format_event_details(event_data)

            # Send notification
            history_id = await self._send_and_log(
                service=service,
                rule=rule,
                event_type=event_type,
                event_data=event_data,
                severity=severity,
                title=title,
                body=body,
            )
            history_ids.append(history_id)

            # Update rule last triggered
            rule.last_triggered = datetime.now(UTC)
            await self.db.commit()

        return history_ids

    async def _send_and_log(
        self,
        service: NotificationServiceModel,
        rule: NotificationRule,
        event_type: str,
        event_data: Dict[str, Any],
        severity: str,
        title: str,
        body: str,
    ) -> int:
        """Send notification and log to history."""
        history = NotificationHistory(
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            service_id=service.id,
            service_name=service.name,
            rule_id=rule.id,
            status="pending",
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        try:
            if service.service_type == "apprise":
                success = await self.dispatcher.send_apprise(service.config, title, body, rule.priority)
            elif service.service_type == "ntfy":
                success = await self.dispatcher.send_ntfy(service.config, title, body, rule.priority)
            elif service.service_type == "webhook":
                success = await self.dispatcher.send_webhook(service.config, title, body, event_data)
            elif service.service_type == "email":
                success = await self.dispatcher.send_email(service.config, title, body, rule.priority)
            else:
                success = False

            history.status = "sent" if success else "failed"
            history.sent_at = datetime.now(UTC)

        except Exception as e:
            history.status = "failed"
            history.error_message = str(e)
            logger.error(f"Notification failed: {e}")

        await self.db.commit()
        return history.id

    def _get_default_title(self, event_type: str) -> str:
        """Get default title for event type."""
        titles = {
            "backup.success": "Backup Completed Successfully",
            "backup.failed": "Backup Failed",
            "backup.started": "Backup Started",
            "container.unhealthy": "Container Unhealthy",
            "container.stopped": "Container Stopped",
            "system.disk_warning": "Disk Space Warning",
            "system.disk_critical": "Disk Space Critical",
        }
        return titles.get(event_type, f"n8n Alert: {event_type}")

    def _get_default_message(self, event_type: str, event_data: Dict[str, Any]) -> str:
        """Get default message for event type."""
        return f"Event: {event_type}"

    def _format_event_details(self, event_data: Dict[str, Any]) -> str:
        """Format event data as readable text."""
        if not event_data:
            return ""

        lines = ["\n\nDetails:"]
        for key, value in event_data.items():
            lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    # History

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[NotificationHistory]:
        """Get notification history."""
        query = select(NotificationHistory).order_by(NotificationHistory.created_at.desc())

        if event_type:
            query = query.where(NotificationHistory.event_type == event_type)
        if status:
            query = query.where(NotificationHistory.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())


# Global dispatcher for use outside of request context
async def dispatch_notification(
    event_type: str,
    event_data: Dict[str, Any],
    severity: str = "info",
) -> None:
    """Dispatch notification (convenience function)."""
    from api.database import async_session_maker

    async with async_session_maker() as db:
        service = NotificationService(db)
        await service.dispatch(event_type, event_data, severity)
