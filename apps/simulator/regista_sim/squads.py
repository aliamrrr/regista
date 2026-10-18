"""Players and lineups: attributes by position, demo-club templates, shirt numbers, first XI."""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from regista_sim.formations import FORMATIONS, role_fit, role_kind
from regista_sim.names import person_name

ATTRIBUTES = (
    "pace",
    "acceleration",
    "stamina",
    "passing",
    "vision",
    "dribbling",
    "finishing",
    "composure",
    "tackling",
    "positioning",
    "aerial",
    "goalkeeping",
)
SEASON_REFERENCE_DATE = date(2026, 10, 24)  # golden match day: ages are given on this date

# Mean attributes per position, in ATTRIBUTES order.
_MEANS: dict[str, tuple[int, ...]] = {
    "GK": (45, 50, 52, 46, 42, 30, 14, 58, 18, 58, 56, 74),
    "RB": (75, 75, 77, 66, 60, 66, 42, 62, 68, 66, 58, 10),
    "LB": (75, 75, 77, 66, 60, 66, 42, 62, 68, 66, 58, 10),
    "CB": (63, 61, 67, 61, 53, 52, 36, 63, 74, 72, 76, 10),
    "DM": (63, 64, 77, 72, 68, 63, 50, 66, 72, 70, 65, 10),
    "CM": (66, 67, 78, 74, 72, 68, 58, 66, 62, 65, 58, 10),
    "AM": (70, 73, 71, 76, 78, 76, 68, 70, 46, 65, 50, 10),
    "RW": (80, 80, 73, 68, 68, 78, 66, 64, 42, 63, 50, 10),
    "LW": (80, 80, 73, 68, 68, 78, 66, 64, 42, 63, 50, 10),
    "ST": (74, 74, 69, 62, 62, 70, 76, 68, 36, 71, 67, 10),
}
_OVERALL_WEIGHTS: dict[str, dict[str, float]] = {
    "GK": {"goalkeeping": 0.7, "positioning": 0.1, "composure": 0.1, "aerial": 0.1},
    "FB": {
        "pace": 0.2,
        "stamina": 0.15,
        "tackling": 0.2,
        "positioning": 0.15,
        "passing": 0.15,
        "dribbling": 0.15,
    },
    "CB": {
        "tackling": 0.3,
        "positioning": 0.25,
        "aerial": 0.2,
        "pace": 0.1,
        "passing": 0.1,
        "composure": 0.05,
    },
    "DM": {"tackling": 0.25, "positioning": 0.2, "passing": 0.25, "stamina": 0.15, "vision": 0.15},
    "CM": {
        "passing": 0.3,
        "vision": 0.2,
        "stamina": 0.15,
        "dribbling": 0.15,
        "tackling": 0.1,
        "composure": 0.1,
    },
    "AM": {"passing": 0.25, "vision": 0.25, "dribbling": 0.2, "finishing": 0.15, "composure": 0.15},
    "W": {
        "pace": 0.25,
        "acceleration": 0.15,
        "dribbling": 0.25,
        "passing": 0.1,
        "finishing": 0.15,
        "vision": 0.1,
    },
    "ST": {
        "finishing": 0.35,
        "composure": 0.15,
        "positioning": 0.15,
        "pace": 0.15,
        "aerial": 0.1,
        "dribbling": 0.1,
    },
}
_POSITION_KIND = {
    "GK": "GK",
    "RB": "FB",
    "LB": "FB",
    "CB": "CB",
    "DM": "DM",
    "CM": "CM",
    "AM": "AM",
    "RW": "W",
    "LW": "W",
    "ST": "ST",
}
_ROLE_KIND_TO_WEIGHTS = {
    "GK": "GK",
    "CB": "CB",
    "FB": "FB",
    "WB": "FB",
    "DM": "DM",
    "CM": "CM",
    "AM": "AM",
    "WM": "W",
    "W": "W",
    "ST": "ST",
}

SQUAD_SHAPE = (
    ("GK", 3),
    ("RB", 2),
    ("LB", 2),
    ("CB", 4),
    ("DM", 2),
    ("CM", 4),
    ("AM", 2),
    ("RW", 2),
    ("LW", 2),
    ("ST", 2),
)
_CLASSIC_NUMBERS = {
    "GK": (1, 13),
    "RB": (2,),
    "LB": (3,),
    "CB": (5, 6),
    "DM": (4,),
    "CM": (8,),
    "AM": (10,),
    "RW": (7,),
    "LW": (11,),
    "ST": (9,),
}


