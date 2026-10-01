"""
Backup archive confidentiality and completeness (audit H-5, H-6):

* archives, their directories, safety dumps are owner-only;
* optional gpg encryption round-trips through every reader;
* the bare-metal inventory (project tree, volume snapshots, project name)
  is collected the way restore.sh expects it.
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import subprocess
import tarfile

import pytest

from api.services import backup_archive as ba
from api.services import stack_inventory as inv
from api.services.backup_service import BackupService

PASSPHRASE = "correct horse battery staple"
needs_gpg = pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")


def _mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture(autouse=True)
def _no_host_env(monkeypatch, tmp_path):
    """No passphrase from the developer's environment or a real .env."""
    monkeypatch.delenv(ba.PASSPHRASE_ENV_KEY, raising=False)
    monkeypatch.setattr(ba, "HOST_ENV_PATH", str(tmp_path / "no.env"))


def _staging(tmp_path):
    src = tmp_path / "staging"
    (src / "config").mkdir(parents=True)
    (src / "config" / ".env").write_text("N8N_ENCRYPTION_KEY=secret\n")
    (src / "databases").mkdir()
    (src / "databases" / "n8n.dump").write_bytes(b"PGDMP" + os.urandom(2048))
    (src / "metadata.json").write_text("{}")
    return src


# --- permissions ---------------------------------------------------------------

def test_private_dir_and_file_modes(tmp_path):
    old = os.umask(0o022)
    try:
        d = ba.make_private_dir(str(tmp_path / "a" / "b"))
        assert _mode(d) == 0o700
        with ba.open_private_file(os.path.join(d, "f")) as f:
            f.write(b"x")
        assert _mode(os.path.join(d, "f")) == 0o600
        with pytest.raises(FileExistsError):
            ba.open_private_file(os.path.join(d, "f"))
    finally:
        os.umask(old)


def test_tighten_backup_tree_fixes_old_world_readable_archives(tmp_path):
    root = tmp_path / "backups"
    (root / "postgres_full").mkdir(parents=True)
    old_archive = root / "postgres_full" / "backup_1.n8n_backup.tar.gz"
    old_archive.write_bytes(b"x")
    os.chmod(old_archive, 0o644)
    os.chmod(root / "postgres_full", 0o755)
    assert ba.tighten_backup_tree(str(root)) >= 2
    assert _mode(old_archive) == 0o600
    assert _mode(root / "postgres_full") == 0o700
    assert ba.tighten_backup_tree(str(root)) == 0


def test_unencrypted_archive_is_0600_and_atomic(tmp_path):
    old = os.umask(0o022)
    try:
        out = tmp_path / "backup.n8n_backup.tar.gz"
        BackupService._write_archive(str(_staging(tmp_path)), str(out), None)
    finally:
        os.umask(old)
    assert _mode(out) == 0o600
    assert not (tmp_path / "backup.n8n_backup.tar.gz.partial").exists()
    assert not ba.is_encrypted_archive(str(out))
    with ba.open_backup_archive(str(out)) as tar:
        assert "config/.env" in tar.getnames()


def test_failed_archive_write_leaves_no_partial(tmp_path, monkeypatch):
    out = tmp_path / "backup.n8n_backup.tar.gz"

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(tarfile.TarFile, "add", boom)
    with pytest.raises(OSError):
        BackupService._write_archive(str(_staging(tmp_path)), str(out), None)
    assert not out.exists()
    assert not (tmp_path / "backup.n8n_backup.tar.gz.partial").exists()


# --- passphrase ----------------------------------------------------------------

def test_passphrase_from_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(f'{ba.PASSPHRASE_ENV_KEY}="{PASSPHRASE}"\n')
    monkeypatch.setattr(ba, "HOST_ENV_PATH", str(env))
    assert ba.get_encryption_passphrase(str(env)) == PASSPHRASE


def test_passphrase_unset_means_no_encryption():
    assert ba.get_encryption_passphrase() is None
    assert ba.encryption_enabled() is False


def test_short_passphrase_is_refused(monkeypatch):
    monkeypatch.setenv(ba.PASSPHRASE_ENV_KEY, "short")
    with pytest.raises(ba.BackupEncryptionError):
        ba.get_encryption_passphrase()


# --- encryption round trip (real gpg) -------------------------------------------

