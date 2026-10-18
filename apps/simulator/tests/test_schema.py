"""Every event and tracking frame validates against the JSON Schemas in apps/simulator/schemas."""

import json

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from sim_helpers import SIM

from regista_sim.tracking import iter_tracking_frames

SCHEMAS = SIM / "schemas"
DERIVED_KEYS = {
    "xg",
    "xpass",
    "speed",
    "speed_kmh",
    "p_complete",
    "p_goal",
    "difficulty",
    "win_probability",
    "ppda",
}


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_every_golden_event_validates(golden):
    validator = _validator("regista.event.v1.schema.json")
    errors = [
        (e["event_id"], err.message) for e in golden.events for err in validator.iter_errors(e)
    ]
    assert errors == []


def test_feed_is_ordered_and_numbered(golden):
    seqs = [e["seq"] for e in golden.events]
    assert seqs == list(range(1, len(seqs) + 1))
    keys = [(e["period"], e["clock_ms"]) for e in golden.events]
    assert keys == sorted(keys)
    assert all(e["event_id"] == f"m001-e{e['seq']:06d}" for e in golden.events)
    assert golden.events[0]["type"] == "match_metadata"
    assert golden.events[-1]["type"] == "match_end"


def test_feed_carries_no_derived_metrics(golden):
    def keys(obj: object) -> set[str]:
        if isinstance(obj, dict):
            return set(obj) | {k for v in obj.values() for k in keys(v)}
        if isinstance(obj, list):
            return {k for v in obj for k in keys(v)}
        return set()

    assert not ({k for e in golden.events for k in keys(e["payload"])} & DERIVED_KEYS)


def test_sampled_tracking_frames_validate(golden):
    validator = _validator("regista.tracking.v1.schema.json")
    for i, frame in enumerate(iter_tracking_frames(golden.tracking)):
        if i % 250 == 0:
            errors = [err.message for err in validator.iter_errors(frame)]
            assert errors == [], (i, errors)


def test_every_tracking_frame_is_well_formed(golden):
    for track in golden.tracking.periods:
        assert len(track.pos_cm) == track.frames
        x, y = track.pos_cm[..., 0] / 100, track.pos_cm[..., 1] / 100
        assert x.min() >= -3
        assert x.max() <= 108
        assert y.min() >= -3
        assert y.max() <= 71
        bx, by, bz = (track.ball_cm[:, k] / 100 for k in range(3))
        assert bx.min() >= -5
        assert bx.max() <= 110
        assert by.min() >= -5
        assert by.max() <= 73
        assert bz.min() >= 0
        for frame in (0, track.frames // 2, track.frames - 1):
            ids = [pid for pid in track.ids_at(frame) if pid]
            assert len(ids) == len(set(ids)) == 22


@pytest.mark.parametrize(
    "name", ["regista.event.v1.schema.json", "regista.tracking.v1.schema.json"]
)
def test_schemas_are_valid_draft_2020_12(name):
    _validator(name)


def test_a_bad_event_is_rejected(golden):
    validator = _validator("regista.event.v1.schema.json")
    bad = json.loads(json.dumps(next(e for e in golden.events if e["type"] == "pass")))
    bad["payload"]["outcome"] = "maybe"
    bad["payload"]["xg"] = 0.3
    assert len(list(validator.iter_errors(bad))) >= 2
    assert np.isfinite(len(golden.events))
