"""
Backup/restore review fixes:

* the archived project tree contains every build context the stack's
  compose files and Dockerfiles need (docs/ for the management image);
* the project tree is bounded (exclusions, total cap) and keeps ownership;
* storage probes cannot freeze the event loop on a hung NFS mount;
* permission tightening only touches the backup system's own files;
* volume snapshots never contain dangling hard links;
* safety dumps are encrypted when a passphrase is configured;
* restoring .env keeps BACKUP_ENCRYPTION_PASSPHRASE;
* workflow checksum comparison and the snapshot-consistent dump;
* restore subprocesses die with a cancelled job; stale partials are swept;
* the management container refuses to recreate itself.
"""

from __future__ import annotations

import asyncio
import glob
import io
import os
import re
import shutil
import stat
import subprocess
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from api.services import backup_archive as ba
from api.services import backup_service as bsvc
from api.services import backup_storage as bs
from api.services import restore_service as rs
from api.services import stack_inventory as inv
from api.services import verification_service as vs

REPO_ROOT = Path(__file__).resolve().parents[2]
PASSPHRASE = "correct horse battery staple"
needs_gpg = pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")
needs_root = pytest.mark.skipif(os.geteuid() != 0, reason="needs root to chown")


@pytest.fixture(autouse=True)
def _no_host_env(monkeypatch, tmp_path):
    monkeypatch.delenv(ba.PASSPHRASE_ENV_KEY, raising=False)
    monkeypatch.setattr(ba, "HOST_ENV_PATH", str(tmp_path / "no.env"))


# --- H1: build contexts ------------------------------------------------------------------

def _build_specs_from_text(text: str):
    """
    (context, dockerfile, {name: additional context}) for every `build:` in a
    compose file or in setup.sh's compose heredocs (same YAML shape).
    """
    specs = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)build:\s*(\S.*)?$", lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1))
        if m.group(2):
            specs.append((m.group(2).strip().strip("'\""), "Dockerfile", {}))
            i += 1
            continue
        context, dockerfile, extra = ".", "Dockerfile", {}
        i += 1
        in_extra = None
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            cur = len(line) - len(line.lstrip())
            if cur <= indent:
                break
            kv = re.match(r"^\s*([\w.-]+):\s*(.*)$", line)
            if kv:
                key, value = kv.group(1), kv.group(2).strip().strip("'\"")
                if in_extra is not None and cur > in_extra:
                    extra[key] = value
                elif key == "context":
                    context, in_extra = value, None
                elif key == "dockerfile":
                    dockerfile, in_extra = value, None
                elif key == "additional_contexts":
                    in_extra = cur
                else:
                    in_extra = None
            i += 1
        specs.append((context, dockerfile, extra))
    return specs


def _stage_names(dockerfile_text: str) -> set:
    return {m.group(1) for m in re.finditer(r"(?im)^FROM\s+\S+\s+AS\s+(\S+)", dockerfile_text)}


def _copy_sources(dockerfile_text: str):
    """(from_name or None, [source paths]) for every COPY/ADD instruction."""
    out = []
    for m in re.finditer(r"(?im)^(?:COPY|ADD)\s+(.+)$", dockerfile_text):
        parts = m.group(1).split()
        from_name = None
        args = []
        for p in parts:
            if p.startswith("--from="):
                from_name = p.split("=", 1)[1]
            elif p.startswith("--"):
                continue
            else:
                args.append(p)
        out.append((from_name, args[:-1]))
    return out


def test_compose_build_specs_parse_like_yaml():
    """The light parser agrees with a real YAML parse of docker-compose.yaml."""
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yaml").read_text())
    from_yaml = []
    for svc in compose["services"].values():
        build = svc.get("build")
        if build is None:
            continue
        if isinstance(build, str):
            from_yaml.append((build, "Dockerfile", {}))
        else:
            from_yaml.append((build.get("context", "."), build.get("dockerfile", "Dockerfile"),
                              dict(build.get("additional_contexts") or {})))
    parsed = _build_specs_from_text((REPO_ROOT / "docker-compose.yaml").read_text())
    assert sorted(map(repr, parsed)) == sorted(map(repr, from_yaml))
    assert any(extra.get("docs_src") == "." for _, _, extra in parsed)


