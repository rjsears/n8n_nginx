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
    """
    Dispatch notification using System Notifications configuration.

    This looks up the event in SystemNotificationEvent and sends to all
    configured targets (channels/groups) in SystemNotificationTarget.

    Features:
    - Per-container configuration checking
    - Cooldown enforcement
    - L1/L2 escalation support
    - History logging
    """
    from api.database import async_session_maker
    from api.models.system_notifications import (
        SystemNotificationEvent,
        SystemNotificationTarget,
        SystemNotificationGlobalSettings,
        SystemNotificationContainerConfig,
        SystemNotificationState,
        SystemNotificationHistory,
    )

    async with async_session_maker() as db:
        # Check global settings for maintenance mode
        settings_result = await db.execute(
            select(SystemNotificationGlobalSettings).limit(1)
        )
        global_settings = settings_result.scalar_one_or_none()

        if global_settings and global_settings.maintenance_mode:
            logger.debug(f"Notifications suppressed - maintenance mode active")
            return

        # For container events, check per-container configuration
        container_name = event_data.get("container") or event_data.get("container_name")
        if container_name and event_type.startswith("container_"):
            config_result = await db.execute(
                select(SystemNotificationContainerConfig).where(
                    SystemNotificationContainerConfig.container_name == container_name
                )
            )
            container_config = config_result.scalar_one_or_none()

            if container_config:
                # Check if monitoring is enabled for this container
                if not container_config.enabled:
                    logger.debug(f"Notifications disabled for container '{container_name}'")
                    return

                # Check specific event type settings
                event_checks = {
                    "container_stopped": container_config.monitor_stopped,
                    "container_unhealthy": container_config.monitor_unhealthy,
                    "container_restart": container_config.monitor_restart,
                    "container_restarted": container_config.monitor_restart,
                    "container_high_cpu": container_config.monitor_high_cpu,
                    "container_high_memory": container_config.monitor_high_memory,
                }

                if event_type in event_checks and not event_checks[event_type]:
                    logger.debug(f"Event '{event_type}' disabled for container '{container_name}'")
                    return

        # Look up the system notification event
        result = await db.execute(
            select(SystemNotificationEvent).where(
                SystemNotificationEvent.event_type == event_type
            )
        )
        event = result.scalar_one_or_none()

        if not event:
            logger.debug(f"No SystemNotificationEvent found for event_type: {event_type}")
            return

        if not event.enabled:
            logger.debug(f"SystemNotificationEvent '{event_type}' is disabled")
            return

        # Check cooldown
        target_id = container_name or event_data.get("target_id") or "global"
        state_result = await db.execute(
            select(SystemNotificationState).where(
                SystemNotificationState.event_type == event_type,
                SystemNotificationState.target_id == target_id
            )
        )
        state = state_result.scalar_one_or_none()

        now = datetime.now(UTC)

        if event.cooldown_minutes and event.cooldown_minutes > 0 and state and state.last_sent_at:
            cooldown_until = state.last_sent_at + timedelta(minutes=event.cooldown_minutes)
            if now < cooldown_until:
                remaining = (cooldown_until - now).total_seconds() / 60
                logger.debug(f"Event '{event_type}' in cooldown for {remaining:.1f} more minutes")
                # Log suppressed notification
                history = SystemNotificationHistory(
                    event_type=event_type,
                    event_id=event.id,
                    target_id=target_id,
                    target_label=event_data.get("container") or event_type,
                    severity=event.severity,
                    event_data=event_data,
                    status="suppressed",
                    suppression_reason=f"cooldown ({event.cooldown_minutes}min)",
                    triggered_at=now,
                )
                db.add(history)
                await db.commit()
                return

        # Get L1 targets for this event (immediate delivery)
        targets_result = await db.execute(
            select(SystemNotificationTarget).where(
                SystemNotificationTarget.event_id == event.id,
                SystemNotificationTarget.escalation_level == 1
            )
        )
        l1_targets = targets_result.scalars().all()

        # Get L2 targets (escalation)
        l2_targets_result = await db.execute(
            select(SystemNotificationTarget).where(
                SystemNotificationTarget.event_id == event.id,
                SystemNotificationTarget.escalation_level == 2
            )
        )
        l2_targets = l2_targets_result.scalars().all()

        if not l1_targets and not l2_targets:
            logger.debug(f"No targets configured for event '{event_type}'")
            return

        # Build notification title and message
        title = f"{event.display_name}"
        message = _build_notification_message(event_type, event_data)

        # Map severity to priority
        priority_map = {
            "info": "normal",
            "warning": "high",
            "critical": "critical",
            "error": "critical",
        }
        priority = priority_map.get(event.severity, "normal")

        # Create notification service instance
        notification_service = NotificationService(db)

        sent_count = 0
        channels_sent = []

        # Send to L1 targets immediately
        for target in l1_targets:
            try:
                if target.target_type == "channel" and target.channel_id:
                    result = await notification_service.send_to_service(
                        target.channel_id, title, message, priority
                    )
                    if result.get("success"):
                        sent_count += 1
                        channels_sent.append({"type": "channel", "id": target.channel_id, "level": 1})
                        logger.info(f"Sent '{event_type}' notification to L1 channel {target.channel_id}")
                    else:
                        logger.error(f"Failed to send to channel {target.channel_id}: {result.get('error')}")

                elif target.target_type == "group" and target.group_id:
                    result = await notification_service.send_to_group(
                        target.group_id, title, message, priority
                    )
                    if result.get("success"):
                        sent_count += result.get("sent_count", 1)
                        channels_sent.append({"type": "group", "id": target.group_id, "level": 1})
                        logger.info(f"Sent '{event_type}' notification to L1 group {target.group_id}")
                    else:
                        logger.error(f"Failed to send to group {target.group_id}: {result.get('error')}")

            except Exception as e:
                logger.error(f"Error sending notification to L1 target {target.id}: {e}")

        # Handle L2 escalation
        if l2_targets:
            # For critical events or L1 failures, send L2 immediately
            if event.severity == "critical" or sent_count == 0:
                for target in l2_targets:
                    try:
                        if target.target_type == "channel" and target.channel_id:
                            escalation_title = f"[ESCALATED] {title}"
                            result = await notification_service.send_to_service(
                                target.channel_id, escalation_title, message, "critical"
                            )
                            if result.get("success"):
                                sent_count += 1
                                channels_sent.append({"type": "channel", "id": target.channel_id, "level": 2})
                                logger.info(f"Sent '{event_type}' escalation to L2 channel {target.channel_id}")

                        elif target.target_type == "group" and target.group_id:
                            escalation_title = f"[ESCALATED] {title}"
                            result = await notification_service.send_to_group(
                                target.group_id, escalation_title, message, "critical"
                            )
                            if result.get("success"):
                                sent_count += result.get("sent_count", 1)
                                channels_sent.append({"type": "group", "id": target.group_id, "level": 2})
                                logger.info(f"Sent '{event_type}' escalation to L2 group {target.group_id}")

                    except Exception as e:
                        logger.error(f"Error sending notification to L2 target {target.id}: {e}")

                # Mark escalation as sent immediately
                if state:
                    state.escalation_sent = True
                    state.escalation_triggered_at = now
            else:
                # Schedule L2 escalation for later (time-delayed)
                # Get timeout from first L2 target or use event default
                timeout_minutes = l2_targets[0].escalation_timeout_minutes or event.escalation_timeout_minutes or 30
                try:
                    from api.tasks.scheduler import schedule_l2_escalation
                    await schedule_l2_escalation(
                        event_type=event_type,
                        event_data=event_data,
                        event_id=event.id,
                        target_id=target_id,
                        timeout_minutes=timeout_minutes,
                    )
                    logger.info(f"L2 escalation scheduled for '{event_type}' in {timeout_minutes} minutes")
                except Exception as e:
                    logger.error(f"Failed to schedule L2 escalation: {e}")

        # Update state for cooldown tracking
        if state:
            state.last_sent_at = now
            state.updated_at = now
        else:
            state = SystemNotificationState(
                event_type=event_type,
                target_id=target_id,
                last_sent_at=now,
            )
            db.add(state)

        # Log to SystemNotificationHistory (for system notifications settings page)
        system_history = SystemNotificationHistory(
            event_type=event_type,
            event_id=event.id,
            target_id=target_id,
            target_label=event_data.get("container") or event_type,
            severity=event.severity,
            event_data=event_data,
            channels_sent=channels_sent,
            escalation_level=2 if l2_targets and sent_count > len(l1_targets) else 1,
            status="sent" if sent_count > 0 else "failed",
            triggered_at=now,
            sent_at=now if sent_count > 0 else None,
        )
        db.add(system_history)

        # ALSO log to NotificationHistory (for main Notifications page)
        # This ensures all notifications appear in the unified Recent Notifications view
        from api.models.notifications import NotificationHistory

        # Get service info from the first channel that was sent to (if any)
        service_id = None
        service_name = None
        if channels_sent:
            first_channel = channels_sent[0]
            if first_channel.get("type") == "channel":
                service_id = first_channel.get("id")
                # Try to get the service name
                try:
                    from api.models.notifications import NotificationService as NotificationServiceModel
                    service_result = await db.execute(
                        select(NotificationServiceModel).where(NotificationServiceModel.id == service_id)
                    )
                    service = service_result.scalar_one_or_none()
                    if service:
                        service_name = service.name
                except Exception:
                    pass

        notification_history = NotificationHistory(
            event_type=event_type,
            event_data={
                **event_data,
                "title": title,
                "message": message,
                "priority": priority,
            },
            severity=event.severity,
            service_id=service_id,
            service_name=service_name,
            status="sent" if sent_count > 0 else "failed",
            sent_at=now if sent_count > 0 else None,
        )
        db.add(notification_history)

        await db.commit()
        logger.info(f"Dispatched '{event_type}' notification to {sent_count} channel(s)")


