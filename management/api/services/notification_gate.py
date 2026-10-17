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

``evaluate`` only reads, apart from clearing an expired maintenance window.
It never touches the rate-limit counter: a lapsed hour simply counts as zero
for the decision, and ``record_delivery`` rolls the window and counts the
delivery in one SQL statement. (Rolling the window in memory here and
incrementing in SQL there let the increment overwrite the reset, so the
counter never went back to zero in production.) It never writes history:
the caller does, so each path can record the suppression where its own
history lives.

The suppression reason names the dial that stopped the send, so "why didn't
it arrive" is answered by the history row, not by someone's memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
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


def rate_window_lapsed(hour_started_at: Optional[datetime], now: datetime) -> bool:
    """True when no rate-limit window is open, or the open one is an hour old or more."""
    return hour_started_at is None or now - hour_started_at >= RATE_LIMIT_WINDOW


def effective_hourly_count(global_settings, now: datetime) -> int:
    """
    Deliveries counted in the current window, treating a lapsed window as
    zero. Read-only: use this for decisions and display instead of the raw
    column, which keeps the last window's total until the next delivery.
    """
    if not global_settings or rate_window_lapsed(global_settings.hour_started_at, now):
        return 0
    return global_settings.notifications_this_hour or 0


def record_delivery(global_settings, now: datetime) -> None:
    """
    Count one delivered notification against the hourly limit, starting a new
    window first if the current one has lapsed. Caller commits.

    On a database row this is one UPDATE whose CASE expressions read the
    stored values, so it is correct whatever the in-memory copy says and
    concurrent dispatches in separate sessions neither lose increments nor
    double-roll the window.
    """
    if not global_settings:
        return
    model = type(global_settings)
    count_col = getattr(model, "notifications_this_hour", None)
    started_col = getattr(model, "hour_started_at", None)
    if (
        isinstance(count_col, InstrumentedAttribute)
        and isinstance(started_col, InstrumentedAttribute)
        and sa_inspect(global_settings).persistent
    ):
        lapsed = or_(started_col.is_(None), started_col <= now - RATE_LIMIT_WINDOW)
        global_settings.notifications_this_hour = case((lapsed, 1), else_=func.coalesce(count_col, 0) + 1)
        global_settings.hour_started_at = case((lapsed, now), else_=started_col)
        return
    # Plain objects (no database row): same rule in Python.
    if rate_window_lapsed(global_settings.hour_started_at, now):
        global_settings.hour_started_at = now
        global_settings.notifications_this_hour = 1
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

    # 5. hourly rate limit (read-only; record_delivery rolls and counts)
    if gs and gs.max_notifications_per_hour:
        if effective_hourly_count(gs, now) >= gs.max_notifications_per_hour:
            return GateDecision.deny(f"rate_limit ({gs.max_notifications_per_hour}/hour)", priority)

    return GateDecision(allow=True, priority=priority, notes=notes)


async def get_global_settings(db: AsyncSession):
    """The singleton SystemNotificationGlobalSettings row, or None before first seed."""
    from api.models.system_notifications import SystemNotificationGlobalSettings

    result = await db.execute(select(SystemNotificationGlobalSettings).limit(1))
    return result.scalar_one_or_none()
