"""Advance a ball flight one tick and resolve receptions, interceptions, saves and exits."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from regista_sim.engine import onball, restarts
from regista_sim.engine.decisions import Action
from regista_sim.engine.events import loc
from regista_sim.engine.flight import (
    finish_pass,
    finish_shot,
    in_goal_mouth,
    launch_shot,
    loose_ball,
)
from regista_sim.engine.models import aerial_win
from regista_sim.engine.state import Flight, Plan
from regista_sim.pitch import GOAL_HALF_WIDTH, GOAL_HEIGHT, LENGTH, WIDTH, in_box, to_rel

if TYPE_CHECKING:
    from regista_sim.engine.match import Match


def advance(m: Match) -> None:
    """Move the ball along its path, then let the right player take it (or let it go out)."""
    f = m.flight
    assert f is not None
    if f.start_tick == m.tick:
        return  # struck this tick: the frame shows the ball at the point of release
    prev = (m.bx, m.by, m.bz)
    if m.path_k < len(m.path):
        m.bx, m.by, m.bz = m.path[m.path_k]
        m.path_k += 1
    x, y, z = m.bx, m.by, m.bz
    if not (0.0 <= x <= LENGTH and 0.0 <= y <= WIDTH):
        _exit(m, f, prev, (x, y, z))
        return
    k = m.path_k
    gk_taker = f.kind == "shot" and f.taker == m.gk_slot[1 - f.team]
    if f.kind == "shot" and f.planned == "blocked" and f.taker >= 0 and k > f.deadline_k:
        gk = m.gk_slot[1 - f.team]  # the blocker missed it: now it is the keeper's
        f.planned, f.taker, f.stop_at, f.deadline_k = "saved", gk, None, len(m.path)
        gk_taker = True
    if f.taker >= 0 and f.truth.get("tag") and f.kind == "pass" and m.bodies.active[f.taker]:
        _chase_scripted(m, f, k)
    early = (
        bool(f.truth.get("tag"))
        and f.kind == "pass"
        and k < f.truth.get("arrive_k", 0) - 1
        and m.path_k < len(m.path)
        and math.hypot(x - f.target[0], y - f.target[1]) > 1.5
    )
    if early and f.taker >= 0:
        return  # a scripted pass is the receiver's alone, and only at its point
    if f.taker >= 0 and k <= f.deadline_k and m.bodies.active[f.taker]:
        reach = 2.6 if gk_taker else (2.2 if f.stop_at is not None else m.params.control_radius_m)
        if f.stop_at is not None and k >= f.deadline_k - 1:
            reach = 3.0
        gap = math.hypot(m.bodies.pos[f.taker, 0] - x, m.bodies.pos[f.taker, 1] - y)
        if gap <= reach and z <= (2.8 if gk_taker else 2.4):
            _taken(m, f, f.taker)
            return
        if gk_taker and _crossing_line(f, x):
            _taken(m, f, f.taker)  # a planned save is completed on the line
            return
        return
    if f.kind == "shot" and f.planned != "goal" and f.taker < 0:
        return  # off target / post / goal: only the line decides
    if f.kind == "shot" and f.planned == "goal":
        return
    _free_ball(m, f, x, y, z)


def _chase_scripted(m: Match, f: Flight, k: int) -> None:
    """A scripted receiver runs to the first point of the ball's path he can reach in time."""
    if not m.path:
        return
    px, py = m.bodies.pos[f.taker]
    vmax = 0.9 * float(m.bodies.vmax[f.taker])
    cap = f.truth.get("receiver_cap")
    dt = m.params.tick_ms / 1000.0
    target = m.path[-1]
    for j in range(max(k, f.truth.get("arrive_k", 0) - 1, 0), len(m.path)):
        x, y, z = m.path[j]
        if not (0.5 < x < LENGTH - 0.5 and 0.5 < y < WIDTH - 0.5):
            break
        if z < 2.0 and math.hypot(x - px, y - py) <= vmax * (j - k + 1) * dt + 0.8:
            target = m.path[j]
            break
        target = m.path[j]
    m.plans[f.taker] = Plan(
        (target[0], target[1]), 1.0, speed_cap=cap, until_tick=m.tick + 3, source="scenario"
    )


