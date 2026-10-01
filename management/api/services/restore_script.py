"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/restore_script.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Renders the bare-metal restore.sh that is embedded in every backup archive
and can be downloaded on its own for use with older archives.

The script body lives in management/scripts/restore.sh.tpl (shipped in the
image as /app/scripts/restore.sh.tpl) so it can be linted with shellcheck.
"""

import os
from functools import lru_cache
from pathlib import Path

# Bump whenever restore.sh.tpl changes in a way operators should know about.
# Recorded in each archive's metadata.json as "restore_script_version".
RESTORE_SCRIPT_VERSION = "3.2.1"

_PLACEHOLDER = "__RESTORE_SCRIPT_VERSION__"
_TEMPLATE_NAME = "restore.sh.tpl"


def _template_candidates() -> list[Path]:
    candidates = []
    override = os.environ.get("RESTORE_SCRIPT_TEMPLATE")
    if override:
        candidates.append(Path(override))
    # /app/api/services/restore_script.py -> /app/scripts (container)
    # management/api/services/restore_script.py -> management/scripts (repo)
    candidates.append(Path(__file__).resolve().parents[2] / "scripts" / _TEMPLATE_NAME)
    candidates.append(Path("/app/scripts") / _TEMPLATE_NAME)
    return candidates


@lru_cache(maxsize=1)
def render_restore_script() -> str:
    """Return the current restore.sh contents. Raises FileNotFoundError if the template is missing."""
    for path in _template_candidates():
        if path.is_file():
            template = path.read_text(encoding="utf-8")
            if _PLACEHOLDER not in template:
                raise ValueError(f"{path} does not contain the {_PLACEHOLDER} placeholder")
            return template.replace(_PLACEHOLDER, RESTORE_SCRIPT_VERSION)
    searched = ", ".join(str(p) for p in _template_candidates())
    raise FileNotFoundError(f"restore.sh template not found (searched: {searched})")
