"""Scenario DSL: a YAML script of beats, regimes and guards (docs/DATA_AND_METRICS.md §2–§3).

Coordinates in beats are team-relative to the beat's team (it attacks towards ``x = 105``, its
left touchline is ``y = 0``), so a script does not care which way a team attacks in a period.
Times are match clocks: ``"67:20"``, or ``"45+2:10"`` in first-half stoppage time.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

SCENARIO_SCHEMA = "regista.scenario.v1"
SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"

Point = tuple[float, float]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MatchSpec(_Model):
    """Fixture, kick-off time, officials and fixed match facts."""

    match_id: str = Field(pattern=r"^[a-z0-9]+$")
    home: str
    away: str
    matchweek: int | None = None
    kickoff: datetime
    referee: str | None = None
    venue: str | None = None
    weather: dict[str, Any] | None = None
    added_time_min: tuple[int, int] | None = None
    half_time_break_s: int = 900
    home_attacks_right_first: bool = True

    @field_validator("kickoff")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "kickoff must include a UTC offset"
            raise ValueError(msg)
        return value


class ShotBan(_Model):
    """A player who takes no unscripted shot until a match time."""

    player: str
    until: str


class Guards(_Model):
    """Free-play limits that keep the script's story intact."""

    unscripted_goals: bool = True
    unscripted_red_cards: bool = True
    protected_players: list[str] = []
    max_unscripted_speed_kmh: float | None = None
    no_unscripted_shots: list[ShotBan] = []


class Regime(_Model):
    """Tactical dial overrides for a team inside a time window (with a linear ramp)."""

    team: str
    start: str = Field(alias="from")
    end: str = Field(alias="to")
    ramp_s: float = 0.0
    dials: dict[str, float] = Field(default_factory=dict, alias="set")
    # < 1: that share of the team's would-be completions arrive (a nervy spell);
    # > 1: (completion − 1) of its would-be failures arrive anyway (a steady spell)
    completion: float = Field(1.0, gt=0.0, lt=2.0)


class Substitution(_Model):
    """A scripted substitution, made at the first stoppage after ``at``."""

    at: str
    team: str
    out: str
    incoming: str = Field(alias="in")


class Correction(_Model):
    """A ``data_correction`` event on the shot of a beat."""

    at: str
    beat: str
    field: str
    old: Any
    new: Any
    reason: str


class Step(_Model):
    """One scripted on-ball action. ``player`` "carrier" means whoever has the ball."""

    action: Literal["pass", "carry", "shot"]
    player: str = "carrier"
    to: str | None = None
    at: Point | None = None
    speed_kmh: float | None = None
    height: Literal["ground", "low", "high"] = "ground"
    pass_type: str = "open_play"
    outcome: str | None = None
    first_time: bool = False
    aim: Point | None = None  # shots: (y, z) at the goal line, team-relative y
    credit_to: str | None = None
    clear_cone: bool = False  # shots: defenders in the shooter's cone step out as the ball comes


class Run(_Model):
    """A movement plan for a player: from a step onwards, run to a point (optionally capped)."""

    player: str
    start_step: int = 0
    to: Point
    speed_kmh: float | None = None
    urgency: float = 1.0
    at_launch: bool = False  # start when step ``start_step`` is struck, not when it begins


class Hold(_Model):
    """Players told to take up positions (team-relative to the beat's team) during a beat."""

    player: str
    at: Point
    until_step: int = 99
    urgency: float = 0.8
    from_start: bool = False  # take the position as soon as the beat starts acquiring
    near: str | None = None  # follow this player: ``at`` is then an offset from him


class Acquire(_Model):
    """How the beat's team gets the ball: keep or win possession, or a turnover in a zone."""

    mode: Literal["possession", "turnover"] = "possession"
    zone: tuple[float, float] = (0.0, 105.0)  # turnover: x range (beat team's frame) of the regain
    hub: Point | None = None  # possession: where the ball is brought before the steps start


class Beat(_Model):
    """A scripted moment: its key action happens at ``at`` (display minute ``minute``)."""

    id: str
    minute: str
    at: str
    team: str
    kind: str
    lead_s: float = 75.0
    acquire: Acquire = Acquire()
    steps: list[Step]
    runs: list[Run] = []
    holds: list[Hold] = []
    targets: dict[str, Any] = {}


class Scenario(_Model):
    """A whole scripted match."""

    schema_: str = Field(default=SCENARIO_SCHEMA, alias="schema")
    name: str
    description: str = ""
    match: MatchSpec
    guards: Guards = Guards()
    regimes: list[Regime] = []
    substitutions: list[Substitution] = []
    corrections: list[Correction] = []
    beats: list[Beat] = []


def scenario_path(name_or_path: str) -> Path:
    """Resolve ``golden`` to ``apps/simulator/scenarios/golden.yaml``, or accept a path."""
    path = Path(name_or_path)
    if path.suffix in (".yaml", ".yml") and path.exists():
        return path
    return SCENARIO_DIR / f"{name_or_path}.yaml"


def load_scenario(name_or_path: str) -> Scenario:
    """Load and validate a scenario file."""
    path = scenario_path(name_or_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Scenario.model_validate(data)
