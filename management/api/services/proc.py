"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/proc.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Non-blocking replacement for ``subprocess.run`` in async code.

The API runs a single uvicorn worker whose event loop also drives the
scheduler, so a blocking ``subprocess.run`` (pg_dump, psql, docker) stalls
every request, terminal and scheduled job until it returns - forever if it
hangs. ``run()`` keeps the familiar subprocess.run call shape and result
(``CompletedProcess``, ``TimeoutExpired`` on timeout) but runs the child with
asyncio and always enforces a timeout: on expiry the child and its process
group are killed and reaped before ``subprocess.TimeoutExpired`` is raised.
"""

import asyncio
import os
import signal
import subprocess
from typing import Any, Mapping, Optional, Sequence, Union

# Default timeouts (seconds) for common command classes.
DOCKER_TIMEOUT = 30        # docker ps/inspect/rm/stop/exec of a quick command
DOCKER_RUN_TIMEOUT = 300   # docker run -d (may have to pull the image first)
PSQL_TIMEOUT = 60          # a single small psql query
QUERY_TIMEOUT = 300        # psql query that reads a whole table (workflows, credentials)
COPY_TIMEOUT = 30 * 60     # docker cp / helper-container file copies
PG_DUMP_TIMEOUT = 2 * 60 * 60   # pg_dump of a large database
PG_RESTORE_TIMEOUT = 2 * 60 * 60  # pg_restore / psql -f of a large dump
PG_LOCK_WAIT_TIMEOUT = "120s"   # pg_dump --lock-wait-timeout: fail instead of hanging behind a migration lock

_Stream = Union[int, Any, None]


def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    """SIGKILL the child and everything it started (it leads its own session)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def _decode(data: Optional[bytes], text: bool) -> Any:
    if data is None or not text:
        return data
    return data.decode("utf-8", errors="replace")


async def run(
    cmd: Sequence[str],
    *,
    timeout: float,
    input: Optional[Union[str, bytes]] = None,
    capture_output: bool = False,
    text: bool = False,
    env: Optional[Mapping[str, str]] = None,
    cwd: Optional[str] = None,
    stdout: _Stream = None,
    stderr: _Stream = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """
    Async counterpart of ``subprocess.run(cmd, ...)`` with a mandatory timeout.

    ``stdout`` / ``stderr`` accept the same values as subprocess.run
    (``subprocess.PIPE``, ``subprocess.DEVNULL``, an open file) and are
    overridden by ``capture_output=True``. Raises FileNotFoundError when the
    program does not exist, ``subprocess.TimeoutExpired`` after killing the
    child on timeout, and ``subprocess.CalledProcessError`` when ``check`` is
    set and the exit status is non-zero.
    """
    if capture_output:
        stdout = stderr = asyncio.subprocess.PIPE
    stdin = asyncio.subprocess.PIPE if input is not None else asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=dict(env) if env is not None else None,
        cwd=cwd,
        # Own process group: a timeout kills grandchildren too (e.g. the
        # command `sh -c` started), which would otherwise keep the pipes open.
        start_new_session=True,
    )
    data = input.encode() if isinstance(input, str) else input
    try:
        out, err = await asyncio.wait_for(proc.communicate(data), timeout=timeout)
    except asyncio.TimeoutError:
        _kill_tree(proc)
        await proc.wait()
        raise subprocess.TimeoutExpired(list(cmd), timeout)
    except asyncio.CancelledError:
        # The caller was cancelled: never leave the child running.
        _kill_tree(proc)
        raise
    result = subprocess.CompletedProcess(
        list(cmd), proc.returncode, _decode(out, text), _decode(err, text)
    )
    if check:
        result.check_returncode()
    return result
