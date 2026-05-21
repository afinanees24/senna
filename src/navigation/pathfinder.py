"""SENNA path planning — A* on a 2D occupancy grid.

Grid convention (matching SennaMap):
  - shape (height, width) = (rows, cols)
  - indexed grid[y, x]
  - cell values: 0 = free, 1 = wall, 2 = unknown

Coordinates are (y, x) tuples throughout, matching numpy indexing.
4-connectivity (N/S/E/W only) — no diagonal moves, which avoids
corner-cutting through inside corners.
"""
from __future__ import annotations

import heapq
from typing import Optional

import numpy as np


FREE = 0
WALL = 1
UNKNOWN = 2

NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _passable(value: int, allow_unknown: bool) -> bool:
    if value == FREE:
        return True
    if value == UNKNOWN and allow_unknown:
        return True
    return False


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def pathfind(
    grid: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    *,
    allow_unknown: bool = False,
) -> Optional[list[tuple[int, int]]]:
    """A* on a 2D occupancy grid.

    Args:
        grid: 2D uint8 array. 0=free, 1=wall, 2=unknown.
        start: (y, x) cell where the agent starts.
        goal:  (y, x) cell to reach.
        allow_unknown: if True, treat unknown cells as passable.

    Returns:
        List of (y, x) cells from start to goal inclusive, or None if
        unreachable. If start == goal, returns [start].

    Raises:
        ValueError: if start or goal is out of bounds or impassable.
    """
    h, w = grid.shape

    def in_bounds(cell: tuple[int, int]) -> bool:
        y, x = cell
        return 0 <= y < h and 0 <= x < w

    if not in_bounds(start):
        raise ValueError(f"start {start} out of bounds for grid {grid.shape}")
    if not in_bounds(goal):
        raise ValueError(f"goal {goal} out of bounds for grid {grid.shape}")
    if not _passable(int(grid[start]), allow_unknown):
        raise ValueError(f"start {start} is on impassable cell (value {int(grid[start])})")
    if not _passable(int(grid[goal]), allow_unknown):
        raise ValueError(f"goal {goal} is on impassable cell (value {int(grid[goal])})")

    if start == goal:
        return [start]

    counter = 0  # heap tiebreaker
    open_heap: list[tuple[int, int, tuple[int, int]]] = []
    heapq.heappush(open_heap, (_manhattan(start, goal), counter, start))

    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], int] = {start: 0}
    closed: set[tuple[int, int]] = set()

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        closed.add(current)

        cy, cx = current
        for dy, dx in NEIGHBORS_4:
            neighbor = (cy + dy, cx + dx)
            if not in_bounds(neighbor):
                continue
            if neighbor in closed:
                continue
            if not _passable(int(grid[neighbor]), allow_unknown):
                continue
            tentative_g = g_score[current] + 1
            if tentative_g < g_score.get(neighbor, 1 << 30):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + _manhattan(neighbor, goal)
                counter += 1
                heapq.heappush(open_heap, (f, counter, neighbor))

    return None
