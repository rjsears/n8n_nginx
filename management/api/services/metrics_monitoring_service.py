"""
Metrics Monitoring Service

Polls the n8n-metrics-agent for host-level metrics and triggers
system notifications based on configured thresholds and rules.
"""

import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from api.models.system_notifications import (
    SystemNotificationEvent,
    SystemNotificationTarget,
    SystemNotificationState,
    SystemNotificationGlobalSettings,
    SystemNotificationHistory,
    SystemNotificationContainerConfig,
)
from api.models.notifications import NotificationService, NotificationGroup
from api.config import settings

logger = logging.getLogger(__name__)


class MetricsMonitoringService:
    """
    Service that monitors host metrics and triggers notifications.

    This service:
    1. Polls the metrics agent for current system state
    2. Compares against configured thresholds
    3. Applies rate limiting, cooldowns, and flapping detection
    4. Sends notifications via configured channels
    5. Handles L1/L2 escalation
    6. Logs all activity to history
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._agent_url = settings.metrics_agent_url
        self._agent_api_key = settings.metrics_agent_api_key
        self._http_client: Optional[httpx.AsyncClient] = None
        self._running = False
        self._last_check: Optional[datetime] = None
        self._last_container_states: Dict[str, Dict[str, Any]] = {}

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._http_client is None:
            headers = {}
            if self._agent_api_key:
                headers["X-API-Key"] = self._agent_api_key
            self._http_client = httpx.AsyncClient(
                base_url=self._agent_url,
                headers=headers,
                timeout=30.0,
            )
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def check_agent_health(self) -> Dict[str, Any]:
        """Check if the metrics agent is available."""
        try:
            response = await self.http_client.get("/health")
            response.raise_for_status()
            return {"available": True, **response.json()}
        except Exception as e:
            logger.warning(f"Metrics agent health check failed: {e}")
            return {"available": False, "error": str(e)}

    async def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Fetch current metrics from the agent."""
        try:
            response = await self.http_client.get("/metrics")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}")
            return None

    async def get_container_events(self) -> List[Dict[str, Any]]:
        """Fetch container state change events."""
        try:
            response = await self.http_client.get("/events/containers")
            response.raise_for_status()
            data = response.json()
            return data.get("events", [])
        except Exception as e:
            logger.error(f"Failed to fetch container events: {e}")
            return []

    # -------------------------------------------------------------------------
    # Global Settings Checks
    # -------------------------------------------------------------------------

    async def get_global_settings(self) -> Optional[SystemNotificationGlobalSettings]:
        """Get global notification settings."""
        result = await self.db.execute(
            select(SystemNotificationGlobalSettings).limit(1)
        )
        return result.scalar_one_or_none()

    async def is_notification_allowed(self) -> tuple[bool, Optional[str]]:
        """
        Check if notifications are currently allowed based on global settings.
        Returns (allowed, reason_if_blocked).
        """
        settings_obj = await self.get_global_settings()
        if not settings_obj:
            return True, None

        now = datetime.now(timezone.utc)

        # Check maintenance mode
        if settings_obj.maintenance_mode:
            if settings_obj.maintenance_until:
                if now < settings_obj.maintenance_until:
                    return False, f"Maintenance mode until {settings_obj.maintenance_until}"
            else:
                return False, "Maintenance mode enabled"

        # Check blackout period
        if settings_obj.blackout_enabled and settings_obj.blackout_start and settings_obj.blackout_end:
            current_time = now.strftime("%H:%M")
            if self._is_in_time_range(current_time, settings_obj.blackout_start, settings_obj.blackout_end):
                return False, f"Blackout period ({settings_obj.blackout_start}-{settings_obj.blackout_end})"

        # Check rate limit
        if settings_obj.notifications_this_hour >= settings_obj.max_notifications_per_hour:
            return False, f"Rate limit exceeded ({settings_obj.max_notifications_per_hour}/hour)"

        return True, None

    async def is_quiet_hours(self) -> bool:
        """Check if we're currently in quiet hours."""
        settings_obj = await self.get_global_settings()
        if not settings_obj or not settings_obj.quiet_hours_enabled:
            return False

        current_time = datetime.now(timezone.utc).strftime("%H:%M")
        return self._is_in_time_range(
            current_time,
            settings_obj.quiet_hours_start,
            settings_obj.quiet_hours_end
        )

    def _is_in_time_range(self, current: str, start: str, end: str) -> bool:
        """Check if current time is within a time range (handles overnight ranges)."""
        if start <= end:
            return start <= current <= end
        else:  # Overnight range (e.g., 22:00-07:00)
            return current >= start or current <= end

    async def increment_notification_count(self):
        """Increment the hourly notification counter."""
        settings_obj = await self.get_global_settings()
        if not settings_obj:
            return

        now = datetime.now(timezone.utc)

        # Reset counter if hour changed
        if settings_obj.hour_started_at:
            hour_start = settings_obj.hour_started_at.replace(tzinfo=timezone.utc)
            if now - hour_start > timedelta(hours=1):
                settings_obj.notifications_this_hour = 0
                settings_obj.hour_started_at = now

        settings_obj.notifications_this_hour += 1
        if not settings_obj.hour_started_at:
            settings_obj.hour_started_at = now

        await self.db.commit()

    # -------------------------------------------------------------------------
    # Event Configuration
    # -------------------------------------------------------------------------

    async def get_event_config(self, event_type: str) -> Optional[SystemNotificationEvent]:
        """Get configuration for a specific event type."""
        result = await self.db.execute(
            select(SystemNotificationEvent)
            .options(selectinload(SystemNotificationEvent.targets))
            .where(SystemNotificationEvent.event_type == event_type)
        )
        return result.scalar_one_or_none()

    async def get_enabled_events(self) -> List[SystemNotificationEvent]:
        """Get all enabled notification events."""
        result = await self.db.execute(
            select(SystemNotificationEvent)
            .options(selectinload(SystemNotificationEvent.targets))
            .where(SystemNotificationEvent.enabled == True)
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # State Management (Cooldown, Flapping)
    # -------------------------------------------------------------------------

    async def get_or_create_state(self, event_type: str, target_id: Optional[str] = None) -> SystemNotificationState:
        """Get or create state record for tracking cooldowns and flapping."""
        result = await self.db.execute(
            select(SystemNotificationState).where(
                SystemNotificationState.event_type == event_type,
                SystemNotificationState.target_id == target_id,
            )
        )
        state = result.scalar_one_or_none()

        if not state:
            state = SystemNotificationState(
                event_type=event_type,
                target_id=target_id,
            )
            self.db.add(state)
            await self.db.flush()

        return state

    async def check_cooldown(self, event: SystemNotificationEvent, target_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        Check if event is in cooldown period.
        Returns (in_cooldown, reason).
        """
        if event.cooldown_minutes <= 0:
            return False, None

        state = await self.get_or_create_state(event.event_type, target_id)

        if state.last_sent_at:
            cooldown_until = state.last_sent_at + timedelta(minutes=event.cooldown_minutes)
            if datetime.now(timezone.utc) < cooldown_until:
                return True, f"Cooldown until {cooldown_until}"

        return False, None

    async def check_flapping(self, event: SystemNotificationEvent, target_id: Optional[str] = None) -> tuple[bool, bool]:
        """
        Check and update flapping state.
        Returns (is_flapping, should_send_summary).
        """
        if not event.flapping_enabled:
            return False, False

        state = await self.get_or_create_state(event.event_type, target_id)
        now = datetime.now(timezone.utc)

        # Check if we should reset the window
        if state.window_start:
            window_end = state.window_start + timedelta(minutes=event.flapping_threshold_minutes)
            if now > window_end:
                # Reset window
                state.window_start = now
                state.event_count_in_window = 1
                state.is_flapping = False
                state.flapping_started_at = None
                await self.db.flush()
                return False, False
        else:
            state.window_start = now
            state.event_count_in_window = 1
            await self.db.flush()
            return False, False

        # Increment counter
        state.event_count_in_window += 1

        # Check if we've hit the flapping threshold
        if state.event_count_in_window >= event.flapping_threshold_count:
            if not state.is_flapping:
                # Just started flapping
                state.is_flapping = True
                state.flapping_started_at = now
                state.last_summary_at = now
                await self.db.flush()
                return True, True  # Send first summary

            # Already flapping - check if we should send another summary
            if state.last_summary_at:
                next_summary = state.last_summary_at + timedelta(minutes=event.flapping_summary_interval)
                if now >= next_summary:
                    state.last_summary_at = now
                    await self.db.flush()
                    return True, True  # Send summary

            return True, False  # Flapping but no summary needed

        await self.db.flush()
        return False, False

    async def update_sent_state(self, event_type: str, target_id: Optional[str] = None):
        """Update state after sending a notification."""
        state = await self.get_or_create_state(event_type, target_id)
        state.last_sent_at = datetime.now(timezone.utc)
        await self.db.commit()

    # -------------------------------------------------------------------------
    # Notification Sending
    # -------------------------------------------------------------------------

    async def send_notification(
        self,
        event: SystemNotificationEvent,
        title: str,
        message: str,
        target_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        escalation_level: int = 1,
    ) -> bool:
        """
        Send notification for an event to configured targets.
        Returns True if at least one notification was sent.
        """
        from api.services.notification_service import NotificationService as NotifSvc

        # Get targets for this escalation level
        targets = [t for t in event.targets if t.escalation_level == escalation_level]

        if not targets:
            logger.debug(f"No L{escalation_level} targets for event {event.event_type}")
            return False

        # Adjust priority during quiet hours
        priority = event.severity
        if await self.is_quiet_hours():
            if priority == "critical":
                priority = "high"
            elif priority == "warning":
                priority = "normal"

        sent_count = 0
        channels_sent = []

        notification_service = NotifSvc(self.db)

        for target in targets:
            try:
                if target.target_type == "channel" and target.channel_id:
                    # Send to single channel
                    result = await notification_service.send_to_service(
                        service_id=target.channel_id,
                        title=title,
                        message=message,
                        priority=priority,
                    )
                    if result.get("success"):
                        sent_count += 1
                        channels_sent.append({"type": "channel", "id": target.channel_id})

                elif target.target_type == "group" and target.group_id:
                    # Send to group
                    result = await notification_service.send_to_group(
                        group_id=target.group_id,
                        title=title,
                        message=message,
                        priority=priority,
                    )
                    if result.get("success"):
                        sent_count += result.get("sent_count", 1)
                        channels_sent.append({"type": "group", "id": target.group_id})

            except Exception as e:
                logger.error(f"Failed to send to target {target.id}: {e}")

        # Log to history
        await self.log_history(
            event=event,
            target_id=target_id,
            target_label=title,
            event_data=event_data,
            channels_sent=channels_sent,
            escalation_level=escalation_level,
            status="sent" if sent_count > 0 else "failed",
        )

        if sent_count > 0:
            await self.update_sent_state(event.event_type, target_id)
            await self.increment_notification_count()

        return sent_count > 0

    async def log_history(
        self,
        event: SystemNotificationEvent,
        target_id: Optional[str],
        target_label: str,
        event_data: Optional[Dict[str, Any]],
        channels_sent: List[Dict[str, Any]],
        escalation_level: int,
        status: str,
        suppression_reason: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Log notification to history."""
        history = SystemNotificationHistory(
            event_type=event.event_type,
            event_id=event.id,
            target_id=target_id,
            target_label=target_label,
            severity=event.severity,
            event_data=event_data,
            channels_sent=channels_sent,
            escalation_level=escalation_level,
            status=status,
            suppression_reason=suppression_reason,
            error_message=error_message,
            triggered_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc) if status == "sent" else None,
        )
        self.db.add(history)
        await self.db.commit()

    # -------------------------------------------------------------------------
    # Event Triggers
    # -------------------------------------------------------------------------

    async def trigger_event(
        self,
        event_type: str,
        title: str,
        message: str,
        target_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a notification event with all checks applied.

        Returns dict with: triggered, sent, suppressed, reason
        """
        result = {
            "triggered": True,
            "sent": False,
            "suppressed": False,
            "reason": None,
        }

        # Get event configuration
        event = await self.get_event_config(event_type)
        if not event:
            result["suppressed"] = True
            result["reason"] = f"Event type '{event_type}' not configured"
            return result

        if not event.enabled:
            result["suppressed"] = True
            result["reason"] = "Event is disabled"
            return result

        if not event.targets:
            result["suppressed"] = True
            result["reason"] = "No targets configured"
            return result

        # Check global settings
        allowed, block_reason = await self.is_notification_allowed()
        if not allowed:
            result["suppressed"] = True
            result["reason"] = block_reason
            await self.log_history(
                event=event,
                target_id=target_id,
                target_label=title,
                event_data=event_data,
                channels_sent=[],
                escalation_level=1,
                status="suppressed",
                suppression_reason=block_reason,
            )
            return result

        # Check cooldown
        in_cooldown, cooldown_reason = await self.check_cooldown(event, target_id)
        if in_cooldown:
            result["suppressed"] = True
            result["reason"] = cooldown_reason
            return result

        # Check flapping
        is_flapping, should_send_summary = await self.check_flapping(event, target_id)
        if is_flapping and not should_send_summary:
            result["suppressed"] = True
            result["reason"] = "Flapping detected, awaiting summary interval"
            return result

        # Modify message if flapping summary
        if is_flapping and should_send_summary:
            state = await self.get_or_create_state(event.event_type, target_id)
            message = f"[FLAPPING] {state.event_count_in_window} occurrences in {event.flapping_threshold_minutes} minutes\n\n{message}"
            title = f"[Flapping] {title}"

        # Send notification
        sent = await self.send_notification(
            event=event,
            title=title,
            message=message,
            target_id=target_id,
            event_data=event_data,
            escalation_level=1,
        )

        result["sent"] = sent
        if not sent:
            result["reason"] = "Failed to send to any target"

        return result

    # -------------------------------------------------------------------------
    # Metric Checks
    # -------------------------------------------------------------------------

    async def check_cpu_threshold(self, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check CPU usage against threshold."""
        cpu = metrics.get("cpu", {})
        percent = cpu.get("percent", 0)

        event = await self.get_event_config("system.high_cpu")
        if not event or not event.enabled:
            return None

        threshold = (event.thresholds or {}).get("percent", 90)

        if percent >= threshold:
            return {
                "event_type": "system.high_cpu",
                "title": f"High CPU Usage: {percent:.1f}%",
                "message": f"CPU usage is at {percent:.1f}% (threshold: {threshold}%)\n\nLoad average: {cpu.get('load_avg_1m', 0):.2f}, {cpu.get('load_avg_5m', 0):.2f}, {cpu.get('load_avg_15m', 0):.2f}",
                "target_id": "cpu",
                "data": {"percent": percent, "threshold": threshold, "load_avg": cpu.get("load_avg_1m")},
            }
        return None

    async def check_memory_threshold(self, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check memory usage against threshold."""
        memory = metrics.get("memory", {})
        percent = memory.get("percent", 0)

        event = await self.get_event_config("system.high_memory")
        if not event or not event.enabled:
            return None

        threshold = (event.thresholds or {}).get("percent", 90)

        if percent >= threshold:
            used_gb = memory.get("used_bytes", 0) / (1024**3)
            total_gb = memory.get("total_bytes", 0) / (1024**3)
            return {
                "event_type": "system.high_memory",
                "title": f"High Memory Usage: {percent:.1f}%",
                "message": f"Memory usage is at {percent:.1f}% ({used_gb:.1f}GB / {total_gb:.1f}GB)\n\nThreshold: {threshold}%",
                "target_id": "memory",
                "data": {"percent": percent, "threshold": threshold, "used_bytes": memory.get("used_bytes")},
            }
        return None

    async def check_disk_thresholds(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check disk usage against thresholds."""
        alerts = []
        disks = metrics.get("disks", [])

        # Get both warning and critical events
        warning_event = await self.get_event_config("system.disk_warning")
        critical_event = await self.get_event_config("system.disk_critical")

        for disk in disks:
            mount = disk.get("mount_point", "unknown")
            percent = disk.get("percent", 0)
            free_gb = disk.get("free_bytes", 0) / (1024**3)
            total_gb = disk.get("total_bytes", 0) / (1024**3)

            # Check critical first
            if critical_event and critical_event.enabled:
                threshold = (critical_event.thresholds or {}).get("percent", 95)
                if percent >= threshold:
                    alerts.append({
                        "event_type": "system.disk_critical",
                        "title": f"CRITICAL: Disk {mount} at {percent:.1f}%",
                        "message": f"Disk {mount} is critically full!\n\nUsage: {percent:.1f}%\nFree: {free_gb:.1f}GB / {total_gb:.1f}GB",
                        "target_id": f"disk:{mount}",
                        "data": {"mount_point": mount, "percent": percent, "free_bytes": disk.get("free_bytes")},
                    })
                    continue

            # Check warning
            if warning_event and warning_event.enabled:
                threshold = (warning_event.thresholds or {}).get("percent", 85)
                if percent >= threshold:
                    alerts.append({
                        "event_type": "system.disk_warning",
                        "title": f"Disk Warning: {mount} at {percent:.1f}%",
                        "message": f"Disk {mount} is getting full.\n\nUsage: {percent:.1f}%\nFree: {free_gb:.1f}GB / {total_gb:.1f}GB",
                        "target_id": f"disk:{mount}",
                        "data": {"mount_point": mount, "percent": percent, "free_bytes": disk.get("free_bytes")},
                    })

        return alerts

    async def check_container_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process container state change events."""
        alerts = []

        for event in events:
            container_name = event.get("container_name", "unknown")
            event_type_raw = event.get("event_type", "")

            # Map agent event types to our event types
            if event_type_raw == "health_changed":
                new_health = event.get("new_value")
                old_health = event.get("old_value")

                if new_health == "unhealthy":
                    config_event = await self.get_event_config("container.unhealthy")
                    if config_event and config_event.enabled:
                        alerts.append({
                            "event_type": "container.unhealthy",
                            "title": f"Container Unhealthy: {container_name}",
                            "message": f"Container {container_name} became unhealthy.\n\nPrevious state: {old_health}\nCurrent state: {new_health}",
                            "target_id": f"container:{container_name}",
                            "data": event,
                        })

                elif new_health == "healthy" and old_health == "unhealthy":
                    config_event = await self.get_event_config("container.unhealthy")
                    if config_event and config_event.enabled and config_event.notify_on_recovery:
                        alerts.append({
                            "event_type": "container.recovered",
                            "title": f"Container Recovered: {container_name}",
                            "message": f"Container {container_name} is now healthy again.",
                            "target_id": f"container:{container_name}",
                            "data": event,
                        })

            elif event_type_raw == "restart":
                config_event = await self.get_event_config("container.restarted")
                if config_event and config_event.enabled:
                    restart_count = event.get("new_value", "?")
                    alerts.append({
                        "event_type": "container.restarted",
                        "title": f"Container Restarted: {container_name}",
                        "message": f"Container {container_name} was restarted.\n\nTotal restart count: {restart_count}",
                        "target_id": f"container:{container_name}",
                        "data": event,
                    })

            elif event_type_raw == "status_changed":
                new_status = event.get("new_value")
                old_status = event.get("old_value")

                if new_status == "exited" and old_status == "running":
                    config_event = await self.get_event_config("container.stopped")
                    if config_event and config_event.enabled:
                        alerts.append({
                            "event_type": "container.stopped",
                            "title": f"Container Stopped: {container_name}",
                            "message": f"Container {container_name} has stopped.\n\nPrevious status: {old_status}\nCurrent status: {new_status}",
                            "target_id": f"container:{container_name}",
                            "data": event,
                        })

        return alerts

    # -------------------------------------------------------------------------
    # Main Monitoring Loop
    # -------------------------------------------------------------------------

    async def run_check(self) -> Dict[str, Any]:
        """
        Run a single monitoring check cycle.

        Returns summary of what was checked and any notifications sent.
        """
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_available": False,
            "checks_performed": [],
            "notifications_triggered": 0,
            "notifications_sent": 0,
            "notifications_suppressed": 0,
            "errors": [],
        }

        # Check agent health
        health = await self.check_agent_health()
        result["agent_available"] = health.get("available", False)

        if not result["agent_available"]:
            result["errors"].append("Metrics agent unavailable")
            return result

        # Get metrics
        metrics = await self.get_metrics()
        if not metrics:
            result["errors"].append("Failed to fetch metrics")
            return result

        alerts = []

        # Check CPU
        try:
            cpu_alert = await self.check_cpu_threshold(metrics)
            if cpu_alert:
                alerts.append(cpu_alert)
            result["checks_performed"].append("cpu")
        except Exception as e:
            result["errors"].append(f"CPU check failed: {e}")

        # Check Memory
        try:
            memory_alert = await self.check_memory_threshold(metrics)
            if memory_alert:
                alerts.append(memory_alert)
            result["checks_performed"].append("memory")
        except Exception as e:
            result["errors"].append(f"Memory check failed: {e}")

        # Check Disks
        try:
            disk_alerts = await self.check_disk_thresholds(metrics)
            alerts.extend(disk_alerts)
            result["checks_performed"].append("disk")
        except Exception as e:
            result["errors"].append(f"Disk check failed: {e}")

        # Check Container Events
        try:
            container_events = await self.get_container_events()
            container_alerts = await self.check_container_events(container_events)
            alerts.extend(container_alerts)
            result["checks_performed"].append("containers")
        except Exception as e:
            result["errors"].append(f"Container check failed: {e}")

        # Process alerts
        for alert in alerts:
            result["notifications_triggered"] += 1
            try:
                trigger_result = await self.trigger_event(
                    event_type=alert["event_type"],
                    title=alert["title"],
                    message=alert["message"],
                    target_id=alert.get("target_id"),
                    event_data=alert.get("data"),
                )
                if trigger_result["sent"]:
                    result["notifications_sent"] += 1
                elif trigger_result["suppressed"]:
                    result["notifications_suppressed"] += 1
            except Exception as e:
                result["errors"].append(f"Failed to process alert {alert['event_type']}: {e}")

        self._last_check = datetime.now(timezone.utc)
        return result
