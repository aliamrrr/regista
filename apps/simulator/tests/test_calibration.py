"""Calibration (docs/DATA_AND_METRICS.md §7): a small events-only sample here; the 40-match run is
the CLI command (``regista-sim calibrate``) whose committed output is checked too."""

import json
import math

from sim_helpers import DATA

from regista_sim.calibrate import chaos_baselines, chaos_index_stats, summarize
from regista_sim.chaos import CHAOS_COMPONENTS, chaos_index
from regista_sim.metrics import RANGES


def test_sample_metrics_are_plausible(calibration_sample):
    """Two matches are noisy: each mean must sit within its range widened by half its width."""
    summary = summarize(calibration_sample)
    for key, (label, low, high, _) in RANGES.items():
        mean = summary[key]["mean"]
        slack = 0.5 * (high - low)
        assert math.isfinite(mean), label
        assert low - slack <= mean <= high + slack, (label, mean)


def test_chaos_baselines_cover_every_component(calibration_sample):
    baselines = chaos_baselines(calibration_sample)
    assert set(baselines) == set(CHAOS_COMPONENTS)
    assert all(v["std"] > 0 for v in baselines.values())


def test_chaos_index_is_standardised_on_free_play(calibration_sample):
    """By construction free play averages 50 on the index, 15 points per standard deviation."""
    components = chaos_baselines(calibration_sample)
    stats = chaos_index_stats(calibration_sample, components)
    base = {"chaos_components": components, "chaos_index": stats}
    values = [chaos_index(w, base) for s in calibration_sample for w in s["chaos"]]
    assert abs(sum(values) / len(values) - 50) < 1.5  # clipping at 0/100 moves it a little
    assert stats["sum_std"] > 0
    assert set(stats["label_share"]) <= {"control", "contested", "chaos"}


def test_committed_calibration_passes():
    baselines = json.loads((DATA / "calibration" / "baselines.json").read_text(encoding="utf-8"))
    assert baselines["matches"] >= 40
    assert baselines["pass"]["ok"] is True
    assert baselines["pass"]["share"] >= 0.9
    assert set(baselines["metrics"]) == set(RANGES)
    assert set(baselines["chaos_components"]) == set(CHAOS_COMPONENTS)
    assert baselines["chaos_index"]["sum_std"] > 0
    report = (DATA / "calibration" / "report.md").read_text(encoding="utf-8")
    for key in RANGES:
        assert (DATA / "calibration" / f"hist_{key}.png").exists()
        assert f"hist_{key}.png" in report
