"""In-memory tracking recorder: one frame per tick, positions in integer centimetres."""

from dataclasses import dataclass, field

import numpy as np

from regista_sim.engine.state import N_SLOTS


@dataclass
class PeriodTrack:
    """Tracking of one period: frame ``i`` is at ``clock_ms = 100 × i``."""

    period: int
    slot_ids: list[str | None]  # player per slot at frame 0
    pos_cm: np.ndarray  # (frames, 22, 2) int32
    ball_cm: np.ndarray  # (frames, 3) int32
    changes: list[tuple[int, int, str | None]] = field(default_factory=list)  # frame, slot, id
    frames: int = 0

    def ids_at(self, frame: int) -> list[str | None]:
        """Return the player id in each slot at ``frame``."""
        ids = list(self.slot_ids)
        for at, slot, pid in self.changes:
            if at > frame:
                break
            ids[slot] = pid
        return ids


class Recorder:
    """Collects tracking frames for every period of a match."""

    def __init__(self, capacity: int = 34_000) -> None:
        self.capacity = capacity
        self.periods: list[PeriodTrack] = []

    def start_period(self, period: int, slot_ids: list[str | None]) -> None:
        """Open a new period with the current slot → player assignment."""
        self.periods.append(
            PeriodTrack(
                period=period,
                slot_ids=list(slot_ids),
                pos_cm=np.zeros((self.capacity, N_SLOTS, 2), dtype=np.int32),
                ball_cm=np.zeros((self.capacity, 3), dtype=np.int32),
            )
        )

    @property
    def current(self) -> PeriodTrack:
        """The period being recorded."""
        return self.periods[-1]

    def set_slot(self, slot: int, player_id: str | None) -> None:
        """Assign ``slot`` to another player (or nobody) from the next recorded frame on."""
        track = self.current
        track.changes.append((track.frames, slot, player_id))

    def record(self, pos: np.ndarray, ball: tuple[float, float, float]) -> None:
        """Store one frame (absolute metres in, centimetres stored)."""
        track = self.current
        i = track.frames
        np.rint(pos * 100.0, out=track.pos_cm[i], casting="unsafe")
        track.ball_cm[i] = (round(ball[0] * 100.0), round(ball[1] * 100.0), round(ball[2] * 100.0))
        track.frames = i + 1

    def end_period(self) -> None:
        """Trim the current period's arrays to the frames actually recorded."""
        track = self.current
        track.pos_cm = track.pos_cm[: track.frames].copy()
        track.ball_cm = track.ball_cm[: track.frames].copy()
