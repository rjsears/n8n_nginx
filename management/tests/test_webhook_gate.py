"""
The n8n webhook path (NotificationService.send_webhook_notification) goes
through the same gate as system events: global dials only, and a suppressed
call is recorded in the notification history.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select


@pytest.fixture
def transport(monkeypatch):
    """Record NotificationDispatcher.send calls; deliver successfully."""
    from api.services.notification_service import NotificationDispatcher

    calls = []

    async def send(self, service, title, body, priority="normal", event_data=None):
        calls.append({"service": service.name, "title": title, "priority": priority, "event_data": event_data})
        return True

    monkeypatch.setattr(NotificationDispatcher, "send", send)
    return calls


async def _webhook_history(db):
    from api.models.notifications import NotificationHistory

    result = await db.execute(
        select(NotificationHistory)
        .where(NotificationHistory.event_type == "webhook.notification")
        .order_by(NotificationHistory.id)
    )
    return list(result.scalars().all())


async def _send(db, priority="normal", title="Workflow finished"):
    from api.services.notification_service import NotificationService

    return await NotificationService(db).send_webhook_notification(
        title=title, message="body", priority=priority, targets=["all"]
    )


async def test_webhook_delivers_and_counts_against_rate_limit(db, global_settings, channel, transport):
    result = await _send(db)

    assert result["success"] is True and result["channels_notified"] == 1
    assert result.get("suppressed") is None
    assert transport[0]["event_data"] == {"source": "n8n_webhook", "targets": ["all"]}
    await db.refresh(global_settings)
    assert global_settings.notifications_this_hour == 1


async def test_webhook_suppressed_during_maintenance(db, global_settings, channel, transport):
    global_settings.maintenance_mode = True
    global_settings.maintenance_until = datetime.now(UTC) + timedelta(hours=1)
    await db.commit()

    result = await _send(db)

    assert result["success"] is False
    assert result["suppressed"] == "maintenance"
    assert result["channels_notified"] == 0
    assert transport == []
    rows = await _webhook_history(db)
    assert [(r.status, r.error_message) for r in rows] == [("suppressed", "suppressed: maintenance")]


async def test_webhook_respects_rate_limit(db, global_settings, channel, transport):
    global_settings.max_notifications_per_hour = 1
    await db.commit()

    first = await _send(db)
    second = await _send(db)

    assert first["success"] is True
    assert second["success"] is False and second["suppressed"] == "rate_limit (1/hour)"
    assert len(transport) == 1


async def test_webhook_priority_lowered_in_quiet_hours(db, global_settings, channel, transport):
    from api.services.notification_gate import local_now

    local = local_now(datetime.now(UTC))
    global_settings.quiet_hours_enabled = True
    global_settings.quiet_hours_start = (local - timedelta(hours=1)).strftime("%H:%M")
    global_settings.quiet_hours_end = (local + timedelta(hours=1)).strftime("%H:%M")
    global_settings.quiet_hours_reduce_priority = True
    await db.commit()

    result = await _send(db, priority="high")

    assert result["success"] is True
    assert transport[0]["priority"] == "low"


async def test_webhook_event_gates_do_not_apply(db, global_settings, channel, transport):
    """No event row, so no cooldown/frequency: two back-to-back calls both deliver."""
    assert (await _send(db))["success"] is True
    assert (await _send(db))["success"] is True
    assert len(transport) == 2
