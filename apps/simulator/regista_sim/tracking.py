"""Tracking files (docs/DATA_AND_METRICS.md §5).

``tracking.npz`` is the committed, lossless compact form: integer centimetres, second-order time
deltas, LZMA-compressed (preset 9e) inside a zip with fixed timestamps (byte-stable for a seed).
``tracking.jsonl.gz`` is the spec's interchange form, one ``regista.tracking.v1`` frame per line;
it is derived from the npz (``regista-sim tracking export``) and not committed.
``iter_frames`` yields exactly the same frames from either file.
"""

import gzip
import io
import lzma
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from regista_sim.engine.recorder import PeriodTrack
from regista_sim.jsonio import dumps_compact

TRACKING_SCHEMA = "regista.tracking.v1"
NPZ_FORMAT = "regista.tracking.npz.v1"
NPZ_NAME = "tracking.npz"
JSONL_NAME = "tracking.jsonl.gz"
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


@dataclass
class Tracking:
    """Decoded tracking of one match."""

    match_id: str
    periods: list[PeriodTrack]
    video_start_ms: list[int]  # broadcast timeline position of each period's frame 0

    def frame_count(self) -> int:
        """Total number of frames over all periods."""
        return sum(p.frames for p in self.periods)


def _deltas(values: np.ndarray) -> np.ndarray:
    """Second-order differences along the last axis (exactly invertible with two cumsums)."""
    d1 = np.diff(values, axis=-1, prepend=0)
    return np.diff(d1, axis=-1, prepend=0)


def _undeltas(d2: np.ndarray) -> np.ndarray:
    return np.cumsum(np.cumsum(d2.astype(np.int64), axis=-1), axis=-1)


def _compact(values: np.ndarray) -> np.ndarray:
    small = np.iinfo(np.int16)
    if values.size and (values.min() < small.min or values.max() > small.max):
        return values.astype(np.int32)
    return values.astype(np.int16)


