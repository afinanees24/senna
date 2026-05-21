"""Generate a fake but spec-compliant .senna file for testing.

Usage:
    python -m src.transfer.make_fake_senna /tmp/fake_apartment.senna
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import datetime, timezone

import numpy as np


def make_fake_senna(output_path: str, venue_name: str = "Fake Apartment") -> None:
    # 50x40 grid: 0 = free, 1 = wall, 2 = unknown
    grid = np.zeros((40, 50), dtype=np.uint8)
    grid[0, :] = 1   # top wall
    grid[-1, :] = 1  # bottom wall
    grid[:, 0] = 1   # left wall
    grid[:, -1] = 1  # right wall
    grid[20, 10:30] = 1  # an interior wall
    grid[15:25, 35] = 1  # another wall

    manifest = {
        "senna_map_version": "1.0",
        "venue_name": venue_name,
        "scope": "apartment",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "grid_resolution_m": 0.10,
        "grid_dimensions": {"width": int(grid.shape[1]), "height": int(grid.shape[0])},
        "coverage_percentage": 87.5,
        "destinations_count": 3,
    }

    destinations = {
        "destinations": [
            {
                "id": "kitchen",
                "name": "Kitchen",
                "aliases": ["kitchen counter", "the kitchen"],
                "grid_x": 5,
                "grid_y": 5,
                "notes": "Counter on the right side",
            },
            {
                "id": "bathroom",
                "name": "Bathroom",
                "aliases": ["restroom", "toilet"],
                "grid_x": 40,
                "grid_y": 10,
                "notes": "Door faces east",
            },
            {
                "id": "front_door",
                "name": "Front Door",
                "aliases": ["entrance", "exit", "door"],
                "grid_x": 25,
                "grid_y": 38,
                "notes": "Main entrance",
            },
        ]
    }

    wifi_fingerprint = {
        "anchors": [
            {"bssid": "AA:BB:CC:11:22:33", "ssid": "AfinHome-5G",   "avg_rssi": -45.5, "observation_count": 120},
            {"bssid": "AA:BB:CC:11:22:34", "ssid": "AfinHome-2.4G", "avg_rssi": -52.3, "observation_count": 115},
            {"bssid": "DD:EE:FF:44:55:66", "ssid": "NeighborWifi",  "avg_rssi": -68.1, "observation_count": 80},
        ]
    }

    # Pack grid as .npz
    grid_buf = io.BytesIO()
    np.savez_compressed(grid_buf, grid=grid)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("grid.npz", grid_buf.getvalue())
        z.writestr("destinations.json", json.dumps(destinations, indent=2))
        z.writestr("wifi_fingerprint.json", json.dumps(wifi_fingerprint, indent=2))
        z.writestr("visual_anchors.bin", b"")  # placeholder

    print(f"Wrote fake .senna to {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fake_apartment.senna"
    make_fake_senna(out)
