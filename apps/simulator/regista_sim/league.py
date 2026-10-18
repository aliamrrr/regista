"""Fictional league generator and I/O (docs/DATA_AND_METRICS.md §1).

``generate_league(seed)`` builds 20 clubs (Harrowmere FC and Kestrel Bay Athletic are fixed),
500 players with attributes, first XIs, a fixture list up to matchweek 9 and career histories.
``write_league`` / ``read_league`` store it as ``data/league/*.json``.
"""

from itertools import combinations
from pathlib import Path

import numpy as np

from regista_sim import __version__
from regista_sim.blocklist import is_blocked
from regista_sim.careers import build_careers
from regista_sim.formations import role_kind
from regista_sim.jsonio import read_json, write_array_lines, write_pretty
from regista_sim.models import (
    Attributes,
    Club,
    Fixture,
    Kit,
    League,
    LineupSlot,
    Player,
    Referee,
    Tactics,
)
from regista_sim.names import CLUB_SUFFIXES, person_name, place_name, venue_name
from regista_sim.rng import stream
from regista_sim.squads import DEMO_TEMPLATES, PlayerSpec, generate_squad, overall, select_lineup

LEAGUE_NAME = "Northwind League"
SEASON = "2026-27"
NEXT_MATCHWEEK = 9
MATCHWEEK_DATES = {
    1: "2026-08-15",
    2: "2026-08-22",
    3: "2026-08-29",
    4: "2026-09-12",
    5: "2026-09-19",
    6: "2026-09-26",
    7: "2026-10-03",
    8: "2026-10-17",
    9: "2026-10-24",
}
N_CLUBS = 20

_FIXED = {
    "HMR": {
        "name": "Harrowmere FC",
        "short": "Harrowmere",
        "venue": "Ashgrove Park",
        "home": ("#ef4f5c", "#ffffff"),
        "away": ("#f4f4f4", "#ef4f5c"),
        "quality": 5.0,
        "dials": {
            "formation": "4-3-3",
            "pressing_intensity": 0.62,
            "defensive_line": 0.6,
            "tempo": 0.55,
            "directness": 0.35,
            "width": 0.65,
        },
    },
    "KBA": {
        "name": "Kestrel Bay Athletic",
        "short": "Kestrel Bay",
        "venue": "Harbour Lane",
        "home": ("#4d86ff", "#ffffff"),
        "away": ("#1b2a4a", "#ffffff"),
        "quality": 3.5,
        "dials": {
            "formation": "4-4-2",
            "pressing_intensity": 0.42,
            "defensive_line": 0.45,
            "tempo": 0.58,
            "directness": 0.55,
            "width": 0.55,
        },
    },
}
_PALETTE = (
    "#d64541",
    "#b03a2e",
    "#7b1e2c",
    "#e67e22",
    "#f2c14e",
    "#ffd23f",
    "#2e7d32",
    "#1b5e20",
    "#0b6e4f",
    "#1f4e9c",
    "#16325c",
    "#5dade2",
    "#2c3e50",
    "#111111",
    "#6d4c41",
    "#8d99ae",
    "#b8860b",
    "#a93226",
    "#145a32",
    "#1a5276",
)
_FORMATION_WEIGHTS = {
    "4-3-3": 0.25,
    "4-2-3-1": 0.25,
    "4-4-2": 0.2,
    "3-5-2": 0.1,
    "3-4-3": 0.1,
    "4-1-4-1": 0.1,
}
_ATTACK_KINDS = {"AM", "W", "WM", "ST", "CM"}
_DEFENCE_KINDS = {"CB", "FB", "WB", "DM"}


def _club_code(stem: str, taken: set[str]) -> str:
    letters = [c for c in stem.upper() if c.isalpha()]
    for a, b in combinations(range(1, len(letters)), 2):
        code = letters[0] + letters[a] + letters[b]
        if code not in taken and not is_blocked(code):
            taken.add(code)
            return code
    msg = f"no free code for {stem!r}"
    raise RuntimeError(msg)


