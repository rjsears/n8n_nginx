"""Unit tests for the global operation lock (api/services/operation_lock.py)."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

_LOCK_PATH = Path(__file__).resolve().parents[1] / "api" / "services" / "operation_lock.py"


@pytest.fixture
def lock_mod():
    # Fresh module (and asyncio.Lock) per test: each test runs its own event loop.
    spec = importlib.util.spec_from_file_location("operation_lock_under_test", _LOCK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_wait_succeeds_when_idle(lock_mod):
    async def scenario():
        assert not lock_mod.is_busy()
        async with lock_mod.exclusive_operation("pruning", wait=False):
            assert lock_mod.is_busy()
            assert lock_mod.current_operation() == "pruning"
        assert not lock_mod.is_busy()
        assert lock_mod.current_operation() is None

    asyncio.run(scenario())


def test_no_wait_raises_while_held(lock_mod):
    async def scenario():
        async with lock_mod.exclusive_operation("backup"):
            with pytest.raises(lock_mod.OperationBusyError) as exc:
                async with lock_mod.exclusive_operation("pruning", wait=False):
                    pass
            assert exc.value.holder == "backup"

    asyncio.run(scenario())


def test_no_wait_raises_when_a_waiter_is_queued_after_release(lock_mod):
    """
    Right after release the lock reads as unlocked until the queued waiter is
    resumed. A no-wait caller must not slip in (or silently queue behind it).
    """
    events = []

    async def queued_backup():
        async with lock_mod.exclusive_operation("backup"):
            events.append("backup ran")

    async def scenario():
        async with lock_mod.exclusive_operation("restore"):
            waiter = asyncio.create_task(queued_backup())
            await asyncio.sleep(0)  # let it block in acquire()
            assert lock_mod._waiters == 1
        # Released; the waiter has not been resumed yet (no await since).
        assert not lock_mod._lock.locked()
        assert lock_mod.is_busy()
        with pytest.raises(lock_mod.OperationBusyError):
            async with lock_mod.exclusive_operation("pruning", wait=False):
                events.append("pruning ran")
        await waiter
        assert lock_mod._waiters == 0
        assert not lock_mod.is_busy()

    asyncio.run(scenario())
    assert events == ["backup ran"]


def test_cancelled_waiter_does_not_leak_count(lock_mod):
    async def scenario():
        async with lock_mod.exclusive_operation("backup"):
            waiter = asyncio.create_task(_enter(lock_mod, "verify"))
            await asyncio.sleep(0)
            assert lock_mod._waiters == 1
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
        assert lock_mod._waiters == 0
        async with lock_mod.exclusive_operation("pruning", wait=False):
            pass

    asyncio.run(scenario())


async def _enter(lock_mod, name):
    async with lock_mod.exclusive_operation(name):
        pass
