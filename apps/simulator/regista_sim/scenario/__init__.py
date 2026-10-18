"""Scripted scenarios: the YAML DSL, the director that plays it, and the match setup it implies."""

from regista_sim.engine.match import MatchSetup
from regista_sim.models import League
from regista_sim.scenario.dsl import Scenario


def setup_from_scenario(scenario: Scenario, league: League, seed: int) -> MatchSetup:
    """Build the engine's ``MatchSetup`` from a scenario's ``match`` block."""
    spec = scenario.match
    referee = next((r for r in league.referees if r.id == spec.referee), None)
    return MatchSetup(
        match_id=spec.match_id,
        home=spec.home,
        away=spec.away,
        seed=seed,
        kickoff=spec.kickoff,
        added_time_min=spec.added_time_min,
        half_time_break_ms=spec.half_time_break_s * 1000,
        home_attacks_right_first=spec.home_attacks_right_first,
        venue=spec.venue or league.club(spec.home).venue,
        referee={"id": referee.id, "name": referee.name} if referee else None,
        weather=spec.weather,
        matchweek=spec.matchweek,
    )
