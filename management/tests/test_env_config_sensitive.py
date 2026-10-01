"""
The environment editor never returns secret values: the credentials setup.sh
writes to .env are listed as sensitive, and any other (custom) variable whose
name looks like a secret is hidden by default.
"""

from __future__ import annotations

import pytest

from api.routers import env_config


SECRETS = {
    "NTFY_ADMIN_PASS": "ntfy-admin-pass-value",
    "NTFY_TOKEN": "tk_abcdefghijklmnopqrstuvwxyz012",
    "NTFY_ADMIN_PASSWORD_HASH": "$2y$10$abcdefghijklmnopqrstuv",
    "PORTAINER_AGENT_SECRET": "portainer-agent-secret-value",
    "BACKUP_ENCRYPTION_PASSPHRASE": "backup-passphrase-value",
    "MY_SERVICE_API_KEY": "custom-api-key-value",
    "SMTP_PASSWORD": "custom-smtp-password",
    "SOME_CLIENT_SECRET": "custom-client-secret",
    "GITHUB_TOKEN": "custom-github-token",
    "AWS_CREDENTIALS": "custom-aws-credentials",
    "WEBHOOK_HMAC_HASH": "custom-hash",
}
PLAIN = {"DOMAIN": "n8n.example.com", "MY_FEATURE_FLAG": "on"}


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in {**PLAIN, **SECRETS}.items()))
    monkeypatch.setattr(env_config, "ENV_FILE_PATH", path)
    return path


async def test_secret_values_are_never_returned(env_file):
    resp = await env_config.get_env_config(_=None)
    variables = {v.key: v for g in resp.groups for v in g.variables}
    for key, value in SECRETS.items():
        assert variables[key].sensitive is True, key
        assert variables[key].value == "", key
    body = resp.model_dump_json()
    for value in SECRETS.values():
        assert value not in body
    assert variables["DOMAIN"].value == "n8n.example.com"
    assert variables["MY_FEATURE_FLAG"].value == "on"
    assert variables["MY_FEATURE_FLAG"].sensitive is False


@pytest.mark.parametrize("key", ["NTFY_ADMIN_PASS", "NTFY_TOKEN", "NTFY_ADMIN_PASSWORD_HASH", "PORTAINER_AGENT_SECRET"])
def test_setup_credentials_are_grouped_as_sensitive(key):
    meta = env_config.get_variable_metadata(key)
    assert meta["group"] != "custom"
    assert meta["sensitive"] is True


@pytest.mark.parametrize("key,expected", [
    ("MY_API_KEY", True),
    ("db_password", True),
    ("X_PASSPHRASE", True),
    ("OAUTH_CLIENT_SECRET", True),
    ("SLACK_TOKEN", True),
    ("GCP_CREDENTIALS", True),
    ("SIGNING_HASH", True),
    ("TIMEZONE", False),
    ("LOG_LEVEL", False),
])
def test_custom_variable_sensitivity_by_name(key, expected):
    meta = env_config.get_variable_metadata(key)
    assert meta["sensitive"] is expected
