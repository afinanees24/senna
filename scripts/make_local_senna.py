"""Generate a .senna file for the current location, using a live WiFi scan.

For Phase 6 localizer testing. Produces a real .senna fingerprinted
against wherever the Pi is right now. Once Noman's iOS scanner is
producing real venue files, this script is redundant.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sensors.wifi_scanner import scan as wifi_scan


def make_local_senna(out_path: Path, venue_name: str = "Home") -> None:
    print(f"Scanning WiFi at current location...")
    obs = wifi_scan()
    if not obs:
        print("No WiFi observations. Aborting.")
        return

    print(f"Captured {len(obs)} APs.")

    # Convert nmcli signal (0-100) to approximate dBm for the fingerprint.
    anchors = [
        {
            "bssid": o.bssid.upper(),
            "ssid": o.ssid,
            "avg_rssi": (o.signal / 2.0) - 100.0,
            "observation_count": 1,
        }
        for o in obs
    ]

    # Minimal viable grid + destinations so loader doesn't choke.
    grid = np.zeros((20, 20), dtype=np.uint8)
    grid[0, :] = 1
    grid[-1, :] = 1
    grid[:, 0] = 1
    grid[:, -1] = 1

    grid_buf = io.BytesIO()
    np.savez_compressed(grid_buf, grid=grid)

    manifest = {
        "senna_map_version": "1.0",
        "venue_name": venue_name,
        "scope": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "grid_resolution_m": 0.10,
        "grid_dimensions": {"width": 20, "height": 20},
        "coverage_percentage": 100.0,
        "destinations_count": 1,
    }
    destinations = {
        "destinations": [
            {"id": "center", "name": "Center", "aliases": [],
             "grid_x": 10, "grid_y": 10, "notes": ""},
        ]
    }

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("grid.npz", grid_buf.getvalue())
        z.writestr("destinations.json", json.dumps(destinations, indent=2))
        z.writestr("wifi_fingerprint.json", json.dumps({"anchors": anchors}, indent=2))
        z.writestr("visual_anchors.bin", b"")

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "senna" / "maps" / "cache" / "home_test.senna"
    name = sys.argv[2] if len(sys.argv) > 2 else "Home"
    make_local_senna(out, name)
