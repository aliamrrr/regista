"""Per-team, per-match calibration metrics (docs/DATA_AND_METRICS.md §7).

Computed from the event feed, the simulator's true xG (ground truth) and tracking. These are a
plausibility check of the simulator, not the product's analytics (Phase 2 owns those).
"""

import itertools
from collections.abc import Sequence
from typing import Any

import numpy as np

from regista_sim.physical import players_physical, release_speed_kmh

# metric → (label, low, high, unit)
RANGES: dict[str, tuple[str, float, float, str]] = {
    "passes": ("Passes attempted", 350, 650, ""),
    "pass_completion": ("Pass completion", 0.75, 0.90, "%"),
    "shots": ("Shots", 8, 20, ""),
    "on_target_ratio": ("Shots on target / shots", 0.30, 0.40, "%"),
    "goals": ("Goals", 1.2, 1.7, ""),
    "xg_per_shot": ("Mean xG per shot", 0.09, 0.13, ""),
    "possession": ("Possession", 0.35, 0.65, "%"),
    "fouls": ("Fouls", 8, 14, ""),
    "corners": ("Corners", 3, 8, ""),
    "yellow_cards": ("Yellow cards", 1, 3, ""),
    "distance_km": ("Distance per outfield player (90′)", 9.5, 12.0, "km"),
    "sprints": ("Sprints (≥ 25.2 km/h) per outfield player", 15, 40, ""),
    "top_speed_kmh": ("Top speed per match (fastest player)", 32, 36, "km/h"),
    "pass_speed_kmh": ("Pass ball speed", 30, 90, "km/h"),
    "shot_speed_kmh": ("Shot speed", 60, 130, "km/h"),
}
_ON_BALL = {"pass", "carry", "shot", "dribble"}


def _mean(values: Sequence[float]) -> float | None:
    """Mean of ``values``, or ``None`` (JSON null) when there is nothing to average."""
    return float(np.mean(values)) if len(values) else None


def possession_shares(feed: Sequence[dict[str, Any]], teams: Sequence[str]) -> dict[str, float]:
    """In-play time share per team: the gap after each on-ball event (capped at 10 s)."""
    time = dict.fromkeys(teams, 0.0)
    on_ball = [e for e in feed if e["type"] in _ON_BALL]
    for a, b in itertools.pairwise(on_ball):
        if a["period"] == b["period"]:
            time[a["team_id"]] += min(b["clock_ms"] - a["clock_ms"], 10_000)
    total = sum(time.values()) or 1.0
    return {team: value / total for team, value in time.items()}


def team_metrics(
    feed: Sequence[dict[str, Any]],
    shots_xg: dict[str, float],
    periods: list[tuple[np.ndarray, list[str | None], list]],
    ball_by_period: list[np.ndarray],
    keepers: set[str],
) -> dict[str, dict[str, float | None]]:
    """Return the §7 metrics for both teams of one match (``None`` where undefined)."""
    teams = [t["team_id"] for t in feed[0]["payload"]["teams"].values()]
    shares = possession_shares(feed, teams)
    physical = players_physical(periods)
    out: dict[str, dict[str, float | None]] = {}
    for team in teams:
        events = [e for e in feed if e["team_id"] == team]
        passes = [e for e in events if e["type"] == "pass"]
        countable = [e for e in passes if e["payload"]["pass_type"] != "throw_in"]
        complete = [e for e in countable if e["payload"]["outcome"] == "complete"]
        shots = [e for e in events if e["type"] == "shot"]
        on_target = [e for e in shots if e["payload"]["outcome"] in ("goal", "saved")]
        goals = [e for e in shots if e["payload"]["outcome"] == "goal"]
        xgs = [shots_xg[e["event_id"]] for e in shots if e["event_id"] in shots_xg]
        players = {pid: v for pid, v in physical.items() if pid.startswith(team + "-")}
        outfield = [v for pid, v in players.items() if pid not in keepers and v.frames >= 18_000]
        pass_speeds = [
            release_speed_kmh(ball_by_period[e["period"] - 1], e["clock_ms"] // 100) for e in passes
        ]
        shot_speeds = [
            release_speed_kmh(ball_by_period[e["period"] - 1], e["clock_ms"] // 100)
            for e in shots
            if e["payload"]["body_part"] != "head"
        ]
        out[team] = {
            "passes": float(len(passes)),
            "pass_completion": len(complete) / max(len(countable), 1),
            "shots": float(len(shots)),
            "on_target_ratio": len(on_target) / max(len(shots), 1),
            "goals": float(len(goals)),
            "xg_per_shot": _mean(xgs),
            "possession": shares[team],
            "fouls": float(sum(e["type"] == "foul" for e in events)),
            "corners": float(
                sum(
                    e["type"] == "stoppage" and e["payload"]["restart_type"] == "corner"
                    for e in events
                )
            ),
            "yellow_cards": float(
                sum(e["type"] == "foul" and e["payload"]["card"] == "yellow" for e in events)
            ),
            "distance_km": _mean([v.distance_m / v.frames * 54_000 / 1000 for v in outfield]),
            "sprints": _mean([v.sprints / v.frames * 54_000 for v in outfield]),
            "top_speed_kmh": max((v.top_speed_kmh for v in players.values()), default=0.0),
            "pass_speed_kmh": _mean(pass_speeds),
            "shot_speed_kmh": _mean(shot_speeds),
        }
    return out
