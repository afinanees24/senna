"""SENNA WiFi Scanner.

Wraps `iwlist scan` to enumerate nearby WiFi access points and return their BSSIDs.
This is the input to the venue-matching pipeline.

Usage:
    from senna.transfer.wifi_scanner import scan_bssids
    bssids = scan_bssids()
    print(bssids)  # ['AA:BB:CC:11:22:33', ...]
"""
from __future__ import annotations

import logging
import re
import subprocess
from typing import Optional

log = logging.getLogger("senna.wifi_scanner")

# iwlist outputs BSSIDs after "Address: " on each "Cell" line
BSSID_RE = re.compile(r"Address:\s*([0-9A-Fa-f:]{17})")
SSID_RE = re.compile(r'ESSID:"([^"]*)"')
RSSI_RE = re.compile(r"Signal level=(-?\d+)\s*dBm")


def scan_bssids(interface: str = "wlan0") -> list[str]:
    """Run a passive WiFi scan; return list of nearby BSSIDs (uppercase, colon-sep)."""
    bssids = []
    for ap in scan_access_points(interface):
        bssids.append(ap["bssid"])
    return bssids


def scan_access_points(interface: str = "wlan0") -> list[dict]:
    """Run a passive WiFi scan; return list of access points with bssid, ssid, rssi."""
    log.info("Scanning WiFi on %s", interface)
    try:
        result = subprocess.run(
            ["sudo", "iwlist", interface, "scan"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        log.error("iwlist scan failed: %s", e.stderr)
        return []
    except subprocess.TimeoutExpired:
        log.error("iwlist scan timed out")
        return []

    output = result.stdout
    access_points: list[dict] = []
    current: Optional[dict] = None

    for line in output.splitlines():
        line = line.strip()

        # New cell starts with "Cell xx - Address: ..."
        m = BSSID_RE.search(line)
        if m and "Cell" in line:
            if current:
                access_points.append(current)
            current = {
                "bssid": m.group(1).upper(),
                "ssid": None,
                "rssi": None,
            }
            continue

        if current is None:
            continue

        m = SSID_RE.search(line)
        if m:
            current["ssid"] = m.group(1)
            continue

        m = RSSI_RE.search(line)
        if m:
            current["rssi"] = int(m.group(1))
            continue

    if current:
        access_points.append(current)

    log.info("Found %d access points", len(access_points))
    return access_points


if __name__ == "__main__":
    import json
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    aps = scan_access_points()
    print(json.dumps(aps, indent=2))
    print()
    print(f"Total: {len(aps)} access points")
