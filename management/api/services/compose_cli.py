"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/compose_cli.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Run ``docker compose`` from inside the management container against the
host's stack.

The project directory is bind-mounted at /app/host_project, but the Docker
daemon resolves bind-mount sources on the HOST. Running plain
``docker compose -f /app/host_project/docker-compose.yaml up`` therefore
  * names the project "host_project" (from the directory name), so compose
    tries to create a second copy of every service and network, and
  * resolves ``./nginx.conf``-style sources to /app/host_project/... on the
    host, which does not exist (the daemon creates empty directories there).

The running containers carry the labels compose put on them:
com.docker.compose.project (the real project name, as setup.sh's
compose_project_name / find_compose_volume use), ...project.working_dir (the
project directory on the host) and ...project.config_files. Commands built
here pass those explicitly (``-p``, ``--project-directory``) and read the
compose/env files through the /app/host_project mount, so relative paths
resolve to the host directory and the existing containers are recreated in
place.
"""

import json
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from api.services import proc as _proc

logger = logging.getLogger(__name__)

HOST_PROJECT_MOUNT = "/app/host_project"

LABEL_PROJECT = "com.docker.compose.project"
LABEL_WORKING_DIR = "com.docker.compose.project.working_dir"
LABEL_CONFIG_FILES = "com.docker.compose.project.config_files"
LABEL_ENV_FILE = "com.docker.compose.project.environment_file"
LABEL_VOLUME = "com.docker.compose.volume"

COMPOSE_UP_TIMEOUT = 600  # may pull an image


class ComposeContextError(RuntimeError):
    """The compose project of the running stack could not be determined."""


@dataclass
class ComposeContext:
    project: str
    host_dir: Optional[str] = None            # project directory on the host
    config_files: List[str] = field(default_factory=list)  # host paths
    env_file: Optional[str] = None            # host path


def context_from_labels(labels: Optional[Dict[str, str]]) -> Optional[ComposeContext]:
    """ComposeContext from a compose-created container's labels (None if not compose-managed)."""
    labels = labels or {}
    project = (labels.get(LABEL_PROJECT) or "").strip()
    if not project:
        return None
    configs = [c.strip() for c in (labels.get(LABEL_CONFIG_FILES) or "").split(",") if c.strip()]
    env_files = [e.strip() for e in (labels.get(LABEL_ENV_FILE) or "").split(",") if e.strip()]
    return ComposeContext(
        project=project,
        host_dir=(labels.get(LABEL_WORKING_DIR) or "").strip() or None,
        config_files=configs,
        env_file=env_files[0] if env_files else None,
    )


def to_mount_path(host_path: str, host_dir: Optional[str], mount_dir: str = HOST_PROJECT_MOUNT) -> str:
    """Translate a path inside the host project directory to its path under the container mount."""
    if host_dir:
        base = host_dir.rstrip("/")
        if host_path == base:
            return mount_dir
        if host_path.startswith(base + "/"):
            return mount_dir + host_path[len(base):]
    return host_path


def build_compose_command(
    ctx: ComposeContext,
    args: Sequence[str],
    mount_dir: str = HOST_PROJECT_MOUNT,
) -> List[str]:
    """
    ``docker compose`` command line for the host stack described by ctx.

    -p pins the real project name; --project-directory makes relative paths
    in the compose file resolve to the host directory (what the daemon needs);
    -f / --env-file point at the same files through the container mount so
    the compose CLI can read them.
    """
    cmd = ["docker", "compose", "-p", ctx.project]
    if ctx.host_dir:
        cmd += ["--project-directory", ctx.host_dir]
    files = [to_mount_path(f, ctx.host_dir, mount_dir) for f in ctx.config_files]
    if not files:
        files = [os.path.join(mount_dir, "docker-compose.yaml")]
    for f in files:
        cmd += ["-f", f]
    env_file = (
        to_mount_path(ctx.env_file, ctx.host_dir, mount_dir)
        if ctx.env_file
        else os.path.join(mount_dir, ".env")
    )
    if os.path.isfile(env_file):
        cmd += ["--env-file", env_file]
    cmd += list(args)
    return cmd


