"""SENNA brain — top-level orchestrator (state machine).

Phase 1: single mode (NAVIGATION). Holds a SennaMap, a PositionTracker,
an AudioOut, and a current path. Caller drives tick() in a loop; each
tick checks position, asks RouteFollower for the next cue, and emits
it via AudioOut — with dedup so the same cue doesn't repeat every tick.

Future phases add modes (LOCALIZATION_QUERY, OBJECT_GUIDANCE, etc.),
voice-command intake, sensor fusion, lost-position recovery, and more.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from src.audio import AudioOut
from src.navigation import plan_route
from src.navigation.route_follower import RouteFollower
from src.sensors.position import PositionTracker
from src.transfer.senna_map import SennaMap


class Mode(Enum):
    IDLE = "idle"
    NAVIGATING = "navigating"
    ARRIVED = "arrived"


def _cue_signature(cue: Optional[dict]) -> Optional[tuple]:
    """Identity tuple for dedup: action + distance rounded to whole meters.

    Two cues with the same action and same rounded distance are treated
    as duplicates and only the first is emitted.
    """
    if cue is None:
        return None
    return (cue.get("action"), round(cue.get("distance_m", 0)))


class Navigator:
    """Top-level state machine. Phase 1: navigation only."""

    def __init__(
        self,
        smap: SennaMap,
        position: PositionTracker,
        audio: AudioOut,
    ) -> None:
        self._map = smap
        self._pos = position
        self._audio = audio
        self._mode: Mode = Mode.IDLE
        self._follower: Optional[RouteFollower] = None
        self._destination_name: Optional[str] = None
        self._last_cue: Optional[dict] = None

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def destination(self) -> Optional[str]:
        return self._destination_name

    def set_destination(self, name: str) -> bool:
        """Plan a route to the named destination from current position.

        Returns True if a route was found, False otherwise. On success,
        transitions to NAVIGATING. On failure, emits a system cue and
        stays in current mode.
        """
        current_cell = self._pos.get_cell()
        path = plan_route(self._map, current_cell, name)

        if path is None:
            self._audio.speak_cue({
                "type": "system",
                "text": f"I can't find a route to {name}.",
            })
            return False

        self._follower = RouteFollower(path, self._map.grid_resolution_m)
        self._destination_name = name
        self._mode = Mode.NAVIGATING
        self._last_cue = None  # fresh route, no prior cue to dedup against
        self._audio.speak_cue({
            "type": "system",
            "text": f"Navigating to {name}.",
        })
        return True

    def cancel(self) -> None:
        """Abandon current route. Returns to IDLE."""
        if self._mode == Mode.NAVIGATING:
            self._audio.speak_cue({"type": "system", "text": "Cancelled."})
        self._follower = None
        self._destination_name = None
        self._mode = Mode.IDLE
        self._last_cue = None

    def tick(self) -> None:
        """Called periodically by the main loop. Emits next cue if needed."""
        if self._mode != Mode.NAVIGATING or self._follower is None:
            return

        cell = self._pos.get_cell()
        heading = self._pos.get_heading()
        cue = self._follower.next_cue(cell, heading)

        if cue is None:
            # Off route. Replan from current position.
            self._audio.speak_cue({
                "type": "system",
                "text": "Off route. Replanning.",
            })
            assert self._destination_name is not None
            self.set_destination(self._destination_name)
            return

        if cue.get("action") == "destination_reached":
            self._audio.speak_cue(cue)
            self._audio.speak_cue({
                "type": "system",
                "text": f"You have arrived at {self._destination_name}.",
            })
            self._follower = None
            self._destination_name = None
            self._mode = Mode.ARRIVED
            self._last_cue = None
            return

        # Dedup: skip identical cues (same action + same rounded distance).
        if _cue_signature(cue) == _cue_signature(self._last_cue):
            return

        self._last_cue = cue
        self._audio.speak_cue(cue)
