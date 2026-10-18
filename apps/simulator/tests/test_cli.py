"""The CLI matches CLAUDE.md "Commands"."""

import gzip
import json

from regista_sim.cli import build_parser, main
from regista_sim.tracking import JSONL_NAME


def test_league_generate_writes_the_league(tmp_path):
    assert main(["league", "generate", "--seed", "7", "--out", str(tmp_path)]) == 0
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["careers.json", "clubs.json", "league.json", "match_logs.json", "players.json"]
    meta = json.loads((tmp_path / "league.json").read_text(encoding="utf-8"))
    assert (meta["schema"], meta["seed"], meta["next_matchweek"]) == ("regista.league.v1", 7, 9)


def test_commands_parse_as_documented():
    parser = build_parser()
    run = parser.parse_args(
        ["match", "run", "--scenario", "golden", "--seed", "7", "--out", "data/golden"]
    )
    assert (run.scenario, run.seed, run.out.as_posix()) == ("golden", 7, "data/golden")
    cal = parser.parse_args(["calibrate", "--matches", "40", "--out", "data/calibration"])
    assert cal.matches == 40


def test_tracking_export(short_match):
    assert main(["tracking", "export", str(short_match.folder)]) == 0
    with gzip.open(short_match.folder / JSONL_NAME, "rt", encoding="utf-8") as handle:
        frame = json.loads(handle.readline())
    assert frame["schema"] == "regista.tracking.v1"
    assert frame["frame"] == 0
