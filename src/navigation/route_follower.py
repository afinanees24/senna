"""SENNA route follower.

Given a planned path, the user's current cell, and their current
heading, produces the next navigation cue dict for the audio layer.

Cue dict schema for navigation (matches src/audio/__init__.py):

    {"type": "navigation",
     "action": "forward" | "turn_left" | "turn_right" | "turn_around"
               | "destination_reached",
     "distance_m": float}     # omitted for destination_reached

Coordinate convention:
  Grid (y, x) indexed as grid[y, x]
  y increases going south, x increases going east
  Heading yaw in degrees, (-180, 180], 0 = north, 90 = east,
                                       -90 = west, 180/-180 = south
"""
from __future__ import annotations

import math
from typing import Optional


# How far off the path (in cells) before we consider the user "off route"
# and ask the caller to replan.
OFF_ROUTE_THRESHOLD_CELLS = 3

# Half-angle of the "forward" cone, in degrees. Turns within this cone
# of the user's heading are reported as "forward" rather than "turn_*".
FORWARD_CONE_DEG = 30.0

# Half-angle of the "behind" zone. Turns more than this away from
# heading get reported as "turn_around" instead of left/right.
BEHIND_CONE_DEG = 135.0


def _closest_path_index(
    path: list[tuple[int, int]],
    cell: tuple[int, int],
) -> tuple[int, int]:
    """Find the index of the path cell closest to `cell` (Manhattan).

    Returns (index, manhattan_distance).
    """
    best_i = 0
    best_d = abs(path[0][0] - cell[0]) + abs(path[0][1] - cell[1])
    for i, c in enumerate(path[1:], start=1):
        d = abs(c[0] - cell[0]) + abs(c[1] - cell[1])
        if d < best_d:
            best_d = d
            best_i = i
    return best_i, best_d


def _step_bearing(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Bearing in degrees from cell a to adjacent cell b.

    Returns 0 for north (y decreasing), 90 east (x increasing),
    -90 west, 180 south.
    """
    dy = b[0] - a[0]
    dx = b[1] - a[1]
    # atan2(dx, -dy): -dy because north is y-decreasing
    return math.degrees(math.atan2(dx, -dy))


def _normalize_deg(deg: float) -> float:
    """Normalize to (-180, 180]."""
    return ((deg + 180.0) % 360.0) - 180.0


def _next_turn_index(
    path: list[tuple[int, int]],
    start_i: int,
) -> Optional[int]:
    """Walk forward from start_i, find the index where the path's
    direction changes. Returns None if path goes straight to the end.
    """
    if start_i >= len(path) - 2:
        return None  # nothing left after start_i to turn at

    initial_bearing = _step_bearing(path[start_i], path[start_i + 1])
    for i in range(start_i + 1, len(path) - 1):
        next_bearing = _step_bearing(path[i], path[i + 1])
        if abs(_normalize_deg(next_bearing - initial_bearing)) > 1.0:
            return i  # path turns at index i
    return None  # straight all the way to destination


def _action_for_turn(
    bearing_to_turn: float,
    heading: float,
) -> str:
    """Classify a turn as forward / left / right / around relative to heading."""
    relative = _normalize_deg(bearing_to_turn - heading)
    if abs(relative) <= FORWARD_CONE_DEG:
        return "forward"
    if abs(relative) >= BEHIND_CONE_DEG:
        return "turn_around"
    return "turn_left" if relative < 0 else "turn_right"


class RouteFollower:
    """Stateless cue generator for a fixed path.

    Phase 1 keeps this dead simple: each call to next_cue() looks at
    the current pose and emits one cue. Higher-level cadence control
    (don't repeat the same cue too often, etc.) lives in the Navigator
    state machine, not here.
    """

    def __init__(
        self,
        path: list[tuple[int, int]],
        grid_resolution_m: float,
    ) -> None:
        if not path:
            raise ValueError("path must contain at least one cell")
        self._path = path
        self._res_m = grid_resolution_m

    def next_cue(
        self,
        current_cell: tuple[int, int],
        heading_yaw: float,
    ) -> Optional[dict]:
        """Compute the next navigation cue for the user.

        Returns None if the user has wandered off the path beyond the
        OFF_ROUTE_THRESHOLD; caller should replan.
        """
        idx, off_dist = _closest_path_index(self._path, current_cell)

        if off_dist > OFF_ROUTE_THRESHOLD_CELLS:
            return None  # off route, caller replans

        # Arrived?
        if idx == len(self._path) - 1:
            return {"type": "navigation", "action": "destination_reached"}

        turn_i = _next_turn_index(self._path, idx)

        if turn_i is None:
            # Straight to destination. Distance is from current cell to
            # final cell, summed along remaining path.
            cells_remaining = len(self._path) - 1 - idx
            return {
                "type": "navigation",
                "action": "forward",
                "distance_m": cells_remaining * self._res_m,
            }

        # Distance from current position to the turn cell, summed along path.
        cells_to_turn = turn_i - idx
        distance_m = cells_to_turn * self._res_m

        # The bearing of the *new* direction after the turn.
        new_bearing = _step_bearing(self._path[turn_i], self._path[turn_i + 1])
        action = _action_for_turn(new_bearing, heading_yaw)

        return {
            "type": "navigation",
            "action": action,
            "distance_m": distance_m,
        }
