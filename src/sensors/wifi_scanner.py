"""WiFi access point scanner using nmcli.

Returns a list of currently-visible APs with BSSID, signal strength
(0-100 scale from nmcli), and SSID. Used by the venue localizer to
match against fingerprints in .senna files.

Requires nmcli (NetworkManager). No sudo needed for scanning.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class WifiObservation:
    bssid: str           # canonical lowercase form, e.g. "dc:69:b5:f6:02:e6"
    signal: int          # 0-100, higher = stronger
    ssid: str            # may be empty for hidden networks

    def __repr__(self) -> str:
        ssid = self.ssid if self.ssid else "<hidden>"
        return f"<WifiObs {self.bssid} {self.signal:3d}/100 {ssid!r}>"


def _unescape_nmcli(field: str) -> str:
    r"""nmcli -t escapes ':' as '\:' and '\' as '\\'. Reverse it."""
    out = []
    i = 0
    while i < len(field):
        if field[i] == "\\" and i + 1 < len(field):
            out.append(field[i + 1])
            i += 2
        else:
            out.append(field[i])
            i += 1
    return "".join(out)


def _normalize_bssid(bssid: str) -> str:
    """Canonical form: lowercase, colon-separated."""
    return bssid.lower()


def scan(timeout_sec: float = 5.0) -> list[WifiObservation]:
    """Run nmcli to scan WiFi APs. Returns one observation per visible AP.

    On any error (nmcli missing, scan timeout, parse failure), returns
    an empty list rather than raising.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "BSSID,SIGNAL,SSID", "dev", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode != 0:
        return []

    observations: list[WifiObservation] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        # nmcli -t output: BSSID:SIGNAL:SSID, but BSSID has escaped colons.
        # Walk the string and split only on UNescaped colons.
        fields: list[str] = []
        buf: list[str] = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                buf.append(line[i])
                buf.append(line[i + 1])
                i += 2
            elif ch == ":":
                fields.append("".join(buf))
                buf = []
                i += 1
            else:
                buf.append(ch)
                i += 1
        fields.append("".join(buf))

        if len(fields) < 3:
            continue

        bssid_raw, signal_str, ssid_raw = fields[0], fields[1], fields[2]
        try:
            signal = int(signal_str)
        except ValueError:
            continue

        observations.append(WifiObservation(
            bssid=_normalize_bssid(_unescape_nmcli(bssid_raw)),
            signal=signal,
            ssid=_unescape_nmcli(ssid_raw),
        ))

    return observations


if __name__ == "__main__":
    obs = scan()
    print(f"Scanned {len(obs)} APs:")
    for o in sorted(obs, key=lambda x: -x.signal):
        print(f"  {o}")
