"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/notification_gate.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

The one gate every outbound notification passes through.

``dispatch_notification`` (system events), ``send_webhook_notification``
(n8n workflows) and anything added later call ``evaluate`` before they send.
A suppression rule that lives in one place cannot disagree with itself.

Order of checks, first match wins:

1. maintenance mode      (global; a window with an end time expires itself)
2. blackout window       (global; suppresses everything, critical included)
3. frequency / cooldown  (per event + target; frequency wins when set,
                          cooldown applies only to ``every_time`` events)
4. quiet hours           (global; critical passes untouched, non-critical is
                          lowered to low priority or muted per the setting)
5. hourly rate limit     (global; counts deliveries, not attempts)

``evaluate`` is pure apart from rolling the rate-limit hour window on the
settings row. It never writes history: the caller does, so each path can
record the suppression where its own history lives.

The suppression reason names the dial that stopped the send, so "why didn't
it arrive" is answered by the history row, not by someone's memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute

from api.config import settings

logger = logging.getLogger(__name__)

# SystemNotificationEvent.frequency -> minimum minutes between deliveries.
# ``every_time`` (0) defers to the event's cooldown_minutes instead.
FREQUENCY_MINUTES = {
    "every_time": 0,
    "once_per_15m": 15,
    "once_per_30m": 30,
    "once_per_hour": 60,
    "once_per_4h": 240,
    "once_per_12h": 720,
    "once_per_day": 1440,
    "once_per_week": 10080,
}

# Priority handed to non-critical notifications during quiet hours when the
# setting is "reduce priority" rather than "mute". ntfy treats low as silent.
QUIET_HOURS_PRIORITY = "low"

RATE_LIMIT_WINDOW = timedelta(hours=1)


@dataclass
class GateDecision:
    allow: bool
    reason: Optional[str] = None       # set when allow is False; names the dial
    priority: str = "normal"           # possibly adjusted by quiet hours
    notes: List[str] = field(default_factory=list)  # non-suppressing adjustments

    @classmethod
    def deny(cls, reason: str, priority: str) -> "GateDecision":
        return cls(allow=False, reason=reason, priority=priority)


# --- time helpers --------------------------------------------------------------------

def _local_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.timezone)
    except Exception:  # unknown TZ string; fall back rather than fail every send
        logger.warning(f"Unknown timezone '{settings.timezone}', using UTC for notification windows")
        return ZoneInfo("UTC")


def local_now(now: datetime) -> datetime:
    """The management console's wall-clock time (TZ env), which is what the HH:MM settings mean."""
    return now.astimezone(_local_zone())


def parse_hhmm(value: Optional[str]) -> Optional[int]:
    """'HH:MM' -> minutes since midnight, or None when the value is unusable."""
    if not value or ":" not in value:
        return None
    try:
        hours, minutes = value.split(":", 1)
        hours, minutes = int(hours), int(minutes)
    except ValueError:
        return None
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        return None
    return hours * 60 + minutes


def in_daily_window(local: datetime, start: Optional[str], end: Optional[str]) -> bool:
    """
    True when ``local`` falls inside [start, end). A window whose start is
    later than its end wraps past midnight (22:00-07:00).
    """
    start_minutes = parse_hhmm(start)
    end_minutes = parse_hhmm(end)
    if start_minutes is None or end_minutes is None or start_minutes == end_minutes:
        return False
    current = local.hour * 60 + local.minute
    if start_minutes < end_minutes:
        return start_minutes <= current < end_minutes
    return current >= start_minutes or current < end_minutes


# --- individual dials ------------------------------------------------------------------

def expire_maintenance(global_settings, now: datetime) -> bool:
    """
    Clear a maintenance window whose end time has passed. Returns True when it
    cleared one. Mutates the settings row; the caller commits.
    """
    if not global_settings or not global_settings.maintenance_mode:
        return False
    until = global_settings.maintenance_until
    if until is None or now < until:
        return False
    global_settings.maintenance_mode = False
    global_settings.maintenance_until = None
    global_settings.maintenance_reason = None
    logger.info("Maintenance window expired - notifications resumed")
    return True


