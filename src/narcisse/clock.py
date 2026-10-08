"""Time source of the engine and the modules, so that tests can run hours of scan in seconds."""

import asyncio
import time
from datetime import UTC, datetime, timedelta


class Clock:
    """Wall-clock time, optionally sped up.

    With `speed=100`, a 30 s fake scan takes 0.3 s, and `now()` moves 100 times faster, so that
    durations computed from timestamps (a `retry_at`, an ETA) stay consistent with the waits.
    """

    def __init__(self, speed: float = 1.0) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.speed = speed
        self._origin = datetime.now(UTC)
        self._start = time.monotonic()

    def now(self) -> datetime:
        if self.speed == 1:
            return datetime.now(UTC)
        elapsed = (time.monotonic() - self._start) * self.speed
        return self._origin + timedelta(seconds=elapsed)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds) / self.speed)

    def seconds_until(self, moment: datetime) -> float:
        return (moment - self.now()).total_seconds()