def _crossing_line(f: Flight, x: float) -> bool:
    return (x >= LENGTH - 0.4) if f.target[0] > 52.5 else (x <= 0.4)


def _free_ball(m: Match, f: Flight, x: float, y: float, z: float) -> None:
    """Nobody is designated: the first player to reach it takes it; nearest ones chase."""
    if z > 2.2:
        _chase(m, x, y)
        return
    pos = m.bodies.pos
    best, best_gap = -1, m.params.control_radius_m
    for slot in range(22):
        if not m.bodies.active[slot]:
            continue
        if slot == f.actor and m.tick - f.start_tick < 6:
            continue
        gap = math.hypot(pos[slot, 0] - x, pos[slot, 1] - y)
        if gap < best_gap:
            best, best_gap = slot, gap
    if best >= 0:
        _taken(m, f, best)
    else:
        _chase(m, x, y)


def _chase(m: Match, x: float, y: float) -> None:
    """The nearest outfield player of each team runs to where the ball is going."""
    k = min(m.path_k + 5, len(m.path) - 1)
    tx, ty = (m.path[k][0], m.path[k][1]) if m.path else (x, y)
    tx = min(max(tx, 0.5), LENGTH - 0.5)
    ty = min(max(ty, 0.5), WIDTH - 0.5)
    for t in (0, 1):
        best, best_d = -1, 1e9
        for slot in range(11 * t, 11 * t + 11):
            if not m.bodies.active[slot] or slot == m.gk_slot[t]:
                continue
            plan = m.plans.get(slot)
            if plan is not None and plan.source == "scenario":
                continue
            d = math.hypot(m.bodies.pos[slot, 0] - tx, m.bodies.pos[slot, 1] - ty)
            if d < best_d:
                best, best_d = slot, d
        if best >= 0:
            m.set_plan(best, Plan((tx, ty), 1.0, until_tick=m.tick + 3, source="chase"))


def _taken(m: Match, f: Flight, slot: int) -> None:
    """``slot`` gets to the ball first: resolve by flight kind."""
    x, y, z = m.bx, m.by, m.bz
    same_team = m.team_of(slot) == f.team
    if f.kind == "pass":
        if same_team:
            if f.planned == "offside" and slot == f.receiver:
                finish_pass(m, f, "offside", (x, y), slot)
                restarts.stop_play(
                    m, "offside", "free_kick", 1 - f.team, (x, y), m.params.delay_offside
                )
                return
            if f.payload["height"] == "high" and _lost_aerial(m, slot):
                return
            finish_pass(m, f, "complete", (x, y), slot)
            if _header_chance(m, f, slot, z):
                return
            onball.gain_control(m, slot, how="reception", pass_type=f.payload["pass_type"])
        else:
            finish_pass(m, f, "incomplete", (x, y), None)
            if slot == f.taker and (_deflect_behind(m, slot) or _deflect_into_touch(m, slot)):
                return
            if slot == f.taker and m.rng.random() < 0.18:  # a touch, not control: deflected loose
                m.events.add(
                    "interception",
                    m.clock.period,
                    m.clock.clock_ms,
                    **m.event_args(slot),
                    payload={"outcome": "lost"},
                )
                m.clear_plan(slot)
                loose_ball(
                    m,
                    m.team_of(slot),
                    slot,
                    m.rng.uniform(4.0, 9.0),
                    math.atan2(f.vy, f.vx) + m.rng.uniform(-1.4, 1.4),
                )
                return
            kind = "interception" if slot == f.taker else "ball_recovery"
            m.events.add(
                kind,
                m.clock.period,
                m.clock.clock_ms,
                **m.event_args(slot, possession_change=True),
                payload={"outcome": "success"},
            )
            onball.gain_control(m, slot, how=kind)
        return
    if f.kind == "shot":
        if slot == m.gk_slot[1 - f.team]:
            finish_shot(m, f, "saved", (x, y, z))
            m.clear_plan(slot)
            if m.rng.random() < 0.58:
                onball.gain_control(m, slot, how="save")
            elif m.rng.random() < 0.7:  # parried behind for a corner
                behind = math.pi if m.teams[1 - f.team].direction > 0 else 0.0
                side = 1.0 if m.by > 34.0 else -1.0
                loose_ball(
                    m,
                    1 - f.team,
                    slot,
                    m.rng.uniform(5.0, 9.0),
                    behind + side * (1.0 if behind == 0.0 else -1.0) * m.rng.uniform(0.5, 1.1),
                    2.0,
                )
            else:
                away = 0.0 if m.teams[1 - f.team].direction > 0 else math.pi
                loose_ball(
                    m,
                    1 - f.team,
                    slot,
                    m.rng.uniform(6.0, 10.0),
                    away + m.rng.uniform(-1.2, 1.2),
                    2.5,
                )
            return
        m.events.add(
            "block",
            m.clock.period,
            m.clock.clock_ms,
            **m.event_args(slot),
            payload={"outcome": "success", "opponent_id": m.pid(f.actor)},
        )
        finish_shot(m, f, "blocked", (x, y, z))
        m.clear_plan(slot)
        out = 0.0 if m.teams[m.team_of(slot)].direction > 0 else math.pi
        if m.rng.random() < 0.45:  # deflected behind for a corner
            out = math.pi - out
        loose_ball(
            m, m.team_of(slot), slot, m.rng.uniform(4.0, 11.0), out + m.rng.uniform(-1.3, 1.3), 1.5
        )
        return
    # clearance or loose ball
    if m.possession_team >= 0 and m.team_of(slot) != m.possession_team:
        m.events.add(
            "ball_recovery",
            m.clock.period,
            m.clock.clock_ms,
            **m.event_args(slot, possession_change=True),
            payload={"outcome": "success"},
        )
    onball.gain_control(m, slot, how="recovery")