def effective_window(event) -> Tuple[int, str]:
    """
    (minutes, label) for the per-event throttle. A non-``every_time``
    frequency is the window; otherwise cooldown_minutes is. The label is the
    suppression reason, naming the dial that applied.
    """
    frequency = getattr(event, "frequency", None) or "every_time"
    minutes = FREQUENCY_MINUTES.get(frequency)
    if minutes is None:
        logger.warning(f"Unknown frequency '{frequency}' on event '{event.event_type}', treating as every_time")
        minutes = 0
    if minutes:
        return minutes, f"frequency ({frequency})"
    cooldown = getattr(event, "cooldown_minutes", None) or 0
    return cooldown, f"cooldown ({cooldown}min)"


def roll_rate_limit_window(global_settings, now: datetime) -> None:
    """Start a new hour window when none is open or the open one has lapsed."""
    started = global_settings.hour_started_at
    if started is None or now - started >= RATE_LIMIT_WINDOW:
        global_settings.hour_started_at = now
        global_settings.notifications_this_hour = 0


def record_delivery(global_settings, now: datetime) -> None:
    """Count one delivered notification against the hourly limit. Caller commits."""
    if not global_settings:
        return
    started = global_settings.hour_started_at
    if started is None or now - started >= RATE_LIMIT_WINDOW:
        global_settings.hour_started_at = now
        global_settings.notifications_this_hour = 1
        return
    column = getattr(type(global_settings), "notifications_this_hour", None)
    if isinstance(column, InstrumentedAttribute) and sa_inspect(global_settings).persistent:
        # Dispatches for different events run concurrently in separate
        # sessions; increment in SQL so simultaneous deliveries are not lost.
        global_settings.notifications_this_hour = func.coalesce(column, 0) + 1
    else:
        global_settings.notifications_this_hour = (global_settings.notifications_this_hour or 0) + 1


# --- the gate ------------------------------------------------------------------------------

def evaluate(
    *,
    global_settings,
    event=None,
    state=None,
    priority: str = "normal",
    now: Optional[datetime] = None,
) -> GateDecision:
    """
    Decide whether a notification may go out now, and at what priority.

    ``event`` and ``state`` are the SystemNotificationEvent and the
    SystemNotificationState row for (event_type, target_id); pass None for
    paths that have no event (the n8n webhook), and only the global dials
    apply. ``priority`` is the caller's intended priority.
    """
    now = now or datetime.now(UTC)
    gs = global_settings

    # 1. maintenance
    if gs and gs.maintenance_mode and not expire_maintenance(gs, now):
        return GateDecision.deny("maintenance", priority)

    local = local_now(now) if gs else None

    # 2. blackout
    if gs and gs.blackout_enabled and in_daily_window(local, gs.blackout_start, gs.blackout_end):
        return GateDecision.deny("blackout", priority)

    # 3. frequency / cooldown
    if event is not None and state is not None and state.last_sent_at:
        window_minutes, label = effective_window(event)
        if window_minutes > 0:
            window_until = state.last_sent_at + timedelta(minutes=window_minutes)
            if now < window_until:
                return GateDecision.deny(label, priority)

    notes: List[str] = []

    # 4. quiet hours
    if (
        gs and gs.quiet_hours_enabled and priority != "critical"
        and in_daily_window(local, gs.quiet_hours_start, gs.quiet_hours_end)
    ):
        if gs.quiet_hours_reduce_priority:
            if priority != QUIET_HOURS_PRIORITY:
                notes.append(f"quiet_hours: priority {priority} -> {QUIET_HOURS_PRIORITY}")
                priority = QUIET_HOURS_PRIORITY
        else:
            return GateDecision.deny("quiet_hours", priority)

    # 5. hourly rate limit
    if gs and gs.max_notifications_per_hour:
        roll_rate_limit_window(gs, now)
        if (gs.notifications_this_hour or 0) >= gs.max_notifications_per_hour:
            return GateDecision.deny(f"rate_limit ({gs.max_notifications_per_hour}/hour)", priority)

    return GateDecision(allow=True, priority=priority, notes=notes)


async def get_global_settings(db: AsyncSession):
    """The singleton SystemNotificationGlobalSettings row, or None before first seed."""
    from api.models.system_notifications import SystemNotificationGlobalSettings

    result = await db.execute(select(SystemNotificationGlobalSettings).limit(1))
    return result.scalar_one_or_none()
