"""
Backup, verification and restore run as background jobs (H-24): the request
returns 202 at once, the client polls the job, a busy system answers 409, and
a job cut short by a restart is reported as interrupted.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.services import operation_jobs as jobs
from api.services import operation_lock


@pytest.fixture(autouse=True)
async def _fresh_jobs():
    jobs._reset_for_tests()
    yield
    await jobs.cancel_all()
    jobs._reset_for_tests()


async def _until(predicate, timeout: float = 5.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, "condition not reached"
        await asyncio.sleep(0.01)


async def _wait(job_id: str, timeout: float = 5.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        job = await jobs.load_job(job_id)
        if job and job.status in jobs.FINAL_STATUSES:
            return job
        assert asyncio.get_running_loop().time() < deadline, f"job still {job.status if job else None}"
        await asyncio.sleep(0.02)


async def _stored(session_maker, job_id):
    from api.models.backups import OperationJob

    async with session_maker() as s:
        return await s.get(OperationJob, job_id)


async def test_job_runs_in_background_and_records_result(session_maker):
    release = asyncio.Event()

    async def runner():
        jobs.report_progress(40, "Dumping databases", backup_id=7)
        await release.wait()
        return {"backup_id": 7, "status": "success"}

    job = jobs.start_job("backup", runner, lock_name="backup")
    assert job.status == "queued"  # returned before any work ran
    await _until(lambda: job.progress == 40)
    assert job.status == "running" and job.backup_id == 7
    assert operation_lock.current_operation() == "backup"

    release.set()
    done = await _wait(job.id)
    assert done.status == "success" and done.result == {"backup_id": 7, "status": "success"}
    assert not operation_lock.is_busy()
    row = await _stored(session_maker, job.id)
    assert row.status == "success" and row.result["backup_id"] == 7 and row.finished_at is not None


async def test_second_job_and_scheduled_work_are_refused_while_busy(session_maker):
    release = asyncio.Event()

    async def runner():
        await release.wait()

    first = jobs.start_job("verify", runner, lock_name="verification")
    with pytest.raises(operation_lock.OperationBusyError):
        jobs.start_job("restore", runner, lock_name="restore")
    release.set()
    await _wait(first.id)

    # the global lock held by e.g. a scheduled backup also blocks a new job
    async with operation_lock.exclusive_operation("backup"):
        with pytest.raises(operation_lock.OperationBusyError) as exc:
            jobs.start_job("restore", runner, lock_name="restore")
        assert exc.value.holder == "backup"


async def test_failed_job_keeps_structured_error(session_maker):
    result = {"status": "failed", "error": "pg_restore failed", "safety_dump": "/x.dump"}

    async def runner():
        raise jobs.JobFailed(result, result=result)

    job = jobs.start_job("restore", runner, lock_name="restore", backup_id=3)
    done = await _wait(job.id)
    assert done.status == "failed" and done.error == result
    assert (await _stored(session_maker, job.id)).error == result


async def test_exception_fails_the_job_and_releases_the_lock(session_maker):
    async def runner():
        raise RuntimeError("disk full")

    job = jobs.start_job("backup", runner, lock_name="backup")
    done = await _wait(job.id)
    assert done.status == "failed" and "disk full" in done.error
    assert not operation_lock.is_busy()


async def test_restart_marks_running_jobs_interrupted(session_maker):
    from api.models.backups import OperationJob

    async with session_maker() as s:
        s.add(OperationJob(id="deadbeef", kind="restore", status="running", progress=30))
        s.add(OperationJob(id="cafef00d", kind="backup", status="success", progress=100))
        await s.commit()

    assert await jobs.mark_interrupted_jobs() == 1
    job = await jobs.load_job("deadbeef")
    assert job.status == "interrupted" and job.error == jobs.INTERRUPTED_MESSAGE
    assert (await jobs.load_job("cafef00d")).status == "success"


# --- HTTP contract -------------------------------------------------------------------

@pytest.fixture
async def client(session_maker, monkeypatch):
    from fastapi import FastAPI

    import api.database
    from api.database import get_db
    from api.dependencies import get_current_user
    from api.routers import backups

    monkeypatch.setattr(api.database, "n8n_session_maker", session_maker)
    app = FastAPI()
    app.include_router(backups.router, prefix="/api/backups")

    async def _db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    async with AsyncClient(app=app, base_url="http://test") as http:
        yield http


async def _poll(client, job_id, timeout=5.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        r = await client.get(f"/api/backups/jobs/{job_id}")
        assert r.status_code == 200, r.text
        if r.json()["status"] in jobs.FINAL_STATUSES:
            return r.json()
        assert asyncio.get_running_loop().time() < deadline
        await asyncio.sleep(0.02)


async def test_post_run_returns_202_and_job_reports_backup(client, monkeypatch):
    from api.services import backup_runner

    release = asyncio.Event()

    async def fake_backup(db, n8n_db, backup_type, compression, skip_auto_verify, wait, **kw):
        assert wait is False
        async with operation_lock.exclusive_operation("backup", wait=False):
            jobs.report_progress(50, "Creating archive", backup_id=12)
            await release.wait()
        return SimpleNamespace(id=12, status="success", filename="backup_x_12.n8n_backup.tar.gz")

    monkeypatch.setattr(backup_runner, "run_backup_exclusive", fake_backup)

    r = await client.post("/api/backups/run", json={"backup_type": "postgres_full", "skip_auto_verify": True})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["job_id"] == body["id"] and body["kind"] == "backup" and body["status"] in ("queued", "running")

    await _until(lambda: jobs.get_job(body["id"]).progress == 50)
    live = (await client.get(f"/api/backups/jobs/{body['id']}")).json()
    assert live["status"] == "running" and live["progress"] == 50 and live["backup_id"] == 12

    # anything else is refused while it runs
    busy = await client.post("/api/backups/run-full", json={"backup_type": "postgres_full"})
    assert busy.status_code == 409

    release.set()
    final = await _poll(client, body["id"])
    assert final["status"] == "success"
    assert final["result"]["backup_id"] == 12 and final["result"]["status"] == "success"

    listing = (await client.get("/api/backups/jobs")).json()["jobs"]
    assert listing[0]["id"] == body["id"]


async def test_failed_restore_job_exposes_full_result(client, monkeypatch):
    from api.routers import backups

    result = {"status": "failed", "error": "pg_restore failed", "stderr": "boom"}

    class FakeRestore:
        def __init__(self, db, *a):
            self.backup_service = SimpleNamespace(get_backup=self._get)

        async def _get(self, backup_id):
            return SimpleNamespace(id=backup_id)

        def check_database_restorable(self, name, target):
            return None

        async def restore_database(self, **kw):
            return result

    monkeypatch.setattr(backups, "RestoreService", FakeRestore)
    r = await client.post("/api/backups/5/restore/database", json={"database_name": "n8n"})
    assert r.status_code == 202, r.text
    final = await _poll(client, r.json()["id"])
    assert final["status"] == "failed" and final["error"] == result and final["backup_id"] == 5


async def test_verify_job_result_is_the_verification_report(client, monkeypatch):
    from api.routers import backups

    class FakeBackupService:
        def __init__(self, db):
            pass

        async def get_backup(self, backup_id):
            return SimpleNamespace(id=backup_id)

    class FakeVerification:
        def __init__(self, db):
            pass

        async def verify_backup(self, backup_id, verify_all_workflows, workflow_sample_size):
            jobs.report_progress(60, "Verifying row counts")
            return {"overall_status": "passed", "checks": {"tables": {"passed": True}}, "errors": [],
                    "warnings": [], "duration_seconds": 1.5}

    monkeypatch.setattr(backups, "BackupService", FakeBackupService)
    monkeypatch.setattr(backups, "VerificationService", FakeVerification)
    r = await client.post("/api/backups/9/verify", json={})
    assert r.status_code == 202
    final = await _poll(client, r.json()["id"])
    assert final["status"] == "success"
    assert final["result"]["overall_status"] == "passed" and final["result"]["backup_id"] == 9


async def test_unknown_job_and_unknown_backup_are_404(client, monkeypatch):
    from api.routers import backups

    class NoBackups:
        def __init__(self, db):
            pass

        async def get_backup(self, backup_id):
            return None

    monkeypatch.setattr(backups, "BackupService", NoBackups)
    assert (await client.get("/api/backups/jobs/nope")).status_code == 404
    assert (await client.post("/api/backups/77/verify", json={})).status_code == 404
    assert jobs.active_job() is None
