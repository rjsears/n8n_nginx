"""
Off-host storage detection (audit H-7) and verification that actually
verifies (audit H-8).
"""

from __future__ import annotations

import os
import subprocess
import tarfile
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from api.services import backup_storage as bs
from api.services import backup_service as bsvc
from api.services import verification_service as vs


# --- mountinfo parsing / detection ---------------------------------------------------

def _mountinfo(tmp_path, backup_dir, fstype, source="nas:/export/n8n"):
    text = (
        "22 1 253:0 / / rw,relatime - overlay overlay rw,lowerdir=/x\n"
        "31 22 253:1 /opt/n8n_backups " + str(backup_dir).replace(" ", "\\040")
        + " rw,relatime - " + fstype + " " + source + " rw,vers=4.2\n"
        "32 22 253:1 /srv/n8n /app/host_project rw,relatime - ext4 /dev/sda1 rw\n"
    )
    path = tmp_path / "mountinfo"
    path.write_text(text)
    return str(path)


def test_parse_mountinfo_handles_optional_fields_and_escapes():
    entries = bs.parse_mountinfo(
        "36 35 98:0 /mnt1 /mnt/with\\040space rw,noatime master:1 shared:2 - nfs4 srv:/x rw\n"
        "garbage line\n"
    )
    assert len(entries) == 1
    assert entries[0].mount_point == "/mnt/with space"
    assert entries[0].fstype == "nfs4"
    assert entries[0].source == "srv:/x"


def test_nfs_share_is_offsite(tmp_path):
    backup_dir = tmp_path / "mnt backups"
    backup_dir.mkdir()
    status = bs.inspect_storage_target(
        str(backup_dir), mountinfo_path=_mountinfo(tmp_path, backup_dir, "nfs4"), local_reference_paths=()
    )
    assert status.is_network_fs and status.offsite
    assert status.source == "nas:/export/n8n"


