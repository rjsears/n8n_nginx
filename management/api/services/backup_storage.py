"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/backup_storage.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Tell real off-host (NFS/CIFS) backup storage apart from the local disk.

The "NFS" path inside the container (/mnt/backups) is a bind mount of a host
directory (/opt/n8n_backups). os.path.ismount() and `mountpoint` are always
true for a bind mount, so they say nothing about whether the host actually
has the NFS share mounted there. If the share is missing (not in fstab,
mount failed at boot, mounted only after the container started), the
container writes to the host's root disk - usually the same disk as the
database - while everything is labelled "nfs".

What is checked instead:
  * the filesystem type of the mount that contains the path, from
    /proc/self/mountinfo (a bind mount reports the type of the filesystem it
    exposes: nfs/nfs4/cifs when the share was mounted, ext4/xfs/... when not);
  * that the path is not on the same device (st_dev) as known-local paths
    such as the host project directory and the local staging volume.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

MOUNTINFO_PATH = "/proc/self/mountinfo"

NETWORK_FS_TYPES = frozenset({
    "nfs", "nfs4", "cifs", "smb3", "smbfs", "ceph", "glusterfs",
    "fuse.glusterfs", "fuse.sshfs", "fuse.cephfs", "lustre", "beegfs", "9p",
})

# Paths that are known to live on this host's local storage. A backup target
# on the same device as one of these is local, whatever it is called.
LOCAL_REFERENCE_PATHS = ("/app/host_project", "/app/backups")


class BackupStorageUnavailableError(RuntimeError):
    """Off-host storage is required but the target is missing or is the local disk."""

    def __init__(self, message: str, status: Optional["StorageTargetStatus"] = None):
        super().__init__(message)
        self.status = status


@dataclass
class MountEntry:
    mount_point: str
    fstype: str
    source: str


@dataclass
class StorageTargetStatus:
    path: str
    exists: bool = False
    writable: bool = False
    mount_point: Optional[str] = None
    fstype: Optional[str] = None
    source: Optional[str] = None
    is_network_fs: bool = False
    same_device_as: List[str] = field(default_factory=list)
    offsite: bool = False
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _unescape(field_value: str) -> str:
    # mountinfo escapes space, tab, newline and backslash as \ooo octal
    out, i = [], 0
    while i < len(field_value):
        c = field_value[i]
        if c == "\\" and len(field_value[i + 1:i + 4]) == 3 and field_value[i + 1:i + 4].isdigit():
            out.append(chr(int(field_value[i + 1:i + 4], 8)))
            i += 4
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_mountinfo(text: str) -> List[MountEntry]:
    """Parse /proc/<pid>/mountinfo (see proc(5)) into mount point, fstype, source."""
    entries: List[MountEntry] = []
    for line in text.splitlines():
        parts = line.split()
        if "-" not in parts:
            continue
        sep = parts.index("-")
        if sep < 5 or len(parts) < sep + 3:
            continue
        entries.append(MountEntry(
            mount_point=_unescape(parts[4]),
            fstype=parts[sep + 1],
            source=_unescape(parts[sep + 2]),
        ))
    return entries


def read_mountinfo(path: str = MOUNTINFO_PATH) -> List[MountEntry]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return parse_mountinfo(f.read())
    except OSError as e:
        logger.warning(f"Cannot read {path}: {e}")
        return []


def find_mount(path: str, entries: Iterable[MountEntry]) -> Optional[MountEntry]:
    """The entry whose mount point is the longest prefix of path (later entries win ties)."""
    real = os.path.realpath(path)
    best: Optional[MountEntry] = None
    for entry in entries:
        mp = entry.mount_point.rstrip("/") or "/"
        if real == mp or mp == "/" or real.startswith(mp + "/"):
            if best is None or len(mp) >= len(best.mount_point.rstrip("/") or "/"):
                best = entry
    return best


def _st_dev(path: str) -> Optional[int]:
    try:
        return os.stat(path).st_dev
    except OSError:
        return None


def inspect_storage_target(
    path: str,
    mountinfo_path: str = MOUNTINFO_PATH,
    local_reference_paths: Iterable[str] = LOCAL_REFERENCE_PATHS,
) -> StorageTargetStatus:
    """Describe path and decide whether it is genuinely off-host storage."""
    status = StorageTargetStatus(path=path)
    status.exists = os.path.isdir(path)
    if not status.exists:
        status.reason = f"{path} does not exist"
        return status
    status.writable = os.access(path, os.W_OK)

    entry = find_mount(path, read_mountinfo(mountinfo_path))
    if entry:
        status.mount_point = entry.mount_point
        status.fstype = entry.fstype
        status.source = entry.source
        status.is_network_fs = entry.fstype in NETWORK_FS_TYPES

    dev = _st_dev(path)
    if dev is not None:
        for ref in local_reference_paths:
            if os.path.realpath(ref) == os.path.realpath(path):
                continue
            if _st_dev(ref) == dev:
                status.same_device_as.append(ref)

    if not status.is_network_fs:
        status.reason = (
            f"{path} is on a local '{status.fstype or 'unknown'}' filesystem, not a network share "
            "(the NFS share is not mounted on the host at the bind-mounted directory, or was "
            "mounted after this container started)"
        )
    elif status.same_device_as:
        status.reason = f"{path} is on the same device as {', '.join(status.same_device_as)}"
    elif not status.writable:
        status.reason = f"{path} is a {status.fstype} share but is not writable"
    else:
        status.offsite = True
        status.reason = f"{status.fstype} share {status.source}"
    return status


def is_offsite_storage(path: str, **kwargs) -> bool:
    return inspect_storage_target(path, **kwargs).offsite


# ---------------------------------------------------------------------------
# Periodic check (scheduler) - dispatches backup_storage_unavailable when the
# configured off-host target goes missing, once per outage.
# ---------------------------------------------------------------------------

_last_check_ok: Optional[bool] = None


async def configured_offsite_path(db) -> Optional[str]:
    """The off-host path backups are configured to use, or None if none is configured."""
    from sqlalchemy import select
    from api.config import settings
    from api.models.backups import BackupConfiguration

    config = (await db.execute(select(BackupConfiguration).limit(1))).scalar_one_or_none()
    if config is not None:
        if config.nfs_enabled and config.storage_preference in ("nfs", "both"):
            return config.nfs_storage_path or settings.nfs_mount_point
        return None
    if settings.nfs_server:
        return settings.nfs_mount_point
    return None


async def notify_storage_unavailable(path: str, status: StorageTargetStatus, context: str) -> None:
    from api.services.notification_service import dispatch_notification

    try:
        await dispatch_notification("backup_storage_unavailable", {
            "path": path,
            "reason": status.reason,
            "fstype": status.fstype,
            "context": context,
        })
    except Exception as e:
        logger.error(f"Could not send backup_storage_unavailable notification: {e}")


async def check_backup_storage() -> Optional[StorageTargetStatus]:
    """Scheduler entry point: verify the configured off-host target, notify on a new outage."""
    global _last_check_ok
    from api.database import async_session_maker

    async with async_session_maker() as db:
        path = await configured_offsite_path(db)
    if not path:
        _last_check_ok = None
        return None
    status = inspect_storage_target(path)
    if status.offsite:
        if _last_check_ok is False:
            logger.info(f"Off-host backup storage is available again: {status.reason}")
        _last_check_ok = True
        return status
    logger.error(f"Off-host backup storage unavailable: {status.reason}")
    if _last_check_ok is not False:
        await notify_storage_unavailable(path, status, "periodic check")
    _last_check_ok = False
    return status