def _get_container_name() -> str:
    """
    Get the container name from Docker API instead of hostname (which returns container ID).
    Falls back to 'n8n_management' if Docker API is unavailable.
    """
    import os
    try:
        import docker
        client = docker.from_env()
        # Get current container's ID from hostname or cgroup
        container_id = os.environ.get("HOSTNAME", "")
        if container_id:
            # Try to get full container info
            container = client.containers.get(container_id)
            # Container name has a leading slash, remove it
            return container.name.lstrip('/')
    except Exception:
        pass
    # Fallback to expected container name
    return "n8n_management"


def _format_local_time(utc_time_str: str, timezone_str: str = None) -> str:
    """
    Convert a UTC timestamp string to local timezone.

    Args:
        utc_time_str: Timestamp string in format "YYYY-MM-DD HH:MM:SS" (assumed UTC)
        timezone_str: Target timezone (defaults to settings.timezone)

    Returns:
        Formatted timestamp in local timezone
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from api.config import settings

    if not timezone_str:
        timezone_str = settings.timezone

    try:
        # Parse the UTC time string
        utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M:%S")
        # Make it timezone-aware (UTC)
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
        # Convert to local timezone
        local_tz = ZoneInfo(timezone_str)
        local_dt = utc_dt.astimezone(local_tz)
        # Return formatted string
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # If conversion fails, return original
        return utc_time_str


def _build_notification_message(event_type: str, event_data: Dict[str, Any]) -> str:
    """Build a human-readable notification message from event data."""
    from datetime import datetime

    # Use container name instead of hostname (container ID)
    hostname = event_data.get("hostname") or _get_container_name()

    # Backup events
    if event_type == "backup_success":
        backup_type = event_data.get("backup_type", "unknown")
        size_mb = event_data.get("size_mb", 0)
        duration = event_data.get("duration_seconds", 0)
        workflow_count = event_data.get("workflow_count", 0)
        config_count = event_data.get("config_file_count", 0)
        # Convert UTC timestamp to local timezone
        completed_at_utc = event_data.get("completed_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        completed_at = _format_local_time(completed_at_utc)

        return (
            f"Host: {hostname}\n"
            f"Completed: {completed_at}\n\n"
            f"Type: {backup_type}\n"
            f"Size: {size_mb} MB\n"
            f"Duration: {duration}s\n"
            f"Workflows: {workflow_count}\n"
            f"Config Files: {config_count}"
        )
    elif event_type == "backup_failure":
        backup_type = event_data.get("backup_type", "unknown")
        error = event_data.get("error", "Unknown error")
        # Convert UTC timestamp to local timezone
        failed_at_utc = event_data.get("failed_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        failed_at = _format_local_time(failed_at_utc)

        return (
            f"Host: {hostname}\n"
            f"Failed: {failed_at}\n\n"
            f"Type: {backup_type}\n"
            f"Error: {error}"
        )
    elif event_type == "backup_started":
        backup_type = event_data.get("backup_type", "unknown")
        # Convert UTC timestamp to local timezone
        started_at_utc = event_data.get("started_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        started_at = _format_local_time(started_at_utc)

        return (
            f"Host: {hostname}\n"
            f"Started: {started_at}\n\n"
            f"Type: {backup_type}"
        )

    # Container events
    elif event_type == "container_unhealthy":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        message = event_data.get("message", "")
        return f"Host: {hostname}\n\nContainer '{container}' is unhealthy!\n\n{message}" if message else f"Host: {hostname}\n\nContainer '{container}' is unhealthy!\n\nPlease check the container health."
    elif event_type == "container_healthy":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' has recovered and is now healthy."
    elif event_type == "container_stopped":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' has stopped.\n\nThis may indicate an issue."
    elif event_type in ("container_restart", "container_restarted"):
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        restart_count = event_data.get("restart_count", "")
        return f"Host: {hostname}\n\nContainer '{container}' was restarted.{f' (Total restarts: {restart_count})' if restart_count else ''}"
    elif event_type == "container_started":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' started."
    elif event_type == "container_removed":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' was removed."
    elif event_type == "container_high_cpu":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        percent = event_data.get("percent", event_data.get("cpu_percent", 0))
        threshold = event_data.get("threshold", 80)
        return f"Host: {hostname}\n\nContainer '{container}' high CPU usage!\n\nCurrent: {percent}%\nThreshold: {threshold}%"
    elif event_type == "container_high_memory":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        percent = event_data.get("percent", event_data.get("memory_percent", 0))
        threshold = event_data.get("threshold", 80)
        return f"Host: {hostname}\n\nContainer '{container}' high memory usage!\n\nCurrent: {percent}%\nThreshold: {threshold}%"

    # System events
    elif event_type == "disk_space_low":
        percent = event_data.get("percent", 0)
        path = event_data.get("path", "/")
        return f"Host: {hostname}\n\nDisk space is low!\n\nPath: {path}\nUsage: {percent}%"
    elif event_type == "high_memory":
        percent = event_data.get("percent", 0)
        return f"Host: {hostname}\n\nHigh memory usage detected: {percent}%"
    elif event_type == "high_cpu":
        percent = event_data.get("percent", 0)
        return f"Host: {hostname}\n\nHigh CPU usage detected: {percent}%"

    # Pruning events
    elif event_type == "backup_pending_deletion":
        count = event_data.get("count", 0)
        reason = event_data.get("reason", "unknown")
        hours = event_data.get("hours_until_deletion", 0)
        return f"Host: {hostname}\n\n{count} backup(s) scheduled for deletion.\n\nReason: {reason}\nDeletion in: {hours} hours"
    elif event_type == "backup_critical_space":
        free_percent = event_data.get("free_percent", 0)
        action = event_data.get("action", "unknown")
        return f"Host: {hostname}\n\nCritical disk space alert!\n\nFree space: {free_percent}%\nAction: {action}"

    else:
        # Generic message with event data
        lines = [f"Host: {hostname}", f"Event: {event_type}"]
        for key, value in event_data.items():
            if key != "hostname":
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
