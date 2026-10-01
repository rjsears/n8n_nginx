"""
Unit tests for api.services.notification_gate.evaluate: pure decisions over
plain objects, no database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from api.services import notification_gate as gate


def _settings(**overrides):
    base = {
        "maintenance_mode": False, "maintenance_until": None, "maintenance_reason": None,
        "quiet_hours_enabled": False, "quiet_hours_start": "22:00", "quiet_hours_end": "07:00",
        "quiet_hours_reduce_priority": True,
        "blackout_enabled": False, "blackout_start": None, "blackout_end": None,
        "max_notifications_per_hour": 50, "notifications_this_hour": 0, "hour_started_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _event(**overrides):
    base = {"event_type": "container_stopped", "frequency": "every_time", "cooldown_minutes": 5}
    base.update(overrides)
    return SimpleNamespace(**base)


def _state(last_sent_minutes_ago: float):
    return SimpleNamespace(last_sent_at=NOW - timedelta(minutes=last_sent_minutes_ago))


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _window_around(now: datetime, before_minutes=60, after_minutes=60):
    """(start, end) HH:MM strings in the console time zone bracketing ``now``."""
    local = gate.local_now(now)
    return (
        (local - timedelta(minutes=before_minutes)).strftime("%H:%M"),
        (local + timedelta(minutes=after_minutes)).strftime("%H:%M"),
    )


# --- helpers -----------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("00:00", 0), ("07:30", 450), ("23:59", 1439),
    ("24:00", None), ("7:61", None), ("garbage", None), (None, None), ("", None),
])
def test_parse_hhmm(value, expected):
    assert gate.parse_hhmm(value) == expected


@pytest.mark.parametrize("hour,expected", [(23, True), (2, True), (6, True), (7, False), (12, False), (21, False)])
def test_overnight_window_wraps_midnight(hour, expected):
    local = datetime(2026, 1, 1, hour, 30)
    assert gate.in_daily_window(local, "22:00", "07:00") is expected


@pytest.mark.parametrize("hour,expected", [(8, False), (9, True), (12, True), (17, False)])
def test_same_day_window(hour, expected):
    local = datetime(2026, 1, 1, hour, 0)
    assert gate.in_daily_window(local, "09:00", "17:00") is expected


def test_empty_or_equal_window_is_never_active():
    local = datetime(2026, 1, 1, 12, 0)
    assert gate.in_daily_window(local, None, "07:00") is False
    assert gate.in_daily_window(local, "12:00", "12:00") is False


def test_effective_window_prefers_frequency_over_cooldown():
    assert gate.effective_window(_event(frequency="once_per_day", cooldown_minutes=5)) == (1440, "frequency (once_per_day)")
    assert gate.effective_window(_event(frequency="every_time", cooldown_minutes=15)) == (15, "cooldown (15min)")
    assert gate.effective_window(_event(frequency="every_time", cooldown_minutes=0)) == (0, "cooldown (0min)")


def test_unknown_frequency_falls_back_to_cooldown():
    assert gate.effective_window(_event(frequency="fortnightly", cooldown_minutes=7)) == (7, "cooldown (7min)")


# --- maintenance -------------------------------------------------------------------------------

def test_no_settings_row_allows():
    decision = gate.evaluate(global_settings=None, priority="high", now=NOW)
    assert decision.allow and decision.priority == "high"


def test_maintenance_active_denies():
    gs = _settings(maintenance_mode=True, maintenance_until=NOW + timedelta(hours=1))
    decision = gate.evaluate(global_settings=gs, now=NOW)
    assert not decision.allow and decision.reason == "maintenance"


def test_maintenance_without_end_denies():
    gs = _settings(maintenance_mode=True, maintenance_until=None)
    assert gate.evaluate(global_settings=gs, now=NOW).reason == "maintenance"


def test_maintenance_expired_clears_and_allows():
    gs = _settings(maintenance_mode=True, maintenance_until=NOW - timedelta(seconds=1), maintenance_reason="x")
    decision = gate.evaluate(global_settings=gs, now=NOW)
    assert decision.allow
    assert gs.maintenance_mode is False and gs.maintenance_until is None and gs.maintenance_reason is None


# --- blackout ----------------------------------------------------------------------------------

def test_blackout_denies_everything_including_critical():
    start, end = _window_around(NOW)
    gs = _settings(blackout_enabled=True, blackout_start=start, blackout_end=end)
    decision = gate.evaluate(global_settings=gs, priority="critical", now=NOW)
    assert not decision.allow and decision.reason == "blackout"


def test_blackout_outside_window_allows():
    start, end = _window_around(NOW + timedelta(hours=6), 30, 30)
    gs = _settings(blackout_enabled=True, blackout_start=start, blackout_end=end)
    assert gate.evaluate(global_settings=gs, now=NOW).allow


# --- frequency / cooldown ----------------------------------------------------------------------

def test_frequency_window_denies_and_names_the_dial():
    decision = gate.evaluate(
        global_settings=_settings(), event=_event(frequency="once_per_hour", cooldown_minutes=0),
        state=_state(last_sent_minutes_ago=30), now=NOW,
    )
    assert not decision.allow and decision.reason == "frequency (once_per_hour)"


def test_frequency_window_elapsed_allows():
    decision = gate.evaluate(
        global_settings=_settings(), event=_event(frequency="once_per_hour"),
        state=_state(last_sent_minutes_ago=61), now=NOW,
    )
    assert decision.allow


def test_cooldown_applies_only_to_every_time():
    denied = gate.evaluate(
        global_settings=_settings(), event=_event(frequency="every_time", cooldown_minutes=15),
        state=_state(last_sent_minutes_ago=10), now=NOW,
    )
    assert denied.reason == "cooldown (15min)"


def test_no_prior_send_allows():
    decision = gate.evaluate(global_settings=_settings(), event=_event(frequency="once_per_day"), state=None, now=NOW)
    assert decision.allow
    decision = gate.evaluate(
        global_settings=_settings(), event=_event(frequency="once_per_day"),
        state=SimpleNamespace(last_sent_at=None), now=NOW,
    )
    assert decision.allow


# --- quiet hours ---------------------------------------------------------------------------------

def test_quiet_hours_reduce_lowers_non_critical_priority():
    start, end = _window_around(NOW)
    gs = _settings(quiet_hours_enabled=True, quiet_hours_start=start, quiet_hours_end=end, quiet_hours_reduce_priority=True)
    decision = gate.evaluate(global_settings=gs, priority="high", now=NOW)
    assert decision.allow and decision.priority == "low"
    assert decision.notes == ["quiet_hours: priority high -> low"]


def test_quiet_hours_mute_denies_non_critical():
    start, end = _window_around(NOW)
    gs = _settings(quiet_hours_enabled=True, quiet_hours_start=start, quiet_hours_end=end, quiet_hours_reduce_priority=False)
    decision = gate.evaluate(global_settings=gs, priority="high", now=NOW)
    assert not decision.allow and decision.reason == "quiet_hours"


@pytest.mark.parametrize("reduce", [True, False])
def test_quiet_hours_never_touch_critical(reduce):
    start, end = _window_around(NOW)
    gs = _settings(quiet_hours_enabled=True, quiet_hours_start=start, quiet_hours_end=end, quiet_hours_reduce_priority=reduce)
    decision = gate.evaluate(global_settings=gs, priority="critical", now=NOW)
    assert decision.allow and decision.priority == "critical" and decision.notes == []


def test_quiet_hours_outside_window_no_effect():
    start, end = _window_around(NOW + timedelta(hours=6), 30, 30)
    gs = _settings(quiet_hours_enabled=True, quiet_hours_start=start, quiet_hours_end=end, quiet_hours_reduce_priority=False)
    decision = gate.evaluate(global_settings=gs, priority="high", now=NOW)
    assert decision.allow and decision.priority == "high"


# --- rate limit ----------------------------------------------------------------------------------

def test_rate_limit_opens_window_on_first_evaluation():
    gs = _settings(max_notifications_per_hour=3)
    assert gate.evaluate(global_settings=gs, now=NOW).allow
    assert gs.hour_started_at == NOW and gs.notifications_this_hour == 0


def test_rate_limit_denies_at_cap():
    gs = _settings(max_notifications_per_hour=3, notifications_this_hour=3, hour_started_at=NOW - timedelta(minutes=10))
    decision = gate.evaluate(global_settings=gs, now=NOW)
    assert not decision.allow and decision.reason == "rate_limit (3/hour)"


def test_rate_limit_window_resets_after_an_hour():
    gs = _settings(max_notifications_per_hour=3, notifications_this_hour=3, hour_started_at=NOW - timedelta(hours=1))
    decision = gate.evaluate(global_settings=gs, now=NOW)
    assert decision.allow
    assert gs.notifications_this_hour == 0 and gs.hour_started_at == NOW


def test_record_delivery_counts_and_rolls():
    gs = _settings(max_notifications_per_hour=3, notifications_this_hour=2, hour_started_at=NOW - timedelta(minutes=59))
    gate.record_delivery(gs, NOW)
    assert gs.notifications_this_hour == 3
    gate.record_delivery(gs, NOW + timedelta(minutes=2))
    assert gs.notifications_this_hour == 1 and gs.hour_started_at == NOW + timedelta(minutes=2)


def test_record_delivery_tolerates_missing_settings():
    gate.record_delivery(None, NOW)


# --- ordering ----------------------------------------------------------------------------------

def test_maintenance_wins_over_rate_limit_and_does_not_touch_the_counter():
    gs = _settings(maintenance_mode=True, notifications_this_hour=7, hour_started_at=NOW)
    decision = gate.evaluate(global_settings=gs, now=NOW)
    assert decision.reason == "maintenance" and gs.notifications_this_hour == 7


def test_frequency_wins_over_quiet_hours():
    start, end = _window_around(NOW)
    gs = _settings(quiet_hours_enabled=True, quiet_hours_start=start, quiet_hours_end=end, quiet_hours_reduce_priority=False)
    decision = gate.evaluate(
        global_settings=gs, event=_event(frequency="once_per_day"), state=_state(5), priority="high", now=NOW,
    )
    assert decision.reason == "frequency (once_per_day)"
