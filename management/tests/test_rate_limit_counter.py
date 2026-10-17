"""
The hourly delivery counter must not lose increments when two dispatches,
each in its own session, record a delivery at the same time.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from api.models.system_notifications import SystemNotificationGlobalSettings
from api.services import notification_gate as gate


async def test_concurrent_deliveries_are_all_counted(session_maker, global_settings):
    now = datetime.now(UTC)
    async with session_maker() as s:
        row = await s.get(SystemNotificationGlobalSettings, global_settings.id)
        row.hour_started_at = now - timedelta(minutes=5)
        row.notifications_this_hour = 4
        await s.commit()

    # Two sessions load the same row before either commits - the lost-update case.
    async with session_maker() as a, session_maker() as b:
        row_a = await a.get(SystemNotificationGlobalSettings, global_settings.id)
        row_b = await b.get(SystemNotificationGlobalSettings, global_settings.id)
        gate.record_delivery(row_a, now)
        gate.record_delivery(row_b, now)
        await a.commit()
        await b.commit()

    async with session_maker() as s:
        count = (await s.execute(
            select(SystemNotificationGlobalSettings.notifications_this_hour)
            .where(SystemNotificationGlobalSettings.id == global_settings.id)
        )).scalar_one()
    assert count == 6


async def test_new_window_starts_at_one(session_maker, global_settings):
    now = datetime.now(UTC)
    async with session_maker() as s:
        row = await s.get(SystemNotificationGlobalSettings, global_settings.id)
        row.hour_started_at = now - timedelta(hours=2)
        row.notifications_this_hour = 40
        await s.commit()

    async with session_maker() as s:
        row = await s.get(SystemNotificationGlobalSettings, global_settings.id)
        gate.record_delivery(row, now)
        await s.commit()

    count, started = await _stored(session_maker, global_settings.id)
    assert count == 1
    assert started == now


async def _stored(session_maker, settings_id):
    async with session_maker() as s:
        row = (await s.execute(
            select(SystemNotificationGlobalSettings.notifications_this_hour,
                   SystemNotificationGlobalSettings.hour_started_at)
            .where(SystemNotificationGlobalSettings.id == settings_id)
        )).one()
    return row[0], row[1]


async def _seed(session_maker, settings_id, count, started, cap=50):
    async with session_maker() as s:
        row = await s.get(SystemNotificationGlobalSettings, settings_id)
        row.max_notifications_per_hour = cap
        row.notifications_this_hour = count
        row.hour_started_at = started
        await s.commit()


async def test_full_window_resets_after_an_hour_through_dispatch(
    session_maker, global_settings, channel, make_event, add_target, sent, history_rows,
):
    """
    Regression: a window that had reached the cap never reset in production
    (autoflush off). The in-memory reset in the gate was overwritten by the SQL
    increment, so the stored count kept growing (50 -> 51) and only about one
    alert per hour got through, critical ones included.
    """
    from api.services.notification_service import dispatch_notification

    await _seed(session_maker, global_settings.id, count=50, started=datetime.now(UTC) - timedelta(hours=2))
    event = await make_event(cooldown_minutes=0)
    await add_target(event, channel)

    for _ in range(3):
        await dispatch_notification(event.event_type, {"container": "n8n_postgres"})

    assert len(sent.calls) == 3, "all three fit in the new hour"
    count, started = await _stored(session_maker, global_settings.id)
    assert count == 3
    assert datetime.now(UTC) - started < timedelta(minutes=1)
    rows = await history_rows(event.event_type)
    assert [r.status for r in rows] == ["sent", "sent", "sent"]


async def test_cap_still_applies_after_a_reset(
    session_maker, global_settings, channel, make_event, add_target, sent, history_rows,
):
    from api.services.notification_service import dispatch_notification

    await _seed(session_maker, global_settings.id, count=2, started=datetime.now(UTC) - timedelta(hours=3), cap=2)
    event = await make_event(cooldown_minutes=0)
    await add_target(event, channel)

    for _ in range(3):
        await dispatch_notification(event.event_type, {"container": "n8n_postgres"})

    assert len(sent.calls) == 2
    rows = await history_rows(event.event_type)
    assert [r.status for r in rows] == ["sent", "sent", "suppressed"]
    assert rows[2].suppression_reason == "rate_limit (2/hour)"
    count, _ = await _stored(session_maker, global_settings.id)
    assert count == 2


async def test_suppressed_or_failed_sends_do_not_touch_the_counter(
    session_maker, global_settings, channel, make_event, add_target, sent,
):
    from api.services.notification_service import dispatch_notification

    started = datetime.now(UTC) - timedelta(hours=2)
    await _seed(session_maker, global_settings.id, count=50, started=started)
    event = await make_event(cooldown_minutes=0)
    await add_target(event, channel)
    sent.fail = True

    await dispatch_notification(event.event_type, {"container": "n8n_postgres"})

    count, stored_start = await _stored(session_maker, global_settings.id)
    assert (count, stored_start) == (50, started), "only a delivery rolls or counts"


async def test_settings_endpoint_reports_a_lapsed_window_as_zero(session_maker, global_settings):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from httpx import AsyncClient

    from api.database import get_db
    from api.dependencies import get_current_user
    from api.routers import system_notifications

    await _seed(session_maker, global_settings.id, count=50, started=datetime.now(UTC) - timedelta(hours=2))

    app = FastAPI()
    app.include_router(system_notifications.router, prefix="/api/system-notifications")

    async def _db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    async with AsyncClient(app=app, base_url="http://test") as http:
        response = await http.get("/api/system-notifications/global-settings")

    assert response.status_code == 200
    assert response.json()["notifications_this_hour"] == 0
