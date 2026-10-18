"""``regista-sim calibrate``: simulate unscripted matches and check §7's plausibility ranges.

Writes ``report.md`` (table + histograms as PNG) and ``baselines.json`` (means and standard
deviations of the §7 metrics, of the control-vs-chaos components the chaos index z-scores
against, and of their weighted sum, which scales the index). Matches run in parallel
processes; each one is fully determined by ``(seed, match index)``, so the result does not
depend on the number of workers.
"""

import logging
import math
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from regista_sim import __version__
from regista_sim.chaos import (
    CHAOS_COMPONENTS,
    INDEX_SCALE,
    WEIGHTS,
    chaos_index,
    chaos_label,
    chaos_windows,
    weighted_sum,
)
from regista_sim.engine.match import Match, MatchSetup
from regista_sim.engine.params import EngineParams
from regista_sim.jsonio import write_pretty
from regista_sim.league import generate_league
from regista_sim.metrics import RANGES, team_metrics
from regista_sim.rng import stream

log = logging.getLogger(__name__)
PASS_SHARE = 0.9  # §7: at least 90% of the metrics inside their range


@lru_cache(maxsize=2)
def _league(seed: int) -> Any:
    return generate_league(seed)


def simulate_one(seed: int, index: int, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Simulate unscripted match ``index`` and return its team metrics and chaos windows."""
    league = _league(seed)
    rng = stream(seed, "calibrate", index)
    codes = [c.code for c in league.clubs]
    home, away = (str(c) for c in rng.choice(codes, 2, replace=False))
    setup = MatchSetup(
        match_id=f"c{index:03d}",
        home=home,
        away=away,
        seed=int(rng.integers(2**31)),
        kickoff=datetime(2026, 11, 1, 15, 0, tzinfo=UTC),
    )
    m = Match(league, setup, params=EngineParams(**(overrides or {})))
    feed = m.run()
    shots_xg = {m.events.id_of(ref): truth["xg"] for ref, truth, _ in m.truth_shots}
    periods = [(p.pos_cm, p.slot_ids, p.changes) for p in m.recorder.periods]
    balls = [p.ball_cm for p in m.recorder.periods]
    keepers = {pid for t in m.teams for pid, pl in t.roster.items() if pl.position == "GK"}
    return {
        "match": index,
        "home": home,
        "away": away,
        "teams": team_metrics(feed, shots_xg, periods, balls, keepers),
        "chaos": chaos_windows(feed),
    }


def run_sample(
    matches: int, seed: int = 7, workers: int | None = None, overrides: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Simulate ``matches`` unscripted matches (in parallel when ``workers`` > 1)."""
    workers = max(1, min(workers or os.cpu_count() or 1, matches))
    if workers == 1:
        return [simulate_one(seed, i, overrides) for i in range(matches)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(simulate_one, [seed] * matches, range(matches), [overrides] * matches))


def summarize(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Mean, standard deviation and range check of every metric over team-matches."""
    summary = {}
    for key, (label, low, high, unit) in RANGES.items():
        values = np.array([t[key] for s in samples for t in s["teams"].values()], dtype=float)
        values = values[np.isfinite(values)]
        mean = float(values.mean()) if len(values) else math.nan
        summary[key] = {
            "label": label,
            "low": low,
            "high": high,
            "unit": unit,
            "mean": round(mean, 4),
            "std": round(float(values.std(ddof=1)), 4) if len(values) > 1 else 0.0,
            "n": len(values),
            "in_range": bool(low <= mean <= high),
            "values": values.tolist(),
        }
    return summary


def chaos_baselines(samples: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Mean and standard deviation of each chaos component over all 5-minute windows."""
    windows = [w for s in samples for w in s["chaos"]]
    out = {}
    for key, spec in CHAOS_COMPONENTS.items():
        values = np.array([w[key] for w in windows if w[key] is not None], dtype=float)
        out[key] = {
            "mean": round(float(values.mean()), 4),
            "std": round(float(values.std(ddof=1)), 4),
            "sign": spec["sign"],
            "definition": spec["definition"],
            "windows": len(values),
        }
    return out


def chaos_index_stats(
    samples: list[dict[str, Any]], components: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Mean and standard deviation of the weighted sum, plus the label mix it gives free play."""
    windows = [w for s in samples for w in s["chaos"]]
    sums = np.array([weighted_sum(w, components) for w in windows])
    stats: dict[str, Any] = {
        "weights": WEIGHTS,
        "sum_mean": round(float(sums.mean()), 4),
        "sum_std": round(float(sums.std(ddof=1)), 4),
        "scale": INDEX_SCALE,
        "formula": "chaos = clip(50 + scale × (weighted_sum − sum_mean) / sum_std, 0, 100)",
        "windows": len(windows),
    }
    base = {"chaos_components": components, "chaos_index": stats}
    labels = [chaos_label(chaos_index(w, base)) for w in windows]
    stats["label_share"] = {k: round(labels.count(k) / len(labels), 3) for k in sorted(set(labels))}
    return stats


def _label_mix(share: dict[str, float]) -> str:
    return ", ".join(
        f"{k} {100 * share.get(k, 0.0):.0f}%" for k in ("control", "contested", "chaos")
    )


def _fmt(value: float, unit: str) -> str:
    if unit == "%":
        return f"{100 * value:.1f}%"
    return f"{value:.3f}" if abs(value) < 1 else f"{value:.2f}"  # xG/shot needs 3 decimals


def write_outputs(out_dir: Path, samples: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Write ``report.md``, histogram PNGs and ``baselines.json``; return the summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(samples)
    passed = sum(v["in_range"] for v in summary.values())
    share = passed / len(summary)
    _histograms(out_dir, summary)
    baselines = {
        "schema": "regista.baselines.v1",
        "generator": f"regista-sim {__version__}",
        "seed": seed,
        "matches": len(samples),
        "metrics": {
            k: {f: v[f] for f in ("label", "mean", "std", "low", "high", "unit", "in_range")}
            for k, v in summary.items()
        },
        "chaos_components": (components := chaos_baselines(samples)),
        "chaos_index": chaos_index_stats(samples, components),
        "pass": {
            "in_range": passed,
            "total": len(summary),
            "share": round(share, 3),
            "required": PASS_SHARE,
            "ok": share >= PASS_SHARE,
        },
    }
    write_pretty(out_dir / "baselines.json", baselines)
    rows = [
        f"| {v['label']} | {_fmt(v['low'], v['unit'])} – {_fmt(v['high'], v['unit'])} | "
        f"{_fmt(v['mean'], v['unit'])} | {_fmt(v['std'], v['unit'])} | "
        f"{'✅' if v['in_range'] else '❌'} | ![{k}](hist_{k}.png) |"
        for k, v in summary.items()
    ]
    report = "\n".join(
        [
            "# REGISTA simulator calibration",
            "",
            f"{len(samples)} unscripted matches between random clubs of the fictional league "
            f"(seed {seed}, `regista-sim calibrate --matches {len(samples)}`), compared with the "
            "plausibility ranges of `docs/DATA_AND_METRICS.md` §7. Values are means over "
            f"{2 * len(samples)} team-matches; the histograms show the per-team-match spread.",
            "",
            f"**Result: {passed} / {len(summary)} metrics in range ({100 * share:.0f}%) — "
            f"{'PASS' if share >= PASS_SHARE else 'FAIL'}** (required: ≥ {100 * PASS_SHARE:.0f}%).",
            "",
            "| Metric (per team per match) | Range | Mean | Std | In range | Histogram |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "Notes: xG is the simulator's true goal model (ground truth), not the Phase 2 "
            "analytics model; physical metrics come from 10 Hz tracking with the §8 formulas "
            "(5-frame centred speed average, sprints ≥ 25.2 km/h for ≥ 1 s), normalised to 90 "
            "minutes per player. "
            "`baselines.json` also holds the means and standard deviations of the control-vs-chaos "
            "components over 5-minute windows and of their weighted sum, which scales the chaos "
            "index so free play averages 50 with 15 points per standard deviation (label mix "
            f"in free play: {_label_mix(baselines['chaos_index']['label_share'])}).",
            "",
        ]
    )
    (out_dir / "report.md").write_text(report, encoding="utf-8", newline="\n")
    return baselines


def _histograms(out_dir: Path, summary: dict[str, dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for key, v in summary.items():
        fig, ax = plt.subplots(figsize=(3.6, 2.2), dpi=80)
        values = np.array(v["values"])
        scale = 100.0 if v["unit"] == "%" else 1.0
        ax.hist(values * scale, bins=12, color="#4d86ff", edgecolor="#1b2a4a")
        ax.axvspan(v["low"] * scale, v["high"] * scale, color="#3ecf8e", alpha=0.18)
        ax.axvline(v["mean"] * scale, color="#ef4f5c", linewidth=1.5)
        ax.set_title(v["label"], fontsize=8)
        ax.tick_params(labelsize=7)
        fig.tight_layout()
        fig.savefig(out_dir / f"hist_{key}.png", metadata={"Software": None})
        plt.close(fig)
