"""SENNA Camera Capture.

Background thread that continuously captures frames from the IMX500 camera
at a target framerate. Provides a thread-safe API to grab the most recent
frame, plus optional frame recording for debugging.

Usage:
    from senna.vision.camera import CameraCapture
    cam = CameraCapture(resolution=(640, 480), target_fps=10)
    cam.start()
    frame = cam.get_latest_frame()  # numpy array, BGR format
    cam.stop()
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
from picamera2 import Picamera2

log = logging.getLogger("senna.camera")


class CameraCapture:
    """Background thread that captures frames at a target framerate."""

    def __init__(
        self,
        resolution: tuple[int, int] = (640, 480),
        target_fps: int = 10,
        recording_dir: Optional[Path | str] = None,
    ):
        self.resolution = resolution
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.recording_dir = Path(recording_dir) if recording_dir else None
        if self.recording_dir:
            self.recording_dir.mkdir(parents=True, exist_ok=True)

        self._picam: Optional[Picamera2] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_frame_time: float = 0.0
        self._frame_count: int = 0
        self._dropped_count: int = 0

    def start(self):
        """Initialize the camera and begin capture in a background thread."""
        if self._thread and self._thread.is_alive():
            log.warning("Camera already running")
            return

        log.info(
            "Starting camera at %dx%d @ %d FPS",
            self.resolution[0], self.resolution[1], self.target_fps,
        )

        self._picam = Picamera2()
        config = self._picam.create_video_configuration(
            main={"size": self.resolution, "format": "RGB888"}
        )
        self._picam.configure(config)
        self._picam.start()
        # Allow auto-exposure/white-balance to settle
        time.sleep(0.5)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        log.info("Camera capture started")

    def _capture_loop(self):
        """Background loop: capture, store, sleep to maintain target FPS."""
        next_frame_time = time.time()
        while not self._stop_event.is_set():
            try:
                # picamera2's "RGB888" format actually returns BGR-ordered arrays
                # (a quirk of the underlying V4L2 format naming). So no swap needed.
                bgr = self._picam.capture_array().copy()

                now = time.time()
                with self._lock:
                    self._latest_frame = bgr
                    self._latest_frame_time = now
                    self._frame_count += 1

                if self.recording_dir:
                    fname = self.recording_dir / f"frame_{self._frame_count:06d}.npy"
                    np.save(fname, bgr)
            except Exception as e:
                log.error("Frame capture error: %s", e)
                self._dropped_count += 1

            # Pace at target FPS
            next_frame_time += self.frame_interval
            sleep_time = next_frame_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Behind schedule; reset to avoid spiral
                next_frame_time = time.time()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the most recent frame, or None if no frame yet."""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def get_stats(self) -> dict:
        """Return capture statistics."""
        with self._lock:
            return {
                "frame_count": self._frame_count,
                "dropped_count": self._dropped_count,
                "latest_frame_age_s": (
                    time.time() - self._latest_frame_time
                    if self._latest_frame_time > 0 else None
                ),
                "resolution": self.resolution,
                "target_fps": self.target_fps,
            }

    def stop(self):
        """Stop capture and release the camera."""
        log.info("Stopping camera")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._picam:
            try:
                self._picam.stop()
                self._picam.close()
            except Exception as e:
                log.warning("Error stopping camera: %s", e)
            self._picam = None
        log.info(
            "Camera stopped (captured=%d, dropped=%d)",
            self._frame_count, self._dropped_count,
        )


if __name__ == "__main__":
    import cv2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cam = CameraCapture(resolution=(640, 480), target_fps=10)
    cam.start()

    print("Capturing for 5 seconds...")
    time.sleep(5)

    frame = cam.get_latest_frame()
    stats = cam.get_stats()

    print()
    print(f"Latest frame shape: {frame.shape if frame is not None else 'None'}")
    print(f"Latest frame dtype: {frame.dtype if frame is not None else 'None'}")
    print(f"Stats: {stats}")

    if frame is not None:
        out_path = "/tmp/camera_test_frame.jpg"
        cv2.imwrite(out_path, frame)
        print(f"Saved frame to {out_path}")

    cam.stop()
