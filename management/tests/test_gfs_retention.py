"""Unit tests for the pure GFS retention selection (api/services/retention.py)."""

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# Load retention.py by path: it has no app imports, and going through the
# api.services package would pull in the whole application (DB, Docker, ...).
_RETENTION_PATH = Path(__file__).resolve().parents[1] / "api" / "services" / "retention.py"
_spec = importlib.util.spec_from_file_location("gfs_retention_under_test", _RETENTION_PATH)
retention = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = retention  # dataclasses need the module registered
_spec.loader.exec_module(retention)

RetentionConfig = retention.RetentionConfig
select_gfs_retention = retention.select_gfs_retention

UTC = timezone.utc


def _daily_series(days, start=datetime(2026, 9, 30, 2, 0, tzinfo=UTC)):
    """One backup per day going back `days` days; id 1 is the newest."""
    return [(i + 1, start - timedelta(days=i)) for i in range(days)]


def _partition_ok(backups, keep, delete):
    ids = {b[0] for b in backups}
    assert keep | delete == ids
    assert not keep & delete


def test_empty_input():
    keep, delete = select_gfs_retention([], RetentionConfig())
    assert keep == set() and delete == set()


def test_single_backup_is_always_kept_even_with_zero_tiers():
    backups = [(1, datetime(2020, 1, 1, tzinfo=UTC))]
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=0, weekly=0, monthly=0, min_count=0))
    assert keep == {1}
    assert delete == set()


def test_min_count_never_below_one():
    cfg = RetentionConfig.from_values(0, 0, 0, 0)
    assert cfg.min_count == 1
    backups = _daily_series(5)
    keep, delete = select_gfs_retention(backups, cfg)
    assert keep == {1}
    assert delete == {2, 3, 4, 5}


def test_from_values_none_uses_model_defaults():
    cfg = RetentionConfig.from_values(None, None, None, None)
    assert (cfg.daily, cfg.weekly, cfg.monthly, cfg.min_count) == (7, 4, 6, 3)


def test_daily_only_keeps_n_most_recent_days():
    backups = _daily_series(20)
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=7, weekly=0, monthly=0, min_count=1))
    assert keep == set(range(1, 8))
    _partition_ok(backups, keep, delete)


def test_multiple_backups_per_day_keep_newest_of_day():
    day = datetime(2026, 9, 29, tzinfo=UTC)
    backups = [
        (10, day + timedelta(hours=1)),
        (11, day + timedelta(hours=13)),
        (12, day + timedelta(hours=23)),  # newest of the 29th
        (13, day - timedelta(hours=1)),   # 28th, 23:00
        (14, day - timedelta(hours=5)),   # 28th, 19:00
    ]
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=2, weekly=0, monthly=0, min_count=1))
    assert keep == {12, 13}
    assert delete == {10, 11, 14}


def test_min_count_keeps_newest_regardless_of_buckets():
    day = datetime(2026, 9, 29, tzinfo=UTC)
    backups = [(i, day + timedelta(hours=i)) for i in range(1, 7)]  # 6 on the same day
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=1, weekly=0, monthly=0, min_count=3))
    assert keep == {6, 5, 4}
    assert delete == {1, 2, 3}


def test_default_config_over_a_year_of_dailies():
    # 400 daily backups ending Wed 2026-09-30.
    backups = _daily_series(400)
    keep, delete = select_gfs_retention(backups, RetentionConfig())
    _partition_ok(backups, keep, delete)
    by_id = dict(backups)
    kept_dates = sorted((by_id[i].date() for i in keep), reverse=True)

    # 7 dailies: 2026-09-24 .. 2026-09-30
    daily_expected = {datetime(2026, 9, 30).date() - timedelta(days=i) for i in range(7)}
    assert daily_expected <= set(kept_dates)

    # Weekly: newest backup of each of the 4 most recent ISO weeks. Those are the
    # Sundays 2026-09-27, 09-20, 09-13 plus Wed 2026-09-30 (current week).
    weekly_expected = {
        datetime(2026, 9, 30).date(),
        datetime(2026, 9, 27).date(),
        datetime(2026, 9, 20).date(),
        datetime(2026, 9, 13).date(),
    }
    assert weekly_expected <= set(kept_dates)

    # Monthly: newest backup of each of the 6 most recent months:
    # 09-30, 08-31, 07-31, 06-30, 05-31, 04-30
    monthly_expected = {
        datetime(2026, 9, 30).date(),
        datetime(2026, 8, 31).date(),
        datetime(2026, 7, 31).date(),
        datetime(2026, 6, 30).date(),
        datetime(2026, 5, 31).date(),
        datetime(2026, 4, 30).date(),
    }
    assert monthly_expected <= set(kept_dates)

    assert set(kept_dates) == daily_expected | weekly_expected | monthly_expected
    # Nothing older than the oldest monthly bucket survives.
    assert min(kept_dates) == datetime(2026, 4, 30).date()


