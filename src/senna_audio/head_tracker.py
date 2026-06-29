"""Continuous IMU read into thread-safe head orientation state."""

import serial
import threading
import time
from adafruit_bno08x_rvc import BNO08x_RVC


class HeadTracker:
    """Background thread that continuously reads IMU and exposes current orientation."""

    def __init__(self, port: str = "/dev/serial0", baud: int = 115200):
        self._uart = serial.Serial(port, baud)
        self._rvc = BNO08x_RVC(self._uart)
        self._lock = threading.Lock()
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0
        self._ax = 0.0
        self._ay = 0.0
        self._az = 0.0
        self._running = False
        self._thread = None
        self._last_update = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._uart.close()

    def _loop(self) -> None:
        while self._running:
            try:
                yaw, pitch, roll, ax, ay, az = self._rvc.heading
                with self._lock:
                    self._yaw, self._pitch, self._roll = yaw, pitch, roll
                    self._ax, self._ay, self._az = ax, ay, az
                    self._last_update = time.time()
            except Exception:
                time.sleep(0.01)

    @property
    def orientation(self) -> tuple[float, float, float]:
        """(yaw, pitch, roll) in degrees."""
        with self._lock:
            return (self._yaw, self._pitch, self._roll)

    @property
    def acceleration(self) -> tuple[float, float, float]:
        """(ax, ay, az) in m/s^2 (gravity included)."""
        with self._lock:
            return (self._ax, self._ay, self._az)

    @property
    def is_fresh(self) -> bool:
        """True if we got an IMU reading in the last 100ms."""
        with self._lock:
            return time.time() - self._last_update < 0.1