def ensure_host_dir_alias(host_dir: Optional[str], mount_dir: str = HOST_PROJECT_MOUNT) -> None:
    """
    Make the host project path also valid inside this container (a symlink
    to the mount) so anything compose reads relative to --project-directory
    (env_file:, secrets) is found. Best effort; never replaces an existing path.
    """
    if not host_dir or not os.path.isabs(host_dir) or os.path.lexists(host_dir):
        return
    try:
        os.makedirs(os.path.dirname(host_dir), exist_ok=True)
        os.symlink(mount_dir, host_dir)
    except OSError as e:
        logger.debug(f"Could not alias {host_dir} -> {mount_dir}: {e}")


def _candidate_containers() -> List[str]:
    names = [
        socket.gethostname(),  # this container (compose leaves the hostname as the container id)
        os.environ.get("MANAGEMENT_CONTAINER", "n8n_management"),
        os.environ.get("POSTGRES_CONTAINER", "n8n_postgres"),
        os.environ.get("POSTGRES_HOST", "n8n_postgres"),
    ]
    seen: List[str] = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen


async def _container_labels(name: str) -> Optional[Dict[str, str]]:
    try:
        result = await _proc.run(
            ["docker", "inspect", "--format", "{{json .Config.Labels}}", name],
            capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT,
        )
    except Exception as e:
        logger.debug(f"docker inspect {name} failed: {e}")
        return None
    if result.returncode != 0:
        return None
    try:
        labels = json.loads(result.stdout or "null")
    except ValueError:
        return None
    return labels if isinstance(labels, dict) else None


async def discover_compose_context() -> ComposeContext:
    """
    Compose project of the running stack, from the labels of this container
    (or the stack's postgres container). Raises ComposeContextError when no
    compose-managed container is found: guessing a project name would create
    a duplicate stack.
    """
    for name in _candidate_containers():
        ctx = context_from_labels(await _container_labels(name))
        if ctx:
            return ctx
    raise ComposeContextError(
        "Could not determine the Docker Compose project of this stack "
        "(no compose labels on the management or postgres container)"
    )


async def run_compose(
    args: Sequence[str],
    timeout: float = COMPOSE_UP_TIMEOUT,
    ctx: Optional[ComposeContext] = None,
):
    """Run ``docker compose <args>`` for the host stack. Returns a CompletedProcess (text)."""
    ctx = ctx or await discover_compose_context()
    ensure_host_dir_alias(ctx.host_dir)
    cmd = build_compose_command(ctx, args, mount_dir=HOST_PROJECT_MOUNT)
    logger.info(f"Running: {' '.join(cmd)}")
    return await _proc.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=HOST_PROJECT_MOUNT)


async def find_compose_volume(volume: str, ctx: Optional[ComposeContext] = None) -> Optional[str]:
    """Real Docker volume name of compose volume ``volume`` (e.g. tailscale_data -> n8n_nginx_tailscale_data)."""
    ctx = ctx or await discover_compose_context()
    result = await _proc.run(
        ["docker", "volume", "ls", "-q",
         "--filter", f"label={LABEL_PROJECT}={ctx.project}",
         "--filter", f"label={LABEL_VOLUME}={volume}"],
        capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT,
    )
    if result.returncode == 0:
        names = [n.strip() for n in (result.stdout or "").splitlines() if n.strip()]
        if names:
            return names[0]
    fallback = f"{ctx.project}_{volume}"
    check = await _proc.run(
        ["docker", "volume", "inspect", fallback],
        capture_output=True, text=True, timeout=_proc.DOCKER_TIMEOUT,
    )
    return fallback if check.returncode == 0 else None
