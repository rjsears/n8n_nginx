"""
Certificate inventory (api.services.ssl_service.get_ssl_info): the
letsencrypt volume mounted in the management container is read first; the
nginx container (NGINX_CONTAINER) is only asked when nothing is found there.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import types

import pytest

from api.services import ssl_service

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl CLI")


def _make_cert(directory, domain):
    live = directory / domain
    live.mkdir(parents=True)
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30",
         "-subj", f"/CN={domain}", "-addext", f"subjectAltName=DNS:{domain}",
         "-keyout", str(live / "privkey.pem"), "-out", str(live / "cert.pem")],
        check=True, capture_output=True,
    )


@pytest.fixture
def docker_calls(monkeypatch):
    """A fake docker module recording which containers were looked up."""
    calls = []

    class Containers:
        def get(self, name):
            calls.append(name)
            raise LookupError(name)

    fake = types.SimpleNamespace(from_env=lambda: types.SimpleNamespace(containers=Containers()))
    monkeypatch.setitem(sys.modules, "docker", fake)
    return calls


def test_reads_the_mounted_volume_without_docker(tmp_path, monkeypatch, docker_calls):
    _make_cert(tmp_path, "example.com")
    monkeypatch.setattr(ssl_service, "LETSENCRYPT_LIVE", str(tmp_path))

    info = ssl_service.get_ssl_info()

    assert info["configured"] and info["source"] == "local"
    assert [c["domain"] for c in info["certificates"]] == ["example.com"]
    assert 28 <= info["certificates"][0]["days_until_expiry"] <= 30
    assert docker_calls == [], "docker was asked although the volume is mounted"


def test_falls_back_to_the_configured_nginx_container(tmp_path, monkeypatch, docker_calls):
    monkeypatch.setattr(ssl_service, "LETSENCRYPT_LIVE", str(tmp_path / "missing"))
    monkeypatch.setenv("NGINX_CONTAINER", "acme_nginx")

    info = ssl_service.get_ssl_info()

    assert docker_calls[0] == "acme_nginx"
    assert info["configured"] is False and info["error"] == "Nginx container not found"
