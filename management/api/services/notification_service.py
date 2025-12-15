"""
Notification service - handles sending notifications via multiple channels.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any
import logging
import asyncio
import re

from api.models.notifications import (
    NotificationService as NotificationServiceModel,
    NotificationRule,
    NotificationHistory,
    NotificationBatch,
    NotificationGroup,
    NotificationGroupMembership,
    generate_slug,
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

            # Map priority to numeric values for JSON API
            priority_map = {
                "low": 2,
                "normal": 3,
                "high": 4,
                "critical": 5,
            }

            # Use JSON body to properly handle Unicode/emojis
            headers = {
                "Content-Type": "application/json",
            }

            if config.get("token"):
                headers["Authorization"] = f"Bearer {config['token']}"

            # Build JSON payload - this properly handles UTF-8 encoding
            payload = {
                "topic": topic,
                "message": body,
                "title": title,
                "priority": priority_map.get(priority, 3),
            }

            if config.get("tags"):
                # Filter tags to only include valid shortcodes (alphanumeric, underscores)
                # NTFY uses shortcodes like 'warning', 'dart', 'rocket' - not actual emoji chars
                valid_tags = [
                    tag for tag in config["tags"]
                    if isinstance(tag, str) and re.match(r'^[a-zA-Z0-9_+-]+$', tag)
                ]
                if valid_tags:
                    payload["tags"] = valid_tags

            logger.debug(f"Sending NTFY notification to {server}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    server,
                    json=payload,
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
        slug: str = None,
    ) -> NotificationServiceModel:
        """Create a notification service."""
        # Generate slug if not provided
        if not slug:
            slug = generate_slug(name)

        # Ensure slug is unique
        slug = await self._ensure_unique_slug(slug)

        service = NotificationServiceModel(
            name=name,
            slug=slug,
            service_type=service_type,
            config=config,
            enabled=enabled,
            webhook_enabled=webhook_enabled,
            priority=priority,
        )
        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)
        logger.info(f"Created notification service: {name} ({service_type}) with slug: {slug}")
        return service

    async def _ensure_unique_slug(self, base_slug: str, exclude_id: int = None) -> str:
        """Ensure slug is unique across services."""
        slug = base_slug
        counter = 1

        while True:
            query = select(NotificationServiceModel).where(NotificationServiceModel.slug == slug)
            if exclude_id:
                query = query.where(NotificationServiceModel.id != exclude_id)

            result = await self.db.execute(query)
            if result.scalar_one_or_none() is None:
                return slug

            slug = f"{base_slug}_{counter}"
            counter += 1

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

        error_msg = None
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
            if not success:
                error_msg = "Send returned false"

        except Exception as e:
            success = False
            error_msg = str(e)
            service.last_test = datetime.now(UTC)
            service.last_test_result = "failed"
            service.last_test_error = str(e)

        # Log to notification history
        now = datetime.now(UTC)
        history = NotificationHistory(
            event_type="service.test",
            event_data={"title": title, "message": message},
            severity="info",
            service_id=service.id,
            service_name=service.name,
            rule_id=None,
            status="sent" if success else "failed",
            sent_at=now if success else None,
            error_message=error_msg,
        )
        self.db.add(history)
        await self.db.commit()

        if not success:
            return {"success": False, "error": error_msg}
        return {"success": True}

    # Group management

    async def get_groups(self) -> List[NotificationGroup]:
        """Get all notification groups with memberships eagerly loaded."""
        result = await self.db.execute(
            select(NotificationGroup)
            .options(selectinload(NotificationGroup.memberships).selectinload(NotificationGroupMembership.service))
            .order_by(NotificationGroup.name)
        )
        return list(result.scalars().all())

    async def get_group(self, group_id: int) -> Optional[NotificationGroup]:
        """Get notification group by ID with memberships eagerly loaded."""
        result = await self.db.execute(
            select(NotificationGroup)
            .options(selectinload(NotificationGroup.memberships).selectinload(NotificationGroupMembership.service))
            .where(NotificationGroup.id == group_id)
        )
        return result.scalar_one_or_none()

    async def get_group_by_slug(self, slug: str) -> Optional[NotificationGroup]:
        """Get notification group by slug with memberships eagerly loaded."""
        result = await self.db.execute(
            select(NotificationGroup)
            .options(selectinload(NotificationGroup.memberships).selectinload(NotificationGroupMembership.service))
            .where(NotificationGroup.slug == slug)
        )
        return result.scalar_one_or_none()

    async def _ensure_unique_group_slug(self, base_slug: str, exclude_id: int = None) -> str:
        """Ensure group slug is unique."""
        slug = base_slug
        counter = 1

        while True:
            query = select(NotificationGroup).where(NotificationGroup.slug == slug)
            if exclude_id:
                query = query.where(NotificationGroup.id != exclude_id)

            result = await self.db.execute(query)
            if result.scalar_one_or_none() is None:
                return slug

            slug = f"{base_slug}_{counter}"
            counter += 1

    async def create_group(
        self,
        name: str,
        channel_ids: List[int],
        description: str = None,
        enabled: bool = True,
        slug: str = None,
    ) -> NotificationGroup:
        """Create a notification group with channels."""
        # Generate slug if not provided
        if not slug:
            slug = generate_slug(name)

        # Ensure slug is unique
        slug = await self._ensure_unique_group_slug(slug)

        # Verify all channel IDs exist
        for channel_id in channel_ids:
            service = await self.get_service(channel_id)
            if not service:
                raise ValueError(f"Channel with ID {channel_id} not found")

        group = NotificationGroup(
            name=name,
            slug=slug,
            description=description,
            enabled=enabled,
        )
        self.db.add(group)
        await self.db.flush()  # Get the group ID

        # Add channel memberships
        for channel_id in channel_ids:
            membership = NotificationGroupMembership(
                group_id=group.id,
                service_id=channel_id,
            )
            self.db.add(membership)

        await self.db.commit()
        await self.db.refresh(group)
        logger.info(f"Created notification group: {name} with slug: {slug}, {len(channel_ids)} channels")
        return group

    async def update_group(
        self,
        group_id: int,
        name: str = None,
        slug: str = None,
        description: str = None,
        enabled: bool = None,
        channel_ids: List[int] = None,
    ) -> Optional[NotificationGroup]:
        """Update a notification group."""
        group = await self.get_group(group_id)
        if not group:
            return None

        if name is not None:
            group.name = name

        if slug is not None:
            # Ensure new slug is unique
            slug = await self._ensure_unique_group_slug(slug, exclude_id=group_id)
            group.slug = slug

        if description is not None:
            group.description = description

        if enabled is not None:
            group.enabled = enabled

        if channel_ids is not None:
            # Verify all channel IDs exist
            for channel_id in channel_ids:
                service = await self.get_service(channel_id)
                if not service:
                    raise ValueError(f"Channel with ID {channel_id} not found")

            # Remove existing memberships
            await self.db.execute(
                delete(NotificationGroupMembership).where(
                    NotificationGroupMembership.group_id == group_id
                )
            )

            # Add new memberships
            for channel_id in channel_ids:
                membership = NotificationGroupMembership(
                    group_id=group_id,
                    service_id=channel_id,
                )
                self.db.add(membership)

        group.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def delete_group(self, group_id: int) -> bool:
        """Delete a notification group."""
        result = await self.db.execute(
            delete(NotificationGroup).where(NotificationGroup.id == group_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def get_groups_for_service(self, service_id: int) -> List[NotificationGroup]:
        """Get all groups that contain a specific service."""
        result = await self.db.execute(
            select(NotificationGroup)
            .join(NotificationGroupMembership, NotificationGroupMembership.group_id == NotificationGroup.id)
            .where(NotificationGroupMembership.service_id == service_id)
        )
        return list(result.scalars().all())

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

    async def get_service_by_slug(self, slug: str) -> Optional[NotificationServiceModel]:
        """Get a notification service by its slug."""
        result = await self.db.execute(
            select(NotificationServiceModel).where(NotificationServiceModel.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_services_in_group(self, group_slug: str) -> List[NotificationServiceModel]:
        """Get all services in a group by the group's slug."""
        result = await self.db.execute(
            select(NotificationServiceModel)
            .join(NotificationGroupMembership, NotificationGroupMembership.service_id == NotificationServiceModel.id)
            .join(NotificationGroup, NotificationGroup.id == NotificationGroupMembership.group_id)
            .where(NotificationGroup.slug == group_slug)
            .where(NotificationGroup.enabled == True)
        )
        return list(result.scalars().all())

    async def resolve_targets(self, targets: List[str]) -> Dict[str, Any]:
        """
        Resolve target specifications to actual services.

        Returns:
            {
                "services": List[NotificationServiceModel],  # Deduplicated services
                "targets_resolved": Dict[str, List[str]],    # Map of target -> resolved channel names
                "errors": List[str]                          # Any resolution errors
            }
        """
        services_map: Dict[int, NotificationServiceModel] = {}  # id -> service (for dedup)
        targets_resolved: Dict[str, List[str]] = {}
        errors: List[str] = []

        for target in targets:
            target = target.strip().lower()

            if target == "all":
                # Send to all webhook-enabled channels
                all_services = await self.get_webhook_enabled_services()
                targets_resolved["all"] = [s.name for s in all_services]
                for s in all_services:
                    services_map[s.id] = s

            elif target.startswith("channel:"):
                # Target a specific channel by slug
                slug = target[8:]  # Remove "channel:" prefix
                service = await self.get_service_by_slug(slug)
                if service:
                    if service.enabled and service.webhook_enabled:
                        services_map[service.id] = service
                        targets_resolved[target] = [service.name]
                    else:
                        errors.append(f"Channel '{slug}' is disabled or not webhook-enabled")
                        targets_resolved[target] = []
                else:
                    errors.append(f"Channel '{slug}' not found")
                    targets_resolved[target] = []

            elif target.startswith("group:"):
                # Target all channels in a group
                slug = target[6:]  # Remove "group:" prefix
                group_services = await self.get_services_in_group(slug)
                if group_services:
                    resolved_names = []
                    for s in group_services:
                        if s.enabled and s.webhook_enabled:
                            services_map[s.id] = s
                            resolved_names.append(s.name)
                    targets_resolved[target] = resolved_names
                    if not resolved_names:
                        errors.append(f"Group '{slug}' has no enabled webhook channels")
                else:
                    # Check if group exists but is empty
                    group = await self.get_group_by_slug(slug)
                    if group:
                        errors.append(f"Group '{slug}' has no channels")
                    else:
                        errors.append(f"Group '{slug}' not found")
                    targets_resolved[target] = []

            else:
                errors.append(f"Invalid target format: '{target}'. Use 'all', 'channel:slug', or 'group:slug'")
                targets_resolved[target] = []

        return {
            "services": list(services_map.values()),
            "targets_resolved": targets_resolved,
            "errors": errors,
        }

    async def send_webhook_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        targets: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Send notification to targeted channels.

        Args:
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high, critical)
            targets: List of targets - "all", "channel:slug", or "group:slug"
        """
        if not targets:
            return {
                "success": False,
                "channels_notified": 0,
                "channels": [],
                "targets_resolved": {},
                "errors": ["No targets specified. Use 'all', 'channel:slug', or 'group:slug'"],
            }

        # Resolve targets to services
        resolved = await self.resolve_targets(targets)
        services = resolved["services"]
        targets_resolved = resolved["targets_resolved"]
        errors = resolved["errors"]

        if not services:
            return {
                "success": False,
                "channels_notified": 0,
                "channels": [],
                "targets_resolved": targets_resolved,
                "errors": errors if errors else ["No channels matched the specified targets"],
            }

        channels_notified = []

        for service in services:
            try:
                if service.service_type == "apprise":
                    success = await self.dispatcher.send_apprise(service.config, title, message, priority)
                elif service.service_type == "ntfy":
                    success = await self.dispatcher.send_ntfy(service.config, title, message, priority)
                elif service.service_type == "webhook":
                    success = await self.dispatcher.send_webhook(service.config, title, message, {"source": "n8n_webhook", "targets": targets})
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
                        event_data={"title": title, "message": message[:500], "priority": priority, "targets": targets},
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
                    event_data={"title": title, "message": message[:500], "priority": priority, "targets": targets},
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
            "targets_resolved": targets_resolved,
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

    # Direct send methods (for system notifications)

    async def send_to_service(
        self,
        service_id: int,
        title: str,
        message: str,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """Send notification directly to a specific service."""
        service = await self.get_service(service_id)
        if not service:
            return {"success": False, "error": "Service not found"}

        if not service.enabled:
            return {"success": False, "error": "Service is disabled"}

        try:
            if service.service_type == "apprise":
                success = await self.dispatcher.send_apprise(service.config, title, message, priority)
            elif service.service_type == "ntfy":
                success = await self.dispatcher.send_ntfy(service.config, title, message, priority)
            elif service.service_type == "webhook":
                success = await self.dispatcher.send_webhook(service.config, title, message, {})
            elif service.service_type == "email":
                success = await self.dispatcher.send_email(service.config, title, message, priority)
            else:
                return {"success": False, "error": f"Unsupported service type: {service.service_type}"}

            return {"success": success}

        except Exception as e:
            logger.error(f"Failed to send to service {service_id}: {e}")
            return {"success": False, "error": str(e)}

    async def send_to_group(
        self,
        group_id: int,
        title: str,
        message: str,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """Send notification to all services in a group."""
        group = await self.get_group(group_id)
        if not group:
            return {"success": False, "error": "Group not found", "sent_count": 0}

        if not group.enabled:
            return {"success": False, "error": "Group is disabled", "sent_count": 0}

        sent_count = 0
        errors = []

        for membership in group.memberships:
            service = membership.service
            if not service or not service.enabled:
                continue

            result = await self.send_to_service(service.id, title, message, priority)
            if result.get("success"):
                sent_count += 1
            else:
                errors.append(f"{service.name}: {result.get('error')}")

        return {
            "success": sent_count > 0,
            "sent_count": sent_count,
            "errors": errors if errors else None,
        }

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
