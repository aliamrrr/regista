"""The ball carrier: control, decisions, carries, take-ons, challenges, fouls and pressure."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from regista_sim.engine import restarts
from regista_sim.engine.decisions import Action, choose_action, time_on_ball_ticks
from regista_sim.engine.events import loc
from regista_sim.engine.flight import launch_clearance, launch_pass, launch_shot, loose_ball
from regista_sim.engine.models import card_for_foul, foul_probability, tackle_success
from regista_sim.engine.state import BallState, Plan
from regista_sim.pitch import PENALTY_SPOT, in_box, to_abs, to_rel

if TYPE_CHECKING:
    from regista_sim.engine.match import Match


@dataclass
class Spell:
    """One player's time on the ball (a ``carry`` is logged if he moved it ≥ 3 m)."""

    slot: int
    start_tick: int
    start_clock_ms: int
    x: float
    y: float


def gain_control(m: Match, slot: int, *, how: str, pass_type: str | None = None) -> None:
    """``slot`` now controls the ball (reception, interception, recovery, save, restart)."""
    close_all_pressure(m)
    t = m.team_of(slot)
    m.ball_state = BallState.CONTROLLED
    m.carrier = slot
    m.flight = None
    m.path = []
    m.set_possession(t)
    m.attacking_team = t
    m.last_touch_team = t
    m.clear_plan(slot)
    m.cancel_engine_plans(1 - t)
    m.spell = Spell(slot, m.tick, m.clock.clock_ms, m.bx, m.by)
    m.received = (slot, pass_type or how, m.tick)
    m.ball_in_hands = how == "save"
    control = 2 if how == "reception" else 4
    if slot == m.gk_slot[t]:
        control += int(m.rng.integers(15, 40))
    pressure = m.nearest_of_team(1 - t, m.bodies.pos[slot])[1]
    m.decision_tick = m.tick + control + time_on_ball_ticks(m, slot, pressure)
    m.steer.on_control(m, slot, how)


def end_spell(m: Match) -> None:
    """Close the carrier's spell, logging a carry when the ball moved at least 3 m."""
    s = m.spell
    m.spell = None
    if s is None:
        return
    if math.hypot(m.bx - s.x, m.by - s.y) >= 3.0 and m.tick - s.start_tick >= 5:
        m.events.add(
            "carry",
            m.clock.period,
            s.start_clock_ms + m.params.tick_ms,
            **m.event_args(s.slot, at=(s.x, s.y)),
            payload={"end_location": loc(m.bx, m.by)},
        )


def controlled_step(m: Match) -> None:
    """Run challenges, then the carrier's decision when his timer fires."""
    c = m.carrier
    if challenge(m, c) or touchline_squeeze(m, c):
        return
    m.update_runs()
    if m.tick < m.decision_tick:
        return
    action = m.steer.choose(m, c) or choose_action(m, c)
    execute(m, c, action)


def execute(m: Match, c: int, a: Action) -> None:
    """Carry out ``a`` for carrier ``c``."""
    if a.kind in ("pass", "cross"):
        launch_pass(m, c, a)
    elif a.kind == "shot":
        launch_shot(
            m,
            c,
            a,
            shot_type=a.extra.get("shot_type", "open_play"),
            header=a.extra.get("header", False),
            assist=m.recent_assist(c),
        )
    elif a.kind == "clearance":
        launch_clearance(m, c, a)
    elif a.kind == "carry":
        vmax = float(m.bodies.vmax[c])
        cap = a.speed or 0.72 * vmax
        m.set_plan(c, Plan(a.target, 0.7, speed_cap=cap, until_tick=m.tick + 30, source="carry"))
        dist = math.hypot(a.target[0] - m.bx, a.target[1] - m.by)
        m.decision_tick = m.tick + min(max(int(dist / (0.75 * cap) * 10), 4), 22)
    elif a.kind == "dribble":
        take_on(m, c, a)


