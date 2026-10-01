"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/terminal.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from sqlalchemy import select
import docker
import json

from api.config import settings
from api.dependencies import get_client_ip
from api.security import SESSION_COOKIE_NAME, is_origin_allowed

logger = logging.getLogger(__name__)
router = APIRouter()


class TerminalSession:
    """Manages a terminal session with a container or host."""

    def __init__(self, websocket: WebSocket, target_id: str, target_type: str):
        self.websocket = websocket
        self.target_id = target_id
        self.target_type = target_type
        self.client = docker.from_env()
        self.container = None
        self.exec_id = None
        self.socket = None
        self._running = False
        self.refused: Optional[str] = None

    async def start(self):
        """Start the terminal session."""
        try:
            if self.target_type == "host":
                # For host access, create a privileged alpine container
                # that shares the host's namespaces
                self.container = await asyncio.to_thread(
                    self.client.containers.run,
                    settings.helper_image,
                    command="/bin/sh",
                    stdin_open=True,
                    tty=True,
                    detach=True,
                    remove=True,
                    pid_mode="host",
                    network_mode="host",
                    privileged=True,
                    security_opt=["apparmor=unconfined"],
                    volumes={"/": {"bind": "/host", "mode": "rw"}},
                )
                # Wait for container to be ready
                await asyncio.sleep(0.5)
            else:
                # Find the container by ID or name
                containers = await asyncio.to_thread(self.client.containers.list, all=True)
                for c in containers:
                    if c.id.startswith(self.target_id) or c.name == self.target_id:
                        self.container = c
                        break

                if not self.container:
                    await self.websocket.send_text(
                        json.dumps({"type": "error", "message": f"Container not found: {self.target_id}"})
                    )
                    return False

                if self.container.status != "running":
                    await self.websocket.send_text(
                        json.dumps({"type": "error", "message": f"Container is not running: {self.container.status}"})
                    )
                    return False

                if not settings.enable_host_terminal:
                    reason = host_equivalent_reason(self.container.attrs)
                    if reason:
                        self.refused = reason
                        await self.websocket.send_text(json.dumps({
                            "type": "error",
                            "message": host_equivalent_refusal(self.container.name, reason),
                        }))
                        return False

            # Determine shell to use
            shell = await asyncio.to_thread(self._detect_shell)

            # Get container's default user and working directory
            container_config = self.container.attrs.get("Config", {})
            default_user = container_config.get("User", "")
            working_dir = container_config.get("WorkingDir", "")

            # Build environment with proper PATH
            env_vars = container_config.get("Env", [])
            # Ensure common bin paths are in PATH
            has_path = any(e.startswith("PATH=") for e in env_vars)
            if not has_path:
                env_vars.append("PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")

            # Create exec instance with full environment
            exec_instance = await asyncio.to_thread(
                self.client.api.exec_create,
                self.container.id,
                shell,
                stdin=True,
                tty=True,
                stdout=True,
                stderr=True,
                user=default_user if default_user else None,
                workdir=working_dir if working_dir else None,
                environment=env_vars,
            )
            self.exec_id = exec_instance["Id"]

            # Start exec with socket
            self.socket = await asyncio.to_thread(
                self.client.api.exec_start,
                self.exec_id,
                socket=True,
                tty=True,
            )

            self._running = True
            return True

        except docker.errors.ImageNotFound:
            await self.websocket.send_text(
                json.dumps({"type": "error", "message": "Alpine image not found. Pull " + settings.helper_image + " first."})
            )
            return False
        except docker.errors.APIError as e:
            await self.websocket.send_text(
                json.dumps({"type": "error", "message": f"Docker API error: {str(e)}"})
            )
            return False
        except Exception as e:
            logger.exception("Failed to start terminal session")
            await self.websocket.send_text(
                json.dumps({"type": "error", "message": f"Failed to start terminal: {str(e)}"})
            )
            return False

    def _detect_shell(self):
        """Detect available shell in container and return command for login shell."""
        # Try common shells
        if self.target_type == "host":
            # For host access, chroot into the mounted host filesystem
            # and use su to get a proper root login shell with correct environment
            return ["chroot", "/host", "/bin/su", "-"]

        # For containers, try to detect the shell
        try:
            # Try bash first
            result = self.container.exec_run("which bash", demux=True)
            if result.exit_code == 0:
                # Use login (-l) and interactive (-i) flags to source bashrc/profile
                return ["/bin/bash", "-li"]
        except Exception:
            pass

        try:
            # Try zsh
            result = self.container.exec_run("which zsh", demux=True)
            if result.exit_code == 0:
                return ["/bin/zsh", "-l"]
        except Exception:
            pass

        try:
            # Try sh
            result = self.container.exec_run("which sh", demux=True)
            if result.exit_code == 0:
                return ["/bin/sh", "-l"]
        except Exception:
            pass

        # Default to sh
        return ["/bin/sh"]

    async def read_output(self):
        """Read output from the terminal and send to websocket."""
        try:
            loop = asyncio.get_running_loop()
            sock = self.socket._sock
            sock.setblocking(False)

            while self._running:
                try:
                    # Use asyncio's efficient socket reading
                    data = await loop.sock_recv(sock, 4096)
                    if data:
                        # Send as text (terminal output)
                        await self.websocket.send_text(
                            json.dumps({"type": "output", "data": data.decode("utf-8", errors="replace")})
                        )
                    else:
                        # Connection closed (empty bytes means EOF)
                        logger.info("Terminal socket closed by remote end")
                        break
                except OSError as e:
                    if self._running:
                        logger.debug(f"Socket error: {e}")
                    break
                except Exception as e:
                    if self._running:
                        logger.exception("Unexpected error in read loop")
                    break

        except Exception as e:
            logger.exception("Error reading terminal output")
        finally:
            self._running = False

    async def write_input(self, data: str):
        """Write input to the terminal."""
        try:
            if self.socket and self._running:
                self.socket._sock.sendall(data.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error writing to terminal: {e}")

    async def resize(self, rows: int, cols: int):
        """Resize the terminal."""
        try:
            if self.exec_id:
                await asyncio.to_thread(self.client.api.exec_resize, self.exec_id, height=rows, width=cols)
        except Exception as e:
            logger.debug(f"Resize error (may be expected): {e}")

    async def stop(self):
        """Stop the terminal session."""
        self._running = False

        try:
            if self.socket:
                self.socket.close()
        except Exception:
            pass

        # If we created a host container, stop it
        if self.target_type == "host" and self.container:
            try:
                await asyncio.to_thread(self.container.stop, timeout=1)
            except Exception:
                pass
            try:
                self.container.remove(force=True)
            except Exception:
                pass




# --- Authentication, revocation and audit ------------------------------------------
#
# The terminal is root on the Docker host (target=host) or inside any
# container, so the WebSocket is authenticated like the rest of the console
# and then kept on a short leash:
#
# * The login session comes from the HttpOnly "session" cookie the browser
#   sends with the same-origin upgrade request - never from the URL, which
#   nginx would write to its access log.
# * The upgrade must carry an Origin naming this console (Cross-Site
#   WebSocket Hijacking: cookies ride along with cross-site WebSockets).
# * Every open terminal is registered in-process; logout, "log out all
#   sessions" and a password change close the user's terminals at once, and a
#   watchdog re-checks the session every TERMINAL_REVALIDATE_SECONDS and at
#   its expiry time.
# * Each open, close and refused host shell is written to the audit log.

HOST_TERMINAL_DISABLED_MESSAGE = (
    "The host terminal is disabled. It gives a root shell on the Docker host, so it is "
    "off unless the operator opts in: set ENABLE_HOST_TERMINAL=true in the n8n_management "
    "environment (docker-compose.yaml / .env) and recreate the container. Terminals in "
    "ordinary containers are not affected; containers that would give host root access "
    "(privileged, or with the Docker socket mounted) are disabled too."
)

CLOSE_UNAUTHORIZED = 4001
CLOSE_FORBIDDEN = 4003

# A shell in some containers is a host root shell by another name: a
# privileged container, one sharing the host's PID or network namespace, or
# one with the Docker socket (n8n_management, Portainer, Dozzle, the status
# page) or the host's root filesystem mounted can take over the host. With
# ENABLE_HOST_TERMINAL=false those containers are refused too, otherwise the
# flag would not hold.
_HOST_EQUIVALENT_MOUNT_SOURCES = frozenset({
    "/", "/var/run", "/run", "/var/run/docker.sock", "/run/docker.sock",
})


def host_equivalent_reason(attrs: dict) -> Optional[str]:
    """Why a shell in the container described by `attrs` (docker inspect output) is host access, or None."""
    host_config = (attrs or {}).get("HostConfig") or {}
    if host_config.get("Privileged"):
        return "it runs privileged"
    if (host_config.get("PidMode") or "") == "host":
        return "it shares the host PID namespace"
    if (host_config.get("NetworkMode") or "") == "host":
        return "it shares the host network namespace"
    sources = [m.get("Source") or "" for m in (attrs or {}).get("Mounts") or [] if m.get("Type", "bind") == "bind"]
    sources += [b.split(":", 1)[0] for b in host_config.get("Binds") or []]
    for source in sources:
        normalized = "/" + source.strip("/") if source else ""
        if normalized in _HOST_EQUIVALENT_MOUNT_SOURCES or normalized.endswith("/docker.sock"):
            return f"it mounts {normalized} from the host"
    return None


def host_equivalent_refusal(name: str, reason: str) -> str:
    """Message shown when a host-equivalent container is refused with the host terminal disabled."""
    return (
        f"A shell in {name} is equivalent to host root access ({reason}), so it is only "
        "available when the host terminal is enabled (ENABLE_HOST_TERMINAL=true)."
    )


@dataclass(eq=False)
class _OpenTerminal:
    """Registry entry for one open terminal WebSocket."""

    token: str
    user_id: int
    expires_at: datetime
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    reason: Optional[str] = None

    def close(self, reason: str) -> None:
        if not self.closed.is_set():
            self.reason = reason
            self.closed.set()


_open_terminals: Set[_OpenTerminal] = set()


async def close_terminals(
    token: Optional[str] = None,
    user_id: Optional[int] = None,
    reason: str = "session ended",
) -> int:
    """
    Close the open terminals of a login session (token) or of every session
    of a user (user_id). Called by logout, logout-all and password change.
    Returns how many terminals were told to close.
    """
    count = 0
    for entry in list(_open_terminals):
        if (token is not None and entry.token == token) or (user_id is not None and entry.user_id == user_id):
            entry.close(reason)
            count += 1
    if count:
        logger.info(f"Closing {count} terminal session(s): {reason}")
    return count


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def _authenticate(token: Optional[str], client_ip: str):
    """
    Resolve the cookie token to (session, user) if the session is active,
    unexpired and the client address passes the allowed-subnet list.
    Returns None otherwise.
    """
    from api import database
    from api.models.auth import AdminUser, Session
    from api.services.auth_service import AuthService

    if not token:
        return None
    try:
        async with database.async_session_maker() as db:
            result = await db.execute(
                select(Session, AdminUser)
                .join(AdminUser, AdminUser.id == Session.user_id)
                .where(Session.token == token)
                .where(Session.is_active == True)
                .where(Session.expires_at > datetime.now(UTC))
            )
            row = result.first()
            if row is None:
                return None
            if not await AuthService(db).is_ip_allowed(client_ip):
                logger.warning(f"Terminal refused for {client_ip}: not in allowed subnets")
                return None
            return row[0], row[1]
    except Exception as e:
        logger.error(f"Terminal session lookup failed: {e}")
        return None


async def _session_still_valid(token: str) -> Optional[bool]:
    """True/False from the database, None if the database could not be asked."""
    from api import database
    from api.models.auth import Session

    try:
        async with database.async_session_maker() as db:
            result = await db.execute(
                select(Session.token)
                .where(Session.token == token)
                .where(Session.is_active == True)
                .where(Session.expires_at > datetime.now(UTC))
            )
            return result.first() is not None
    except Exception as e:
        logger.warning(f"Terminal session re-check failed (will retry): {e}")
        return None


async def _audit(
    action: str,
    user_id: Optional[int],
    username: Optional[str],
    client_ip: Optional[str],
    user_agent: Optional[str],
    details: dict,
) -> None:
    """Write a terminal audit record. Never raises: auditing must not break the terminal."""
    from api import database
    from api.models.audit import AuditLog

    logger.info(f"AUDIT {action} user={username} ip={client_ip} {details}")
    try:
        async with database.async_session_maker() as db:
            db.add(
                AuditLog(
                    user_id=user_id,
                    username=username,
                    action=action,
                    resource_type="terminal",
                    resource_id=str(details.get("target", ""))[:100] or None,
                    details=details,
                    ip_address=client_ip if client_ip and client_ip != "unknown" else None,
                    user_agent=user_agent[:500] if user_agent else None,
                )
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to write terminal audit log ({action}): {e}")


async def _watch_session(entry: _OpenTerminal) -> None:
    """Close the terminal when its login session expires or is revoked."""
    interval = max(1, int(settings.terminal_revalidate_seconds))
    while not entry.closed.is_set():
        remaining = (_aware(entry.expires_at) - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            entry.close("session expired")
            return
        try:
            await asyncio.wait_for(entry.closed.wait(), timeout=min(interval, remaining))
            return
        except asyncio.TimeoutError:
            pass
        if await _session_still_valid(entry.token) is False:
            entry.close("session expired or revoked")
            return


async def _pump_input(websocket: WebSocket, session: "TerminalSession", entry: _OpenTerminal) -> None:
    """Forward client messages to the terminal until the client goes away."""
    while not entry.closed.is_set():
        message = await websocket.receive_text()
        if entry.closed.is_set():
            return

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            # Treat as raw input
            await session.write_input(message)
            continue
        if not isinstance(data, dict):
            continue

        msg_type = data.get("type")
        if msg_type == "input":
            await session.write_input(data.get("data", ""))
        elif msg_type == "resize":
            await session.resize(data.get("rows", 24), data.get("cols", 80))
        elif msg_type == "ping":
            await websocket.send_text(json.dumps({"type": "pong"}))


@router.websocket("/ws/terminal")
async def terminal_websocket(
    websocket: WebSocket,
    target: str = Query(..., description="Target container ID or 'host'"),
):
    """
    WebSocket endpoint for terminal access.

    Connect with: wss://host/management/api/ws/terminal?target=container_id
    from the console page. Authentication is the HttpOnly session cookie set
    at login; the Origin header must be this console. Host shells
    (target=host) and shells in host-equivalent containers (privileged, host
    PID/network namespace, Docker socket or / mounted) additionally require
    ENABLE_HOST_TERMINAL=true.

    Messages from client:
    - {"type": "input", "data": "command"} - Send input to terminal
    - {"type": "resize", "rows": 24, "cols": 80} - Resize terminal
    - {"type": "ping"} - Keep-alive

    Messages from server:
    - {"type": "output", "data": "text"} - Terminal output
    - {"type": "error", "message": "error text"} - Error message
    - {"type": "connected"} - Connection established
    - {"type": "disconnected", "reason": "..."} - Connection closed

    Close codes: 4001 not authenticated / session ended, 4003 forbidden
    (bad Origin, host terminal disabled).
    """
    client_ip = await get_client_ip(websocket)
    user_agent = websocket.headers.get("user-agent")
    origin = websocket.headers.get("origin")
    target_type = "host" if target == "host" else "container"

    # Cross-site WebSocket hijacking: refuse before the handshake completes
    if not is_origin_allowed(origin, websocket.headers.get("host")):
        logger.warning(f"Terminal WebSocket refused from {client_ip}: origin {origin!r} not allowed")
        await websocket.close(code=CLOSE_FORBIDDEN, reason="Origin not allowed")
        return

    auth = await _authenticate(websocket.cookies.get(SESSION_COOKIE_NAME), client_ip)
    if auth is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="Unauthorized")
        return
    login_session, user = auth

    await websocket.accept()

    audit_details = {"target": target, "target_type": target_type}

    if target_type == "host" and not settings.enable_host_terminal:
        await _audit("terminal_denied", user.id, user.username, client_ip, user_agent,
                     {**audit_details, "reason": "host terminal disabled"})
        await websocket.send_text(json.dumps({"type": "error", "message": HOST_TERMINAL_DISABLED_MESSAGE}))
        await websocket.close(code=CLOSE_FORBIDDEN, reason="Host terminal disabled")
        return

    # Send connection acknowledgment
    await websocket.send_text(
        json.dumps({"type": "connecting", "target": target, "target_type": target_type})
    )

    # Create terminal session
    session = await asyncio.to_thread(TerminalSession, websocket, target, target_type)

    if not await session.start():
        refused = getattr(session, "refused", None)
        if refused:
            await _audit("terminal_denied", user.id, user.username, client_ip, user_agent,
                         {**audit_details, "reason": f"host terminal disabled and {refused}"})
            await websocket.close(code=CLOSE_FORBIDDEN, reason="Host terminal disabled")
        else:
            await websocket.close()
        return

    if session.container is not None and target_type == "container":
        audit_details["container"] = getattr(session.container, "name", None)

    entry = _OpenTerminal(
        token=login_session.token,
        user_id=user.id,
        expires_at=_aware(login_session.expires_at),
    )
    _open_terminals.add(entry)
    opened_at = time.monotonic()
    await _audit("terminal_open", user.id, user.username, client_ip, user_agent, audit_details)

    # Send connected message
    await websocket.send_text(json.dumps({"type": "connected"}))

    output_task = asyncio.create_task(session.read_output())
    input_task = asyncio.create_task(_pump_input(websocket, session, entry))
    watch_task = asyncio.create_task(_watch_session(entry))
    tasks = {output_task, input_task, watch_task}

    reason = "client disconnected"
    close_code = None
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if entry.closed.is_set():
            reason = entry.reason or "session ended"
            close_code = CLOSE_UNAUTHORIZED
        elif output_task in done:
            reason = "shell exited"
            close_code = 1000
        elif input_task in done and input_task.exception() is not None:
            exc = input_task.exception()
            if not isinstance(exc, WebSocketDisconnect):
                logger.error(f"Terminal WebSocket error: {exc!r}")
                reason = "error"
    except Exception:
        logger.exception("Terminal WebSocket error")
        reason = "error"
    finally:
        _open_terminals.discard(entry)
        entry.close(reason)
        for task in tasks:
            task.cancel()

        async def _cleanup():
            await asyncio.gather(*tasks, return_exceptions=True)

            await session.stop()

            if close_code is not None:
                try:
                    if close_code == CLOSE_UNAUTHORIZED:
                        await websocket.send_text(json.dumps({"type": "error", "message": f"Terminal closed: {reason}"}))
                    await websocket.send_text(json.dumps({"type": "disconnected", "reason": reason}))
                    await websocket.close(code=close_code, reason=reason[:120])
                except Exception:
                    pass

            await _audit(
                "terminal_close",
                user.id,
                user.username,
                client_ip,
                user_agent,
                {**audit_details, "reason": reason, "duration_seconds": round(time.monotonic() - opened_at)},
            )
            logger.info(f"Terminal WebSocket closed: {target} ({reason})")

        # Run the cleanup to completion (remove the host helper container,
        # write the close audit record) even if this handler is cancelled,
        # e.g. on server shutdown.
        await asyncio.shield(asyncio.ensure_future(_cleanup()))
