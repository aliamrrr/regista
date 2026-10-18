"""Small re-implementations of docs/DATA_AND_METRICS.md §8 formulas, used to check the golden
match. Phase 2 owns the real analytics; these only make sure the scenario lands near its targets.
"""

import itertools
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from regista_sim.engine.match import MatchSetup
from regista_sim.engine.models import PassFeatures, pass_completion
from regista_sim.physical import smoothed_speed_kmh, track_segments
from regista_sim.tracking import Tracking

PITCH = 105.0
REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"
SIM = REPO / "apps" / "simulator"


def short_setup(seed: int = 5) -> MatchSetup:
    """Two 3-minute periods of free play between two mid-table clubs."""
    return MatchSetup(
        match_id="s001",
        home="BRA",
        away="TAR",
        seed=seed,
        kickoff=datetime(2026, 11, 7, 15, 0, tzinfo=UTC),
        added_time_min=(1, 1),
        period_minutes=3,
    )


def team_direction(golden_metadata: dict[str, Any], team: str, period: int) -> int:
    """+1 if ``team`` attacks towards x = 105 in ``period``."""
    for item in golden_metadata["attacking_directions"]:
        if item["period"] == period:
            return 1 if item["towards_x_105"] == team else -1
    msg = f"no direction for period {period}"
    raise ValueError(msg)


def speed_series(tracking: Tracking, player: str, period: int) -> np.ndarray:
    """Smoothed speed (km/h) of ``player`` for every frame of ``period`` (NaN off the pitch)."""
    track = tracking.periods[period - 1]
    out = np.full(track.frames, np.nan)
    for slot, start, end in track_segments(track.slot_ids, track.changes, track.frames).get(
        player, []
    ):
        out[start:end] = smoothed_speed_kmh(track.pos_cm[start:end, slot].astype(float) / 100)
    return out


def distance_until(tracking: Tracking, player: str, period: int, clock_ms: int) -> float:
    """Metres covered by ``player`` from kick-off until ``clock_ms`` of ``period``."""
    total = 0.0
    for p in range(1, period + 1):
        track = tracking.periods[p - 1]
        for slot, start, end in track_segments(track.slot_ids, track.changes, track.frames).get(
            player, []
        ):
            stop = end if p < period else min(end, clock_ms // 100)
            xy = track.pos_cm[start:stop, slot].astype(float) / 100
            if len(xy) > 1:
                total += float(np.sqrt((np.diff(xy, axis=0) ** 2).sum(axis=1)).sum())
    return total


def opponents_at(tracking: Tracking, period: int, frame: int, team: str) -> np.ndarray:
    """Positions (m) of the opponents of ``team`` (outfield only) at a frame."""
    track = tracking.periods[period - 1]
    ids = track.ids_at(frame)
    pts = [
        track.pos_cm[frame, slot] / 100
        for slot, pid in enumerate(ids)
        if pid and not pid.startswith(team + "-") and not pid.endswith("-1")
    ]
    return np.array(pts)


def lines_broken(
    opponents: np.ndarray, start: tuple[float, float], end: tuple[float, float]
) -> int:
    """§8: cluster opponents into 3 lines by x (1-D k-means), count lines the pass crosses."""
    xs = opponents[:, 0]
    centres = np.percentile(xs, [15, 50, 85])
    for _ in range(50):
        labels = np.argmin(np.abs(xs[:, None] - centres[None, :]), axis=1)
        centres = np.array(
            [xs[labels == k].mean() if (labels == k).any() else centres[k] for k in range(3)]
        )
    labels = np.argmin(np.abs(xs[:, None] - centres[None, :]), axis=1)
    lo, hi = sorted((start[0], end[0]))
    broken = 0
    for k in range(3):
        cx = centres[k]
        if not lo < cx < hi:
            continue
        y_at = start[1] + (cx - start[0]) / (end[0] - start[0]) * (end[1] - start[1])
        members = opponents[labels == k]
        if members[:, 1].min() <= y_at <= members[:, 1].max():
            broken += 1
    return broken


def pass_difficulty(
    opponents: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    height: str,
    direction: int,
) -> tuple[float, PassFeatures]:
    """§8 difficulty ``1 + 9 × (1 − xPass)``, xPass from the true model without passer skill."""
    s, e = np.array(start), np.array(end)
    seg = e - s
    length2 = float(seg @ seg)
    proj = ((opponents - s) @ seg) / length2
    closest = s + np.clip(proj, 0.0, 1.0)[:, None] * seg
    gap = np.sqrt(((opponents - closest) ** 2).sum(axis=1))
    feats = PassFeatures(
        distance=math.sqrt(length2),
        forward=float(seg[0] * direction / math.sqrt(length2)),
        pressure=float(min(np.sqrt(((opponents - s) ** 2).sum(axis=1)).min(), 10.0)),
        lane=int(((gap < 2.0) & (proj > 0.08) & (proj < 1.0)).sum()),
        separation=float(min(np.sqrt(((opponents - e) ** 2).sum(axis=1)).min(), 10.0)),
        height=height,
        passing=70,
    )
    return 1 + 9 * (1 - pass_completion(feats)), feats


def possession_share(
    events: list[dict[str, Any]], team: str, period: int, from_ms: int, to_ms: int
) -> float:
    """Share of the time between on-ball events credited to ``team`` in a window."""
    on_ball = [
        e
        for e in events
        if e["period"] == period
        and from_ms <= e["clock_ms"] < to_ms
        and e["type"] in ("pass", "carry", "shot", "dribble")
    ]
    mine = total = 0.0
    for a, b in itertools.pairwise(on_ball):
        gap = min(b["clock_ms"] - a["clock_ms"], 10_000)
        total += gap
        if a["team_id"] == team:
            mine += gap
    return mine / total


def pressing(
    events: list[dict[str, Any]],
    metadata: dict[str, Any],
    team: str,
    period: int,
    from_ms: int,
    to_ms: int,
) -> tuple[float, float]:
    """§8 PPDA and press height (team-relative x of defensive actions) for ``team``."""
    opponent = next(t["team_id"] for t in metadata["teams"].values() if t["team_id"] != team)
    d_opp = team_direction(metadata, opponent, period)
    d_me = team_direction(metadata, team, period)
    window = [e for e in events if e["period"] == period and from_ms <= e["clock_ms"] < to_ms]
    passes = [
        e
        for e in window
        if e["type"] == "pass"
        and e["team_id"] == opponent
        and (e["location"]["x"] if d_opp > 0 else PITCH - e["location"]["x"]) < 0.6 * PITCH
    ]
    actions = [
        e
        for e in window
        if e["team_id"] == team and e["type"] in ("tackle", "interception", "foul", "duel")
    ]
    zone = [
        e
        for e in actions
        if (e["location"]["x"] if d_opp > 0 else PITCH - e["location"]["x"]) < 0.6 * PITCH
    ]
    ppda = len(passes) / max(len(zone), 1)
    height = (
        float(
            np.mean(
                [e["location"]["x"] if d_me > 0 else PITCH - e["location"]["x"] for e in actions]
            )
        )
        if actions
        else float("nan")
    )
    return ppda, height
