"""Scenario director: the ``Steering`` that plays a scripted match (§2 Scenario DSL, §3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from regista_sim.engine.clock import minute_label, parse_match_time
from regista_sim.engine.events import EventRef
from regista_sim.engine.steering import Steering
from regista_sim.scenario.beats import DONE, BeatRunner
from regista_sim.scenario.dsl import Scenario

if TYPE_CHECKING:
    from regista_sim.engine.decisions import Action
    from regista_sim.engine.match import Match
    from regista_sim.engine.state import Flight

_PERIOD = 10_000_000  # time key = period × _PERIOD + clock_ms (comparable across periods)


def time_key(period: int, clock_ms: int) -> int:
    """Comparable key for a (period, clock) pair."""
    return period * _PERIOD + clock_ms


class Director(Steering):
    """Plays the scenario: regimes, guards, substitutions, corrections and beats."""

    def __init__(self, scenario: Scenario) -> None:
        self.s = scenario
        g = scenario.guards
        self.protected = set(g.protected_players)
        self.bans = [(b.player, self.when(b.until)) for b in g.no_unscripted_shots]
        self.subs = [
            {"at": self.when(x.at), "team": x.team, "out": x.out, "in": x.incoming, "done": False}
            for x in scenario.substitutions
        ]
        self.protected |= {x.incoming for x in scenario.substitutions}
        self.corrections = [
            {"spec": c, "at": self.when(c.at), "done": False} for c in scenario.corrections
        ]
        self.regimes = [
            (r.team, self.when(r.start), self.when(r.end), int(r.ramp_s * 1000), r.dials)
            for r in scenario.regimes
        ]
        self.spells = [  # nervy (completion < 1) or steady (> 1) passing spells
            (r.team, self.when(r.start), self.when(r.end), r.completion)
            for r in scenario.regimes
            if r.completion != 1.0
        ]
        self.beats = [BeatRunner(self, b) for b in scenario.beats]
        self.logged_corrections: list[dict[str, Any]] = []
        self.needed_until: dict[str, int] = {}  # player → time key of the last beat that uses him
        for beat in scenario.beats:
            names = {st.player for st in beat.steps if st.player != "carrier"}
            names |= {st.to for st in beat.steps if st.to} | {r.player for r in beat.runs}
            names |= {h.player for h in beat.holds}
            for name in names:
                self.needed_until[name] = max(
                    self.needed_until.get(name, 0), self.when(beat.at) + 60_000
                )

    # ---- helpers --------------------------------------------------------------------------------
    @staticmethod
    def when(text: str) -> int:
        """Time key of a scenario time string."""
        return time_key(*parse_match_time(text))

    @staticmethod
    def now(m: Match) -> int:
        """Time key of the engine's current tick."""
        return time_key(m.clock.period, m.clock.clock_ms)

    @staticmethod
    def team_index(m: Match, code: str) -> int:
        """Index of the team with ``code``."""
        return 0 if m.teams[0].code == code else 1

    def current(self) -> BeatRunner | None:
        """The beat in progress, if any."""
        return next((b for b in self.beats if b.state not in ("wait", DONE)), None)

    # ---- hooks -------------------------------------------------------------------------------
    def setup(self, m: Match) -> None:
        """Apply speed guards before kick-off."""
        cap = self.s.guards.max_unscripted_speed_kmh
        if cap is not None:
            m.speed_cap[:] = cap / 3.6

    def on_tick(self, m: Match) -> None:
        """Advance beats and log due corrections."""
        now = self.now(m)
        for beat in self.beats:
            if beat.state != DONE:
                beat.tick(m, now)
                if beat.state not in ("wait", DONE):
                    break
        for item in self.corrections:
            if not item["done"] and now >= item["at"]:
                self._correct(m, item)

    def _correct(self, m: Match, item: dict[str, Any]) -> None:
        spec = item["spec"]
        beat = next(b for b in self.beats if b.b.id == spec.beat)
        ref = beat.refs.get("shot")
        if ref is None:
            return
        item["done"] = True
        m.events.add(
            "data_correction",
            m.clock.period,
            m.clock.clock_ms,
            team=beat.b.team,
            payload={
                "target_event_id": ref,
                "field": spec.field,
                "old_value": spec.old,
                "new_value": spec.new,
                "reason": spec.reason,
            },
        )
        self.logged_corrections.append(
            {
                "beat": spec.beat,
                "ref": ref,
                "field": spec.field,
                "old_value": spec.old,
                "new_value": spec.new,
                "minute": minute_label(m.clock.period, m.clock.clock_ms),
            }
        )

    def choose(self, m: Match, carrier: int) -> Action | None:
        """Scripted actions while a beat controls play."""
        beat = self.current()
        return beat.choose(m, carrier) if beat is not None else None

    def can_shoot(self, m: Match, slot: int) -> bool:
        """No unscripted shots for banned players before their time."""
        pid = m.pid(slot)
        now = self.now(m)
        return not any(pid == player and now < until for player, until in self.bans)

    def pass_result(self, m: Match, action: Action, natural: str) -> str:
        """Scripted passes keep their outcome; acquisitions cut out the opponent's pass."""
        if action.tag and action.outcome:
            return action.outcome
        beat = self.current()
        passer = m.carrier
        if beat is not None and passer >= 0:
            if beat.wants_interception(m, passer):
                return "incomplete"
            if beat.busy() and m.team_of(passer) == beat.team(m):
                return "complete"
        if self._sub_overdue(m):
            return "out"
        if passer >= 0 and natural in ("complete", "incomplete", "out"):
            now, code = self.now(m), m.teams[m.team_of(passer)].code
            for team, start, end, factor in self.spells:
                if team != code or not start <= now < end:
                    continue
                if factor < 1.0 and natural == "complete" and m.rng.random() > factor:
                    return "incomplete"  # nervy: a pass that should have arrived does not
                if factor > 1.0 and natural != "complete" and m.rng.random() < factor - 1.0:
                    return "complete"  # steady: a pass that should have failed finds its man
        return natural

    def shot_result(self, m: Match, action: Action, natural: str) -> str:
        """Scripted shots keep their outcome; unscripted ones cannot score if guarded."""
        if action.tag and action.outcome:
            return action.outcome
        if natural == "goal" and not self.s.guards.unscripted_goals:
            return "saved"
        return natural

    def card_result(self, m: Match, fouler: int, card: str) -> str:
        """No unscripted red cards (and no second yellows) when guarded."""
        if self.s.guards.unscripted_red_cards:
            return card
        if card == "red":
            card = "yellow"
        team = m.teams[m.team_of(fouler)]
        if card == "yellow" and team.yellows.get(m.pid(fouler), 0) >= 1:
            return "none"
        return card

    def allow_challenge(self, m: Match, carrier: int, defender: int) -> bool:
        """Leave the beat team's carrier alone while its move runs or its regain is set up.

        A foul then would stop play and eat the turnover window.
        """
        beat = self.current()
        if beat is None or m.team_of(carrier) != beat.team(m):
            return True
        return not (beat.busy() or beat.setting_up_regain(m))

    def restart_ticks(self, m: Match, kind: str, ticks: int, shortest: int) -> int:
        """While a beat is due (or about to be), restarts are taken at the short end."""
        now = self.now(m)
        soon = any(b.state != DONE and now >= b.t_start - 100_000 for b in self.beats)
        return shortest if soon else ticks

    def forced_tackle(self, m: Match, carrier: int) -> int:
        """Turnover beats in their window: a defender within 2 m wins the ball cleanly."""
        beat = self.current()
        if beat is None or not beat.wants_interception(m, carrier):
            return -1
        j, gap = m.nearest_of_team(1 - m.team_of(carrier), m.bodies.pos[carrier])
        return j if gap < 2.0 else -1

    def can_substitute(self, m: Match, player_id: str) -> bool:
        """Stars, scripted substitutes and players a later beat needs are not changed."""
        if player_id in self.protected or self.current() is not None:
            return False
        return self.now(m) > self.needed_until.get(player_id, 0)

    def due_substitutions(self, m: Match) -> list[tuple[int, str, str]]:
        """Scripted substitutions whose time has come."""
        now = self.now(m)
        due = []
        for sub in self.subs:
            if not sub["done"] and now >= sub["at"]:
                sub["done"] = True
                due.append((self.team_index(m, sub["team"]), sub["out"], sub["in"]))
        return due

    def _sub_overdue(self, m: Match) -> bool:
        now = self.now(m)
        return any(not s["done"] and now >= s["at"] + 20_000 for s in self.subs)

    def dial_overrides(self, m: Match, team: int, dial: dict[str, float]) -> dict[str, float]:
        """Regime dials for ``team`` (linear ramp in and out)."""
        now = self.now(m)
        code = m.teams[team].code
        out: dict[str, float] = {}
        for who, start, end, ramp, dials in self.regimes:
            if who != code or not start <= now < end:
                continue
            w = 1.0 if ramp <= 0 else min(1.0, (now - start) / ramp, (end - now) / ramp)
            for name, value in dials.items():
                base = out.get(name, dial[name])
                out[name] = base + w * (value - base)
        return out

    def on_control(self, m: Match, slot: int, how: str) -> None:
        """Let the running beat react to receptions and regains."""
        beat = self.current()
        if beat is not None:
            beat.on_control(m, slot, how)

    def on_pass(self, m: Match, ref: EventRef, flight: Flight, outcome: str) -> None:
        """Remember the passes of scripted moves (and notice the ones that went astray)."""
        self._remember(flight, ref, "pass")
        tag = flight.truth.get("tag", "")
        beat = self.current()
        if beat is not None and tag.startswith(beat.b.id + ":"):
            beat.pass_resolved(m, tag, outcome)

    def on_shot(self, m: Match, ref: EventRef, flight: Flight, outcome: str) -> None:
        """Remember the shots of scripted moves."""
        self._remember(flight, ref, "shot")

    def _remember(self, flight: Flight, ref: EventRef, kind: str) -> None:
        tag = flight.truth.get("tag", "")
        if not tag or ":" not in tag:
            return
        beat_id, step = tag.split(":")
        for beat in self.beats:
            if beat.b.id == beat_id:
                beat.refs[f"{kind}" if kind == "shot" else f"{kind}_{step}"] = ref

    def truth(self, m: Match) -> dict[str, Any]:
        """Beats, corrections, regimes and scripted substitutions for ``ground_truth.json``."""
        return {
            "beats": [beat.record(m) for beat in self.beats],
            "corrections": [
                {
                    **{k: v for k, v in c.items() if k != "ref"},
                    "target_event_id": m.events.ids[c["ref"].index],
                }
                for c in self.logged_corrections
            ],
            "regimes": [r.model_dump(by_alias=True) for r in self.s.regimes],
            "scripted_substitutions": [s.model_dump(by_alias=True) for s in self.s.substitutions],
        }
