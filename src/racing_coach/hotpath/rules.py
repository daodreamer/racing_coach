"""Hot-path rules — BrakePointCue and LockAlertRule."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from racing_coach.telemetry.models import TelemetryFrame


@dataclass
class CooldownTracker:
    """Prevents a rule from firing more than once per *cooldown_s* seconds."""

    cooldown_s: float
    _last_fire: float = field(default=-999.0, init=False, repr=False)

    def can_fire(self) -> bool:
        """Return True if enough time has passed since the last fire."""
        return (time.monotonic() - self._last_fire) >= self.cooldown_s

    def mark_fired(self) -> None:
        """Record that the rule just fired."""
        self._last_fire = time.monotonic()


class BrakePointCue:
    """Fires a cue when the car is within *distance_m* of a reference brake point.

    Deduplicates: fires at most once per (lap_number, corner_id) pair.

    Parameters
    ----------
    brake_pcts:
        Mapping of corner_id → lap_dist_pct of the reference brake point.
    track_length_m:
        Total track length in metres (used to convert distance to pct).
    distance_m:
        How far ahead of the brake point to start warning the driver.
    """

    def __init__(
        self,
        brake_pcts: dict[int, float],
        track_length_m: float = 4000.0,
        distance_m: float = 50.0,
    ) -> None:
        self._brake_pcts = brake_pcts
        self._track_length_m = track_length_m
        self._distance_m = distance_m
        self._fired: set[tuple[int, int]] = set()

    def check(self, frame: TelemetryFrame) -> list[int]:
        """Return a list of corner_ids for which a brake cue should fire."""
        triggered: list[int] = []
        lap = frame.lap_number
        pos = frame.lap_dist_pct
        window_pct = self._distance_m / self._track_length_m

        for corner_id, brake_pct in self._brake_pcts.items():
            key = (lap, corner_id)
            if key in self._fired:
                continue
            delta_pct = brake_pct - pos
            if 0.0 < delta_pct <= window_pct:
                triggered.append(corner_id)
                self._fired.add(key)

        return triggered


class LockAlertRule:
    """Detects wheel lock from sudden deceleration combined with high brake pressure.

    Uses two-frame differentiation of speed to estimate instantaneous deceleration.
    A :class:`CooldownTracker` prevents repeated alerts during the same braking zone.

    Parameters
    ----------
    decel_threshold:
        Deceleration in m/s² that triggers the alert (default 12 m/s² ≈ 1.2 g).
    brake_min:
        Minimum brake pressure [0.0, 1.0] required to trigger the check.
    cooldown_s:
        Minimum seconds between consecutive alerts.
    sample_dt:
        Expected time step between frames in seconds (default 1/60 s).
    """

    def __init__(
        self,
        decel_threshold: float = 12.0,
        brake_min: float = 0.7,
        cooldown_s: float = 3.0,
        sample_dt: float = 1.0 / 60.0,
    ) -> None:
        self._decel_threshold = decel_threshold
        self._brake_min = brake_min
        self._cooldown = CooldownTracker(cooldown_s)
        self._dt = sample_dt
        self._prev_speed: float | None = None

    def check(self, frame: TelemetryFrame) -> bool:
        """Return True if a wheel lock is detected on this frame."""
        speed = frame.speed
        prev = self._prev_speed
        self._prev_speed = speed

        if prev is None:
            return False
        if frame.brake < self._brake_min:
            return False
        if not self._cooldown.can_fire():
            return False

        decel = (prev - speed) / self._dt
        if decel >= self._decel_threshold:
            self._cooldown.mark_fired()
            return True

        return False
