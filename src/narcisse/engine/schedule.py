"""Scans the profiles ask for again on their own, every week or every month.

While Narcisse runs, the engine looks every few minutes for a profile whose last full scan (not a
check of one trace) is older than its interval, and starts one for it: one scheduled scan at a
time, never next to a scan of the same profile. A profile never scanned waits for its first scan
by hand. A computer that was off catches up a little after Narcisse starts.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

INTERVALS = {"weekly": timedelta(days=7), "monthly": timedelta(days=30)}
FIRST_LOOK = 120.0  # seconds after the start: not while Narcisse is starting
LOOK_EVERY = 300.0


@dataclass(frozen=True)
class ProfileState:
    profile_id: int
    rescan: str  # "never", "weekly", "monthly"
    last_scan: datetime | None  # when its last full scan started
    busy: bool  # a scan of it runs or waits paused


def interval(settings: dict[str, Any]) -> timedelta | None:
    return INTERVALS.get(str(settings.get("rescan", "never")))


def next_scan(rescan: str, last_scan: datetime | None) -> datetime | None:
    """When the profile's next scheduled scan is due, if it has one."""
    every = INTERVALS.get(rescan)
    return last_scan + every if every is not None and last_scan is not None else None


def due(profiles: Iterable[ProfileState], now: datetime, scheduled_running: bool) -> int | None:
    """The profile to scan now, if any: the most overdue one."""
    if scheduled_running:
        return None
    overdue = [
        (when, state.profile_id)
        for state in profiles
        if not state.busy
        and (when := next_scan(state.rescan, state.last_scan)) is not None
        and when <= now
    ]
    return min(overdue)[1] if overdue else None
