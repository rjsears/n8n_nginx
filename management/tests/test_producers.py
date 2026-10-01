"""
The sampling producers in api.services.system_monitors: given sampled data
and the registry's thresholds, the right event is dispatched with the right
payload, and nothing fires below threshold.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from api.services import system_monitors as monitors


@pytest.fixture
async def seeded(db, session_maker):
    """All default events, each enabled with the shared channel as L1 target."""
    from api.database import seed_system_notification_events

    await seed_system_notification_events()


@pytest.fixture
async def targeted(db, seeded, channel, add_target):
    """Attach the channel to every seeded event and return {event_type: event}."""
    from api.models.system_notifications import SystemNotificationEvent

    result = await db.execute(select(SystemNotificationEvent))
    events = {e.event_type: e for e in result.scalars().all()}
    for event in events.values():
        await add_target(event, channel)
    return events


def _host(cpu=10, memory=10, disk=10):
    return {
        "cpu": {"percent": cpu, "count": 4},
        "memory": {"percent": memory, "available": 1},
        "disk": {"percent": disk, "free": 1},
    }


# --- host metrics ----------------------------------------------------------------------------

async def test_host_metrics_quiet_below_threshold(targeted, sent):
    fired = await monitors.check_host_metrics(_host(cpu=50, memory=50, disk=50))
    assert fired == [] and sent.calls == []


async def test_disk_and_memory_fire_at_seeded_threshold(targeted, sent):
    fired = await monitors.check_host_metrics(_host(memory=91, disk=95))

    assert fired == ["disk_space_low", "high_memory"]
    messages = "\n".join(c["message"] for c in sent.calls)
    assert "Usage: 95%" in messages and "threshold 90%" in messages
    assert "91%" in messages


async def test_thresholds_are_read_from_the_event_row(db, targeted, sent):
    disk = targeted["disk_space_low"]
    disk.thresholds = {"percent": 60}
    await db.commit()

    fired = await monitors.check_host_metrics(_host(disk=65))

    assert fired == ["disk_space_low"]


async def test_disabled_event_does_not_fire(db, targeted, sent):
    targeted["high_memory"].enabled = False
    await db.commit()

    fired = await monitors.check_host_metrics(_host(memory=99))

    assert fired == [] and sent.calls == []


async def test_high_cpu_single_sample_when_duration_is_one_interval(targeted, sent):
    # seeded: 90% for 5 minutes; samples every 5 minutes -> one sample suffices
    fired = await monitors.check_host_metrics(_host(cpu=95))

    assert fired == ["high_cpu"]
    assert "for 5 min" in sent.calls[0]["message"]


async def test_high_cpu_sustained_needs_earlier_samples(db, targeted, sent):
    from api.models.audit import SystemMetricsCache

    targeted["high_cpu"].thresholds = {"percent": 90, "duration_minutes": 15}
    await db.commit()
    now = datetime.now(UTC)

    # Only one earlier high sample: not sustained yet
    db.add(SystemMetricsCache(metric_type="cpu", metric_data={"percent": 97}, collected_at=now - timedelta(minutes=5)))
    await db.commit()
    assert await monitors.check_host_metrics(_host(cpu=96), now=now) == []

    # A second earlier high sample completes the 15-minute window
    db.add(SystemMetricsCache(metric_type="cpu", metric_data={"percent": 93}, collected_at=now - timedelta(minutes=10)))
    await db.commit()
    assert await monitors.check_host_metrics(_host(cpu=96), now=now) == ["high_cpu"]


async def test_high_cpu_dip_inside_window_is_not_sustained(db, targeted, sent):
    from api.models.audit import SystemMetricsCache

    targeted["high_cpu"].thresholds = {"percent": 90, "duration_minutes": 15}
    await db.commit()
    now = datetime.now(UTC)
    db.add(SystemMetricsCache(metric_type="cpu", metric_data={"percent": 97}, collected_at=now - timedelta(minutes=5)))
    db.add(SystemMetricsCache(metric_type="cpu", metric_data={"percent": 40}, collected_at=now - timedelta(minutes=10)))
    await db.commit()

    assert await monitors.check_host_metrics(_host(cpu=96), now=now) == []


async def test_host_events_are_throttled_by_their_frequency(targeted, sent, history_rows):
    await monitors.check_host_metrics(_host(memory=95))
    await monitors.check_host_metrics(_host(memory=95))

    rows = await history_rows("high_memory")
    assert [r.status for r in rows] == ["sent", "suppressed"]
    assert rows[1].suppression_reason == "frequency (once_per_hour)"


# --- container resources ----------------------------------------------------------------------

async def _config(db, name, **kw):
    from api.models.system_notifications import SystemNotificationContainerConfig

    row = SystemNotificationContainerConfig(container_name=name, **kw)
    db.add(row)
    await db.commit()
    return row


async def test_container_resources_skip_when_nothing_monitored(db, targeted, sent):
    await _config(db, "n8n_postgres", monitor_high_cpu=False, monitor_high_memory=False)

    fired = await monitors.check_container_resources([{"name": "n8n_postgres", "cpu_percent": 99, "memory_percent": 99}])

    assert fired == [] and sent.calls == []


async def test_container_thresholds_come_from_container_config(db, targeted, sent):
    await _config(db, "n8n_postgres", monitor_high_cpu=True, cpu_threshold=50, monitor_high_memory=True, memory_threshold=95)

    fired = await monitors.check_container_resources([
        {"name": "n8n_postgres", "cpu_percent": 55, "memory_percent": 80},
        {"name": "n8n_nginx", "cpu_percent": 99, "memory_percent": 99},   # no config -> ignored
    ])

    assert fired == ["container_high_cpu:n8n_postgres"]
    assert sent.calls[0]["message"].count("n8n_postgres") == 1
    assert "Threshold: 50%" in sent.calls[0]["message"]


async def test_container_monitor_flag_gates_each_metric(db, targeted, sent):
    await _config(db, "n8n", monitor_high_cpu=False, cpu_threshold=10, monitor_high_memory=True, memory_threshold=10)

    fired = await monitors.check_container_resources([{"name": "n8n", "cpu_percent": 90, "memory_percent": 90}])

    assert fired == ["container_high_memory:n8n"]


# --- container recovery ------------------------------------------------------------------------

async def _open_episode(db, event_type, name):
    from api.models.system_notifications import SystemNotificationState

    state = SystemNotificationState(event_type=event_type, target_id=name, last_sent_at=datetime.now(UTC))
    db.add(state)
    await db.commit()
    return state


async def test_recovery_fires_once_and_closes_the_episode(db, targeted, sent, state_row):
    await _open_episode(db, "container_unhealthy", "n8n_postgres")

    recovered = await monitors.check_container_recovery({"healthy": ["n8n_postgres", "n8n"], "unhealthy": [], "stopped": []})

    assert recovered == ["n8n_postgres"]
    assert len(sent.calls) == 1 and "recovered" in sent.calls[0]["message"] and "was unhealthy" in sent.calls[0]["message"]
    state = await state_row("container_unhealthy", "n8n_postgres")
    await db.refresh(state)
    assert state.last_sent_at is None, "the problem episode must be closed"

    # Still healthy next cycle: nothing more
    assert await monitors.check_container_recovery({"healthy": ["n8n_postgres"]}) == []
    assert len(sent.calls) == 1


async def test_recovery_ignores_containers_still_in_trouble(db, targeted, sent):
    await _open_episode(db, "container_stopped", "n8n_postgres")

    recovered = await monitors.check_container_recovery({"healthy": [], "stopped": ["n8n_postgres"]})

    assert recovered == [] and sent.calls == []


async def test_recovery_respects_notify_on_recovery_of_the_problem_event(db, targeted, sent, state_row):
    targeted["container_stopped"].notify_on_recovery = False
    await db.commit()
    await _open_episode(db, "container_stopped", "n8n_postgres")

    recovered = await monitors.check_container_recovery({"healthy": ["n8n_postgres"]})

    assert recovered == [] and sent.calls == []
    state = await state_row("container_stopped", "n8n_postgres")
    await db.refresh(state)
    assert state.last_sent_at is None, "the episode closes even when recovery is not announced"


# --- certificate expiry -------------------------------------------------------------------------

def _cert(domain, days, valid_until="Oct 12 10:00:00 2026 GMT"):
    return {"domain": domain, "days_until_expiry": days, "valid_until": valid_until}


async def test_certificate_fires_at_or_under_threshold_only(targeted, sent):
    fired = await monitors.check_certificate_expiry([
        _cert("a.example.com", 30),
        _cert("b.example.com", 14),
        _cert("c.example.com", 3),
        {"domain": "d.example.com"},  # unparseable date: skipped
    ])

    assert fired == ["b.example.com", "c.example.com"]
    assert "expires in 3 day(s)" in sent.calls[1]["message"]


async def test_expired_certificate_says_so(targeted, sent):
    fired = await monitors.check_certificate_expiry([_cert("x.example.com", -2)])

    assert fired == ["x.example.com"]
    assert "EXPIRED" in sent.calls[0]["message"]


async def test_certificates_throttle_per_domain(targeted, sent, history_rows):
    certs = [_cert("a.example.com", 5), _cert("b.example.com", 5)]
    await monitors.check_certificate_expiry(certs)
    await monitors.check_certificate_expiry(certs)

    assert len(sent.calls) == 2, "two domains, one delivery each"
    rows = await history_rows("certificate_expiring")
    assert sorted(r.target_id for r in rows if r.status == "sent") == ["a.example.com", "b.example.com"]
    assert all(r.suppression_reason == "frequency (once_per_day)" for r in rows if r.status == "suppressed")


async def test_certificate_threshold_from_event_row(db, targeted, sent):
    targeted["certificate_expiring"].thresholds = {"days": 45}
    await db.commit()

    assert await monitors.check_certificate_expiry([_cert("a.example.com", 40)]) == ["a.example.com"]


# --- security --------------------------------------------------------------------------------------

async def test_security_event_account_locked(targeted, sent):
    await monitors.report_security_event(
        "account_locked", target_id="user:admin", username="admin", failed_attempts=5,
        locked_until="2026-09-28T12:00:00+00:00", client_ip="10.0.0.9",
    )

    assert len(sent.calls) == 1
    message = sent.calls[0]["message"]
    assert "'admin' locked after 5 failed" in message and "10.0.0.9" in message
    assert sent.calls[0]["priority"] == "critical"


async def test_security_event_webhook_invalid_key(targeted, sent):
    await monitors.report_security_event("webhook_invalid_key", target_id="webhook", client_ip="203.0.113.5")

    assert "invalid API key" in sent.calls[0]["message"] and "203.0.113.5" in sent.calls[0]["message"]


async def test_security_event_never_raises(monkeypatch):
    import api.services.notification_service as ns

    async def boom(*a, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(ns, "dispatch_notification", boom)
    await monitors.report_security_event("account_locked", target_id="user:x")


async def test_lockout_reports_security_event(db, monkeypatch):
    """AuthService._increment_failed_attempts reports the lockout with the client IP."""
    from types import SimpleNamespace

    from api.services import auth_service as auth_module
    from api.services.auth_service import AuthService

    reported = []

    async def fake_report(kind, target_id, **details):
        reported.append((kind, target_id, details))

    monkeypatch.setattr("api.services.system_monitors.report_security_event", fake_report)
    monkeypatch.setattr(auth_module, "calculate_lockout_expiry", lambda attempts: datetime(2026, 9, 28, tzinfo=UTC) if attempts >= 2 else None)

    class FakeDb:
        async def commit(self):
            pass

    user = SimpleNamespace(username="admin", failed_attempts=0, locked_until=None)
    service = AuthService(FakeDb())

    await service._increment_failed_attempts(user, client_ip="10.1.1.1")
    assert reported == []
    await service._increment_failed_attempts(user, client_ip="10.1.1.1")
    assert reported == [("account_locked", "user:admin", {
        "username": "admin", "failed_attempts": 2,
        "locked_until": "2026-09-28T00:00:00+00:00", "client_ip": "10.1.1.1",
    })]
