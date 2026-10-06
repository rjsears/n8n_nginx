"""
docker compose run from inside the management container must target the
running stack's project and host directory (H-22).
"""

from __future__ import annotations

import json
import subprocess

import pytest

from api.services import compose_cli

LABELS = {
    "com.docker.compose.project": "n8n_nginx",
    "com.docker.compose.project.working_dir": "/home/ops/n8n_nginx",
    "com.docker.compose.project.config_files": "/home/ops/n8n_nginx/docker-compose.yaml",
    "com.docker.compose.project.environment_file": "/home/ops/n8n_nginx/.env",
    "com.docker.compose.service": "n8n_management",
}


@pytest.fixture
def mount(tmp_path):
    """Stand-in for /app/host_project with an .env file."""
    (tmp_path / ".env").write_text("DOMAIN=example.com\n")
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n")
    return str(tmp_path)


def test_context_from_compose_labels():
    ctx = compose_cli.context_from_labels(LABELS)
    assert ctx.project == "n8n_nginx"
    assert ctx.host_dir == "/home/ops/n8n_nginx"
    assert ctx.config_files == ["/home/ops/n8n_nginx/docker-compose.yaml"]
    assert ctx.env_file == "/home/ops/n8n_nginx/.env"
    assert compose_cli.context_from_labels({"other": "x"}) is None
    assert compose_cli.context_from_labels(None) is None


def test_host_paths_are_read_through_the_mount():
    host = "/home/ops/n8n_nginx"
    assert compose_cli.to_mount_path(f"{host}/docker-compose.yaml", host, "/m") == "/m/docker-compose.yaml"
    assert compose_cli.to_mount_path(host, host, "/m") == "/m"
    # a sibling directory with a common prefix is not inside the project
    assert compose_cli.to_mount_path("/home/ops/n8n_nginx2/x", host, "/m") == "/home/ops/n8n_nginx2/x"


def test_compose_command_uses_project_name_and_host_directory(mount):
    ctx = compose_cli.context_from_labels(LABELS)
    cmd = compose_cli.build_compose_command(ctx, ["up", "-d", "--no-deps", "tailscale"], mount_dir=mount)

    assert cmd[:2] == ["docker", "compose"]
    assert cmd[cmd.index("-p") + 1] == "n8n_nginx", "without -p compose names the project 'host_project'"
    # relative bind sources (./nginx.conf, ./tailscale-serve.json) resolve on the HOST
    assert cmd[cmd.index("--project-directory") + 1] == "/home/ops/n8n_nginx"
    # ... while the CLI reads the files through the container mount
    assert cmd[cmd.index("-f") + 1] == f"{mount}/docker-compose.yaml"
    assert cmd[cmd.index("--env-file") + 1] == f"{mount}/.env"
    assert cmd[-4:] == ["up", "-d", "--no-deps", "tailscale"]
    assert "/app/host_project" not in " ".join(cmd)


def test_compose_command_with_override_files_and_no_env_file(tmp_path):
    ctx = compose_cli.ComposeContext(
        project="stack",
        host_dir="/srv/stack",
        config_files=["/srv/stack/docker-compose.yaml", "/srv/stack/docker-compose.override.yaml"],
    )
    cmd = compose_cli.build_compose_command(ctx, ["ps"], mount_dir=str(tmp_path))
    files = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-f"]
    assert files == [f"{tmp_path}/docker-compose.yaml", f"{tmp_path}/docker-compose.override.yaml"]
    assert "--env-file" not in cmd  # no .env in the mount: let compose use its default


async def test_discover_reads_labels_of_a_running_stack_container(monkeypatch):
    calls = []

    async def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[-1] == "n8n_postgres":
            return subprocess.CompletedProcess(cmd, 0, json.dumps(LABELS), "")
        return subprocess.CompletedProcess(cmd, 1, "", "No such object")

    monkeypatch.setattr(compose_cli._proc, "run", fake_run)
    monkeypatch.setattr(compose_cli.socket, "gethostname", lambda: "abc123")
    ctx = await compose_cli.discover_compose_context()
    assert ctx.project == "n8n_nginx"
    assert all(c[:2] == ["docker", "inspect"] for c in calls)


async def test_discover_refuses_to_guess(monkeypatch):
    async def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, "null", "")

    monkeypatch.setattr(compose_cli._proc, "run", fake_run)
    with pytest.raises(compose_cli.ComposeContextError):
        await compose_cli.discover_compose_context()


