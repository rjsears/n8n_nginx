"""
Every column on the system-notification models is either read by the
dispatch path or explicitly classified here as not (yet) enforced.

A stored setting that nothing reads is worse than no setting: it looks
configured. This test forces every column into one of three buckets and
fails when a column moves between them without the list being updated.

The "phase" tags in UNENFORCED_PENDING refer to the notification-enforcement
work plan: phase 2 (done) built one gate consulted by every delivery path
(api/services/notification_gate.py); phase 3 (done) wrote producers for the
registered events that had none (api/services/system_monitors.py); phase 4
removes or hides the controls that will not be built (digest, flapping,
emergency contact, custom targets).
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

# Stored, surfaced by the API, never read by dispatch. Each entry names the
# phase of the work plan that decides its fate. Enforcing one MUST remove it
# from this map, or the test fails.
UNENFORCED_PENDING: Dict[str, str] = {
    # Phase 4: remove or defer
    "flapping_enabled": "phase 4 - deferred", "flapping_threshold_count": "phase 4 - deferred",
    "flapping_threshold_minutes": "phase 4 - deferred", "flapping_summary_interval": "phase 4 - deferred",
    "event_count_in_window": "phase 4 - deferred", "window_start": "phase 4 - deferred",
    "is_flapping": "phase 4 - deferred", "flapping_started_at": "phase 4 - deferred",
    "last_summary_at": "phase 4 - deferred",
    "include_in_digest": "phase 4 - deferred", "digest_enabled": "phase 4 - deferred",
    "digest_time": "phase 4 - deferred", "digest_severity_levels": "phase 4 - deferred",
    "last_digest_sent": "phase 4 - deferred",
    "emergency_contact_id": "phase 4 - remove",
    "custom_targets": "phase 4 - remove",
    # The delayed L2 path was removed in phase 1 (it escalated unconditionally
    # and its "acknowledged" promise had no acknowledgement behind it). The
    # timeout columns it read are now inert until phase 4 removes them.
    "escalation_timeout_minutes": "phase 4 - remove (delayed L2 path deleted in phase 1)",
}

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
    unclassified = _all_columns() - STRUCTURAL - ENFORCED - set(UNENFORCED_PENDING)
    assert not unclassified, (
        f"new column(s) with no classification: {sorted(unclassified)}. "
        "Wire them into dispatch and add to ENFORCED, or add to UNENFORCED_PENDING with a phase."
    )


def test_classifications_do_not_overlap():
    assert not (STRUCTURAL & ENFORCED)
    assert not (STRUCTURAL & set(UNENFORCED_PENDING))
    assert not (ENFORCED & set(UNENFORCED_PENDING))


def test_classified_columns_exist():
    stale = (ENFORCED | set(UNENFORCED_PENDING)) - _all_columns()
    assert not stale, f"classified but no longer a column: {sorted(stale)}"


@pytest.mark.parametrize("column", sorted(ENFORCED))
def test_enforced_column_is_read_by_dispatch_code(column):
    assert _is_referenced(column, _enforcement_source()), (
        f"'{column}' is listed as ENFORCED but nothing under api/services or api/tasks reads it"
    )


@pytest.mark.parametrize("column", sorted(set(UNENFORCED_PENDING) - AMBIGUOUS))
def test_pending_column_is_still_unenforced(column):
    """When one of these gets wired in, move it to ENFORCED."""
    assert not _is_referenced(column, _enforcement_source()), (
        f"'{column}' is now referenced under api/services or api/tasks; "
        f"move it from UNENFORCED_PENDING ({UNENFORCED_PENDING[column]}) to ENFORCED"
    )
