"""Control-vs-chaos components and index (docs/DATA_AND_METRICS.md §8).

The simulator computes the components per 5-minute window to calibrate the index
(``baselines.json``) and to check the golden story; Phase 2 analytics computes the same thing
from the live feed. The definitions sit next to the numbers so both sides agree.
"""

import itertools
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

WINDOW_MS = 5 * 60_000
STEP_MS = 60_000
INDEX_SCALE = 15.0  # index points per standard deviation of the weighted sum in free play
_REGAINS = {"interception", "ball_recovery"}

CHAOS_COMPONENTS: dict[str, dict[str, Any]] = {
    "possession_changes_per_min": {
        "sign": 1,
        "definition": "new possession_id values among events in the window ÷ 5",
    },
    "short_possession_share": {
        "sign": 1,
        "definition": "share of possessions starting in the window with < 3 passes",
    },
    "duels_per_min": {"sign": 1, "definition": "duel + tackle events in the window ÷ 5"},
    "fouls_per_min": {"sign": 1, "definition": "foul events in the window ÷ 5"},
    "shots_after_regain": {
        "sign": 1,
        "definition": "shots in the window within 10 s of their possession's regain "
        "(interception, ball recovery or won tackle)",
    },
    "long_possession_share": {
        "sign": -1,
        "definition": "share of possessions starting in the window with ≥ 6 passes",
    },
    "completion_under_pressure": {
        "sign": -1,
        "definition": "completed / attempted passes with under_pressure = true "
        "(null when there are none)",
    },
}
WEIGHTS = dict.fromkeys(CHAOS_COMPONENTS, 1.0)


@dataclass
class _Possessions:
    """Per-possession facts the components need, from one pass over the feed."""

    passes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start: dict[str, tuple[int, int]] = field(default_factory=dict)  # period, clock_ms
    regain_at: dict[str, int] = field(default_factory=dict)


def _possessions(feed: Sequence[dict[str, Any]]) -> _Possessions:
    poss = _Possessions()
    for e in feed:
        pid = e["possession_id"]
        if pid is None:
            continue
        poss.start.setdefault(pid, (e["period"], e["clock_ms"]))
        if e["type"] == "pass":
            poss.passes[pid] += 1
        won_tackle = e["type"] == "tackle" and e["payload"].get("outcome") == "won"
        if (e["type"] in _REGAINS or won_tackle) and pid not in poss.regain_at:
            poss.regain_at[pid] = e["clock_ms"]
    return poss


def _share(started: list[str], hit: int) -> float | None:
    return hit / len(started) if started else None


def _components(
    events: Sequence[dict[str, Any]], poss: _Possessions, period: int, lo: int, hi: int
) -> dict[str, float | None]:
    """Component values for ``lo <= clock_ms < hi`` of ``period`` (a 5-minute window)."""
    win = [e for e in events if lo <= e["clock_ms"] < hi]
    ids = [e["possession_id"] for e in win if e["possession_id"]]
    started = [p for p, (per, at) in poss.start.items() if per == period and lo <= at < hi]
    pressured = [e for e in win if e["type"] == "pass" and e["under_pressure"]]
    shots_fast = sum(
        1
        for e in win
        if e["type"] == "shot"
        and e["possession_id"] in poss.regain_at
        and 0 <= e["clock_ms"] - poss.regain_at[e["possession_id"]] <= 10_000
    )
    complete = sum(e["payload"]["outcome"] == "complete" for e in pressured)
    return {
        "possession_changes_per_min": sum(a != b for a, b in itertools.pairwise(ids)) / 5.0,
        "short_possession_share": _share(started, sum(poss.passes[p] < 3 for p in started)),
        "duels_per_min": sum(e["type"] in ("duel", "tackle") for e in win) / 5.0,
        "fouls_per_min": sum(e["type"] == "foul" for e in win) / 5.0,
        "shots_after_regain": float(shots_fast),
        "long_possession_share": _share(started, sum(poss.passes[p] >= 6 for p in started)),
        "completion_under_pressure": complete / len(pressured) if pressured else None,
    }


def _windows(feed: Sequence[dict[str, Any]], step_ms: int) -> list[dict[str, Any]]:
    poss = _possessions(feed)
    out = []
    for period in (1, 2):
        events = [e for e in feed if e["period"] == period]
        if not events:
            continue
        end = max(e["clock_ms"] for e in events)
        for lo in range(0, end - WINDOW_MS + 1, step_ms):
            hi = lo + WINDOW_MS
            out.append(
                {"period": period, "from_ms": lo, **_components(events, poss, period, lo, hi)}
            )
    return out


def chaos_windows(feed: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Component values for every full, non-overlapping 5-minute window of each period."""
    return _windows(feed, WINDOW_MS)


def chaos_series(feed: Sequence[dict[str, Any]], step_ms: int = STEP_MS) -> list[dict[str, Any]]:
    """Rolling 5-minute windows every ``step_ms``; ``from_ms + 5 min`` is the sample time."""
    return _windows(feed, step_ms)


def weighted_sum(window: dict[str, Any], components: dict[str, dict[str, Any]]) -> float:
    """Σ weight × sign × z over the components; a missing component counts as average (z = 0)."""
    total = 0.0
    for key, spec in CHAOS_COMPONENTS.items():
        value = window.get(key)
        if value is not None:
            base = components[key]
            total += WEIGHTS[key] * spec["sign"] * (value - base["mean"]) / base["std"]
    return total


def chaos_index(window: dict[str, Any], baselines: dict[str, Any]) -> float:
    """The 0–100 index of one window: free play averages 50, ``INDEX_SCALE`` points per σ."""
    stats = baselines["chaos_index"]
    z = (weighted_sum(window, baselines["chaos_components"]) - stats["sum_mean"]) / stats["sum_std"]
    return min(max(50.0 + INDEX_SCALE * z, 0.0), 100.0)


def chaos_label(index: float) -> str:
    """Control (Calm) 0–33, Contested (Breezy) 34–66, Chaos (Stormy) 67–100."""
    if index < 33.5:
        return "control"
    return "contested" if index < 66.5 else "chaos"