async def test_find_compose_volume_uses_labels(monkeypatch):
    async def fake_run(cmd, **kwargs):
        assert "label=com.docker.compose.project=n8n_nginx" in cmd
        assert "label=com.docker.compose.volume=tailscale_data" in cmd
        return subprocess.CompletedProcess(cmd, 0, "n8n_nginx_tailscale_data\n", "")

    monkeypatch.setattr(compose_cli._proc, "run", fake_run)
    ctx = compose_cli.context_from_labels(LABELS)
    assert await compose_cli.find_compose_volume("tailscale_data", ctx) == "n8n_nginx_tailscale_data"


async def test_recreate_container_runs_compose_for_the_real_project(monkeypatch, mount):
    from api.services import container_service

    ran = []

    async def fake_proc_run(cmd, **kwargs):
        ran.append((cmd, kwargs))
        if cmd[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(LABELS), "")
        return subprocess.CompletedProcess(cmd, 0, "recreated", "")

    async def no_notify(*a, **kw):
        return None

    monkeypatch.setattr(compose_cli._proc, "run", fake_proc_run)
    monkeypatch.setattr(compose_cli, "HOST_PROJECT_MOUNT", mount)
    monkeypatch.setattr(compose_cli, "ensure_host_dir_alias", lambda *a, **kw: None)
    monkeypatch.setattr(container_service, "dispatch_notification", no_notify)
    monkeypatch.setattr(container_service.ContainerService, "_get_service_name_from_container",
                        lambda self, name: "nginx")

    result = await container_service.ContainerService().recreate_container("n8n_nginx", pull=True)

    assert result["success"] and result["service"] == "nginx"
    cmd, kwargs = next((c, k) for c, k in ran if c[:2] == ["docker", "compose"])
    assert cmd[cmd.index("-p") + 1] == "n8n_nginx"
    assert cmd[cmd.index("--project-directory") + 1] == "/home/ops/n8n_nginx"
    assert cmd[cmd.index("-f") + 1] == f"{mount}/docker-compose.yaml"
    assert cmd[cmd.index("--env-file") + 1] == f"{mount}/.env"
    assert cmd[-7:] == ["up", "-d", "--no-deps", "--force-recreate", "--pull", "always", "nginx"]
    assert kwargs["timeout"] > 0 and kwargs["cwd"] == mount


async def test_tailscale_reset_recreates_in_the_existing_project(monkeypatch, mount):
    from api.routers import settings as settings_router

    ran = []

    async def fake_proc_run(cmd, **kwargs):
        ran.append(cmd)
        assert kwargs.get("timeout"), f"no timeout for {cmd}"
        if cmd[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(LABELS), "")
        if cmd[:3] == ["docker", "volume", "ls"]:
            return subprocess.CompletedProcess(cmd, 0, "n8n_nginx_tailscale_data\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(compose_cli._proc, "run", fake_proc_run)
    monkeypatch.setattr(compose_cli, "HOST_PROJECT_MOUNT", mount)
    monkeypatch.setattr(compose_cli, "ensure_host_dir_alias", lambda *a, **kw: None)

    result = await settings_router.reset_tailscale_container()

    assert result["success"], result
    assert ["docker", "volume", "rm", "n8n_nginx_tailscale_data"] in ran
    up = next(c for c in ran if c[:2] == ["docker", "compose"])
    assert up[up.index("-p") + 1] == "n8n_nginx"
    assert up[up.index("--project-directory") + 1] == "/home/ops/n8n_nginx"
    assert up[-4:] == ["up", "-d", "--no-deps", "tailscale"]


async def test_tailscale_reset_removes_nothing_when_project_unknown(monkeypatch):
    from api.routers import settings as settings_router

    ran = []

    async def fake_proc_run(cmd, **kwargs):
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "No such object")

    monkeypatch.setattr(compose_cli._proc, "run", fake_proc_run)
    result = await settings_router.reset_tailscale_container()
    assert result["success"] is False
    assert all(c[:2] == ["docker", "inspect"] for c in ran), "must not stop/remove anything it cannot recreate"


def test_host_dir_alias_points_at_the_mount(tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    host_dir = tmp_path / "home" / "ops" / "n8n_nginx"
    compose_cli.ensure_host_dir_alias(str(host_dir), str(mount))
    assert host_dir.is_symlink() and host_dir.resolve() == mount.resolve()
    # never replaces an existing path
    compose_cli.ensure_host_dir_alias(str(mount), str(tmp_path))
    assert mount.is_dir() and not mount.is_symlink()
