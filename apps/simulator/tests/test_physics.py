"""Scripted or not, every move obeys the same physics: no teleports, human speeds."""

import numpy as np

from regista_sim.physical import track_segments


def test_players_never_exceed_human_speed_or_teleport(golden):
    for track in golden.tracking.periods:
        segments = track_segments(track.slot_ids, track.changes, track.frames)
        for pid, spans in segments.items():
            for slot, start, end in spans:
                xy = track.pos_cm[start:end, slot].astype(float) / 100
                if len(xy) < 3:
                    continue
                step = np.sqrt((np.diff(xy, axis=0) ** 2).sum(axis=1))
                assert step.max() < 1.05, (pid, float(step.max()))  # < 37.8 km/h, frame to frame


def test_player_accelerations_stay_physical(golden):
    for track in golden.tracking.periods:
        segments = track_segments(track.slot_ids, track.changes, track.frames)
        for slot, start, end in (s for spans in segments.values() for s in spans):
            xy = track.pos_cm[start:end, slot].astype(float) / 100
            if len(xy) < 10:
                continue
            accel = np.sqrt((np.diff(xy, n=2, axis=0) ** 2).sum(axis=1)) / 0.01
            assert np.percentile(accel, 99.9) < 12.0  # m/s², incl. ±2 m/s² of 1 cm rounding


def test_ball_moves_continuously(golden):
    for track in golden.tracking.periods:
        ball = track.ball_cm.astype(float) / 100
        step = np.sqrt((np.diff(ball[:, :2], axis=0) ** 2).sum(axis=1))
        assert step.max() < 4.5  # < 45 m/s: shots top out near 36 m/s


def test_ball_starts_each_period_on_the_centre_spot(golden):
    for track in golden.tracking.periods:
        assert np.allclose(track.ball_cm[0, :2] / 100, (52.5, 34.0), atol=0.01)
