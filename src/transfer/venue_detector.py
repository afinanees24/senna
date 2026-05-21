"""SENNA Venue Detector.

The boot-time function that:
  1. Scans WiFi for nearby BSSIDs
  2. Asks Supabase which venue matches
  3. Downloads the .senna file
  4. Parses it into a SennaMap

Returns the SennaMap, or None if no venue was matched.

Usage:
    from senna.transfer.venue_detector import detect_venue
    smap = detect_venue()
    if smap:
        print(f"You are at: {smap.venue_name}")
"""
from __future__ import annotations

import logging
from typing import Optional

from .map_fetcher import MapFetcher
from .senna_map import SennaMap
from .wifi_scanner import scan_bssids

log = logging.getLogger("senna.venue_detector")


def detect_venue() -> Optional[SennaMap]:
    """Run the full boot-time venue detection pipeline."""
    log.info("=== Starting venue detection ===")

    bssids = scan_bssids()
    if not bssids:
        log.warning("No WiFi APs found; cannot detect venue")
        return None

    fetcher = MapFetcher()
    map_path = fetcher.find_and_fetch_map(bssids)
    if not map_path:
        log.info("No venue matched WiFi fingerprint")
        return None

    smap = SennaMap.load(map_path)
    log.info("=== Venue detected: %s ===", smap.venue_name)
    return smap


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    smap = detect_venue()
    if smap:
        print()
        print(f"Detected venue: {smap.venue_name}")
        print(f"Map: {smap.grid_width}x{smap.grid_height} cells")
        print(f"Destinations: {len(smap.destinations)}")
        for d in smap.destinations:
            print(f"  - {d.name}")
    else:
        print("No venue detected")
