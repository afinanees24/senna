"""SENNA audio output interface.

Defines the abstract AudioOut contract that all audio backends must
satisfy, plus a StdoutAudio impl for development and testing.

The state machine emits structured cue dicts; the AudioOut backend is
responsible for turning them into actual sound (TTS, spatial audio,
earcons, etc.) Abdul's senna_audio package will provide the real impl.

Cue dict schema (the subset needed for Phase 1; will grow later):

    {"type": "navigation", "action": "turn_left" | "turn_right" |
                                     "forward" | "destination_reached",
     "distance_m": float}

    {"type": "system",  "text": str}

    {"type": "warning", "text": str, "urgency": "normal" | "high"}
"""
from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from typing import Any


class AudioOut(ABC):
    """Abstract base for any audio output backend."""

    @abstractmethod
    def speak_cue(self, cue: dict[str, Any]) -> None:
        """Emit a single cue. Should not block longer than necessary.

        Implementations are responsible for queueing/serializing cues
        so rapid successive calls don't interleave audio.
        """
        ...

    @abstractmethod
    def stop_speaking(self) -> None:
        """Cancel any in-flight speech immediately.

        Used when the user interrupts (Phase 4+). Phase 1 impls may
        treat this as a no-op.
        """
        ...


class StdoutAudio(AudioOut):
    """Development backend. Prints cues to stdout with timestamps.

    Lets the state machine be developed and tested without depending on
    real audio hardware or Abdul's senna_audio being ready.
    """

    def __init__(self, prefix: str = "[AUDIO]") -> None:
        self._prefix = prefix
        self._t0 = time.monotonic()

    def speak_cue(self, cue: dict[str, Any]) -> None:
        elapsed = time.monotonic() - self._t0
        ctype = cue.get("type", "?")

        if ctype == "navigation":
            action = cue.get("action", "?")
            dist = cue.get("distance_m")
            dist_str = f" ({dist:.1f}m)" if isinstance(dist, (int, float)) else ""
            msg = f"{action}{dist_str}"
        elif ctype == "system":
            msg = cue.get("text", "")
        elif ctype == "warning":
            urgency = cue.get("urgency", "normal")
            msg = f"[{urgency.upper()}] {cue.get('text', '')}"
        else:
            msg = repr(cue)

        print(f"{self._prefix} {elapsed:7.2f}s  {ctype:12s}  {msg}", flush=True)

    def stop_speaking(self) -> None:
        # No-op for stdout — nothing to interrupt.
        pass
