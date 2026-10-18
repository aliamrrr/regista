"""Career histories and last-ten match logs (docs/DATA_AND_METRICS.md §1).

The Archivist reads these for milestones ("50th career goal") and records ("fastest sprint of
the season"). Two story constraints are enforced for the golden match: Iker Valdane has exactly
49 career goals before it, and Kian Sorvali's 34.1 km/h is the league's best sprint of the
season so far, so his 34.6 km/h at 31′ is a new record.
"""

import numpy as np

from regista_sim.models import (
    Career,
    CareerTotals,
    Fixture,
    MatchLog,
    MatchLogEntry,
    SeasonRecord,
)
from regista_sim.squads import PlayerSpec

CURRENT_SEASON = "2026-27"
PREVIOUS_SEASON_TAIL = (("2026-05-16", 37), ("2026-05-24", 38))  # 2025-26 matchweeks 37–38
VALDANE_ID, VALDANE_GOALS = "HMR-9", 49
SORVALI_ID, SORVALI_SEASON_BEST = "HMR-7", 34.1
SEASON_BEST_CAP = 33.9  # everyone else this season, so Sorvali holds the season record
CAREER_SPEED_CAP = 34.4  # nobody has ever reached the 34.6 km/h of the golden match

_GOAL_RATE = {
    "GK": 0.0,
    "RB": 0.03,
    "LB": 0.03,
    "CB": 0.045,
    "DM": 0.05,
    "CM": 0.09,
    "AM": 0.22,
    "RW": 0.26,
    "LW": 0.26,
    "ST": 0.42,
}
_ASSIST_RATE = {
    "GK": 0.004,
    "RB": 0.08,
    "LB": 0.08,
    "CB": 0.02,
    "DM": 0.05,
    "CM": 0.1,
    "AM": 0.24,
    "RW": 0.22,
    "LW": 0.22,
    "ST": 0.12,
}
_CLEAN_SHEET_POSITIONS = {"GK", "RB", "LB", "CB"}


def vmax_kmh(pace: int, age: int) -> float:
    """Return a player's physical top speed (km/h) from ``pace`` and age."""
    return 26.5 + 0.09 * pace - 0.15 * max(0, age - 30)


def _season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _minutes(rng: np.random.Generator, status: str) -> int:
    draw = rng.random()
    if status == "starter":
        return 90 if draw < 0.74 else (int(rng.integers(55, 90)) if draw < 0.9 else 0)
    if status == "bench":
        return 0 if draw < 0.5 else (int(rng.integers(8, 36)) if draw < 0.95 else 90)
    return 0 if draw < 0.92 else int(rng.integers(1, 25))


def _rates(p: PlayerSpec) -> tuple[float, float]:
    attack = (p.attributes["finishing"] - 60) / 60
    create = (p.attributes["passing"] + p.attributes["vision"] - 120) / 120
    return (
        _GOAL_RATE[p.position] * float(np.exp(attack)),
        _ASSIST_RATE[p.position] * float(np.exp(create)),
    )


def _match_speed(rng: np.random.Generator, p: PlayerSpec, minutes: int, cap: float) -> float | None:
    if minutes == 0:
        return None
    drop = rng.uniform(0.4, 3.0) * (1.0 if minutes >= 45 else 1.35)
    return round(min(vmax_kmh(p.attributes["pace"], p.age) - drop, cap), 1)


def _log(
    rng: np.random.Generator,
    p: PlayerSpec,
    status: str,
    schedule: list[tuple[str, str, int, str, str]],
) -> list[MatchLogEntry]:
    goal_rate, assist_rate = _rates(p)
    entries = []
    for day, season, week, opponent, venue in schedule:
        minutes = _minutes(rng, status)
        entries.append(
            MatchLogEntry(
                date=day,
                season=season,
                matchweek=week,
                opponent=opponent,
                venue=venue,
                minutes=minutes,
                goals=int(rng.poisson(goal_rate * minutes / 90)),
                assists=int(rng.poisson(assist_rate * minutes / 90)),
                top_speed_kmh=_match_speed(rng, p, minutes, SEASON_BEST_CAP),
            )
        )
    return entries


