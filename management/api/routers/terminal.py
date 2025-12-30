"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/terminal.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
import docker
import json

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

    async def start(self):
        """Start the terminal session."""
        try:
            if self.target_type == "host":
                # For host access, create a privileged alpine container
                # that shares the host's namespaces
                self.container = self.client.containers.run(
                    "alpine:latest",
                    command="/bin/sh",
                    stdin_open=True,
                    tty=True,
                    detach=True,
                    remove=True,
                    pid_mode="host",
                    network_mode="host",
                    privileged=True,
                    volumes={"/": {"bind": "/host", "mode": "rw"}},
                )
                # Wait for container to be ready
                await asyncio.sleep(0.5)
            else:
                # Find the container by ID or name
                containers = self.client.containers.list(all=True)
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

            # Determine shell to use
            shell = self._detect_shell()

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
            exec_instance = self.client.api.exec_create(
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
            self.socket = self.client.api.exec_start(
                self.exec_id,
                socket=True,
                tty=True,
            )

            self._running = True
            return True

        except docker.errors.ImageNotFound:
            await self.websocket.send_text(
                json.dumps({"type": "error", "message": "Alpine image not found. Pull alpine:latest first."})
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
            sock = self.socket._sock
            sock.setblocking(False)

            while self._running:
                try:
                    data = sock.recv(4096)
                    if data:
                        # Send as text (terminal output)
                        await self.websocket.send_text(
                            json.dumps({"type": "output", "data": data.decode("utf-8", errors="replace")})
                        )
                    else:
                        # Connection closed
                        break
                except BlockingIOError:
                    # No data available, wait a bit
                    await asyncio.sleep(0.01)
                except Exception as e:
                    if self._running:
                        logger.debug(f"Read error: {e}")
                    break

        except Exception as e:
            logger.exception("Error reading terminal output")

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
                self.client.api.exec_resize(self.exec_id, height=rows, width=cols)
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
                self.container.stop(timeout=1)
            except Exception:
                pass
            try:
                self.container.remove(force=True)
            except Exception:
                pass


async def verify_token(token: str) -> bool:
    """Verify the authentication token for WebSocket connection."""
    from api.database import async_session_maker
    from api.services.auth_service import AuthService
    from sqlalchemy import select
    from api.models.auth import Session
    from datetime import datetime, UTC

    if not token:
        return False

    try:
        async with async_session_maker() as db:
            # Directly query the session table for simplicity
            result = await db.execute(
                select(Session).where(
                    Session.token == token,
                    Session.is_active == True,
                    Session.expires_at > datetime.now(UTC)
                )
            )
            session = result.scalar_one_or_none()
            return session is not None
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return False


@router.websocket("/ws/terminal")
async def terminal_websocket(
    websocket: WebSocket,
    target: str = Query(..., description="Target container ID or 'host'"),
    token: str = Query(..., description="Authentication token"),
):
    """
    WebSocket endpoint for terminal access.

    Connect with: ws://host/api/ws/terminal?target=container_id&token=session_token

    Messages from client:
    - {"type": "input", "data": "command"} - Send input to terminal
    - {"type": "resize", "rows": 24, "cols": 80} - Resize terminal

    Messages from server:
    - {"type": "output", "data": "text"} - Terminal output
    - {"type": "error", "message": "error text"} - Error message
    - {"type": "connected"} - Connection established
    - {"type": "disconnected"} - Connection closed
    """
    # Verify authentication
    if not await verify_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    # Determine target type
    target_type = "host" if target == "host" else "container"

    # Send connection acknowledgment
    await websocket.send_text(
        json.dumps({"type": "connecting", "target": target, "target_type": target_type})
    )

    # Create terminal session
    session = TerminalSession(websocket, target, target_type)

    if not await session.start():
        await websocket.close()
        return

    # Send connected message
    await websocket.send_text(json.dumps({"type": "connected"}))

    # Start output reader task
    output_task = asyncio.create_task(session.read_output())

    try:
        while True:
            # Receive message from client
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "input":
                    await session.write_input(data.get("data", ""))
                elif msg_type == "resize":
                    await session.resize(
                        data.get("rows", 24),
                        data.get("cols", 80)
                    )
                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                # Treat as raw input
                await session.write_input(message)

    except WebSocketDisconnect:
        logger.info(f"Terminal WebSocket disconnected: {target}")
    except Exception as e:
        logger.exception("Terminal WebSocket error")
    finally:
        # Clean up
        await session.stop()
        output_task.cancel()
        try:
            await output_task
        except asyncio.CancelledError:
            pass

        try:
            await websocket.send_text(json.dumps({"type": "disconnected"}))
        except Exception:
            pass
