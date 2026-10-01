"""
ENABLE_HOST_TERMINAL=false must also keep the console out of containers that
amount to host root: privileged ones, ones sharing the host PID or network
namespace, and ones with the Docker socket or the host's / bind-mounted
(n8n_management, Portainer, Dozzle, the status page). Both the WebSocket
(server side) and the target list refuse them; ordinary containers stay open.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from api.config import settings
from api.routers import system, terminal
from api.routers.terminal import host_equivalent_reason


def _attrs(privileged=False, pid="", net="bridge", mounts=(), binds=None):
    return {
        "Config": {"User": "", "WorkingDir": "", "Env": []},
        "HostConfig": {"Privileged": privileged, "PidMode": pid, "NetworkMode": net, "Binds": binds},
        "Mounts": [{"Type": t, "Source": s, "Destination": d} for t, s, d in mounts],
    }


ORDINARY = _attrs(mounts=[("volume", "/var/lib/docker/volumes/n8n_data/_data", "/home/node/.n8n"),
                          ("bind", "/opt/n8n/nginx.conf", "/etc/nginx/nginx.conf")])
DOCKER_SOCK = _attrs(mounts=[("bind", "/var/run/docker.sock", "/var/run/docker.sock")])


@pytest.mark.parametrize("attrs,expected", [
    (ORDINARY, None),
    ({}, None),
    (_attrs(privileged=True), "privileged"),
    (_attrs(pid="host"), "PID"),
    (_attrs(net="host"), "network"),
    (DOCKER_SOCK, "/var/run/docker.sock"),
    (_attrs(mounts=[("bind", "/run/docker.sock", "/sock")]), "/run/docker.sock"),
    (_attrs(mounts=[("bind", "/var/run", "/hostrun")]), "/var/run"),
    (_attrs(mounts=[("bind", "/", "/host")]), "mounts / from"),
    (_attrs(mounts=[("bind", "/srv/docker.sock", "/x")]), "docker.sock"),
    (_attrs(binds=["/var/run/docker.sock:/var/run/docker.sock:ro"]), "docker.sock"),
])
def test_host_equivalent_reason(attrs, expected):
    reason = host_equivalent_reason(attrs)
    if expected is None:
        assert reason is None
    else:
        assert reason and expected in reason


# --- WebSocket session start -----------------------------------------------------------------

class FakeContainer:
    def __init__(self, name, attrs, status="running"):
        self.id = f"{name:0<64}"[:64]
        self.name = name
        self.status = status
        self.attrs = attrs
        self.image = SimpleNamespace(tags=[f"{name}:latest"])

    def exec_run(self, *_a, **_kw):
        return SimpleNamespace(exit_code=0)


class FakeDocker:
    def __init__(self, containers):
        self._containers = containers
        self.containers = SimpleNamespace(list=lambda all=False: list(self._containers))
        self.exec_created = []
        self.api = SimpleNamespace(
            exec_create=lambda cid, *a, **kw: self.exec_created.append(cid) or {"Id": "exec1"},
            exec_start=lambda *a, **kw: object(),
        )


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


@pytest.fixture
def fake_docker(monkeypatch):
    client = FakeDocker([
        FakeContainer("n8n", ORDINARY),
        FakeContainer("n8n_portainer", DOCKER_SOCK),
        FakeContainer("priv", _attrs(privileged=True)),
    ])
    monkeypatch.setattr(terminal.docker, "from_env", lambda: client)
    return client


@pytest.mark.parametrize("name", ["n8n_portainer", "priv"])
async def test_host_equivalent_container_refused_when_host_terminal_disabled(fake_docker, monkeypatch, name):
    monkeypatch.setattr(settings, "enable_host_terminal", False)
    ws = FakeWebSocket()
    session = terminal.TerminalSession(ws, name, "container")
    assert await session.start() is False
    assert session.refused
    assert fake_docker.exec_created == []
    assert ws.sent[-1]["type"] == "error"
    assert "ENABLE_HOST_TERMINAL=true" in ws.sent[-1]["message"]


async def test_ordinary_container_opens_when_host_terminal_disabled(fake_docker, monkeypatch):
    monkeypatch.setattr(settings, "enable_host_terminal", False)
    session = terminal.TerminalSession(FakeWebSocket(), "n8n", "container")
    assert await session.start() is True
    assert session.refused is None
    assert len(fake_docker.exec_created) == 1


async def test_host_equivalent_container_opens_when_host_terminal_enabled(fake_docker, monkeypatch):
    monkeypatch.setattr(settings, "enable_host_terminal", True)
    session = terminal.TerminalSession(FakeWebSocket(), "n8n_portainer", "container")
    assert await session.start() is True
    assert len(fake_docker.exec_created) == 1


# --- Target list -----------------------------------------------------------------------------

def test_targets_mark_host_equivalent_containers_disabled(fake_docker, monkeypatch):
    import docker

    monkeypatch.setattr(docker, "from_env", lambda: fake_docker)
    monkeypatch.setattr(settings, "enable_host_terminal", False)
    targets = {t["name"]: t for t in system.get_terminal_targets(_=None)["targets"]}
    assert targets["Host System"]["enabled"] is False
    assert targets["n8n"].get("enabled", True) is True
    for name in ("n8n_portainer", "priv"):
        assert targets[name]["enabled"] is False
        assert "host root" in targets[name]["description"]

    monkeypatch.setattr(settings, "enable_host_terminal", True)
    targets = {t["name"]: t for t in system.get_terminal_targets(_=None)["targets"]}
    assert all(t.get("enabled", True) for t in targets.values())
