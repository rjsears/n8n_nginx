"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/stack_inventory.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

What a bare-metal restore needs besides the databases, collected at backup
time and recorded in the archive:

* the project directory (every bind-mounted config file, scripts/certbot,
  the management and n8n_status build contexts, and docs/ + mkdocs.yml,
  which the management image build pulls in through the compose
  ``additional_contexts: docs_src: .``), minus git history, screenshots,
  generated output, dependency folders and local backup copies;
* the Docker Compose project name (volumes are <project>_<name>);
* the image each service was running (reference, image ID and registry
  digest), so restore.sh can pin those instead of pulling :latest;
* snapshots of the named volumes that hold state outside Postgres: n8n_data
  (~/.n8n: config with encryptionKey, binaryData in filesystem mode,
  community nodes, ssh/git) and ntfy_data (ntfy users/ACL).

All functions are synchronous (Docker SDK / filesystem); call them through
asyncio.to_thread.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import tarfile
import tempfile
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

HOST_PROJECT_DIR = "/app/host_project"

# Top-level project entries never copied into the archive: history,
# screenshots, generated/local-only folders and local backup copies.
# Secrets (.env, *.ini, letsencrypt) ARE included on purpose. docs/ and
# mkdocs.yml are included: the management image build needs them (compose
# `additional_contexts: docs_src: .`, management/Dockerfile docs stage).
PROJECT_EXCLUDE_TOP = frozenset({
    ".git", "images", "env_backups", ".backups", "backups", "tests", ".github",
    "site",  # mkdocs build output
})
# Directory names excluded at any depth: VCS metadata (nested checkouts),
# agent/editor worktrees, dependency and build output folders, caches.
PROJECT_EXCLUDE_ANY = frozenset({
    ".git", ".claude", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".venv", "venv", "dist", "build",
})
# File names never copied: backup archives and their partial or encrypted
# forms (downloaded backups must not nest inside the next backup) and
# editor/restore leftovers.
PROJECT_EXCLUDE_SUFFIXES = (".gpg", ".partial", ".swp", "~")
PROJECT_EXCLUDE_NAME_PARTS = (".n8n_backup.tar.gz", ".bak.")
PROJECT_MAX_FILE_BYTES = 50 * 1024 * 1024
# Cap for the whole copied project tree (env BACKUP_PROJECT_MAX_MB).
PROJECT_MAX_TOTAL_DEFAULT_MB = 200


class ProjectTreeTooLargeError(RuntimeError):
    """The project directory is over the size cap; the backup fails before any dump."""


def project_max_total_bytes() -> int:
    try:
        mb = int(os.environ.get("BACKUP_PROJECT_MAX_MB", str(PROJECT_MAX_TOTAL_DEFAULT_MB)))
    except ValueError:
        mb = PROJECT_MAX_TOTAL_DEFAULT_MB
    return max(mb, 1) * 1024 * 1024

# Named volumes with state that lives outside Postgres. "service" is the
# compose service whose container mounts the volume at "path".
VOLUME_SNAPSHOTS = [
    {
        "volume": "n8n_data",
        "service": "n8n",
        "path": "/home/node/.n8n",
        # Regenerated / log-only content
        "exclude": (".cache", "n8nEventLog"),
    },
    {
        "volume": "ntfy_data",
        "service": "ntfy",
        "path": "/var/lib/ntfy",
        "exclude": (),
    },
]

_PROJECT_NAME_RE = re.compile(r"[^a-z0-9_-]")


def normalize_project_name(name: str) -> str:
    """Same normalisation as Docker Compose and setup.sh's compose_project_name()."""
    return _PROJECT_NAME_RE.sub("", name.lower())


# ---------------------------------------------------------------------------
# Project directory
# ---------------------------------------------------------------------------

def _project_excluded(rel: str) -> bool:
    parts = rel.split(os.sep)
    if parts[0] in PROJECT_EXCLUDE_TOP:
        return True
    if any(p in PROJECT_EXCLUDE_ANY for p in parts):
        return True
    name = parts[-1]
    return name.endswith(PROJECT_EXCLUDE_SUFFIXES) or any(x in name for x in PROJECT_EXCLUDE_NAME_PARTS)


