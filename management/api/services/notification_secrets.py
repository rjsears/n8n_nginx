"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/notification_secrets.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Secret handling for notification channel configs.

Two functions, used together:

* ``redact_config`` produces the copy of a channel config that may leave the
  API. Every endpoint that returns a channel goes through it.
* ``merge_config_secrets`` is applied to an incoming config on update. Any
  secret value that comes back as the mask, or as exactly the redacted form
  the API handed out, or that is omitted, keeps the stored value. This is
  what lets the edit dialog round-trip a redacted config without
  overwriting a real token with ``***``.

What counts as secret:

* any key whose name contains pass / token / secret / key / credential /
  auth (``smtp_password``, ``token``, ``api_key``, ``webhook_secret`` ...);
* ``headers`` values whose header name looks like a credential
  (Authorization, Cookie, X-Api-Key, *token*, *secret*, *signature* ...);
* URLs: user:password in the authority and secret-looking query parameters
  are masked; an Apprise URL is masked entirely after the scheme (its path
  is the token for most services), and a webhook URL keeps only scheme and
  host (Discord/Slack style webhooks carry the token in the path).
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "***"

SECRET_KEY_PATTERN = re.compile(r"pass|token|secret|key|credential|auth", re.IGNORECASE)
SECRET_HEADER_PATTERN = re.compile(
    r"auth|cookie|token|secret|key|signature|pass|credential", re.IGNORECASE
)
SECRET_QUERY_PATTERN = re.compile(r"pass|token|secret|key|sig|auth|credential", re.IGNORECASE)

# Keys that hold URLs, and how much of each URL is kept visible.
URL_KEYS = ("url", "server")


def is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_PATTERN.search(str(key)))


def _mask_netloc(parts) -> str:
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    if parts.password:
        return f"{parts.username or ''}:{MASK}@{host}"
    if parts.username:
        # A bare userinfo component is often a token (``https://TOKEN@host``)
        return f"{MASK}@{host}"
    return host


def redact_url(url: Any, service_type: Optional[str] = None, key: str = "url") -> Any:
    """Mask the credential-bearing parts of a URL. Non-strings pass through."""
    if not isinstance(url, str) or not url:
        return url

    if service_type == "apprise" and key == "url":
        scheme, sep, rest = url.partition("://")
        return f"{scheme}://{MASK}" if sep and rest else MASK

    try:
        parts = urlsplit(url)
    except ValueError:
        return MASK
    if not parts.scheme or not parts.netloc:
        return url

    netloc = _mask_netloc(parts)
    path = parts.path
    if service_type == "webhook" and key == "url" and path not in ("", "/"):
        path = f"/{MASK}"
    query = parts.query
    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        query = urlencode(
            [(k, MASK if SECRET_QUERY_PATTERN.search(k) else v) for k, v in pairs], safe="*"
        )
    return urlunsplit((parts.scheme, netloc, path, query, parts.fragment))


def _redact_headers(headers: Any) -> Any:
    if not isinstance(headers, dict):
        return headers
    return {
        name: (MASK if SECRET_HEADER_PATTERN.search(str(name)) and value not in (None, "") else value)
        for name, value in headers.items()
    }


def _redact_value(key: str, value: Any, service_type: Optional[str]) -> Any:
    if key == "headers":
        return _redact_headers(value)
    if key in URL_KEYS:
        return redact_url(value, service_type, key)
    if is_secret_key(key) and isinstance(value, str) and value:
        return MASK
    return value


def redact_config(config: Optional[Dict[str, Any]], service_type: Optional[str] = None) -> Dict[str, Any]:
    """Copy of a channel config that is safe to return to a client."""
    return {key: _redact_value(key, value, service_type) for key, value in (config or {}).items()}


def _keep_stored(incoming: Any, stored: Any, redacted_stored: Any) -> bool:
    """True when ``incoming`` is just the masked echo of ``stored``."""
    if incoming == stored:
        return False
    return incoming == MASK or incoming == redacted_stored


def merge_config_secrets(
    stored: Optional[Dict[str, Any]],
    incoming: Optional[Dict[str, Any]],
    service_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    The config to store when a client sends ``incoming`` for a channel whose
    current config is ``stored``.

    Secret values that are omitted, equal to the mask, or equal to the
    redacted form of the stored value keep the stored value. A secret sent
    as an empty string clears it (that is how a user removes a token).
    Non-secret keys behave as a plain replacement.
    """
    stored = stored or {}
    merged = copy.deepcopy(incoming or {})

    for key, stored_value in stored.items():
        if key == "headers" and isinstance(stored_value, dict):
            incoming_headers = merged.get("headers")
            if incoming_headers is None:
                merged["headers"] = copy.deepcopy(stored_value)
                continue
            if not isinstance(incoming_headers, dict):
                continue
            redacted_headers = _redact_headers(stored_value)
            for name, value in stored_value.items():
                if not SECRET_HEADER_PATTERN.search(str(name)):
                    continue
                if name not in incoming_headers:
                    # Left out of a headers dict the client did send: removed on purpose.
                    continue
                if _keep_stored(incoming_headers[name], value, redacted_headers.get(name)):
                    incoming_headers[name] = value
            continue

        secret = is_secret_key(key) or key in URL_KEYS
        if not secret:
            continue
        if key not in merged:
            if is_secret_key(key):
                merged[key] = copy.deepcopy(stored_value)
            continue
        if _keep_stored(merged[key], stored_value, _redact_value(key, stored_value, service_type)):
            merged[key] = copy.deepcopy(stored_value)

    return merged
