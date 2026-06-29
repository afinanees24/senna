"""Live step-detection test. Wear the IMU, walk around, watch position.

Initializes everything, prints pose + step count every 0.5 sec.
Ctrl+C to stop.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sensors.head_tracker import HeadTracker
from src.sensors.position import PositionTracker
from src.sensors.step_detector import StepDetector


def main() -> None:
    grid_res = 0.10  # 10cm per cell

    ht = HeadTracker()
    ht.start()
    time.sleep(0.5)

    pos = PositionTracker(grid_y=0, grid_x=0, heading_yaw=0.0)
    sd = StepDetector(ht, pos, grid_resolution_m=grid_res)
    sd.start()

    print("Walk around. Ctrl+C to stop.")
    print("  Output: steps | (grid_y, grid_x) | heading_yaw")
    try:
        while True:
            ori = ht.latest()
            if ori is not None:
                pos.set_heading(ori.yaw)  # feed IMU yaw into position tracker
            steps = sd.step_count()
            pose = pos.get_pose()
            print(f"  steps={steps:4d}  pose=({pose.grid_y:4d}, {pose.grid_x:4d})  yaw={pose.heading_yaw:7.2f}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        sd.stop()
        ht.stop()
        print("\nFinal:", pos.get_pose())


if __name__ == "__main__":
    main()
