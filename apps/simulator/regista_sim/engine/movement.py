"""Movement of all 22 players (vectorized, docs/DATA_AND_METRICS.md §2).

Target = formation anchor shifted with the ball and the phase (width and height in possession,
compactness and line height out of possession) + role behaviour (pressing, marking, support,
runs in behind, recovery runs) + noise. Velocity is then integrated with an acceleration that
falls with speed, a top speed from ``pace``, both reduced by fatigue. Scenario plans only change
targets and speed caps; nothing here ever writes a position directly.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from regista_sim.engine.state import BallState
from regista_sim.pitch import LENGTH, WIDTH

if TYPE_CHECKING:
    from regista_sim.engine.match import Match

_GK = 0
CARRY_MARGIN_M = 0.8  # a ball carrier never aims closer than this to a line


def _team_shape(m: Match, t: int, attacking: bool) -> tuple[np.ndarray, np.ndarray]:
    """Team-relative zonal targets for the 11 slots of team ``t``."""
    team = m.teams[t]
    dial = m.dials[t]
    s = slice(11 * t, 11 * t + 11)
    bx, by = m.ball_rel(team.direction)
    depth = m.role_depth[s]
    ry = m.role_y[s]
    if attacking:
        line = min(max(36.0 + 14.0 * dial["defensive_line"] + 0.55 * (bx - 52.5), 20.0), 64.0)
        x = line + depth * 1.12
        y = 34.0 + (ry - 34.0) * (0.88 + 0.30 * dial["width"]) + 0.15 * (by - 34.0)
        x = np.minimum(x, max(m.offside_line(t) - 0.7, 30.0))
    else:
        line = min(max(26.0 + 20.0 * dial["defensive_line"] + 0.45 * (bx - 52.5), 8.0), 50.0)
        line = min(line, max(bx - 3.0, 6.0))
        x = line + depth * (0.80 - 0.12 * dial["pressing_intensity"])
        y = 34.0 + (ry - 34.0) * (0.62 + 0.12 * dial["width"]) + 0.42 * (by - 34.0)
    gk = m.gk_slot[t] - 11 * t
    if attacking:
        x[gk] = 6.0 + 0.10 * bx
        y[gk] = 34.0 + 0.08 * (by - 34.0)
    else:
        dx, dy = bx, by - 34.0
        dist = math.sqrt(dx * dx + dy * dy) + 1e-6
        reach = min(max(0.11 * dist, 1.2), 6.5)
        x[gk] = dx / dist * reach
        y[gk] = 34.0 + dy / dist * reach
    return x, y


def _marking(m: Match, t: int, target: np.ndarray) -> None:
    """Pull defending outfield players goal-side of the nearest attacker within 12 m."""
    s = slice(11 * t, 11 * t + 11)
    o = slice(11 * (1 - t), 11 * (1 - t) + 11)
    mine, theirs = target[s], m.bodies.pos[o]
    diff = mine[:, None, :] - theirs[None, :, :]
    dist2 = (diff * diff).sum(axis=2)
    dist2[:, ~m.bodies.active[o]] = 1e9
    nearest = dist2.argmin(axis=1)
    close = dist2[np.arange(11), nearest] < 144.0
    close[m.gk_slot[t] - 11 * t] = False
    goal_x = 0.0 if m.teams[t].direction > 0 else LENGTH
    marks = theirs[nearest].copy()
    marks[:, 0] += np.sign(goal_x - marks[:, 0]) * 2.0
    bx, _ = m.ball_rel(m.teams[t].direction)
    w = min(
        m.params.marking_weight + m.params.marking_box_bonus * max(0.0, (50.0 - bx) / 50.0), 0.9
    )
    mine[close] = (1.0 - w) * mine[close] + w * marks[close]


def _zonal(m: Match) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Zonal targets, recovery urgency and cruise speed for both teams (refreshed at 5 Hz)."""
    p = m.params
    target = np.empty((22, 2))
    urgency = np.zeros(22)
    cruise = np.empty(22)
    dead = m.ball_state == BallState.DEAD
    for t in (0, 1):
        s = slice(11 * t, 11 * t + 11)
        team = m.teams[t]
        attacking = (
            (m.restart.team == t) if (dead and m.restart is not None) else m.attacking_team == t
        )
        x, y = _team_shape(m, t, attacking)
        x = np.minimum(np.maximum(x + m.bodies.noise[s, 0], 0.8), LENGTH - 0.8)
        y = np.minimum(np.maximum(y + m.bodies.noise[s, 1], 1.0), WIDTH - 1.0)
        if team.direction > 0:
            target[s, 0], target[s, 1] = x, y
            rel_pos = m.bodies.pos[s, 0]
        else:
            target[s, 0], target[s, 1] = LENGTH - x, WIDTH - y
            rel_pos = LENGTH - m.bodies.pos[s, 0]
        dial = m.dials[t]
        if dead:
            cruise[s] = p.cruise_dead
            continue
        if attacking:
            cruise[s] = (p.cruise_attack + p.tempo_cruise * dial["tempo"]) * m.work_rate[s]
            urgency[s] = np.minimum(
                np.maximum((x - rel_pos - p.surge_slack) / p.surge_span, 0.0), p.surge_max
            )
        else:
            cruise[s] = (
                p.cruise_defend + p.press_cruise * dial["pressing_intensity"]
            ) * m.work_rate[s]
            urgency[s] = np.minimum(
                np.maximum((rel_pos - x - p.recover_slack) / p.recover_span, 0.0), 1.0
            )
            _marking(m, t, target)
    return target, urgency, cruise