def take_on(m: Match, c: int, a: Action) -> None:
    """A take-on against ``a.opponent``."""
    j = a.opponent
    won = (a.outcome == "complete") if a.outcome else m.rng.random() < a.p_success
    m.events.add(
        "dribble",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(c),
        payload={"opponent_id": m.pid(j), "outcome": "complete" if won else "incomplete"},
    )
    if won:
        m.stunned_until[j] = m.tick + 12
        m.set_plan(c, Plan(a.target, 0.85, until_tick=m.tick + 15, source="carry"))
        m.decision_tick = m.tick + 8
        return
    if m.rng.random() < 0.12:
        handle_foul(m, j, c)
        return
    end_spell(m)
    m.events.add(
        "tackle",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(j, at=(m.bx, m.by), possession_change=True),
        payload={"outcome": "won", "opponent_id": m.pid(c)},
    )
    gain_control(m, j, how="tackle")


def challenge(m: Match, c: int) -> bool:
    """A nearby defender may challenge the carrier: tackle won/lost or a foul."""
    p = m.params
    if m.spell is None or m.tick - m.spell.start_tick < 4:
        return False
    forced = m.steer.forced_tackle(m, c)
    if forced >= 0:  # a scenario regain: a clean tackle by a defender already on the ball
        end_spell(m)
        m.events.add(
            "tackle",
            m.clock.period,
            m.clock.clock_ms,
            **m.event_args(forced, at=(m.bx, m.by), possession_change=True),
            payload={"outcome": "won", "opponent_id": m.pid(c)},
        )
        gain_control(m, forced, how="tackle")
        return True
    t = m.team_of(c)
    j, gap = m.nearest_of_team(1 - t, m.bodies.pos[c])
    if j < 0 or gap > p.challenge_radius_m or m.stunned_until[j] > m.tick:
        return False
    pressing = m.dials[1 - t]["pressing_intensity"]
    own_x, _ = m.ball_rel(m.teams[1 - t].direction)
    boost = 1.0 + p.own_third_boost * max(0.0, (35.0 - own_x) / 35.0)
    if m.rng.random() >= p.challenge_rate * p.tick_ms / 1000.0 * (0.6 + 0.8 * pressing) * boost:
        return False
    if not m.steer.allow_challenge(m, c, j):
        return False
    tired = 1.0 - float(m.bodies.energy[j])
    careful = p.box_foul_factor if in_box(*m.ball_rel(m.teams[t].direction)) else 1.0
    if m.rng.random() < careful * p.foul_scale * foul_probability(
        m.attr(j, "tackling"), pressing, tired
    ):
        return handle_foul(m, j, c)
    near_goal = max(0.0, (35.0 - own_x) / 35.0)
    won = m.rng.random() < tackle_success(
        m.attr(j, "tackling") + p.box_tackle_bonus * near_goal,
        m.attr(c, "dribbling"),
        m.attr(c, "composure"),
    )
    if won:
        end_spell(m)
        m.events.add(
            "tackle",
            m.clock.period,
            m.clock.clock_ms,
            **m.event_args(j, at=(m.bx, m.by), possession_change=True),
            payload={"outcome": "won", "opponent_id": m.pid(c)},
        )
        if m.rng.random() < p.loose_after_tackle:
            loose_ball(m, 1 - t, j, m.rng.uniform(4.0, 9.0), _knock_angle(m))
        else:
            gain_control(m, j, how="tackle")
        return True
    m.events.add(
        "tackle",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(j, at=(m.bx, m.by)),
        payload={"outcome": "lost", "opponent_id": m.pid(c)},
    )
    m.stunned_until[j] = m.tick + 10
    return False


def _knock_angle(m: Match) -> float:
    """Direction of a ball knocked loose: towards the nearest touchline when close to it."""
    if m.by < 15.0 and m.rng.random() < 0.55:
        return -math.pi / 2 + m.rng.uniform(-0.6, 0.6)
    if m.by > 53.0 and m.rng.random() < 0.55:
        return math.pi / 2 + m.rng.uniform(-0.6, 0.6)
    return m.rng.uniform(-math.pi, math.pi)


