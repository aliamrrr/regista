"""Match folder writers (docs/DATA_AND_METRICS.md §6).

``metadata.json``, ``events.jsonl``, ``tracking.npz`` (+ ``tracking.jsonl.gz``),
``ground_truth.json`` (true probabilities, beat timings, true scorers) and ``summary.json``.
"""

from pathlib import Path
from typing import Any

from regista_sim import __version__
from regista_sim.engine.clock import minute_label
from regista_sim.engine.match import Match
from regista_sim.engine.models import PASS_ANCHORS, PASS_COEF, XG_ANCHORS, XG_COEF
from regista_sim.jsonio import write_jsonl, write_jsonl_gz_copy, write_pretty
from regista_sim.metrics import team_metrics
from regista_sim.physical import players_physical
from regista_sim.tracking import JSONL_NAME, NPZ_NAME, Tracking, write_jsonl_gz, write_npz

EVENTS_GZ = "events.jsonl.gz"  # the committed form (events.jsonl itself is over 1 MB)
PITCH = {
    "length_m": 105.0,
    "width_m": 68.0,
    "origin": "top-left corner of the broadcast view",
    "x": "0 → 105 along the length",
    "y": "0 → 68 across",
}
TIME = {
    "clock_ms": "period clock: 0 at each period's kick-off",
    "video_ts_ms": "broadcast timeline: 0 at kick-off, continuous through stoppage time and the "
    "half-time break",
    "wall_ts": "UTC ISO 8601: kick-off time + video_ts_ms",
    "minute": "45 × (period − 1) + clock_ms // 60000, shown as 45+n′ / 90+n′ in stoppage time",
    "tracking_frame": "clock_ms / 100 within the period (10 Hz)",
}
UNITS = {
    "distance": "m",
    "positions": "m (events 0.1 m, tracking 0.01 m)",
    "time": "ms",
    "speed_shown_to_fans": "km/h (computed by analytics, never in the feed)",
}


def tracking_of(m: Match) -> Tracking:
    """The match's tracking, ready to write."""
    p1 = m.clock.period_lengths_ms[0]
    return Tracking(
        match_id=m.setup.match_id,
        periods=m.recorder.periods,
        video_start_ms=[0, p1 + m.clock.half_time_break_ms],
    )


def build_metadata(m: Match, scenario: str) -> dict[str, Any]:
    """Contents of ``metadata.json``."""
    payload = m.metadata_payload()
    lengths = m.clock.period_lengths_ms
    return {
        "schema": "regista.metadata.v1",
        "match_id": m.setup.match_id,
        "competition": m.league.name,
        "season": m.league.season,
        "matchweek": m.setup.matchweek,
        "date": m.setup.kickoff.date().isoformat(),
        "kickoff_wall_ts": m.clock.wall_ts(0),
        "venue": payload["venue"],
        "referee": payload["referee"],
        "weather": payload["weather"],
        "teams": payload["teams"],
        "attacking_directions": payload["attacking_directions"],
        "periods": [
            {
                "period": 1,
                "added_time_min": m.added_time[0],
                "length_ms": lengths[0],
                "video_start_ms": 0,
            },
            {
                "period": 2,
                "added_time_min": m.added_time[1],
                "length_ms": lengths[1],
                "video_start_ms": lengths[0] + m.clock.half_time_break_ms,
            },
        ],
        "half_time_break_ms": m.clock.half_time_break_ms,
        "final_score": {"home": m.teams[0].score, "away": m.teams[1].score},
        "pitch": PITCH,
        "time": TIME,
        "units": UNITS,
        "schemas": {"events": "regista.event.v1", "tracking": "regista.tracking.v1"},
        "files": {
            "events": "events.jsonl",
            "events_gz": EVENTS_GZ,
            "tracking": NPZ_NAME,
            "tracking_jsonl": JSONL_NAME,
            "ground_truth": "ground_truth.json",
            "summary": "summary.json",
        },
        "generator": {
            "name": "regista-sim",
            "version": __version__,
            "seed": m.setup.seed,
            "scenario": scenario,
        },
        "licence": "CC BY 4.0",
        "synthetic": True,
    }


