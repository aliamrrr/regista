"""Pitch geometry (105 × 68 m) and coordinate frames (docs/DATA_AND_METRICS.md §2).

Absolute frame: ``x`` 0 → 105 along the length, ``y`` 0 → 68 across, origin at the top-left
corner of the broadcast view. Team-relative frame: the team attacks towards ``x = 105`` and its
left touchline is ``y = 0``; for the team attacking towards ``x = 0`` it is the absolute frame
rotated by 180°.
"""

import math

import numpy as np

LENGTH = 105.0
WIDTH = 68.0
CENTRE = (52.5, 34.0)
GOAL_HALF_WIDTH = 3.66
GOAL_HEIGHT = 2.44
BOX_DEPTH = 16.5
BOX_HALF_WIDTH = 20.16
SIX_DEPTH = 5.5
SIX_HALF_WIDTH = 9.16
PENALTY_SPOT = 11.0
BALL_RADIUS = 0.11


def to_rel(x: float, y: float, direction: int) -> tuple[float, float]:
    """Absolute → team-relative for a team attacking towards ``x = 105`` (+1) or 0 (−1)."""
    return (x, y) if direction > 0 else (LENGTH - x, WIDTH - y)


def to_abs(x_rel: float, y_rel: float, direction: int) -> tuple[float, float]:
    """Team-relative → absolute (the transform is its own inverse)."""
    return to_rel(x_rel, y_rel, direction)


def rel_x_array(x: np.ndarray, direction: int) -> np.ndarray:
    """Vectorized team-relative ``x``."""
    return x if direction > 0 else LENGTH - x


def goal_centre(direction: int) -> tuple[float, float]:
    """Absolute centre of the goal a team attacks."""
    return (LENGTH, 34.0) if direction > 0 else (0.0, 34.0)


def goal_distance(x_rel: float, y_rel: float) -> float:
    """Distance (m) from a team-relative point to the centre of the goal being attacked."""
    return math.sqrt((LENGTH - x_rel) ** 2 + (y_rel - 34.0) ** 2)


def goal_angle(x_rel: float, y_rel: float) -> float:
    """Angle (radians) the goal mouth subtends from a team-relative point."""
    dx = max(LENGTH - x_rel, 0.05)
    a1 = math.atan2(34.0 - GOAL_HALF_WIDTH - y_rel, dx)
    a2 = math.atan2(34.0 + GOAL_HALF_WIDTH - y_rel, dx)
    return abs(a2 - a1)


def expected_threat(x_rel: float, y_rel: float) -> float:
    """A smooth expected-threat surface: chance the possession scores from this spot.

    Hand-built (not fitted to any real dataset): rises towards goal and towards the middle,
    about 0.006 in a team's own half, 0.05 entering the final third, 0.13 at the edge of the
    box, 0.20 at the penalty spot and 0.30 inside the six-yard box.
    """
    distance = goal_distance(x_rel, y_rel)
    centrality = max(0.0, math.cos(math.atan2(abs(y_rel - 34.0), max(LENGTH - x_rel, 0.1)))) ** 2
    return (
        0.004
        + 0.45 * math.exp(-distance / 12.0) * (0.4 + 0.6 * centrality)
        + 0.02 * (max(x_rel, 0.0) / LENGTH) ** 2
    )


def in_box(x_rel: float, y_rel: float) -> bool:
    """True when a team-relative point is inside the penalty area being attacked."""
    return x_rel >= LENGTH - BOX_DEPTH and abs(y_rel - 34.0) <= BOX_HALF_WIDTH


def inside_pitch(x: float, y: float) -> bool:
    """True when an absolute point is on the field of play."""
    return 0.0 <= x <= LENGTH and 0.0 <= y <= WIDTH
