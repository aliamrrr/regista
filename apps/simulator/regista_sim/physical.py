"""Tracking-derived physical numbers, computed exactly as docs/DATA_AND_METRICS.md §8 says.

Player speed = ``|Δpos| / Δt`` smoothed with a 5-frame centred moving average (km/h); sprint =
≥ 25.2 km/h for ≥ 1 s; distance = cumulative path. Ball speed = peak ``|Δball| / Δt`` over the
first 0.3 s after release. These feed ``summary.json``, the calibration report and the tests;
they never enter the event feed.
"""

from dataclasses import dataclass

import numpy as np

FRAME_S = 0.1
SPRINT_KMH = 25.2
SPRINT_MIN_FRAMES = 10


@dataclass
class PlayerPhysical:
    """Physical output of one player over a match."""

    distance_m: float
    top_speed_kmh: float
    sprints: int
    frames: int


def smoothed_speed_kmh(xy_m: np.ndarray) -> np.ndarray:
    """Per-frame speed (km/h) of a track, 5-frame centred moving average.

    ``xy_m`` is (frames, 2) in metres. Frame ``i`` gets the speed over ``i−1 → i``; the average
    is taken where a full window exists (edges are NaN).
    """
    if len(xy_m) < 2:
        return np.full(len(xy_m), np.nan)
    step = np.sqrt((np.diff(xy_m, axis=0) ** 2).sum(axis=1)) / FRAME_S * 3.6
    inst = np.concatenate(([np.nan], step))
    out = np.full(len(inst), np.nan)
    if len(inst) >= 6:
        window = np.convolve(step, np.ones(5) / 5.0, mode="valid")  # covers frames 3 … n−3
        out[3 : 3 + len(window)] = window
    return out


def sprint_count(speed_kmh: np.ndarray) -> int:
    """Number of runs at ≥ 25.2 km/h lasting at least 1 s (10 frames)."""
    fast = np.nan_to_num(speed_kmh, nan=0.0) >= SPRINT_KMH
    if not fast.any():
        return 0
    edges = np.diff(np.concatenate(([0], fast.astype(np.int8), [0])))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return int(((ends - starts) >= SPRINT_MIN_FRAMES).sum())


def track_segments(
    slot_ids: list[str | None], changes: list[tuple[int, int, str | None]], frames: int
) -> dict[str, list[tuple[int, int, int]]]:
    """Map player id → list of (slot, first frame, end frame) while on the pitch."""
    current = list(slot_ids)
    start = [0] * len(current)
    out: dict[str, list[tuple[int, int, int]]] = {}
    for at, slot, pid in [*changes, *((frames, s, None) for s in range(len(current)))]:
        old = current[slot]
        if old is not None and at > start[slot]:
            out.setdefault(old, []).append((slot, start[slot], at))
        current[slot] = pid
        start[slot] = at
    return out


def players_physical(
    periods: list[tuple[np.ndarray, list[str | None], list[tuple[int, int, str | None]]]],
) -> dict[str, PlayerPhysical]:
    """Physical output per player from per-period tracking.

    Each period is ``(pos_cm (frames, 22, 2), slot_ids at frame 0, slot changes)``.
    """
    acc: dict[str, list[float]] = {}
    for pos_cm, slot_ids, changes in periods:
        for pid, segments in track_segments(slot_ids, changes, len(pos_cm)).items():
            for slot, a, b in segments:
                xy = pos_cm[a:b, slot].astype(np.float64) / 100.0
                speed = smoothed_speed_kmh(xy)
                dist = (
                    float(np.sqrt((np.diff(xy, axis=0) ** 2).sum(axis=1)).sum())
                    if len(xy) > 1
                    else 0.0
                )
                top = float(np.nanmax(speed)) if np.isfinite(speed).any() else 0.0
                rec = acc.setdefault(pid, [0.0, 0.0, 0.0, 0.0])
                rec[0] += dist
                rec[1] = max(rec[1], top)
                rec[2] += sprint_count(speed)
                rec[3] += b - a
    return {
        pid: PlayerPhysical(round(v[0], 1), round(v[1], 2), int(v[2]), int(v[3]))
        for pid, v in sorted(acc.items())
    }


def release_speed_kmh(ball_cm: np.ndarray, frame: int) -> float:
    """Peak ball speed (km/h) over the first 0.3 s after a release at ``frame``."""
    window = ball_cm[frame : frame + 4].astype(np.float64) / 100.0
    if len(window) < 2:
        return 0.0
    step = np.sqrt((np.diff(window, axis=0) ** 2).sum(axis=1)) / FRAME_S * 3.6
    return float(step.max())