def test_bind_mount_of_local_disk_is_not_offsite(tmp_path):
    """The share is not mounted on the host: the bind mount exposes ext4."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    status = bs.inspect_storage_target(
        str(backup_dir), mountinfo_path=_mountinfo(tmp_path, backup_dir, "ext4", "/dev/sda1"),
        local_reference_paths=(),
    )
    assert not status.offsite
    assert "not a network share" in status.reason


def test_network_type_on_same_device_as_local_paths_is_not_offsite(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    local_ref = tmp_path / "project"
    local_ref.mkdir()
    status = bs.inspect_storage_target(
        str(backup_dir), mountinfo_path=_mountinfo(tmp_path, backup_dir, "nfs"),
        local_reference_paths=(str(local_ref),),
    )
    assert status.is_network_fs and not status.offsite
    assert str(local_ref) in status.same_device_as


def test_missing_target_is_not_offsite(tmp_path):
    status = bs.inspect_storage_target(str(tmp_path / "nope"))
    assert not status.exists and not status.offsite


# --- storage selection fails closed ---------------------------------------------------

def _config(pref):
    return SimpleNamespace(
        storage_preference=pref, nfs_enabled=True, nfs_storage_path="/mnt/backups",
        primary_storage_path="/", include_public_website=False,
    )


async def test_nfs_only_refuses_local_disk_and_both_falls_back(monkeypatch):
    local = bs.StorageTargetStatus(path="/mnt/backups", exists=True, fstype="ext4", reason="local ext4")
    monkeypatch.setattr(bsvc, "inspect_storage_target", lambda p: local)
    sent = []

    async def fake_notify(path, status, context):
        sent.append((path, context))

    monkeypatch.setattr(bsvc, "notify_storage_unavailable", fake_notify)
    service = bsvc.BackupService(db=None)

    async def cfg_nfs():
        return _config("nfs")

    monkeypatch.setattr(service, "_get_backup_configuration", cfg_nfs)
    with pytest.raises(bs.BackupStorageUnavailableError, match="Refusing to write"):
        await service._get_storage_location()

    async def cfg_both():
        return _config("both")

    monkeypatch.setattr(service, "_get_backup_configuration", cfg_both)
    assert await service._get_storage_location() == "/"
    assert await service._get_storage_location() == "/"
    assert sent == [("/mnt/backups", "backup fell back to local storage")]  # once per service


async def test_nfs_used_when_real_share(monkeypatch):
    real = bs.StorageTargetStatus(path="/mnt/backups", exists=True, fstype="nfs4", is_network_fs=True,
                                  offsite=True)
    monkeypatch.setattr(bsvc, "inspect_storage_target", lambda p: real)
    service = bsvc.BackupService(db=None)

    async def cfg():
        return _config("nfs")

    monkeypatch.setattr(service, "_get_backup_configuration", cfg)
    assert await service._get_storage_location() == "/mnt/backups"


async def test_periodic_check_dispatches_once_per_outage(monkeypatch):
    calls = []

    async def fake_dispatch(event_type, event_data):
        calls.append(event_type)

    import api.services.notification_service as ns

    monkeypatch.setattr(ns, "dispatch_notification", fake_dispatch)

    async def path(_db):
        return "/mnt/backups"

    monkeypatch.setattr(bs, "configured_offsite_path", path)
    state = {"offsite": False}
    monkeypatch.setattr(
        bs, "inspect_storage_target",
        lambda p: bs.StorageTargetStatus(path=p, exists=True, offsite=state["offsite"], reason="r"),
    )

    class _Session:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    import api.database

    monkeypatch.setattr(api.database, "async_session_maker", lambda: _Session())
    monkeypatch.setattr(bs, "_last_check_ok", None)

    await bs.check_backup_storage()
    await bs.check_backup_storage()
    assert calls == ["backup_storage_unavailable"]
    state["offsite"] = True
    await bs.check_backup_storage()
    state["offsite"] = False
    await bs.check_backup_storage()
    assert calls == ["backup_storage_unavailable", "backup_storage_unavailable"]


# --- archive-level (auto) verification -----------------------------------------------

def _archive(tmp_path, dumps=("n8n", "n8n_management"), metadata=True):
    src = tmp_path / "src"
    (src / "databases").mkdir(parents=True)
    for d in dumps:
        (src / "databases" / f"{d}.dump").write_bytes(b"PGDMP fake")
    if metadata:
        (src / "metadata.json").write_text("{}")
    out = tmp_path / "backup.n8n_backup.tar.gz"
    bsvc.BackupService._write_archive(str(src), str(out), None)
    return str(out)


def _fake_run(rc_by_db):
    def run(cmd, **kwargs):
        assert cmd[:2] == ["pg_restore", "--list"]
        db = os.path.basename(cmd[2])[:-len(".dump")]
        rc = rc_by_db.get(db, 0)
        return subprocess.CompletedProcess(cmd, rc, stdout="; toc\n1; 2615 2200 SCHEMA - public\n",
                                           stderr="" if rc == 0 else "pg_restore: error: corrupt")
    return run


def test_archive_inspection_passes_with_listable_dumps(tmp_path, monkeypatch):
    path = _archive(tmp_path)
    monkeypatch.setattr(bsvc.subprocess, "run", _fake_run({}))
    result = bsvc.inspect_backup_archive(path, ["n8n", "n8n_management"])
    assert result["passed"], result["errors"]
    assert result["dumps"]["n8n"]["toc_entries"] == 1


def test_archive_inspection_fails_when_pg_restore_list_fails(tmp_path, monkeypatch):
    path = _archive(tmp_path)
    monkeypatch.setattr(bsvc.subprocess, "run", _fake_run({"n8n_management": 1}))
    result = bsvc.inspect_backup_archive(path, ["n8n", "n8n_management"])
    assert not result["passed"]
    assert any("n8n_management.dump" in e and "exited 1" in e for e in result["errors"])


def test_archive_inspection_fails_on_missing_dump_and_truncation(tmp_path, monkeypatch):
    monkeypatch.setattr(bsvc.subprocess, "run", _fake_run({}))
    path = _archive(tmp_path, dumps=("n8n",))
    result = bsvc.inspect_backup_archive(path, ["n8n", "n8n_management"])
    assert not result["passed"]
    assert "databases/n8n_management.dump missing from archive" in result["errors"]

    data = open(path, "rb").read()
    with open(path, "wb") as f:
        f.write(data[: len(data) // 2])
    result = bsvc.inspect_backup_archive(path, ["n8n"])
    assert not result["passed"]
    assert any("unreadable or truncated" in e for e in result["errors"])


# --- comprehensive verification: pg_restore errors fail -----------------------------

def test_verify_restore_fails_on_pg_restore_error(monkeypatch, tmp_path):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        rc = 1 if "pg_restore" in cmd else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="pg_restore: error: could not execute query")

    monkeypatch.setattr(vs.subprocess, "run", run)
    service = vs.VerificationService(db=None)
    dump = tmp_path / "n8n.dump"
    dump.write_bytes(b"x")
    ok, error = service._restore_dump_into_verify_db(str(dump), "n8n", vs.verify_db_name("n8n"))
    assert not ok
    assert "pg_restore failed (exit 1)" in error
    restore_cmd = next(c for c in calls if "pg_restore" in c)
    assert "--exit-on-error" in restore_cmd and "n8n_verify" in restore_cmd


def test_verify_restore_succeeds_and_uses_separate_databases(monkeypatch, tmp_path):
    seen = []

    def run(cmd, **kwargs):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(vs.subprocess, "run", run)
    service = vs.VerificationService(db=None)
    dump = tmp_path / "d.dump"
    dump.write_bytes(b"x")
    assert service._restore_dump_into_verify_db(str(dump), "n8n_management", "n8n_management_verify") == (True, "")
    assert any('CREATE DATABASE "n8n_management_verify" TEMPLATE template0' in " ".join(c) for c in seen)
    assert vs.verify_db_name("n8n") == vs.VERIFY_DB_NAME
    assert vs.VERIFY_CONTAINER_IMAGE == "pgvector/pgvector:pg16"


def test_workflow_checksum_comparison():
    expected = {
        "a": {"sha256": "1" * 64, "updated_at_ms": 100},
        "b": {"sha256": "2" * 64, "updated_at_ms": 200},
        "c": {"sha256": "3" * 64, "updated_at_ms": 300},
        "d": {"sha256": "4" * 64, "updated_at_ms": 400},
    }
    restored = vs.parse_workflow_checksum_rows(
        f"a\t{'1' * 64}\t100\n"
        f"b\t{'f' * 64}\t200\n"     # same updatedAt, different content: corruption
        f"c\t{'e' * 64}\t999\n"     # saved while the backup ran
    )
    result = vs.compare_workflow_checksums(expected, restored)
    assert not result["passed"]
    assert result["verified"] == 1
    assert result["changed_during_backup"] == ["c"]
    failed = {m["workflow_id"] for m in result["mismatches"]}
    assert failed == {"b", "d"}  # d missing from the restored copy

    ok = vs.compare_workflow_checksums({"a": expected["a"]}, restored)
    assert ok["passed"] and ok["verified"] == 1


def test_workflow_checksum_sql_is_shared():
    """Backup and verification compute the checksum with the same SQL."""
    assert vs.WORKFLOW_CHECKSUM_SQL is bsvc.WORKFLOW_CHECKSUM_SQL
    assert "sha256" in bsvc.WORKFLOW_CHECKSUM_SQL and "updatedAt" in bsvc.WORKFLOW_CHECKSUM_SQL


# --- VerificationSchedule ----------------------------------------------------------------

def _schedule(**kw):
    base = {"enabled": True, "frequency": "weekly", "day_of_week": 0, "hour": 3, "last_run": None,
            "verify_latest_count": 2}
    base.update(kw)
    return SimpleNamespace(**base)


def test_verification_schedule_due():
    monday_3 = datetime(2026, 9, 28, 3, 40, tzinfo=UTC)  # a Monday
    assert vs.verification_schedule_due(_schedule(), monday_3, "UTC")
    assert not vs.verification_schedule_due(_schedule(enabled=False), monday_3, "UTC")
    assert not vs.verification_schedule_due(_schedule(hour=4), monday_3, "UTC")
    assert not vs.verification_schedule_due(_schedule(day_of_week=1), monday_3, "UTC")
    assert vs.verification_schedule_due(_schedule(frequency="daily", day_of_week=5), monday_3, "UTC")
    assert not vs.verification_schedule_due(_schedule(frequency="monthly"), monday_3, "UTC")
    assert vs.verification_schedule_due(
        _schedule(frequency="monthly"), datetime(2026, 10, 1, 3, 40, tzinfo=UTC), "UTC")
    # already ran in this slot
    assert not vs.verification_schedule_due(
        _schedule(last_run=datetime(2026, 9, 28, 3, 0, tzinfo=UTC)), monday_3, "UTC")
    # timezone: 03:40 in Los Angeles is 10:40 UTC
    assert vs.verification_schedule_due(
        _schedule(), datetime(2026, 9, 28, 10, 40, tzinfo=UTC), "America/Los_Angeles")


def test_scheduler_registers_backup_health_job():
    import inspect

    from api.tasks import scheduler

    src = inspect.getsource(scheduler._add_maintenance_jobs)
    assert "_run_backup_health_checks" in src
    body = inspect.getsource(scheduler._run_backup_health_checks)
    assert "run_scheduled_verification" in body and "check_backup_storage" in body


# --- restore container hardening -------------------------------------------------------

async def test_restore_container_has_no_network_label_and_secret_password(monkeypatch):
    from api.services import restore_service as rs

    runs = []

    def run(cmd, **kwargs):
        runs.append((cmd, kwargs))
        out = "cid1\n" if cmd[:3] == ["docker", "ps", "-aq"] else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(rs.subprocess, "run", run)

    async def ready(self, timeout=30):
        raise Exception("never ready")

    monkeypatch.setattr(rs.RestoreService, "_wait_for_postgres_ready", ready)
    service = rs.RestoreService(db=None)
    assert await service.spin_up_restore_container() is False

    create = next((c, k) for c, k in runs if c[:3] == ["docker", "run", "-d"])
    cmd, kwargs = create
    joined = " ".join(cmd)
    assert "--network none" in joined
    assert f"--label {rs.RESTORE_CONTAINER_LABEL}" in joined
    assert "POSTGRES_PASSWORD" in cmd and not any(a.startswith("POSTGRES_PASSWORD=") for a in cmd)
    password = kwargs["env"]["POSTGRES_PASSWORD"]
    assert len(password) >= 24 and password not in joined
    # failed start: removed with its volume
    create_index = runs.index(create)
    assert any(c == ["docker", "rm", "-f", "-v", "cid1"] for c, _ in runs[create_index:])


async def test_startup_cleanup_removes_labelled_and_legacy_containers(monkeypatch):
    from api.services import restore_service as rs

    removed = []

    def run(cmd, **kwargs):
        if cmd[:3] == ["docker", "ps", "-aq"]:
            out = "aaa\n" if "label=" in cmd[-1] else "aaa\nbbb\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        if cmd[:4] == ["docker", "rm", "-f", "-v"]:
            removed.append(cmd[4])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(rs.subprocess, "run", run)
    assert await rs.cleanup_leftover_restore_containers() == 2
    assert removed == ["aaa", "bbb"]


def test_tarfile_helper_rejects_traversal(tmp_path):
    """safe_extract refuses members escaping the destination (Python >= 3.11.4 filters)."""
    import io

    from api.services.backup_archive import safe_extract

    evil = tmp_path / "evil.tar"
    with tarfile.open(evil, "w") as t:
        info = tarfile.TarInfo("../outside.txt")
        info.size = 1
        t.addfile(info, io.BytesIO(b"x"))
    dest = tmp_path / "dest"
    dest.mkdir()
    with tarfile.open(evil) as t:
        if not hasattr(tarfile, "data_filter"):
            pytest.skip("Python without tarfile extraction filters")
        with pytest.raises(tarfile.TarError):
            safe_extract(t, str(dest))
    assert not (tmp_path / "outside.txt").exists()


# --- BackupService.verify_backup (auto-verification) end to end ------------------------

@pytest.fixture
async def backup_db(engine, session_maker):
    import api.models.backups as mb
    from api.database import Base

    tables = [Base.metadata.tables[t.__tablename__] for t in
              (mb.BackupSchedule, mb.BackupHistory, mb.BackupContents, mb.BackupConfiguration)]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    async with session_maker() as session:
        yield session


async def _history(db, path, databases="n8n,n8n_management"):
    from api.models.backups import BackupHistory
    from api.security import hash_file_sha256

    row = BackupHistory(
        backup_type="postgres_full", filename=os.path.basename(path), filepath=path,
        status="success", checksum=hash_file_sha256(path), database_name=databases,
        started_at=datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.mark.parametrize("failing,expected", [({}, "passed"), ({"n8n": 1}, "failed")])
async def test_auto_verification_runs_pg_restore_list(backup_db, tmp_path, monkeypatch, failing, expected):
    path = _archive(tmp_path)
    monkeypatch.setattr(bsvc.subprocess, "run", _fake_run(failing))
    row = await _history(backup_db, path)
    result = await bsvc.BackupService(backup_db).verify_backup(row.id)
    assert result["status"] == expected
    await backup_db.refresh(row)
    assert row.verification_status == expected
    assert row.verification_details["method"] == "archive"
    assert set(row.verification_details["dumps"]) == {"n8n", "n8n_management"}
    if expected == "failed":
        assert "n8n.dump" in result["error"]


async def test_auto_verification_detects_checksum_mismatch(backup_db, tmp_path, monkeypatch):
    path = _archive(tmp_path)
    monkeypatch.setattr(bsvc.subprocess, "run", _fake_run({}))
    row = await _history(backup_db, path)
    with open(path, "ab") as f:
        f.write(b"tamper")
    result = await bsvc.BackupService(backup_db).verify_backup(row.id)
    assert result["status"] == "failed" and result["error"] == "Checksum mismatch"
