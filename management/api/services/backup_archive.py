"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/backup_archive.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

File permissions and optional encryption for backup archives.

Every complete backup archive contains .env (N8N_ENCRYPTION_KEY, database
passwords, DNS API tokens), TLS private keys and the management database
(notification channel secrets). So:

* archives, safety dumps and their directories are created owner-only
  (files 0600, directories 0700);
* when BACKUP_ENCRYPTION_PASSPHRASE is set (process environment, or the
  project's .env), archives are written as OpenPGP symmetric ciphertext
  (AES-256, integrity protected) named ``*.n8n_backup.tar.gz.gpg``. Decrypt
  with ``gpg --decrypt FILE | tar xz`` on any machine. Losing the passphrase
  means losing every encrypted backup.

Readers (verification, restore, browsing, downloads) open archives through
``open_backup_archive`` / ``plaintext_archive``, which decrypt transparently.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import IO, Iterator, Optional

logger = logging.getLogger(__name__)

ENCRYPTED_SUFFIX = ".gpg"
PASSPHRASE_ENV_KEY = "BACKUP_ENCRYPTION_PASSPHRASE"
HOST_ENV_PATH = "/app/host_project/.env"
MIN_PASSPHRASE_LENGTH = 12

PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700

_GZIP_MAGIC = b"\x1f\x8b"
_GPG_TIMEOUT = 6 * 3600


class BackupEncryptionError(RuntimeError):
    """Encryption/decryption failed (missing passphrase, wrong passphrase, gpg error)."""


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def chmod_quietly(path: str, mode: int) -> bool:
    """chmod that tolerates filesystems refusing it (NFS root_squash, CIFS)."""
    try:
        os.chmod(path, mode)
        return True
    except OSError as e:
        logger.warning(f"Could not chmod {oct(mode)} {path}: {e}")
        return False


def make_private_dir(path: str) -> str:
    """Create path (and parents) and make the leaf directory owner-only."""
    os.makedirs(path, mode=PRIVATE_DIR_MODE, exist_ok=True)
    chmod_quietly(path, PRIVATE_DIR_MODE)
    return path


def open_private_file(path: str, mode: str = "wb") -> IO:
    """Create path exclusively with mode 0600 (no window in which it is world-readable)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags, PRIVATE_FILE_MODE)
    return os.fdopen(fd, mode)


def tighten_backup_tree(root: str) -> int:
    """
    Make existing backup files under root owner-only (archives written by
    older versions were 0644). Returns the number of entries changed.
    """
    changed = 0
    if not os.path.isdir(root):
        return 0
    for dirpath, _dirnames, filenames in os.walk(root):
        try:
            if os.stat(dirpath).st_mode & 0o077 and chmod_quietly(dirpath, PRIVATE_DIR_MODE):
                changed += 1
        except OSError:
            continue
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if os.path.islink(path) or not (st.st_mode & 0o077):
                continue
            if chmod_quietly(path, PRIVATE_FILE_MODE):
                changed += 1
    if changed:
        logger.info(f"Restricted permissions on {changed} existing backup file(s)/dir(s) under {root}")
    return changed


# ---------------------------------------------------------------------------
# Passphrase
# ---------------------------------------------------------------------------

def get_encryption_passphrase(env_path: str = HOST_ENV_PATH) -> Optional[str]:
    """
    The archive passphrase: process environment first, then the project's .env
    (read at call time, so editing .env takes effect without a restart).
    Returns None when encryption is not configured.
    """
    value = os.environ.get(PASSPHRASE_ENV_KEY)
    if not value:
        try:
            from api.services.env_file import read_env_value
            value = read_env_value(env_path, PASSPHRASE_ENV_KEY)
        except Exception as e:  # unreadable .env must not break backups
            logger.warning(f"Could not read {PASSPHRASE_ENV_KEY} from {env_path}: {e}")
            value = None
    value = (value or "").strip()
    if not value:
        return None
    if len(value) < MIN_PASSPHRASE_LENGTH:
        raise BackupEncryptionError(
            f"{PASSPHRASE_ENV_KEY} is shorter than {MIN_PASSPHRASE_LENGTH} characters; "
            "refusing to encrypt backups with a weak passphrase"
        )
    return value


def encryption_enabled() -> bool:
    try:
        return get_encryption_passphrase() is not None
    except BackupEncryptionError:
        return True


# ---------------------------------------------------------------------------
# gpg
# ---------------------------------------------------------------------------

def _gpg_base_cmd(homedir: str, passphrase_fd: int) -> list:
    return [
        "gpg", "--homedir", homedir, "--batch", "--yes", "--quiet",
        "--no-tty", "--no-symkey-cache", "--pinentry-mode", "loopback",
        "--passphrase-fd", str(passphrase_fd),
    ]


@contextlib.contextmanager
def _gpg_session(passphrase: str) -> Iterator[tuple]:
    """Private GNUPGHOME plus a pipe carrying the passphrase (never on argv/env)."""
    homedir = tempfile.mkdtemp(prefix="n8n_gpg_")
    r, w = os.pipe()
    try:
        os.write(w, passphrase.encode("utf-8") + b"\n")
        os.close(w)
        w = -1
        yield homedir, r
    finally:
        if w != -1:
            os.close(w)
        with contextlib.suppress(OSError):
            os.close(r)
        shutil.rmtree(homedir, ignore_errors=True)


def encrypt_command(homedir: str, passphrase_fd: int, output_path: str) -> list:
    """gpg command reading plaintext on stdin and writing ciphertext to output_path."""
    return _gpg_base_cmd(homedir, passphrase_fd) + [
        "--symmetric", "--cipher-algo", "AES256",
        "--s2k-mode", "3", "--s2k-digest-algo", "SHA512", "--s2k-count", "65011712",
        "--compress-algo", "none",
        "--output", output_path,
    ]


def _check_gpg_result(proc: subprocess.CompletedProcess, action: str) -> None:
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace") if isinstance(proc.stderr, bytes) else (proc.stderr or "")
        hint = ""
        if "bad passphrase" in err.lower() or "decryption failed" in err.lower():
            hint = f" (wrong {PASSPHRASE_ENV_KEY}, or the file is damaged)"
        raise BackupEncryptionError(f"gpg {action} failed (exit {proc.returncode}){hint}: {err.strip()[-500:]}")


def encrypt_file(src: str, dst: str, passphrase: str) -> None:
    """Encrypt src into dst (created 0600)."""
    with _gpg_session(passphrase) as (homedir, fd):
        with open(src, "rb") as fin:
            try:
                proc = subprocess.run(
                    encrypt_command(homedir, fd, dst), stdin=fin, capture_output=True,
                    pass_fds=(fd,), timeout=_GPG_TIMEOUT,
                )
            except FileNotFoundError as e:
                raise BackupEncryptionError("gpg is not installed") from e
    _check_gpg_result(proc, "encryption")
    chmod_quietly(dst, PRIVATE_FILE_MODE)


def decrypt_file(src: str, dst: str, passphrase: Optional[str] = None) -> None:
    """Decrypt src into dst (created 0600). Raises BackupEncryptionError."""
    if passphrase is None:
        passphrase = get_encryption_passphrase()
    if not passphrase:
        raise BackupEncryptionError(
            f"{os.path.basename(src)} is encrypted but {PASSPHRASE_ENV_KEY} is not set. "
            f"Add the passphrase the archive was created with to .env as {PASSPHRASE_ENV_KEY}."
        )
    with _gpg_session(passphrase) as (homedir, fd):
        # Pre-create the output owner-only; gpg --yes overwrites in place.
        open_private_file(dst).close()
        try:
            proc = subprocess.run(
                _gpg_base_cmd(homedir, fd) + ["--decrypt", "--output", dst, src],
                capture_output=True, pass_fds=(fd,), timeout=_GPG_TIMEOUT,
            )
        except FileNotFoundError as e:
            raise BackupEncryptionError("gpg is not installed") from e
    if proc.returncode != 0:
        with contextlib.suppress(OSError):
            os.remove(dst)
    _check_gpg_result(proc, "decryption")
    chmod_quietly(dst, PRIVATE_FILE_MODE)


class EncryptingWriter:
    """
    File-like sink that pipes everything written to it through gpg into
    output_path, so a plaintext archive never touches the backup disk.
    """

    def __init__(self, output_path: str, passphrase: str):
        self._session = _gpg_session(passphrase)
        homedir, fd = self._session.__enter__()
        open_private_file(output_path).close()
        try:
            self._proc = subprocess.Popen(
                encrypt_command(homedir, fd, output_path),
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                pass_fds=(fd,),
            )
        except FileNotFoundError as e:
            self._session.__exit__(None, None, None)
            raise BackupEncryptionError("gpg is not installed") from e
        self._closed = False
        self.output_path = output_path

    def write(self, data: bytes) -> int:
        try:
            self._proc.stdin.write(data)
        except BrokenPipeError as e:
            raise BackupEncryptionError("gpg exited while the archive was being written") from e
        return len(data)

    def flush(self) -> None:
        self._proc.stdin.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            with contextlib.suppress(BrokenPipeError):
                self._proc.stdin.close()
            stderr = self._proc.stderr.read()
            rc = self._proc.wait(timeout=_GPG_TIMEOUT)
        finally:
            self._session.__exit__(None, None, None)
        _check_gpg_result(subprocess.CompletedProcess(self._proc.args, rc, b"", stderr), "encryption")
        chmod_quietly(self.output_path, PRIVATE_FILE_MODE)

    def abort(self) -> None:
        if not self._closed:
            self._closed = True
            with contextlib.suppress(Exception):
                self._proc.kill()
                self._proc.wait(timeout=30)
            self._session.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Reading archives
# ---------------------------------------------------------------------------

def is_encrypted_archive(path: str) -> bool:
    """True for gpg-encrypted archives (by suffix, or content that is not gzip)."""
    if path.endswith(ENCRYPTED_SUFFIX):
        return True
    try:
        with open(path, "rb") as f:
            head = f.read(2)
    except OSError:
        return False
    if not head or head == _GZIP_MAGIC:
        return False
    # OpenPGP packet header with tag 3 (symmetric-key encrypted session key):
    # old format 0x8c-0x8f, new format 0xc3.
    return head[0] in (0x8C, 0x8D, 0x8E, 0x8F, 0xC3)


@contextlib.contextmanager
def plaintext_archive(path: str, passphrase: Optional[str] = None) -> Iterator[str]:
    """
    Yield a path to the plaintext .tar.gz for path: path itself when it is not
    encrypted, otherwise a decrypted copy in a private temp dir that is
    removed on exit.
    """
    if not is_encrypted_archive(path):
        yield path
        return
    tmpdir = tempfile.mkdtemp(prefix="n8n_backup_plain_")
    try:
        plain = os.path.join(tmpdir, "archive.tar.gz")
        decrypt_file(path, plain, passphrase)
        yield plain
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@contextlib.contextmanager
def open_backup_archive(path: str, passphrase: Optional[str] = None) -> Iterator[tarfile.TarFile]:
    """tarfile.open(path, "r:gz") that transparently decrypts encrypted archives."""
    with plaintext_archive(path, passphrase) as plain:
        with tarfile.open(plain, "r:gz") as tar:
            yield tar


def safe_extract(tar: tarfile.TarFile, dest_dir: str) -> None:
    """extractall refusing absolute paths / traversal where Python supports filters."""
    try:
        tar.extractall(dest_dir, filter="tar")
    except TypeError:  # Python without extraction filters (< 3.11.4)
        tar.extractall(dest_dir)