@dataclass
class PlayerSpec:
    """A generated player before it becomes a pydantic ``Player``."""

    club: str
    shirt: int
    position: str
    first_name: str
    last_name: str
    foot: str
    age: int
    birth_date: str
    attributes: dict[str, int]

    @property
    def player_id(self) -> str:
        """Return the stable id ``{club}-{shirt}``."""
        return f"{self.club}-{self.shirt}"


@dataclass(frozen=True)
class Star:
    """A fixed, named demo player (docs/DATA_AND_METRICS.md §1)."""

    first_name: str
    last_name: str
    age: int
    foot: str
    attributes: tuple[int, ...]  # ATTRIBUTES order


@dataclass(frozen=True)
class ClubTemplate:
    """A hand-written squad: shirt → position, optional star, plus the first XI and bench."""

    squad: dict[int, str]
    stars: dict[int, Star]
    lineup: tuple[tuple[str, int], ...]  # (role, shirt)
    bench: tuple[int, ...]
    boosts: dict[int, dict[str, int]] = field(default_factory=dict)


DEMO_TEMPLATES: dict[str, ClubTemplate] = {
    "HMR": ClubTemplate(
        squad={
            1: "GK",
            13: "GK",
            31: "GK",
            2: "RB",
            22: "RB",
            3: "LB",
            23: "LB",
            5: "CB",
            6: "CB",
            15: "CB",
            26: "CB",
            4: "DM",
            16: "DM",
            8: "CM",
            14: "CM",
            18: "CM",
            20: "CM",
            10: "AM",
            21: "AM",
            7: "RW",
            17: "RW",
            11: "LW",
            19: "LW",
            9: "ST",
            24: "ST",
        },
        stars={
            9: Star(
                "Iker", "Valdane", 27, "right", (83, 85, 80, 70, 72, 80, 89, 87, 34, 88, 79, 10)
            ),
            10: Star(
                "Mattis", "Quell", 26, "left", (72, 76, 80, 92, 94, 85, 72, 88, 50, 78, 52, 10)
            ),
            7: Star(
                "Kian", "Sorvali", 23, "left", (96, 94, 82, 72, 70, 86, 74, 72, 38, 72, 48, 10)
            ),
        },
        lineup=(
            ("GK", 1),
            ("RB", 2),
            ("RCB", 5),
            ("LCB", 6),
            ("LB", 3),
            ("DM", 4),
            ("RCM", 8),
            ("LCM", 10),
            ("RW", 7),
            ("ST", 9),
            ("LW", 11),
        ),
        bench=(13, 22, 15, 16, 14, 18, 21, 17, 24),
        boosts={8: {"stamina": 84, "passing": 76, "pace": 74}, 11: {"finishing": 79, "pace": 82}},
    ),
    "KBA": ClubTemplate(
        squad={
            1: "GK",
            13: "GK",
            30: "GK",
            2: "RB",
            24: "RB",
            3: "LB",
            23: "LB",
            5: "CB",
            6: "CB",
            16: "CB",
            25: "CB",
            4: "DM",
            21: "DM",
            8: "CM",
            15: "CM",
            14: "CM",
            18: "CM",
            10: "AM",
            20: "AM",
            7: "RW",
            22: "RW",
            17: "LW",
            19: "LW",
            9: "ST",
            11: "ST",
        },
        stars={
            7: Star(
                "Yanis", "Belkora", 25, "right", (85, 88, 80, 76, 77, 88, 83, 80, 40, 79, 55, 10)
            ),
            11: Star(
                "Oskar", "Vennholm", 28, "left", (78, 79, 76, 68, 70, 74, 82, 79, 38, 82, 85, 10)
            ),
        },
        lineup=(
            ("GK", 1),
            ("RB", 2),
            ("RCB", 5),
            ("LCB", 6),
            ("LB", 3),
            ("RM", 7),
            ("RCM", 8),
            ("LCM", 4),
            ("LM", 17),
            ("RST", 11),
            ("LST", 9),
        ),
        bench=(13, 24, 16, 21, 15, 14, 10, 22, 19),
        boosts={
            15: {"stamina": 87, "tackling": 77, "pace": 75, "acceleration": 76},
            19: {"pace": 88, "acceleration": 88, "stamina": 85, "tackling": 52},
        },
    ),
}


def overall(attributes: dict[str, int], kind: str) -> float:
    """Return a 1–99 rating of a player for a role kind (``"CB"``, ``"W"``, ...)."""
    weights = _OVERALL_WEIGHTS[_ROLE_KIND_TO_WEIGHTS.get(kind, kind)]
    return sum(attributes[name] * w for name, w in weights.items())


def position_kind(position: str) -> str:
    """Return the rating kind used for a player position (``"RB"`` → ``"FB"``)."""
    return _POSITION_KIND[position]


