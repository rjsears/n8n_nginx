"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/operation_jobs.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Background jobs for backups, verifications and restores started from the API.

These operations take from seconds to well over the 300 s proxy timeout of
the management nginx, so the API no longer runs them inside the HTTP request:
POST starts a job and returns 202 with its id; the client polls
GET /api/backups/jobs/{id} for status, progress and the final result.

* Only one job runs at a time, and none starts while the global operation
  lock (api.services.operation_lock) is held: start_job raises
  OperationBusyError, which the API turns into 409. The check and the job
  registration happen without an await in between, so two requests cannot
  both get through.
* Live state (progress, message) is kept in memory. Every state change is
  also written to the operation_jobs table, so the outcome can be read after
  the fact and a job cut short by an API restart is reported as
  'interrupted' (mark_interrupted_jobs at startup).
* Code running inside a job reports progress with report_progress(); it is a
  no-op outside a job, so services can call it unconditionally.
"""

import asyncio
import json
import logging
import secrets
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from api.services import operation_lock
from api.services.operation_lock import OperationBusyError

logger = logging.getLogger(__name__)

JOB_KINDS = ("backup", "verify", "restore")
ACTIVE_STATUSES = ("queued", "running")
FINAL_STATUSES = ("success", "failed", "interrupted")
MAX_JOBS_IN_MEMORY = 50
INTERRUPTED_MESSAGE = "The management API restarted while this job was running; the operation did not finish."


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"
    backup_id: Optional[int] = None
    params: Dict[str, Any] = field(default_factory=dict)
    progress: int = 0
    message: str = "Queued"
    result: Any = None
    error: Any = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "backup_id": self.backup_id,
            "params": self.params,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class JobFailed(Exception):
    """Raised by a job runner to finish the job as 'failed' with a structured error."""

    def __init__(self, detail: Any, result: Any = None):
        self.detail = detail
        self.result = result
        super().__init__(detail if isinstance(detail, str) else json.dumps(_jsonable(detail)))


_jobs: "OrderedDict[str, Job]" = OrderedDict()
_tasks: Dict[str, asyncio.Task] = {}
_current_job: ContextVar[Optional[Job]] = ContextVar("current_operation_job", default=None)


def _jsonable(value: Any) -> Any:
    """Round-trip through JSON so results with datetimes etc. can be stored and returned."""
    if value is None:
        return None
    return json.loads(json.dumps(value, default=str))


def _now() -> datetime:
    return datetime.now(UTC)


def active_job() -> Optional[Job]:
    """The queued/running job, if any."""
    for job in _jobs.values():
        if job.active:
            return job
    return None


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def current_job() -> Optional[Job]:
    return _current_job.get()


def report_progress(
    progress: Optional[int] = None,
    message: Optional[str] = None,
    backup_id: Optional[int] = None,
) -> None:
    """Update the progress of the job this code runs in (no-op outside a job)."""
    job = _current_job.get()
    if job is None or not job.active:
        return
    if progress is not None:
        job.progress = max(0, min(int(progress), 100))
    if message is not None:
        job.message = message
    if backup_id is not None and job.backup_id is None:
        job.backup_id = backup_id


def _remember(job: Job) -> None:
    _jobs[job.id] = job
    while len(_jobs) > MAX_JOBS_IN_MEMORY:
        oldest_id = next(iter(_jobs))
        if _jobs[oldest_id].active:
            break
        _jobs.pop(oldest_id)


def start_job(
    kind: str,
    runner: Callable[[], Awaitable[Any]],
    *,
    lock_name: Optional[str],
    backup_id: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Job:
    """
    Register a job and start it in the background. Returns immediately.

    lock_name: hold the global operation lock under this name while the
    runner runs (None when the runner takes the lock itself, as
    run_backup_exclusive does).

    Raises OperationBusyError if another job is queued/running or the
    operation lock is held (e.g. by a scheduled backup).
    """
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown job kind {kind!r}")
    running = active_job()
    if running is not None:
        raise OperationBusyError(lock_name or kind, f"{running.kind} job {running.id}")
    if operation_lock.is_busy():
        raise OperationBusyError(lock_name or kind, operation_lock.current_operation())

    job = Job(id=secrets.token_hex(8), kind=kind, backup_id=backup_id, params=_jsonable(params or {}))
    _remember(job)
    task = asyncio.get_running_loop().create_task(_run(job, runner, lock_name), name=f"{kind}-job-{job.id}")
    _tasks[job.id] = task
    task.add_done_callback(lambda _t, jid=job.id: _tasks.pop(jid, None))
    logger.info(f"Started {kind} job {job.id} (backup_id={backup_id})")
    return job


async def _run(job: Job, runner: Callable[[], Awaitable[Any]], lock_name: Optional[str]) -> None:
    token = _current_job.set(job)
    await _persist(job)
    try:
        if lock_name:
            async with operation_lock.exclusive_operation(lock_name, wait=False):
                await _mark_running(job)
                result = await runner()
        else:
            await _mark_running(job)
            result = await runner()
        job.result = _jsonable(result)
        job.status = "success"
        job.progress = 100
        job.message = "Completed"
    except OperationBusyError as e:
        job.status = "failed"
        job.error = f"{e}. Wait for it to finish and try again."
        job.message = "Another operation is in progress"
    except JobFailed as e:
        job.status = "failed"
        job.error = _jsonable(e.detail)
        job.result = _jsonable(e.result)
        job.message = "Failed"
    except asyncio.CancelledError:
        job.status = "interrupted"
        job.error = "The job was cancelled (management API shutting down)."
        job.message = "Interrupted"
        job.finished_at = _now()
        await asyncio.shield(_persist(job))
        raise
    except Exception as e:
        logger.exception(f"{job.kind} job {job.id} failed")
        job.status = "failed"
        job.error = str(e) or repr(e)
        job.message = "Failed"
    finally:
        _current_job.reset(token)
    job.finished_at = _now()
    logger.info(f"{job.kind} job {job.id} finished: {job.status}")
    await _persist(job)


async def _mark_running(job: Job) -> None:
    job.status = "running"
    job.started_at = _now()
    if job.message == "Queued":
        job.message = "Running"
    await _persist(job)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _row_values(job: Job) -> Dict[str, Any]:
    return {
        "kind": job.kind,
        "status": job.status,
        "backup_id": job.backup_id,
        "params": job.params,
        "progress": job.progress,
        "message": job.message,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


async def _persist(job: Job) -> None:
    """Write the job's state; a database problem never fails the job itself."""
    from api import database
    from api.models.backups import OperationJob

    try:
        async with database.async_session_maker() as session:
            row = await session.get(OperationJob, job.id)
            if row is None:
                session.add(OperationJob(id=job.id, **_row_values(job)))
            else:
                for key, value in _row_values(job).items():
                    setattr(row, key, value)
            await session.commit()
    except Exception as e:
        logger.warning(f"Could not record {job.kind} job {job.id} ({job.status}): {e}")


