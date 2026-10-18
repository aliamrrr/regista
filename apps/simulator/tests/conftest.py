"""Shared fixtures: the league, the golden match, a short free-play match, a calibration sample.

The calibration sample (two unscripted matches) starts in worker processes right after
collection, so it is simulated while this process works on the golden match.
"""

import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sim_helpers import short_setup

from regista_sim.calibrate import simulate_one
from regista_sim.engine.match import Match
from regista_sim.jsonio import read_jsonl
from regista_sim.league import generate_league
from regista_sim.models import League
from regista_sim.scenario import setup_from_scenario
from regista_sim.scenario.director import Director
from regista_sim.scenario.dsl import load_scenario
from regista_sim.tracking import Tracking, load_tracking
from regista_sim.writers import write_match


@dataclass
class Golden:
    """A generated golden match, loaded back from its files."""

    folder: Path
    events: list[dict[str, Any]]
    metadata: dict[str, Any]
    truth: dict[str, Any]
    summary: dict[str, Any]
    tracking: Tracking
    seconds: float

    def event(self, event_id: str) -> dict[str, Any]:
        """The event with ``event_id``."""
        return next(e for e in self.events if e["event_id"] == event_id)

    def beat(self, beat_id: str) -> dict[str, Any]:
        """The ground-truth record of a beat."""
        return next(b for b in self.truth["beats"] if b["id"] == beat_id)


CALIBRATION_MATCHES = 2
_background: dict[str, Any] = {}


def _needs_sample(item: pytest.Item) -> bool:
    return "calibration_sample" in getattr(item, "fixturenames", ())


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Start the calibration sample in the background when a collected test needs it.

    Those tests run last, so the sample is simulated while the rest of the suite runs.
    """
    items.sort(key=_needs_sample)  # stable: everything else keeps its order
    if any(_needs_sample(item) for item in items):
        pool = ProcessPoolExecutor(max_workers=CALIBRATION_MATCHES)
        _background["pool"] = pool
        _background["futures"] = [
            pool.submit(simulate_one, 7, i) for i in range(CALIBRATION_MATCHES)
        ]


def pytest_sessionfinish() -> None:
    """Stop the background workers."""
    if pool := _background.pop("pool", None):
        pool.shutdown(cancel_futures=True)


@pytest.fixture(scope="session")
def calibration_sample() -> list[dict[str, Any]]:
    """Two unscripted matches for seed 7, as ``regista-sim calibrate`` simulates them."""
    if futures := _background.get("futures"):
        return [f.result() for f in futures]
    return [simulate_one(7, i) for i in range(CALIBRATION_MATCHES)]


@dataclass
class Short:
    """A short free-play match, loaded back from its files."""

    folder: Path
    metadata: dict[str, Any]
    tracking: Tracking


@pytest.fixture(scope="session")
def league() -> League:
    """The fictional league for seed 7 (what ``data/league`` holds)."""
    return generate_league(7)


@pytest.fixture(scope="session")
def golden(tmp_path_factory: pytest.TempPathFactory, league: League) -> Golden:
    """The golden match for seed 7, simulated once and written to a temporary folder."""
    folder = tmp_path_factory.mktemp("golden")
    scenario = load_scenario("golden")
    started = time.perf_counter()
    match = Match(league, setup_from_scenario(scenario, league, 7), steer=Director(scenario))
    match.run()
    write_match(folder, match, scenario.name, tracking_jsonl=False)
    seconds = time.perf_counter() - started
    return Golden(
        folder=folder,
        events=read_jsonl(folder / "events.jsonl"),
        metadata=json.loads((folder / "metadata.json").read_text(encoding="utf-8")),
        truth=json.loads((folder / "ground_truth.json").read_text(encoding="utf-8")),
        summary=json.loads((folder / "summary.json").read_text(encoding="utf-8")),
        tracking=load_tracking(folder),
        seconds=seconds,
    )


@pytest.fixture(scope="session")
def short_match(tmp_path_factory: pytest.TempPathFactory, league: League) -> Short:
    """Two 3-minute periods of free play (seed 5), written exactly like a real match."""
    folder = tmp_path_factory.mktemp("short")
    match = Match(league, short_setup(5))
    match.run()
    write_match(folder, match, "free-play")
    return Short(
        folder=folder,
        metadata=json.loads((folder / "metadata.json").read_text(encoding="utf-8")),
        tracking=load_tracking(folder),
    )