def compute_targets(m: Match) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return absolute targets (22, 2), urgency (22,) and cruise speed (22,) for every slot."""
    key = (int(m.ball_state), m.attacking_team, m.restart.kind if m.restart else "")
    if m.tick % 2 == 0 or m.zonal_key != key or m.zonal is None:
        m.zonal = _zonal(m)
        m.zonal_key = key
    target, urgency, cruise = (a.copy() for a in m.zonal)
    if m.smooth_target is None or m.tick == 0:
        m.smooth_target = target.copy()
    m.smooth_target += m.params.target_smoothing * (target - m.smooth_target)  # no jitter
    target[:] = m.smooth_target
    if m.ball_state == BallState.DEAD:
        m.restart_targets(target, urgency, cruise)
    else:
        _pressing(m, target, urgency)
        _support(m, target)
    for slot, plan in m.plans.items():
        target[slot] = plan.target
        urgency[slot] = plan.urgency
    if m.ball_state == BallState.CONTROLLED and m.carrier >= 0:  # a carrier keeps the ball in
        c = m.carrier
        target[c, 0] = min(max(target[c, 0], CARRY_MARGIN_M), LENGTH - CARRY_MARGIN_M)
        target[c, 1] = min(max(target[c, 1], CARRY_MARGIN_M), WIDTH - CARRY_MARGIN_M)
    return target, urgency, cruise


def _pressing(m: Match, target: np.ndarray, urgency: np.ndarray) -> None:
    """Press the carrier inside the press zone; near goal, cover the line to goal as well."""
    if m.ball_state != BallState.CONTROLLED or m.carrier < 0:
        return
    t = 1 - m.team_of(m.carrier)
    pressing = m.dials[t]["pressing_intensity"]
    bx, _ = m.ball_rel(m.teams[t].direction)
    in_zone = bx <= m.params.press_zone_base + m.params.press_zone_span * pressing
    danger = bx < m.params.cover_zone_m
    if not (in_zone or danger):
        return
    s = slice(11 * t, 11 * t + 11)
    carrier = m.bodies.pos[m.carrier]
    diff = m.bodies.pos[s] - carrier
    dist2 = (diff * diff).sum(axis=1)
    dist2[m.gk_slot[t] - 11 * t] = 1e9
    dist2[~m.bodies.active[s]] = 1e9
    order = [11 * t + int(k) for k in np.argsort(dist2, kind="stable")]
    lead = carrier + m.bodies.vel[m.carrier] * 0.3
    goal = np.array((0.0 if m.teams[t].direction > 0 else LENGTH, 34.0))
    to_goal = goal - carrier
    to_goal /= max(float(np.sqrt((to_goal * to_goal).sum())), 1e-6)
    side = np.array((-to_goal[1], to_goal[0]))
    jobs: list[tuple[np.ndarray, float]] = [(lead, 0.45 + 0.55 * pressing)]
    if danger:
        ahead = carrier + m.bodies.vel[m.carrier] * 0.6
        jobs[0] = (lead + to_goal * 0.8, 0.9)
        jobs.append((ahead + to_goal * 3.0, 1.0))
        if bx < m.params.cover_zone_m - 10.0:
            jobs.append((ahead + to_goal * 6.0 + side * 1.2, 0.9))
    elif pressing > 0.5:
        jobs.append((0.65 * lead + 0.35 * goal, 0.45 + 0.55 * pressing))
    pressers: list[int] = []
    free = [slot for slot in order if slot not in m.plans and dist2[slot - 11 * t] < 30.0**2]
    for spot, urge in jobs:  # each job goes to the nearest free defender to *its* spot
        if not free:
            break
        gaps = [float(((m.bodies.pos[slot] - spot) ** 2).sum()) for slot in free]
        slot = free.pop(int(np.argmin(gaps)))
        target[slot] = spot
        urgency[slot] = urge
        pressers.append(slot)
    m.pressers = pressers


def _support(m: Match, target: np.ndarray) -> None:
    """The nearest teammate offers a short, safe angle to the ball carrier."""
    if m.ball_state != BallState.CONTROLLED or m.carrier < 0:
        return
    t = m.team_of(m.carrier)
    s = slice(11 * t, 11 * t + 11)
    carrier = m.bodies.pos[m.carrier]
    diff = m.bodies.pos[s] - carrier
    dist2 = (diff * diff).sum(axis=1)
    dist2[m.carrier - 11 * t] = 1e9
    dist2[m.gk_slot[t] - 11 * t] = 1e9
    slot = 11 * t + int(np.argmin(dist2))
    if slot in m.plans:
        return
    d = m.teams[t].direction
    side = 1.0 if carrier[1] < target[slot, 1] else -1.0
    offer = carrier + np.array((-6.0 * d, 9.0 * side))
    target[slot] = 0.5 * target[slot] + 0.5 * offer


_LO = np.array((-1.5, -1.5))
_HI = np.array((LENGTH + 1.5, WIDTH + 1.5))


def integrate(m: Match, target: np.ndarray, urgency: np.ndarray, cruise: np.ndarray) -> None:
    """Advance every active body one tick towards its target (in place)."""
    b, p = m.bodies, m.params
    dt = p.tick_ms / 1000.0
    vmax_eff = b.vmax * (0.93 + 0.07 * b.energy)
    hard = np.minimum(vmax_eff, m.speed_cap)
    for slot, plan in m.plans.items():
        if plan.speed_cap is not None:
            hard[slot] = plan.speed_cap
    cap = np.minimum(cruise + urgency * (vmax_eff - cruise), hard)
    disp = target - b.pos
    dist = np.sqrt((disp * disp).sum(axis=1))
    want = np.minimum(dist * p.arrival_gain, cap)
    dv = disp * (want / np.maximum(dist, 1e-9))[:, None] - b.vel
    speed = np.sqrt((b.vel * b.vel).sum(axis=1))
    a0_eff = b.a0 * (0.9 + 0.1 * b.energy)
    a_lim = np.where(
        want > speed, a0_eff * (1.0 - p.accel_falloff * speed / vmax_eff), p.brake_factor * a0_eff
    )
    dvn = np.sqrt((dv * dv).sum(axis=1))
    scale = np.minimum(1.0, np.maximum(a_lim, 0.3) * dt / np.maximum(dvn, 1e-9))
    b.vel += dv * scale[:, None]
    speed = np.sqrt((b.vel * b.vel).sum(axis=1))
    over = speed > hard
    if over.any():
        b.vel[over] *= (hard[over] / speed[over])[:, None]
        speed = np.minimum(speed, hard)
    if not b.active.all():
        b.vel[~b.active] = 0.0
    b.pos += b.vel * dt
    np.minimum(np.maximum(b.pos, _LO, out=b.pos), _HI, out=b.pos)
    m.effort_acc += speed / b.vmax
    if m.tick % 10 == 9:
        _fatigue(m, m.effort_acc / 10.0, 1.0)
        m.effort_acc[:] = 0.0


def _fatigue(m: Match, effort: np.ndarray, dt: float) -> None:
    b, p = m.bodies, m.params
    drain = p.fatigue_drain * effort * effort * (1.3 - b.stamina) + p.fatigue_base
    recover = np.where(effort < 0.25, p.fatigue_recovery, 0.0)
    b.energy = np.clip(b.energy - (drain - recover) * dt, 0.0, 1.0)


def update_noise(m: Match) -> None:
    """Advance each player's Ornstein-Uhlenbeck target wobble (every second tick)."""
    if m.tick % 2:
        return
    p = m.params
    dt = 2 * p.tick_ms / 1000.0
    theta = dt / p.noise_tau_s
    m.bodies.noise += -theta * m.bodies.noise + p.noise_sigma * math.sqrt(
        2.0 * theta
    ) * m.rng_move.standard_normal((22, 2))
