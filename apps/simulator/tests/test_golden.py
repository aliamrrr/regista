"""Every beat of the golden match (docs/DATA_AND_METRICS.md §3) at the right minute, with the
right players, and close to its targets where physics alone decides the number.

Model-dependent targets (win probability, PPDA values) are measured and tuned in Phase 2; here
we check their ingredients (the pressure shift's direction, the 88' chance's true xG). The chaos
targets use the §8 index exactly as defined, scaled by the committed calibration baselines.
"""

import json
import math

import numpy as np
import pytest
from sim_helpers import (
    DATA,
    distance_until,
    lines_broken,
    opponents_at,
    pass_difficulty,
    possession_share,
    pressing,
    speed_series,
    team_direction,
)

from regista_sim.chaos import WINDOW_MS, chaos_index, chaos_series
from regista_sim.engine.clock import minute_label
from regista_sim.physical import release_speed_kmh

BEATS = {  # id → (minute, team, key player)
    "goal_hmr_14": ("14′", "HMR", "HMR-11"),
    "valdane_shot_23": ("23′", "HMR", "HMR-9"),
    "sorvali_record_31": ("31′", "HMR", "HMR-7"),
    "valdane_shot_40": ("40′", "HMR", "HMR-9"),
    "valdane_shot_49": ("49′", "HMR", "HMR-9"),
    "goal_kba_63": ("63′", "KBA", "KBA-7"),
    "goal_hmr_67": ("67′", "HMR", "HMR-9"),
    "chance_kba_88": ("88′", "KBA", "KBA-19"),
}


def _label(event: dict) -> str:
    return minute_label(event["period"], event["clock_ms"])


def test_golden_match_generates_in_under_60_seconds(golden):
    assert golden.seconds < 60


@pytest.mark.parametrize("beat_id", sorted(BEATS))
def test_beat_key_action_at_its_minute(golden, beat_id):
    minute, team, player = BEATS[beat_id]
    beat = golden.beat(beat_id)
    assert not beat["failed"]
    shot = golden.event(beat["event_ids"]["shot"])
    assert _label(shot) == minute
    assert shot["team_id"] == team
    shooter = shot["player_id"] if beat_id != "goal_kba_63" else "KBA-7"
    assert shooter == player


def test_scoreline_and_scorers(golden):
    goals = [
        (_label(e), e["team_id"], e["player_id"])
        for e in golden.events
        if e["type"] == "shot" and e["payload"]["outcome"] == "goal"
    ]
    assert goals == [("14′", "HMR", "HMR-11"), ("63′", "KBA", "KBA-11"), ("67′", "HMR", "HMR-9")]
    scores = [
        (e["payload"]["home"], e["payload"]["away"])
        for e in golden.events
        if e["type"] == "score_update"
    ]
    assert scores == [(1, 0), (1, 1), (2, 1)]
    assert golden.metadata["final_score"] == {"home": 2, "away": 1}
    assert golden.summary["half_time_score"] == {"home": 1, "away": 0}


def test_first_goal_comes_from_a_cutback_by_number_8(golden):
    beat = golden.beat("goal_hmr_14")
    cutback = golden.event(beat["event_ids"]["pass_2"])
    assert (cutback["player_id"], cutback["payload"]["recipient_id"]) == ("HMR-8", "HMR-11")
    assert cutback["payload"]["pass_type"] == "cutback"
    assert golden.truth["shots"][beat["event_ids"]["shot"]]["features"]["assist"] == "cutback"


def test_half_and_full_time(golden):
    ends = [_label(e) for e in golden.events if e["type"] == "period_end"]
    assert ends == ["45+2′", "90+4′"]
    assert [p["added_time_min"] for p in golden.metadata["periods"]] == [2, 4]


def test_kestrel_bay_double_substitution_at_52(golden):
    subs = [
        (_label(e), e["payload"]["player_out"], e["payload"]["player_in"])
        for e in golden.events
        if e["type"] == "substitution" and e["team_id"] == "KBA"
    ]
    assert ("52′", "KBA-8", "KBA-15") in subs
    assert ("52′", "KBA-9", "KBA-19") in subs


def test_equaliser_first_credited_to_vennholm_then_corrected(golden):
    shot = golden.event(golden.beat("goal_kba_63")["event_ids"]["shot"])
    assert shot["player_id"] == "KBA-11"
    goal = next(g for g in golden.truth["goals"] if g["minute"] == "63′")
    assert (goal["credited_player"], goal["true_scorer"]) == ("KBA-11", "KBA-7")
    corrections = [e for e in golden.events if e["type"] == "data_correction"]
    assert len(corrections) == 1
    fix = corrections[0]
    assert _label(fix) == "65′"
    assert fix["payload"]["target_event_id"] == shot["event_id"]
    assert (fix["payload"]["field"], fix["payload"]["old_value"], fix["payload"]["new_value"]) == (
        "player_id",
        "KBA-11",
        "KBA-7",
    )
    assert next(g for g in golden.summary["goals"] if g["minute"] == "63′")["player"] == "KBA-7"


def test_equaliser_follows_a_high_turnover(golden):
    shot = golden.event(golden.beat("goal_kba_63")["event_ids"]["shot"])
    regains = [
        e
        for e in golden.events
        if e["team_id"] == "KBA"
        and e["period"] == 2
        and e["type"] in ("interception", "ball_recovery", "tackle")
        and 0 < shot["clock_ms"] - e["clock_ms"] <= 15_000
    ]
    assert regains, "no regain in the 15 s before the goal"
    d = team_direction(golden.metadata, "KBA", 2)
    x = regains[-1]["location"]["x"] if d > 0 else 105 - regains[-1]["location"]["x"]
    assert x >= 52  # in Harrowmere's half (65 m is the §8 "high turnover" line; Phase 2 tunes)


