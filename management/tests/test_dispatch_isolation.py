"""
Notification sends must not block or break their callers: dispatch never
raises, a slow channel costs the caller at most DISPATCH_WAIT_SECONDS, every
transport send is bounded, failures while the database is down are logged
clearly and routed to the fallback URL, and SMTP has a timeout and SMTPS.
"""

from __future__ import annotations

import asyncio
import smtplib
import time

import pytest

import api.services.notification_service as ns


@pytest.fixture
def fallback_calls(monkeypatch):
    import api.services.external_alerts as external_alerts

    calls = []

    async def fake_notify(event_type, event_data, error):
        calls.append((event_type, event_data, error))
        return True

    monkeypatch.setattr(external_alerts, "notify_dispatch_failure", fake_notify)
    return calls


async def test_dispatch_never_raises(monkeypatch, fallback_calls):
    async def boom(event_type, event_data):
        raise RuntimeError("formatter exploded")

    monkeypatch.setattr(ns, "_dispatch_now", boom)

    await ns.dispatch_notification("backup_success", {"backup_id": 1})  # must not raise

    assert [c[0] for c in fallback_calls] == ["backup_success"]


async def test_database_outage_is_logged_and_sent_to_fallback(monkeypatch, fallback_calls, caplog):
    from sqlalchemy.exc import OperationalError

    async def db_down(event_type, event_data):
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))

    monkeypatch.setattr(ns, "_dispatch_now", db_down)

    with caplog.at_level("ERROR"):
        await ns.dispatch_notification("container_stopped", {"container": "n8n_postgres"})

    assert "management database is unreachable" in caplog.text
    assert fallback_calls and fallback_calls[0][1] == {"container": "n8n_postgres"}


async def test_slow_channel_does_not_hold_the_caller(
    monkeypatch, global_settings, make_event, channel, add_target, sent, history_rows
):
    event = await make_event("backup_success", category="backup", severity="info")
    await add_target(event, channel)

    release = asyncio.Event()
    from api.services.notification_service import NotificationService

    async def slow_send(self, service_id, title, message, priority="normal"):
        await release.wait()
        return {"success": True}

    monkeypatch.setattr(NotificationService, "send_to_service", slow_send)
    monkeypatch.setattr(ns, "DISPATCH_WAIT_SECONDS", 0.1)

    started = time.monotonic()
    await ns.dispatch_notification("backup_success", {"backup_id": 7})
    assert time.monotonic() - started < 1.0, "caller was held by a slow channel"

    # Delivery carries on in the background and still gets recorded
    release.set()
    assert await ns.drain_notifications(timeout=5) == 0
    assert [r.status for r in await history_rows("backup_success")] == ["sent"]


async def test_dispatches_are_serialised_in_order(monkeypatch, global_settings, make_event, channel, add_target, sent):
    event = await make_event("container_stopped")
    await add_target(event, channel)

    for name in ("a", "b", "c"):
        await ns.dispatch_notification("container_stopped", {"container": name}, wait=0)
    await ns.drain_notifications(timeout=5)

    assert ["'a'" in c["message"] for c in sent.calls] == [True, False, False]
    assert ["'c'" in c["message"] for c in sent.calls] == [False, False, True]


async def test_transport_send_is_bounded(monkeypatch):
    from types import SimpleNamespace

    dispatcher = ns.NotificationDispatcher()

    async def hang(config, title, body, priority):
        await asyncio.sleep(30)

    monkeypatch.setattr(dispatcher, "send_ntfy", hang)
    monkeypatch.setattr(ns, "SEND_TIMEOUT_SECONDS", 0.05)

    service = SimpleNamespace(service_type="ntfy", name="slow", config={})
    with pytest.raises(TimeoutError, match="timed out"):
        await dispatcher.send(service, "t", "b")


async def test_hung_channel_counts_as_failed_delivery(db, channel, monkeypatch):
    monkeypatch.setattr(ns, "SEND_TIMEOUT_SECONDS", 0.05)

    async def hang(self, config, title, body, priority):
        await asyncio.sleep(30)

    monkeypatch.setattr(ns.NotificationDispatcher, "send_ntfy", hang)

    result = await ns.NotificationService(db).send_to_service(channel.id, "t", "m")

    assert result["success"] is False and "timed out" in result["error"]


# --- SMTP ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("port,use_ssl,expected_cls,starttls", [
    (465, None, smtplib.SMTP_SSL, False),
    (587, None, smtplib.SMTP, True),
    (465, False, smtplib.SMTP, True),
    (2465, True, smtplib.SMTP_SSL, False),
])
def test_email_sender_tls_mode_and_timeout(port, use_ssl, expected_cls, starttls):
    from api.services.email_service import SMTP_TIMEOUT_SECONDS, build_email_sender

    sender = build_email_sender("smtp.example.com", port, "u", "p", use_starttls=True, use_ssl=use_ssl)

    assert sender.cls_smtp is expected_cls
    assert sender.use_starttls is starttls
    assert sender.kws_smtp["timeout"] == SMTP_TIMEOUT_SECONDS


async def test_email_channel_uses_smtps_on_port_465(monkeypatch):
    import api.services.email_service as email_service

    captured = {}

    class FakeSender:
        def send(self, **kwargs):
            captured["sent"] = kwargs

    def fake_build(host, port, username=None, password=None, use_starttls=True, use_ssl=None, **_):
        captured.update(host=host, port=port, username=username, use_ssl=use_ssl, starttls=use_starttls)
        captured["implicit"] = email_service.wants_implicit_tls(port, use_ssl)
        return FakeSender()

    monkeypatch.setattr(email_service, "build_email_sender", fake_build)

    ok = await ns.NotificationDispatcher().send_email(
        {
            "smtp_server": "mail.example.com", "smtp_port": 465, "smtp_user": "u", "smtp_password": "p",
            "from_email": "a@example.com", "to_emails": "b@example.com",
        },
        "Title", "Body", "normal",
    )

    assert ok is True
    assert captured["implicit"] is True and captured["username"] == "u"
    assert captured["sent"]["receivers"] == ["b@example.com"]
