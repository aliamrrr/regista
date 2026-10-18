"""The simulator's "true" outcome models (docs/DATA_AND_METRICS.md §2).

Their shapes follow the anchors of §8, so the xPass and xG models fitted on simulator output in
Phase 2 can hit those anchors. The true probabilities are written to ``ground_truth.json`` and
never to the event feed.
"""

import math
from dataclasses import dataclass

import numpy as np


def sigmoid(z: float) -> float:
    """Logistic function."""
    return 1.0 / (1.0 + math.exp(-z))


def logit(p: float) -> float:
    """Inverse logistic function (``p`` clipped away from 0 and 1)."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


@dataclass(frozen=True)
class PassFeatures:
    """Inputs of the true pass-completion model."""

    distance: float  # m, start → target
    forward: float  # cosine between the pass and the attacking direction (−1 … 1)
    pressure: float  # m, nearest opponent to the passer (capped at 10)
    lane: int  # opponents within 2 m of the pass segment
    separation: float  # m, nearest opponent to the target point (capped at 10)
    height: str  # ground | low | high
    passing: int = 70  # passer attribute


PASS_COEF = {
    "intercept": 0.79,
    "distance": -0.04,
    "forward": -0.45,
    "pressure": 0.12,
    "lane": -0.30,
    "separation": 0.18,
    "low": -0.40,
    "high": -0.99,
    "skill": 0.15,
}

# §8 xPass anchors with the exact features they are defined on (Phase 2 reuses these).
PASS_ANCHORS: dict[str, tuple[PassFeatures, float]] = {
    "10m_backward_unpressed_ground": (PassFeatures(10.0, -1.0, 10.0, 0, 8.0, "ground"), 0.97),
    "25m_forward_congested_lane": (PassFeatures(25.0, 1.0, 6.0, 2, 4.0, "ground"), 0.55),
    "40m_high_switch": (PassFeatures(40.0, 0.0, 6.0, 0, 6.0, "high"), 0.50),
    "through_ball_between_two_defenders": (PassFeatures(22.0, 1.0, 5.0, 2, 1.5, "ground"), 0.40),
}


def pass_completion(f: PassFeatures) -> float:
    """Return the true probability that a pass is completed."""
    c = PASS_COEF
    z = (
        c["intercept"]
        + c["distance"] * f.distance
        + c["forward"] * f.forward
        + c["pressure"] * min(f.pressure, 10.0)
        + c["lane"] * f.lane
        + c["separation"] * min(f.separation, 10.0)
        + c["skill"] * (f.passing - 70) / 10
    )
    if f.height == "low":
        z += c["low"]
    elif f.height == "high":
        z += c["high"]
    return sigmoid(z)


@dataclass(frozen=True)
class ShotFeatures:
    """Inputs of the true goal model (the simulator's xG)."""

    distance: float  # m to the goal centre
    angle: float  # radians subtended by the goal mouth
    header: bool
    assist: str  # none | through_ball | cutback | cross
    defenders_in_cone: int  # outfield opponents inside the shot → posts triangle
    penalty: bool = False


XG_COEF = {
    "intercept": -3.296,
    "distance": -0.0043,
    "angle": 3.174,
    "header": -0.9,
    "through_ball": 0.35,
    "cutback": 0.45,
    "cone": -0.35,
    "penalty": 2.449,
}

# §8 xG anchors (+ a 15 m one of ours that keeps mid-range shots realistic).
XG_ANCHORS: dict[str, tuple[ShotFeatures, float]] = {
    "penalty": (ShotFeatures(11.0, 0.645, False, "none", 0, penalty=True), 0.76),
    "6m_central_open_play": (ShotFeatures(6.0, 1.094, False, "none", 1), 0.45),
    "15m_central_one_defender": (ShotFeatures(15.0, 0.476, False, "none", 1), 0.10),
    "25m_central": (ShotFeatures(25.0, 0.291, False, "none", 2), 0.04),
}


def expected_goals(f: ShotFeatures) -> float:
    """Return the true chance a shot with these features scores, for average skills."""
    c = XG_COEF
    z = (
        c["intercept"]
        + c["distance"] * f.distance
        + c["angle"] * f.angle
        + c["cone"] * f.defenders_in_cone
    )
    if f.header:
        z += c["header"]
    if f.assist in ("through_ball", "cutback"):
        z += c[f.assist]
    if f.penalty:
        z += c["penalty"]
    return sigmoid(z)


FINISHING_MEAN = 77  # shot-weighted finishing (aerial for headers) of free-play shooters
GOALKEEPING_MEAN = 78  # the league's keepers: an average duel scores with probability xG


def goal_probability(xg: float, finishing: int, goalkeeping: int) -> float:
    """Return the scoring chance once the shooter's and keeper's skills are applied."""
    skill = 0.2 * (finishing - FINISHING_MEAN) / 10 - 0.25 * (goalkeeping - GOALKEEPING_MEAN) / 10
    return sigmoid(logit(xg) + skill)


def tackle_success(tackling: int, dribbling: int, composure: int) -> float:
    """Return the chance a challenge wins the ball."""
    return sigmoid((tackling - 0.8 * dribbling - 0.2 * composure + 6.0) / 12.0)


def dribble_success(dribbling: int, tackling: int) -> float:
    """Return the chance a take-on beats the defender."""
    return sigmoid((dribbling - tackling + 4.0) / 11.0)


def foul_probability(tackling: int, pressing: float, fatigue: float) -> float:
    """Return the chance a challenge is a foul (clumsier when tired or pressing hard)."""
    return 0.17 * (1.25 - tackling / 100) * (0.8 + 0.6 * pressing) * (1.0 + 0.4 * fatigue)


def aerial_win(aerial_a: int, aerial_b: int) -> float:
    """Return the chance player A wins an aerial duel against player B."""
    return sigmoid((aerial_a - aerial_b) / 12.0)


def card_for_foul(rng: np.random.Generator, severity_bias: float = 0.0) -> str:
    """Sample the card a foul earns: ``none``, ``yellow`` or ``red``."""
    severity = rng.random() + severity_bias
    if severity > 0.997:
        return "red"
    return "yellow" if severity > 0.79 else "none"
