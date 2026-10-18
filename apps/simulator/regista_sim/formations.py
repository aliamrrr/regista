"""Formations: role lists, positional fit and base anchors (team-relative, attacking +x).

Team-relative coordinates put the team's own goal at ``x = 0`` and its left touchline at
``y = 0`` (facing +x with ``y`` growing downward on the broadcast view, the left hand points to
``y = 0``). An anchor is ``(depth, y)``: ``depth`` metres ahead of the team's defensive line.
"""

from typing import Literal

Kind = Literal["GK", "CB", "FB", "WB", "DM", "CM", "AM", "WM", "W", "ST"]
Line = Literal["goal", "defence", "midfield", "attack"]

# role → (kind, line, depth ahead of the defensive line in metres, lateral y in metres)
ROLES: dict[str, tuple[Kind, Line, float, float]] = {
    "GK": ("GK", "goal", -30.0, 34.0),
    "RB": ("FB", "defence", 2.0, 61.0),
    "LB": ("FB", "defence", 2.0, 7.0),
    "RCB": ("CB", "defence", 0.0, 44.0),
    "LCB": ("CB", "defence", 0.0, 24.0),
    "RCB3": ("CB", "defence", 0.0, 50.0),
    "CB3": ("CB", "defence", -1.0, 34.0),
    "LCB3": ("CB", "defence", 0.0, 18.0),
    "RWB": ("WB", "midfield", 13.0, 63.0),
    "LWB": ("WB", "midfield", 13.0, 5.0),
    "DM": ("DM", "midfield", 9.0, 34.0),
    "RDM": ("DM", "midfield", 9.0, 42.0),
    "LDM": ("DM", "midfield", 9.0, 26.0),
    "RCM": ("CM", "midfield", 17.0, 46.0),
    "LCM": ("CM", "midfield", 17.0, 22.0),
    "CAM": ("AM", "midfield", 26.0, 34.0),
    "RM": ("WM", "midfield", 18.0, 61.0),
    "LM": ("WM", "midfield", 18.0, 7.0),
    "RW": ("W", "attack", 30.0, 60.0),
    "LW": ("W", "attack", 30.0, 8.0),
    "ST": ("ST", "attack", 35.0, 34.0),
    "RST": ("ST", "attack", 34.0, 41.0),
    "LST": ("ST", "attack", 34.0, 27.0),
}

FORMATIONS: dict[str, tuple[str, ...]] = {
    "4-3-3": ("GK", "RB", "RCB", "LCB", "LB", "DM", "RCM", "LCM", "RW", "ST", "LW"),
    "4-2-3-1": ("GK", "RB", "RCB", "LCB", "LB", "RDM", "LDM", "RW", "CAM", "LW", "ST"),
    "4-4-2": ("GK", "RB", "RCB", "LCB", "LB", "RM", "RCM", "LCM", "LM", "RST", "LST"),
    "3-5-2": ("GK", "RCB3", "CB3", "LCB3", "RWB", "RCM", "DM", "LCM", "LWB", "RST", "LST"),
    "3-4-3": ("GK", "RCB3", "CB3", "LCB3", "RWB", "RCM", "LCM", "LWB", "RW", "ST", "LW"),
    "4-1-4-1": ("GK", "RB", "RCB", "LCB", "LB", "DM", "RM", "RCM", "LCM", "LM", "ST"),
}

POSITIONS = ("GK", "RB", "LB", "CB", "DM", "CM", "AM", "RW", "LW", "ST")

# role kind → player positions that can fill it, best fit first
_FIT: dict[str, tuple[str, ...]] = {
    "GK": ("GK",),
    "CB": ("CB", "DM", "RB", "LB"),
    "DM": ("DM", "CM", "CB"),
    "CM": ("CM", "DM", "AM"),
    "AM": ("AM", "CM", "RW", "LW"),
    "ST": ("ST", "AM", "LW", "RW"),
}
_SIDED_FIT: dict[str, tuple[str, ...]] = {
    "RB": ("RB", "LB", "CB"),
    "LB": ("LB", "RB", "CB"),
    "RWB": ("RB", "RW", "LB"),
    "LWB": ("LB", "LW", "RB"),
    "RM": ("RW", "LW", "AM", "CM"),
    "LM": ("LW", "RW", "AM", "CM"),
    "RW": ("RW", "LW", "AM", "ST"),
    "LW": ("LW", "RW", "AM", "ST"),
}


def role_fit(role: str) -> tuple[str, ...]:
    """Return the player positions that can play ``role``, best fit first."""
    if role in _SIDED_FIT:
        return _SIDED_FIT[role]
    return _FIT[ROLES[role][0]]


def role_kind(role: str) -> Kind:
    """Return the behavioural kind of ``role`` (``"FB"`` for ``"RB"``, ...)."""
    return ROLES[role][0]


def role_line(role: str) -> Line:
    """Return the line of ``role``: goal, defence, midfield or attack."""
    return ROLES[role][1]
