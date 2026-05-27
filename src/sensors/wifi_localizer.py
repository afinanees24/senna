"""WiFi-based venue identification.

Loads wifi_fingerprint.json from each .senna file in a search directory,
scores a live scan against each, returns the best venue match.

Used at startup to identify which venue the user is in, so the right
.senna map gets loaded. Phase 6 only — within-venue position refinement
comes from vision (Phase 9).

Algorithm: cosine similarity on overlapping BSSIDs' signal strengths.

  - Each venue's fingerprint is a dict {bssid -> avg_rssi}
  - A live scan is a dict {bssid -> signal (0-100)}
  - Convert nmcli signal (0-100) to approximate dBm using the standard
    nmcli formula: dBm ≈ (signal/2) - 100
  - Take BSSIDs present in both venue fingerprint and live scan
  - Score = cosine similarity of their RSSI vectors
  - Best score wins, IF above a confidence threshold; else "unknown"
"""
from __future__ import annotations

import io
import json
import logging
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.sensors.wifi_scanner import WifiObservation, scan as wifi_scan

log = logging.getLogger("senna.wifi_localizer")


# Minimum cosine similarity to call a venue "identified".
# Tuned conservatively — false positives are worse than false negatives.
MIN_CONFIDENCE = 0.7

# Minimum number of overlapping BSSIDs to even attempt scoring.
# With fewer than this, the match is too speculative to trust.
MIN_OVERLAP = 3


@dataclass(frozen=True)
class VenueMatch:
    senna_path: Path
    venue_name: str
    confidence: float       # 0-1, higher = better
    overlapping_bssids: int


def _signal_to_dbm(signal: int) -> float:
    """nmcli signal (0-100) -> approximate dBm.

    nmcli uses: signal_percent = max(0, min(100, 2 * (dBm + 100)))
    Inverting: dBm = (signal / 2) - 100
    """
    return (signal / 2.0) - 100.0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors of equal length."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _load_fingerprint(senna_path: Path) -> tuple[str, dict[str, float]] | None:
    """Extract (venue_name, {bssid -> avg_rssi}) from a .senna file.

    Returns None on any failure (file missing, malformed, no fingerprint).
    """
    try:
        with zipfile.ZipFile(senna_path, "r") as z:
            names = set(z.namelist())
            if "wifi_fingerprint.json" not in names:
                return None
            with z.open("wifi_fingerprint.json") as f:
                wifi_data = json.load(f)

            venue_name = "Unknown"
            if "manifest.json" in names:
                with z.open("manifest.json") as f:
                    manifest = json.load(f)
                    venue_name = manifest.get("venue_name", "Unknown")
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, OSError) as e:
        log.warning("Couldn't read fingerprint from %s: %s", senna_path, e)
        return None

    anchors = wifi_data.get("anchors", [])
    if not anchors:
        return None

    fingerprint: dict[str, float] = {}
    for a in anchors:
        bssid = a.get("bssid", "").lower()
        rssi = a.get("avg_rssi")
        if bssid and rssi is not None:
            fingerprint[bssid] = float(rssi)

    return (venue_name, fingerprint)


def score_match(
    venue_fingerprint: dict[str, float],
    live_scan: list[WifiObservation],
) -> tuple[float, int]:
    """Score a live scan against a venue fingerprint.

    Returns (cosine_similarity, n_overlapping_bssids).
    """
    live: dict[str, float] = {o.bssid: _signal_to_dbm(o.signal) for o in live_scan}
    shared = sorted(set(venue_fingerprint) & set(live))

    if len(shared) < MIN_OVERLAP:
        return (0.0, len(shared))

    venue_vec = [venue_fingerprint[b] for b in shared]
    live_vec = [live[b] for b in shared]
    return (_cosine_similarity(venue_vec, live_vec), len(shared))


def identify_venue(
    search_dir: Path,
    live_scan: Optional[list[WifiObservation]] = None,
) -> Optional[VenueMatch]:
    """Scan WiFi and identify which venue (if any) the user is in.

    Args:
        search_dir: Directory containing .senna files to search.
        live_scan: Optional pre-captured scan; if None, runs wifi_scan() now.

    Returns:
        Best-matching VenueMatch with confidence above threshold, or None
        if no venue matches confidently enough.
    """
    if live_scan is None:
        live_scan = wifi_scan()

    if not live_scan:
        log.warning("Live WiFi scan returned no observations")
        return None

    senna_files = sorted(search_dir.glob("*.senna"))
    if not senna_files:
        log.warning("No .senna files found in %s", search_dir)
        return None

    best: Optional[VenueMatch] = None
    for senna_path in senna_files:
        loaded = _load_fingerprint(senna_path)
        if loaded is None:
            continue
        venue_name, fingerprint = loaded
        score, overlap = score_match(fingerprint, live_scan)
        log.info(
            "  %s (%s): score=%.3f overlap=%d",
            venue_name, senna_path.name, score, overlap,
        )
        if score >= MIN_CONFIDENCE and (best is None or score > best.confidence):
            best = VenueMatch(
                senna_path=senna_path,
                venue_name=venue_name,
                confidence=score,
                overlapping_bssids=overlap,
            )

    return best


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    search_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "senna" / "maps" / "cache"
    print(f"Searching: {search_dir}")
    match = identify_venue(search_dir)
    if match:
        print(f"\nMatched: {match.venue_name}")
        print(f"  File:       {match.senna_path}")
        print(f"  Confidence: {match.confidence:.3f}")
        print(f"  Overlap:    {match.overlapping_bssids} BSSIDs")
    else:
        print("\nNo venue identified.")
