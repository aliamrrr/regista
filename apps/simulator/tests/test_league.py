"""The fictional league (docs/DATA_AND_METRICS.md §1)."""

from collections import Counter

from sim_helpers import DATA

from regista_sim.league import generate_league, read_league
from regista_sim.squads import ATTRIBUTES

STARS = {
    "HMR-9": ("Iker Valdane", "ST"),
    "HMR-10": ("Mattis Quell", "AM"),
    "HMR-7": ("Kian Sorvali", "RW"),
    "KBA-7": ("Yanis Belkora", "RW"),
    "KBA-11": ("Oskar Vennholm", "ST"),
}


def test_twenty_clubs_and_five_hundred_players(league):
    assert len(league.clubs) == 20
    assert len(league.players) == 500
    assert len({p.id for p in league.players}) == 500
    for club in league.clubs:
        squad = [p for p in league.players if p.club == club.code]
        assert len(squad) == 25
        assert len({p.shirt_number for p in squad}) == 25
        assert len(club.lineup) == 11
        assert len(club.bench) == 9
        assert set(club.squad) == {p.id for p in squad}


def test_demo_clubs_and_stars(league):
    hmr, kba = league.club("HMR"), league.club("KBA")
    assert (hmr.name, hmr.venue, hmr.home_kit.primary, hmr.home_kit.secondary) == (
        "Harrowmere FC",
        "Ashgrove Park",
        "#ef4f5c",
        "#ffffff",
    )
    assert (kba.name, kba.home_kit.primary, kba.home_kit.secondary) == (
        "Kestrel Bay Athletic",
        "#4d86ff",
        "#ffffff",
    )
    players = league.players_by_id()
    for pid, (name, position) in STARS.items():
        assert (players[pid].name, players[pid].position) == (name, position)
    starters = {s.player_id for c in (hmr, kba) for s in c.lineup}
    assert set(STARS) <= starters
    assert {"KBA-15", "KBA-19"} <= set(kba.bench)


def test_career_story_constraints(league):
    careers = {c.player_id: c for c in league.careers}
    assert careers["HMR-9"].totals.goals == 49  # the 67' goal is his 50th
    season_best = {pid: c.seasons[-1].top_speed_kmh for pid, c in careers.items()}
    assert season_best["HMR-7"] == 34.1
    others = [v for pid, v in season_best.items() if pid != "HMR-7" and v is not None]
    assert max(others) < 34.1  # Sorvali holds the season's fastest sprint before the match
    assert max(c.totals.top_speed_kmh or 0.0 for c in careers.values()) < 34.6


def test_careers_and_logs_are_consistent(league):
    logs = {lg.player_id: lg.matches for lg in league.match_logs}
    for career in league.careers:
        matches = logs[career.player_id]
        assert len(matches) == 10
        current = career.seasons[-1]
        this_season = [m for m in matches if m.season == current.season]
        assert current.goals == sum(m.goals for m in this_season)
        assert current.appearances == sum(1 for m in this_season if m.minutes)
        assert career.totals.goals == sum(s.goals for s in career.seasons)


def test_attributes_and_names(league):
    for player in league.players:
        values = player.attributes.model_dump()
        assert set(values) == set(ATTRIBUTES)
        assert all(1 <= v <= 99 for v in values.values())
    names = Counter(p.name for p in league.players)
    surnames = Counter(p.last_name for p in league.players)
    assert names.most_common(1)[0][1] == 1
    assert surnames.most_common(1)[0][1] == 1


def test_matchweek_nine_is_the_golden_fixture(league):
    week9 = [f for f in league.fixtures if f.matchweek == 9]
    assert len(week9) == 10
    assert any((f.home, f.away, f.date) == ("HMR", "KBA", "2026-10-24") for f in week9)
    for week in range(1, 10):
        teams = [t for f in league.fixtures if f.matchweek == week for t in (f.home, f.away)]
        assert sorted(teams) == sorted(c.code for c in league.clubs)


def test_generation_is_deterministic_and_seeded(league):
    again = generate_league(7)
    assert again.model_dump() == league.model_dump()
    other = generate_league(8)
    assert [p.name for p in other.players] != [p.name for p in league.players]


def test_committed_league_matches_the_generator(league):
    assert read_league(DATA / "league").model_dump() == league.model_dump()
