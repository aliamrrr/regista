"""One scripted beat: acquire the ball, build, then execute the steps with the engine's physics.

The runner only chooses actions, forces outcomes, vetoes challenges on its carriers and sets
movement plans. Players and the ball still move through the same integrator and flight model,
so tracking stays consistent.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from regista_sim.engine.decisions import CLOSE_BLOCK_M, CONE_MARGIN_M, Action
from regista_sim.engine.events import EventRef
from regista_sim.engine.state import BallState, Plan
from regista_sim.pitch import GOAL_HALF_WIDTH, LENGTH, to_abs, to_rel
from regista_sim.scenario.dsl import Beat

if TYPE_CHECKING:
    from regista_sim.engine.match import Match
    from regista_sim.scenario.director import Director

WAIT, ACQUIRE, BUILD, EXECUTE, DONE = "wait", "acquire", "build", "execute", "done"
_HOLD_TICKS = 3
TURNOVER_WINDOW_MS = 15_000  # how long before the key moment a turnover may start the move
SETUP_MS = 25_000  # before that window, the opponent is helped onto the ball
_CLEAR_M = CLOSE_BLOCK_M + 2.0  # a cleared cone also keeps defenders this far from the shooter


class BeatRunner:
    """State machine for one beat: wait → acquire → build → execute → done."""

    def __init__(self, director: Director, beat: Beat) -> None:
        self.director = director
        self.b = beat
        self.state = WAIT
        self.t_key = director.when(beat.at)
        self.t_start = self.t_key - int(beat.lead_s * 1000)
        self.k = 0
        self.wait_from = -1
        self.refs: dict[str, EventRef] = {}
        self.key_clock: tuple[int, int] | None = None
        self.started_runs: set[int] = set()
        self.failed = False
        self.hold_plans: dict[int, Plan] = {}
        self.cleared: list[int] = []  # defenders sent out of a shooter's cone
        self.clear_spot: tuple[float, float] | None = None  # that shooter's spot, until he shoots

    # ---- helpers ------------------------------------------------------------------------------
    def team(self, m: Match) -> int:
        """Index of the beat's team."""
        return self.director.team_index(m, self.b.team)

    def slot(self, m: Match, player: str) -> int:
        """Slot of a named player (must be on the pitch)."""
        slot = m.slot_of(player)
        if slot < 0:
            msg = f"beat {self.b.id}: {player} is not on the pitch"
            raise RuntimeError(msg)
        return slot

    def point(self, m: Match, rel: tuple[float, float]) -> tuple[float, float]:
        """Absolute point of a team-relative point of the beat's team."""
        return to_abs(rel[0], rel[1], m.teams[self.team(m)].direction)

    def busy(self) -> bool:
        """True while the beat controls its team's play."""
        return self.state in (BUILD, EXECUTE)

    def _exec_estimate_ms(self) -> int:
        """Rough duration of the steps, from their geometry (to schedule the key action)."""
        total, prev = 0.0, self.b.acquire.hub
        for step in self.b.steps:
            if step.at is not None and prev is not None:
                dist = math.dist(prev, step.at)
                speed = (
                    (step.speed_kmh or 50.0) / 3.6
                    if step.action == "pass"
                    else ((step.speed_kmh or 20.0) / 3.6)
                )
                total += dist / max(speed * (0.85 if step.action == "pass" else 0.8), 1.0) + 0.5
            prev = step.at or prev
        return int(total * 1000)

    # ---- per tick -------------------------------------------------------------------------------
    def tick(self, m: Match, now: int) -> None:
        """Advance the state machine."""
        t = self.team(m)
        if self.state == WAIT and now >= self.t_start:
            self.state = ACQUIRE
            for hold in self.b.holds:
                if hold.from_start and (slot := m.slot_of(hold.player)) >= 0 and slot != m.carrier:
                    plan = Plan(self.point(m, hold.at), hold.urgency, source="scenario")
                    m.plans[slot] = self.hold_plans[slot] = plan
        if self.state not in (WAIT, DONE) and now > self.t_key + 50_000:
            self.state = DONE  # give up rather than freeze the match; tests catch a missed beat
            self.failed = True
            self._release(m)
            return
        ours = m.ball_state == BallState.CONTROLLED and m.team_of(m.carrier) == t
        if self.state == ACQUIRE and self.b.acquire.mode == "possession" and ours:
            self.state = BUILD
            self._hold_players(m)
        if (
            self.state == BUILD
            and m.ball_state == BallState.CONTROLLED
            and m.team_of(m.carrier) != t
        ):
            self.state = ACQUIRE  # lost it before the move started: win it back
        if (
            self.state == ACQUIRE
            and self.b.acquire.mode == "turnover"
            and now >= self._fallback_ms()
            and m.ball_state == BallState.CONTROLLED
            and m.team_of(m.carrier) == t
        ):
            self._hold_players(m)  # no high regain came in time: start from the ball we have
            self._start_execute(m)
        if self.state in (BUILD, EXECUTE):
            self._follow(m)
        start = self.t_key - self._exec_estimate_ms() - 1500
        ready = self._holds_ready(m) or now >= start + 6000
        if self.state == BUILD and now >= start and ready and ours:
            self._start_execute(m)

    def window_start(self) -> int:
        """Turnover beats: when a regain may start the move."""
        return self.t_key - self._exec_estimate_ms() - TURNOVER_WINDOW_MS

    def _fallback_ms(self) -> int:
        """Turnover beats: past this, the move starts from whatever ball the team has."""
        return self.t_key - self._exec_estimate_ms() - 5000

    def setting_up_regain(self, m: Match) -> bool:
        """A turnover beat is arranging its regain (setup stage or window, before the fallback)."""
        now = self.director.now(m)
        return (
            self.state == ACQUIRE
            and self.b.acquire.mode == "turnover"
            and self.window_start() - SETUP_MS <= now < self._fallback_ms()
        )

    def in_window(self, m: Match) -> bool:
        """Turnover beats: the regain counts only shortly before the key moment, in the zone."""
        if self.director.now(m) < self.window_start():
            return False
        lo, hi = self.b.acquire.zone
        x, _ = m.ball_rel(m.teams[self.team(m)].direction)
        return lo <= x <= hi

    def wants_interception(self, m: Match, passer: int) -> bool:
        """Force this pass to be cut out so the beat team wins the ball.

        Before and during a turnover window it also works the other way: a ball the beat team
        wins too early, or outside the zone, goes back to the opponent, so the regain that starts
        the move is a real high turnover.
        """
        if self.state != ACQUIRE:
            return False
        ours = m.team_of(passer) == self.team(m)
        if self.b.acquire.mode == "possession":
            return not ours
        if ours:
            return self.setting_up_regain(m)
        return self.in_window(m)

    def on_control(self, m: Match, slot: int, how: str) -> None:
        """A player gained control: start, or advance, the scripted move."""
        t = self.team(m)
        if self.state == ACQUIRE and self.b.acquire.mode == "turnover" and m.team_of(slot) == t:
            if how in ("interception", "recovery", "tackle", "ball_recovery") and self.in_window(m):
                self._hold_players(m)
                self._start_execute(m)
            return
        if self.state != EXECUTE:
            return
        step = self.b.steps[self.k] if self.k < len(self.b.steps) else None
        if step is not None and step.action == "pass" and step.to and m.pid(slot) == step.to:
            self._advance(m)
            self._drop_plan(m, slot)
            nxt = self.b.steps[self.k] if self.k < len(self.b.steps) else None
            m.decision_tick = m.tick + (1 if nxt is not None and nxt.first_time else 4)

    # ---- actions ---------------------------------------------------------------------------------
    def choose(self, m: Match, carrier: int) -> Action | None:
        """The beat team's action while the beat runs."""
        if m.team_of(carrier) != self.team(m):
            return None
        if self.setting_up_regain(m):
            return self._go_long(m, carrier)
        if self.state == BUILD:
            return self._build_action(m, carrier)
        if self.state != EXECUTE or self.k >= len(self.b.steps):
            return None
        step = self.b.steps[self.k]
        if step.player != "carrier" and m.pid(carrier) != step.player:
            return self._hold(m, carrier)
        tag = f"{self.b.id}:{self.k}"
        if step.action == "carry":
            tx, ty = self.point(m, step.at)
            if math.hypot(m.bx - tx, m.by - ty) < 1.6:
                self._advance(m)
                return self.choose(m, carrier)
            speed = (step.speed_kmh or 22.0) / 3.6
            m.plans[carrier] = Plan((tx, ty), 1.0, speed_cap=speed, source="scenario")
            return Action("carry", (tx, ty), speed=speed, tag=tag)
        if step.action == "pass":
            return self._pass(m, carrier, step, tag)
        gy, gz = step.aim if step.aim is not None else (34.0, 0.5)
        gx, ty = self.point(m, (LENGTH, gy))
        self.key_clock = (m.clock.period, m.clock.clock_ms)
        self._advance(m)
        self.state = DONE
        self._release(m)
        extra: dict[str, Any] = {"aim_y": True, "aim_z": gz}
        if step.credit_to:
            extra["credit_to"] = step.credit_to
        return Action(
            "shot",
            (gx, ty),
            speed=(step.speed_kmh or 95.0) / 3.6,
            outcome=step.outcome or "goal",
            tag=tag,
            extra=extra,
        )

    def _pass(self, m: Match, carrier: int, step: Any, tag: str) -> Action:
        receiver = self.slot(m, step.to)
        tx, ty = self.point(m, step.at)
        dist = math.hypot(tx - m.bx, ty - m.by)
        speed = (step.speed_kmh or 0.0) / 3.6 or None
        flight = dist / ((speed or 15.0) * 0.82) + 0.2
        eta = math.hypot(*(m.bodies.pos[receiver] - (tx, ty))) / (
            0.82 * float(m.bodies.vmax[receiver])
        )
        if self.wait_from < 0:
            self.wait_from = m.tick
        late = eta > flight + 0.3 or not self._shadows_ready(m, carrier)
        if late and m.tick - self.wait_from < 50:
            if receiver not in m.plans:
                m.plans[receiver] = Plan((tx, ty), 1.0, source="scenario")
            return self._hold(m, carrier)
        self.wait_from = -1
        self._start_runs(m, launched=True)
        nxt = self.b.steps[self.k + 1] if self.k + 1 < len(self.b.steps) else None
        if nxt is not None and nxt.action == "shot" and nxt.clear_cone:
            self.clear_spot = (tx, ty)
            self._clear_cone(m, self.clear_spot)
        caps = [r.speed_kmh / 3.6 for r in self.b.runs if r.player == step.to and r.speed_kmh]
        return Action(
            "pass",
            (tx, ty),
            receiver=receiver,
            height=step.height,
            pass_type=step.pass_type,
            speed=speed,
            outcome=step.outcome or "complete",
            tag=tag,
            extra={"receiver_cap": caps[0] if caps else None},
        )

    def _hold(self, m: Match, carrier: int) -> Action:
        """Keep the ball a moment (a short shielding carry)."""
        m.decision_tick = m.tick + _HOLD_TICKS
        x, y = float(m.bodies.pos[carrier, 0]), float(m.bodies.pos[carrier, 1])
        return Action("carry", (x, y), speed=1.0)

    def _go_long(self, m: Match, carrier: int) -> Action:
        """Before its regain, a turnover beat's team goes long and loses the ball in the zone."""
        t = self.team(m)
        d = m.teams[t].direction
        mates = [
            s
            for s in range(11 * t, 11 * t + 11)
            if s != carrier and m.bodies.active[s] and s != m.gk_slot[t]
        ]
        front = max(mates, key=lambda s: (float(m.bodies.pos[s, 0]) * d, -s))
        _, ry = to_rel(float(m.bodies.pos[front, 0]), float(m.bodies.pos[front, 1]), d)
        lo, hi = self.b.acquire.zone
        return Action(
            "pass",
            self.point(m, (0.5 * (lo + hi), ry)),
            receiver=front,
            height="high",
            outcome="incomplete",
            tag=f"{self.b.id}:long",
        )

    def _build_action(self, m: Match, carrier: int) -> Action:
        """Keep possession and bring the ball towards the hub before the move starts."""
        hub = self.b.acquire.hub
        if hub is None:
            return self._hold(m, carrier)
        hx, hy = self.point(m, hub)
        if math.hypot(m.bx - hx, m.by - hy) < 22.0:
            return self._hold(m, carrier)
        t = self.team(m)
        mates = [
            s
            for s in range(11 * t, 11 * t + 11)
            if s != carrier and m.bodies.active[s] and s != m.gk_slot[t]
        ]
        best = min(
            mates, key=lambda s: (math.hypot(m.bodies.pos[s, 0] - hx, m.bodies.pos[s, 1] - hy), s)
        )
        target = (float(m.bodies.pos[best, 0]), float(m.bodies.pos[best, 1]))
        if math.hypot(target[0] - m.bx, target[1] - m.by) < 6.0:
            return self._hold(m, carrier)
        return Action("pass", target, receiver=best, outcome="complete", tag=f"{self.b.id}:build")

    # ---- plans -------------------------------------------------------------------------------
    def _start_execute(self, m: Match) -> None:
        self.state = EXECUTE
        self.k = 0
        self._start_runs(m)
        m.decision_tick = min(m.decision_tick, m.tick + 4)

    def _advance(self, m: Match) -> None:
        self.k += 1
        self._start_runs(m)
        for hold in self.b.holds:
            slot = m.slot_of(hold.player)
            released = hold.until_step < self.k and slot in self.hold_plans
            if released and m.plans.get(slot) is self.hold_plans.pop(slot):  # no run since
                del m.plans[slot]

    def _start_runs(self, m: Match, launched: bool = False) -> None:
        for i, run in enumerate(self.b.runs):
            if i in self.started_runs or run.start_step > self.k:
                continue
            if run.at_launch and not (launched or run.start_step < self.k):
                continue
            self.started_runs.add(i)
            slot = self.slot(m, run.player)
            cap = run.speed_kmh / 3.6 if run.speed_kmh else None
            m.plans[slot] = Plan(
                self.point(m, run.to), run.urgency, speed_cap=cap, source="scenario"
            )

    def _hold_point(self, m: Match, hold: Any) -> tuple[float, float]:
        if hold.near is None:
            return self.point(m, hold.at)
        anchor = m.slot_of(hold.near)
        ax, ay = to_rel(*m.bodies.pos[anchor], m.teams[self.team(m)].direction)
        return self.point(m, (ax + hold.at[0], ay + hold.at[1]))

    def _clear_cone(self, m: Match, spot: tuple[float, float]) -> None:
        """Defenders in the cone from ``spot`` to the posts (or goal-side right on it) step out.

        The cut-back drags them: each moves sideways to 1.5 m outside the cone at his depth
        (and, level with the shot, ``_CLEAR_M`` from the shooter).
        Called on every tick from the final ball to the shot, so late runners are caught too.
        """
        t = self.team(m)
        d = m.teams[t].direction
        sx, sy = to_rel(spot[0], spot[1], d)
        o = 1 - t
        for slot in range(11 * o, 11 * o + 11):
            if not m.bodies.active[slot] or slot == m.gk_slot[o]:
                continue
            px, py = to_rel(float(m.bodies.pos[slot, 0]), float(m.bodies.pos[slot, 1]), d)
            if px <= sx - 0.3 or px >= LENGTH:
                continue
            frac = (px - sx) / (LENGTH - sx)
            low = sy + frac * (34.0 - GOAL_HALF_WIDTH - sy) - CONE_MARGIN_M - 1.5
            high = sy + frac * (34.0 + GOAL_HALF_WIDTH - sy) + CONE_MARGIN_M + 1.5
            if px - sx < _CLEAR_M:  # level with the shot: keep clear of the shooter as well
                low, high = min(low, sy - _CLEAR_M), max(high, sy + _CLEAR_M)
            if not low < py < high:
                continue
            if slot in self.cleared and m.plans.get(slot) is not None:
                continue  # already on his way out
            ty = low if py - low < high - py else high
            m.plans[slot] = Plan(self.point(m, (px, ty)), 1.0, source="scenario")
            self.cleared.append(slot)

    def _shadows_ready(self, m: Match, passer: int) -> bool:
        """Holds that follow the passer are within 1 m of their spot (the pressure is on)."""
        name = m.pid(passer)
        for hold in self.b.holds:
            if hold.near != name or hold.until_step < self.k:
                continue
            slot = m.slot_of(hold.player)
            plan = self.hold_plans.get(slot)
            active = plan is not None and m.plans.get(slot) is plan
            if active and math.hypot(*(m.bodies.pos[slot] - plan.target)) > 1.0:
                return False
        return True

    def _holds_ready(self, m: Match) -> bool:
        """Every held player is within 2.5 m of his spot."""
        for slot, plan in self.hold_plans.items():
            if m.plans.get(slot) is plan and math.hypot(*(m.bodies.pos[slot] - plan.target)) > 2.5:
                return False
        return True

    def _hold_players(self, m: Match) -> None:
        for hold in self.b.holds:
            slot = m.slot_of(hold.player)
            if slot >= 0 and slot != m.carrier:
                plan = Plan(self._hold_point(m, hold), hold.urgency, source="scenario")
                m.plans[slot] = self.hold_plans[slot] = plan

    def _follow(self, m: Match) -> None:
        """Holds that follow a player keep their offset from him; a cleared cone stays clear."""
        if self.clear_spot is not None:
            self._clear_cone(m, self.clear_spot)
        for hold in self.b.holds:
            if hold.near is None or hold.until_step < self.k:
                continue
            slot = m.slot_of(hold.player)
            if slot in self.hold_plans and m.plans.get(slot) is self.hold_plans[slot]:
                plan = Plan(self._hold_point(m, hold), hold.urgency, source="scenario")
                m.plans[slot] = self.hold_plans[slot] = plan

    def _drop_plan(self, m: Match, slot: int) -> None:
        if slot >= 0 and slot in m.plans and m.plans[slot].source == "scenario":
            del m.plans[slot]

    def _release(self, m: Match) -> None:
        """Hand every scripted player back to the engine (runners keep running briefly)."""
        names = {r.player for r in self.b.runs} | {h.player for h in self.b.holds}
        names |= {s.player for s in self.b.steps if s.player != "carrier"} | {
            s.to for s in self.b.steps if s.to
        }
        slots = [m.slot_of(name) for name in names] + self.cleared
        self.cleared = []
        self.clear_spot = None
        for slot in slots:
            if slot >= 0 and slot in m.plans and m.plans[slot].source == "scenario":
                plan = m.plans[slot]
                m.plans[slot] = Plan(
                    plan.target, plan.urgency, plan.speed_cap, until_tick=m.tick + 12, source="run"
                )

    def pass_resolved(self, m: Match, tag: str, outcome: str) -> None:
        """A scripted pass that did not arrive sends the beat back to winning the ball."""
        if self.state == EXECUTE and outcome != "complete" and not tag.endswith(":build"):
            self.state = ACQUIRE
            self.k = 0
            self.started_runs.clear()
            self._release(m)

    def record(self, m: Match) -> dict[str, Any]:
        """Ground-truth record of this beat."""
        ids = {name: m.events.ids[ref.index] for name, ref in self.refs.items()}
        out: dict[str, Any] = {
            "id": self.b.id,
            "kind": self.b.kind,
            "team": self.b.team,
            "minute": self.b.minute,
            "state": self.state,
            "failed": self.failed,
            "players": sorted(
                {s.player for s in self.b.steps if s.player != "carrier"}
                | {s.to for s in self.b.steps if s.to}
            ),
            "event_ids": ids,
            "targets": self.b.targets,
        }
        if self.key_clock is not None:
            out["key_period"], out["key_clock_ms"] = self.key_clock
        return out


__all__ = ["BeatRunner", "to_rel"]
