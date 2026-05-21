"""SENNA Map Fetcher.

Queries the Supabase backend for venues matching observed WiFi BSSIDs,
downloads the matching .senna file, and caches it locally.

Usage:
    from senna.transfer.map_fetcher import MapFetcher
    fetcher = MapFetcher()
    bssids = ["AA:BB:CC:11:22:33", "DD:EE:FF:44:55:66"]
    map_path = fetcher.find_and_fetch_map(bssids)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from supabase import create_client, Client

CONFIG_PATH = Path("/home/pi/senna/config/supabase.env")
CACHE_DIR = Path("/home/pi/senna/maps/cache")
STORAGE_BUCKET = "senna-maps"
MIN_MATCHING_BSSIDS = 2  # need at least this many BSSIDs matching to trust the venue

log = logging.getLogger("senna.map_fetcher")


def _load_config() -> dict[str, str]:
    """Read SUPABASE_URL and SUPABASE_KEY from the config file."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    config = {}
    with open(CONFIG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip()

    for required in ("SUPABASE_URL", "SUPABASE_KEY"):
        if required not in config:
            raise ValueError(f"Missing {required} in {CONFIG_PATH}")

    return config


class MapFetcher:
    """Connects to Supabase, matches venues by WiFi, downloads maps."""

    def __init__(self):
        config = _load_config()
        self.supabase: Client = create_client(
            config["SUPABASE_URL"],
            config["SUPABASE_KEY"],
        )
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        log.info("MapFetcher initialized, cache at %s", CACHE_DIR)

    def match_venue(self, bssids: list[str]) -> Optional[dict]:
        """Given a list of BSSIDs, return the best-matching venue (or None).

        Returns a dict with keys:
            map_id, venue_id, venue_name, storage_path,
            matching_bssids, total_bssids, match_score
        """
        if not bssids:
            return None

        log.info("Querying Supabase for %d BSSIDs", len(bssids))
        try:
            response = self.supabase.rpc(
                "match_venue_by_bssids",
                {"query_bssids": bssids},
            ).execute()
        except Exception as e:
            log.error("Supabase query failed: %s", e)
            return None

        results = response.data
        if not results:
            log.info("No venue matched")
            return None

        best = results[0]
        if best["matching_bssids"] < MIN_MATCHING_BSSIDS:
            log.info(
                "Best match has only %d BSSIDs (need %d), rejecting",
                best["matching_bssids"], MIN_MATCHING_BSSIDS,
            )
            return None

        log.info(
            "Matched venue '%s' with %d/%d BSSIDs (score=%.2f)",
            best["venue_name"],
            best["matching_bssids"],
            best["total_bssids"],
            best["match_score"],
        )
        return best

    def fetch_map(self, storage_path: str, map_id: str) -> Path:
        """Download the .senna file from storage; cache locally.

        Returns the path to the cached file. Re-uses cache if present.
        """
        local_path = CACHE_DIR / f"{map_id}.senna"

        if local_path.exists():
            log.info("Using cached map: %s", local_path)
            return local_path

        log.info("Downloading %s from storage bucket %s", storage_path, STORAGE_BUCKET)
        try:
            data = self.supabase.storage.from_(STORAGE_BUCKET).download(storage_path)
        except Exception as e:
            log.error("Download failed: %s", e)
            raise

        local_path.write_bytes(data)
        log.info("Saved %d bytes to %s", len(data), local_path)
        return local_path

    def find_and_fetch_map(self, bssids: list[str]) -> Optional[Path]:
        """Convenience: match venue and download in one call.

        Returns path to cached .senna file, or None if no match.
        """
        match = self.match_venue(bssids)
        if not match:
            return None
        return self.fetch_map(match["storage_path"], match["map_id"])


if __name__ == "__main__":
    # Quick self-test when run as a script
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    fetcher = MapFetcher()

    test_bssids = [
        "AA:BB:CC:11:22:33",
        "AA:BB:CC:11:22:34",
        "DD:EE:FF:44:55:66",
        "FF:FF:FF:FF:FF:FF",
    ]
    print("Testing match_venue with fake BSSIDs...")
    match = fetcher.match_venue(test_bssids)
    if match:
        print(f"  Matched: {match['venue_name']}")
        print(f"  Map ID: {match['map_id']}")
        print(f"  Score: {match['matching_bssids']}/{match['total_bssids']}")
    else:
        print("  No match")