def build_ground_truth(m: Match, scenario: str) -> dict[str, Any]:
    """Contents of ``ground_truth.json`` (never part of the live feed)."""
    ids = m.events.ids
    goals = []
    for g in m.goals:
        goals.append(
            {
                "minute": minute_label(g["period"], g["clock_ms"]),
                "team": g["team"],
                "credited_player": g["credited"],
                "true_scorer": g["shooter"],
                "event_id": ids[g["ref"].index],
            }
        )
    return {
        "schema": "regista.ground_truth.v1",
        "match_id": m.setup.match_id,
        "seed": m.setup.seed,
        "scenario": scenario,
        "note": "True probabilities come from the simulator's own outcome models. Analytics must "
        "estimate them from the feed; they never appear in events.jsonl.",
        "models": {
            "pass_completion": {
                "coefficients": PASS_COEF,
                "anchors": {k: {"features": vars(f), "p": p} for k, (f, p) in PASS_ANCHORS.items()},
            },
            "xg": {
                "coefficients": XG_COEF,
                "anchors": {k: {"features": vars(f), "p": p} for k, (f, p) in XG_ANCHORS.items()},
                "defenders_in_cone": "outfield opponents inside the shot → posts triangle "
                "widened by 1.0 m each side, plus any goal-side "
                "opponent within 2.5 m of the shooter",
            },
        },
        "passes": {
            ids[ref.index]: {
                "p_complete": tr["p_complete"],
                "planned": tr["planned"],
                "outcome": outcome,
            }
            for ref, tr, outcome in m.truth_passes
        },
        "shots": {
            ids[ref.index]: {
                "xg": tr["xg"],
                "p_goal": tr["p_goal"],
                "planned": tr["planned"],
                "outcome": outcome,
                "features": tr["features"],
            }
            for ref, tr, outcome in m.truth_shots
        },
        "goals": goals,
        **m.steer.truth(m),
    }


def build_summary(m: Match) -> dict[str, Any]:
    """Contents of ``summary.json``: result, scorers, cards, subs, team and player stats."""
    feed = m.feed
    shots_xg = {m.events.ids[ref.index]: tr["xg"] for ref, tr, _ in m.truth_shots}
    periods = [(p.pos_cm, p.slot_ids, p.changes) for p in m.recorder.periods]
    keepers = {pid for t in m.teams for pid, pl in t.roster.items() if pl.position == "GK"}
    stats = team_metrics(feed, shots_xg, periods, [p.ball_cm for p in m.recorder.periods], keepers)
    corrected = {
        e["payload"]["target_event_id"]: e["payload"]
        for e in feed
        if e["type"] == "data_correction"
    }
    goals = []
    for e in feed:
        if e["type"] == "shot" and e["payload"]["outcome"] == "goal":
            fix = corrected.get(e["event_id"])
            player = fix["new_value"] if fix and fix["field"] == "player_id" else e["player_id"]
            goals.append(
                {
                    "minute": minute_label(e["period"], e["clock_ms"]),
                    "team": e["team_id"],
                    "player": player,
                    "event_id": e["event_id"],
                }
            )
    half = {
        code: sum(
            1
            for e in feed
            if e["type"] == "shot"
            and e["period"] == 1
            and e["team_id"] == code
            and e["payload"]["outcome"] == "goal"
        )
        for code in (m.teams[0].code, m.teams[1].code)
    }
    physical = players_physical(periods)
    return {
        "schema": "regista.summary.v1",
        "match_id": m.setup.match_id,
        "note": "Simulator summary for dataset users, computed from the feed, ground truth and "
        "tracking. Not part of the live feed; the core recomputes everything itself.",
        "home": m.teams[0].code,
        "away": m.teams[1].code,
        "final_score": {"home": m.teams[0].score, "away": m.teams[1].score},
        "half_time_score": {"home": half[m.teams[0].code], "away": half[m.teams[1].code]},
        "goals": goals,
        "cards": [
            {
                "minute": minute_label(e["period"], e["clock_ms"]),
                "team": e["team_id"],
                "player": e["player_id"],
                "card": e["payload"]["card"],
            }
            for e in feed
            if e["type"] == "foul" and e["payload"]["card"] != "none"
        ],
        "substitutions": [
            {
                "minute": minute_label(e["period"], e["clock_ms"]),
                "team": e["team_id"],
                "out": e["payload"]["player_out"],
                "in": e["payload"]["player_in"],
            }
            for e in feed
            if e["type"] == "substitution"
        ],
        "team_stats": {
            code: {k: None if v is None else round(v, 3) for k, v in values.items()}
            for code, values in stats.items()
        },
        "players": {
            pid: {
                "minutes": round(v.frames / 600, 1),
                "distance_km": round(v.distance_m / 1000, 2),
                "top_speed_kmh": v.top_speed_kmh,
                "sprints": v.sprints,
            }
            for pid, v in physical.items()
        },
    }


def write_match(
    out_dir: Path,
    m: Match,
    scenario: str,
    *,
    tracking_jsonl: bool = True,
    events_only: bool = False,
) -> list[Path]:
    """Write every match file under ``out_dir`` and return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        out_dir / "metadata.json",
        out_dir / "events.jsonl",
        out_dir / "ground_truth.json",
        out_dir / "summary.json",
    ]
    write_pretty(paths[0], build_metadata(m, scenario))
    write_jsonl(paths[1], m.feed)
    paths.append(out_dir / EVENTS_GZ)
    write_jsonl_gz_copy(paths[1], paths[-1])
    write_pretty(paths[2], build_ground_truth(m, scenario))
    write_pretty(paths[3], build_summary(m))
    if not events_only:
        tracking = tracking_of(m)
        write_npz(out_dir / NPZ_NAME, tracking)
        paths.append(out_dir / NPZ_NAME)
        if tracking_jsonl:
            write_jsonl_gz(out_dir / JSONL_NAME, tracking)
            paths.append(out_dir / JSONL_NAME)
    return paths
