"""Dead balls: stoppages with realistic delays, set pieces, kick-offs and substitutions."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from regista_sim.engine.clock import match_minute
from regista_sim.engine.decisions import Action, pass_features, shot_features
from regista_sim.engine.events import EventRef, loc
from regista_sim.engine.state import BallState, Flight, Plan, Restart
from regista_sim.pitch import (
    BOX_DEPTH,
    LENGTH,
    WIDTH,
    goal_angle,
    goal_distance,
    to_abs,
    to_rel,
)

if TYPE_CHECKING:
    from regista_sim.engine.match import Match

_KICKOFF_SPOT = (52.5, 34.0)


def stop_play(
    m: Match,
    reason: str,
    kind: str,
    team: int,
    spot: tuple[float, float],
    delay: tuple[float, float],
) -> None:
    """Whistle: log a ``stoppage`` and set up the restart for ``team`` at ``spot``."""
    from regista_sim.engine import onball  # local import: onball imports this module

    if m.ball_state == BallState.CONTROLLED:
        onball.end_spell(m)
    onball.close_all_pressure(m)
    m.ball_state = BallState.DEAD
    m.carrier = -1
    m.flight = None
    m.path = []
    sx = min(max(spot[0], 0.0), LENGTH)
    sy = min(max(spot[1], 0.0), WIDTH)
    lo, hi = delay
    ticks = round((lo + (hi - lo) * m.rng.random() ** 0.6) * 1000 / m.params.tick_ms)
    ticks = m.steer.restart_ticks(m, kind, ticks, round(lo * 1000 / m.params.tick_ms))
    m.restart = Restart(
        kind=kind, team=team, spot=(sx, sy), ready_tick=m.tick + ticks, reason=reason
    )
    m.cancel_engine_plans(0)
    m.cancel_engine_plans(1)
    m.restart.taker = choose_taker(m, kind, team, (sx, sy))
    m.events.add(
        "stoppage",
        m.clock.period,
        m.clock.clock_ms,
        team=m.teams[team].code,
        location=loc(sx, sy),
        payload={"reason": reason, "restart_type": kind},
    )
    substitutions(m)
    m.steer.on_stoppage(m, reason, kind, team)


def goal_scored(m: Match, f: Flight, crossing: tuple[float, float], ref: EventRef) -> None:
    """Score, stop play, log the new score; the conceding team kicks off."""
    t = f.team
    m.teams[t].score += 1
    m.goals.append(
        {
            "team": m.teams[t].code,
            "credited": f.event_meta["player"],
            "shooter": m.pid(f.actor),
            "period": m.clock.period,
            "clock_ms": f.start_clock_ms,
            "tag": f.truth.get("tag", ""),
            "ref": ref,
        }
    )
    stop_play(m, "goal", "kick_off", 1 - t, _KICKOFF_SPOT, m.params.delay_goal)
    m.events.add(
        "score_update",
        m.clock.period,
        m.clock.clock_ms,
        payload={"home": m.teams[0].score, "away": m.teams[1].score},
    )
    net_x = LENGTH + 1.2 if crossing[0] > 52.5 else -1.2
    m.bx, m.by, m.bz = net_x, crossing[1], 0.11
    m.ball_wait_until = m.tick + 40
    m.steer.on_goal(m, f)


def choose_taker(
    m: Match, kind: str, team: int, spot: tuple[float, float], avoid_scripted: bool = False
) -> int:
    """Pick who takes the restart (``avoid_scripted``: skip players a scenario is moving)."""
    slots = [s for s in range(11 * team, 11 * team + 11) if m.bodies.active[s]]
    if avoid_scripted:
        free = [s for s in slots if (p := m.plans.get(s)) is None or p.source != "scenario"]
        slots = free or slots
    if kind == "goal_kick":
        return m.gk_slot[team]
    if kind == "penalty":
        outfield = [s for s in slots if s != m.gk_slot[team] and m.steer.can_shoot(m, s)]
        outfield = outfield or [s for s in slots if s != m.gk_slot[team]]
        return max(outfield, key=lambda s: (m.attr(s, "finishing"), -s))
    if kind == "kick_off":
        forwards = [s for s in slots if m.role_kind[s] in ("ST", "AM", "W")] or slots
        return min(forwards, key=lambda s: (abs(m.role_depth[s] - 35.0), s))
    outfield = [s for s in slots if s != m.gk_slot[team]]
    dist = [
        math.hypot(m.bodies.pos[s, 0] - spot[0], m.bodies.pos[s, 1] - spot[1]) for s in outfield
    ]
    order = [outfield[i] for i in np.argsort(dist, kind="stable")]
    if kind in ("corner", "free_kick"):
        return max(order[:4], key=lambda s: (m.attr(s, "passing"), -s))
    return order[0]


def dead_step(m: Match) -> None:
    """Send the taker to the spot; take the restart once the delay is over."""
    r = m.restart
    if r is None:
        return
    held = m.plans.get(r.taker)
    if not m.bodies.active[r.taker] or (
        held is not None and held.source == "scenario" and m.tick >= r.ready_tick
    ):
        r.taker = choose_taker(m, r.kind, r.team, r.spot, avoid_scripted=True)
    gap = math.hypot(m.bodies.pos[r.taker, 0] - r.spot[0], m.bodies.pos[r.taker, 1] - r.spot[1])
    plan = m.plans.get(r.taker)
    if plan is None or plan.source != "scenario":
        m.set_plan(r.taker, Plan(r.spot, 0.55 if gap > 8.0 else 0.15, source="taker"))
    ball_gap = math.hypot(m.bx - r.spot[0], m.by - r.spot[1])
    if m.tick >= r.ready_tick and gap <= 1.2 and ball_gap < 0.2:
        take_restart(m)


def move_dead_ball(m: Match) -> None:
    """The ball is brought back to the restart spot at walking (or jogging) pace."""
    r = m.restart
    if r is None or m.tick < m.ball_wait_until:
        return
    dx, dy = r.spot[0] - m.bx, r.spot[1] - m.by
    gap = math.hypot(dx, dy)
    if gap < 1e-6:
        m.bz = 0.11
        return
    speed = 7.0 if r.reason == "goal" else 3.0
    step = min(gap, speed * m.params.tick_ms / 1000.0)
    m.bx += dx / gap * step
    m.by += dy / gap * step
    m.bz = 0.11


def take_restart(m: Match) -> None:
    """Play the restart: throw-in, goal kick, corner, free kick, penalty or kick-off."""
    from regista_sim.engine import onball
    from regista_sim.engine.flight import launch_pass, launch_shot

    r = m.restart
    assert r is not None
    m.restart = None
    c = r.taker
    m.clear_plan(c)
    m.bx, m.by, m.bz = r.spot[0], r.spot[1], 0.11
    m.set_possession(r.team)
    m.ball_state = BallState.CONTROLLED
    m.carrier = c
    m.spell = None
    action = m.steer.restart_action(m, r) or _restart_action(m, r, c)
    if action.kind == "shot":
        shot_type = "penalty" if r.kind == "penalty" else "free_kick"
        if action.features is None:
            action.features = shot_features(m, c, penalty=r.kind == "penalty")
        launch_shot(m, c, action, shot_type=shot_type)
    elif action.kind == "carry":
        onball.gain_control(m, c, how="restart")
    else:
        launch_pass(m, c, action)


def _restart_action(m: Match, r: Restart, c: int) -> Action:
    t = r.team
    d = m.teams[t].direction
    rx, ry = to_rel(r.spot[0], r.spot[1], d)
    mates = [s for s in range(11 * t, 11 * t + 11) if s != c and m.bodies.active[s]]
    if r.kind == "penalty":
        return Action("shot", to_abs(LENGTH, 34.0, d))
    if (
        r.kind == "free_kick"
        and goal_distance(rx, ry) < 28.0
        and goal_angle(rx, ry) > 0.28
        and m.rng.random() < 0.45
        and m.steer.can_shoot(m, c)
    ):
        return Action("shot", to_abs(LENGTH, 34.0, d))
    if r.kind == "corner":
        qx, qy = ((99.0, 30.5), (94.0, 34.0), (99.5, 37.5))[int(m.rng.integers(3))]
        tx, ty = to_abs(qx, qy, d)
        receiver = min(
            mates, key=lambda s: (math.hypot(m.bodies.pos[s, 0] - tx, m.bodies.pos[s, 1] - ty), s)
        )
        return Action("pass", (tx, ty), receiver=receiver, height="high", pass_type="corner")
    if r.kind == "kick_off":
        back = [s for s in mates if to_rel(*m.bodies.pos[s], d)[0] < 50.0]
        receiver = min(back or mates, key=lambda s: (math.hypot(*(m.bodies.pos[s] - r.spot)), s))
        return Action("pass", tuple(m.bodies.pos[receiver]), receiver=receiver)
    long_ball = r.kind == "goal_kick" and m.rng.random() < 0.55
    best, best_u = mates[0], -1e9
    for s in mates:
        target = (float(m.bodies.pos[s, 0]), float(m.bodies.pos[s, 1]))
        dist = math.hypot(target[0] - r.spot[0], target[1] - r.spot[1])
        if r.kind == "throw_in" and not 5.0 < dist < 26.0:
            continue
        if long_ball and dist < 30.0:
            continue
        feats = pass_features(m, c, target, "high" if long_ball else "ground")
        u = feats.separation * 0.4 - feats.lane - 0.02 * dist + m.rng.normal(0.0, 0.6)
        if u > best_u:
            best, best_u = s, u
    target = (float(m.bodies.pos[best, 0]), float(m.bodies.pos[best, 1]))
    ptype = {"throw_in": "throw_in", "goal_kick": "goal_kick", "free_kick": "free_kick"}[r.kind]
    height = "low" if r.kind == "throw_in" else ("high" if long_ball else "ground")
    return Action("pass", target, receiver=best, height=height, pass_type=ptype)


_CORNER_ATTACKERS = ("ST", "W", "AM", "CM", "WM", "CB")


def restart_targets(m: Match, target: np.ndarray, urgency: np.ndarray, cruise: np.ndarray) -> None:
    """Set-piece positions during a dead ball (kick-off shape, corners, penalties)."""
    r = m.restart
    if r is None:
        return
    if r.kind in ("kick_off", "corner", "penalty"):
        for t in (0, 1):
            s = slice(11 * t, 11 * t + 11)
            d = m.teams[t].direction
            x = target[s, 0] if d > 0 else LENGTH - target[s, 0]
            y = target[s, 1] if d > 0 else WIDTH - target[s, 1]
            if r.kind == "kick_off":
                x = np.minimum(x, 50.0 if t == r.team else 42.0)
            elif r.kind == "corner":
                attacking = t == r.team
                idx = np.arange(11 * t, 11 * t + 11)
                kinds = m.role_kind[11 * t : 11 * t + 11]
                movers = np.array(
                    [
                        (k in _CORNER_ATTACKERS) if attacking else (k not in ("ST", "GK"))
                        for k in kinds
                    ]
                )
                x = np.where(
                    movers, 92.0 + (idx % 4) * 2.5 if attacking else 2.0 + (idx % 5) * 2.2, x
                )
                y = np.where(movers, 27.0 + (idx % 6) * 2.8, y)
            else:
                keep = np.zeros(11, dtype=bool)
                keep[m.gk_slot[t] - 11 * t] = True
                if m.team_of(r.taker) == t:
                    keep[r.taker - 11 * t] = True
                moved = (
                    np.minimum(x, LENGTH - BOX_DEPTH - 2.0)
                    if t == r.team
                    else np.maximum(x, BOX_DEPTH + 2.0)
                )
                x = np.where(keep, x, moved)
            target[s, 0] = x if d > 0 else LENGTH - x
            target[s, 1] = y if d > 0 else WIDTH - y
    target[r.taker] = r.spot
    urgency[r.taker] = max(urgency[r.taker], 0.3)
    np.maximum(cruise, m.params.cruise_dead, out=cruise)


def kickoff_positions(m: Match, kicking: int) -> None:
    """Place both teams for a period kick-off (teleport: tracking starts here)."""
    for t in (0, 1):
        d = m.teams[t].direction
        for s in range(11 * t, 11 * t + 11):
            depth, y = float(m.role_depth[s]), float(m.role_y[s])
            x = (
                4.0
                if m.role_kind[s] == "GK"
                else min(24.0 + depth * 0.72, 49.0 if t == kicking else 42.0)
            )
            m.bodies.pos[s] = to_abs(x, 34.0 + (y - 34.0) * 0.8, d)
            m.bodies.vel[s] = 0.0
    taker = choose_taker(m, "kick_off", kicking, _KICKOFF_SPOT)
    m.bodies.pos[taker] = _KICKOFF_SPOT


def substitutions(m: Match) -> None:
    """Make the scenario's due substitutions, then the engine's tired-player changes."""
    due = list(m.steer.due_substitutions(m))
    minute = match_minute(m.clock.period, m.clock.clock_ms)
    for t in (0, 1):
        team = m.teams[t]
        if minute < m.params.sub_from_minute + m.sub_offset[t] or team.subs_used >= m.sub_limit[t]:
            continue
        wanted = min(1 + (minute - m.params.sub_from_minute - m.sub_offset[t]) // 8, m.sub_limit[t])
        pending = sum(1 for d in due if d[0] == t)
        if team.subs_used + pending < wanted:
            out = m.tired_player(t)
            incoming = m.bench_match(t, out) if out else None
            if out and incoming:
                due.append((t, out, incoming))
    made = False
    for t, out, incoming in due:
        if m.substitute(t, out, incoming):
            made = True
    if made and m.restart is not None:
        extra = round(m.rng.uniform(*m.params.delay_substitution) * 1000 / m.params.tick_ms)
        m.restart.ready_tick = max(m.restart.ready_tick, m.tick + extra)