def _deflect_behind(m: Match, slot: int) -> bool:
    """A defender stretching near his own goal line sometimes turns the ball behind."""
    t = m.team_of(slot)
    own_x, _ = m.ball_rel(m.teams[t].direction)
    if own_x > m.params.behind_zone_m or m.rng.random() >= m.params.behind_share:
        return False
    m.events.add(
        "interception",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(slot),
        payload={"outcome": "lost"},
    )
    m.clear_plan(slot)
    behind = math.pi if m.teams[t].direction > 0 else 0.0
    wide = 1.0 if m.by > 34.0 else -1.0
    loose_ball(
        m,
        t,
        slot,
        m.rng.uniform(6.0, 10.0),
        behind + wide * (1.0 if behind == 0.0 else -1.0) * m.rng.uniform(0.3, 0.9),
        1.5,
    )
    return True


def _deflect_into_touch(m: Match, slot: int) -> bool:
    """An interception close to a touchline often goes out for a throw-in."""
    side = min(m.by, WIDTH - m.by)
    if side > 8.0 or m.rng.random() >= 0.3:
        return False
    m.events.add(
        "interception",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(slot),
        payload={"outcome": "lost"},
    )
    m.clear_plan(slot)
    out = -math.pi / 2 if m.by < 34.0 else math.pi / 2
    loose_ball(m, m.team_of(slot), slot, m.rng.uniform(6.0, 9.0), out + m.rng.uniform(-0.5, 0.5))
    return True


def _lost_aerial(m: Match, slot: int) -> bool:
    """A high ball arrives contested: aerial duel. Returns True if the defender won it."""
    o = 1 - m.team_of(slot)
    rival, gap = m.nearest_of_team(o, m.bodies.pos[slot])
    if rival < 0 or gap > 2.0:
        return False
    won = m.rng.random() < aerial_win(m.attr(slot, "aerial"), m.attr(rival, "aerial"))
    m.events.add(
        "duel",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(slot),
        payload={
            "kind": "aerial",
            "outcome": "won" if won else "lost",
            "opponent_id": m.pid(rival),
        },
    )
    if won:
        return False
    f = m.flight
    finish_pass(m, f, "incomplete", (m.bx, m.by), None)
    m.events.add(
        "clearance",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(rival),
        payload={"outcome": "success"},
    )
    away = 0.0 if m.teams[o].direction > 0 else math.pi
    own_x, _ = m.ball_rel(m.teams[o].direction)
    if own_x < m.params.behind_zone_m and m.rng.random() < m.params.behind_share:
        away = math.pi - away  # headed behind for a corner
    loose_ball(m, o, rival, m.rng.uniform(7.0, 13.0), away + m.rng.uniform(-1.0, 1.0), 4.0)
    return True


