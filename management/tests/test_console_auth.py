"""
Browser-facing authentication of the management console:

* the terminal WebSocket (cookie auth, Origin check, host-terminal flag,
  revocation on logout / session end, audit records),
* CSRF protection for cookie-authenticated state-changing requests,
* no wildcard CORS,
* login/logout/session endpoints never hand the session token to scripts.

The WebSocket tests run against a minimal app with the terminal router and a
fake terminal backend (no Docker). The HTTP tests run the real application
against an in-memory SQLite database holding the auth tables.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from api.config import settings
from api.routers import terminal
from api.security import is_origin_allowed


@compiles(INET, "sqlite")
def _compile_inet_for_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(45)"


SAME_ORIGIN = "https://testserver"


# --- Origin helper -------------------------------------------------------------------------

@pytest.mark.parametrize("origin,host,expected", [
    ("https://n8n.example.com", "n8n.example.com", True),
    ("https://n8n.example.com:8443", "n8n.example.com", True),   # nginx $host drops the port
    ("https://N8N.example.com/", "n8n.example.com", True),
    ("https://evil.example", "n8n.example.com", False),
    ("https://n8n.example.com.evil.example", "n8n.example.com", False),
    ("https://sub.n8n.example.com", "n8n.example.com", False),    # sibling/sub domains are other origins
    ("null", "n8n.example.com", False),
    (None, "n8n.example.com", False),
    ("", "n8n.example.com", False),
    ("file:///etc/passwd", "n8n.example.com", False),
    ("https://n8n.example.com", None, False),
    ("http://n8n.example.com", "n8n.example.com", False),         # plain-http page on the same host
    ("http://n8n.example.com:80", "n8n.example.com", False),
    ("ws://n8n.example.com", "n8n.example.com", False),
])
def test_is_origin_allowed(origin, host, expected):
    assert is_origin_allowed(origin, host) is expected


def test_allowed_origins_setting_extends_the_list(monkeypatch):
    monkeypatch.setattr(settings, "allowed_origins", "https://manage.example.com, https://other.example.com/")
    assert is_origin_allowed("https://manage.example.com", "n8n.example.com")
    assert is_origin_allowed("https://other.example.com", "n8n.example.com")
    assert not is_origin_allowed("https://evil.example", "n8n.example.com")


def test_allowed_origins_can_list_an_http_origin_explicitly(monkeypatch):
    monkeypatch.setattr(settings, "allowed_origins", "http://n8n.example.com")
    assert is_origin_allowed("http://n8n.example.com", "n8n.example.com")
    assert not is_origin_allowed("http://other.example.com", "other.example.com")


# --- Terminal WebSocket ----------------------------------------------------------------------

class FakeTerminal:
    """Stands in for TerminalSession: no Docker, echoes input back as output."""

    instances: list["FakeTerminal"] = []

    def __init__(self, websocket, target_id, target_type):
        self.websocket = websocket
        self.target_id = target_id
        self.target_type = target_type
        self.container = SimpleNamespace(name=f"fake-{target_id}")
        self.inputs: list[str] = []
        self.stopped = False
        self._done = asyncio.Event()
        FakeTerminal.instances.append(self)

    async def start(self):
        return True

    async def read_output(self):
        await self._done.wait()

    async def write_input(self, data):
        self.inputs.append(data)
        await self.websocket.send_text(json.dumps({"type": "output", "data": data}))

    async def resize(self, rows, cols):
        pass

    async def stop(self):
        self.stopped = True
        self._done.set()


VALID_TOKEN = "valid-session-token"


@pytest.fixture
def ws_env(monkeypatch):
    """Terminal router with fake auth/DB/Docker; returns the recorded audit calls."""
    FakeTerminal.instances = []
    audit: list[dict] = []
    state = {"valid": True, "expires_at": datetime.now(UTC) + timedelta(hours=1)}

    async def fake_authenticate(token, client_ip):
        if token != VALID_TOKEN or not state["valid"]:
            return None
        session = SimpleNamespace(token=token, user_id=7, expires_at=state["expires_at"])
        user = SimpleNamespace(id=7, username="admin")
        return session, user

    async def fake_still_valid(token):
        return state["valid"]

    async def fake_audit(action, user_id, username, client_ip, user_agent, details):
        audit.append({"action": action, "user_id": user_id, "username": username, "ip": client_ip, **details})

    monkeypatch.setattr(terminal, "_authenticate", fake_authenticate)
    monkeypatch.setattr(terminal, "_session_still_valid", fake_still_valid)
    monkeypatch.setattr(terminal, "_audit", fake_audit)
    monkeypatch.setattr(terminal, "TerminalSession", FakeTerminal)
    monkeypatch.setattr(settings, "enable_host_terminal", False)
    monkeypatch.setattr(settings, "allowed_origins", "")

    app = FastAPI()
    app.include_router(terminal.router, prefix="/api")
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, audit=audit, state=state)
    terminal._open_terminals.clear()


def _connect(client, target="n8n", origin=SAME_ORIGIN, cookie=VALID_TOKEN, query=""):
    headers = {"x-real-ip": "10.1.2.3"}
    if origin is not None:
        headers["origin"] = origin
    if cookie is not None:
        headers["cookie"] = f"session={cookie}"
    return client.websocket_connect(f"/api/ws/terminal?target={target}{query}", headers=headers)


def _open(ws):
    assert ws.receive_json()["type"] == "connecting"
    assert ws.receive_json()["type"] == "connected"


def test_terminal_opens_with_session_cookie_and_audits(ws_env):
    with _connect(ws_env.client) as ws:
        _open(ws)
        ws.send_json({"type": "input", "data": "ls\n"})
        assert ws.receive_json() == {"type": "output", "data": "ls\n"}
    # The handler finishes after the client goes away
    for _ in range(50):
        if any(a["action"] == "terminal_close" for a in ws_env.audit):
            break
        ws_env.client.portal.call(asyncio.sleep, 0.02)

    actions = [a["action"] for a in ws_env.audit]
    assert actions == ["terminal_open", "terminal_close"]
    opened = ws_env.audit[0]
    assert opened["username"] == "admin" and opened["ip"] == "10.1.2.3"
    assert opened["target"] == "n8n" and opened["container"] == "fake-n8n"
    assert ws_env.audit[1]["reason"] == "client disconnected"
    assert FakeTerminal.instances[0].stopped
    assert not terminal._open_terminals


@pytest.mark.parametrize("origin", [None, "https://evil.example", "null"])
def test_terminal_rejects_foreign_or_missing_origin(ws_env, origin):
    with pytest.raises(WebSocketDisconnect) as exc:
        with _connect(ws_env.client, origin=origin):
            pass
    assert exc.value.code == terminal.CLOSE_FORBIDDEN
    assert FakeTerminal.instances == []


def test_terminal_rejects_missing_cookie(ws_env):
    with pytest.raises(WebSocketDisconnect) as exc:
        with _connect(ws_env.client, cookie=None):
            pass
    assert exc.value.code == terminal.CLOSE_UNAUTHORIZED


def test_terminal_ignores_token_in_query_string(ws_env):
    """The old ?token= URL parameter (logged by nginx) no longer authenticates."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with _connect(ws_env.client, cookie=None, query=f"&token={VALID_TOKEN}"):
            pass
    assert exc.value.code == terminal.CLOSE_UNAUTHORIZED


