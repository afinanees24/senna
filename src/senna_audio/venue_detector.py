"""WiFi-based venue identification for SENNA."""

import subprocess
import re
import math
from pathlib import Path
import json


def scan_wifi(interface: str = "wlan0", timeout: int = 10) -> dict[str, float]:
    """Scan all nearby APs. Returns dict of {bssid: signal_dbm}."""
    result = subprocess.run(
        ["sudo", "iw", "dev", interface, "scan"],
        capture_output=True, text=True, timeout=timeout
    )
    fp = {}
    current_bssid = None
    for line in result.stdout.splitlines():
        if line.startswith("BSS "):
            current_bssid = line.split()[1].split("(")[0].lower()
        elif "signal:" in line and current_bssid:
            m = re.search(r"signal:\s*(-?\d+\.?\d*)", line)
            if m:
                fp[current_bssid] = float(m.group(1))
    return fp


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity of two WiFi fingerprints (dicts of bssid → dBm)."""
    def strength(dbm: float) -> float:
        return max(0.0, 100.0 + dbm)

    keys = set(a) | set(b)
    va = [strength(a.get(k, -100)) for k in keys]
    vb = [strength(b.get(k, -100)) for k in keys]
    dot = sum(x * y for x, y in zip(va, vb))
    ma = math.sqrt(sum(x * x for x in va))
    mb = math.sqrt(sum(x * x for x in vb))
    return dot / (ma * mb) if ma and mb else 0.0


class VenueDetector:
    """Identifies the current venue from a set of known venue fingerprints."""

    THRESHOLD_SAME_VENUE = 0.7
    THRESHOLD_DIFFERENT_VENUE = 0.4

    def __init__(self, venues: dict[str, dict[str, float]] | None = None):
        """venues: dict of {venue_id: fingerprint dict from a .senna file}"""
        self._venues = venues or {}

    def register_venue(self, venue_id: str, fingerprint: dict[str, float]) -> None:
        self._venues[venue_id] = fingerprint

    def load_from_senna_dir(self, senna_dir: Path) -> None:
        """Load wifi_fingerprint.json from each .senna venue directory."""
        for venue_dir in Path(senna_dir).iterdir():
            wifi_file = venue_dir / "wifi_fingerprint.json"
            if wifi_file.exists():
                self._venues[venue_dir.name] = json.loads(wifi_file.read_text())

    def detect(self) -> tuple[str | None, float]:
        """Scan WiFi and return (best_venue_id, confidence) or (None, 0)."""
        live = scan_wifi()
        if not self._venues:
            return None, 0.0
        scores = {
            vid: cosine_similarity(live, fp) for vid, fp in self._venues.items()
        }
        best = max(scores, key=scores.get)
        return (best, scores[best]) if scores[best] >= self.THRESHOLD_SAME_VENUE else (None, scores[best])


if __name__ == "__main__":
    # Quick self-test
    fp = scan_wifi()
    print(f"Live scan: {len(fp)} APs, top 5:")
    for bssid, signal in sorted(fp.items(), key=lambda x: -x[1])[:5]:
        print(f"  {bssid}: {signal:.0f} dBm")
