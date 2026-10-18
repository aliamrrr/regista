"""Pydantic models for the fictional league (``data/league/*.json``)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LEAGUE_SCHEMA = "regista.league.v1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Kit(_Model):
    """A kit as two hex colours."""

    primary: str = Field(pattern=r"^#[0-9a-f]{6}$")
    secondary: str = Field(pattern=r"^#[0-9a-f]{6}$")


class Tactics(_Model):
    """A club's tactical profile; the 0–1 dials drive the match engine."""

    formation: str
    pressing_intensity: float = Field(ge=0, le=1)
    defensive_line: float = Field(ge=0, le=1)
    tempo: float = Field(ge=0, le=1)
    directness: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    attack_rating: float = Field(ge=0, le=100, description="first-XI attacking quality, 0–100")
    defence_rating: float = Field(ge=0, le=100, description="first-XI defensive quality, 0–100")


class LineupSlot(_Model):
    """One role of the first XI."""

    role: str
    player_id: str


class Club(_Model):
    """A fictional club."""

    code: str = Field(pattern=r"^[A-Z]{3}$")
    name: str
    short_name: str
    venue: str
    home_kit: Kit
    away_kit: Kit
    tactics: Tactics
    squad: list[str]
    lineup: list[LineupSlot]
    bench: list[str]


class Attributes(_Model):
    """Player attributes, 1–99."""

    pace: int = Field(ge=1, le=99)
    acceleration: int = Field(ge=1, le=99)
    stamina: int = Field(ge=1, le=99)
    passing: int = Field(ge=1, le=99)
    vision: int = Field(ge=1, le=99)
    dribbling: int = Field(ge=1, le=99)
    finishing: int = Field(ge=1, le=99)
    composure: int = Field(ge=1, le=99)
    tackling: int = Field(ge=1, le=99)
    positioning: int = Field(ge=1, le=99)
    aerial: int = Field(ge=1, le=99)
    goalkeeping: int = Field(ge=1, le=99)


class Player(_Model):
    """A fictional player; ``id`` is ``{club}-{shirt_number}``."""

    id: str = Field(pattern=r"^[A-Z]{3}-\d{1,2}$")
    club: str
    shirt_number: int = Field(ge=1, le=99)
    first_name: str
    last_name: str
    name: str
    position: Literal["GK", "RB", "LB", "CB", "DM", "CM", "AM", "RW", "LW", "ST"]
    preferred_foot: Literal["right", "left", "both"]
    age: int
    birth_date: str
    attributes: Attributes


class SeasonRecord(_Model):
    """One season of a player's league career."""

    season: str
    club: str
    appearances: int
    goals: int
    assists: int
    clean_sheets: int
    top_speed_kmh: float | None


class CareerTotals(_Model):
    """Career totals before the next match (``top_speed_kmh`` is the best season best)."""

    appearances: int
    goals: int
    assists: int
    clean_sheets: int
    top_speed_kmh: float | None


class Career(_Model):
    """A player's career history (used by the Archivist for milestones and records)."""

    player_id: str
    totals: CareerTotals
    seasons: list[SeasonRecord]


class MatchLogEntry(_Model):
    """One of a player's last ten league matches (``minutes`` 0 = unused)."""

    date: str
    season: str
    matchweek: int
    opponent: str
    venue: Literal["H", "A"]
    minutes: int
    goals: int
    assists: int
    top_speed_kmh: float | None


class MatchLog(_Model):
    """A player's last ten league matches, oldest first."""

    player_id: str
    matches: list[MatchLogEntry]


class Fixture(_Model):
    """A league fixture."""

    matchweek: int
    date: str
    home: str
    away: str


class Referee(_Model):
    """A fictional referee."""

    id: str
    name: str


class League(_Model):
    """The whole fictional league, as written to ``data/league``."""

    schema_: str = Field(default=LEAGUE_SCHEMA, alias="schema")
    name: str
    season: str
    seed: int
    generator: str
    next_matchweek: int
    fixtures: list[Fixture]
    referees: list[Referee]
    clubs: list[Club]
    players: list[Player]
    careers: list[Career]
    match_logs: list[MatchLog]

    def club(self, code: str) -> Club:
        """Return the club with ``code``."""
        return next(c for c in self.clubs if c.code == code)

    def player(self, player_id: str) -> Player:
        """Return the player with ``player_id``."""
        return self.players_by_id()[player_id]

    def players_by_id(self) -> dict[str, Player]:
        """Return every player keyed by id."""
        return {p.id: p for p in self.players}