def _walk_project(source_dir: str) -> Iterator[Tuple[str, str, str]]:
    """Yield (kind, rel, src) for every entry that belongs in the archive; kind is dir, link or file."""
    for root, dirs, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)
        rel_root = "" if rel_root == "." else rel_root
        dirs[:] = sorted(d for d in dirs if not _project_excluded(os.path.join(rel_root, d) if rel_root else d))
        yield "dir", rel_root, root
        for name in sorted(files):
            rel = os.path.join(rel_root, name) if rel_root else name
            if _project_excluded(rel):
                continue
            src = os.path.join(root, name)
            if os.path.islink(src):
                yield "link", rel, src
            elif os.path.isfile(src):
                yield "file", rel, src
            # sockets, fifos: skipped


def scan_project_tree(source_dir: str = HOST_PROJECT_DIR) -> Dict[str, Any]:
    """
    Size of what copy_project_tree would copy: {"total_bytes", "file_count",
    "largest_dirs": [(top-level entry, bytes), ...]}. Files over the
    per-file limit are skipped by the copy and not counted.
    """
    total = 0
    count = 0
    by_top: Dict[str, int] = {}
    if os.path.isdir(source_dir):
        for kind, rel, src in _walk_project(source_dir):
            if kind != "file":
                continue
            try:
                size = os.path.getsize(src)
            except OSError:
                continue
            if size > PROJECT_MAX_FILE_BYTES:
                continue
            total += size
            count += 1
            top = rel.split(os.sep, 1)[0]
            by_top[top] = by_top.get(top, 0) + size
    largest = sorted(by_top.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {"total_bytes": total, "file_count": count, "largest_dirs": largest}


def _too_large_message(total: int, cap: int, largest: List[Tuple[str, int]]) -> str:
    biggest = ", ".join(f"{name} ({size / 1024**2:.0f} MiB)" for name, size in largest)
    return (
        f"The project directory to back up is at least {total / 1024**2:.0f} MiB, over the "
        f"{cap / 1024**2:.0f} MiB limit (largest entries: {biggest}). Move large files out of the "
        "project directory (downloaded backups, build output, copies), or raise BACKUP_PROJECT_MAX_MB "
        "in .env if they really belong in every backup."
    )


def check_project_tree_size(source_dir: str = HOST_PROJECT_DIR) -> int:
    """Raise ProjectTreeTooLargeError if the project tree is over the cap; return its size in bytes."""
    scan = scan_project_tree(source_dir)
    cap = project_max_total_bytes()
    if scan["total_bytes"] > cap:
        raise ProjectTreeTooLargeError(_too_large_message(scan["total_bytes"], cap, scan["largest_dirs"]))
    return scan["total_bytes"]


def _copy_owner(src: str, dst: str) -> None:
    """Keep the source uid/gid (the copy runs as root and would otherwise own everything)."""
    try:
        st = os.lstat(src)
        os.chown(dst, st.st_uid, st.st_gid, follow_symlinks=False)
    except (OSError, NotImplementedError) as e:
        logger.debug(f"Could not keep ownership of {dst}: {e}")


def copy_project_tree(
    dest_dir: str,
    source_dir: str = HOST_PROJECT_DIR,
    max_total_bytes: Optional[int] = None,
) -> Tuple[int, List[str]]:
    """
    Copy the project directory into dest_dir, preserving symlinks, modes and
    ownership. Returns (file_count, skipped_paths).

    Raises ProjectTreeTooLargeError once the copied files exceed
    max_total_bytes (default BACKUP_PROJECT_MAX_MB). The backup then fails
    loudly rather than producing an archive whose project/ tree is silently
    incomplete, which would only surface as a failed `compose up` build in
    the middle of a bare-metal restore, after the databases were replaced.
    """
    import shutil

    count = 0
    copied_bytes = 0
    skipped: List[str] = []
    cap = project_max_total_bytes() if max_total_bytes is None else max_total_bytes
    if not os.path.isdir(source_dir):
        return 0, skipped
    for kind, rel, src in _walk_project(source_dir):
        dst = os.path.join(dest_dir, rel) if rel else dest_dir
        try:
            if kind == "dir":
                os.makedirs(dst, exist_ok=True)
                shutil.copystat(src, dst)
                _copy_owner(src, dst)
                continue
            if kind == "link":
                os.symlink(os.readlink(src), dst)
            else:
                size = os.path.getsize(src)
                if size > PROJECT_MAX_FILE_BYTES:
                    skipped.append(rel)
                    continue
                copied_bytes += size
                if copied_bytes > cap:
                    raise ProjectTreeTooLargeError(
                        _too_large_message(copied_bytes, cap, scan_project_tree(source_dir)["largest_dirs"])
                    )
                shutil.copy2(src, dst)
            _copy_owner(src, dst)
            count += 1
        except OSError as e:
            logger.warning(f"Could not copy project file {rel}: {e}")
            skipped.append(rel)
    return count, skipped


def read_git_commit(project_dir: str = HOST_PROJECT_DIR) -> Optional[str]:
    """HEAD commit of the project checkout, without needing git installed."""
    git_dir = os.path.join(project_dir, ".git")
    try:
        if os.path.isfile(git_dir):  # worktree / submodule: "gitdir: <path>"
            with open(git_dir) as f:
                line = f.read().strip()
            if not line.startswith("gitdir:"):
                return None
            git_dir = os.path.normpath(os.path.join(project_dir, line.split(":", 1)[1].strip()))
        with open(os.path.join(git_dir, "HEAD")) as f:
            head = f.read().strip()
        if not head.startswith("ref:"):
            return head or None
        ref = head.split(":", 1)[1].strip()
        for base in (git_dir, os.path.join(git_dir, "..", "..")):  # worktrees share refs with the main repo
            ref_path = os.path.join(base, ref)
            if os.path.isfile(ref_path):
                with open(ref_path) as f:
                    return f.read().strip() or None
            packed = os.path.join(base, "packed-refs")
            if os.path.isfile(packed):
                with open(packed) as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) == 2 and parts[1] == ref:
                            return parts[0]
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

