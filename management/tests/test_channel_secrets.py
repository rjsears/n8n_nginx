"""
Channel secrets: what the API returns is redacted everywhere, and editing a
channel with the redacted config it was handed never overwrites a stored
secret with the mask.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.services.notification_secrets import MASK, merge_config_secrets, redact_config, redact_url


@pytest.fixture
async def client(session_maker):
    from fastapi import FastAPI

    from api.database import get_db
    from api.dependencies import get_current_user
    from api.routers import notifications

    app = FastAPI()
    app.include_router(notifications.router, prefix="/api/notifications")

    async def _db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")

    async with AsyncClient(app=app, base_url="http://test") as http:
        yield http


@pytest.fixture(autouse=True)
def _no_ntfy_sync(monkeypatch):
    """Channel create/update tries to mirror local ntfy topics; not under test here."""
    import api.routers.notifications as router_module

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(router_module, "_sync_ntfy_channel_to_topic", _noop)


async def _stored_config(session_maker, service_id):
    from api.models.notifications import NotificationService as Channel

    async with session_maker() as session:
        return (await session.get(Channel, service_id)).config


EMAIL_CONFIG = {
    "smtp_server": "smtp.example.com",
    "smtp_port": 587,
    "smtp_user": "alerts@example.com",
    "smtp_password": "hunter2",
    "from_email": "alerts@example.com",
    "to_emails": "ops@example.com",
}
WEBHOOK_CONFIG = {
    "url": "https://hooks.example.com/services/T000/B000/abcdefSECRET?token=qs-secret&channel=ops",
    "method": "POST",
    "headers": {"Authorization": "Bearer hdr-secret", "X-Api-Key": "key-secret", "Content-Type": "application/json"},
}
APPRISE_CONFIG = {"url": "tgram://123456:AAbot-token-secret/987654"}


# --- the redaction helper ------------------------------------------------------------------

def test_redact_covers_every_secret_shape():
    ntfy = redact_config({"server": "https://user:pw@ntfy.example", "topic": "ops", "token": "tk", "password": "p"}, "ntfy")
    assert ntfy == {"server": f"https://user:{MASK}@ntfy.example", "topic": "ops", "token": MASK, "password": MASK}

    email = redact_config(EMAIL_CONFIG, "email")
    assert email["smtp_password"] == MASK and email["smtp_user"] == "alerts@example.com"

    webhook = redact_config(WEBHOOK_CONFIG, "webhook")
    assert "abcdefSECRET" not in webhook["url"] and "qs-secret" not in webhook["url"]
    assert webhook["url"].startswith("https://hooks.example.com/")
    assert "channel=ops" in webhook["url"]
    assert webhook["headers"] == {"Authorization": MASK, "X-Api-Key": MASK, "Content-Type": "application/json"}

    apprise = redact_config(APPRISE_CONFIG, "apprise")
    assert apprise["url"] == f"tgram://{MASK}"

    generic = redact_config({"webhook_secret": "s", "bot_token": "t", "api_key": "k", "requires_auth": True}, "ntfy")
    assert generic == {"webhook_secret": MASK, "bot_token": MASK, "api_key": MASK, "requires_auth": True}


def test_redact_url_leaves_plain_urls_alone():
    assert redact_url("https://ntfy.sh", "ntfy", "server") == "https://ntfy.sh"
    assert redact_url("", "webhook") == ""


@pytest.mark.parametrize("service_type,config", [
    ("email", EMAIL_CONFIG),
    ("webhook", WEBHOOK_CONFIG),
    ("apprise", APPRISE_CONFIG),
    ("ntfy", {"server": "https://u:p@ntfy.example", "topic": "ops", "token": "tk_secret"}),
])
def test_echoing_the_redacted_config_keeps_every_secret(service_type, config):
    echoed = redact_config(config, service_type)
    assert merge_config_secrets(config, echoed, service_type) == config


def test_merge_rules():
    stored = {"topic": "ops", "token": "tk_old", "server": "https://ntfy.example"}

    # omitted secret is kept, non-secret change applies
    assert merge_config_secrets(stored, {"topic": "alerts", "server": "https://ntfy.example"}, "ntfy") == {
        "topic": "alerts", "token": "tk_old", "server": "https://ntfy.example",
    }
    # a new secret replaces the old one
    assert merge_config_secrets(stored, {**stored, "token": "tk_new"}, "ntfy")["token"] == "tk_new"
    # an empty string clears it
    assert merge_config_secrets(stored, {**stored, "token": ""}, "ntfy")["token"] == ""
    # webhook: a new URL replaces; a header the client dropped is gone; a masked one is kept
    merged = merge_config_secrets(
        WEBHOOK_CONFIG,
        {"url": "https://new.example/hook", "method": "POST", "headers": {"Authorization": MASK}},
        "webhook",
    )
    assert merged["url"] == "https://new.example/hook"
    assert merged["headers"] == {"Authorization": "Bearer hdr-secret"}


# --- the endpoints ----------------------------------------------------------------------------

async def test_every_endpoint_returns_redacted_configs(client, session_maker):
    created = await client.post("/api/notifications/services", json={
        "name": "Mail", "service_type": "email", "config": EMAIL_CONFIG,
    })
    assert created.status_code == 201
    service_id = created.json()["id"]
    assert created.json()["config"]["smtp_password"] == MASK, "POST response leaked the password"

    listed = await client.get("/api/notifications/services")
    assert listed.json()[0]["config"]["smtp_password"] == MASK

    single = await client.get(f"/api/notifications/services/{service_id}")
    assert single.json()["config"]["smtp_password"] == MASK

    updated = await client.put(f"/api/notifications/services/{service_id}", json={"name": "Mail 2"})
    assert updated.json()["config"]["smtp_password"] == MASK, "PUT response leaked the password"

    assert (await _stored_config(session_maker, service_id))["smtp_password"] == "hunter2"


@pytest.mark.parametrize("service_type,config,secret_paths", [
    ("ntfy", {"server": "https://ntfy.example", "topic": "ops", "token": "tk_secret"}, [("token",)]),
    ("email", EMAIL_CONFIG, [("smtp_password",)]),
    ("webhook", WEBHOOK_CONFIG, [("url",), ("headers", "Authorization"), ("headers", "X-Api-Key")]),
    ("apprise", APPRISE_CONFIG, [("url",)]),
])
async def test_editing_with_the_redacted_config_keeps_secrets(client, session_maker, service_type, config, secret_paths):
    """The edit dialog sends back exactly what GET gave it; the stored secrets must survive."""
    created = await client.post("/api/notifications/services", json={
        "name": f"chan {service_type}", "service_type": service_type, "config": config,
    })
    service_id = created.json()["id"]

    shown = (await client.get(f"/api/notifications/services/{service_id}")).json()
    response = await client.put(f"/api/notifications/services/{service_id}", json={
        "name": "renamed", "config": shown["config"],
    })
    assert response.status_code == 200

    stored = await _stored_config(session_maker, service_id)
    for path in secret_paths:
        expected, actual = config, stored
        for part in path:
            expected, actual = expected[part], actual[part]
        assert actual == expected, f"{service_type}: {'.'.join(path)} was overwritten by the mask"
        assert MASK not in str(actual)


async def test_editing_can_replace_a_secret(client, session_maker):
    created = await client.post("/api/notifications/services", json={
        "name": "n", "service_type": "ntfy", "config": {"server": "https://ntfy.example", "topic": "ops", "token": "old"},
    })
    service_id = created.json()["id"]

    await client.put(f"/api/notifications/services/{service_id}", json={
        "config": {"server": "https://ntfy.example", "topic": "ops", "token": "new"},
    })

    assert (await _stored_config(session_maker, service_id))["token"] == "new"


async def test_group_endpoints_redact_member_configs(client, session_maker):
    created = await client.post("/api/notifications/services", json={
        "name": "Hook", "service_type": "webhook", "config": WEBHOOK_CONFIG,
    })
    service_id = created.json()["id"]
    group = await client.post("/api/notifications/groups", json={
        "name": "Ops", "slug": "ops", "channel_ids": [service_id],
    })
    assert group.status_code == 201, group.text

    for payload in (group.json(), (await client.get("/api/notifications/groups")).json()[0]):
        text = str(payload)
        assert "hdr-secret" not in text and "abcdefSECRET" not in text