def touchline_squeeze(m: Match, c: int) -> bool:
    """A carrier hemmed in on the touchline loses the ball out of play (a lost ground duel)."""
    side = min(m.by, 68.0 - m.by)
    if side > 4.0 or m.spell is None or m.tick - m.spell.start_tick < 3:
        return False
    j, gap = m.nearest_of_team(1 - m.team_of(c), m.bodies.pos[c])
    rate = m.params.squeeze_rate * m.params.tick_ms / 1000.0
    if gap > 2.2 or m.rng.random() >= rate or not m.steer.allow_challenge(m, c, j):
        return False
    m.events.add(
        "duel",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(c),
        payload={"kind": "ground", "outcome": "lost", "opponent_id": m.pid(j)},
    )
    line_y = 0.0 if m.by < 34.0 else 68.0
    m.last_touch_team = m.team_of(c)
    restarts.stop_play(
        m, "ball_out", "throw_in", 1 - m.team_of(c), (m.bx, line_y), m.params.delay_throw_in
    )
    return True


def handle_foul(m: Match, fouler: int, victim: int) -> bool:
    """Log a foul with its card; stop play unless advantage is played. True if play stopped."""
    vt = m.team_of(victim)
    card = m.steer.card_result(m, fouler, card_for_foul(m.rng))
    rx, ry = to_rel(m.bx, m.by, m.teams[vt].direction)
    advantage = rx > 55.0 and card != "red" and not in_box(rx, ry) and m.rng.random() < 0.28
    m.events.add(
        "foul",
        m.clock.period,
        m.clock.clock_ms,
        **m.event_args(fouler, at=(m.bx, m.by)),
        payload={"victim_id": m.pid(victim), "card": card, "advantage": advantage},
    )
    m.apply_card(fouler, card)
    if advantage:
        return False
    if in_box(rx, ry):
        spot = to_abs(105.0 - PENALTY_SPOT, 34.0, m.teams[vt].direction)
        restarts.stop_play(m, "foul", "penalty", vt, spot, m.params.delay_foul)
    else:
        restarts.stop_play(m, "foul", "free_kick", vt, (m.bx, m.by), m.params.delay_foul)
    if m.rng.random() < 0.06 and m.restart is not None:
        extra = round(m.rng.uniform(30.0, 80.0) * 1000 / m.params.tick_ms)
        extra = m.steer.restart_ticks(m, "treatment", extra, 0)
        if extra <= 0:
            return True
        m.restart.ready_tick += extra
        m.events.add(
            "stoppage",
            m.clock.period,
            m.clock.clock_ms,
            team=m.teams[vt].code,
            location=loc(m.bx, m.by),
            payload={"reason": "treatment", "restart_type": m.restart.kind},
        )
    return True


def track_pressure(m: Match) -> None:
    """Open a pressure when an opponent closes within 3 m; log it when he drops off."""
    c = m.carrier
    o = 1 - m.team_of(c)
    cx, cy = m.bodies.pos[c]
    for j in range(11 * o, 11 * o + 11):
        if not m.bodies.active[j]:
            continue
        gap = math.hypot(m.bodies.pos[j, 0] - cx, m.bodies.pos[j, 1] - cy)
        if gap < 2.2 and j not in m.pressure:
            m.pressure[j] = (
                m.clock.clock_ms,
                c,
                (float(m.bodies.pos[j, 0]), float(m.bodies.pos[j, 1])),
                m.possession_id(),
                m.pid(j),
                m.pid(c),
            )
        elif j in m.pressure and (gap > 4.0 or m.pressure[j][1] != c):
            close_pressure(m, j)


def close_pressure(m: Match, j: int) -> None:
    """Log the pressure applied by ``j`` if it lasted at least 0.3 s."""
    start, _, (x, y), possession, presser, target = m.pressure.pop(j)
    duration = m.clock.clock_ms - start
    if duration >= 900:
        m.events.add(
            "pressure",
            m.clock.period,
            start,
            team=m.teams[m.team_of(j)].code,
            player=presser,
            location=loc(x, y),
            possession=possession,
            payload={"target_player_id": target, "duration_ms": int(duration)},
        )


def close_all_pressure(m: Match) -> None:
    """Close every open pressure (the ball changed hands or went dead)."""
    for j in list(m.pressure):
        close_pressure(m, j)
