"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/notification_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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
    NotificationHistory,
    NotificationGroup,
    NotificationGroupMembership,
    generate_slug,
)
from api.config import settings

logger = logging.getLogger(__name__)


class UnsupportedServiceType(ValueError):
    """A channel whose service_type has no transport."""

    def __init__(self, service_type: str):
        super().__init__(f"Unsupported service type: {service_type}")
        self.service_type = service_type


class NotificationDispatcher:
    """Handles sending notifications via various services."""

    async def send(
        self,
        service: "NotificationServiceModel",
        title: str,
        body: str,
        priority: str = "normal",
        event_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Deliver one message to one channel, choosing the transport from
        ``service.service_type``. The single place that knows which types
        exist; every sender goes through here.

        Webhook channels receive ``event_data`` (with the priority added) as
        their payload; the other transports take the priority directly.
        Raises UnsupportedServiceType for an unknown type.
        """
        service_type = service.service_type
        if service_type == "webhook":
            payload = dict(event_data or {})
            payload.setdefault("priority", priority)
            return await self.send_webhook(service.config, title, body, payload)

        transports = {
            "apprise": self.send_apprise,
            "ntfy": self.send_ntfy,
            "email": self.send_email,
        }
        transport = transports.get(service_type)
        if transport is None:
            raise UnsupportedServiceType(service_type)
        return await transport(service.config, title, body, priority)

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
            success = await self.dispatcher.send(service, title, message, "normal", {"source": "service.test"})

            # Update test status
            service.last_test = datetime.now(UTC)
            service.last_test_result = "success" if success else "failed"
            service.last_test_error = None if success else "Send returned false"
            if not success:
                error_msg = "Send returned false"

        except UnsupportedServiceType as e:
            return {"success": False, "error": str(e)}

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

        # Re-fetch with eager loading of memberships and services
        group = await self.get_group(group.id)
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

        # Re-fetch with eager loading of memberships and services
        return await self.get_group(group_id)

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

        # The same gate system events pass through. There is no event row for
        # a workflow message, so only the global dials apply: maintenance,
        # blackout, quiet hours (priority), hourly rate limit.
        from api.services.notification_gate import evaluate, get_global_settings, record_delivery

        now = datetime.now(UTC)
        global_settings = await get_global_settings(self.db)
        decision = evaluate(global_settings=global_settings, priority=priority, now=now)
        if not decision.allow:
            logger.info(f"Webhook notification '{title}' suppressed: {decision.reason}")
            self.db.add(NotificationHistory(
                event_type="webhook.notification",
                event_data={"title": title, "message": message[:500], "priority": priority, "targets": targets},
                severity=priority,
                status="suppressed",
                error_message=f"suppressed: {decision.reason}",
            ))
            await self.db.commit()
            return {
                "success": False,
                "channels_notified": 0,
                "channels": [],
                "targets_resolved": targets_resolved,
                "errors": [],
                "suppressed": decision.reason,
            }
        priority = decision.priority

        channels_notified = []

        for service in services:
            try:
                success = await self.dispatcher.send(
                    service, title, message, priority, {"source": "n8n_webhook", "targets": targets}
                )

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

            except UnsupportedServiceType:
                errors.append(f"{service.name}: Unsupported service type")

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

        if channels_notified:
            record_delivery(global_settings, now)

        await self.db.commit()

        return {
            "success": len(channels_notified) > 0,
            "channels_notified": len(channels_notified),
            "channels": channels_notified,
            "targets_resolved": targets_resolved,
            "errors": errors,
        }

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
            success = await self.dispatcher.send(
                service, title, message, priority, {"source": "system_notification"}
            )
            return {"success": success}

        except UnsupportedServiceType as e:
            return {"success": False, "error": str(e)}

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
SEVERITY_PRIORITY = {
    "info": "normal",
    "warning": "high",
    "critical": "critical",
    "error": "critical",
}


def _priority_for_severity(severity: str) -> str:
    """Map an event severity to a transport priority."""
    return SEVERITY_PRIORITY.get(severity, "normal")


def _suppressed_history(event, event_data: Dict[str, Any], target_id: str, reason: str, now: datetime):
    """
    A history row for a notification that was gated. Every suppression must
    leave one of these so the dashboard can say why nothing arrived.
    """
    from api.models.system_notifications import SystemNotificationHistory

    return SystemNotificationHistory(
        event_type=event.event_type,
        event_id=event.id,
        target_id=target_id,
        target_label=event_data.get("container") or event.event_type,
        severity=event.severity,
        event_data=event_data,
        status="suppressed",
        suppression_reason=reason,
        triggered_at=now,
    )


async def _deliver_to_targets(
    notification_service: "NotificationService",
    targets,
    title: str,
    message: str,
    priority: str,
    event_type: str,
    level: Optional[int] = None,
) -> tuple[int, List[Dict[str, Any]]]:
    """
    Send one message to a list of SystemNotificationTarget rows.

    Returns (sent_count, channels_sent). ``level`` labels the entries in
    channels_sent; when None, each target's own escalation_level is used.
    Used by dispatch_notification for L1 and L2, and by the test endpoint.
    """
    sent_count = 0
    channels_sent: List[Dict[str, Any]] = []

    for target in targets:
        target_level = level or target.escalation_level or 1
        try:
            if target.target_type == "channel" and target.channel_id:
                result = await notification_service.send_to_service(
                    target.channel_id, title, message, priority
                )
                if result.get("success"):
                    sent_count += 1
                    channels_sent.append({"type": "channel", "id": target.channel_id, "level": target_level})
                    logger.info(f"Sent '{event_type}' notification to L{target_level} channel {target.channel_id}")
                else:
                    logger.error(
                        f"Failed to send '{event_type}' to channel {target.channel_id}: {result.get('error')}"
                    )

            elif target.target_type == "group" and target.group_id:
                result = await notification_service.send_to_group(
                    target.group_id, title, message, priority
                )
                if result.get("success"):
                    sent_count += result.get("sent_count", 1)
                    channels_sent.append({"type": "group", "id": target.group_id, "level": target_level})
                    logger.info(f"Sent '{event_type}' notification to L{target_level} group {target.group_id}")
                else:
                    logger.error(
                        f"Failed to send '{event_type}' to group {target.group_id}: {result.get('error')}"
                    )

        except Exception as e:
            logger.error(f"Error sending '{event_type}' to L{target_level} target {target.id}: {e}")

    return sent_count, channels_sent


async def dispatch_notification(
    event_type: str,
    event_data: Dict[str, Any],
) -> None:
    """
    Dispatch notification using System Notifications configuration.

    Severity (and therefore transport priority) comes from the event row,
    which is what the Settings page shows and lets you change. Callers do
    not pass one.

    This looks up the event in SystemNotificationEvent and sends to all
    configured targets (channels/groups) in SystemNotificationTarget.

    Features:
    - Per-container configuration checking
    - The shared gate (api.services.notification_gate): maintenance mode,
      blackout window, frequency/cooldown, quiet hours, hourly rate limit
    - L1/L2 escalation (L2 fires when L1 fails to deliver or the event is critical)
    - History logging, including a row for every suppression naming the reason
    """
    from api.database import async_session_maker
    from api.models.system_notifications import (
        SystemNotificationEvent,
        SystemNotificationTarget,
        SystemNotificationContainerConfig,
        SystemNotificationState,
        SystemNotificationHistory,
    )
    from api.services.notification_gate import evaluate, get_global_settings, record_delivery

    async with async_session_maker() as db:
        now = datetime.now(UTC)

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

        target_id = container_name or event_data.get("target_id") or "global"

        # Per-(event, target) throttle state
        state_result = await db.execute(
            select(SystemNotificationState).where(
                SystemNotificationState.event_type == event_type,
                SystemNotificationState.target_id == target_id
            )
        )
        state = state_result.scalar_one_or_none()

        # The gate: maintenance (with expiry), blackout, frequency/cooldown,
        # quiet hours, hourly rate limit. Every suppression is recorded.
        global_settings = await get_global_settings(db)
        decision = evaluate(
            global_settings=global_settings,
            event=event,
            state=state,
            priority=_priority_for_severity(event.severity),
            now=now,
        )
        if not decision.allow:
            logger.debug(f"Event '{event_type}' suppressed: {decision.reason}")
            db.add(_suppressed_history(event, event_data, target_id, decision.reason, now))
            await db.commit()
            return
        priority = decision.priority
        for note in decision.notes:
            logger.debug(f"Event '{event_type}': {note}")

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
            await db.commit()  # keep any maintenance expiry / rate window roll
            return

        # Build notification title and message
        title = f"{event.display_name}"
        message = _build_notification_message(event_type, event_data)

        notification_service = NotificationService(db)

        # Send to L1 targets immediately
        sent_count, channels_sent = await _deliver_to_targets(
            notification_service, l1_targets, title, message, priority, event_type, level=1
        )

        # Every occurrence starts a fresh escalation cycle. (Previously the
        # flag was never cleared, so a pair that had escalated once could
        # never escalate again.)
        if not state:
            state = SystemNotificationState(event_type=event_type, target_id=target_id)
            db.add(state)
        state.escalation_sent = False
        state.escalation_triggered_at = None

        # L2 escalation: only when enabled on the event, and only when L1 could
        # not deliver or the event is critical. There is no time-delayed
        # escalation: the product has no acknowledgement concept for a timeout
        # to wait on, so a delayed L2 was just a duplicate.
        if l2_targets and event.escalation_enabled:
            if event.severity == "critical" or sent_count == 0:
                l2_sent, l2_channels = await _deliver_to_targets(
                    notification_service, l2_targets, f"[ESCALATED] {title}", message, "critical",
                    event_type, level=2,
                )
                sent_count += l2_sent
                channels_sent.extend(l2_channels)
                state.escalation_sent = True
                state.escalation_triggered_at = now
        elif l2_targets:
            logger.debug(f"L2 targets configured for '{event_type}' but escalation is disabled")

        # Update state for the frequency/cooldown window and the hourly count
        state.last_sent_at = now
        state.updated_at = now
        if sent_count > 0:
            record_delivery(global_settings, now)

        # Log to SystemNotificationHistory (for system notifications settings page)
        system_history = SystemNotificationHistory(
            event_type=event_type,
            event_id=event.id,
            target_id=target_id,
            target_label=event_data.get("container") or event_type,
            severity=event.severity,
            event_data=event_data,
            channels_sent=channels_sent,
            escalation_level=2 if state.escalation_sent else 1,
            status="sent" if sent_count > 0 else "failed",
            triggered_at=now,
            sent_at=now if sent_count > 0 else None,
        )
        db.add(system_history)

        # ALSO log to NotificationHistory (for main Notifications page)
        # This ensures all notifications appear in the unified Recent Notifications view
        # We need to create one record per channel for proper grouping in the frontend
        from api.models.notifications import NotificationHistory, NotificationGroup

        # Build targets list for each channel_sent entry
        from sqlalchemy.orm import selectinload
        from api.models.notifications import NotificationGroupMembership

        for channel_info in channels_sent:
            target_type = channel_info.get("type")
            target_id_val = channel_info.get("id")

            if target_type == "group" and target_id_val:
                # For groups, get the group slug and create history for each channel in the group
                try:
                    # Eagerly load memberships and their services
                    group_result = await db.execute(
                        select(NotificationGroup)
                        .options(
                            selectinload(NotificationGroup.memberships)
                            .selectinload(NotificationGroupMembership.service)
                        )
                        .where(NotificationGroup.id == target_id_val)
                    )
                    group = group_result.scalar_one_or_none()
                    if group:
                        targets = [f"group:{group.slug}"]
                        logger.info(f"Creating history for group '{group.name}' with {len(group.memberships)} memberships")
                        # Create a history record for each channel in the group
                        for membership in group.memberships:
                            service = membership.service
                            if service and service.enabled:
                                logger.info(f"Creating history record for channel '{service.name}'")
                                notification_history = NotificationHistory(
                                    event_type=event_type,
                                    event_data={
                                        **event_data,
                                        "title": title,
                                        "message": message,
                                        "priority": priority,
                                        "targets": targets,
                                    },
                                    severity=event.severity,
                                    service_id=service.id,
                                    service_name=service.name,
                                    status="sent",
                                    sent_at=now,
                                )
                                db.add(notification_history)
                    else:
                        logger.warning(f"Group with id {target_id_val} not found")
                except Exception as e:
                    logger.error(f"Failed to create history for group {target_id_val}: {e}", exc_info=True)

            elif target_type == "channel" and target_id_val:
                # For individual channels, create one history record
                try:
                    from api.models.notifications import NotificationService as NotificationServiceModel
                    service_result = await db.execute(
                        select(NotificationServiceModel).where(NotificationServiceModel.id == target_id_val)
                    )
                    service = service_result.scalar_one_or_none()
                    if service:
                        notification_history = NotificationHistory(
                            event_type=event_type,
                            event_data={
                                **event_data,
                                "title": title,
                                "message": message,
                                "priority": priority,
                            },
                            severity=event.severity,
                            service_id=service.id,
                            service_name=service.name,
                            status="sent",
                            sent_at=now,
                        )
                        db.add(notification_history)
                except Exception as e:
                    logger.error(f"Failed to create history for channel {target_id_val}: {e}")

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
        credential_count = event_data.get("credential_count", 0)
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
            f"Credentials: {credential_count}\n"
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

    # Verification events
    elif event_type == "verification_started":
        backup_filename = event_data.get("backup_filename", "unknown")
        backup_id = event_data.get("backup_id", "")
        return (
            f"Host: {hostname}\n\n"
            f"Backup verification started.\n\n"
            f"Backup: {backup_filename}"
        )
    elif event_type == "verification_passed":
        backup_filename = event_data.get("backup_filename", "unknown")
        backup_type = event_data.get("backup_type", "unknown")
        size_mb = event_data.get("size_mb", 0)
        duration = event_data.get("duration_seconds", 0)
        duration_str = f"{duration:.1f}s" if duration else "N/A"
        workflow_count = event_data.get("workflow_count", 0)
        credential_count = event_data.get("credential_count", 0)
        config_count = event_data.get("config_file_count", 0)

        # Format backup creation time
        backup_created_utc = event_data.get("backup_created_at")
        backup_created = _format_local_time(backup_created_utc) if backup_created_utc else "N/A"

        # Format verification completion time
        completed_at_utc = event_data.get("completed_at")
        completed_at = _format_local_time(completed_at_utc) if completed_at_utc else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"Host: {hostname}\n"
            f"Completed: {completed_at}\n\n"
            f"✅ Backup verification passed!\n\n"
            f"Backup: {backup_filename}\n"
            f"Backup Date: {backup_created}\n"
            f"Type: {backup_type}\n"
            f"Size: {size_mb} MB\n"
            f"Verification Duration: {duration_str}\n"
            f"Workflows: {workflow_count}\n"
            f"Credentials: {credential_count}\n"
            f"Config Files: {config_count}"
        )
    elif event_type == "verification_failed":
        backup_filename = event_data.get("backup_filename", "unknown")
        backup_type = event_data.get("backup_type", "unknown")
        size_mb = event_data.get("size_mb", 0)
        duration = event_data.get("duration_seconds", 0)
        duration_str = f"{duration:.1f}s" if duration else "N/A"
        workflow_count = event_data.get("workflow_count", 0)
        credential_count = event_data.get("credential_count", 0)
        config_count = event_data.get("config_file_count", 0)
        errors = event_data.get("errors", [])
        warnings = event_data.get("warnings", [])
        error_str = "\n".join(f"  • {e}" for e in errors) if errors else "  No specific errors"

        # Format backup creation time
        backup_created_utc = event_data.get("backup_created_at")
        backup_created = _format_local_time(backup_created_utc) if backup_created_utc else "N/A"

        # Format verification completion time
        completed_at_utc = event_data.get("completed_at")
        completed_at = _format_local_time(completed_at_utc) if completed_at_utc else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"Host: {hostname}\n"
            f"Completed: {completed_at}\n\n"
            f"❌ Backup verification failed!\n\n"
            f"Backup: {backup_filename}\n"
            f"Backup Date: {backup_created}\n"
            f"Type: {backup_type}\n"
            f"Size: {size_mb} MB\n"
            f"Verification Duration: {duration_str}\n"
            f"Workflows: {workflow_count}\n"
            f"Credentials: {credential_count}\n"
            f"Config Files: {config_count}\n\n"
            f"Errors:\n{error_str}"
        )

    # Container events
    elif event_type == "container_unhealthy":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        message = event_data.get("message", "")
        return f"Host: {hostname}\n\nContainer '{container}' is unhealthy!\n\n{message}" if message else f"Host: {hostname}\n\nContainer '{container}' is unhealthy!\n\nPlease check the container health."
    elif event_type == "container_healthy":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        recovered_from = event_data.get("recovered_from")
        detail = f" (was {recovered_from})" if recovered_from else ""
        return f"Host: {hostname}\n\nContainer '{container}' has recovered and is now healthy{detail}."
    elif event_type == "container_stopped":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' has stopped.\n\nThis may indicate an issue."
    elif event_type == "container_restart":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        restart_count = event_data.get("restart_count", "")
        return f"Host: {hostname}\n\nContainer '{container}' was restarted.{f' (Total restarts: {restart_count})' if restart_count else ''}"
    elif event_type == "container_started":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' started."
    elif event_type == "container_removed":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        return f"Host: {hostname}\n\nContainer '{container}' was removed."
    elif event_type == "container_recreated":
        container = event_data.get("container") or event_data.get("container_name", "unknown")
        action = event_data.get("action") or "recreated"
        return f"Host: {hostname}\n\nContainer '{container}' was {action}."
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
        threshold = event_data.get("threshold")
        detail = f" (threshold {threshold}%)" if threshold else ""
        return f"Host: {hostname}\n\nDisk space is low!\n\nPath: {path}\nUsage: {percent}%{detail}"
    elif event_type == "high_memory":
        percent = event_data.get("percent", 0)
        threshold = event_data.get("threshold")
        detail = f" (threshold {threshold}%)" if threshold else ""
        return f"Host: {hostname}\n\nHigh memory usage detected: {percent}%{detail}"
    elif event_type == "high_cpu":
        percent = event_data.get("percent", 0)
        threshold = event_data.get("threshold")
        duration = event_data.get("duration_minutes")
        detail = f" (threshold {threshold}%" + (f" for {duration} min)" if duration else ")") if threshold else ""
        return f"Host: {hostname}\n\nHigh CPU usage detected: {percent}%{detail}"

    # SSL events
    elif event_type == "certificate_expiring":
        domain = event_data.get("domain", "unknown")
        days = event_data.get("days_until_expiry")
        valid_until = event_data.get("valid_until", "")
        if days is not None and days <= 0:
            return f"Host: {hostname}\n\nSSL certificate for '{domain}' has EXPIRED ({valid_until}).\n\nRenew it now."
        return (
            f"Host: {hostname}\n\nSSL certificate for '{domain}' expires in {days} day(s) ({valid_until}).\n\n"
            "Check that certbot renewal is working."
        )

    # Security events
    elif event_type == "security_event":
        kind = event_data.get("kind", "unknown")
        client_ip = event_data.get("client_ip") or "unknown"
        if kind == "account_locked":
            return (
                f"Host: {hostname}\n\nAccount '{event_data.get('username')}' locked after "
                f"{event_data.get('failed_attempts')} failed login attempts.\n\n"
                f"Last attempt from: {client_ip}\nLocked until: {event_data.get('locked_until')}"
            )
        if kind == "webhook_invalid_key":
            return f"Host: {hostname}\n\nNotification webhook called with an invalid API key.\n\nFrom: {client_ip}"
        return f"Host: {hostname}\n\nSecurity event: {kind}\nFrom: {client_ip}"

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