def test_sorvali_sets_the_speed_record(golden):
    shot = golden.event(golden.beat("sorvali_record_31")["event_ids"]["shot"])
    speed = speed_series(golden.tracking, "HMR-7", 1)
    frame = shot["clock_ms"] // 100
    assert np.nanmax(speed[frame - 150 : frame + 1]) == pytest.approx(34.6, abs=0.3)
    series = [
        speed_series(golden.tracking, pid, p) for p in (1, 2) for pid in golden.summary["players"]
    ]
    match_best = max(np.nanmax(v) for v in series if np.isfinite(v).any())  # skip unused periods
    assert match_best == pytest.approx(np.nanmax(speed), abs=1e-9)


def test_quell_to_valdane_targets(golden):
    beat = golden.beat("goal_hmr_67")
    through = golden.event(beat["event_ids"]["pass_1"])
    shot = golden.event(beat["event_ids"]["shot"])
    assert (through["player_id"], through["payload"]["recipient_id"]) == ("HMR-10", "HMR-9")
    start = (through["location"]["x"], through["location"]["y"])
    end = (through["payload"]["end_location"]["x"], through["payload"]["end_location"]["y"])
    assert math.dist(start, end) == pytest.approx(31, abs=2)
    track = golden.tracking.periods[1]
    assert release_speed_kmh(track.ball_cm, through["clock_ms"] // 100) == pytest.approx(62, abs=5)
    assert release_speed_kmh(track.ball_cm, shot["clock_ms"] // 100) == pytest.approx(98, abs=6)
    valdane = speed_series(golden.tracking, "HMR-9", 2)
    window = valdane[through["clock_ms"] // 100 - 40 : shot["clock_ms"] // 100 + 1]
    assert np.nanmax(window) == pytest.approx(32.8, abs=0.5)
    assert golden.truth["shots"][shot["event_id"]]["xg"] == pytest.approx(0.31, abs=0.05)
    opponents = opponents_at(golden.tracking, 2, through["clock_ms"] // 100, "HMR")
    assert lines_broken(opponents, start, end) == 3
    direction = team_direction(golden.metadata, "HMR", 2)
    difficulty, _ = pass_difficulty(opponents, start, end, through["payload"]["height"], direction)
    assert difficulty == pytest.approx(8.7, abs=0.4)


def test_valdane_before_his_fiftieth_goal(golden):
    shot = golden.event(golden.beat("goal_hmr_67")["event_ids"]["shot"])
    shots = [
        e
        for e in golden.events
        if e["type"] == "shot"
        and e["player_id"] == "HMR-9"
        and (e["period"], e["clock_ms"]) <= (shot["period"], shot["clock_ms"])
    ]
    assert len(shots) == 4
    covered = distance_until(golden.tracking, "HMR-9", 2, shot["clock_ms"])
    assert covered / 1000 == pytest.approx(7.6, abs=0.6)


def test_late_big_chance_is_saved(golden):
    beat = golden.beat("chance_kba_88")
    shot = golden.event(beat["event_ids"]["shot"])
    assert shot["payload"]["outcome"] == "saved"
    assert golden.truth["shots"][shot["event_id"]]["xg"] >= 0.4


def test_harrowmere_control_the_first_twenty_minutes(golden):
    assert possession_share(golden.events, "HMR", 1, 0, 20 * 60_000) >= 0.58


def test_kestrel_bay_press_rises_after_the_substitution(golden):
    """Direction and rough size of the 55-60' shift (Phase 2 tunes it to +11 m, PPDA 13.8 → 7.2)."""
    ppda_before, height_before = pressing(
        golden.events, golden.metadata, "KBA", 2, 0, 9 * 60_000
    )  # 45'-54'
    ppda_after, height_after = pressing(
        golden.events, golden.metadata, "KBA", 2, 11 * 60_000, 20 * 60_000
    )  # 56'-65'
    assert height_after > height_before + 5
    assert ppda_after < ppda_before


def _chaos(golden) -> dict[tuple[int, int], float]:
    """Rolling 5-minute chaos index keyed by (period, minute of the period the window ends)."""
    base = json.loads((DATA / "calibration" / "baselines.json").read_text(encoding="utf-8"))
    return {
        (w["period"], (w["from_ms"] + WINDOW_MS) // 60_000): chaos_index(w, base)
        for w in chaos_series(golden.events)
    }


def _mean(chaos: dict[tuple[int, int], float], period: int, first: int, last: int) -> float:
    values = [v for (p, minute), v in chaos.items() if p == period and first <= minute <= last]
    return sum(values) / len(values)


def test_harrowmere_control_is_calm(golden):
    """0-20': Harrowmere's spell sits on the Control side of the index."""
    assert _mean(_chaos(golden), 1, 5, 20) <= 50


def test_pressure_shift_takes_chaos_from_41_to_72(golden):
    """§3: chaos 41 → 72 (±5), before (50'-56') and after (58'-67') the shift detected at 58'."""
    chaos = _chaos(golden)
    assert abs(_mean(chaos, 2, 5, 11) - 41) <= 5
    assert abs(_mean(chaos, 2, 13, 22) - 72) <= 5


def test_kestrel_bay_siege_is_chaos(golden):
    """§3: chaos ≥ 70 for at least 5 minutes between 80' and full time (sampled each minute)."""
    chaos = _chaos(golden)
    longest = run = 0
    for minute in range(35, 51):  # 80' to 95' of the match
        run = run + 1 if chaos.get((2, minute), 0.0) >= 70 else 0
        longest = max(longest, run)
    assert longest >= 5