def test_host_terminal_disabled_by_default(ws_env):
    with _connect(ws_env.client, target="host") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "ENABLE_HOST_TERMINAL=true" in msg["message"]
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == terminal.CLOSE_FORBIDDEN
    assert FakeTerminal.instances == []
    assert [a["action"] for a in ws_env.audit] == ["terminal_denied"]


def test_host_equivalent_container_refusal_closes_forbidden_and_audits(ws_env, monkeypatch):
    class RefusingTerminal(FakeTerminal):
        async def start(self):
            self.refused = "it mounts /var/run/docker.sock from the host"
            await self.websocket.send_text(json.dumps({"type": "error", "message": "refused"}))
            return False

    monkeypatch.setattr(terminal, "TerminalSession", RefusingTerminal)
    with _connect(ws_env.client, target="n8n_portainer") as ws:
        assert ws.receive_json()["type"] == "connecting"
        assert ws.receive_json() == {"type": "error", "message": "refused"}
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == terminal.CLOSE_FORBIDDEN
    assert [a["action"] for a in ws_env.audit] == ["terminal_denied"]
    assert "docker.sock" in ws_env.audit[0]["reason"]


def test_host_terminal_opens_when_enabled(ws_env, monkeypatch):
    monkeypatch.setattr(settings, "enable_host_terminal", True)
    with _connect(ws_env.client, target="host") as ws:
        _open(ws)
    assert FakeTerminal.instances[0].target_type == "host"


