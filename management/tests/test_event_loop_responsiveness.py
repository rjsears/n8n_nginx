"""
Long backup/restore/verify work must not block the API's single event loop
(H-11): subprocesses run asynchronously with a timeout, blocking calls are
moved to worker threads.
"""

from __future__ import annotations

import ast
import asyncio
import os
import subprocess
import time
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1] / "api"


async def _ticks_while(coro, interval: float = 0.05):
    """Run coro while a ticker counts how often the loop lets it run."""
    ticks = 0
    done = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not done.is_set():
            ticks += 1
            await asyncio.sleep(interval)

    t = asyncio.create_task(ticker())
    try:
        result = await coro
    finally:
        done.set()
        await t
    return result, ticks


def _fake_program(tmp_path: Path, name: str, body: str) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    prog = bin_dir / name
    prog.write_text("#!/bin/sh\n" + body)
    prog.chmod(0o755)


@pytest.fixture
def fake_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")
    return tmp_path


async def test_proc_run_returns_completed_process():
    from api.services import proc

    result = await proc.run(["sh", "-c", "cat; echo err >&2; exit 3"], input="hello",
                            capture_output=True, text=True, timeout=10)
    assert isinstance(result, subprocess.CompletedProcess)
    assert (result.returncode, result.stdout, result.stderr.strip()) == (3, "hello", "err")
    with pytest.raises(subprocess.CalledProcessError):
        await proc.run(["false"], timeout=10, check=True)


async def test_proc_run_kills_the_child_on_timeout(tmp_path):
    from api.services import proc

    marker = tmp_path / "still-running"
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        await proc.run(["sh", "-c", f"sleep 3; touch {marker}"], capture_output=True, timeout=0.3)
    assert time.monotonic() - started < 2
    await asyncio.sleep(3.2)
    assert not marker.exists(), "the timed-out child kept running"


async def test_event_loop_stays_responsive_during_pg_dump(fake_path, monkeypatch):
    """A slow pg_dump (the longest backup step) leaves the loop free for other requests."""
    from api.services.backup_service import BackupService

    args_file = fake_path / "args"
    _fake_program(fake_path, "pg_dump", f'echo "$@" > {args_file}\nsleep 1\n'
                                        'while [ "$1" != "-f" ]; do shift; done; echo dump > "$2"\n')
    out = fake_path / "n8n.dump"

    started = time.monotonic()
    _, ticks = await _ticks_while(BackupService(db=None)._execute_pg_dump_to_file("n8n", str(out)))

    assert time.monotonic() - started >= 1
    assert out.read_text().strip() == "dump"
    assert ticks >= 10, f"event loop was blocked during pg_dump (ticker ran {ticks}x in ~1s)"
    assert "--lock-wait-timeout=" in args_file.read_text(), "pg_dump can hang forever behind a lock"


async def test_event_loop_stays_responsive_while_writing_the_archive(tmp_path, monkeypatch):
    """tar/gzip of the staging directory runs in a worker thread."""
    from api.services import backup_service

    def slow_write(source_dir, archive_path, passphrase):
        time.sleep(1)  # stands in for tar+gzip(+gpg) of a large staging dir
        Path(archive_path).write_bytes(b"x")

    monkeypatch.setattr(backup_service.BackupService, "_write_archive", staticmethod(slow_write))
    archive = tmp_path / "a.tar.gz"
    _, ticks = await _ticks_while(
        asyncio.to_thread(backup_service.BackupService._write_archive, str(tmp_path), str(archive), None)
    )
    assert ticks >= 10


async def test_verification_restore_runs_off_the_loop(monkeypatch):
    """pg_restore into the verification container (sync helper) is awaited via a thread."""
    from api.services import verification_service as vs

    def slow_restore(self, dump_path, db_name, target_db):
        time.sleep(1)
        return True, ""

    monkeypatch.setattr(vs.VerificationService, "_restore_dump_into_verify_db", slow_restore)
    service = vs.VerificationService(db=None)
    _, ticks = await _ticks_while(asyncio.to_thread(service._restore_dump_into_verify_db, "d", "n8n", "verify_n8n"))
    assert ticks >= 10


def test_archive_names_are_unique_per_backup():
    from datetime import UTC, datetime

    from api.services.backup_service import backup_archive_basename

    now = datetime(2026, 11, 1, 8, 30, 0, tzinfo=UTC)
    a = backup_archive_basename(41, now)
    b = backup_archive_basename(42, now)
    assert a == "backup_20261101T083000Z_41.n8n_backup.tar.gz"
    assert a != b
    # without a history id two calls in the same second still differ
    assert backup_archive_basename(None, now) != backup_archive_basename(None, now)


def test_write_archive_never_overwrites(tmp_path):
    from api.services.backup_service import BackupService

    src = tmp_path / "src"
    src.mkdir()
    (src / "f").write_text("x")
    target = tmp_path / "backup.tar.gz"
    target.write_text("existing")
    with pytest.raises(FileExistsError):
        BackupService._write_archive(str(src), str(target), None)
    assert target.read_text() == "existing"


# --- static guard ------------------------------------------------------------------

def _python_files():
    return [p for p in API_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def _calls_in_async_bodies(tree):
    """(call, function) for calls lexically inside an async def (not inside nested sync defs)."""
    found = []

    def visit(node, fn):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.AsyncFunctionDef):
                visit(child, child)
            elif isinstance(child, (ast.FunctionDef, ast.Lambda)):
                visit(child, None)
            else:
                if fn is not None and isinstance(child, ast.Call):
                    found.append((child, fn))
                visit(child, fn)

    visit(tree, None)
    return found


BLOCKING_IN_ASYNC = {"subprocess.run", "subprocess.check_output", "subprocess.call", "subprocess.check_call",
                     "time.sleep", "docker.from_env"}


def test_no_blocking_subprocess_or_sleep_inside_async_functions():
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text())
        for call, fn in _calls_in_async_bodies(tree):
            name = ast.unparse(call.func)
            if name in BLOCKING_IN_ASYNC:
                offenders.append(f"{path.relative_to(API_DIR)}:{call.lineno} {fn.name}: {name}()")
    assert not offenders, "blocking call on the event loop:\n" + "\n".join(offenders)


def test_every_subprocess_has_a_timeout():
    missing = []
    for path in _python_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            kwargs = {k.arg for k in node.keywords}
            direct = name in ("subprocess.run", "_proc.run", "proc.run")
            threaded = (name == "asyncio.to_thread" and node.args
                        and ast.unparse(node.args[0]) == "subprocess.run")
            if (direct or threaded) and "timeout" not in kwargs:
                missing.append(f"{path.relative_to(API_DIR)}:{node.lineno} {name}")
    assert not missing, "subprocess without a timeout:\n" + "\n".join(missing)
