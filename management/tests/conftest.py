"""
Test harness for the management API.

Runs the real SQLAlchemy models and the real dispatch code against an
in-memory SQLite database, with the outbound transports (ntfy, apprise,
email, webhook) replaced by a recorder. No Docker, Postgres or network is
required.

Two SQLite accommodations are made here so production code needs none:

* ``JSONB`` columns compile to SQLite ``JSON``.
* SQLite returns naive datetimes; the result processor is patched to mark
  them UTC so the ``datetime.now(UTC)`` comparisons in the dispatch path
  behave as they do on PostgreSQL.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite.base import DATETIME as SQLiteDateTime
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

MANAGEMENT_DIR = Path(__file__).resolve().parents[1]
API_DIR = MANAGEMENT_DIR / "api"
if str(MANAGEMENT_DIR) not in sys.path:
    sys.path.insert(0, str(MANAGEMENT_DIR))


# --- SQLite accommodations -------------------------------------------------

@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


_original_datetime_result_processor = SQLiteDateTime.result_processor


def _utc_aware_result_processor(self, dialect, coltype):
    inner = _original_datetime_result_processor(self, dialect, coltype)

    def process(value):
        result = inner(value) if inner else value
        if isinstance(result, datetime) and result.tzinfo is None:
            result = result.replace(tzinfo=UTC)
        return result

    return process


SQLiteDateTime.result_processor = _utc_aware_result_processor


# --- Database fixtures ---------------------------------------------------------

@pytest.fixture
async def engine():
    import api.models  # noqa: F401  (registers every model on Base.metadata)
    from api.database import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # Only the notification tables. Other models use PostgreSQL-only types
    # (ARRAY) that SQLite cannot create, and nothing here touches them.
    tables = [
        table
        for name, table in Base.metadata.tables.items()
        if name.startswith("notification_")
        or name.startswith("system_notification_")
        or name == "system_metrics_cache"  # read by the sustained-CPU check
        or name in ("backup_schedules", "backup_history")  # read by the backup freshness check
        or name == "operation_jobs"  # background backup/verify/restore jobs
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def session_maker(engine, monkeypatch):
    """
    A session factory bound to the test database, installed as
    ``api.database.async_session_maker`` so code that opens its own session
    (``dispatch_notification``, the seeders) lands on the same database.
    """
    import api.database

    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api.database, "async_session_maker", maker)
    return maker


@pytest.fixture
async def db(session_maker):
    async with session_maker() as session:
        yield session


@pytest.fixture(autouse=True)
def _no_docker_lookup(monkeypatch):
    """The message formatter asks Docker for the container name; don't."""
    import api.services.notification_service as ns

    monkeypatch.setattr(ns, "_get_container_name", lambda: "test-host")


# --- Transport recorder ----------------------------------------------------------

class SentRecorder:
    """
    Replaces ``NotificationService.send_to_service`` / ``send_to_group``.
    Records every attempted delivery; ``fail = True`` makes them all fail.
    """

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.fail = False

    def _record(self, kind: str, target_id: int, title: str, message: str, priority: str):
        self.calls.append(
            {"kind": kind, "id": target_id, "title": title, "message": message, "priority": priority}
        )
        if self.fail:
            return {"success": False, "error": "recorder configured to fail"}
        return {"success": True, "sent_count": 1}

    @property
    def titles(self) -> List[str]:
        return [c["title"] for c in self.calls]


@pytest.fixture
def sent(monkeypatch) -> SentRecorder:
    from api.services.notification_service import NotificationService

    recorder = SentRecorder()

    async def send_to_service(self, service_id, title, message, priority="normal"):
        return recorder._record("channel", service_id, title, message, priority)

    async def send_to_group(self, group_id, title, message, priority="normal"):
        return recorder._record("group", group_id, title, message, priority)

    monkeypatch.setattr(NotificationService, "send_to_service", send_to_service)
    monkeypatch.setattr(NotificationService, "send_to_group", send_to_group)
    return recorder


# --- Row factories ---------------------------------------------------------------

@pytest.fixture
async def global_settings(db):
    from api.models.system_notifications import SystemNotificationGlobalSettings

    settings = SystemNotificationGlobalSettings()
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


@pytest.fixture
async def channel(db):
    from api.models.notifications import NotificationService as Channel

    row = Channel(
        name="Ops ntfy",
        slug="ops-ntfy",
        service_type="ntfy",
        enabled=True,
        config={"topic": "ops", "token": "tk_super_secret", "server": "https://ntfy.example"},
        webhook_enabled=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.fixture
def make_event(db):
    from api.models.system_notifications import SystemNotificationEvent

    async def _make(event_type: str = "container_stopped", **overrides):
        defaults = {
            "display_name": event_type.replace("_", " ").title(),
            "category": "container",
            "severity": "warning",
            "frequency": "every_time",
            "cooldown_minutes": 0,
            "enabled": True,
        }
        defaults.update(overrides)
        event = SystemNotificationEvent(event_type=event_type, **defaults)
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    return _make


@pytest.fixture
def add_target(db):
    from api.models.system_notifications import SystemNotificationTarget

    async def _add(event, channel, level: int = 1, timeout: Optional[int] = None):
        target = SystemNotificationTarget(
            event_id=event.id,
            target_type="channel",
            channel_id=channel.id,
            escalation_level=level,
            escalation_timeout_minutes=timeout,
        )
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    return _add


@pytest.fixture
def history_rows(db):
    from sqlalchemy import select

    from api.models.system_notifications import SystemNotificationHistory

    async def _rows(event_type: Optional[str] = None):
        query = select(SystemNotificationHistory).order_by(SystemNotificationHistory.id)
        if event_type:
            query = query.where(SystemNotificationHistory.event_type == event_type)
        result = await db.execute(query)
        return list(result.scalars().all())

    return _rows


@pytest.fixture
def state_row(db):
    from sqlalchemy import select

    from api.models.system_notifications import SystemNotificationState

    async def _row(event_type: str, target_id: str):
        result = await db.execute(
            select(SystemNotificationState).where(
                SystemNotificationState.event_type == event_type,
                SystemNotificationState.target_id == target_id,
            )
        )
        return result.scalar_one_or_none()

    return _row
