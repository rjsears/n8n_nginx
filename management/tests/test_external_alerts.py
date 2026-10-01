"""
Database-free alerting (api.services.external_alerts): the outbound
heartbeat that an external monitor watches for silence, and the fallback
URL used when a notification cannot be dispatched.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

import api.services.external_alerts as ext


class FakeHttp:
    """Stands in for httpx.AsyncClient; records requests."""

    requests: List[Dict[str, Any]] = []
    status_code = 200
    raise_error: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def _request(self, method, url, **kwargs):
        if FakeHttp.raise_error:
            raise FakeHttp.raise_error
        FakeHttp.requests.append({"method": method, "url": url, **kwargs})
        return type("Response", (), {"status_code": FakeHttp.status_code})()

    async def get(self, url, **kwargs):
        return await self._request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._request("POST", url, **kwargs)


@pytest.fixture(autouse=True)
def fake_http(monkeypatch, tmp_path):
    import httpx

    FakeHttp.requests = []
    FakeHttp.status_code = 200
    FakeHttp.raise_error = None
    monkeypatch.setattr(httpx, "AsyncClient", FakeHttp)
    for key in (ext.HEARTBEAT_URL_KEY, ext.HEARTBEAT_INTERVAL_KEY, ext.FALLBACK_URL_KEY):
        monkeypatch.delenv(key, raising=False)
    # No project .env unless a test writes one
    monkeypatch.setattr(ext, "HOST_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setattr(ext, "_last_heartbeat", None)
    ext._fallback_last_sent.clear()
    return FakeHttp


@pytest.fixture
def healthy(monkeypatch):
    state = {"healthy": True}

    async def fake_health():
        return {"healthy": state["healthy"], "checks": {"database": "ok" if state["healthy"] else "error: down"}}

    monkeypatch.setattr(ext, "stack_health", fake_health)
    return state


def test_settings_come_from_env_then_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text('HEARTBEAT_URL="https://hc-ping.com/abc"\nALERT_FALLBACK_URL=\n')

    assert ext.read_setting("HEARTBEAT_URL") == "https://hc-ping.com/abc"
    assert ext.read_setting("ALERT_FALLBACK_URL") is None

    monkeypatch.setenv("HEARTBEAT_URL", "https://kuma.example/api/push/xyz")
    assert ext.read_setting("HEARTBEAT_URL") == "https://kuma.example/api/push/xyz"


async def test_no_heartbeat_url_means_no_ping(healthy, fake_http):
    assert await ext.send_heartbeat() is None
    assert fake_http.requests == []


async def test_heartbeat_pings_when_healthy(monkeypatch, healthy, fake_http):
    monkeypatch.setenv("HEARTBEAT_URL", "https://hc-ping.com/abc")

    assert await ext.send_heartbeat() is True
    assert [(r["method"], r["url"]) for r in fake_http.requests] == [("GET", "https://hc-ping.com/abc")]


async def test_heartbeat_withheld_when_unhealthy(monkeypatch, healthy, fake_http, caplog):
    monkeypatch.setenv("HEARTBEAT_URL", "https://hc-ping.com/abc")
    healthy["healthy"] = False

    with caplog.at_level("ERROR"):
        assert await ext.send_heartbeat() is False
    assert fake_http.requests == [], "an unhealthy stack must go silent so the external monitor alerts"
    assert "Heartbeat withheld" in caplog.text


async def test_heartbeat_respects_interval(monkeypatch, healthy, fake_http):
    monkeypatch.setenv("HEARTBEAT_URL", "https://hc-ping.com/abc")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_MINUTES", "5")

    assert await ext.send_heartbeat() is True
    assert await ext.send_heartbeat() is None  # a minute later: not yet
    assert len(fake_http.requests) == 1


async def test_stack_health_checks_database_and_n8n(session_maker, fake_http):
    health = await ext.stack_health()
    assert health == {"healthy": True, "checks": {"database": "ok", "n8n": "ok"}}
    assert fake_http.requests[0]["url"].endswith("/healthz")

    fake_http.status_code = 503
    health = await ext.stack_health()
    assert health["healthy"] is False and health["checks"]["n8n"] == "HTTP 503"


async def test_fallback_alert_posts_text_and_dedups(monkeypatch, fake_http):
    monkeypatch.setenv("ALERT_FALLBACK_URL", "https://ntfy.sh/my-alerts")

    error = ConnectionRefusedError("connection refused")
    assert await ext.notify_dispatch_failure("container_stopped", {"container": "n8n_postgres"}, error) is True
    assert await ext.notify_dispatch_failure("container_stopped", {"container": "n8n_postgres"}, error) is False

    assert len(fake_http.requests) == 1
    request = fake_http.requests[0]
    assert request["method"] == "POST" and request["url"] == "https://ntfy.sh/my-alerts"
    body = request["content"].decode()
    assert "n8n_postgres" in body and "connection refused" in body
    assert request["headers"]["Priority"] == "5"


async def test_fallback_without_url_or_with_unreachable_endpoint_never_raises(monkeypatch, fake_http):
    assert await ext.send_fallback_alert("t", "m") is False

    monkeypatch.setenv("ALERT_FALLBACK_URL", "https://ntfy.sh/my-alerts")
    fake_http.raise_error = OSError("network unreachable")
    assert await ext.send_fallback_alert("t", "m") is False
