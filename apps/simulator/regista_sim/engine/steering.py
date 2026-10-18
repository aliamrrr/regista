"""Hooks a scenario uses to steer the engine. The base class steers nothing (free play).

A scenario may choose actions, force outcomes, set movement plans and dial overrides, and add
events (substitutions, corrections). It never moves a player or the ball directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from regista_sim.engine.decisions import Action
    from regista_sim.engine.events import EventRef
    from regista_sim.engine.match import Match
    from regista_sim.engine.state import Flight, Restart


class Steering:
    """Free play: every hook keeps the engine's own choice."""

    def setup(self, m: Match) -> None:
        """Called once the match is built, before kick-off."""

    def on_tick(self, m: Match) -> None:
        """Called at the start of every tick."""

    def choose(self, m: Match, carrier: int) -> Action | None:
        """Return an action for ``carrier``, or None to let the decision model choose."""
        return None

    def restart_action(self, m: Match, restart: Restart) -> Action | None:
        """Return the restart action, or None for the default set piece."""
        return None

    def can_shoot(self, m: Match, slot: int) -> bool:
        """Whether ``slot`` may consider a shot."""
        return True

    def pass_result(self, m: Match, action: Action, natural: str) -> str:
        """Final planned outcome of a pass (``natural`` was sampled from the true model)."""
        return natural

    def shot_result(self, m: Match, action: Action, natural: str) -> str:
        """Final planned outcome of a shot."""
        return natural

    def card_result(self, m: Match, fouler: int, card: str) -> str:
        """Final card for a foul."""
        return card

    def allow_challenge(self, m: Match, carrier: int, defender: int) -> bool:
        """Whether ``defender`` may challenge ``carrier`` now."""
        return True

    def restart_ticks(self, m: Match, kind: str, ticks: int, shortest: int) -> int:
        """Delay before a restart is taken (``shortest`` is the low end of its range)."""
        return ticks

    def forced_tackle(self, m: Match, carrier: int) -> int:
        """A defender slot that wins the ball off ``carrier`` now (−1: none)."""
        return -1

    def can_substitute(self, m: Match, player_id: str) -> bool:
        """Whether the engine may substitute (or bring on) ``player_id``."""
        return True

    def due_substitutions(self, m: Match) -> list[tuple[int, str, str]]:
        """Scripted substitutions to make at this stoppage: (team, out, in)."""
        return []

    def dial_overrides(self, m: Match, team: int, dial: dict[str, float]) -> dict[str, float]:
        """Tactical dial values to override for ``team`` (after game-state effects)."""
        return {}

    def on_control(self, m: Match, slot: int, how: str) -> None:
        """Called when ``slot`` gains control of the ball."""

    def on_pass(self, m: Match, ref: EventRef, flight: Flight, outcome: str) -> None:
        """Called when a pass is resolved and logged."""

    def on_shot(self, m: Match, ref: EventRef, flight: Flight, outcome: str) -> None:
        """Called when a shot is resolved and logged."""

    def on_goal(self, m: Match, flight: Flight) -> None:
        """Called after a goal is scored."""

    def on_stoppage(self, m: Match, reason: str, kind: str, team: int) -> None:
        """Called when play stops."""

    def finish(self, m: Match) -> None:
        """Called after the final whistle, once the feed is finalized."""

    def truth(self, m: Match) -> dict[str, Any]:
        """Extra ``ground_truth.json`` sections (beats, corrections) — none in free play."""
        return {}
