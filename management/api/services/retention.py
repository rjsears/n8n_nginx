"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/retention.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Pure GFS (Grandfather-Father-Son) retention selection.

This module has no database or application imports so the selection rules can
be unit tested in isolation. PruningService.apply_gfs_retention() feeds it the
eligible backups (one backup type at a time) and acts on the result.

Rules (per call, i.e. per backup type):
  * Backups are ordered newest first (created_at desc, id desc as tie-break).
  * The newest ``min_count`` backups are always kept (at least 1, so the most
    recent successful backup is never deleted).
  * Daily tier: the newest backup of each of the ``daily`` most recent calendar
    days that contain a backup is kept.
  * Weekly tier: same with ISO weeks (Monday-Sunday), ``weekly`` buckets.
  * Monthly tier: same with calendar months, ``monthly`` buckets.
  * Buckets are computed in the given timezone. Naive datetimes are treated
    as UTC.
  * Backups without a created_at cannot be placed in a bucket; they are
    always kept and do not count towards any rule.
  * A backup kept by any rule is kept; everything else is selected for
    deletion.

select_floor_ids() computes the retention floor shared by every pruning path
(GFS, time/space/size based, critical space, pending deletions): the newest
max(min_count, 1) successful, not-deleted backups of each backup type are never
marked for deletion or deleted automatically.

"Most recent buckets that contain a backup" (rather than "the last N calendar
days") means that if backups stop being taken, the remaining ones are not
aged out: retention never deletes more because time has passed without new
backups.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from typing import Callable, Dict, Hashable, Iterable, List, Optional, Set, Tuple

# Model/UI defaults (see BackupConfiguration in api/models/backups.py and the
# Retention tab in BackupSettingsView.vue).
DEFAULT_DAILY = 7
DEFAULT_WEEKLY = 4
DEFAULT_MONTHLY = 6
DEFAULT_MIN_COUNT = 3


@dataclass(frozen=True)
class RetentionConfig:
    """GFS retention counts. Tier counts of 0 disable that tier."""

    daily: int = DEFAULT_DAILY
    weekly: int = DEFAULT_WEEKLY
    monthly: int = DEFAULT_MONTHLY
    min_count: int = DEFAULT_MIN_COUNT

    @classmethod
    def from_values(
        cls,
        daily: Optional[int],
        weekly: Optional[int],
        monthly: Optional[int],
        min_count: Optional[int],
    ) -> "RetentionConfig":
        """Build a config, falling back to the model defaults for NULL values."""
        return cls(
            daily=DEFAULT_DAILY if daily is None else max(int(daily), 0),
            weekly=DEFAULT_WEEKLY if weekly is None else max(int(weekly), 0),
            monthly=DEFAULT_MONTHLY if monthly is None else max(int(monthly), 0),
            min_count=DEFAULT_MIN_COUNT if min_count is None else max(int(min_count), 1),
        )


def _localize(dt: datetime, tz: tzinfo) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def day_bucket(dt: datetime) -> Hashable:
    return dt.date()


def week_bucket(dt: datetime) -> Hashable:
    iso = dt.isocalendar()
    return (iso[0], iso[1])


def month_bucket(dt: datetime) -> Hashable:
    return (dt.year, dt.month)


def select_gfs_retention(
    backups: Iterable[Tuple[int, datetime]],
    config: RetentionConfig,
    tz: tzinfo = timezone.utc,
) -> Tuple[Set[int], Set[int]]:
    """
    Decide which backups to keep and which to delete.

    Args:
        backups: (id, created_at) pairs of eligible backups of ONE backup type
            (successful, not deleted, not protected).
        config: retention counts.
        tz: timezone used to compute day/week/month boundaries.

    Returns:
        (keep_ids, delete_ids). Together they contain every input id exactly once.
        Backups whose created_at is None are always in keep_ids.
    """
    keep: Set[int] = set()
    items: List[Tuple[int, datetime]] = []
    for backup_id, created_at in backups:
        if created_at is None:
            keep.add(backup_id)  # cannot be bucketed: never delete
            continue
        items.append((backup_id, _localize(created_at, tz)))
    # Newest first; id as deterministic tie-break for identical timestamps.
    items.sort(key=lambda item: (item[1], item[0]), reverse=True)

    # Safety net: newest N always kept, and never fewer than 1.
    min_keep = max(config.min_count, 1)
    for backup_id, _ in items[:min_keep]:
        keep.add(backup_id)

    tiers: List[Tuple[int, Callable[[datetime], Hashable]]] = [
        (config.daily, day_bucket),
        (config.weekly, week_bucket),
        (config.monthly, month_bucket),
    ]
    for limit, bucket_fn in tiers:
        if limit <= 0:
            continue
        seen: Set[Hashable] = set()
        for backup_id, created_at in items:
            bucket = bucket_fn(created_at)
            if bucket in seen:
                continue
            if len(seen) >= limit:
                break
            seen.add(bucket)
            keep.add(backup_id)  # newest backup in this bucket

    all_ids = {backup_id for backup_id, _ in items} | keep
    return keep, all_ids - keep


def select_floor_ids(
    backups: Iterable[Tuple[int, Hashable, Optional[datetime]]],
    min_count: Optional[int],
) -> Set[int]:
    """
    Return the ids protected by the retention floor.

    Args:
        backups: (id, backup_type, created_at) for every successful, not-deleted
            backup (protected ones included: they count towards the floor).
        min_count: the GFS "Safety Net" count; None means the model default.
            Values below 1 are raised to 1.

    Returns:
        The ids of the newest max(min_count, 1) backups of each backup type, plus
        every backup without a created_at (which cannot be ordered).
    """
    floor = max(DEFAULT_MIN_COUNT if min_count is None else int(min_count), 1)
    protected: Set[int] = set()
    by_type: Dict[Hashable, List[Tuple[datetime, int]]] = {}
    for backup_id, backup_type, created_at in backups:
        if created_at is None:
            protected.add(backup_id)
            continue
        by_type.setdefault(backup_type, []).append(
            (_localize(created_at, timezone.utc), backup_id)
        )
    for items in by_type.values():
        items.sort(reverse=True)  # newest first, id as tie-break
        protected.update(backup_id for _, backup_id in items[:floor])
    return protected
