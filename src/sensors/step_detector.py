"""Step detection + dead-reckoning position update.

Watches the accelerometer stream from HeadTracker for footfall peaks.
Each detected step advances PositionTracker by step_length_m in the
current heading direction. Fractional cell movement accumulates so
short steps on a fine grid don't get rounded away.

This is the Phase 5 piece — converts the navigation system from
"simulates walking" to "responds to actual walking." Drift accumulates;
later phases (vision in Phase 9) correct it.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Optional

from src.sensors.head_tracker import HeadTracker
from src.sensors.position import PositionTracker


# Earth gravity (m/s^2). Slight regional variation but 9.81 is fine.
GRAVITY = 9.81

# Default tuning. Step length: average adult walking is 0.65-0.75m.
DEFAULT_STEP_LENGTH_M = 0.7

# Peak detection thresholds. a_dynamic = ||(ax, ay, az)|| - g
# Crossing UP threshold = candidate step; falling below DOWN = ready for next.
# Minimum interval prevents double-counting (max ~3 steps/sec).
PEAK_UP_THRESHOLD = 1.5      # m/s^2 above gravity
PEAK_DOWN_THRESHOLD = 0.5    # hysteresis to avoid chattering
MIN_STEP_INTERVAL_SEC = 0.3


class StepDetector:
    """Background-thread step detector + dead-reckoning updater.

    Usage:
        sd = StepDetector(head_tracker, position_tracker, grid_resolution_m)
        sd.start()
        # ... wear IMU, walk around ...
        print(sd.step_count(), position_tracker.get_pose())
        sd.stop()
    """

    def __init__(
        self,
        head_tracker: HeadTracker,
        position_tracker: PositionTracker,
        grid_resolution_m: float,
        step_length_m: float = DEFAULT_STEP_LENGTH_M,
    ) -> None:
        self._ht = head_tracker
        self._pos = position_tracker
        self._grid_res = grid_resolution_m
        self._step_length = step_length_m

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()

        # Fractional-cell accumulator (carries leftover sub-cell movement).
        self._fy_accum = 0.0
        self._fx_accum = 0.0

        # Peak detection state.
        self._above_threshold = False
        self._last_step_time = 0.0
        self._steps = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._run, name="StepDetector", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def step_count(self) -> int:
        with self._lock:
            return self._steps

    def reset(self) -> None:
        """Reset step count and fractional accumulator (not PositionTracker)."""
        with self._lock:
            self._steps = 0
            self._fy_accum = 0.0
            self._fx_accum = 0.0
            self._above_threshold = False
            self._last_step_time = 0.0

    def _run(self) -> None:
        while not self._stop_evt.is_set():
            ori = self._ht.latest()
            if ori is None:
                time.sleep(0.01)
                continue

            a_total = math.sqrt(ori.ax ** 2 + ori.ay ** 2 + ori.az ** 2)
            a_dynamic = a_total - GRAVITY
            now = time.monotonic()

            # Peak detection with hysteresis.
            if not self._above_threshold and a_dynamic > PEAK_UP_THRESHOLD:
                if now - self._last_step_time > MIN_STEP_INTERVAL_SEC:
                    self._on_step(ori.yaw)
                    self._last_step_time = now
                self._above_threshold = True
            elif self._above_threshold and a_dynamic < PEAK_DOWN_THRESHOLD:
                self._above_threshold = False

            time.sleep(0.01)  # 100Hz poll

    def _on_step(self, heading_yaw: float) -> None:
        """Apply one step's worth of dead-reckoning displacement."""
        # heading_yaw: 0=north (y decreasing), 90=east (x increasing)
        rad = math.radians(heading_yaw)
        dy_m = -math.cos(rad) * self._step_length
        dx_m = math.sin(rad) * self._step_length

        with self._lock:
            self._fy_accum += dy_m / self._grid_res
            self._fx_accum += dx_m / self._grid_res
            self._steps += 1

            dy_int = round(self._fy_accum)
            dx_int = round(self._fx_accum)

            if dy_int != 0 or dx_int != 0:
                pose = self._pos.get_pose()
                self._pos.set_position(
                    pose.grid_y + dy_int,
                    pose.grid_x + dx_int,
                )
                self._fy_accum -= dy_int
                self._fx_accum -= dx_int
