"""
SENNA head tracker — BNO085 IMU via UART-RVC at 100 Hz.

Reads orientation in a background thread and exposes the latest reading
to the rest of the system with latest-wins semantics. No blocking on
the consumer side; no stale-buffer accumulation on the producer side.

Sign conventions (chip body frame, verified empirically 2026-05-21):
  +pitch -> chip +Y axis tilts up
  +roll  -> chip +X axis tilts down
  yaw    -> rotation about chip +Z; CW vs CCW sign TBD, flip at consumer
           if needed when mounted.

Mount-to-head axis remapping is the consumer's responsibility for now.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import serial
from adafruit_bno08x_rvc import BNO08x_RVC


@dataclass(frozen=True)
class Orientation:
    yaw: float       # degrees
    pitch: float     # degrees
    roll: float      # degrees
    ax: float        # m/s^2, chip body frame
    ay: float
    az: float
    timestamp: float # time.monotonic() seconds


class HeadTracker:
    def __init__(self, port: str = "/dev/serial0", baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self._uart: Optional[serial.Serial] = None
        self._rvc: Optional[BNO08x_RVC] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._latest: Optional[Orientation] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._uart = serial.Serial(self._port, self._baudrate, timeout=0.5)
        self._rvc = BNO08x_RVC(self._uart)
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._run, name="HeadTracker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._uart is not None:
            self._uart.close()
            self._uart = None
        self._rvc = None

    def latest(self) -> Optional[Orientation]:
        """Most recent orientation sample, or None before first read."""
        with self._lock:
            return self._latest

    def _run(self) -> None:
        assert self._rvc is not None
        while not self._stop_evt.is_set():
            try:
                yaw, pitch, roll, ax, ay, az = self._rvc.heading
            except Exception:
                # Transient frame error; just try the next one.
                continue
            ori = Orientation(
                yaw=yaw, pitch=pitch, roll=roll,
                ax=ax, ay=ay, az=az,
                timestamp=time.monotonic(),
            )
            with self._lock:
                self._latest = ori