def _generated_club_identities(rng: np.random.Generator) -> list[dict]:
    taken_places: set[str] = {"Harrowmere", "Kestrel Bay"}
    used_heads: set[str] = set()
    taken_codes: set[str] = {"HMR", "KBA"}
    taken_venues: set[str] = {"Ashgrove Park", "Harbour Lane"}
    colours = list(_PALETTE)
    rng.shuffle(colours)
    identities = []
    for index in range(N_CLUBS - len(_FIXED)):
        for _ in range(100):
            stem = place_name(rng, taken_places, used_heads)
            name = f"{stem} {CLUB_SUFFIXES[int(rng.integers(len(CLUB_SUFFIXES)))]}"
            if not is_blocked(name):
                break
        primary = colours[index % len(colours)]
        secondary = "#ffffff" if primary not in {"#ffd23f", "#f2c14e"} else "#111111"
        away_primary = colours[(index + 7) % len(colours)]
        identities.append(
            {
                "code": _club_code(stem, taken_codes),
                "name": name,
                "short": stem,
                "venue": venue_name(rng, taken_venues),
                "home": (primary, secondary),
                "away": (away_primary, "#ffffff" if away_primary != "#ffffff" else "#111111"),
                "quality": float(np.clip(rng.normal(0.0, 2.5), -5.5, 5.5)),
                "dials": {
                    "formation": str(
                        rng.choice(list(_FORMATION_WEIGHTS), p=list(_FORMATION_WEIGHTS.values()))
                    ),
                    **{
                        k: round(float(rng.uniform(0.25, 0.8)), 2)
                        for k in (
                            "pressing_intensity",
                            "defensive_line",
                            "tempo",
                            "directness",
                            "width",
                        )
                    },
                },
            }
        )
    return identities


def _ratings(players: dict[str, PlayerSpec], lineup: list[tuple[str, str]]) -> tuple[float, float]:
    attack, defence = [], []
    for role, pid in lineup:
        kind = role_kind(role)
        rating = overall(players[pid].attributes, kind)
        if kind in _ATTACK_KINDS:
            attack.append(rating)
        elif kind in _DEFENCE_KINDS:
            defence.append(rating)
        else:  # the goalkeeper counts double in the defence rating
            defence += [rating, rating]
    return round(float(np.mean(attack)), 1), round(float(np.mean(defence)), 1)


