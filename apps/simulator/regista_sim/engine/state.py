"""Mutable match state shared by the engine modules."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np

from regista_sim.models import Club, Player

N_SLOTS = 22  # slots 0–10: home, 11–21: away


class BallState(IntEnum):
    """Ball state machine of docs/DATA_AND_METRICS.md §2."""

    CONTROLLED = 0
    IN_FLIGHT = 1
    DEAD = 2


@dataclass
class Plan:
    """A movement override: the player heads for ``target`` (absolute) until ``until_tick``."""

    target: tuple[float, float]
    urgency: float = 1.0
    speed_cap: float | None = None  # m/s; scripted sprints set an exact top speed
    until_tick: int | None = None
    source: str = "engine"  # run | receive | intercept | chase | taker | carry | scenario


@dataclass
class TeamState:
    """One team: identity, lineup by slot, bench, score and discipline."""

    index: int  # 0 home, 1 away
    club: Club
    roster: dict[str, Player]
    roles: list[str]  # role per slot (11 entries)
    on_pitch: list[str | None]  # player id per slot, None after a red card
    bench: list[str]
    direction: int = 1  # +1 attacks towards x = 105 this period
    score: int = 0
    subs_used: int = 0
    yellows: dict[str, int] = field(default_factory=dict)
    sent_off: list[str] = field(default_factory=list)

    @property
    def code(self) -> str:
        """Three-letter club code."""
        return self.club.code


@dataclass
class Flight:
    """A ball in the air or rolling after a pass, shot or clearance."""

    kind: str  # pass | shot | clearance
    team: int
    actor: int  # slot that struck the ball
    start: tuple[float, float]
    start_tick: int
    start_clock_ms: int
    target: tuple[float, float]
    vx: float
    vy: float
    vz: float
    lofted: bool
    planned: str  # pass: complete/incomplete/out/offside; shot: goal/saved/off_target/blocked/post
    receiver: int = -1  # intended receiver (passes)
    taker: int = -1  # slot allowed to take the ball first (receiver or interceptor)
    stop_at: tuple[float, float] | None = None  # interception / block / save point
    payload: dict[str, Any] = field(default_factory=dict)  # event payload under construction
    event_meta: dict[str, Any] = field(default_factory=dict)  # location, possession, pressure
    truth: dict[str, Any] = field(default_factory=dict)
    deadline_k: int = 1_000_000  # path index after which the designated taker gives up


@dataclass
class Restart:
    """A dead ball waiting to be played."""

    kind: str  # throw_in | goal_kick | corner | free_kick | penalty | kick_off
    team: int
    spot: tuple[float, float]
    ready_tick: int
    taker: int = -1
    reason: str = "ball_out"


@dataclass
class Bodies:
    """Physical state of the 22 slots (absolute metres, m/s)."""

    pos: np.ndarray = field(default_factory=lambda: np.zeros((N_SLOTS, 2)))
    vel: np.ndarray = field(default_factory=lambda: np.zeros((N_SLOTS, 2)))
    vmax: np.ndarray = field(default_factory=lambda: np.full(N_SLOTS, 8.5))
    a0: np.ndarray = field(default_factory=lambda: np.full(N_SLOTS, 4.5))
    stamina: np.ndarray = field(default_factory=lambda: np.full(N_SLOTS, 0.7))
    energy: np.ndarray = field(default_factory=lambda: np.ones(N_SLOTS))
    noise: np.ndarray = field(default_factory=lambda: np.zeros((N_SLOTS, 2)))
    active: np.ndarray = field(default_factory=lambda: np.ones(N_SLOTS, dtype=bool))
