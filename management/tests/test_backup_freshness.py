"""
The backup dead-man's switch (system_monitors.check_backup_freshness):
overdue scheduled backups and backups stuck in 'running' alert, and stuck
rows are closed out.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from api.services import system_monitors as monitors

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


async def _fresh(db, model, row_id):
    """Re-read a row the code under test changed through its own session."""
    result = await db.execute(
        select(model).where(model.id == row_id).execution_options(populate_existing=True)
    )
    return result.scalar_one()


@pytest.fixture
async def events(db, session_maker, channel, add_target):
    """Seeded registry with the shared channel on the two backup monitor events."""
    from api.database import seed_system_notification_events
    from api.models.system_notifications import SystemNotificationEvent

    await seed_system_notification_events()
    result = await db.execute(
        select(SystemNotificationEvent).where(SystemNotificationEvent.event_type.in_(["backup_overdue", "backup_stuck"]))
    )
    found = {e.event_type: e for e in result.scalars().all()}
    assert set(found) == {"backup_overdue", "backup_stuck"}
    for event in found.values():
        await add_target(event, channel)
    return found


@pytest.fixture
def make_schedule(db):
    from api.models.backups import BackupSchedule

    async def _make(frequency="daily", created_ago=timedelta(days=10), last_run_ago=None, edited_ago=None, **kw):
        created = NOW - created_ago
        last_run = NOW - last_run_ago if last_run_ago is not None else None
        schedule = BackupSchedule(
            name=kw.pop("name", f"{frequency} backup"),
            backup_type="postgres_full",
            frequency=frequency,
            hour=2,
            minute=0,
            enabled=kw.pop("enabled", True),
            created_at=created,
            last_run=last_run,
            updated_at=NOW - edited_ago if edited_ago is not None else (last_run or created),
            config_changed_at=NOW - edited_ago if edited_ago is not None else created,
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        return schedule

    return _make


@pytest.fixture
def make_history(db):
    from api.models.backups import BackupHistory

    async def _make(status="success", ago=timedelta(hours=1), schedule=None, duration=timedelta(minutes=5)):
        started = NOW - ago
        row = BackupHistory(
            backup_type="postgres_full",
            schedule_id=schedule.id if schedule else None,
            filename="f",
            filepath="/x/f",
            status=status,
            started_at=started,
            completed_at=started + duration if status != "running" else None,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    return _make


async def test_missed_daily_backup_is_overdue(events, make_schedule, make_history, sent, history_rows):
    schedule = await make_schedule("daily", last_run_ago=timedelta(days=3))
    await make_history("success", ago=timedelta(days=3), schedule=schedule)

    fired = await monitors.check_backup_freshness(NOW)

    assert fired == [f"backup_overdue:schedule:{schedule.id}"]
    assert "daily backup" in sent.calls[0]["message"] and "overdue" in sent.calls[0]["message"]
    rows = await history_rows("backup_overdue")
    assert rows[0].target_id == f"schedule:{schedule.id}" and rows[0].status == "sent"


async def test_schedule_that_never_succeeded_is_overdue(events, make_schedule, sent):
    schedule = await make_schedule("hourly", created_ago=timedelta(hours=5))

    assert await monitors.check_backup_freshness(NOW) == [f"backup_overdue:schedule:{schedule.id}"]
    assert "never" in sent.calls[0]["message"]


async def test_failures_alone_do_not_count_as_success(events, make_schedule, make_history, sent):
    schedule = await make_schedule("daily", last_run_ago=timedelta(hours=10))
    await make_history("failed", ago=timedelta(hours=10), schedule=schedule)
    await make_history("success", ago=timedelta(days=4), schedule=schedule)

    assert await monitors.check_backup_freshness(NOW) == [f"backup_overdue:schedule:{schedule.id}"]


@pytest.mark.parametrize("frequency,ago", [
    ("hourly", timedelta(minutes=90)),     # within 1h + 60 min grace
    ("daily", timedelta(hours=24, minutes=30)),
    ("weekly", timedelta(days=7)),
    ("monthly", timedelta(days=30)),
])
async def test_recent_success_is_not_overdue(events, make_schedule, make_history, sent, frequency, ago):
    schedule = await make_schedule(frequency, created_ago=timedelta(days=60), last_run_ago=ago)
    await make_history("success", ago=ago, schedule=schedule)

    assert await monitors.check_backup_freshness(NOW) == []
    assert sent.calls == []


async def test_recently_edited_schedule_gets_a_full_interval(events, make_schedule, make_history, sent):
    """Re-enabling a schedule that was off for weeks must not alert straight away."""
    schedule = await make_schedule("daily", last_run_ago=timedelta(days=30), edited_ago=timedelta(hours=2))
    await make_history("success", ago=timedelta(days=30), schedule=schedule)

    assert await monitors.check_backup_freshness(NOW) == []


async def test_disabled_schedule_and_disabled_event_are_quiet(db, events, make_schedule, sent):
    await make_schedule("daily", name="off", enabled=False)
    assert await monitors.check_backup_freshness(NOW) == []

    await make_schedule("daily", name="on")
    events["backup_overdue"].enabled = False
    await db.commit()
    assert await monitors.check_backup_freshness(NOW) == []
    assert sent.calls == []


async def test_grace_is_read_from_the_event(db, events, make_schedule, make_history, sent):
    schedule = await make_schedule("daily", last_run_ago=timedelta(hours=25))
    await make_history("success", ago=timedelta(hours=25), schedule=schedule)
    assert await monitors.check_backup_freshness(NOW) == []

    events["backup_overdue"].thresholds = {"grace_minutes": 10}
    await db.commit()
    assert await monitors.check_backup_freshness(NOW) == [f"backup_overdue:schedule:{schedule.id}"]


async def test_stuck_running_backup_is_failed_and_alerted(db, events, make_history, sent, history_rows):
    from api.models.backups import BackupHistory

    stuck = await make_history("running", ago=timedelta(hours=7))
    live = await make_history("running", ago=timedelta(hours=1))

    fired = await monitors.check_backup_freshness(NOW)

    assert fired == [f"backup_stuck:backup:{stuck.id}"]
    assert f"#{stuck.id}" in sent.calls[0]["message"]
    closed = await _fresh(db, BackupHistory, stuck.id)
    assert closed.status == "failed" and closed.completed_at is not None
    assert "still 'running'" in closed.error_message
    assert (await _fresh(db, BackupHistory, live.id)).status == "running"

    # Closed out: a second pass does not alert again
    assert await monitors.check_backup_freshness(NOW) == []


async def test_stuck_rows_are_closed_even_when_the_event_is_off(db, events, make_history, sent):
    from api.models.backups import BackupHistory

    events["backup_stuck"].enabled = False
    await db.commit()
    stuck = await make_history("running", ago=timedelta(hours=8))

    assert await monitors.check_backup_freshness(NOW) == []
    assert (await _fresh(db, BackupHistory, stuck.id)).status == "failed"


async def test_new_backup_events_inherit_backup_failure_targets(db, session_maker, make_event, channel, add_target):
    from api.database import seed_system_notification_events
    from api.models.system_notifications import SystemNotificationEvent, SystemNotificationTarget

    failure = await make_event("backup_failure", category="backup", severity="critical")
    await add_target(failure, channel)

    await seed_system_notification_events()

    for event_type in ("backup_overdue", "backup_stuck"):
        event = (await db.execute(
            select(SystemNotificationEvent).where(SystemNotificationEvent.event_type == event_type)
        )).scalar_one()
        targets = (await db.execute(
            select(SystemNotificationTarget).where(SystemNotificationTarget.event_id == event.id)
        )).scalars().all()
        assert [t.channel_id for t in targets] == [channel.id], event_type


# --- a restart must not reset the overdue baseline -----------------------------------------------

class _FakeScheduler:
    """Just enough of AsyncIOScheduler for the next_run persistence paths."""

    def __init__(self, next_run):
        self.next_run = next_run
        self.jobs = {}

    def add_job(self, func, trigger, args, id, name, replace_existing):  # noqa: A002
        from types import SimpleNamespace

        self.jobs[id] = SimpleNamespace(id=id, next_run_time=self.next_run)

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def get_jobs(self):
        return list(self.jobs.values())


async def test_scheduler_start_does_not_reset_the_overdue_baseline(
    db, events, make_schedule, make_history, sent, monkeypatch
):
    """init_scheduler persists next_run on every start; that is not a human edit."""
    from api.models.backups import BackupSchedule
    from api.models.system_notifications import SystemNotificationState
    from api.tasks import scheduler as sched

    schedule = await make_schedule("daily", created_ago=timedelta(days=10), last_run_ago=timedelta(hours=72))
    await make_history("success", ago=timedelta(hours=72), schedule=schedule)
    assert await monitors.check_backup_freshness(NOW) == [f"backup_overdue:schedule:{schedule.id}"]
    before = await _fresh(db, BackupSchedule, schedule.id)

    fake = _FakeScheduler(next_run=NOW + timedelta(hours=14))
    monkeypatch.setattr(sched, "scheduler", fake)
    await sched.add_backup_job(before)
    await sched._persist_backup_next_run_times()

    after = await _fresh(db, BackupSchedule, schedule.id)
    assert after.next_run is not None and after.apscheduler_job_id == f"backup_{schedule.id}"
    assert after.updated_at == before.updated_at, "persisting next_run bumped updated_at"
    assert after.config_changed_at == before.config_changed_at

    await db.execute(SystemNotificationState.__table__.update().values(last_sent_at=None))
    await db.commit()
    assert await monitors.check_backup_freshness(NOW + timedelta(minutes=5)) == [
        f"backup_overdue:schedule:{schedule.id}"
    ], "a management restart silenced the overdue alarm"


async def test_baseline_ignores_updated_at_when_config_changed_at_is_set(make_schedule):
    schedule = await make_schedule("daily", created_ago=timedelta(days=10), last_run_ago=timedelta(hours=72))
    schedule.updated_at = NOW  # bumped by something other than a person
    assert monitors._schedule_baseline(schedule, NOW - timedelta(hours=72)) == NOW - timedelta(hours=72)


async def test_schedule_edit_through_the_api_restarts_the_baseline(
    db, session_maker, events, make_schedule, make_history, sent
):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from httpx import AsyncClient

    from api.database import get_db
    from api.dependencies import get_current_user
    from api.models.backups import BackupSchedule
    from api.routers import backups

    schedule = await make_schedule("daily", created_ago=timedelta(days=10), last_run_ago=timedelta(hours=72))
    await make_history("success", ago=timedelta(hours=72), schedule=schedule)
    schedule.timezone = "UTC"
    await db.commit()

    app = FastAPI()
    app.include_router(backups.router, prefix="/api/backups")

    async def _db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    async with AsyncClient(app=app, base_url="http://test") as http:
        response = await http.put(f"/api/backups/schedules/{schedule.id}", json={"hour": 3})
    assert response.status_code == 200, response.text

    edited = await _fresh(db, BackupSchedule, schedule.id)
    assert edited.config_changed_at > NOW
    assert await monitors.check_backup_freshness(NOW + timedelta(days=1)) == []


# --- a long backup that is still running is not stuck ---------------------------------------------

@pytest.fixture
def started_before_backups(monkeypatch):
    """This process started before the test's backups did."""
    monkeypatch.setattr(monitors, "PROCESS_STARTED_AT", NOW - timedelta(days=1))


