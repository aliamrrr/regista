"""Ball flights: passes, crosses, shots, clearances and loose balls (§2 ball state machine).

A flight's path is precomputed at launch with the same drag/bounce model every time, so
interception and save points are chosen on the path the ball will really follow. Outcomes are
sampled from the true models (``engine/models.py``); a scenario may force them, but the ball
still travels the same physics.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from regista_sim.engine.decisions import Action, pass_features, shot_features
from regista_sim.engine.events import EventRef, loc
from regista_sim.engine.models import expected_goals, goal_probability, pass_completion
from regista_sim.engine.state import BallState, Flight, Plan
from regista_sim.pitch import BALL_RADIUS, GOAL_HALF_WIDTH, GOAL_HEIGHT, LENGTH, WIDTH

if TYPE_CHECKING:
    from regista_sim.engine.match import Match

MAX_PATH_TICKS = 90


def ball_path(
    m: Match, x: float, y: float, z: float, vx: float, vy: float, vz: float, lofted: bool
) -> list[tuple[float, float, float]]:
    """Positions after each tick until the ball stops or leaves the pitch (+1 point outside)."""
    p = m.params
    dt = p.tick_ms / 1000.0
    path = []
    airborne = lofted or z > BALL_RADIUS + 0.05
    for _ in range(MAX_PATH_TICKS):
        speed = math.hypot(vx, vy)
        if airborne:
            dec = p.air_decel + p.air_drag * speed * speed
        else:
            dec = p.ground_decel + p.ground_drag * speed * speed
        new_speed = max(speed - dec * dt, 0.0)
        if speed > 1e-9:
            vx, vy = vx * new_speed / speed, vy * new_speed / speed
        x += vx * dt
        y += vy * dt
        if airborne:
            vz -= p.gravity * dt
            z += vz * dt
            if z <= BALL_RADIUS:
                z = BALL_RADIUS
                if abs(vz) > 1.6:
                    vz = -0.45 * vz
                    vx, vy = 0.8 * vx, 0.8 * vy
                else:
                    vz, airborne = 0.0, False
        path.append((x, y, z))
        if not (0.0 <= x <= LENGTH and 0.0 <= y <= WIDTH):
            break
        if not airborne and new_speed < 0.15:
            break
    return path


def ground_speed_for(m: Match, distance: float, arrive_speed: float) -> float:
    """Launch speed for a ground pass that still rolls at ``arrive_speed`` after ``distance``."""
    p = m.params
    v, s = arrive_speed, 0.0
    dt = p.tick_ms / 1000.0
    while s < distance:  # integrate the deceleration backwards from the receiver
        v += (p.ground_decel + p.ground_drag * v * v) * dt
        s += v * dt
    return v


def _out_chance(point: tuple[float, float]) -> float:
    """How often a misplaced pass aimed here ends up out of play rather than cut out."""
    side = min(point[1], WIDTH - point[1])
    if side < 15.0:
        return 0.3 + 0.45 * (1.0 - side / 15.0)
    return 0.35 if min(point[0], LENGTH - point[0]) < 6.0 else 0.0


def _foot(m: Match, slot: int) -> str:
    foot = m.foot(slot)
    if foot == "both":
        foot = "right" if m.rng.random() < 0.5 else "left"
    return f"{foot}_foot"


def _start_flight(m: Match, f: Flight, path: list[tuple[float, float, float]]) -> None:
    m.flight = f
    m.path = path
    m.path_k = 0
    m.ball_state = BallState.IN_FLIGHT
    m.attacking_team = f.team
    m.carrier = -1
    m.last_touch_team = f.team


def _interceptor(
    m: Match, team: int, path: list[tuple[float, float, float]], until: int
) -> tuple[int, int] | None:
    """Earliest (slot, path index) an opponent can physically reach before the ball."""
    o = 1 - team
    slots = [j for j in range(11 * o, 11 * o + 11) if m.bodies.active[j] and j not in m.plans]
    if not slots or until < 2:
        return None
    pts = np.array([pt[:2] for pt in path[:until]])
    zs = np.array([pt[2] for pt in path[:until]])
    tau = (np.arange(1, len(pts) + 1) * m.params.tick_ms / 1000.0)[:, None]
    pos = m.bodies.pos[slots]
    reach = np.maximum(0.0, 0.72 * m.bodies.vmax[slots][None, :] * (tau - 0.25)) + 1.0
    diff = pts[:, None, :] - pos[None, :, :]
    gap = np.sqrt((diff * diff).sum(axis=2))
    ok = (gap <= reach) & (zs[:, None] < 2.2) & (tau > 0.25)
    rows = np.flatnonzero(ok.any(axis=1))
    if not len(rows):
        return None
    k = int(rows[0])
    j = int(np.argmax(np.where(ok[k], reach[k] - gap[k], -1e9)))
    return slots[j], k


def launch_pass(m: Match, c: int, a: Action) -> None:
    """Strike a pass or cross from carrier ``c``; resolution happens in ``advance``."""
    t = m.team_of(c)
    feats = a.features or pass_features(m, c, a.target, a.height)
    p_true = pass_completion(feats)
    if a.pass_type in ("cross", "corner"):
        p_true *= m.params.cross_difficulty
    elif a.pass_type == "through_ball":
        p_true *= m.params.through_ball_difficulty
    if a.extra.get("offside"):
        natural = "offside"
    else:
        natural = "complete" if m.rng.random() < p_true else "incomplete"
    if natural == "incomplete" and not a.outcome and m.rng.random() < _out_chance(a.target):
        natural = "out"  # overhit or deflected over a line
    planned = a.outcome or m.steer.pass_result(m, a, natural)
    sx, sy = m.bx, m.by
    dx, dy = a.target[0] - sx, a.target[1] - sy
    dist = max(math.hypot(dx, dy), 0.5)
    ux, uy = dx / dist, dy / dist
    lofted = a.height in ("low", "high")
    tempo = m.dials[t]["tempo"]
    if lofted:
        hang = 0.7 + dist / (22.0 if a.height == "high" else 34.0)
        v_h = a.speed if a.speed else dist / hang + 1.2
        vz = 0.5 * m.params.gravity * hang * (0.95 if a.height == "high" else 0.6)
        vx, vy = ux * v_h, uy * v_h
    else:
        arrive = 4.5 if a.tag else max(4.0, 6.0 + 2.6 * tempo + float(m.rng.normal(0.0, 0.8)))
        v0 = a.speed if a.speed else ground_speed_for(m, dist, arrive)
        vx, vy, vz = ux * v0, uy * v0, 0.0
    if planned == "out":
        vx, vy = vx * 1.45, vy * 1.45
    path = ball_path(m, sx, sy, BALL_RADIUS, vx, vy, vz, lofted)
    arrival = next(
        (k for k, pt in enumerate(path) if math.hypot(pt[0] - sx, pt[1] - sy) >= dist),
        len(path) - 1,
    )
    f = Flight(
        kind="pass",
        team=t,
        actor=c,
        start=(sx, sy),
        start_tick=m.tick,
        start_clock_ms=m.clock.clock_ms,
        target=a.target,
        vx=vx,
        vy=vy,
        vz=vz,
        lofted=lofted,
        planned=planned,
        receiver=a.receiver,
    )
    if planned in ("complete", "offside") and a.receiver >= 0:
        f.taker = a.receiver
        f.deadline_k = arrival + 12 if not a.tag else 10_000  # scripted: only he may take it
        m.set_plan(
            a.receiver, Plan(a.target, 1.0, until_tick=m.tick + arrival + 25, source="receive")
        )
    elif planned == "incomplete":
        hit = _interceptor(m, t, path, max(int(arrival * 0.97), 1))
        if hit is not None:
            f.taker, k = hit
            f.stop_at = path[k][:2]
            f.deadline_k = k + 6
            m.set_plan(
                f.taker, Plan(f.stop_at, 1.0, until_tick=m.tick + k + 15, source="intercept")
            )
        elif a.receiver >= 0:  # nobody can cut it out: a loose ball between receiver and marker
            m.set_plan(
                a.receiver, Plan(a.target, 1.0, until_tick=m.tick + arrival + 25, source="receive")
            )
    f.payload = {
        "end_location": None,
        "recipient_id": m.pid(a.receiver) if a.receiver >= 0 else None,
        "outcome": None,
        "height": a.height,
        "pass_type": a.pass_type,
        "body_part": "hands" if a.pass_type == "throw_in" else _foot(m, c),
    }
    f.event_meta = m.event_context(c)
    f.truth = {
        "p_complete": round(p_true, 4),
        "natural": natural,
        "planned": planned,
        "tag": a.tag,
        "arrive_k": arrival,
        "receiver_cap": a.extra.get("receiver_cap"),
    }
    m.note_release(c, "pass", a)
    _start_flight(m, f, path)


def launch_shot(
    m: Match,
    c: int,
    a: Action,
    *,
    shot_type: str = "open_play",
    header: bool = False,
    assist: str = "none",
) -> None:
    """Strike a shot from ``c``; its outcome is planned now and played out by the path."""
    t = m.team_of(c)
    d = m.teams[t].direction
    feats = a.features or shot_features(
        m, c, header=header, assist=assist, penalty=shot_type == "penalty"
    )
    xg = expected_goals(feats)
    gk = m.gk_slot[1 - t]
    skill = m.attr(c, "aerial" if header else "finishing")
    p_goal = goal_probability(xg, skill, m.attr(gk, "goalkeeping"))
    r = m.rng.random()
    if r < p_goal:
        natural = "goal"
    elif feats.defenders_in_cone and m.rng.random() < 1.0 - math.exp(
        -0.32 * feats.defenders_in_cone
    ):
        natural = "blocked"
    else:
        natural = (
            "saved"
            if m.rng.random() < 0.31 + 0.8 * xg
            else ("post" if m.rng.random() < 0.05 else "off_target")
        )
    planned = a.outcome or m.steer.shot_result(m, a, natural)
    goal_x = LENGTH if d > 0 else 0.0
    gk_y = float(m.bodies.pos[gk, 1]) if m.bodies.active[gk] else 34.0
    if planned == "goal":
        side = 1.0 if gk_y < 34.0 else -1.0
        ty = a.target[1] if a.extra.get("aim_y") else 34.0 + side * m.rng.uniform(1.4, 3.2)
        tz = a.z_target if a.z_target is not None else m.rng.uniform(0.15, 2.0)
    elif planned == "saved":
        ty = min(max(gk_y + m.rng.uniform(-1.4, 1.4), 34.0 - 3.3), 34.0 + 3.3)
        tz = m.rng.uniform(0.2, 1.7)
    elif planned == "post":
        ty = 34.0 + (GOAL_HALF_WIDTH + 0.05) * (1 if m.rng.random() < 0.5 else -1)
        tz = m.rng.uniform(0.3, 2.0)
    else:
        wide = m.rng.random() < 0.7
        ty = 34.0 + (
            m.rng.uniform(4.2, 9.0) * (1 if m.rng.random() < 0.5 else -1)
            if wide
            else m.rng.uniform(-3.0, 3.0)
        )
        tz = m.rng.uniform(0.2, 1.5) if wide else m.rng.uniform(2.7, 4.0)
    if a.extra.get("aim_y") and planned != "goal":
        ty = a.target[1]
    if a.extra.get("aim_z") is not None:
        tz = a.extra["aim_z"]
    sx, sy = m.bx, m.by
    sz = 1.8 if header else BALL_RADIUS
    dist = math.hypot(goal_x - sx, ty - sy)
    speed = a.speed or (
        float(np.clip(m.rng.normal(14.5, 1.8), 10.0, 19.0))
        if header
        else float(np.clip(m.rng.normal(26.5 + 0.08 * (skill - 70), 3.0), 18.0, 35.0))
    )
    hang = dist / speed
    vx, vy = (goal_x - sx) / dist * speed, (ty - sy) / dist * speed
    vz = (tz - sz) / hang + 0.5 * m.params.gravity * hang
    path = ball_path(m, sx, sy, sz, vx, vy, vz, True)
    for _ in range(4):  # drag slows the ball: nudge the loft until it crosses the line as planned
        crossing = _goal_line_crossing(path, goal_x)
        if crossing is None:
            break
        z_now = crossing[1]
        wanted = (
            tz
            if planned in ("goal", "saved", "post") or abs(ty - 34.0) > GOAL_HALF_WIDTH
            else max(tz, 2.9)
        )
        if abs(z_now - wanted) < 0.15 or (planned == "goal" and in_goal_mouth(crossing[0], z_now)):
            break
        vz += (wanted - z_now) / hang
        path = ball_path(m, sx, sy, sz, vx, vy, vz, True)
    f = Flight(
        kind="shot",
        team=t,
        actor=c,
        start=(sx, sy),
        start_tick=m.tick,
        start_clock_ms=m.clock.clock_ms,
        target=(goal_x, ty),
        vx=vx,
        vy=vy,
        vz=vz,
        lofted=True,
        planned=planned,
    )
    if planned == "saved" and m.bodies.active[gk]:
        f.taker = gk
        k = _closest_index(path, m.bodies.pos[gk])
        f.stop_at = path[k][:2]
        f.deadline_k = len(path)
        m.set_plan(gk, Plan(f.stop_at, 1.0, until_tick=m.tick + k + 10, source="intercept"))
    elif planned == "blocked":
        blocker = _blocker(m, t, path)
        if blocker is None:
            f.planned = planned = "off_target"
        else:
            f.taker, k = blocker
            f.stop_at = path[k][:2]
            f.deadline_k = k + 3
            m.set_plan(
                f.taker, Plan(f.stop_at, 1.0, until_tick=m.tick + k + 10, source="intercept")
            )
    f.payload = {
        "end_location": None,
        "outcome": None,
        "body_part": "head" if header else _foot(m, c),
        "shot_type": "header" if header else shot_type,
    }
    f.event_meta = m.event_context(c)
    if a.extra.get("credit_to"):  # scenario: the live feed first credits someone else
        f.event_meta["player"] = a.extra["credit_to"]
    f.truth = {
        "xg": round(xg, 4),
        "p_goal": round(p_goal, 4),
        "natural": natural,
        "planned": planned,
        "tag": a.tag,
        "features": {
            "distance": round(feats.distance, 2),
            "angle": round(feats.angle, 4),
            "header": feats.header,
            "assist": feats.assist,
            "defenders_in_cone": feats.defenders_in_cone,
            "penalty": feats.penalty,
        },
    }
    m.note_release(c, "shot", a)
    _start_flight(m, f, path)


def _goal_line_crossing(
    path: list[tuple[float, float, float]], goal_x: float
) -> tuple[float, float] | None:
    """(y, z) where the path crosses the goal line ``goal_x``, if it does."""
    prev = None
    for x, y, z in path:
        if (goal_x > 52.5 and x >= goal_x) or (goal_x < 52.5 and x <= goal_x):
            if prev is None:
                return y, z
            px, py, pz = prev
            frac = (goal_x - px) / (x - px) if x != px else 1.0
            return py + frac * (y - py), pz + frac * (z - pz)
        prev = (x, y, z)
    return None


def _closest_index(path: list[tuple[float, float, float]], point: np.ndarray) -> int:
    gaps = [math.hypot(px - point[0], py - point[1]) for px, py, _ in path]
    return int(np.argmin(gaps))


def _blocker(m: Match, team: int, path: list[tuple[float, float, float]]) -> tuple[int, int] | None:
    o = 1 - team
    best = None
    for j in range(11 * o, 11 * o + 11):
        if not m.bodies.active[j] or j == m.gk_slot[o]:
            continue
        k = _closest_index(path, m.bodies.pos[j])
        gap = math.hypot(path[k][0] - m.bodies.pos[j, 0], path[k][1] - m.bodies.pos[j, 1])
        if gap < 2.2 and k >= 1 and (best is None or k < best[1]):
            best = (j, k)
    return best


def launch_clearance(m: Match, c: int, a: Action) -> None:
    """Clear the ball long; it lands loose (``clearance`` is logged now)."""
    t = m.team_of(c)
    m.events.add(
        "clearance",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(c),
        payload={"outcome": "success"},
    )
    m.note_release(c, "clearance", a)
    sx, sy = m.bx, m.by
    dx, dy = a.target[0] - sx, a.target[1] - sy
    dist = max(math.hypot(dx, dy), 1.0)
    hang = 1.2 + dist / 20.0
    v_h = dist / hang + 1.0
    path = ball_path(
        m,
        sx,
        sy,
        BALL_RADIUS,
        dx / dist * v_h,
        dy / dist * v_h,
        0.5 * m.params.gravity * hang,
        True,
    )
    f = Flight(
        kind="clearance",
        team=t,
        actor=c,
        start=(sx, sy),
        start_tick=m.tick,
        start_clock_ms=m.clock.clock_ms,
        target=a.target,
        vx=dx / dist * v_h,
        vy=dy / dist * v_h,
        vz=0.5 * m.params.gravity * hang,
        lofted=True,
        planned="loose",
    )
    _start_flight(m, f, path)


def loose_ball(
    m: Match, team: int, actor: int, speed: float, angle: float, z_speed: float = 0.0
) -> None:
    """Knock the ball loose (after a tackle, a block, a parry or the post)."""
    vx, vy = speed * math.cos(angle), speed * math.sin(angle)
    path = ball_path(m, m.bx, m.by, max(m.bz, BALL_RADIUS), vx, vy, z_speed, z_speed > 0)
    f = Flight(
        kind="loose",
        team=team,
        actor=actor,
        start=(m.bx, m.by),
        start_tick=m.tick,
        start_clock_ms=m.clock.clock_ms,
        target=path[-1][:2],
        vx=vx,
        vy=vy,
        vz=z_speed,
        lofted=z_speed > 0,
        planned="loose",
    )
    _start_flight(m, f, path)


def finish_pass(
    m: Match, f: Flight, outcome: str, end: tuple[float, float], recipient: int | None
) -> None:
    """Log the pass once it is resolved (stamped with its launch time)."""
    payload = dict(f.payload)
    payload["end_location"] = loc(*end)
    payload["outcome"] = outcome
    if outcome == "complete" and recipient is not None and recipient >= 0:
        payload["recipient_id"] = m.pid(recipient)
    ref = m.events.add("pass", m.clock.period, f.start_clock_ms, **f.event_meta, payload=payload)
    m.truth_passes.append((ref, f.truth, outcome))
    m.steer.on_pass(m, ref, f, outcome)


def finish_shot(m: Match, f: Flight, outcome: str, end: tuple[float, float, float]) -> EventRef:
    """Log the shot once it is resolved."""
    payload = dict(f.payload)
    payload["end_location"] = {"x": round(end[0], 1), "y": round(end[1], 1), "z": round(end[2], 2)}
    payload["outcome"] = outcome
    ref = m.events.add("shot", m.clock.period, f.start_clock_ms, **f.event_meta, payload=payload)
    m.truth_shots.append((ref, f.truth, outcome))
    m.steer.on_shot(m, ref, f, outcome)
    return ref


def in_goal_mouth(y: float, z: float) -> bool:
    """True when the ball crosses the goal line under the bar and between the posts."""
    return abs(y - 34.0) < GOAL_HALF_WIDTH - BALL_RADIUS and z < GOAL_HEIGHT - BALL_RADIUS
