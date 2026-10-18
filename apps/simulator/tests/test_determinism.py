"""Same seed + same scenario ⇒ identical output (docs/DATA_AND_METRICS.md §2)."""

import gzip

import numpy as np
from sim_helpers import DATA, short_setup

from regista_sim.engine.match import Match
from regista_sim.tracking import read_npz
from regista_sim.writers import write_match

FILES = (
    "metadata.json",
    "events.jsonl",
    "events.jsonl.gz",
    "ground_truth.json",
    "summary.json",
    "tracking.npz",
    "tracking.jsonl.gz",
)


def _write(league, seed: int, folder) -> None:
    match = Match(league, short_setup(seed))
    match.run()
    write_match(folder, match, "free-play")


def test_same_seed_writes_identical_files(league, short_match, tmp_path):
    again, other = tmp_path / "again", tmp_path / "other"
    _write(league, 5, again)  # the session's short match is seed 5 too
    for name in FILES:
        assert (again / name).read_bytes() == (short_match.folder / name).read_bytes(), name
    _write(league, 6, other)
    assert (again / "events.jsonl").read_bytes() != (other / "events.jsonl").read_bytes()


def test_generated_golden_equals_the_committed_dataset(golden):
    """The committed data/golden is what the code produces for seed 7 (content, not zip bytes)."""
    committed = DATA / "golden"
    for name in ("metadata.json", "ground_truth.json", "summary.json"):
        assert (committed / name).read_bytes() == (golden.folder / name).read_bytes(), name
    with gzip.open(committed / "events.jsonl.gz", "rb") as handle:
        assert handle.read() == (golden.folder / "events.jsonl").read_bytes()
    ours, theirs = golden.tracking, read_npz(committed / "tracking.npz")
    assert ours.video_start_ms == theirs.video_start_ms
    for a, b in zip(ours.periods, theirs.periods, strict=True):
        assert np.array_equal(a.pos_cm, b.pos_cm)
        assert np.array_equal(a.ball_cm, b.ball_cm)
        assert a.changes == b.changes