def test_archived_project_tree_contains_every_build_context(tmp_path):
    dest = tmp_path / "project"
    count, skipped = inv.copy_project_tree(str(dest), str(REPO_ROOT))
    assert count > 0

    specs = _build_specs_from_text((REPO_ROOT / "docker-compose.yaml").read_text())
    specs += _build_specs_from_text((REPO_ROOT / "setup.sh").read_text())
    assert any(ctx == "./management" for ctx, _, _ in specs)
    checked_from = 0
    for context, dockerfile, extra in specs:
        ctx_dir = dest / context
        assert ctx_dir.is_dir(), f"build context {context} missing from the archived project tree"
        df = ctx_dir / dockerfile
        assert df.is_file(), f"{context}/{dockerfile} missing from the archived project tree"
        for name, path in extra.items():
            assert (dest / path).is_dir(), f"additional context {name}={path} missing"
        text = df.read_text()
        stages = _stage_names(text)
        for from_name, sources in _copy_sources(text):
            if from_name in stages:
                continue
            base = dest / extra[from_name] if from_name else ctx_dir
            if from_name and from_name not in extra:
                continue  # an image reference
            for src in sources:
                matches = glob.glob(str(base / src))
                assert matches, f"{dockerfile} in {context}: COPY source {src} (from {from_name}) missing"
                if from_name:
                    checked_from += 1
    assert checked_from >= 3  # docs/requirements.txt, mkdocs.yml, docs
    assert (dest / "docs" / "requirements.txt").is_file() and (dest / "mkdocs.yml").is_file()


def test_real_project_tree_fits_the_default_cap():
    scan = inv.scan_project_tree(str(REPO_ROOT))
    assert 0 < scan["total_bytes"] < inv.PROJECT_MAX_TOTAL_DEFAULT_MB * 1024 * 1024


# --- M3 / L3: project tree bounds and ownership --------------------------------------------

def test_project_tree_total_cap_fails_loudly(tmp_path, monkeypatch):
    src = tmp_path / "src"
    (src / "big").mkdir(parents=True)
    for i in range(3):
        (src / "big" / f"f{i}").write_bytes(b"x" * 600_000)
    (src / ".env").write_text("A=1")
    monkeypatch.setenv("BACKUP_PROJECT_MAX_MB", "1")
    with pytest.raises(inv.ProjectTreeTooLargeError, match="big"):
        inv.copy_project_tree(str(tmp_path / "out"), str(src))
    with pytest.raises(inv.ProjectTreeTooLargeError, match="BACKUP_PROJECT_MAX_MB"):
        inv.check_project_tree_size(str(src))
    monkeypatch.setenv("BACKUP_PROJECT_MAX_MB", "5")
    assert inv.check_project_tree_size(str(src)) == 3 * 600_000 + 3
    count, _ = inv.copy_project_tree(str(tmp_path / "out2"), str(src))
    assert count == 4


async def test_stack_inventory_propagates_the_cap(monkeypatch, tmp_path):
    def too_big(dest):
        raise inv.ProjectTreeTooLargeError("too big")

    monkeypatch.setattr(inv, "copy_project_tree", too_big)
    with pytest.raises(inv.ProjectTreeTooLargeError):
        await bsvc.BackupService(db=None)._add_stack_inventory(str(tmp_path), {})