def _past_seasons(
    rng: np.random.Generator, p: PlayerSpec, status: str, clubs: list[str]
) -> list[SeasonRecord]:
    goal_rate, assist_rate = _rates(p)
    first_year = 2026 - max(0, p.age - 18)
    records = []
    for year in range(first_year, 2026):
        age_then = p.age - (2026 - year)
        if age_then < 21:
            apps = int(rng.integers(0, 14))
        else:
            low, high = {"starter": (22, 37), "bench": (8, 26)}.get(status, (0, 15))
            apps = int(rng.integers(low, high))
        recent = year >= 2023 and rng.random() < 0.8
        club = p.club if recent else clubs[int(rng.integers(len(clubs)))]
        speed_drop = float(rng.uniform(0.3, 2.0))
        top = round(min(vmax_kmh(p.attributes["pace"], age_then) - speed_drop, CAREER_SPEED_CAP), 1)
        records.append(
            SeasonRecord(
                season=_season_label(year),
                club=club,
                appearances=apps,
                goals=int(rng.poisson(goal_rate * apps * 0.85)),
                assists=int(rng.poisson(assist_rate * apps * 0.85)),
                clean_sheets=int(rng.binomial(apps, 0.3))
                if p.position in _CLEAN_SHEET_POSITIONS
                else 0,
                top_speed_kmh=top if apps else None,
            )
        )
    return records


def _fix_goal_total(seasons: list[SeasonRecord], target: int, floor_last: int) -> None:
    """Rescale past seasons' goals (largest remainder) so all seasons sum to ``target``."""
    past, current = seasons[:-1], seasons[-1]
    want = target - current.goals
    weights = np.array([max(s.goals, 0.5) * max(s.appearances, 1) for s in past], dtype=float)
    raw = want * weights / weights.sum()
    goals = np.floor(raw).astype(int)
    for index in np.argsort(-(raw - goals), kind="stable")[: want - int(goals.sum())]:
        goals[index] += 1
    if goals[-1] < floor_last:  # keep the 2025-26 tail matches' goals inside 2025-26
        surplus = floor_last - goals[-1]
        goals[-1] = floor_last
        for index in np.argsort(-goals[:-1], kind="stable")[:surplus]:
            goals[index] -= 1
    for record, value in zip(past, goals, strict=True):
        record.goals = int(value)


def build_careers(
    seed_rng: np.random.Generator,
    players: list[PlayerSpec],
    statuses: dict[str, str],
    fixtures: list[Fixture],
    previous_opponents: dict[str, list[str]],
) -> tuple[list[Career], list[MatchLog]]:
    """Return career histories and last-ten logs for every player (oldest match first)."""
    clubs = sorted({p.club for p in players})
    careers: list[Career] = []
    logs: list[MatchLog] = []
    for p in players:
        rng = np.random.default_rng(seed_rng.integers(2**63))
        status = statuses.get(p.player_id, "reserve")
        schedule = [
            (day, "2025-26", week, previous_opponents[p.club][i], "H" if i == 0 else "A")
            for i, (day, week) in enumerate(PREVIOUS_SEASON_TAIL)
        ]
        for f in fixtures:
            if f.matchweek < 9 and p.club in (f.home, f.away):
                home = f.home == p.club
                schedule.append(
                    (
                        f.date,
                        CURRENT_SEASON,
                        f.matchweek,
                        f.away if home else f.home,
                        "H" if home else "A",
                    )
                )
        matches = _log(rng, p, status, schedule)
        if p.player_id == SORVALI_ID:
            this_season = matches[2:]
            if not any(m.minutes for m in this_season):
                this_season[-1].minutes = 90
            best = max((m for m in this_season if m.minutes), key=lambda m: m.top_speed_kmh or 0.0)
            best.top_speed_kmh = SORVALI_SEASON_BEST
        seasons = _past_seasons(rng, p, status, clubs)
        tail = matches[:2]
        if seasons:
            last = seasons[-1]
            last.appearances = max(last.appearances, sum(1 for m in tail if m.minutes))
            last.goals = max(last.goals, sum(m.goals for m in tail))
            last.assists = max(last.assists, sum(m.assists for m in tail))
        played = [m for m in matches[2:] if m.minutes]
        speeds = [m.top_speed_kmh for m in played if m.top_speed_kmh is not None]
        seasons.append(
            SeasonRecord(
                season=CURRENT_SEASON,
                club=p.club,
                appearances=len(played),
                goals=sum(m.goals for m in played),
                assists=sum(m.assists for m in played),
                clean_sheets=int(rng.binomial(len(played), 0.3))
                if p.position in _CLEAN_SHEET_POSITIONS
                else 0,
                top_speed_kmh=max(speeds) if speeds else None,
            )
        )
        if p.player_id == VALDANE_ID:
            _fix_goal_total(seasons, VALDANE_GOALS, sum(m.goals for m in tail))
        bests = [s.top_speed_kmh for s in seasons if s.top_speed_kmh is not None]
        careers.append(
            Career(
                player_id=p.player_id,
                totals=CareerTotals(
                    appearances=sum(s.appearances for s in seasons),
                    goals=sum(s.goals for s in seasons),
                    assists=sum(s.assists for s in seasons),
                    clean_sheets=sum(s.clean_sheets for s in seasons),
                    top_speed_kmh=max(bests) if bests else None,
                ),
                seasons=seasons,
            )
        )
        logs.append(MatchLog(player_id=p.player_id, matches=matches))
    return careers, logs