def _write_member(archive: zipfile.ZipFile, name: str, array: np.ndarray) -> None:
    buffer = io.BytesIO()
    np.lib.format.write_array(buffer, np.asarray(array), allow_pickle=False)
    info = zipfile.ZipInfo(f"{name}.npy", date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    archive.writestr(info, buffer.getvalue())


def _packed(values: np.ndarray) -> np.ndarray:
    """An int array as LZMA (preset 9e) bytes in a uint8 array; header = dtype + shape."""
    small = _compact(values)
    header = f"{small.dtype.str}|{','.join(map(str, small.shape))}|".encode()
    blob = lzma.compress(small.tobytes(), preset=9 | lzma.PRESET_EXTREME)
    return np.frombuffer(header + blob, dtype=np.uint8)


def _unpacked(packed: np.ndarray) -> np.ndarray:
    raw = packed.tobytes()
    dtype, shape, blob = raw.split(b"|", 2)
    dims = tuple(int(n) for n in shape.decode().split(",") if n)
    return np.frombuffer(lzma.decompress(blob), dtype=np.dtype(dtype.decode())).reshape(dims)


def write_npz(path: Path, tracking: Tracking) -> None:
    """Write ``tracking`` as a deterministic, LZMA-compressed ``.npz``."""
    pos = np.concatenate([p.pos_cm for p in tracking.periods])  # (F, 22, 2)
    ball = np.concatenate([p.ball_cm for p in tracking.periods])  # (F, 3)
    ids = np.array([[pid or "" for pid in p.slot_ids] for p in tracking.periods], dtype="<U8")
    changes = [
        (i, frame, slot) for i, p in enumerate(tracking.periods) for frame, slot, _ in p.changes
    ]
    change_ids = [pid or "" for p in tracking.periods for _, _, pid in p.changes]
    members = {
        "format": np.array(NPZ_FORMAT),
        "match_id": np.array(tracking.match_id),
        "periods": np.array([p.period for p in tracking.periods], dtype=np.int16),
        "frames": np.array([p.frames for p in tracking.periods], dtype=np.int32),
        "video_start_ms": np.array(tracking.video_start_ms, dtype=np.int64),
        "slot_ids": ids,
        "changes": np.array(changes, dtype=np.int32).reshape(-1, 3),
        "change_ids": np.array(change_ids, dtype="<U8"),
        "pos_d2": _packed(_deltas(np.transpose(pos, (1, 2, 0)))),  # (22, 2, F)
        "ball_d2": _packed(_deltas(ball.T)),  # (3, F)
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, array in members.items():
            _write_member(archive, name, array)


def read_npz(path: Path) -> Tracking:
    """Decode a ``tracking.npz`` written by ``write_npz``."""
    with np.load(path, allow_pickle=False) as data:
        if str(data["format"].item()) != NPZ_FORMAT:
            msg = f"{path}: not a {NPZ_FORMAT} file"
            raise ValueError(msg)
        pos = np.transpose(_undeltas(_unpacked(data["pos_d2"])), (2, 0, 1)).astype(np.int32)
        ball = _undeltas(_unpacked(data["ball_d2"])).T.astype(np.int32)
        frames = data["frames"].tolist()
        periods_no = data["periods"].tolist()
        ids = data["slot_ids"].tolist()
        changes = data["changes"].tolist()
        change_ids = data["change_ids"].tolist()
        match_id = str(data["match_id"].item())
        video = [int(v) for v in data["video_start_ms"]]
    periods, start = [], 0
    for i, (no, n) in enumerate(zip(periods_no, frames, strict=True)):
        track = PeriodTrack(
            period=int(no),
            slot_ids=[pid or None for pid in ids[i]],
            pos_cm=pos[start : start + n],
            ball_cm=ball[start : start + n],
            frames=n,
        )
        track.changes = [
            (frame, slot, change_ids[k] or None)
            for k, (pi, frame, slot) in enumerate(changes)
            if pi == i
        ]
        periods.append(track)
        start += n
    return Tracking(match_id=match_id, periods=periods, video_start_ms=video)


def _m(cm: int) -> float:
    return int(cm) / 100


def iter_tracking_frames(tracking: Tracking) -> Iterator[dict[str, Any]]:
    """Yield ``regista.tracking.v1`` frames (players in slot order, active slots only)."""
    for track, video0 in zip(tracking.periods, tracking.video_start_ms, strict=True):
        ids = list(track.slot_ids)
        pending = list(track.changes)
        pos = track.pos_cm.tolist()
        ball = track.ball_cm.tolist()
        for frame in range(track.frames):
            while pending and pending[0][0] <= frame:
                _, slot, pid = pending.pop(0)
                ids[slot] = pid
            clock = frame * 100
            yield {
                "schema": TRACKING_SCHEMA,
                "match_id": tracking.match_id,
                "frame": frame,
                "period": track.period,
                "clock_ms": clock,
                "video_ts_ms": video0 + clock,
                "ball": {"x": _m(ball[frame][0]), "y": _m(ball[frame][1]), "z": _m(ball[frame][2])},
                "players": [
                    {"id": pid, "x": _m(pos[frame][s][0]), "y": _m(pos[frame][s][1])}
                    for s, pid in enumerate(ids)
                    if pid is not None
                ],
            }


def write_jsonl_gz(path: Path, tracking: Tracking) -> None:
    """Write the spec's ``tracking.jsonl.gz`` (gzip without name or timestamp: byte-stable)."""
    with (
        path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as handle,
    ):
        for frame in iter_tracking_frames(tracking):
            handle.write(dumps_compact(frame).encode())
            handle.write(b"\n")


def load_tracking(match_dir: Path) -> Tracking:
    """Load a match folder's tracking from ``tracking.npz``."""
    return read_npz(match_dir / NPZ_NAME)


def iter_frames(match_dir: Path) -> Iterator[dict[str, Any]]:
    """Yield the match's tracking frames from ``tracking.npz``, else ``tracking.jsonl.gz``."""
    if (match_dir / NPZ_NAME).exists():
        yield from iter_tracking_frames(read_npz(match_dir / NPZ_NAME))
        return
    import json

    with gzip.open(match_dir / JSONL_NAME, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)
