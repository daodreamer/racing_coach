"""Analysis data models for Sprint 3 (reference lap comparison & error detection)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LapFrame:
    """A single telemetry frame used as input for all analysis modules.

    Can be constructed directly in tests or converted from storage dicts via
    :meth:`from_storage_dict`.
    """

    lap_dist_pct: float
    """Fraction of lap completed [0.0, 1.0]."""

    lap_time: float
    """Elapsed lap time in seconds (starts at 0 at the start/finish line)."""

    speed: float
    """Vehicle speed in m/s."""

    throttle: float
    """Throttle pedal position [0.0, 1.0]."""

    brake: float
    """Brake pedal position [0.0, 1.0]."""

    steering_angle: float
    """Steering wheel angle in radians (positive = right)."""

    @classmethod
    def from_storage_dict(cls, d: dict) -> LapFrame:
        """Create a :class:`LapFrame` from a TelemetryStorage row dict."""
        return cls(
            lap_dist_pct=float(d["lap_dist_pct"]),
            lap_time=float(d["lap_time"]),
            speed=float(d["speed"]),
            throttle=float(d["throttle"]),
            brake=float(d["brake"]),
            steering_angle=float(d["steering_angle"]),
        )


@dataclass
class CornerDelta:
    """Time delta summary for a single corner.

    Positive values mean the user was *slower* than the reference;
    negative values mean *faster*.
    """

    corner_id: int

    delta_entry: float
    """Time delta at the corner entry point (user_time - ref_time), seconds."""

    delta_apex: float
    """Time delta at the apex point, seconds."""

    delta_exit: float
    """Time delta at the corner exit point, seconds."""

    delta_total: float
    """Time gained/lost *within* this corner = ``delta_exit - delta_entry``, seconds.
    Positive = time lost in this corner.
    """


@dataclass
class BrakingEvent:
    """Braking analysis result for a single corner approach."""

    corner_id: int

    brake_point_pct: float
    """lap_dist_pct where user first applied brake > threshold."""

    ref_brake_point_pct: float
    """lap_dist_pct where reference first applied brake."""

    brake_point_delta_m: float
    """Distance difference (user - ref) in metres.  Positive = user braked *later*."""

    peak_pressure: float
    """Maximum brake pressure [0.0, 1.0] in the braking zone."""

    time_to_peak_s: float
    """Seconds from brake start to peak pressure."""

    trail_brake_linearity: float
    """R² of a linear fit to the brake *release* phase [0.0, 1.0].
    1.0 = perfectly smooth linear release; 0.0 = sudden step release.
    """

    lock_detected: bool
    """True if wheel-lock symptoms (high brake + excessive deceleration) were detected."""


@dataclass
class ThrottleEvent:
    """Throttle analysis result for a single corner exit."""

    corner_id: int

    throttle_point_pct: float
    """lap_dist_pct of the first frame after the apex zone where throttle > threshold."""

    too_early_full_throttle: bool
    """True if full throttle (≥ 99%) was applied while steering angle > threshold."""

    overlap_count: int
    """Number of frames where both brake > 0.05 and throttle > 0.05 simultaneously."""


@dataclass
class ApexSpeedResult:
    """Apex minimum-speed analysis for a single corner."""

    corner_id: int

    min_speed_mps: float
    """User's minimum speed in the apex zone (m/s)."""

    ref_min_speed_mps: float
    """Reference lap minimum speed in the apex zone (m/s)."""

    delta_kph: float
    """Speed difference (user - ref) in km/h.  Negative = user was slower at apex."""

    too_slow: bool
    """True if ``delta_kph < -threshold``  (user was more than *threshold* km/h slower)."""
