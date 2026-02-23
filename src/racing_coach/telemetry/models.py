"""Telemetry data models."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class TelemetryFrame:
    """A single sampled frame of iRacing telemetry data.

    All values are validated/clamped to their documented valid ranges.
    """

    speed: float
    """Vehicle speed in m/s. Clamped to >= 0."""

    throttle: float
    """Throttle pedal position [0.0, 1.0]."""

    brake: float
    """Brake pedal position [0.0, 1.0]."""

    steering_angle: float
    """Steering wheel angle in radians [-π, π]. Positive = right."""

    gear: int
    """Gear position: -1=reverse, 0=neutral, 1-8=forward."""

    rpm: float
    """Engine RPM. Clamped to >= 0."""

    g_force_lon: float
    """Longitudinal G-force (g). Positive = acceleration forward."""

    g_force_lat: float
    """Lateral G-force (g). Positive = acceleration to the right."""

    lap_dist_pct: float
    """Lap distance as fraction [0.0, 1.0]."""

    lap_number: int
    """Current lap number. Clamped to >= 0."""

    lap_time: float
    """Current lap elapsed time in seconds. Clamped to >= 0."""

    def is_valid(self) -> bool:
        """Return True if all fields are finite (no NaN/Inf)."""
        floats = (
            self.speed,
            self.throttle,
            self.brake,
            self.steering_angle,
            self.rpm,
            self.g_force_lon,
            self.g_force_lat,
            self.lap_dist_pct,
            self.lap_time,
        )
        return all(math.isfinite(f) for f in floats)
