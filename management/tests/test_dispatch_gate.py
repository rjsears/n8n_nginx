"""
Behaviour of ``dispatch_notification``: what suppresses, what delivers, and
that every suppression leaves a history row saying why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


async def _dispatch(event_type: str, data: dict | None = None, severity: str = "warning"):
    from api.services.notification_service import dispatch_notification

    await dispatch_notification(event_type, data or {"container": "n8n_postgres"}, severity=severity)


# --- registration -----------------------------------------------------------------

async def test_container_recreated_is_registered_and_delivers(db, session_maker, channel, add_target, sent, history_rows):
    from sqlalchemy import select

    from api.database import seed_system_notification_events
    from api.models.system_notifications import SystemNotificationEvent

    await seed_system_notification_events()
    result = await db.execute(
        select(SystemNotificationEvent).where(SystemNotificationEvent.event_type == "container_recreated")
    )
    event = result.scalar_one_or_none()
    assert event is not None, "container_recreated is dispatched by container_service but not registered"
    await add_target(event, channel)

    await _dispatch("container_recreated", {"container": "n8n", "action": "pulled and recreated", "pulled": True})

    assert len(sent.calls) == 1
    assert "recreated" in sent.calls[0]["message"]
    rows = await history_rows("container_recreated")
    assert [r.status for r in rows] == ["sent"]


# --- maintenance mode ---------------------------------------------------------------

async def test_active_maintenance_suppresses_and_records_it(db, global_settings, channel, make_event, add_target, sent, history_rows):
    event = await make_event()
    await add_target(event, channel)
    global_settings.maintenance_mode = True
    global_settings.maintenance_until = datetime.now(UTC) + timedelta(hours=2)
    await db.commit()

    await _dispatch(event.event_type)

    assert sent.calls == []
    rows = await history_rows(event.event_type)
    assert len(rows) == 1
    assert rows[0].status == "suppressed"
    assert rows[0].suppression_reason == "maintenance"


async def test_open_ended_maintenance_suppresses(db, global_settings, channel, make_event, add_target, sent):
    event = await make_event()
    await add_target(event, channel)
    global_settings.maintenance_mode = True
    global_settings.maintenance_until = None
    await db.commit()

    await _dispatch(event.event_type)

    assert sent.calls == []


async def test_expired_maintenance_clears_itself_and_delivers(db, global_settings, channel, make_event, add_target, sent):
    event = await make_event()
    await add_target(event, channel)
    global_settings.maintenance_mode = True
    global_settings.maintenance_until = datetime.now(UTC) - timedelta(minutes=1)
    global_settings.maintenance_reason = "patching"
    await db.commit()

    await _dispatch(event.event_type)

    assert len(sent.calls) == 1, "a lapsed maintenance window must not keep suppressing"
    await db.refresh(global_settings)
    assert global_settings.maintenance_mode is False
    assert global_settings.maintenance_until is None


# --- event enabled / cooldown ---------------------------------------------------------

async def test_disabled_event_does_not_deliver(db, channel, make_event, add_target, sent):
    event = await make_event(enabled=False)
    await add_target(event, channel)

    await _dispatch(event.event_type)

    assert sent.calls == []


async def test_cooldown_suppresses_second_occurrence_with_reason(db, channel, make_event, add_target, sent, history_rows):
    event = await make_event(cooldown_minutes=15)
    await add_target(event, channel)

    await _dispatch(event.event_type)
    await _dispatch(event.event_type)

    assert len(sent.calls) == 1
    rows = await history_rows(event.event_type)
    assert [r.status for r in rows] == ["sent", "suppressed"]
    assert rows[1].suppression_reason == "cooldown (15min)"


async def test_unregistered_event_is_dropped_without_delivery(db, channel, sent):
    await _dispatch("not_a_real_event")
    assert sent.calls == []


# --- escalation -------------------------------------------------------------------------

async def test_l2_does_not_fire_when_escalation_disabled(db, channel, make_event, add_target, sent):
    event = await make_event(severity="critical", escalation_enabled=False)
    await add_target(event, channel, level=1)
    await add_target(event, channel, level=2)

    await _dispatch(event.event_type, severity="critical")

    assert [c["title"] for c in sent.calls] == [event.display_name], "escalation_enabled=False must gate L2"


async def test_l2_fires_immediately_for_critical_when_enabled(db, channel, make_event, add_target, sent, state_row):
    event = await make_event(severity="critical", escalation_enabled=True)
    await add_target(event, channel, level=1)
    await add_target(event, channel, level=2)

    await _dispatch(event.event_type, severity="critical")

    titles = [c["title"] for c in sent.calls]
    assert titles == [event.display_name, f"[ESCALATED] {event.display_name}"]
    state = await state_row(event.event_type, "n8n_postgres")
    assert state is not None and state.escalation_sent is True


async def test_l2_fires_when_l1_delivery_fails(db, channel, make_event, add_target, sent):
    event = await make_event(severity="warning", escalation_enabled=True)
    await add_target(event, channel, level=1)
    await add_target(event, channel, level=2)
    sent.fail = True

    await _dispatch(event.event_type)

    titles = [c["title"] for c in sent.calls]
    assert titles == [event.display_name, f"[ESCALATED] {event.display_name}"]


async def test_l2_does_not_fire_when_l1_succeeds_on_non_critical(db, channel, make_event, add_target, sent, state_row):
    event = await make_event(severity="warning", escalation_enabled=True)
    await add_target(event, channel, level=1)
    await add_target(event, channel, level=2, timeout=30)

    await _dispatch(event.event_type)

    assert [c["title"] for c in sent.calls] == [event.display_name]
    state = await state_row(event.event_type, "n8n_postgres")
    assert state is not None and state.escalation_sent is False


async def test_no_delayed_escalation_job_exists():
    """
    The time-delayed L2 job escalated unconditionally after a timeout, checked
    neither maintenance mode nor event.enabled, and its UI promised
    acknowledgement the product does not have. It must stay removed.
    """
    import api.tasks.scheduler as scheduler

    assert not hasattr(scheduler, "schedule_l2_escalation")
    assert not hasattr(scheduler, "_send_l2_escalation")


async def test_escalation_state_resets_on_each_new_occurrence(db, channel, make_event, add_target, sent, state_row):
    """
    Regression: escalation_sent was never cleared, so after the first L2 for a
    given (event, target) no later occurrence could ever escalate again.
    """
    event = await make_event(severity="warning", escalation_enabled=True)
    await add_target(event, channel, level=1)
    await add_target(event, channel, level=2)

    sent.fail = True
    await _dispatch(event.event_type)              # L1 fails -> L2 fires -> escalation_sent=True
    state = await state_row(event.event_type, "n8n_postgres")
    assert state.escalation_sent is True

    sent.fail = False
    await _dispatch(event.event_type)              # new occurrence, L1 succeeds -> no escalation
    await db.refresh(state)
    assert state.escalation_sent is False, "a new occurrence must start a fresh escalation cycle"

    sent.fail = True
    sent.calls.clear()
    await _dispatch(event.event_type)              # L1 fails again -> L2 must fire again
    assert any(c["title"].startswith("[ESCALATED]") for c in sent.calls)


# --- the shared gate, end to end ----------------------------------------------------------

def _bracket_now():
    from api.services.notification_gate import local_now

    local = local_now(datetime.now(UTC))
    return (local - timedelta(hours=1)).strftime("%H:%M"), (local + timedelta(hours=1)).strftime("%H:%M")


async def test_frequency_throttles_even_with_zero_cooldown(db, channel, make_event, add_target, sent, history_rows):
    event = await make_event(frequency="once_per_hour", cooldown_minutes=0)
    await add_target(event, channel)

    await _dispatch(event.event_type)
    await _dispatch(event.event_type)

    assert len(sent.calls) == 1
    rows = await history_rows(event.event_type)
    assert [r.status for r in rows] == ["sent", "suppressed"]
    assert rows[1].suppression_reason == "frequency (once_per_hour)"


async def test_rate_limit_suppresses_over_cap_and_counts_deliveries(db, global_settings, channel, make_event, add_target, sent, history_rows):
    global_settings.max_notifications_per_hour = 2
    await db.commit()
    event = await make_event(cooldown_minutes=0)
    await add_target(event, channel)

    for _ in range(3):
        await _dispatch(event.event_type)

    assert len(sent.calls) == 2
    rows = await history_rows(event.event_type)
    assert [r.status for r in rows] == ["sent", "sent", "suppressed"]
    assert rows[2].suppression_reason == "rate_limit (2/hour)"
    await db.refresh(global_settings)
    assert global_settings.notifications_this_hour == 2
    assert global_settings.hour_started_at is not None


async def test_quiet_hours_lower_priority_when_reduce_is_on(db, global_settings, channel, make_event, add_target, sent):
    start, end = _bracket_now()
    global_settings.quiet_hours_enabled = True
    global_settings.quiet_hours_start, global_settings.quiet_hours_end = start, end
    global_settings.quiet_hours_reduce_priority = True
    await db.commit()
    event = await make_event(severity="warning")
    await add_target(event, channel)

    await _dispatch(event.event_type)

    assert len(sent.calls) == 1
    assert sent.calls[0]["priority"] == "low"


async def test_quiet_hours_mute_suppresses_non_critical(db, global_settings, channel, make_event, add_target, sent, history_rows):
    start, end = _bracket_now()
    global_settings.quiet_hours_enabled = True
    global_settings.quiet_hours_start, global_settings.quiet_hours_end = start, end
    global_settings.quiet_hours_reduce_priority = False
    await db.commit()
    event = await make_event(severity="warning")
    await add_target(event, channel)

    await _dispatch(event.event_type)

    assert sent.calls == []
    rows = await history_rows(event.event_type)
    assert [(r.status, r.suppression_reason) for r in rows] == [("suppressed", "quiet_hours")]


async def test_quiet_hours_let_critical_through_at_full_priority(db, global_settings, channel, make_event, add_target, sent):
    start, end = _bracket_now()
    global_settings.quiet_hours_enabled = True
    global_settings.quiet_hours_start, global_settings.quiet_hours_end = start, end
    global_settings.quiet_hours_reduce_priority = False
    await db.commit()
    event = await make_event(severity="critical")
    await add_target(event, channel)

    await _dispatch(event.event_type, severity="critical")

    assert [c["priority"] for c in sent.calls] == ["critical"]


async def test_blackout_suppresses_critical_too(db, global_settings, channel, make_event, add_target, sent, history_rows):
    start, end = _bracket_now()
    global_settings.blackout_enabled = True
    global_settings.blackout_start, global_settings.blackout_end = start, end
    await db.commit()
    event = await make_event(severity="critical")
    await add_target(event, channel)

    await _dispatch(event.event_type, severity="critical")

    assert sent.calls == []
    rows = await history_rows(event.event_type)
    assert rows[0].suppression_reason == "blackout"
