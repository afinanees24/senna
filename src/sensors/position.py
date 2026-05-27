"""SENNA position tracker.

Holds the user's current best estimate of where they are on the grid
and which way they're facing. Phase 1: set explicitly. Later phases
fold in IMU heading (from HeadTracker), step-counted dead reckoning,
WiFi venue ID, and vision-aided localization.

Coordinate convention matches SennaMap and pathfinder: (grid_y, grid_x)
indexed as grid[y, x]. Heading is yaw in degrees, range (-180, 180],
with 0 = north (grid_y decreasing direction by convention).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Pose:
    """Snapshot of where the user is and which way they're facing."""
    grid_y: int
    grid_x: int
    heading_yaw: float   # degrees, (-180, 180]
    timestamp: float     # time.monotonic()

    def as_cell(self) -> tuple[int, int]:
        """Just the (y, x) cell for pathfinder/route-follower use."""
        return (self.grid_y, self.grid_x)


class PositionTracker:
    """Thread-safe holder for the current pose estimate.

    Phase 1 API: explicit set_position / set_heading. Phase 2+ will
    add update_from_imu, update_from_vision, update_from_wifi.
    """

    def __init__(
        self,
        grid_y: int = 0,
        grid_x: int = 0,
        heading_yaw: float = 0.0,
    ) -> None:
        self._lock = threading.Lock()
        self._pose = Pose(
            grid_y=grid_y,
            grid_x=grid_x,
            heading_yaw=heading_yaw,
            timestamp=time.monotonic(),
        )

    def get_pose(self) -> Pose:
        """Latest pose snapshot. Safe to call from any thread."""
        with self._lock:
            return self._pose

    def get_cell(self) -> tuple[int, int]:
        """Just (y, x). Convenience for pathfinder/route-follower."""
        return self.get_pose().as_cell()

    def get_heading(self) -> float:
        """Just yaw in degrees."""
        return self.get_pose().heading_yaw

    def set_position(self, grid_y: int, grid_x: int) -> None:
        """Explicitly set (y, x). Heading unchanged."""
        with self._lock:
            self._pose = Pose(
                grid_y=grid_y,
                grid_x=grid_x,
                heading_yaw=self._pose.heading_yaw,
                timestamp=time.monotonic(),
            )

    def set_heading(self, heading_yaw: float) -> None:
        """Explicitly set heading in degrees. Position unchanged.

        Normalizes to (-180, 180].
        """
        normalized = ((heading_yaw + 180.0) % 360.0) - 180.0
        with self._lock:
            self._pose = Pose(
                grid_y=self._pose.grid_y,
                grid_x=self._pose.grid_x,
                heading_yaw=normalized,
                timestamp=time.monotonic(),
            )

    def set_pose(
        self,
        grid_y: int,
        grid_x: int,
        heading_yaw: float,
    ) -> None:
        """Set both at once atomically."""
        normalized = ((heading_yaw + 180.0) % 360.0) - 180.0
        with self._lock:
            self._pose = Pose(
                grid_y=grid_y,
                grid_x=grid_x,
                heading_yaw=normalized,
                timestamp=time.monotonic(),
            )