def _job_from_row(row) -> Job:
    return Job(
        id=row.id,
        kind=row.kind,
        status=row.status,
        backup_id=row.backup_id,
        params=row.params or {},
        progress=row.progress or 0,
        message=row.message or "",
        result=row.result,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


async def load_job(job_id: str) -> Optional[Job]:
    """Job by id: the live in-memory copy, else the stored record."""
    job = _jobs.get(job_id)
    if job is not None:
        return job
    from api import database
    from api.models.backups import OperationJob

    try:
        async with database.async_session_maker() as session:
            row = await session.get(OperationJob, job_id)
            return _job_from_row(row) if row else None
    except Exception as e:
        logger.warning(f"Could not read job {job_id}: {e}")
        return None


async def list_jobs(limit: int = 20, kind: Optional[str] = None) -> List[Job]:
    """Most recent jobs first (stored records, with live state for jobs in memory)."""
    from sqlalchemy import select

    from api import database
    from api.models.backups import OperationJob

    jobs: Dict[str, Job] = {}
    try:
        async with database.async_session_maker() as session:
            stmt = select(OperationJob).order_by(OperationJob.created_at.desc()).limit(limit)
            if kind:
                stmt = stmt.where(OperationJob.kind == kind)
            for row in (await session.execute(stmt)).scalars():
                jobs[row.id] = _job_from_row(row)
    except Exception as e:
        logger.warning(f"Could not list stored jobs: {e}")
    for job in _jobs.values():
        if kind is None or job.kind == kind:
            jobs[job.id] = job
    ordered = sorted(jobs.values(), key=lambda j: j.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return ordered[:limit]


async def mark_interrupted_jobs() -> int:
    """
    Startup hook: jobs recorded as queued/running belonged to the previous
    process and can no longer finish. Returns how many were marked.
    """
    from sqlalchemy import update

    from api import database
    from api.models.backups import OperationJob

    try:
        async with database.async_session_maker() as session:
            result = await session.execute(
                update(OperationJob)
                .where(OperationJob.status.in_(ACTIVE_STATUSES))
                .values(status="interrupted", error=INTERRUPTED_MESSAGE, message="Interrupted",
                        finished_at=_now())
            )
            await session.commit()
            count = result.rowcount or 0
    except Exception as e:
        logger.warning(f"Could not mark interrupted jobs: {e}")
        return 0
    if count:
        logger.warning(f"Marked {count} backup/verify/restore job(s) as interrupted by the restart")
    return count


async def cancel_all() -> None:
    """Shutdown hook: cancel running jobs so they are recorded as interrupted."""
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _reset_for_tests() -> None:
    _jobs.clear()
    _tasks.clear()
