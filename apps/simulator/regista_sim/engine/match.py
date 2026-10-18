"""The 10 Hz match engine: setup, the tick loop and shared helpers (§2)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from regista_sim.careers import vmax_kmh
from regista_sim.engine import onball, resolve, restarts
from regista_sim.engine.clock import MatchClock, match_minute
from regista_sim.engine.events import EventLog, loc
from regista_sim.engine.movement import compute_targets, integrate, update_noise
from regista_sim.engine.params import EngineParams
from regista_sim.engine.recorder import Recorder
from regista_sim.engine.state import BallState, Bodies, Flight, Plan, Restart, TeamState
from regista_sim.engine.steering import Steering
from regista_sim.formations import ROLES, role_kind
from regista_sim.models import League
from regista_sim.pitch import LENGTH, WIDTH, to_abs, to_rel
from regista_sim.rng import stream
from regista_sim.squads import ATTRIBUTES

BALL_IN_M = 0.05  # a ball at a carrier's feet stays at least this far inside the lines
_DIALS = ("pressing_intensity", "defensive_line", "tempo", "directness", "width")


@dataclass
class MatchSetup:
    """Everything that defines a match before kick-off."""

    match_id: str
    home: str
    away: str
    seed: int
    kickoff: datetime
    added_time_min: tuple[int, int] | None = None
    half_time_break_ms: int = 900_000
    home_attacks_right_first: bool = True
    venue: str | None = None
    referee: dict[str, str] | None = None
    weather: dict[str, Any] | None = None
    matchweek: int | None = None
    period_minutes: int = 45  # shorter periods make quick test matches


class Match:
    """One simulated match. ``run()`` plays it; the result lives on the instance."""

    def __init__(
        self,
        league: League,
        setup: MatchSetup,
        steer: Steering | None = None,
        params: EngineParams | None = None,
    ) -> None:
        self.league = league
        self.setup = setup
        self.params = params or EngineParams()
        self.steer = steer or Steering()
        self.rng = stream(setup.seed, "match", setup.match_id, "play")
        self.rng_move = stream(setup.seed, "match", setup.match_id, "movement")
        players = league.players_by_id()
        self.teams = [
            self._team(i, league.club(code), players)
            for i, code in enumerate((setup.home, setup.away))
        ]
        self.bodies = Bodies()
        self.role_depth = np.zeros(22)
        self.role_y = np.zeros(22)
        self.role_kind = [""] * 22
        self.work_rate = np.ones(22)
        self.gk_slot = [0, 11]
        self.attrs: dict[str, list[int]] = {name: [0] * 22 for name in ATTRIBUTES}
        for slot in range(22):
            self._load_slot(slot)
        added = setup.added_time_min or (int(self.rng.integers(1, 5)), int(self.rng.integers(2, 8)))
        self.added_time = added
        self.clock = MatchClock(setup.kickoff, setup.half_time_break_ms)
        self.events = EventLog(setup.match_id)
        self.recorder = Recorder()
        self.bx, self.by, self.bz = 52.5, 34.0, 0.11
        self.ball_state = BallState.DEAD
        self.carrier = -1
        self.flight: Flight | None = None
        self.path: list[tuple[float, float, float]] = []
        self.path_k = 0
        self.restart: Restart | None = None
        self.plans: dict[int, Plan] = {}
        self.pressers: list[int] = []
        self.pressure: dict[int, tuple] = {}
        self.dials = [dict(self._base_dials(t)) for t in (0, 1)]
        self.speed_cap = np.full(22, np.inf)
        self.zonal: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
        self.zonal_key: tuple = ()
        self.effort_acc = np.zeros(22)
        self.smooth_target: np.ndarray | None = None
        self.tick = 0
        self.possession_team = -1
        self.possession_seq = 0
        self.attacking_team = -1
        self.last_touch_team = -1
        self.decision_tick = 0
        self.spell: onball.Spell | None = None
        self.received: tuple[int, str, int] = (-1, "", -10_000)
        self.ball_in_hands = False
        self.ball_wait_until = 0
        self.stunned_until = np.zeros(22, dtype=np.int64)
        self.truth_passes: list[tuple] = []
        self.truth_shots: list[tuple] = []
        self.goals: list[dict[str, Any]] = []
        self.subbed_on: set[str] = set()
        self.sub_offset = [int(self.rng.integers(-4, 7)) for _ in (0, 1)]
        self.sub_limit = [int(self.rng.integers(3, 6)) for _ in (0, 1)]
        self.feed: list[dict[str, Any]] = []
        self.steer.setup(self)

    # ---- setup --------------------------------------------------------------------------
    def _team(self, index: int, club: Any, players: dict) -> TeamState:
        roster = {pid: players[pid] for pid in club.squad}
        return TeamState(
            index=index,
            club=club,
            roster=roster,
            roles=[slot.role for slot in club.lineup],
            on_pitch=[slot.player_id for slot in club.lineup],
            bench=list(club.bench),
        )

    def _base_dials(self, t: int) -> dict[str, float]:
        tactics = self.teams[t].club.tactics
        return {name: float(getattr(tactics, name)) for name in _DIALS}

    def _load_slot(self, slot: int) -> None:
        t, k = divmod(slot, 11)
        team = self.teams[t]
        role = team.roles[k]
        _, _, depth, y = ROLES[role]
        self.role_depth[slot], self.role_y[slot] = depth, y
        self.role_kind[slot] = role_kind(role)
        self.work_rate[slot] = 0.6 if self.role_kind[slot] == "ST" else 1.0  # strikers cover less
        if self.role_kind[slot] == "GK":
            self.gk_slot[t] = slot
        pid = team.on_pitch[k]
        if pid is None:
            self.bodies.active[slot] = False
            return
        player = team.roster[pid]
        a = player.attributes
        for name in ATTRIBUTES:
            self.attrs[name][slot] = getattr(a, name)
        self.bodies.vmax[slot] = vmax_kmh(a.pace, player.age) / 3.6
        self.bodies.a0[slot] = 2.6 + 0.03 * a.acceleration
        self.bodies.stamina[slot] = a.stamina / 100.0
        self.bodies.energy[slot] = 1.0
        self.bodies.active[slot] = True

    # ---- small helpers used everywhere ---------------------------------------------------
    @staticmethod
    def team_of(slot: int) -> int:
        """Team index (0 home, 1 away) of a slot."""
        return 0 if slot < 11 else 1

    def pid(self, slot: int) -> str:
        """Player id currently in ``slot``."""
        t, k = divmod(slot, 11)
        pid = self.teams[t].on_pitch[k]
        if pid is None:
            msg = f"slot {slot} is empty"
            raise ValueError(msg)
        return pid

    def slot_of(self, player_id: str) -> int:
        """Slot of an on-pitch player (−1 if not on the pitch)."""
        for t in (0, 1):
            if player_id in self.teams[t].on_pitch:
                return 11 * t + self.teams[t].on_pitch.index(player_id)
        return -1

    def attr(self, slot: int, name: str) -> int:
        """Attribute of the player in ``slot``."""
        return self.attrs[name][slot]

    def foot(self, slot: int) -> str:
        """Preferred foot of the player in ``slot``."""
        t = self.team_of(slot)
        return self.teams[t].roster[self.pid(slot)].preferred_foot

    def ball_rel(self, direction: int) -> tuple[float, float]:
        """Ball position in the frame of a team attacking in ``direction``."""
        return to_rel(self.bx, self.by, direction)

    def minute(self) -> int:
        """Current match minute (rounded down)."""
        return match_minute(self.clock.period, self.clock.clock_ms)

    def nearest_of_team(self, t: int, point: np.ndarray) -> tuple[int, float]:
        """Nearest active player of team ``t`` to ``point`` and the distance."""
        s = slice(11 * t, 11 * t + 11)
        diff = self.bodies.pos[s] - point
        dist2 = diff[:, 0] ** 2 + diff[:, 1] ** 2
        dist2[~self.bodies.active[s]] = np.inf
        k = int(np.argmin(dist2))
        return 11 * t + k, math.sqrt(float(dist2[k]))

    def offside_line(self, t: int) -> float:
        """Offside line in team ``t``'s frame: second-last opponent, ball, or halfway."""
        o = 1 - t
        s = slice(11 * o, 11 * o + 11)
        xs = self.bodies.pos[s, 0][self.bodies.active[s]]
        rel = xs if self.teams[t].direction > 0 else LENGTH - xs
        rel = np.sort(rel)
        second = float(rel[-2]) if len(rel) >= 2 else LENGTH
        return max(second, self.ball_rel(self.teams[t].direction)[0], 52.5)

    def set_possession(self, t: int) -> None:
        """Start a new possession when control passes to the other team."""
        if t != self.possession_team:
            self.possession_team = t
            self.possession_seq += 1

    def possession_id(self) -> str:
        """Current possession id (``m001-p0412``)."""
        return f"{self.setup.match_id}-p{self.possession_seq:04d}"

    def event_args(
        self, slot: int, at: tuple[float, float] | None = None, possession_change: bool = False
    ) -> dict[str, Any]:
        """Common event fields for an action by ``slot`` (at the ball unless ``at``)."""
        if possession_change:
            self.set_possession(self.team_of(slot))
        x, y = (
            at
            if at is not None
            else (float(self.bodies.pos[slot, 0]), float(self.bodies.pos[slot, 1]))
        )
        return {
            "team": self.teams[self.team_of(slot)].code,
            "player": self.pid(slot),
            "location": loc(x, y),
            "possession": self.possession_id(),
            "under_pressure": False,
        }

    def event_context(self, slot: int) -> dict[str, Any]:
        """Event fields for an on-ball action by ``slot`` at the ball, with pressure."""
        gap = self.nearest_of_team(1 - self.team_of(slot), np.array((self.bx, self.by)))[1]
        return {
            "team": self.teams[self.team_of(slot)].code,
            "player": self.pid(slot),
            "location": loc(self.bx, self.by),
            "possession": self.possession_id(),
            "under_pressure": gap < 2.5,
        }

    def recent_assist(self, slot: int) -> str:
        """Assist type (through ball, cut-back, cross) of the pass ``slot`` is still carrying."""
        who, kind, _ = self.received
        in_spell = self.spell is not None and self.spell.slot == slot
        if (
            who == slot
            and (in_spell or self.carrier < 0)
            and kind in ("through_ball", "cutback", "cross")
        ):
            return kind
        return "none"

    def note_release(self, slot: int, kind: str, action: Any) -> None:
        """The carrier released the ball: close his spell and carry plan."""
        if self.carrier == slot:
            onball.end_spell(self)
        self.clear_plan(slot)
        self.ball_in_hands = False

    # ---- plans ----------------------------------------------------------------------------
    def set_plan(self, slot: int, plan: Plan) -> None:
        """Give ``slot`` a movement plan; engine plans never replace scenario plans."""
        current = self.plans.get(slot)
        if current is not None and current.source == "scenario" and plan.source != "scenario":
            return
        self.plans[slot] = plan

    def clear_plan(self, slot: int) -> None:
        """Drop an engine plan of ``slot`` (scenario plans stay)."""
        plan = self.plans.get(slot)
        if plan is not None and plan.source != "scenario":
            del self.plans[slot]

    def cancel_engine_plans(self, t: int) -> None:
        """Drop every engine plan (runs, receptions, chases) of team ``t``."""
        for slot in [
            s for s, p in self.plans.items() if self.team_of(s) == t and p.source != "scenario"
        ]:
            del self.plans[slot]

    def _expire_plans(self) -> None:
        for slot in [
            s
            for s, p in self.plans.items()
            if p.until_tick is not None and p.until_tick < self.tick
        ]:
            del self.plans[slot]

    def update_runs(self) -> None:
        """Forwards of the team in possession sometimes run in behind the defensive line."""
        c = self.carrier
        t = self.team_of(c)
        d = self.teams[t].direction
        if self.ball_rel(d)[0] < 40.0:
            return
        draws = self.rng.random(11)
        line = self.offside_line(t)
        rate = self.params.run_hazard * self.params.tick_ms / 1000.0
        for slot, plan in list(self.plans.items()):  # runners caught beyond the line check back
            if plan.source == "run" and self.team_of(slot) == t:
                rel = self.bodies.pos[slot, 0] if d > 0 else LENGTH - self.bodies.pos[slot, 0]
                if rel > line + self.params.run_overshoot_m:
                    del self.plans[slot]
        for k in range(11):
            slot = 11 * t + k
            if (
                slot == c
                or slot in self.plans
                or draws[k] >= rate
                or not self.bodies.active[slot]
                or self.role_kind[slot] not in ("ST", "W", "AM", "WM")
            ):
                continue
            ry = float(self.role_y[slot])
            tx = min(line + 6.0 + 8.0 * float(self.rng.random()), LENGTH - 6.0)
            ty = min(max(ry + float(self.rng.normal(0.0, 4.0)), 4.0), 64.0)
            self.plans[slot] = Plan(
                to_abs(tx, ty, d),
                0.95,
                until_tick=self.tick + round(self.params.run_duration_s * 10),
                source="run",
            )

    # ---- discipline and substitutions ------------------------------------------------------
    def apply_card(self, slot: int, card: str) -> None:
        """Book or send off the player in ``slot``."""
        if card == "none":
            return
        team = self.teams[self.team_of(slot)]
        pid = self.pid(slot)
        if card == "yellow":
            team.yellows[pid] = team.yellows.get(pid, 0) + 1
            if team.yellows[pid] < 2:
                return
        team.sent_off.append(pid)
        team.on_pitch[slot % 11] = None
        self.bodies.active[slot] = False
        self.bodies.vel[slot] = 0.0
        self.recorder.set_slot(slot, None)
        self.clear_plan(slot)

    def tired_player(self, t: int) -> str | None:
        """Most tired outfield player the scenario allows to be replaced."""
        best, best_e = None, 2.0
        for k, pid in enumerate(self.teams[t].on_pitch):
            slot = 11 * t + k
            if (
                pid is None
                or slot == self.gk_slot[t]
                or pid in self.subbed_on
                or not self.steer.can_substitute(self, pid)
            ):
                continue
            if self.bodies.energy[slot] < best_e:
                best, best_e = pid, float(self.bodies.energy[slot])
        return best

    def bench_match(self, t: int, out: str) -> str | None:
        """Best bench player for the position of ``out``."""
        team = self.teams[t]
        kind = team.roster[out].position
        options = [
            p
            for p in team.bench
            if team.roster[p].position != "GK" and self.steer.can_substitute(self, p)
        ]
        if not options:
            return None
        return max(options, key=lambda p: (team.roster[p].position == kind, p))

    def substitute(self, t: int, out: str, incoming: str) -> bool:
        """Replace ``out`` by ``incoming`` in the same slot (he walks on at halfway)."""
        team = self.teams[t]
        if out not in team.on_pitch or incoming not in team.bench:
            return False
        k = team.on_pitch.index(out)
        slot = 11 * t + k
        team.on_pitch[k] = incoming
        team.bench.remove(incoming)
        team.subs_used += 1
        self.subbed_on.add(incoming)
        y_side = -0.5 if self.bodies.pos[slot, 1] < 34.0 else 68.5
        self._load_slot(slot)
        self.bodies.pos[slot] = (52.5, y_side)
        self.bodies.vel[slot] = 0.0
        self.recorder.set_slot(slot, incoming)
        self.clear_plan(slot)
        self.events.add(
            "substitution",
            self.clock.period,
            self.clock.clock_ms,
            team=team.code,
            player=out,
            location=None,
            possession=None,
            payload={"player_out": out, "player_in": incoming},
        )
        self.events.add(
            "stoppage",
            self.clock.period,
            self.clock.clock_ms,
            team=team.code,
            location=None,
            payload={
                "reason": "substitution",
                "restart_type": self.restart.kind if self.restart else "drop_ball",
            },
        )
        return True

    # ---- dials ---------------------------------------------------------------------------
    def _update_dials(self) -> None:
        minute = self.minute()
        for t in (0, 1):
            dial = self._base_dials(t)
            lead = self.teams[t].score - self.teams[1 - t].score
            if minute >= 60 and lead < 0:
                for name, delta in (
                    ("tempo", 0.12),
                    ("pressing_intensity", 0.15),
                    ("defensive_line", 0.10),
                    ("directness", 0.10),
                ):
                    dial[name] += delta
            elif minute >= 60 and lead > 0:
                for name, delta in (
                    ("defensive_line", -0.12),
                    ("pressing_intensity", -0.10),
                    ("tempo", -0.05),
                ):
                    dial[name] += delta
            if len(self.teams[t].sent_off) > len(self.teams[1 - t].sent_off):
                dial["pressing_intensity"] -= 0.10
                dial["defensive_line"] -= 0.06
            dial.update(self.steer.dial_overrides(self, t, dial))
            self.dials[t] = {k: min(max(v, 0.0), 1.0) for k, v in dial.items()}

    # ---- the loop ----------------------------------------------------------------------------
    def run(self) -> list[dict[str, Any]]:
        """Play both periods and return the finalized event feed."""
        self.events.add("match_metadata", 1, 0, payload=self.metadata_payload())
        for period in (1, 2):
            self._start_period(period)
            end_ms = self.setup.period_minutes * 60_000 + self.added_time[period - 1] * 60_000
            while not (self.clock.clock_ms >= end_ms and self._can_end(end_ms)):
                self._tick()
            self._end_period(period)
        self.events.add("match_end", 2, self.clock.clock_ms)
        self.feed = self.events.finalize(self.clock)
        self.steer.finish(self)
        return self.feed

    def _start_period(self, period: int) -> None:
        self.clock.period, self.clock.clock_ms = period, 0
        first = 1 if self.setup.home_attacks_right_first else -1
        self.teams[0].direction = first if period == 1 else -first
        self.teams[1].direction = -self.teams[0].direction
        kicking = 0 if period == 1 else 1
        self.plans.clear()
        self.smooth_target = None
        restarts.kickoff_positions(self, kicking)
        self.bx, self.by, self.bz = 52.5, 34.0, 0.11
        self.ball_state = BallState.DEAD
        self.restart = Restart(
            "kick_off",
            kicking,
            (52.5, 34.0),
            self.tick + 1,
            taker=restarts.choose_taker(self, "kick_off", kicking, (52.5, 34.0)),
            reason="period_start",
        )
        self._update_dials()
        self.events.add("period_start", period, 0)
        self.recorder.start_period(
            period, [self.teams[s // 11].on_pitch[s % 11] for s in range(22)]
        )

    def _can_end(self, end_ms: int) -> bool:
        if self.clock.clock_ms > end_ms + 40_000:
            return True
        if self.ball_state == BallState.IN_FLIGHT and self.flight and self.flight.kind == "shot":
            return False
        if self.ball_state == BallState.DEAD:
            return True
        t = self.attacking_team
        return t < 0 or self.ball_rel(self.teams[t].direction)[0] < 70.0

    def _end_period(self, period: int) -> None:
        if self.ball_state == BallState.CONTROLLED:
            onball.end_spell(self)
        elif self.ball_state == BallState.IN_FLIGHT and self.flight is not None:
            self._abandon_flight()
        onball.close_all_pressure(self)
        self.events.add("period_end", period, self.clock.clock_ms)
        self.recorder.end_period()
        self.clock.period_lengths_ms.append(self.clock.clock_ms)
        self.ball_state, self.carrier, self.flight, self.restart = BallState.DEAD, -1, None, None
        self.plans.clear()

    def _abandon_flight(self) -> None:
        """The whistle blows with the ball in the air: log a pass as incomplete."""
        from regista_sim.engine.flight import finish_pass, finish_shot

        f = self.flight
        if f.kind == "pass":
            finish_pass(self, f, "incomplete", (self.bx, self.by), None)
        elif f.kind == "shot":
            finish_shot(self, f, "off_target", (self.bx, self.by, self.bz))

    def _tick(self) -> None:
        self._expire_plans()
        if self.tick % 10 == 0:
            self._update_dials()
        self.steer.on_tick(self)
        self.pressers = []
        if self.ball_state == BallState.CONTROLLED:
            onball.controlled_step(self)
        elif self.ball_state == BallState.DEAD:
            restarts.dead_step(self)
        update_noise(self)
        target, urgency, cruise = compute_targets(self)
        integrate(self, target, urgency, cruise)
        if self.ball_state == BallState.CONTROLLED:
            self._ball_at_feet()
            onball.track_pressure(self)
        elif self.ball_state == BallState.IN_FLIGHT:
            resolve.advance(self)
        else:
            restarts.move_dead_ball(self)
        self.recorder.record(self.bodies.pos, (self.bx, self.by, self.bz))
        self.tick += 1
        self.clock.clock_ms += self.params.tick_ms

    def restart_targets(self, target: np.ndarray, urgency: np.ndarray, cruise: np.ndarray) -> None:
        """Dead-ball positions (delegates to ``restarts``)."""
        restarts.restart_targets(self, target, urgency, cruise)

    def _ball_at_feet(self) -> None:
        c = self.carrier
        vx, vy = self.bodies.vel[c]
        speed = math.hypot(vx, vy)
        x, y = self.bodies.pos[c]
        if speed > 0.4:
            x, y = x + 0.45 * vx / speed, y + 0.45 * vy / speed
        # a carrier on the line shields the ball inside it; running it out is touchline_squeeze
        self.bx = min(max(float(x), BALL_IN_M), LENGTH - BALL_IN_M)
        self.by = min(max(float(y), BALL_IN_M), WIDTH - BALL_IN_M)
        self.bz = 1.0 if self.ball_in_hands else 0.11

    # ---- metadata ----------------------------------------------------------------------------
    def metadata_payload(self) -> dict[str, Any]:
        """Teams, line-ups, formations, kits, venue, referee, directions and weather."""
        teams = {}
        for side, team in zip(("home", "away"), self.teams, strict=True):
            club = team.club
            kit = club.home_kit if side == "home" else club.away_kit
            teams[side] = {
                "team_id": club.code,
                "name": club.name,
                "short_name": club.short_name,
                "formation": club.tactics.formation,
                "kit": kit.model_dump(),
                "lineup": [
                    {
                        "player_id": pid,
                        "role": role,
                        "name": team.roster[pid].name,
                        "shirt_number": team.roster[pid].shirt_number,
                        "position": team.roster[pid].position,
                    }
                    for role, pid in zip(team.roles, team.on_pitch, strict=True)
                ],
                "bench": [
                    {
                        "player_id": pid,
                        "name": team.roster[pid].name,
                        "shirt_number": team.roster[pid].shirt_number,
                        "position": team.roster[pid].position,
                    }
                    for pid in team.bench
                ],
            }
        first = (
            self.teams[0].club.code
            if self.setup.home_attacks_right_first
            else self.teams[1].club.code
        )
        second = (
            self.teams[1].club.code if first == self.teams[0].club.code else self.teams[0].club.code
        )
        return {
            "teams": teams,
            "venue": self.setup.venue or self.teams[0].club.venue,
            "referee": self.setup.referee,
            "attacking_directions": [
                {"period": 1, "towards_x_105": first},
                {"period": 2, "towards_x_105": second},
            ],
            "weather": self.setup.weather,
        }