def _docker_client():
    import docker

    return docker.from_env(timeout=60)


def find_compose_project(client=None) -> Optional[str]:
    """Compose project of this stack, from this container's (or postgres') labels."""
    client = client or _docker_client()
    candidates = [socket.gethostname(), os.environ.get("POSTGRES_HOST", "n8n_postgres"), "n8n_management"]
    for name in candidates:
        try:
            labels = client.containers.get(name).labels or {}
        except Exception:
            continue
        project = labels.get("com.docker.compose.project")
        if project:
            return project
    env_project = os.environ.get("COMPOSE_PROJECT_NAME")
    return normalize_project_name(env_project) if env_project else None


def _project_containers(client, project: str) -> list:
    return client.containers.list(all=True, filters={"label": f"com.docker.compose.project={project}"})


def collect_service_images(client=None, project: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    One entry per compose service: the image reference from the compose file,
    the image ID the container runs, and its registry digest when it was
    pulled (locally built images have none).
    """
    client = client or _docker_client()
    project = project or find_compose_project(client)
    if not project:
        return []
    images: Dict[str, Dict[str, Any]] = {}
    for container in _project_containers(client, project):
        labels = container.labels or {}
        service = labels.get("com.docker.compose.service")
        if not service or service in images:
            continue
        ref = (container.attrs.get("Config") or {}).get("Image") or ""
        image_id = container.attrs.get("Image") or ""
        repo_digest = None
        try:
            digests = container.image.attrs.get("RepoDigests") or []
            repo = ref.split("@", 1)[0]
            repo_name = repo.rsplit(":", 1)[0] if ":" in repo.rsplit("/", 1)[-1] else repo
            for digest in digests:
                if digest.split("@", 1)[0] in (repo_name, f"docker.io/{repo_name}", f"docker.io/library/{repo_name}"):
                    repo_digest = digest
                    break
            if repo_digest is None and digests:
                repo_digest = digests[0]
        except Exception as e:
            logger.debug(f"No digest for {service} ({ref}): {e}")
        images[service] = {
            "service": service,
            "ref": ref,
            "image_id": image_id,
            "repo_digest": repo_digest,
        }
    return [images[k] for k in sorted(images)]


def _find_service_container(client, project: str, service: str):
    for container in _project_containers(client, project):
        if (container.labels or {}).get("com.docker.compose.service") == service:
            return container
    return None


def _volume_mount(container, path: str) -> Optional[Dict[str, Any]]:
    for mount in container.attrs.get("Mounts") or []:
        if mount.get("Destination") == path and mount.get("Type") == "volume":
            return mount
    return None


def _excluded_member(rel: str, excludes: Iterable[str]) -> bool:
    first = rel.split("/", 1)[0]
    return any(first == e or first.startswith(e) for e in excludes)


def _strip_leading(name: str) -> str:
    return re.sub(r"^(?:\./|/)+", "", name)


def _rewrite_snapshot(raw_path: str, out_path: str, excludes: Iterable[str]) -> int:
    """
    `docker cp` archives are rooted at the directory's basename (".n8n/...").
    Rewrite them relative to the volume root and drop excluded entries.

    A hard link whose target was excluded (or is absent) would make tar fail
    on extraction ("Cannot hard link"), so it becomes a regular file with the
    target's content; a hard link to a target that is not in the raw archive
    at all is dropped.
    """
    count = 0
    written: set = set()
    excluded: Dict[str, tarfile.TarInfo] = {}
    # Random access ("r:", the raw archive is a file on disk) so a hard link
    # to an excluded member can be materialised from that member's data.
    with tarfile.open(raw_path, "r:") as src, tarfile.open(out_path, "w") as dst:
        for member in src:
            parts = _strip_leading(member.name).split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue  # the top-level directory itself
            rel = parts[1]
            if _excluded_member(rel, excludes):
                if member.isfile():
                    excluded[rel] = member
                continue
            if member.islnk():
                link_parts = _strip_leading(member.linkname).split("/", 1)
                target = link_parts[1] if len(link_parts) == 2 else member.linkname
                if target in written:
                    member.linkname = target
                elif target in excluded:
                    source = excluded[target]
                    member.type = tarfile.REGTYPE
                    member.linkname = ""
                    member.size = source.size
                    member.name = rel
                    dst.addfile(member, src.extractfile(source))
                    written.add(rel)
                    count += 1
                    continue
                else:
                    logger.warning(f"Dropping hard link {rel} -> {target}: target not in the snapshot")
                    continue
            member.name = rel
            if member.isfile():
                dst.addfile(member, src.extractfile(member))
                count += 1
            else:
                dst.addfile(member)
            written.add(rel)
    return count


# Raw `docker cp` size of each snapshotted volume from the last backup in
# this process, for the free-space pre-check.
_last_volume_bytes: Dict[str, int] = {}


def estimate_snapshot_bytes(client=None, project: Optional[str] = None) -> int:
    """
    Approximate total size of the volumes in VOLUME_SNAPSHOTS: the raw size
    seen by the last snapshot in this process, otherwise Docker's volume usage
    (`docker system df`). 0 when unknown.
    """
    if _last_volume_bytes:
        return sum(_last_volume_bytes.values())
    try:
        client = client or _docker_client()
        project = project or find_compose_project(client)
        if not project:
            return 0
        wanted = {f"{project}_{spec['volume']}" for spec in VOLUME_SNAPSHOTS}
        total = 0
        for vol in client.df().get("Volumes") or []:
            if vol.get("Name") in wanted:
                size = (vol.get("UsageData") or {}).get("Size") or 0
                total += max(int(size), 0)
        return total
    except Exception as e:
        logger.debug(f"Could not estimate volume sizes: {e}")
        return 0


def snapshot_volumes(dest_dir: str, client=None, project: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Write volumes/<volume>.tar for every entry in VOLUME_SNAPSHOTS whose
    service container exists (running or stopped). Returns metadata entries.
    """
    client = client or _docker_client()
    project = project or find_compose_project(client)
    results: List[Dict[str, Any]] = []
    if not project:
        logger.warning("Compose project not found; volume snapshots skipped")
        return results
    os.makedirs(dest_dir, exist_ok=True)
    for spec in VOLUME_SNAPSHOTS:
        container = _find_service_container(client, project, spec["service"])
        if container is None:
            continue
        mount = _volume_mount(container, spec["path"])
        entry: Dict[str, Any] = {
            "volume": spec["volume"],
            "service": spec["service"],
            "container_path": spec["path"],
            "docker_volume": mount.get("Name") if mount else None,
            "archive_path": f"volumes/{spec['volume']}.tar",
            "included": False,
        }
        if mount is None:
            entry["error"] = f"{spec['path']} is not a named volume in {container.name}"
            results.append(entry)
            continue
        fd, raw_path = tempfile.mkstemp(prefix=f"{spec['volume']}_", suffix=".raw.tar", dir=dest_dir)
        try:
            with os.fdopen(fd, "wb") as raw:
                stream, _stat = container.get_archive(spec["path"])
                for chunk in stream:
                    raw.write(chunk)
            out_path = os.path.join(dest_dir, f"{spec['volume']}.tar")
            _last_volume_bytes[spec["volume"]] = os.path.getsize(raw_path)
            entry["file_count"] = _rewrite_snapshot(raw_path, out_path, spec["exclude"])
            entry["size"] = os.path.getsize(out_path)
            entry["included"] = True
            logger.info(f"Snapshot of volume {spec['volume']}: {entry['file_count']} files")
        except Exception as e:
            entry["error"] = str(e)
            logger.error(f"Could not snapshot volume {spec['volume']}: {e}")
        finally:
            try:
                os.remove(raw_path)
            except OSError:
                pass
        results.append(entry)
    return results
