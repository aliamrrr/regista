"""Command-line entry point for ``regista-sim`` (CLAUDE.md "Commands").

regista-sim league generate --seed 7 --out data/league
regista-sim match run --scenario golden --seed 7 --out data/golden
regista-sim calibrate --matches 40 --out data/calibration
regista-sim tracking export data/golden
"""

import argparse
import json
import logging
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from regista_sim import __version__
from regista_sim.calibrate import run_sample, write_outputs
from regista_sim.engine.match import Match
from regista_sim.league import generate_league, load_or_generate, write_league
from regista_sim.scenario import setup_from_scenario
from regista_sim.scenario.director import Director
from regista_sim.scenario.dsl import load_scenario
from regista_sim.tracking import JSONL_NAME, load_tracking, write_jsonl_gz
from regista_sim.writers import write_match

log = logging.getLogger("regista_sim")


class _JsonFormatter(logging.Formatter):
    """One JSON object per log line (structured logs, no ``print``)."""

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` with any ``extra=`` fields."""
        base = logging.makeLogRecord({}).__dict__
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update((k, v) for k, v in vars(record).items() if k not in base and k != "message")
        return json.dumps(payload, default=str, ensure_ascii=False)


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


def build_parser() -> argparse.ArgumentParser:
    """Build the ``regista-sim`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="regista-sim",
        description="Synthetic football league and match engine for REGISTA.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    league = commands.add_parser("league", help="fictional league")
    league_cmd = league.add_subparsers(dest="league_command", required=True, metavar="ACTION")
    generate = league_cmd.add_parser("generate", help="generate the 20-club league")
    generate.add_argument("--seed", type=int, default=7)
    generate.add_argument("--out", type=Path, default=Path("data/league"))

    match = commands.add_parser("match", help="simulate a match")
    match_cmd = match.add_subparsers(dest="match_command", required=True, metavar="ACTION")
    run = match_cmd.add_parser("run", help="run a scenario (events + 10 Hz tracking)")
    run.add_argument("--scenario", default="golden", help="scenario name or YAML path")
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--out", type=Path, default=Path("data/golden"))
    run.add_argument(
        "--league",
        type=Path,
        default=Path("data/league"),
        help="league folder (generated from --seed when missing)",
    )
    run.add_argument("--events-only", action="store_true", help="skip the tracking files")
    run.add_argument(
        "--no-jsonl", action="store_true", help="write tracking.npz only, not tracking.jsonl.gz"
    )

    calibrate = commands.add_parser("calibrate", help="simulate unscripted matches vs §7 ranges")
    calibrate.add_argument("--matches", type=int, default=40)
    calibrate.add_argument("--seed", type=int, default=7)
    calibrate.add_argument("--workers", type=int, default=None)
    calibrate.add_argument("--out", type=Path, default=Path("data/calibration"))

    tracking = commands.add_parser("tracking", help="tracking files")
    tracking_cmd = tracking.add_subparsers(dest="tracking_command", required=True, metavar="ACTION")
    export = tracking_cmd.add_parser("export", help="write tracking.jsonl.gz from tracking.npz")
    export.add_argument("match_dir", type=Path)
    return parser


def _league(args: argparse.Namespace) -> int:

    started = time.perf_counter()
    paths = write_league(generate_league(args.seed), args.out)
    log.info(
        "league written",
        extra={
            "seed": args.seed,
            "files": [str(p) for p in paths],
            "seconds": round(time.perf_counter() - started, 2),
        },
    )
    return 0


def _match(args: argparse.Namespace) -> int:

    started = time.perf_counter()
    league = load_or_generate(args.league, args.seed)
    scenario = load_scenario(args.scenario)
    match = Match(
        league, setup_from_scenario(scenario, league, args.seed), steer=Director(scenario)
    )
    match.run()
    simulated = time.perf_counter() - started
    paths = write_match(
        args.out,
        match,
        scenario.name,
        tracking_jsonl=not args.no_jsonl,
        events_only=args.events_only,
    )
    log.info(
        "match written",
        extra={
            "scenario": scenario.name,
            "seed": args.seed,
            "score": f"{match.teams[0].code} {match.teams[0].score}-{match.teams[1].score} "
            f"{match.teams[1].code}",
            "events": len(match.feed),
            "files": [str(p) for p in paths],
            "simulate_s": round(simulated, 1),
            "total_s": round(time.perf_counter() - started, 1),
        },
    )
    return 0


def _calibrate(args: argparse.Namespace) -> int:

    started = time.perf_counter()
    samples = run_sample(args.matches, seed=args.seed, workers=args.workers)
    baselines = write_outputs(args.out, samples, args.seed)
    result = baselines["pass"]
    log.info(
        "calibration written",
        extra={
            "matches": args.matches,
            "in_range": f"{result['in_range']}/{result['total']}",
            "ok": result["ok"],
            "out": str(args.out),
            "seconds": round(time.perf_counter() - started, 1),
        },
    )
    return 0 if result["ok"] else 1


def _tracking(args: argparse.Namespace) -> int:

    write_jsonl_gz(args.match_dir / JSONL_NAME, load_tracking(args.match_dir))
    log.info("tracking exported", extra={"file": str(args.match_dir / JSONL_NAME)})
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with ``argv`` (defaults to ``sys.argv``) and return the exit code."""
    args = build_parser().parse_args(argv)
    _configure_logging()
    handlers = {"league": _league, "match": _match, "calibrate": _calibrate, "tracking": _tracking}
    return handlers[args.command](args)
