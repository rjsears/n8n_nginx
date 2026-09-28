"""NotificationDispatcher.send routes by service type; one place knows the types."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.services.notification_service import NotificationDispatcher, UnsupportedServiceType


@pytest.fixture
def dispatcher(monkeypatch):
    d = NotificationDispatcher()
    calls = []

    def fake(kind):
        async def _send(config, title, body, last):
            calls.append((kind, config, title, body, last))
            return True
        return _send

    for kind in ("apprise", "ntfy", "email", "webhook"):
        monkeypatch.setattr(d, f"send_{kind}", fake(kind))
    d.calls = calls
    return d


@pytest.mark.parametrize("service_type", ["apprise", "ntfy", "email"])
async def test_priority_transports_receive_priority(dispatcher, service_type):
    service = SimpleNamespace(service_type=service_type, config={"k": "v"})
    assert await dispatcher.send(service, "T", "B", "high", {"source": "x"}) is True
    kind, config, title, body, last = dispatcher.calls[0]
    assert (kind, config, title, body, last) == (service_type, {"k": "v"}, "T", "B", "high")


async def test_webhook_receives_event_data_with_priority(dispatcher):
    service = SimpleNamespace(service_type="webhook", config={"url": "http://x"})
    await dispatcher.send(service, "T", "B", "critical", {"source": "n8n_webhook", "targets": ["all"]})
    kind, _, _, _, payload = dispatcher.calls[0]
    assert kind == "webhook"
    assert payload == {"source": "n8n_webhook", "targets": ["all"], "priority": "critical"}


async def test_webhook_payload_defaults_when_no_event_data(dispatcher):
    service = SimpleNamespace(service_type="webhook", config={})
    await dispatcher.send(service, "T", "B")
    assert dispatcher.calls[0][4] == {"priority": "normal"}


async def test_unknown_type_raises(dispatcher):
    with pytest.raises(UnsupportedServiceType) as excinfo:
        await dispatcher.send(SimpleNamespace(service_type="carrier_pigeon", config={}), "T", "B")
    assert "carrier_pigeon" in str(excinfo.value)
    assert dispatcher.calls == []