def _birth_date(rng: np.random.Generator, age: int) -> str:
    born = SEASON_REFERENCE_DATE.replace(year=SEASON_REFERENCE_DATE.year - age - 1)
    born += timedelta(days=int(rng.integers(1, 365)))
    return born.isoformat()


def _attributes(
    rng: np.random.Generator, position: str, quality: float, age: int
) -> dict[str, int]:
    means = np.array(_MEANS[position], dtype=float)
    values = means + rng.normal(0.0, 6.5, len(means))
    values[:-1] += quality  # club quality lifts everything but goalkeeping...
    if position == "GK":
        values[-1] += quality  # ...unless this is a goalkeeper
    if age < 21:
        values -= 4.0
    elif age > 31:
        values[:3] -= 2.0 * (age - 31)  # pace, acceleration, stamina fade first
    return {name: int(np.clip(round(v), 1, 99)) for name, v in zip(ATTRIBUTES, values, strict=True)}


def _age(rng: np.random.Generator) -> int:
    return int(np.clip(round(rng.normal(25.5, 4.0)), 17, 36))


def _foot(rng: np.random.Generator, position: str) -> str:
    left = 0.45 if position in {"LB", "LW"} else 0.18
    draw = rng.random()
    return "both" if draw < 0.03 else ("left" if draw < 0.03 + left else "right")


def generate_squad(
    rng: np.random.Generator, club: str, quality: float, taken_names: set[str]
) -> list[PlayerSpec]:
    """Generate the 25 players of ``club`` (demo clubs follow their template)."""
    template = DEMO_TEMPLATES.get(club)
    if template is None:
        positions = [pos for pos, count in SQUAD_SHAPE for _ in range(count)]
        shirts = _assign_numbers(rng, positions)
        stars: dict[int, Star] = {}
        boosts: dict[int, dict[str, int]] = {}
    else:
        shirts = list(template.squad)
        positions = list(template.squad.values())
        stars, boosts = template.stars, template.boosts
    players: list[PlayerSpec] = []
    for shirt, position in zip(shirts, positions, strict=True):
        star = stars.get(shirt)
        if star is not None:
            first, last, age, foot = star.first_name, star.last_name, star.age, star.foot
            attrs = dict(zip(ATTRIBUTES, star.attributes, strict=True))
        else:
            age = _age(rng)
            first, last = person_name(rng, taken_names)
            foot = _foot(rng, position)
            attrs = _attributes(rng, position, quality, age)
            attrs.update(boosts.get(shirt, {}))
        players.append(
            PlayerSpec(club, shirt, position, first, last, foot, age, _birth_date(rng, age), attrs)
        )
    return players


def _assign_numbers(rng: np.random.Generator, positions: list[str]) -> list[int]:
    shirts: list[int] = []
    used: set[int] = set()
    seen: dict[str, int] = {}
    for position in positions:
        classic = _CLASSIC_NUMBERS.get(position, ())
        index = seen.get(position, 0)
        seen[position] = index + 1
        if index < len(classic) and classic[index] not in used:
            number = classic[index]
        else:
            free = [n for n in range(12, 41) if n not in used]
            number = free[int(rng.integers(len(free)))]
        used.add(number)
        shirts.append(number)
    return shirts


def select_lineup(
    players: list[PlayerSpec], formation: str
) -> tuple[list[tuple[str, str]], list[str]]:
    """Pick the first XI (role, player id) for ``formation`` and a nine-player bench."""
    template = DEMO_TEMPLATES.get(players[0].club)
    if template is not None:
        club = players[0].club
        lineup = [(role, f"{club}-{shirt}") for role, shirt in template.lineup]
        return lineup, [f"{club}-{shirt}" for shirt in template.bench]
    available = {p.player_id: p for p in players}
    lineup: list[tuple[str, str]] = []
    for role in FORMATIONS[formation]:
        fits = role_fit(role)

        def score(p: PlayerSpec, fits: tuple[str, ...] = fits, role: str = role) -> float:
            rank = fits.index(p.position) if p.position in fits else len(fits) + 2
            return overall(p.attributes, role_kind(role)) - 6.0 * rank

        best = max(sorted(available.values(), key=lambda p: p.shirt), key=score)
        lineup.append((role, best.player_id))
        del available[best.player_id]
    rest = sorted(available.values(), key=lambda p: p.shirt)
    keepers = [p for p in rest if p.position == "GK"]
    outfield = sorted(
        (p for p in rest if p.position != "GK"),
        key=lambda p: -overall(p.attributes, position_kind(p.position)),
    )
    bench = [keepers[0].player_id] + [p.player_id for p in outfield[:8]]
    return lineup, bench
