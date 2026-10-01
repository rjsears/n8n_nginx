"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/env_file.py

Helpers for reading and updating the host .env file.

The encoding mirrors env_quote_value / env_unquote_value in setup.sh so that
values written by the installer and by the management console round-trip
identically through docker compose, `source .env` and this parser:

  * plain values ([A-Za-z0-9_./:@,+=%-]) are written unquoted
  * other values without a single quote are written '...' (literal)
  * values containing a single quote, or ending in a backslash (compose would
    read '...\\' as an escaped closing quote), are written "..." with \\ " $
    escaped
  * newlines, and values with a backtick together with a single quote or a
    trailing backslash, are rejected (compose and bash disagree on escaping `
    inside "...")

Part of the "n8n_nginx/n8n_management" suite
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import os
import re
import tempfile
from typing import Iterable, Optional

_PLAIN_VALUE = re.compile(r"^[A-Za-z0-9_./:@,+=%-]*$")
_KEY_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
ENV_KEY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
_VALID_KEY = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")


def is_valid_env_key(key: str) -> bool:
    """True if key is a plain shell/compose variable name."""
    return isinstance(key, str) and bool(_VALID_KEY.match(key))


def validate_env_key(key: str) -> str:
    """Return key, or raise ValueError if it is not a plain variable name."""
    if not is_valid_env_key(key):
        raise ValueError(f"Invalid variable name {key!r}: must match {ENV_KEY_PATTERN}")
    return key


def encode_env_value(value: str) -> str:
    """Encode a value for a .env line. Raises ValueError for values that cannot be stored."""
    if "\n" in value or "\r" in value:
        raise ValueError("Value must not contain newlines")
    ends_with_backslash = value.endswith("\\")
    if "`" in value and ("'" in value or ends_with_backslash):
        raise ValueError("Value must not contain ` together with ' or a trailing backslash")
    if _PLAIN_VALUE.match(value):
        return value
    if "'" not in value and not ends_with_backslash:
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


def write_file_atomic(path: str, lines: Iterable[str], default_mode: int = 0o600) -> None:
    """
    Replace path with the given content atomically: write a temp file in the
    same directory, copy the original's mode/owner (default_mode for a new
    file), fsync, then os.replace. A crash or a full disk never leaves a
    truncated .env behind.

    The project directory (not the .env file itself) is bind-mounted into the
    management container, so renaming over the file is safe here.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        st = os.stat(path)
    except FileNotFoundError:
        st = None

    fd, tmp_path = tempfile.mkstemp(prefix=".env.tmp.", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        if st is not None:
            os.chmod(tmp_path, st.st_mode & 0o7777)
            try:
                os.chown(tmp_path, st.st_uid, st.st_gid)
            except OSError:
                pass  # not permitted (non-root); keep our own ownership
        else:
            os.chmod(tmp_path, default_mode)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    try:
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def update_env_file_key(path: str, key: str, value: str) -> None:
    """
    Set key=value in the .env file, leaving every other line (comments,
    ordering, other keys and their quoting) untouched.

    Raises ValueError for an invalid key or a value that cannot be encoded.
    The file is replaced atomically and its permissions are preserved.
    """
    validate_env_key(key)
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

    write_file_atomic(path, out)
