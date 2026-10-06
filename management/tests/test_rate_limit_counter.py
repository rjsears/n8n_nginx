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
        assert row.notifications_this_hour == 1
