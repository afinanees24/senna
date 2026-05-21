"""Tests for src.navigation.pathfinder. Runs without pytest."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.navigation.pathfinder import pathfind, FREE, WALL, UNKNOWN
from src.transfer.senna_map import SennaMap


FIXTURE = Path(__file__).parent / "fixtures" / "fake_apartment.senna"


def make_grid(rows):
    h = len(rows)
    w = len(rows[0])
    g = np.zeros((h, w), dtype=np.uint8)
    chars = {".": FREE, "#": WALL, "?": UNKNOWN}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            g[y, x] = chars[ch]
    return g


def assert_valid_path(path, grid, start, goal, allow_unknown=False):
    assert path[0] == start
    assert path[-1] == goal
    for cell in path:
        v = int(grid[cell])
        if allow_unknown:
            assert v in (FREE, UNKNOWN), f"path on wall at {cell}"
        else:
            assert v == FREE, f"path on non-free cell {cell} (v={v})"
    for a, b in zip(path, path[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, f"non-adjacent {a} -> {b}"


def expect_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    raise AssertionError(f"expected {exc_type.__name__}, none raised")


# -- Synthetic grid tests --

def test_straight_line():
    grid = np.zeros((5, 5), dtype=np.uint8)
    path = pathfind(grid, (0, 0), (0, 4))
    assert path is not None
    assert_valid_path(path, grid, (0, 0), (0, 4))
    assert len(path) == 5


def test_start_equals_goal():
    grid = np.zeros((5, 5), dtype=np.uint8)
    assert pathfind(grid, (2, 2), (2, 2)) == [(2, 2)]


def test_around_obstacle():
    grid = make_grid([".....", ".###.", "....."])
    path = pathfind(grid, (0, 0), (2, 2))
    assert path is not None
    assert_valid_path(path, grid, (0, 0), (2, 2))


def test_unreachable():
    grid = make_grid([".....", "#####", "....."])
    assert pathfind(grid, (0, 0), (2, 0)) is None


def test_unknown_blocked_by_default():
    grid = make_grid(["..?..", "..?..", "..?.."])
    assert pathfind(grid, (0, 0), (0, 4)) is None


def test_unknown_passable_when_allowed():
    grid = make_grid(["..?..", "..?..", "..?.."])
    path = pathfind(grid, (0, 0), (0, 4), allow_unknown=True)
    assert path is not None
    assert_valid_path(path, grid, (0, 0), (0, 4), allow_unknown=True)


def test_start_on_wall_raises():
    grid = make_grid(["###", "#.#", "###"])
    expect_raises(ValueError, pathfind, grid, (0, 0), (1, 1))


def test_goal_out_of_bounds_raises():
    grid = np.zeros((3, 3), dtype=np.uint8)
    expect_raises(ValueError, pathfind, grid, (0, 0), (5, 5))


# -- Integration against the fake apartment fixture --

def test_fake_apartment_kitchen_to_bathroom():
    smap = SennaMap.load(FIXTURE)
    k = smap.find_destination("kitchen")
    b = smap.find_destination("bathroom")
    start = (k.grid_y, k.grid_x)
    goal = (b.grid_y, b.grid_x)
    path = pathfind(smap.grid, start, goal)
    assert path is not None
    assert_valid_path(path, smap.grid, start, goal)


def test_fake_apartment_kitchen_to_front_door():
    smap = SennaMap.load(FIXTURE)
    k = smap.find_destination("kitchen")
    fd = smap.find_destination("front door")
    start = (k.grid_y, k.grid_x)
    goal = (fd.grid_y, fd.grid_x)
    path = pathfind(smap.grid, start, goal)
    assert path is not None
    assert_valid_path(path, smap.grid, start, goal)


if __name__ == "__main__":
    tests = [(n, globals()[n]) for n in sorted(globals()) if n.startswith("test_")]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception:
            print(f"FAIL  {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
