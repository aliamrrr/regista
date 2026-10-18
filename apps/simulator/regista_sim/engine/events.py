"""Event log: collects raw events, then orders, numbers and timestamps them (§4).

Events are recorded when they are resolved (a pass once the ball arrives, a pressure once it
ends) but stamped with the clock time they started; ``finalize`` sorts by
``(period, clock_ms, recording order)`` and assigns ``seq`` and ``event_id``.
"""

from dataclasses import dataclass
from typing import Any

from regista_sim import __version__
from regista_sim.engine.clock import MatchClock

EVENT_SCHEMA = "regista.event.v1"


@dataclass(frozen=True)
class EventRef:
    """A reference to another event, resolved to its ``event_id`` by ``finalize``."""

    index: int


def loc(x: float, y: float) -> dict[str, float]:
    """Return a location object rounded to 0.1 m."""
    return {"x": round(x, 1), "y": round(y, 1)}


class EventLog:
    """Append-only raw event store for one match."""

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        self.raw: list[dict[str, Any]] = []
        self.ids: dict[int, str] = {}  # raw index → event_id, filled by finalize

    def add(
        self,
        kind: str,
        period: int,
        clock_ms: int,
        *,
        team: str | None = None,
        player: str | None = None,
        location: dict[str, float] | None = None,
        possession: str | None = None,
        under_pressure: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> EventRef:
        """Record an event and return a reference to it."""
        self.raw.append(
            {
                "type": kind,
                "period": period,
                "clock_ms": int(clock_ms),
                "team_id": team,
                "player_id": player,
                "location": location,
                "possession_id": possession,
                "under_pressure": bool(under_pressure),
                "payload": payload or {},
                "_order": len(self.raw),
            }
        )
        return EventRef(len(self.raw) - 1)

    def finalize(self, clock: MatchClock) -> list[dict[str, Any]]:
        """Return the ordered feed with ``seq``, ``event_id`` and both timestamps."""
        ordered = sorted(self.raw, key=lambda e: (e["period"], e["clock_ms"], e["_order"]))
        ids = {e["_order"]: f"{self.match_id}-e{seq:06d}" for seq, e in enumerate(ordered, start=1)}
        self.ids = ids
        feed = []
        for seq, event in enumerate(ordered, start=1):
            video = clock.video_ts(event["period"], event["clock_ms"])
            payload = {
                k: (ids[v.index] if isinstance(v, EventRef) else v)
                for k, v in event["payload"].items()
            }
            feed.append(
                {
                    "schema": EVENT_SCHEMA,
                    "event_id": ids[event["_order"]],
                    "match_id": self.match_id,
                    "seq": seq,
                    "type": event["type"],
                    "period": event["period"],
                    "clock_ms": event["clock_ms"],
                    "video_ts_ms": video,
                    "wall_ts": clock.wall_ts(video),
                    "team_id": event["team_id"],
                    "player_id": event["player_id"],
                    "location": event["location"],
                    "possession_id": event["possession_id"],
                    "under_pressure": event["under_pressure"],
                    "payload": payload,
                    "provenance": {"source": "simulator", "version": __version__},
                }
            )
        return feed

    def id_of(self, ref: EventRef) -> str:
        """Return the final ``event_id`` of ``ref`` (after ``finalize``)."""
        return self.ids[ref.index]
