"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/env_file.py

Helpers for reading and updating the host .env file.

The encoding mirrors env_quote_value / env_unquote_value in setup.sh so that
values written by the installer and by the management console round-trip
identically through docker compose, `source .env` and this parser:

  * plain values ([A-Za-z0-9_./:@,+=%-]) are written unquoted
  * other values without a single quote are written '...' (literal)
  * values containing a single quote are written "..." with \\ " $ escaped
  * newlines, and values with both a single quote and a backtick, are
    rejected (compose and bash disagree on escaping ` inside "...")

Part of the "n8n_nginx/n8n_management" suite
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import os
import re
from typing import Optional

_PLAIN_VALUE = re.compile(r"^[A-Za-z0-9_./:@,+=%-]*$")
_KEY_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def encode_env_value(value: str) -> str:
    """Encode a value for a .env line. Raises ValueError for newlines."""
    if "\n" in value or "\r" in value:
        raise ValueError("Value must not contain newlines")
    if "'" in value and "`" in value:
        raise ValueError("Value must not contain both ' and `")
    if _PLAIN_VALUE.match(value):
        return value
    if "'" not in value:
        return f"'{value}'"
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
    )
    return f'"{escaped}"'


def decode_env_value(raw: str) -> str:
    """Decode the right-hand side of a KEY=VALUE line."""
    raw = raw.lstrip()
    if raw.startswith("'"):
        end = raw.find("'", 1)
        return raw[1:] if end == -1 else raw[1:end]
    if raw.startswith('"'):
        out = []
        i = 1
        while i < len(raw):
            ch = raw[i]
            if ch == "\\" and i + 1 < len(raw):
                out.append(raw[i + 1])
                i += 2
                continue
            if ch == '"':
                break
            out.append(ch)
            i += 1
        return "".join(out)
    # Unquoted: drop an inline " # comment" and trailing whitespace
    raw = re.split(r"\s#", raw, maxsplit=1)[0]
    return raw.rstrip()


def parse_env_line(line: str) -> Optional[tuple]:
    """Return (key, raw_value) for a KEY=VALUE line, or None."""
    stripped = line.rstrip("\r\n")
    if not stripped.strip() or stripped.lstrip().startswith("#"):
        return None
    match = _KEY_LINE.match(stripped)
    if not match:
        return None
    return match.group(1), match.group(2)


def read_env_value(path: str, key: str) -> Optional[str]:
    """Return the decoded value of key (last occurrence wins), or None."""
    if not os.path.exists(path):
        return None
    value = None
    with open(path, "r") as f:
        for line in f:
            parsed = parse_env_line(line)
            if parsed and parsed[0] == key:
                value = decode_env_value(parsed[1])
    return value


def update_env_file_key(path: str, key: str, value: str) -> None:
    """
    Set key=value in the .env file, leaving every other line (comments,
    ordering, other keys and their quoting) untouched.

    The file is rewritten in place (it is bind-mounted into the container, so
    an atomic rename is not possible); its permissions are preserved.
    """
    new_line = f"{key}={encode_env_value(value)}\n"
    lines = []
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.readlines()

    out = []
    replaced = False
    for line in lines:
        parsed = parse_env_line(line)
        if parsed and parsed[0] == key:
            if not replaced:
                out.append(new_line)
                replaced = True
            continue
        out.append(line)

    if not replaced:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append(new_line)

    existed = os.path.exists(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.writelines(out)
    if not existed:
        os.chmod(path, 0o600)