async def test_live_long_backup_is_not_marked_stuck(db, events, make_history, sent, started_before_backups):
    from api.models.backups import BackupHistory
    from api.services.operation_lock import exclusive_operation

    row = await make_history("running", ago=timedelta(hours=7))
    async with exclusive_operation("backup"):
        assert await monitors.check_backup_freshness(NOW) == []
    fresh = await _fresh(db, BackupHistory, row.id)
    assert fresh.status == "running" and fresh.error_message is None
    assert sent.calls == []


async def test_active_backup_job_also_counts_as_live(
    db, events, make_history, sent, started_before_backups, monkeypatch
):
    from types import SimpleNamespace

    from api.models.backups import BackupHistory
    from api.services import operation_jobs

    monkeypatch.setattr(operation_jobs, "active_job", lambda: SimpleNamespace(kind="backup"))
    row = await make_history("running", ago=timedelta(hours=7))
    assert await monitors.check_backup_freshness(NOW) == []
    assert (await _fresh(db, BackupHistory, row.id)).status == "running"


async def test_row_from_before_a_restart_is_closed_even_while_a_backup_runs(
    db, events, make_history, sent, monkeypatch
):
    from api.models.backups import BackupHistory
    from api.services.operation_lock import exclusive_operation

    monkeypatch.setattr(monitors, "PROCESS_STARTED_AT", NOW - timedelta(hours=2))
    orphan = await make_history("running", ago=timedelta(hours=7))
    async with exclusive_operation("backup"):
        assert await monitors.check_backup_freshness(NOW) == [f"backup_stuck:backup:{orphan.id}"]
    assert (await _fresh(db, BackupHistory, orphan.id)).status == "failed"
