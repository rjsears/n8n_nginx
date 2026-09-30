"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/operation_lock.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Process-wide lock that serialises backup, restore, verification and pruning.

The management API runs a single uvicorn worker (see supervisord.conf), so an
asyncio.Lock is sufficient to stop these operations from overlapping.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_holder: Optional[str] = None


class OperationBusyError(RuntimeError):
    """Raised when a non-waiting caller finds another operation in progress."""

    def __init__(self, requested: str, holder: Optional[str]):
        self.requested = requested
        self.holder = holder
        super().__init__(
            f"Cannot start {requested}: {holder or 'another operation'} is already in progress"
        )


def is_busy() -> bool:
    """Return True if a backup/restore/verify/prune operation holds the lock."""
    return _lock.locked()


def current_operation() -> Optional[str]:
    """Return the name of the operation holding the lock, if any."""
    return _holder


@asynccontextmanager
async def exclusive_operation(name: str, wait: bool = True) -> AsyncIterator[None]:
    """
    Hold the global operation lock for the duration of the block.

    Args:
        name: Human-readable operation name, e.g. "backup", "restore", "pruning".
        wait: If False, raise OperationBusyError instead of waiting when busy.
    """
    global _holder
    if not wait and _lock.locked():
        raise OperationBusyError(name, _holder)
    await _lock.acquire()
    _holder = name
    logger.debug("Operation lock acquired by %s", name)
    try:
        yield
    finally:
        _holder = None
        _lock.release()
        logger.debug("Operation lock released by %s", name)