def test_logout_closes_open_terminal(ws_env):
    with _connect(ws_env.client) as ws:
        _open(ws)
        closed = ws_env.client.portal.call(terminal.close_terminals, VALID_TOKEN, None, "logged out")
        assert closed == 1
        assert ws.receive_json() == {"type": "error", "message": "Terminal closed: logged out"}
        assert ws.receive_json() == {"type": "disconnected", "reason": "logged out"}
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == terminal.CLOSE_UNAUTHORIZED
    assert ws_env.audit[-1]["action"] == "terminal_close"
    assert ws_env.audit[-1]["reason"] == "logged out"


def test_close_terminals_by_user_leaves_other_users_alone(ws_env):
    with _connect(ws_env.client) as ws:
        _open(ws)
        assert ws_env.client.portal.call(terminal.close_terminals, None, 999, "x") == 0
        assert ws_env.client.portal.call(terminal.close_terminals, None, 7, "password changed") == 1
        assert ws.receive_json()["message"] == "Terminal closed: password changed"


def test_watchdog_closes_terminal_when_session_revoked(ws_env, monkeypatch):
    monkeypatch.setattr(settings, "terminal_revalidate_seconds", 1)
    with _connect(ws_env.client) as ws:
        _open(ws)
        ws_env.state["valid"] = False  # e.g. revoked by another API worker or directly in the DB
        assert ws.receive_json() == {"type": "error", "message": "Terminal closed: session expired or revoked"}


def test_watchdog_closes_terminal_at_session_expiry(ws_env, monkeypatch):
    monkeypatch.setattr(settings, "terminal_revalidate_seconds", 60)
    ws_env.state["expires_at"] = datetime.now(UTC) + timedelta(seconds=1)
    with _connect(ws_env.client) as ws:
        _open(ws)
        assert ws.receive_json() == {"type": "error", "message": "Terminal closed: session expired"}


# --- Database-backed auth (real models on SQLite) -------------------------------------------

AUTH_TABLES = ("admin_user", "sessions", "audit_log", "allowed_subnets")


@pytest.fixture
async def auth_db(monkeypatch):
    import api.database
    import api.models  # noqa: F401
    from api.database import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    tables = [Base.metadata.tables[name] for name in AUTH_TABLES]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api.database, "async_session_maker", maker)
    try:
        yield maker
    finally:
        await engine.dispose()


@pytest.fixture
async def admin(auth_db, monkeypatch):
    from api.services.auth_service import AuthService

    monkeypatch.setattr(settings, "bcrypt_rounds", 4)
    async with auth_db() as db:
        return await AuthService(db).create_user(username="admin", password="correct-horse", email=None)


@pytest.fixture
async def http(admin):
    from api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


