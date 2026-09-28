"""
Every column on the system-notification models is either read by the
dispatch path or explicitly classified here as not (yet) enforced.

A stored setting that nothing reads is worse than no setting: it looks
configured. This test forces every column into one of three buckets and
fails when a column moves between them without the list being updated.

Buckets: STRUCTURAL (identity and presentation), ENFORCED (read by the
gate or a producer), UNENFORCED_PENDING (stored, exposed, decision pending;
empty today) and RETIRED (never enforced, removed from the API and UI,
column kept for existing databases).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Set

import pytest

MANAGEMENT_DIR = Path(__file__).resolve().parents[1]
API_DIR = MANAGEMENT_DIR / "api"

# Where enforcement lives. Models, schemas and routers only store and echo.
ENFORCEMENT_DIRS = (API_DIR / "services", API_DIR / "tasks")

# Identity, bookkeeping and presentation columns. Not settings; never gated on.
STRUCTURAL: Set[str] = {
    "id", "created_at", "updated_at",
    "event_type", "event_id", "target_id", "target_type", "channel_id", "group_id",
    "display_name", "description", "icon", "category", "container_name",
    "maintenance_reason",
}

# Settings the dispatch path reads. Removing a read of one of these fails.
ENFORCED: Set[str] = {
    # SystemNotificationEvent
    "enabled", "severity", "cooldown_minutes", "frequency", "escalation_enabled",
    "thresholds", "notify_on_recovery",
    # SystemNotificationGlobalSettings
    "maintenance_mode", "maintenance_until",
    "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end", "quiet_hours_reduce_priority",
    "blackout_enabled", "blackout_start", "blackout_end",
    "max_notifications_per_hour", "notifications_this_hour", "hour_started_at",
    # SystemNotificationContainerConfig
    "monitor_unhealthy", "monitor_restart", "monitor_stopped", "monitor_high_cpu", "monitor_high_memory",
    "cpu_threshold", "memory_threshold",
    # SystemNotificationState
    "last_sent_at", "escalation_sent", "escalation_triggered_at",
    # SystemNotificationTarget
    "escalation_level",
}

# Never enforced and not going to be. Phase 4 removed them from the API,
# the UI and the docs; the columns stay so existing databases keep loading.
# A retired column must not reappear in a schema, a router or the frontend.
RETIRED: Dict[str, str] = {
    "flapping_enabled": "flapping detection never built",
    "flapping_threshold_count": "flapping detection never built",
    "flapping_threshold_minutes": "flapping detection never built",
    "flapping_summary_interval": "flapping detection never built",
    "event_count_in_window": "flapping detection never built",
    "window_start": "flapping detection never built",
    "is_flapping": "flapping detection never built",
    "flapping_started_at": "flapping detection never built",
    "last_summary_at": "flapping detection never built",
    "include_in_digest": "digest never built",
    "digest_enabled": "digest never built",
    "digest_time": "digest never built",
    "digest_severity_levels": "digest never built",
    "last_digest_sent": "digest never built",
    "emergency_contact_id": "no defined semantics",
    "custom_targets": "no UI, never read",
    "escalation_timeout_minutes": "delayed L2 escalation removed",
}

# Stored, surfaced by the API, never read by dispatch: settings whose fate
# is still being decided. Enforcing one MUST remove it from this map, or
# the test fails. Empty since phase 3; a new column lands here only with a
# plan attached.
UNENFORCED_PENDING: Dict[str, str] = {}

# Names that also occur in unrelated code in the enforcement dirs, so a
# "must be unreferenced" assertion is not meaningful for them.
AMBIGUOUS: Set[str] = {
    "frequency",   # backup_schedules.frequency (hourly/daily/...) in tasks/scheduler.py
    "thresholds",  # generic word
}


def _models():
    import api.models  # noqa: F401
    from api.models.system_notifications import (
        SystemNotificationContainerConfig,
        SystemNotificationEvent,
        SystemNotificationGlobalSettings,
        SystemNotificationState,
        SystemNotificationTarget,
    )

    return (
        SystemNotificationEvent,
        SystemNotificationGlobalSettings,
        SystemNotificationContainerConfig,
        SystemNotificationState,
        SystemNotificationTarget,
    )


def _all_columns() -> Set[str]:
    return {column.name for model in _models() for column in model.__table__.columns}


def _enforcement_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for directory in ENFORCEMENT_DIRS
        for path in sorted(directory.rglob("*.py"))
    )


def _is_referenced(name: str, source: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", source) is not None


def test_every_column_is_classified():
    unclassified = _all_columns() - STRUCTURAL - ENFORCED - set(UNENFORCED_PENDING) - set(RETIRED)
    assert not unclassified, (
        f"new column(s) with no classification: {sorted(unclassified)}. "
        "Wire them into dispatch and add to ENFORCED, or add to UNENFORCED_PENDING with a plan."
    )


def test_classifications_do_not_overlap():
    buckets = [STRUCTURAL, ENFORCED, set(UNENFORCED_PENDING), set(RETIRED)]
    for i, a in enumerate(buckets):
        for b in buckets[i + 1:]:
            assert not (a & b), sorted(a & b)


def test_classified_columns_exist():
    stale = (ENFORCED | set(UNENFORCED_PENDING) | set(RETIRED)) - _all_columns()
    assert not stale, f"classified but no longer a column: {sorted(stale)}"


def _exposure_source() -> str:
    """Everything that can put a setting in front of a user: schemas, routers, frontend."""
    parts = []
    for directory, suffixes in (
        (API_DIR / "schemas", (".py",)),
        (API_DIR / "routers", (".py",)),
        (MANAGEMENT_DIR / "frontend" / "src", (".vue", ".js")),
    ):
        for path in sorted(directory.rglob("*")):
            if path.suffix in suffixes and path.is_file():
                parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


@pytest.mark.parametrize("column", sorted(RETIRED))
def test_retired_column_is_not_exposed_anywhere(column):
    """A retired setting must not come back through a schema, a router or the UI."""
    assert not _is_referenced(column, _exposure_source()), (
        f"'{column}' is RETIRED ({RETIRED[column]}) but is referenced by a schema, router or frontend file"
    )


@pytest.mark.parametrize("column", sorted(RETIRED))
def test_retired_column_is_not_read_by_dispatch(column):
    assert not _is_referenced(column, _enforcement_source()), (
        f"'{column}' is RETIRED but api/services or api/tasks reads it; either enforce it (move to ENFORCED) or remove the read"
    )


@pytest.mark.parametrize("column", sorted(ENFORCED))
def test_enforced_column_is_read_by_dispatch_code(column):
    assert _is_referenced(column, _enforcement_source()), (
        f"'{column}' is listed as ENFORCED but nothing under api/services or api/tasks reads it"
    )


def test_pending_columns_are_still_unenforced():
    """When one of these gets wired in, move it to ENFORCED. (Plain loop: the map may be empty.)"""
    source = _enforcement_source()
    wired = [c for c in sorted(set(UNENFORCED_PENDING) - AMBIGUOUS) if _is_referenced(c, source)]
    assert not wired, (
        f"now referenced under api/services or api/tasks; move from UNENFORCED_PENDING to ENFORCED: "
        + ", ".join(f"{c} ({UNENFORCED_PENDING[c]})" for c in wired)
    )