def _header_chance(m: Match, f: Flight, slot: int, z: float) -> bool:
    """A cross met in the air inside the box is headed at goal straight away."""
    if f.payload["pass_type"] not in ("cross", "corner") or z < 0.6:
        return False
    rx, ry = to_rel(m.bx, m.by, m.teams[m.team_of(slot)].direction)
    if not in_box(rx, ry) or m.rng.random() > 0.75 or not m.steer.can_shoot(m, slot):
        return False
    gx = LENGTH if m.teams[m.team_of(slot)].direction > 0 else 0.0
    launch_shot(m, slot, Action("shot", (gx, 34.0)), header=True, assist="cross")
    return True


def _exit(
    m: Match, f: Flight, prev: tuple[float, float, float], now: tuple[float, float, float]
) -> None:
    """The ball left the field: goal, throw-in, goal kick or corner."""
    (px, py, pz), (x, y, z) = prev, now
    goal_line = x < 0.0 or x > LENGTH
    if goal_line:
        line_x = 0.0 if x < 0.0 else LENGTH
        frac = (line_x - px) / (x - px) if x != px else 1.0
    else:
        line_y = 0.0 if y < 0.0 else WIDTH
        frac = (line_y - py) / (y - py) if y != py else 1.0
    cx, cy, cz = px + frac * (x - px), py + frac * (y - py), pz + frac * (z - pz)
    attacking_this_end = (cx > 52.5) == (m.teams[f.team].direction > 0)
    if f.kind == "shot" and goal_line and attacking_this_end:
        gk = m.gk_slot[1 - f.team]
        if f.planned == "goal" or (in_goal_mouth(cy, cz) and not m.bodies.active[gk]):
            ref = finish_shot(m, f, "goal", (cx, cy, cz))
            restarts.goal_scored(m, f, (cx, cy), ref)
            return
        if in_goal_mouth(cy, cz):  # heading in although no goal was drawn: kept out on the line
            m.bx, m.by, m.bz = cx, cy, cz
            finish_shot(m, f, "saved", (cx, cy, cz))
            onball.gain_control(m, gk, how="save")
            return
        near_post = abs(abs(cy - 34.0) - GOAL_HALF_WIDTH) < 0.35 or abs(cz - GOAL_HEIGHT) < 0.2
        if f.planned == "post" or (near_post and abs(cy - 34.0) < GOAL_HALF_WIDTH + 0.35):
            finish_shot(m, f, "post", (cx, cy, cz))
            m.bx, m.by, m.bz = cx - 0.3 * math.copysign(1.0, x - 52.5), cy, min(cz, 2.0)
            back = math.pi if x > 52.5 else 0.0
            loose_ball(
                m, f.team, f.actor, m.rng.uniform(5.0, 9.0), back + m.rng.uniform(-0.9, 0.9), 1.0
            )
            return
        finish_shot(m, f, "off_target", (cx, cy, cz))
    elif f.kind == "pass":
        finish_pass(m, f, "out", (cx, cy), None)
    m.bx, m.by, m.bz = min(max(cx, -0.5), LENGTH + 0.5), min(max(cy, -0.5), WIDTH + 0.5), 0.11
    last = m.last_touch_team
    if not goal_line:
        restarts.stop_play(
            m,
            "ball_out",
            "throw_in",
            1 - last,
            (cx, min(max(cy, 0.0), WIDTH)),
            m.params.delay_throw_in,
        )
        return
    # which team defends this goal line?
    defender = 0 if (m.teams[0].direction > 0) == (cx < 52.5) else 1
    if last == defender:
        corner_y = 0.0 if cy < 34.0 else WIDTH
        restarts.stop_play(
            m,
            "ball_out",
            "corner",
            1 - defender,
            (0.0 if cx < 52.5 else LENGTH, corner_y),
            m.params.delay_corner,
        )
    else:
        gx = 5.5 if cx < 52.5 else LENGTH - 5.5
        restarts.stop_play(
            m,
            "ball_out",
            "goal_kick",
            defender,
            (gx, 34.0 + (6.0 if cy > 34 else -6.0)),
            m.params.delay_goal_kick,
        )


__all__ = ["advance", "loc"]