async def _login(http):
    return await http.post(
        "/api/auth/login",
        json={"username": "admin", "password": "correct-horse"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


async def test_login_sets_httponly_strict_cookie_and_returns_no_token(http):
    resp = await _login(http)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "token" not in body
    assert body["user"]["username"] == "admin"

    cookie = resp.headers["set-cookie"].lower()
    assert "session=" in cookie
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie

    me = await http.get("/api/auth/me")
    assert me.status_code == 200

    sessions = await http.get("/api/auth/sessions")
    assert sessions.status_code == 200
    assert all("token" not in s for s in sessions.json())
    session = await http.get("/api/auth/session")
    assert "token" not in session.json()


async def test_cookie_post_without_csrf_header_is_rejected(http):
    await _login(http)
    resp = await http.post("/api/auth/logout")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF check failed"
    # Still logged in
    assert (await http.get("/api/auth/me")).status_code == 200


async def test_cookie_post_from_foreign_origin_is_rejected(http):
    await _login(http)
    resp = await http.post(
        "/api/auth/logout",
        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example"},
    )
    assert resp.status_code == 403
    assert (await http.get("/api/auth/me")).status_code == 200


async def test_logout_with_csrf_header_ends_session_and_terminals(http, monkeypatch):
    closed = []

    async def fake_close_terminals(token=None, user_id=None, reason=""):
        closed.append((token is not None, user_id, reason))
        return 0

    import api.routers.auth as auth_router

    monkeypatch.setattr(auth_router, "close_terminals", fake_close_terminals)
    await _login(http)
    resp = await http.post(
        "/api/auth/logout",
        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://testserver"},
    )
    assert resp.status_code == 200
    assert closed == [(True, None, "logged out")]
    # Cookie cleared and the session itself is dead even if replayed
    assert (await http.get("/api/auth/me")).status_code == 401


@pytest.mark.parametrize("prefix", [
    'prefs={"theme":"dark"}',   # JSON value: SimpleCookie stops parsing here
    "a=b c",                    # space inside an unquoted value
    'x="unbalanced',            # unbalanced quote
    "k[1]=v",                   # illegal key character
])
async def test_malformed_cookie_header_does_not_skip_csrf(http, prefix):
    """Auth still finds the session cookie behind a malformed one, so CSRF must not skip it."""
    await _login(http)
    token = http.cookies.get("session")
    assert token
    http.cookies.clear()
    cookie = f"{prefix}; session={token}"
    # The session really authenticates with this header ...
    assert (await http.get("/api/auth/me", headers={"Cookie": cookie})).status_code == 200
    # ... so a state-changing request with it must pass the CSRF check.
    resp = await http.post("/api/auth/logout", headers={"Cookie": cookie})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF check failed"
    resp = await http.post(
        "/api/auth/logout",
        headers={"Cookie": cookie, "X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example"},
    )
    assert resp.status_code == 403
    assert (await http.get("/api/auth/me", headers={"Cookie": cookie})).status_code == 200


async def test_any_cookie_header_requires_csrf_header(http):
    resp = await http.post("/api/auth/login", json={"username": "admin"}, headers={"Cookie": "unrelated=1"})
    assert resp.status_code == 403


async def test_http_origin_on_console_host_is_rejected(http):
    await _login(http)
    resp = await http.post(
        "/api/auth/logout",
        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "http://testserver"},
    )
    assert resp.status_code == 403
    assert (await http.get("/api/auth/me")).status_code == 200


async def test_authorization_header_requests_skip_csrf(http):
    await _login(http)
    token = http.cookies.get("session")
    http.cookies.clear()
    resp = await http.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_get_with_cookie_is_not_csrf_checked(http):
    """nginx auth_request (GET /api/auth/verify) carries the cookie and no CSRF header."""
    await _login(http)
    assert (await http.get("/api/auth/me")).status_code == 200


async def test_requests_without_session_cookie_skip_csrf(http):
    """Bearer/API-key callers (e.g. n8n hitting the notification webhook) carry no cookie."""
    resp = await http.post("/api/auth/login", json={"username": "admin"})
    assert resp.status_code == 422  # reached the route: validation error, not 403


async def test_no_wildcard_cors(http):
    preflight = await http.options(
        "/api/auth/logout",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in preflight.headers
    resp = await http.get("/api/auth/me", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
    assert "access-control-allow-credentials" not in resp.headers


async def test_authenticate_checks_session_state(admin, auth_db):
    from api.services.auth_service import AuthService

    async with auth_db() as db:
        user, session, error = await AuthService(db).authenticate("admin", "correct-horse", "10.0.0.5", "pytest")
    assert error is None

    result = await terminal._authenticate(session.token, "10.0.0.5")
    assert result is not None and result[1].username == "admin"
    assert await terminal._authenticate("not-a-token", "10.0.0.5") is None
    assert await terminal._authenticate(None, "10.0.0.5") is None
    assert await terminal._session_still_valid(session.token) is True

    async with auth_db() as db:
        await AuthService(db).add_allowed_subnet("192.168.0.0/16")
    assert await terminal._authenticate(session.token, "10.0.0.5") is None
    assert await terminal._authenticate(session.token, "192.168.1.9") is not None

    async with auth_db() as db:
        await AuthService(db).logout(session.token)
    assert await terminal._session_still_valid(session.token) is False
    assert await terminal._authenticate(session.token, "192.168.1.9") is None


async def test_terminal_audit_rows_are_written(admin, auth_db):
    from sqlalchemy import select

    from api.models.audit import AuditLog

    await terminal._audit("terminal_open", admin.id, "admin", "10.0.0.5", "pytest", {"target": "host"})
    async with auth_db() as db:
        rows = (await db.execute(select(AuditLog))).scalars().all()
    assert [(r.action, r.username, r.resource_type, r.resource_id) for r in rows] == [
        ("terminal_open", "admin", "terminal", "host")
    ]