@needs_gpg
def test_encrypted_archive_round_trip(tmp_path, monkeypatch):
    out = tmp_path / "backup.n8n_backup.tar.gz.gpg"
    BackupService._write_archive(str(_staging(tmp_path)), str(out), PASSPHRASE)
    assert _mode(out) == 0o600
    raw = out.read_bytes()
    assert not raw.startswith(b"\x1f\x8b")
    assert b"N8N_ENCRYPTION_KEY" not in raw
    assert ba.is_encrypted_archive(str(out))

    # Readers decrypt transparently with the configured passphrase
    monkeypatch.setenv(ba.PASSPHRASE_ENV_KEY, PASSPHRASE)
    with ba.open_backup_archive(str(out)) as tar:
        env = tar.extractfile("config/.env").read()
    assert env == b"N8N_ENCRYPTION_KEY=secret\n"

    # ... including the in-app restore extraction path
    from api.services.restore_service import _extract_tar_sync

    dest = tmp_path / "x"
    dest.mkdir()
    _extract_tar_sync(str(out), str(dest))
    assert (dest / "databases" / "n8n.dump").exists()

    # The documented operator command works on the file as written
    plain = subprocess.run(
        ["gpg", "--homedir", str(tmp_path), "--batch", "--quiet", "--pinentry-mode", "loopback",
         "--passphrase-fd", "0", "--decrypt", str(out)],
        input=PASSPHRASE.encode() + b"\n", capture_output=True, check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as tar:
        assert "metadata.json" in tar.getnames()


@needs_gpg
def test_wrong_or_missing_passphrase_fails_clearly(tmp_path, monkeypatch):
    out = tmp_path / "backup.n8n_backup.tar.gz.gpg"
    BackupService._write_archive(str(_staging(tmp_path)), str(out), PASSPHRASE)

    with pytest.raises(ba.BackupEncryptionError, match="not set"):
        with ba.open_backup_archive(str(out)):
            pass

    monkeypatch.setenv(ba.PASSPHRASE_ENV_KEY, "a completely different passphrase")
    with pytest.raises(ba.BackupEncryptionError, match="decryption failed"):
        with ba.open_backup_archive(str(out)):
            pass
    leftovers = [p for p in os.listdir(tmp_path) if p.startswith("n8n_backup_plain_")]
    assert leftovers == []


@needs_gpg
def test_tampered_ciphertext_is_rejected(tmp_path, monkeypatch):
    out = tmp_path / "backup.n8n_backup.tar.gz.gpg"
    BackupService._write_archive(str(_staging(tmp_path)), str(out), PASSPHRASE)
    data = bytearray(out.read_bytes())
    data[len(data) // 2] ^= 0xFF
    out.write_bytes(bytes(data))
    monkeypatch.setenv(ba.PASSPHRASE_ENV_KEY, PASSPHRASE)
    with pytest.raises(ba.BackupEncryptionError):
        with ba.open_backup_archive(str(out)):
            pass


# --- bare-metal inventory (H-6) -------------------------------------------------

def test_project_tree_copies_bind_mounted_configs_and_skips_noise(tmp_path):
    src = tmp_path / "project"
    files = {
        ".env": "A=1",
        "docker-compose.yaml": "services: {}",
        "nginx-router.conf": "x",
        "nginx-public.conf": "x",
        ".filebrowser.json": "{}",
        "ntfy/server.yml": "x",
        "dozzle/users.yml": "x",
        "scripts/certbot/renew-loop.sh": "x",
        "management/Dockerfile": "x",
        "management/frontend/node_modules/pkg/index.js": "x",
        "management/frontend/dist/app.js": "x",
        ".git/HEAD": "ref: refs/heads/main",
        "docs/index.md": "x",
        "docs/requirements.txt": "mkdocs",
        "mkdocs.yml": "site_name: x",
        "site/index.html": "x",
        ".claude/worktrees/agent/.env": "COPY=1",
        "n8n_status/vendor/.git/HEAD": "x",
        "backup_20260101T000000Z_1.n8n_backup.tar.gz": "x",
        "dl/backup_20260101T000000Z_2.n8n_backup.tar.gz.gpg": "x",
        "x.partial": "x",
        "nginx.conf.bak.20260101": "x",
    }
    for rel, content in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(content)
    os.symlink("nginx-router.conf", src / "link.conf")

    dest = tmp_path / "out"
    count, skipped = inv.copy_project_tree(str(dest), str(src))
    copied = {str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file() or p.is_symlink()}
    for rel in (".env", "nginx-router.conf", "nginx-public.conf", ".filebrowser.json", "ntfy/server.yml",
                "dozzle/users.yml", "scripts/certbot/renew-loop.sh", "management/Dockerfile", "link.conf",
                "docs/index.md", "docs/requirements.txt", "mkdocs.yml"):
        assert rel in copied
    assert os.path.islink(dest / "link.conf")
    assert copied == {
        ".env", "nginx-router.conf", "nginx-public.conf", ".filebrowser.json", "ntfy/server.yml",
        "dozzle/users.yml", "scripts/certbot/renew-loop.sh", "management/Dockerfile", "link.conf",
        "docs/index.md", "docs/requirements.txt", "mkdocs.yml", "docker-compose.yaml",
    }
    assert count == len(copied) and skipped == []


def test_read_git_commit(tmp_path):
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (git / "refs" / "heads" / "main").write_text("abc123\n")
    assert inv.read_git_commit(str(tmp_path)) == "abc123"
    (git / "refs" / "heads" / "main").unlink()
    (git / "packed-refs").write_text("# pack-refs\ndef456 refs/heads/main\n")
    assert inv.read_git_commit(str(tmp_path)) == "def456"


def test_project_name_normalisation_matches_compose():
    assert inv.normalize_project_name("N8N Nginx.prod") == "n8nnginxprod"
    assert inv.normalize_project_name("n8n_nginx-1") == "n8n_nginx-1"


def test_volume_snapshot_is_rewritten_relative_to_volume_root(tmp_path):
    raw = tmp_path / "raw.tar"
    with tarfile.open(raw, "w") as t:
        for name, data in ((".n8n/config", b'{"encryptionKey":"k"}'),
                           (".n8n/binaryData/a.bin", b"bin"),
                           (".n8n/.cache/x", b"c"),
                           (".n8n/n8nEventLog.log", b"log")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.uid = 1000
            t.addfile(info, io.BytesIO(data))
        d = tarfile.TarInfo(".n8n")
        d.type = tarfile.DIRTYPE
        t.addfile(d)
    out = tmp_path / "n8n_data.tar"
    count = inv._rewrite_snapshot(str(raw), str(out), (".cache", "n8nEventLog"))
    with tarfile.open(out) as t:
        names = t.getnames()
        assert t.getmember("config").uid == 1000
    assert sorted(names) == ["binaryData/a.bin", "config"]
    assert count == 2


class _FakeContainer:
    def __init__(self, name, service, project, mounts=(), image_ref="", digests=()):
        self.name = name
        self.labels = {"com.docker.compose.project": project, "com.docker.compose.service": service}
        self.attrs = {"Config": {"Image": image_ref}, "Image": f"sha256:{service}", "Mounts": list(mounts)}
        self.image = type("I", (), {"attrs": {"RepoDigests": list(digests)}})()

    def get_archive(self, path):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as t:
            info = tarfile.TarInfo(os.path.basename(path) + "/config")
            info.size = 2
            t.addfile(info, io.BytesIO(b"{}"))
        return iter([buf.getvalue()]), {}


class _FakeClient:
    def __init__(self, containers):
        self._containers = containers
        self.containers = self

    def list(self, all=False, filters=None):  # noqa: A002
        return self._containers


def test_images_and_volume_snapshots_from_docker(tmp_path):
    n8n = _FakeContainer(
        "n8n", "n8n", "proj",
        mounts=[{"Type": "volume", "Name": "proj_n8n_data", "Destination": "/home/node/.n8n"}],
        image_ref="n8nio/n8n:latest", digests=["n8nio/n8n@sha256:abc"],
    )
    mgmt = _FakeContainer("n8n_management", "n8n_management", "proj", image_ref="rjsears/n8n_management:latest")
    client = _FakeClient([n8n, mgmt])

    images = {i["service"]: i for i in inv.collect_service_images(client, "proj")}
    assert images["n8n"]["repo_digest"] == "n8nio/n8n@sha256:abc"
    assert images["n8n_management"]["repo_digest"] is None

    vols = inv.snapshot_volumes(str(tmp_path / "volumes"), client, "proj")
    assert [v["volume"] for v in vols] == ["n8n_data"]
    assert vols[0]["included"] and vols[0]["docker_volume"] == "proj_n8n_data"
    with tarfile.open(tmp_path / "volumes" / "n8n_data.tar") as t:
        assert t.getnames() == ["config"]
    assert sorted(os.listdir(tmp_path / "volumes")) == ["n8n_data.tar"]
