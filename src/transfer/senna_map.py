"""SENNA Map File Parser.

Loads a .senna ZIP archive into a typed runtime object that exposes
the occupancy grid, destinations, manifest, and WiFi fingerprint.

Usage:
    from senna.transfer.senna_map import SennaMap
    smap = SennaMap.load("/path/to/map.senna")
    print(smap.venue_name, smap.grid.shape, len(smap.destinations))
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("senna.map")

# Required ZIP entries per the .senna spec
REQUIRED_ENTRIES = {
    "manifest.json",
    "grid.npz",
    "destinations.json",
    "wifi_fingerprint.json",
}
# visual_anchors.bin is optional


@dataclass
class Destination:
    """A named point of interest (kitchen, bathroom door, exit, etc.)."""
    id: str
    name: str
    aliases: list[str]
    grid_x: int
    grid_y: int
    notes: Optional[str] = None


@dataclass
class WiFiAnchor:
    """One observed access point in the venue's WiFi fingerprint."""
    bssid: str
    ssid: Optional[str]
    avg_rssi: float
    observation_count: int


@dataclass
class SennaMap:
    """A parsed .senna map file in memory."""

    # Identification
    venue_name: str
    senna_map_version: str
    scope: Optional[str]
    created_at: Optional[str]

    # Spatial
    grid: np.ndarray                      # 2D uint8 occupancy grid
    grid_resolution_m: float              # meters per cell
    coverage_percentage: Optional[float]

    # Semantics
    destinations: list[Destination]
    wifi_anchors: list[WiFiAnchor]

    # Optional
    visual_anchors: Optional[bytes] = None  # raw bytes; format defined by iOS side

    # Bookkeeping
    source_path: Optional[Path] = None
    raw_manifest: dict = field(default_factory=dict)

    @property
    def grid_width(self) -> int:
        return int(self.grid.shape[1])

    @property
    def grid_height(self) -> int:
        return int(self.grid.shape[0])

    @property
    def physical_width_m(self) -> float:
        return self.grid_width * self.grid_resolution_m

    @property
    def physical_height_m(self) -> float:
        return self.grid_height * self.grid_resolution_m

    def find_destination(self, query: str) -> Optional[Destination]:
        """Look up a destination by name or alias (case-insensitive)."""
        q = query.strip().lower()
        for d in self.destinations:
            if d.name.lower() == q:
                return d
            if any(a.lower() == q for a in d.aliases):
                return d
        return None

    @classmethod
    def load(cls, path: str | Path) -> "SennaMap":
        """Open and parse a .senna file from disk."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f".senna file not found: {path}")

        log.info("Loading SENNA map from %s", path)
        with zipfile.ZipFile(path, "r") as z:
            entries = set(z.namelist())
            missing = REQUIRED_ENTRIES - entries
            if missing:
                raise ValueError(
                    f"Invalid .senna file: missing entries {sorted(missing)}"
                )

            # manifest.json
            with z.open("manifest.json") as f:
                manifest = json.load(f)

            # grid.npz — numpy array
            with z.open("grid.npz") as f:
                buf = io.BytesIO(f.read())
                npz = np.load(buf)
                # The grid is stored under key 'grid' by convention
                if "grid" not in npz.files:
                    raise ValueError(
                        f"grid.npz missing 'grid' array (has: {npz.files})"
                    )
                grid = npz["grid"].astype(np.uint8)

            # destinations.json
            with z.open("destinations.json") as f:
                dest_data = json.load(f)
            destinations = [
                Destination(
                    id=d.get("id", ""),
                    name=d["name"],
                    aliases=d.get("aliases", []),
                    grid_x=int(d["grid_x"]),
                    grid_y=int(d["grid_y"]),
                    notes=d.get("notes"),
                )
                for d in dest_data.get("destinations", [])
            ]

            # wifi_fingerprint.json
            with z.open("wifi_fingerprint.json") as f:
                wifi_data = json.load(f)
            wifi_anchors = [
                WiFiAnchor(
                    bssid=w["bssid"],
                    ssid=w.get("ssid"),
                    avg_rssi=float(w.get("avg_rssi", -100.0)),
                    observation_count=int(w.get("observation_count", 1)),
                )
                for w in wifi_data.get("anchors", [])
            ]

            # visual_anchors.bin — optional
            visual_anchors: Optional[bytes] = None
            if "visual_anchors.bin" in entries:
                with z.open("visual_anchors.bin") as f:
                    visual_anchors = f.read()
                if not visual_anchors:
                    visual_anchors = None  # empty bytes treated as absent

        log.info(
            "Parsed map: venue=%r grid=%dx%d destinations=%d wifi=%d",
            manifest.get("venue_name"),
            grid.shape[1], grid.shape[0],
            len(destinations), len(wifi_anchors),
        )

        return cls(
            venue_name=manifest.get("venue_name", "Unknown"),
            senna_map_version=manifest.get("senna_map_version", "?"),
            scope=manifest.get("scope"),
            created_at=manifest.get("created_at"),
            grid=grid,
            grid_resolution_m=float(manifest.get("grid_resolution_m", 0.10)),
            coverage_percentage=manifest.get("coverage_percentage"),
            destinations=destinations,
            wifi_anchors=wifi_anchors,
            visual_anchors=visual_anchors,
            source_path=path,
            raw_manifest=manifest,
        )


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if len(sys.argv) < 2:
        print("Usage: python -m src.transfer.senna_map <path-to-.senna>")
        sys.exit(1)
    smap = SennaMap.load(sys.argv[1])
    print()
    print(f"Venue:        {smap.venue_name}")
    print(f"Version:      {smap.senna_map_version}")
    print(f"Scope:        {smap.scope}")
    print(f"Grid:         {smap.grid_width} x {smap.grid_height} cells")
    print(f"Resolution:   {smap.grid_resolution_m} m/cell")
    print(f"Physical:     {smap.physical_width_m:.2f} m x {smap.physical_height_m:.2f} m")
    print(f"Coverage:     {smap.coverage_percentage}%")
    print(f"Destinations: {len(smap.destinations)}")
    for d in smap.destinations:
        aliases = f" ({', '.join(d.aliases)})" if d.aliases else ""
        print(f"  - {d.name}{aliases} at ({d.grid_x}, {d.grid_y})")
    print(f"WiFi anchors: {len(smap.wifi_anchors)}")
