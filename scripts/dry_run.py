"""Phase 1 dry run: fake-walk through a route and print the cue stream.

Simulates the user starting at one named destination and walking,
one path cell per tick, to another. No real sensors — position is
advanced explicitly. Useful for verifying that Navigator + RouteFollower
+ plan_route produce a sensible sequence of cues end to end.

Usage:
    python scripts/dry_run.py [.senna_path] [start_destination] [end_destination]

Defaults to tests/fixtures/fake_apartment.senna and kitchen -> front door.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Make project root importable regardless of where the script is run from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.transfer.senna_map import SennaMap
from src.sensors.position import PositionTracker
from src.audio import StdoutAudio
from src.brain import Navigator, Mode
from src.navigation import plan_route


def fake_walk(
    senna_path: str,
    start_dest_name: str,
    end_dest_name: str,
    tick_rate_hz: float = 2.0,
) -> None:
    smap = SennaMap.load(senna_path)

    start = smap.find_destination(start_dest_name)
    if start is None:
        print(f"ERROR: start '{start_dest_name}' not found in venue")
        return

    # Start facing south by default — arbitrary; real system gets this from IMU
    pos = PositionTracker(
        grid_y=start.grid_y,
        grid_x=start.grid_x,
        heading_yaw=180.0,
    )
    audio = StdoutAudio()
    nav = Navigator(smap, pos, audio)

    print(f"\n=== Dry run: {start.name} -> {end_dest_name} ===")
    print(f"Starting at ({start.grid_y}, {start.grid_x}), facing south\n")

    ok = nav.set_destination(end_dest_name)
    if not ok:
        return

    # Recompute the path for stepping — Navigator owns it internally but we
    # need it here to drive the fake walk.
    path = plan_route(smap, pos.get_cell(), end_dest_name)
    assert path is not None

    # Walk one cell per tick.
    tick_interval = 1.0 / tick_rate_hz
    for i, cell in enumerate(path):
        # Update heading to face the next step (if any) so cues reflect a
        # walker who actually turns when the path turns.
        if i + 1 < len(path):
            dy = path[i + 1][0] - cell[0]
            dx = path[i + 1][1] - cell[1]
            import math
            heading = math.degrees(math.atan2(dx, -dy))
            pos.set_pose(cell[0], cell[1], heading)
        else:
            pos.set_position(cell[0], cell[1])

        nav.tick()

        if nav.mode == Mode.ARRIVED:
            break

        time.sleep(tick_interval)

    print(f"\n=== Final mode: {nav.mode} ===")


if __name__ == "__main__":
    args = sys.argv[1:]
    senna_path = args[0] if len(args) > 0 else "tests/fixtures/fake_apartment.senna"
    start_dest = args[1] if len(args) > 1 else "kitchen"
    end_dest = args[2] if len(args) > 2 else "front door"
    fake_walk(senna_path, start_dest, end_dest)
