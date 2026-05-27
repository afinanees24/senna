"""SENNA navigation package — high-level route planning API.

Wraps pathfind() and SennaMap.find_destination() into a single call
that the state machine can use without knowing about either.
"""
from __future__ import annotations

from typing import Optional

from src.navigation.pathfinder import pathfind
from src.transfer.senna_map import SennaMap


def plan_route(
    smap: SennaMap,
    current_position: tuple[int, int],
    destination_query: str,
    *,
    allow_unknown: bool = False,
) -> Optional[list[tuple[int, int]]]:
    """Plan a route from current position to a named destination.

    Args:
        smap: Loaded SENNA map.
        current_position: (y, x) cell where the user currently is.
        destination_query: Destination name or alias (case-insensitive),
            e.g. "kitchen", "front door", "the bathroom".
        allow_unknown: If True, A* may path through unknown cells.

    Returns:
        List of (y, x) cells from current_position to the destination
        inclusive, or None if either:
          - the destination name doesn't match any known destination, or
          - no path exists.

    Raises:
        ValueError: if current_position is out of bounds or on an
            impassable cell.
    """
    dest = smap.find_destination(destination_query)
    if dest is None:
        return None

    # Destinations store (grid_x, grid_y); pathfinder uses (y, x).
    goal = (dest.grid_y, dest.grid_x)
    return pathfind(smap.grid, current_position, goal, allow_unknown=allow_unknown)
