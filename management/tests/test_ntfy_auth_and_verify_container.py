"""ntfy publish token handling and the verification container's isolation."""

from __future__ import annotations

import subprocess

import pytest

from api.services import ntfy_service as ntfy_mod
from api.services import verification_service as verify_mod
from api.services.notification_service import NotificationDispatcher
from api.services.ntfy_service import NtfyService

TOKEN = "tk_abcdefghijklmnopqrstuvwxyz012"


@pytest.fixture
def svc(monkeypatch, tmp_path):
    monkeypatch.setattr(ntfy_mod, "HOST_ENV_PATH", str(tmp_path / "missing.env"))
    monkeypatch.setenv("NTFY_TOKEN", TOKEN)
    monkeypatch.setenv("DOMAIN", "n8n.example.com")
    return NtfyService(base_url="https://ntfy.example.com", public_url="https://ntfy.example.com")


@pytest.mark.parametrize(
    "url",
    [
        "http://n8n_ntfy:80",
        "http://n8n_ntfy",
        "https://ntfy.example.com",
        "https://NTFY.example.com/",
        "https://n8n.example.com/ntfy/",
    ],
)
def test_own_server_urls(svc, url):
    assert svc.is_own_server(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://ntfy.sh",
        "https://ntfy.example.com.evil.net",
        "https://evil.net/?u=https://ntfy.example.com",
        "https://n8n.example.com/ntfyx",
        "https://ntfy.example.com:8443",
        "",
        None,
    ],
)
def test_foreign_server_urls(svc, url):
    assert not svc.is_own_server(url)


def test_auth_headers_use_token(svc):
    assert svc.auth_headers() == {"Authorization": f"Bearer {TOKEN}"}
    assert svc.auth_headers("tk_explicit") == {"Authorization": "Bearer tk_explicit"}


def test_host_env_token_wins(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("NTFY_TOKEN=tk_fromhostenvfile0000000000000\n")
    monkeypatch.setattr(ntfy_mod, "HOST_ENV_PATH", str(env))
    monkeypatch.setenv("NTFY_TOKEN", TOKEN)
    assert ntfy_mod.get_ntfy_token() == "tk_fromhostenvfile0000000000000"


class _Resp:
    status_code = 200
    text = "{}"


class _Client:
    sent: list = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None, timeout=None):
        _Client.sent.append((url, headers))
        return _Resp()


@pytest.mark.parametrize(
    "server,expect_token",
    [("https://ntfy.example.com", True), ("https://ntfy.sh", False)],
)
async def test_channel_token_only_for_own_server(monkeypatch, svc, server, expect_token):
    import httpx

    monkeypatch.setattr(ntfy_mod, "ntfy_service", svc)
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    _Client.sent = []
    await NotificationDispatcher().send_ntfy({"server": server, "topic": "alerts"}, "t", "b", "normal")
    _, headers = _Client.sent[-1]
    assert ("Authorization" in headers) is expect_token


async def test_verify_container_is_isolated(monkeypatch):
    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append((cmd, kw))
        out = verify_mod.VERIFY_CONTAINER_NAME if cmd[:2] == ["docker", "ps"] and "-a" not in cmd else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    async def ready(self, timeout=90):
        return None

    async def no_sleep(*a, **kw):
        return None

    monkeypatch.setattr(verify_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(verify_mod.VerificationService, "_wait_for_postgres_ready", ready)
    monkeypatch.setattr(verify_mod.asyncio, "sleep", no_sleep)

    service = verify_mod.VerificationService(db=None)
    assert await service.spin_up_verify_container()

    run_cmd, run_kw = next((c, kw) for c, kw in calls if c[:2] == ["docker", "run"])
    assert "-p" not in run_cmd and "--publish" not in run_cmd
    assert run_cmd[run_cmd.index("--network") + 1] == "none"
    # The password is passed by name only; its value never appears in argv
    assert "POSTGRES_PASSWORD" in run_cmd
    password = run_kw["env"]["POSTGRES_PASSWORD"]
    assert len(password) >= 24 and not any(password in part for part in run_cmd)

    service2 = verify_mod.VerificationService(db=None)
    await service2.spin_up_verify_container()
    runs = [kw["env"]["POSTGRES_PASSWORD"] for c, kw in calls if c[:2] == ["docker", "run"]]
    assert runs[0] != runs[1]
