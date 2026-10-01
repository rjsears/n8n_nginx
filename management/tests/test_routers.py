"""
Router behaviour that the dispatch tests cannot see: secret redaction and the
system-notification test endpoint.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient


@pytest.fixture
async def client(session_maker):
    from fastapi import FastAPI

    from api.database import get_db
    from api.dependencies import get_current_user
    from api.routers import notifications, system_notifications

    app = FastAPI()
    app.include_router(notifications.router, prefix="/api/notifications")
    app.include_router(system_notifications.router, prefix="/api/system-notifications")

    async def _db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")

    async with AsyncClient(app=app, base_url="http://test") as http:
        yield http


async def test_get_single_service_redacts_secrets(client, channel):
    response = await client.get(f"/api/notifications/services/{channel.id}")

    assert response.status_code == 200
    config = response.json()["config"]
    assert config["token"] == "***", "GET /services/{id} leaked a token the list endpoint hides"
    assert config["topic"] == "ops"


async def test_list_services_redacts_secrets(client, channel):
    response = await client.get("/api/notifications/services")

    assert response.status_code == 200
    assert response.json()[0]["config"]["token"] == "***"


async def test_test_endpoint_actually_sends(client, channel, make_event, add_target, sent, history_rows):
    event = await make_event("backup_failure", category="backup", severity="critical")
    await add_target(event, channel)

    response = await client.post("/api/system-notifications/test", json={"event_type": "backup_failure"})

    assert response.status_code == 200, response.text
    assert len(sent.calls) == 1, "the test endpoint recorded 'sent' without calling any transport"
    assert sent.calls[0]["id"] == channel.id
    rows = await history_rows("backup_failure")
    assert [r.status for r in rows] == ["sent"]


async def test_test_endpoint_reports_transport_failure(client, channel, make_event, add_target, sent, history_rows):
    event = await make_event("backup_failure", category="backup", severity="critical")
    await add_target(event, channel)
    sent.fail = True

    response = await client.post("/api/system-notifications/test", json={"event_type": "backup_failure"})

    assert response.status_code == 502, "a broken channel must fail the test, not pass it"
    rows = await history_rows("backup_failure")
    assert [r.status for r in rows] == ["failed"]


async def test_test_endpoint_requires_targets(client, make_event):
    await make_event("backup_failure", category="backup")

    response = await client.post("/api/system-notifications/test", json={"event_type": "backup_failure"})

    assert response.status_code == 400