def _round_robin(codes: list[str]) -> list[list[tuple[str, str]]]:
    teams = list(codes)
    rounds = []
    for r in range(len(teams) - 1):
        pairs = []
        for i in range(len(teams) // 2):
            a, b = teams[i], teams[-1 - i]
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds


def _fixtures(rng: np.random.Generator, codes: list[str]) -> list[Fixture]:
    order = list(codes)
    rng.shuffle(order)
    rounds = _round_robin(order)
    target = next(i for i, pairs in enumerate(rounds) if {"HMR", "KBA"} in map(set, pairs))
    rounds[target], rounds[NEXT_MATCHWEEK - 1] = rounds[NEXT_MATCHWEEK - 1], rounds[target]
    fixtures = []
    for week in range(1, NEXT_MATCHWEEK + 1):
        for home, away in rounds[week - 1]:
            if {home, away} == {"HMR", "KBA"}:
                home, away = "HMR", "KBA"
            fixtures.append(
                Fixture(matchweek=week, date=MATCHWEEK_DATES[week], home=home, away=away)
            )
    return fixtures


def generate_league(seed: int) -> League:
    """Generate the whole fictional league deterministically from ``seed``."""
    identities = [{"code": code, **spec} for code, spec in _FIXED.items()]
    identities += _generated_club_identities(stream(seed, "league", "clubs"))
    taken_names: set[str] = set()
    for template in DEMO_TEMPLATES.values():
        for star in template.stars.values():
            taken_names.update((f"{star.first_name} {star.last_name}", star.last_name))
    clubs: list[Club] = []
    specs: list[PlayerSpec] = []
    statuses: dict[str, str] = {}
    for ident in identities:
        code = ident["code"]
        squad = generate_squad(
            stream(seed, "league", "squad", code), code, ident["quality"], taken_names
        )
        by_id = {p.player_id: p for p in squad}
        formation = ident["dials"]["formation"]
        lineup, bench = select_lineup(squad, formation)
        statuses.update({pid: "starter" for _, pid in lineup})
        statuses.update(dict.fromkeys(bench, "bench"))
        attack, defence = _ratings(by_id, lineup)
        clubs.append(
            Club(
                code=code,
                name=ident["name"],
                short_name=ident["short"],
                venue=ident["venue"],
                home_kit=Kit(primary=ident["home"][0], secondary=ident["home"][1]),
                away_kit=Kit(primary=ident["away"][0], secondary=ident["away"][1]),
                tactics=Tactics(**ident["dials"], attack_rating=attack, defence_rating=defence),
                squad=[p.player_id for p in sorted(squad, key=lambda p: p.shirt)],
                lineup=[LineupSlot(role=role, player_id=pid) for role, pid in lineup],
                bench=bench,
            )
        )
        specs.extend(sorted(squad, key=lambda p: p.shirt))
    codes = [c.code for c in clubs]
    fixtures = _fixtures(stream(seed, "league", "fixtures"), codes)
    opp_rng = stream(seed, "league", "previous-season")
    previous = {
        c: [str(x) for x in opp_rng.choice([o for o in codes if o != c], 2, replace=False)]
        for c in codes
    }
    careers, logs = build_careers(
        stream(seed, "league", "careers"), specs, statuses, fixtures, previous
    )
    ref_rng = stream(seed, "league", "referees")
    referees = [
        Referee(id=f"REF-{i:02d}", name=" ".join(person_name(ref_rng, taken_names)))
        for i in range(1, 13)
    ]
    players = [
        Player(
            id=p.player_id,
            club=p.club,
            shirt_number=p.shirt,
            first_name=p.first_name,
            last_name=p.last_name,
            name=f"{p.first_name} {p.last_name}",
            position=p.position,
            preferred_foot=p.foot,
            age=p.age,
            birth_date=p.birth_date,
            attributes=Attributes(**p.attributes),
        )
        for p in specs
    ]
    return League(
        name=LEAGUE_NAME,
        season=SEASON,
        seed=seed,
        generator=f"regista-sim {__version__}",
        next_matchweek=NEXT_MATCHWEEK,
        fixtures=fixtures,
        referees=referees,
        clubs=clubs,
        players=players,
        careers=careers,
        match_logs=logs,
    )


def write_league(league: League, out_dir: Path) -> list[Path]:
    """Write ``league`` as five JSON files under ``out_dir`` and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = league.model_dump(
        mode="json", by_alias=True, exclude={"clubs", "players", "careers", "match_logs"}
    )
    paths = {
        name: out_dir / f"{name}.json"
        for name in ("league", "clubs", "players", "careers", "match_logs")
    }
    write_pretty(paths["league"], meta)
    write_pretty(paths["clubs"], [c.model_dump(mode="json") for c in league.clubs])
    write_array_lines(paths["players"], (p.model_dump(mode="json") for p in league.players))
    write_array_lines(paths["careers"], (c.model_dump(mode="json") for c in league.careers))
    write_array_lines(paths["match_logs"], (m.model_dump(mode="json") for m in league.match_logs))
    return list(paths.values())


def read_league(league_dir: Path) -> League:
    """Read a league written by ``write_league``."""
    meta = read_json(league_dir / "league.json")
    return League.model_validate(
        {
            **meta,
            **{
                name: read_json(league_dir / f"{name}.json")
                for name in ("clubs", "players", "careers", "match_logs")
            },
        }
    )


def load_or_generate(league_dir: Path | None, seed: int) -> League:
    """Read the league from ``league_dir`` when it exists, else generate it from ``seed``."""
    if league_dir is not None and (league_dir / "league.json").exists():
        return read_league(league_dir)
    return generate_league(seed)
