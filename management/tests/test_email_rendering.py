"""
Email bodies are sent as plain text, never rendered as templates.

red-mail renders bodies as Jinja templates by default. Notification text
comes from outside (n8n workflows through the webhook, backup error text,
container names), so "{{ ... }}" in it would run as Python inside the
management container, which holds the Docker socket.
"""

from __future__ import annotations

import pytest

from api.services.email_service import build_email_sender
from api.services.notification_service import NotificationDispatcher

PAYLOAD = "{{ 7*7 }} {{ cycler.__init__.__globals__.os.getcwd() }}"


def test_sender_does_not_render_jinja():
    sender = build_email_sender("localhost", 587)

    assert sender.use_jinja is False
    msg = sender.get_message(
        subject="s", sender="a@example.com", receivers=["b@example.com"],
        text=PAYLOAD, html=f"<p>{PAYLOAD}</p>",
    )
    assert msg.get_body(("plain",)).get_content().strip() == PAYLOAD
    html_part = msg.get_body(("html",)).get_content()
    assert "{{ 7*7 }}" in html_part and "49" not in html_part


def test_implicit_tls_sender_does_not_render_jinja():
    assert build_email_sender("smtp.example.com", 465).use_jinja is False


@pytest.fixture
def captured(monkeypatch):
    """Run NotificationDispatcher.send_email with the real sender, capturing the message instead of sending."""
    import api.services.email_service as email_service

    messages = []
    real_build = email_service.build_email_sender

    def build(*args, **kwargs):
        sender = real_build(*args, **kwargs)

        def send(**send_kwargs):
            messages.append(sender.get_message(**send_kwargs))

        sender.send = send
        return sender

    monkeypatch.setattr(email_service, "build_email_sender", build)
    return messages


async def test_notification_email_sends_template_syntax_literally(captured):
    config = {"smtp_server": "smtp.example.com", "smtp_port": 587, "to_emails": ["ops@example.com"]}

    ok = await NotificationDispatcher().send_email(config, f"Title {PAYLOAD}", f"Body {PAYLOAD}", "high")

    assert ok is True
    msg = captured[0]
    assert msg.get_body(("plain",)).get_content().strip() == f"Body {PAYLOAD}"
    html_part = msg.get_body(("html",)).get_content()
    assert "49" not in html_part and "/home" not in html_part


async def test_notification_email_escapes_html(captured):
    config = {"smtp_server": "smtp.example.com", "smtp_port": 587, "to_emails": ["ops@example.com"]}
    body = 'Backup failed: <a href="https://evil.example">click</a>\nsecond line'

    await NotificationDispatcher().send_email(config, "<b>Alert</b>", body, "normal")

    html_part = captured[0].get_body(("html",)).get_content()
    assert "<a href" not in html_part and "&lt;a href=&quot;https://evil.example&quot;&gt;" in html_part
    assert "&lt;b&gt;Alert&lt;/b&gt;" in html_part
    assert "second line" in html_part and "<br>second line" in html_part
