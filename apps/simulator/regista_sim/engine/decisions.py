"""On-ball decisions (docs/DATA_AND_METRICS.md §2).

Candidates: a pass to each teammate (to feet, or into the path of a runner), carries, a take-on,
a shot when in range, a cross from wide areas, a clearance under pressure deep in its own half.
Utility = success probability × value (expected-threat gain, or the shot's xG) − failure × risk,
shaped by the team's directness and the player's vision and passing; the choice is a softmax
whose temperature falls with composure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from regista_sim.engine.models import (
    PassFeatures,
    ShotFeatures,
    dribble_success,
    expected_goals,
    pass_completion,
)
from regista_sim.pitch import (
    GOAL_HALF_WIDTH,
    LENGTH,
    WIDTH,
    expected_threat,
    goal_angle,
    goal_distance,
    to_abs,
    to_rel,
)

if TYPE_CHECKING:
    from regista_sim.engine.match import Match

CONE_MARGIN_M = 1.0  # a defender's body blocks this far either side of the shot → posts triangle
CLOSE_BLOCK_M = 2.5  # a goal-side defender this close to the shooter counts as in the cone


@dataclass
class Action:
    """What the ball carrier does next (absolute coordinates)."""

    kind: str  # pass | cross | shot | carry | dribble | clearance
    target: tuple[float, float]
    receiver: int = -1
    height: str = "ground"
    pass_type: str = "open_play"
    p_success: float = 1.0
    features: PassFeatures | ShotFeatures | None = None
    speed: float | None = None  # launch speed (m/s); scenarios set exact ball speeds
    outcome: str | None = None  # scenario-forced outcome
    z_target: float | None = None  # shots: height at the goal line
    opponent: int = -1  # take-ons: the defender to beat
    tag: str = ""  # scenario step id
    extra: dict = field(default_factory=dict)


def _segment_counts(start: np.ndarray, ends: np.ndarray, opp: np.ndarray) -> np.ndarray:
    """Opponents within 2 m of each start → end segment (excluding the passer's own spot)."""
    seg = ends - start  # (K, 2)
    rel = opp[None, :, :] - start[None, None, :]  # (1, M, 2)
    length2 = np.maximum((seg * seg).sum(axis=1), 1e-9)  # (K,)
    proj = (rel * seg[:, None, :]).sum(axis=2) / length2[:, None]  # (K, M)
    closest = start + np.clip(proj, 0.0, 1.0)[:, :, None] * seg[:, None, :]
    gap = opp[None, :, :] - closest
    near = (gap * gap).sum(axis=2) < 4.0
    return (near & (proj > 0.08) & (proj < 1.0)).sum(axis=1)


def _nearest(points: np.ndarray, opp: np.ndarray) -> np.ndarray:
    diff = points[:, None, :] - opp[None, :, :]
    return np.sqrt((diff * diff).sum(axis=2).min(axis=1))


def cone_defenders(m: Match, x: float, y: float, team: int) -> int:
    """Outfield opponents in the triangle from (x, y) to the posts, or goal-side within 2.5 m."""
    d = m.teams[team].direction
    sx, sy = to_rel(x, y, d)
    o = 1 - team
    count = 0
    for slot in range(11 * o, 11 * o + 11):
        if not m.bodies.active[slot] or slot == m.gk_slot[o]:
            continue
        px, py = to_rel(float(m.bodies.pos[slot, 0]), float(m.bodies.pos[slot, 1]), d)
        if px > sx - 0.3 and math.hypot(px - sx, py - sy) < CLOSE_BLOCK_M:
            count += 1  # right on the shooter, goal side: can block
            continue
        if px <= sx or px >= LENGTH:
            continue
        frac = (px - sx) / (LENGTH - sx)
        low = sy + frac * (34.0 - GOAL_HALF_WIDTH - sy)
        high = sy + frac * (34.0 + GOAL_HALF_WIDTH - sy)
        if low - CONE_MARGIN_M <= py <= high + CONE_MARGIN_M:
            count += 1
    return count


def shot_features(
    m: Match, slot: int, *, header: bool = False, assist: str = "none", penalty: bool = False
) -> ShotFeatures:
    """Features of a shot taken now by ``slot`` from its feet (or head)."""
    t = m.team_of(slot)
    x, y = (m.bx, m.by)
    rx, ry = to_rel(x, y, m.teams[t].direction)
    return ShotFeatures(
        goal_distance(rx, ry),
        goal_angle(rx, ry),
        header,
        assist,
        0 if penalty else cone_defenders(m, x, y, t),
        penalty,
    )


def pass_features(m: Match, slot: int, target: tuple[float, float], height: str) -> PassFeatures:
    """Features of a pass from ``slot`` at the ball to ``target`` (absolute)."""
    t = m.team_of(slot)
    o = slice(11 * (1 - t), 11 * (1 - t) + 11)
    opp = m.bodies.pos[o][m.bodies.active[o]]
    start = np.array((m.bx, m.by))
    end = np.array([target])
    seg = end[0] - start
    dist = float(math.hypot(seg[0], seg[1]))
    d = m.teams[t].direction
    forward = (seg[0] * d) / max(dist, 1e-6)
    return PassFeatures(
        distance=dist,
        forward=float(forward),
        pressure=float(min(_nearest(start[None, :], opp)[0], 10.0)),
        lane=int(_segment_counts(start, end, opp)[0]),
        separation=float(min(_nearest(end, opp)[0], 10.0)),
        height=height,
        passing=m.attr(slot, "passing"),
    )


def time_on_ball_ticks(m: Match, slot: int, pressure: float) -> int:
    """Sample how long the carrier keeps the ball before the next decision."""
    p = m.params
    tempo = m.dials[m.team_of(slot)]["tempo"]
    mean = (
        p.time_on_ball_s
        * (1.25 - 0.5 * tempo)
        * (p.pressured_time_factor if pressure < 3.0 else 1.0)
    )
    seconds = max(0.3, float(m.rng.gamma(2.0, mean / 2.0)))
    return round(seconds * 1000 / p.tick_ms)


def choose_action(m: Match, c: int) -> Action:
    """Score every candidate action for carrier ``c`` and sample one with a softmax."""
    p = m.params
    t = m.team_of(c)
    d = m.teams[t].direction
    dial = m.dials[t]
    directness = dial["directness"]
    o = slice(11 * (1 - t), 11 * (1 - t) + 11)
    opp = m.bodies.pos[o][m.bodies.active[o]]
    start = np.array((m.bx, m.by))
    rx, ry = to_rel(m.bx, m.by, d)
    pressure = float(min(_nearest(start[None, :], opp)[0], 10.0))
    risk_w = p.risk_weight * (1.2 - directness)
    vision = m.attr(c, "vision") / 100.0
    off_line = m.offside_line(t)

    actions: list[Action] = []
    utils: list[float] = []

    def add(action: Action, utility: float) -> None:
        actions.append(action)
        utils.append(utility)

    here = expected_threat(rx, ry)
    c_poss = p.possession_value
    keep_w = p.keep_weight

    def value_at(tx: float, ty: float) -> tuple[float, float]:
        """Value if the ball arrives at (tx, ty) still ours; cost if it is lost there."""
        qx, qy = to_rel(tx, ty, d)
        gain = expected_threat(qx, qy) + c_poss + p.progress_bonus * directness * (qx - rx)
        loss = keep_w * here + risk_w * expected_threat(LENGTH - qx, WIDTH - qy)
        return gain, loss

    # passes: one target per teammate (feet, or the space ahead of a runner)
    mates = [j for j in range(11 * t, 11 * t + 11) if j != c and m.bodies.active[j]]
    if mates:
        pos = m.bodies.pos[mates]
        vel = m.bodies.vel[mates]
        dist0 = np.sqrt(((pos - start) ** 2).sum(axis=1))
        lead = np.minimum(np.maximum(dist0 / 14.0, 0.3), 1.8)[:, None]
        ends = pos + vel * lead
        for k, j in enumerate(mates):
            run = m.plans.get(j)
            if run is not None and run.source == "run":
                ends[k] = 0.5 * ends[k] + 0.5 * np.asarray(run.target)
        ends[:, 0] = np.minimum(np.maximum(ends[:, 0], 0.5), LENGTH - 0.5)
        ends[:, 1] = np.minimum(np.maximum(ends[:, 1], 0.5), WIDTH - 0.5)
        rel_now = pos[:, 0] if d > 0 else LENGTH - pos[:, 0]
        seg = ends - start
        dist = np.sqrt((seg * seg).sum(axis=1))
        lanes = _segment_counts(start, ends, opp)
        seps = np.minimum(_nearest(ends, opp), 10.0)
        passing = m.attr(c, "passing")
        for k, j in enumerate(mates):
            if dist[k] < 4.0 or (j == m.gk_slot[t] and rx > 40.0):
                continue
            ex, ey = float(ends[k, 0]), float(ends[k, 1])
            fwd = float(seg[k, 0] * d / max(dist[k], 1e-6))
            if dist[k] > 34.0 or (lanes[k] >= 2 and dist[k] > 20.0):
                height = "high"
            elif dist[k] > 24.0 and lanes[k] >= 1:
                height = "low"
            else:
                height = "ground"
            feats = PassFeatures(
                float(dist[k]), fwd, pressure, int(lanes[k]), float(seps[k]), height, passing
            )
            prob = pass_completion(feats)
            run = m.plans.get(j)
            ptype = (
                "through_ball"
                if (run is not None and run.source == "run" and fwd > 0.5)
                else ("switch" if abs(seg[k, 1]) > 30.0 and height == "high" else "open_play")
            )
            if ptype == "through_ball":
                prob *= p.through_ball_difficulty
            offside = bool(rel_now[k] > off_line + 0.2 and rel_now[k] > 52.5)
            gain, loss = value_at(ex, ey)
            if fwd > 0.4:
                gain *= 0.75 + 0.5 * vision
            utility = prob * gain - (1.0 - prob) * loss
            if offside:
                utility -= p.offside_penalty
            add(
                Action(
                    "pass",
                    (ex, ey),
                    receiver=j,
                    height=height,
                    pass_type=ptype,
                    p_success=prob,
                    features=feats,
                    extra={"offside": offside},
                ),
                utility,
            )

    # carries: forward, diagonals, and a short hold
    carry_len = 3.0 if pressure < 2.5 else 6.5
    for angle in (0.0, 0.6, -0.6, 2.4):
        qx = rx + carry_len * math.cos(angle)
        qy = ry + carry_len * math.sin(angle)
        if not (1.0 < qx < LENGTH - 1.0 and 1.0 < qy < WIDTH - 1.0):
            continue
        ax, ay = to_abs(qx, qy, d)
        end = np.array([[ax, ay]])
        gaps = np.sqrt(((opp - end) ** 2).sum(axis=1))
        space = float(min(gaps.min(), 10.0))
        crowd = int((gaps < 5.0).sum())
        keep = 1.0 / (
            1.0 + math.exp(-(p.carry_keep_base + 0.9 * (space - 2.5) - p.carry_crowd * crowd))
        )
        gain, loss = value_at(ax, ay)
        add(
            Action("carry", (ax, ay), p_success=keep),
            p.carry_bias * (keep * gain - (1 - keep) * loss),
        )

    # take-on against the nearest defender in front
    near_k = int(np.argmin(((opp - start) ** 2).sum(axis=1))) if len(opp) else -1
    if near_k >= 0:
        defender_slots = [j for j in range(11 * (1 - t), 11 * (1 - t) + 11) if m.bodies.active[j]]
        dslot = defender_slots[near_k]
        dpos = opp[near_k]
        ddist = float(math.hypot(dpos[0] - start[0], dpos[1] - start[1]))
        drx, _ = to_rel(float(dpos[0]), float(dpos[1]), d)
        if ddist < 4.0 and drx > rx - 1.0:
            prob = dribble_success(m.attr(c, "dribbling"), m.attr(dslot, "tackling"))
            bx, by = to_abs(min(drx + 4.0, LENGTH - 1.0), ry, d)
            gain, loss = value_at(bx, by)
            add(
                Action("dribble", (bx, by), p_success=prob, opponent=dslot),
                p.dribble_bias * (prob * gain - (1 - prob) * loss),
            )

    # shot
    dist_goal = goal_distance(rx, ry)
    shot_on = m.rng.random() < p.shot_consider  # body shape and lane allow a shot this time?
    if dist_goal < p.shot_range_m and shot_on and m.steer.can_shoot(m, c):
        feats = shot_features(m, c, assist=m.recent_assist(c))
        xg = expected_goals(feats)
        if goal_angle(rx, ry) > 0.15 or dist_goal < 10.0:
            gx, gy = to_abs(LENGTH, 34.0, d)
            add(
                Action("shot", (gx, gy), features=feats, p_success=xg),
                p.shot_bias * xg + (1.0 - xg) * p.shot_retain * (here + c_poss) - p.shot_cost,
            )

    # cross from wide in the final third
    if rx > 78.0 and abs(ry - 34.0) > 13.0:
        for qx, qy in ((99.0, 31.0), (94.0, 34.0), (99.0, 38.0)):
            ax, ay = to_abs(qx, qy, d)
            header = expected_goals(
                ShotFeatures(goal_distance(qx, qy), goal_angle(qx, qy), True, "cross", 1)
            )
            add(
                Action("cross", (ax, ay), height="high", pass_type="cross", p_success=0.33),
                p.cross_bias * 0.33 * (header * 1.6 + c_poss) - 0.67 * keep_w * here,
            )

    # clearance under pressure deep in its own half (sometimes into touch)
    if rx < 30.0 and pressure < 4.0:
        side = 1.0 if ry > 34.0 else -1.0
        if m.rng.random() < 0.4:
            ax, ay = to_abs(rx + 25.0, 34.0 + side * 40.0, d)
        else:
            ax, ay = to_abs(min(rx + 42.0, 80.0), min(max(ry + 10.0 * side, 4.0), WIDTH - 4.0), d)
        add(
            Action("clearance", (ax, ay), height="high"),
            p.clearance_bias * (1.5 if rx < 18.0 else 1.0) * (4.0 - pressure) / 2.0
            + 0.3 * c_poss
            - 0.8 * keep_w * here,
        )

    temperature = p.temperature * (1.3 - m.attr(c, "composure") / 100.0)
    u = np.array(utils) / temperature
    probs = np.exp(u - u.max())
    probs /= probs.sum()
    return actions[int(m.rng.choice(len(actions), p=probs))]
