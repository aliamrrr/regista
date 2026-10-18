"""Tracking codec, the spec's JSONL export, and the §8 physical formulas."""

import gzip
import json

import numpy as np
import pytest

from regista_sim.physical import release_speed_kmh, smoothed_speed_kmh, sprint_count
from regista_sim.tracking import (
    JSONL_NAME,
    NPZ_NAME,
    iter_frames,
    iter_tracking_frames,
    read_npz,
    write_jsonl_gz,
    write_npz,
)


def test_npz_round_trip_is_exact(short_match):
    again = short_match.folder / "again.npz"
    write_npz(again, short_match.tracking)
    back = read_npz(again)
    assert back.match_id == short_match.tracking.match_id
    assert back.video_start_ms == short_match.tracking.video_start_ms
    for a, b in zip(short_match.tracking.periods, back.periods, strict=True):
        assert np.array_equal(a.pos_cm, b.pos_cm)
        assert np.array_equal(a.ball_cm, b.ball_cm)
        assert a.slot_ids == b.slot_ids
        assert a.changes == b.changes
    assert again.read_bytes() == (short_match.folder / NPZ_NAME).read_bytes()


def test_jsonl_export_matches_the_frames(short_match, tmp_path):
    target = tmp_path / JSONL_NAME
    write_jsonl_gz(target, short_match.tracking)
    with gzip.open(target, "rt", encoding="utf-8") as handle:
        first = [json.loads(next(handle)) for _ in range(3)]
    frames = iter_tracking_frames(short_match.tracking)
    assert first == [next(frames) for _ in range(3)]
    assert first[1]["frame"] == 1
    assert first[1]["clock_ms"] == 100
    assert len(first[0]["players"]) == 22


def test_iter_frames_prefers_npz_and_counts_every_frame(short_match):
    frames = list(iter_frames(short_match.folder))
    assert len(frames) == short_match.tracking.frame_count()
    p2 = [f for f in frames if f["period"] == 2]
    assert p2[0]["frame"] == 0
    assert p2[0]["video_ts_ms"] == short_match.metadata["periods"][1]["video_start_ms"]


def test_smoothed_speed_of_a_steady_run():
    xy = np.column_stack([np.arange(40) * 0.75, np.zeros(40)])  # 7.5 m/s = 27 km/h
    speed = smoothed_speed_kmh(xy)
    assert np.nanmax(speed) == pytest.approx(27.0)
    assert np.isnan(speed[:3]).all()


def test_sprints_need_a_full_second():
    speed = np.zeros(60)
    speed[5:14] = 26.0  # 0.9 s: not a sprint
    speed[20:32] = 26.0  # 1.2 s: one sprint
    speed[40:55] = 30.0  # 1.5 s: another
    assert sprint_count(speed) == 2


def test_release_speed_is_the_peak_over_the_first_0_3_s():
    ball = np.zeros((10, 3), dtype=np.int32)
    ball[1:, 0] = np.cumsum([170, 165, 160, 155, 150, 145, 140, 135, 130])  # cm per frame
    assert release_speed_kmh(ball, 0) == pytest.approx(170 / 100 / 0.1 * 3.6)