def test_buckets_only_count_days_that_have_backups():
    # Backups stopped 100 days ago: retention must not age them all out.
    start = datetime(2026, 6, 1, 12, tzinfo=UTC)
    backups = _daily_series(10, start=start)
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=7, weekly=0, monthly=0, min_count=1))
    assert keep == set(range(1, 8))


def test_iso_week_boundary():
    # Sunday 2026-09-27 and Monday 2026-09-28 are in different ISO weeks.
    backups = [
        (1, datetime(2026, 9, 28, 1, tzinfo=UTC)),   # Mon, week 40
        (2, datetime(2026, 9, 27, 23, tzinfo=UTC)),  # Sun, week 39
        (3, datetime(2026, 9, 22, 1, tzinfo=UTC)),   # Tue, week 39
    ]
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=0, weekly=2, monthly=0, min_count=1))
    assert keep == {1, 2}
    assert delete == {3}


def test_iso_week_year_boundary():
    # 2026-12-31 (Thu) and 2027-01-01 (Fri) are both in ISO week 2026-W53.
    backups = [
        (1, datetime(2027, 1, 1, 12, tzinfo=UTC)),
        (2, datetime(2026, 12, 31, 12, tzinfo=UTC)),
        (3, datetime(2026, 12, 27, 12, tzinfo=UTC)),  # Sun, 2026-W52
    ]
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=0, weekly=2, monthly=0, min_count=1))
    assert keep == {1, 3}
    assert delete == {2}


def test_timezone_changes_day_bucket():
    # 2026-09-30 05:00 UTC and 2026-09-29 20:00 UTC are both 2026-09-29 in Los Angeles.
    backups = [
        (1, datetime(2026, 9, 30, 5, tzinfo=UTC)),
        (2, datetime(2026, 9, 29, 20, tzinfo=UTC)),
        (3, datetime(2026, 9, 28, 20, tzinfo=UTC)),
    ]
    cfg = RetentionConfig(daily=2, weekly=0, monthly=0, min_count=1)

    keep_utc, _ = select_gfs_retention(backups, cfg, UTC)
    assert keep_utc == {1, 2}  # different UTC days

    keep_la, delete_la = select_gfs_retention(backups, cfg, ZoneInfo("America/Los_Angeles"))
    assert keep_la == {1, 3}  # 1 and 2 share a local day; newest wins
    assert delete_la == {2}


def test_naive_datetimes_treated_as_utc():
    backups = [
        (1, datetime(2026, 9, 30, 5)),
        (2, datetime(2026, 9, 30, 4, tzinfo=UTC)),
    ]
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=1, weekly=0, monthly=0, min_count=1))
    assert keep == {1}
    assert delete == {2}


def test_deterministic_tie_break_on_identical_timestamps():
    ts = datetime(2026, 9, 30, 2, tzinfo=UTC)
    backups = [(5, ts), (7, ts), (6, ts)]
    cfg = RetentionConfig(daily=1, weekly=0, monthly=0, min_count=1)
    for order in (backups, list(reversed(backups))):
        keep, delete = select_gfs_retention(order, cfg)
        assert keep == {7}
        assert delete == {5, 6}


def test_input_order_does_not_matter():
    backups = _daily_series(60)
    cfg = RetentionConfig()
    a = select_gfs_retention(backups, cfg)
    b = select_gfs_retention(list(reversed(backups)), cfg)
    assert a == b


@pytest.mark.parametrize("hours_between", [1, 6, 24, 24 * 7])
def test_newest_always_kept(hours_between):
    start = datetime(2026, 9, 30, 12, tzinfo=UTC)
    backups = [(i, start - timedelta(hours=i * hours_between)) for i in range(1, 200)]
    keep, delete = select_gfs_retention(backups, RetentionConfig(daily=1, weekly=1, monthly=1, min_count=1))
    assert 1 in keep
    _partition_ok(backups, keep, delete)