@needs_root
def test_project_tree_keeps_ownership(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    f = src / "sub" / "conf"
    f.write_text("x")
    os.chown(f, 1234, 2345)
    os.chown(src / "sub", 1234, 2345)
    os.symlink("conf", src / "sub" / "link")
    os.lchown(src / "sub" / "link", 1234, 2345)
    dest = tmp_path / "out"
    inv.copy_project_tree(str(dest), str(src))
    for rel in ("sub", "sub/conf", "sub/link"):
        st = os.lstat(dest / rel)
        assert (st.st_uid, st.st_gid) == (1234, 2345), rel


async def test_free_space_estimate_counts_project_and_volumes(monkeypatch, tmp_path):
    service = bsvc.BackupService(db=None)

    async def location():
        return str(tmp_path)

    async def last(_t):
        return 0

    monkeypatch.setattr(service, "_get_storage_location", location)
    monkeypatch.setattr(service, "_estimate_backup_size", last)
    monkeypatch.setattr(bsvc, "_backup_min_free_bytes", lambda: 0)
    monkeypatch.setattr(inv, "check_project_tree_size", lambda: 100 * 1024**2)
    monkeypatch.setattr(inv, "estimate_snapshot_bytes", lambda: 50 * 1024**2)
    free = 300 * 1024**2  # archive 150 + staging 150 + 100 + 2 x 50 = 500 MiB needed (same disk)
    monkeypatch.setattr(bsvc.os, "statvfs", lambda p: SimpleNamespace(f_bavail=free, f_frsize=1))
    with pytest.raises(bsvc.InsufficientBackupSpaceError, match="project files 100 MiB"):
        await service._check_free_space_for_backup("postgres_full")
    free = 600 * 1024**2
    await service._check_free_space_for_backup("postgres_full")


# --- M1: storage probe with a deadline ---------------------------------------------------

async def test_hung_storage_probe_times_out_without_blocking(monkeypatch):
    calls = []

    def hang(path, **kwargs):
        calls.append(path)
        time.sleep(1.5)
        return bs.StorageTargetStatus(path=path, exists=True, offsite=True)

    monkeypatch.setattr(bs, "inspect_storage_target", hang)
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    t = asyncio.create_task(ticker())
    start = time.monotonic()
    first, second = await asyncio.gather(
        bs.inspect_storage_target_async("/mnt/hung", timeout=0.3),
        bs.inspect_storage_target_async("/mnt/hung", timeout=0.3),
    )
    elapsed = time.monotonic() - start
    assert first.timed_out and not first.offsite and "did not respond" in first.reason
    assert second.timed_out
    assert elapsed < 1.0 and ticks >= 10
    assert bs.probe_in_flight("/mnt/hung")
    # still hung: a new call joins the in-flight probe instead of starting another thread
    third = await bs.inspect_storage_target_async("/mnt/hung", timeout=0.1)
    assert third.timed_out and calls == ["/mnt/hung"]
    t.cancel()
    await asyncio.sleep(1.6)
    assert not bs.probe_in_flight("/mnt/hung")
    ok = await bs.inspect_storage_target_async("/mnt/hung", timeout=3)
    assert ok.offsite and calls == ["/mnt/hung", "/mnt/hung"]


async def test_backup_falls_back_when_nfs_probe_hangs(monkeypatch):
    monkeypatch.setattr(bs, "STORAGE_PROBE_TIMEOUT", 0.2)
    monkeypatch.setattr(bs, "inspect_storage_target", lambda p, **k: time.sleep(1) or bs.StorageTargetStatus(path=p))

    async def no_notify(*a, **k):
        return None

    monkeypatch.setattr(bsvc, "notify_storage_unavailable", no_notify)
    service = bsvc.BackupService(db=None)

    async def cfg():
        return SimpleNamespace(storage_preference="both", nfs_enabled=True, nfs_storage_path="/mnt/hang2",
                               primary_storage_path="/", include_public_website=False)

    monkeypatch.setattr(service, "_get_backup_configuration", cfg)
    start = time.monotonic()
    assert await service._get_storage_location() == "/"
    assert time.monotonic() - start < 0.9


# --- M2: tightening only touches our files -----------------------------------------------

def test_tighten_leaves_root_and_unrelated_files_alone(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    os.chmod(root, 0o755)
    unrelated = root / "someone_elses.txt"
    unrelated.write_text("x")
    os.chmod(unrelated, 0o644)
    (root / "other_app").mkdir()
    other = root / "other_app" / "backup_x.n8n_backup.tar.gz"
    other.write_text("x")
    os.chmod(other, 0o644)
    full = root / "postgres_full"
    full.mkdir()
    os.chmod(full, 0o755)
    ours = full / "backup_20260101T000000Z_7.n8n_backup.tar.gz.gpg"
    ours.write_text("x")
    legacy = full / "postgres_full_20250101_120000.sql.gz"
    legacy.write_text("x")
    notes = full / "README.txt"
    notes.write_text("x")
    pre = root / "pre_restore"
    pre.mkdir()
    safety = pre / "n8n_pre_restore_20260101_120000.dump"
    safety.write_text("x")
    for p in (ours, legacy, notes, safety):
        os.chmod(p, 0o644)

    assert ba.tighten_backup_tree(str(root)) == 5  # both owned dirs, the archive, the legacy dump, the safety dump
    mode = lambda p: stat.S_IMODE(os.stat(p).st_mode)  # noqa: E731
    assert mode(root) == 0o755 and mode(unrelated) == 0o644 and mode(other) == 0o644
    assert mode(notes) == 0o644
    assert mode(full) == 0o700 and mode(ours) == 0o600 and mode(legacy) == 0o600 and mode(safety) == 0o600


def test_tighten_runs_once_per_root(tmp_path):
    full = tmp_path / "postgres_full"
    full.mkdir()
    a = full / "backup_1.n8n_backup.tar.gz"
    a.write_text("x")
    os.chmod(a, 0o644)
    assert ba.tighten_backup_tree_once(str(tmp_path)) >= 1
    b = full / "backup_2.n8n_backup.tar.gz"
    b.write_text("x")
    os.chmod(b, 0o644)
    assert ba.tighten_backup_tree_once(str(tmp_path)) == 0
    assert stat.S_IMODE(os.stat(b).st_mode) == 0o644


def test_owned_subdirs_match_backup_types():
    from api.schemas.backups import BackupType

    assert set(ba.OWNED_BACKUP_SUBDIRS) == {t.value for t in BackupType} | {"pre_restore"}


# --- L1: hard links in volume snapshots --------------------------------------------------

def _raw_snapshot_with_hardlinks(path):
    with tarfile.open(path, "w") as t:
        d = tarfile.TarInfo(".n8n")
        d.type = tarfile.DIRTYPE
        t.addfile(d)
        for name, data in ((".n8n/.cache/blob", b"cached-data"), (".n8n/config", b"{}")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        for name, target in ((".n8n/nodes/blob", ".n8n/.cache/blob"),
                             (".n8n/config.link", ".n8n/config"),
                             (".n8n/orphan", ".n8n/not-there")):
            link = tarfile.TarInfo(name)
            link.type = tarfile.LNKTYPE
            link.linkname = target
            t.addfile(link)


def test_hardlink_to_excluded_member_becomes_a_file(tmp_path):
    raw = tmp_path / "raw.tar"
    _raw_snapshot_with_hardlinks(raw)
    out = tmp_path / "n8n_data.tar"
    count = inv._rewrite_snapshot(str(raw), str(out), (".cache",))
    with tarfile.open(out) as t:
        members = {m.name: m for m in t.getmembers()}
        assert set(members) == {"config", "nodes/blob", "config.link"}
        assert members["nodes/blob"].isfile()
        assert t.extractfile("nodes/blob").read() == b"cached-data"
        assert members["config.link"].islnk() and members["config.link"].linkname == "config"
    assert count == 2
    if shutil.which("tar"):
        dest = tmp_path / "x"
        dest.mkdir()
        subprocess.run(["tar", "-xpf", str(out), "-C", str(dest)], check=True)
        assert (dest / "nodes" / "blob").read_bytes() == b"cached-data"
        assert os.stat(dest / "config").st_ino == os.stat(dest / "config.link").st_ino


# --- L2: encrypted safety dump ------------------------------------------------------------

async def _safety_dump_run(monkeypatch, tmp_path):
    service = rs.RestoreService(db=None)
    seen = []

    async def fake_run(cmd, env=None, timeout=0):
        seen.append(cmd)
        if cmd[:2] == ["pg_restore", "--list"]:
            return 0, "", ""
        if cmd[0] == "pg_dump":
            out = cmd[cmd.index("-f") + 1]
            Path(out).write_bytes(b"PGDMP live data")
            return 0, "", ""
        return 1, "", "stop here"  # pg_restore into the temp db: end the test run

    async def exists(name):
        return name == "n8n"

    async def psql(sql, database="postgres"):
        return 0, "", ""

    monkeypatch.setattr(rs, "_run_subprocess", fake_run)
    monkeypatch.setattr(service, "_database_exists", exists)
    monkeypatch.setattr(service, "_psql", psql)
    dump = tmp_path / "in.dump"
    dump.write_bytes(b"PGDMP")
    result = await service._restore_n8n_database_from_dump(str(dump), "n8n", str(tmp_path / "pre_restore"))
    return result, seen


@needs_gpg
async def test_safety_dump_is_encrypted_with_passphrase(monkeypatch, tmp_path):
    monkeypatch.setenv(ba.PASSPHRASE_ENV_KEY, PASSPHRASE)
    result, seen = await _safety_dump_run(monkeypatch, tmp_path)
    safety = result["safety_dump"]
    assert safety.endswith(".dump.gpg") and result["safety_dump_encrypted"]
    assert b"PGDMP" not in Path(safety).read_bytes()
    assert stat.S_IMODE(os.stat(safety).st_mode) == 0o600
    dump_target = next(c for c in seen if c[0] == "pg_dump")
    plain = dump_target[dump_target.index("-f") + 1]
    assert not plain.startswith(str(tmp_path / "pre_restore")) and not os.path.exists(plain)
    assert os.listdir(tmp_path / "pre_restore") == [os.path.basename(safety)]
    out = tmp_path / "decrypted.dump"
    ba.decrypt_file(safety, str(out), PASSPHRASE)
    assert out.read_bytes() == b"PGDMP live data"
    # the documented manual decrypt works too
    proc = subprocess.run(
        ["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", PASSPHRASE,
         "--homedir", str(tmp_path), "--decrypt", safety],
        capture_output=True,
    )
    assert proc.returncode == 0 and proc.stdout == b"PGDMP live data"


async def test_safety_dump_plain_without_passphrase(monkeypatch, tmp_path):
    result, _ = await _safety_dump_run(monkeypatch, tmp_path)
    assert result["safety_dump"].endswith(".dump") and not result["safety_dump_encrypted"]
    assert Path(result["safety_dump"]).read_bytes() == b"PGDMP live data"


# --- L6: .env restore keeps the passphrase -------------------------------------------------

def _restore_env(tmp_path, current: str, restored: str):
    extracted = tmp_path / "extract"
    (extracted / "config").mkdir(parents=True)
    (extracted / "config" / ".env").write_text(restored)
    target = tmp_path / "project" / ".env"
    target.parent.mkdir(exist_ok=True)
    target.write_text(current)
    result = rs.RestoreService(db=None)._restore_config_from_dir(
        str(extracted), "config/.env", target_path=str(target), create_backup=False
    )
    return result, target.read_text()


def test_env_restore_keeps_current_passphrase(tmp_path):
    result, text = _restore_env(
        tmp_path, f"A=1\nBACKUP_ENCRYPTION_PASSPHRASE='{PASSPHRASE}'\n", "A=old\nB=2"
    )
    assert result["status"] == "success"
    assert text == f"A=old\nB=2\nBACKUP_ENCRYPTION_PASSPHRASE='{PASSPHRASE}'\n"
    assert "kept" in result["warnings"][0] and "kept" in result["message"]


def test_env_restore_warns_on_different_passphrase(tmp_path):
    result, text = _restore_env(
        tmp_path, f"BACKUP_ENCRYPTION_PASSPHRASE={PASSPHRASE.replace(' ', '')}\n",
        "BACKUP_ENCRYPTION_PASSPHRASE=another-long-passphrase\n",
    )
    assert text == "BACKUP_ENCRYPTION_PASSPHRASE=another-long-passphrase\n"
    assert "different" in result["warnings"][0]


def test_env_restore_without_passphrase_anywhere_is_unchanged(tmp_path):
    result, text = _restore_env(tmp_path, "A=1\n", "A=2\n")
    assert text == "A=2\n" and "warnings" not in result


# --- L7: workflow checksums ----------------------------------------------------------------

def test_missing_workflow_is_changed_during_backup_unless_same_snapshot():
    expected = {"a": {"sha256": "1" * 64, "updated_at_ms": 1}, "d": {"sha256": "4" * 64, "updated_at_ms": 4}}
    restored = {"a": {"sha256": "1" * 64, "updated_at_ms": 1}}
    loose = vs.compare_workflow_checksums(expected, restored)
    assert loose["passed"] and loose["changed_during_backup"] == ["d"]
    strict = vs.compare_workflow_checksums(expected, restored, same_snapshot=True)
    assert not strict["passed"] and strict["mismatches"][0]["workflow_id"] == "d"
    saved = {"a": {"sha256": "f" * 64, "updated_at_ms": 9}}
    assert not vs.compare_workflow_checksums({"a": expected["a"]}, saved, same_snapshot=True)["passed"]


async def test_pg_dump_uses_snapshot_and_falls_back(monkeypatch, tmp_path):
    calls = []

    async def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if any(c.startswith("--snapshot=") for c in cmd):
            return subprocess.CompletedProcess(cmd, 1, b"", b"invalid snapshot identifier")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(bsvc._proc, "run", fake_run)
    service = bsvc.BackupService(db=None)
    assert await service._execute_pg_dump_to_file("n8n", str(tmp_path / "x"), snapshot="0000-1") is False
    assert "--snapshot=0000-1" in calls[0] and not any(c.startswith("--snapshot") for c in calls[1])

    calls.clear()

    async def ok_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(bsvc._proc, "run", ok_run)
    assert await service._execute_pg_dump_to_file("n8n", str(tmp_path / "x"), snapshot="0000-1") is True
    assert len(calls) == 1
    assert await service._execute_pg_dump_to_file("n8n", str(tmp_path / "x")) is False


async def test_snapshot_context_falls_back_without_postgres(monkeypatch):
    service = bsvc.BackupService(db=None)

    async def checksums(_db):
        return {"w": {"sha256": "s", "updated_at_ms": 1}}

    monkeypatch.setattr(service, "capture_workflow_checksums", checksums)
    async with service._n8n_dump_snapshot(SimpleNamespace(bind=None), True) as (snap, sums):
        assert snap is None and sums == {"w": {"sha256": "s", "updated_at_ms": 1}}
    async with service._n8n_dump_snapshot(None, False) as (snap, sums):
        assert snap is None and sums == {}


# --- L8: subprocess cancellation and stale partials ----------------------------------------

async def test_restore_subprocess_killed_on_cancel(tmp_path):
    pidfile = tmp_path / "pid"
    task = asyncio.create_task(rs._run_subprocess(
        ["sh", "-c", f"echo $$ > {pidfile}; exec sleep 30"], timeout=60
    ))
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        await asyncio.sleep(0.02)
    pid = int(pidfile.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    def alive():
        try:
            with open(f"/proc/{pid}/status") as f:
                return "\nState:\tZ" not in f.read()
        except FileNotFoundError:
            return False

    for _ in range(100):
        if not alive():
            break
        await asyncio.sleep(0.02)
    assert not alive()


async def test_restore_subprocess_timeout_returns_minus_one():
    rc, _, err = await rs._run_subprocess(["sleep", "5"], timeout=0.2)
    assert rc == -1 and "timed out" in err


def test_sweep_stale_partials(tmp_path):
    full = tmp_path / "postgres_full"
    full.mkdir()
    old = full / "backup_1.n8n_backup.tar.gz.gpg.partial"
    fresh = full / "backup_2.n8n_backup.tar.gz.partial"
    foreign = full / "something.partial"
    for p in (old, fresh, foreign):
        p.write_text("x")
    ancient = time.time() - 10 * 3600
    os.utime(old, (ancient, ancient))
    os.utime(foreign, (ancient, ancient))
    assert ba.sweep_stale_partials([str(tmp_path)], max_age_seconds=6 * 3600) == 1
    assert not old.exists() and fresh.exists() and foreign.exists()


def test_sweep_stale_temp_dirs(tmp_path):
    stale = tmp_path / "n8n_backup_stage_abc"
    stale.mkdir()
    (stale / "dump").write_text("x")
    fresh = tmp_path / "n8n_backup_stage_new"
    fresh.mkdir()
    other = tmp_path / "unrelated_dir"
    other.mkdir()
    ancient = time.time() - 10 * 3600
    for p in (stale, other):
        os.utime(p, (ancient, ancient))
    assert bsvc._sweep_stale_temp_dirs(6 * 3600, str(tmp_path)) == 1
    assert not stale.exists() and fresh.exists() and other.exists()


# --- management container cannot recreate itself ---------------------------------------

async def test_management_container_refuses_to_recreate_itself(monkeypatch):
    from api.services import compose_cli, container_service

    async def never(*a, **k):
        raise AssertionError("compose must not run")

    monkeypatch.setattr(compose_cli, "run_compose", never)
    monkeypatch.setattr(container_service.ContainerService, "_get_service_name_from_container",
                        lambda self, name: "n8n_management")
    with pytest.raises(ValueError, match="cannot recreate itself"):
        await container_service.ContainerService().recreate_container("n8n_management")
