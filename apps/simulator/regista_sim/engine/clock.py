"""Match time: period clock, broadcast timeline and wall clock (CLAUDE.md "Time").

- ``clock_ms`` restarts at 0 when each period kicks off (the spec example: period 2,
  ``clock_ms`` 1 332 400 is 67′).
- ``video_ts_ms`` is the broadcast timeline: 0 at kick-off, continuous through stoppage time and
  the half-time break.
- ``wall_ts`` is the kick-off time (from the scenario, never ``now()``) plus ``video_ts_ms``.
- Minutes display rounded down: ``45 × (period − 1) + clock_ms // 60 000``, and ``45+n′`` /
  ``90+n′`` in stoppage time.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

PERIOD_MS = 45 * 60_000


@dataclass
class MatchClock:
    """Tracks the current period and converts period clocks to the other timelines."""

    kickoff: datetime  # timezone-aware UTC
    half_time_break_ms: int = 900_000
    period: int = 1
    clock_ms: int = 0
    period_lengths_ms: list[int] = field(default_factory=list)

    def video_ts(self, period: int, clock_ms: int) -> int:
        """Return the broadcast timeline position of ``clock_ms`` in ``period``."""
        if period == 1:
            return clock_ms
        return self.period_lengths_ms[0] + self.half_time_break_ms + clock_ms

    def wall_ts(self, video_ts_ms: int) -> str:
        """Return the UTC ISO 8601 timestamp (milliseconds, ``Z``) of a timeline position."""
        moment = self.kickoff + timedelta(milliseconds=video_ts_ms)
        return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def match_minute(period: int, clock_ms: int) -> int:
    """Return the match minute, rounded down (``67`` for period 2 at 22:12)."""
    return 45 * (period - 1) + clock_ms // 60_000


def minute_label(period: int, clock_ms: int) -> str:
    """Return the display minute: ``67′``, ``45′`` or ``45+2′`` in stoppage time."""
    if clock_ms >= PERIOD_MS + 60_000:
        return f"{45 * period}+{(clock_ms - PERIOD_MS) // 60_000}′"
    return f"{min(match_minute(period, clock_ms), 45 * period)}′"


def parse_match_time(text: str) -> tuple[int, int]:
    """Parse ``"67:20"`` (match clock) or ``"45+2:10"`` into ``(period, clock_ms)``."""
    head, _, seconds = text.partition(":")
    sec = float(seconds or 0)
    if "+" in head:
        base, extra = head.split("+")
        period = 1 if int(base) == 45 else 2
        return period, int((45 + int(extra)) * 60_000 + sec * 1000)
    minute = int(head)
    period = 1 if minute < 45 else 2
    return period, int(((minute - 45 * (period - 1)) * 60 + sec) * 1000)
