"""TelemetryParser — converts raw iRacing SDK data to TelemetryFrame."""

from __future__ import annotations

import math

from racing_coach.telemetry.models import TelemetryFrame

_G = 9.80665  # m/s² per standard gravity

# iRacing SDK field name → (TelemetryFrame field, conversion fn, clamp_min, clamp_max)
# clamp_min/max of None means no bound on that side.
_FIELD_MAP: tuple[tuple[str, str, float | None, float | None], ...] = (
    # raw_key           frame_field        min    max
    ("Speed",               "speed",           0.0,  None),
    ("Throttle",            "throttle",        0.0,  1.0),
    ("Brake",               "brake",           0.0,  1.0),
    ("SteeringWheelAngle",  "steering_angle",  None, None),
    ("RPM",                 "rpm",             0.0,  None),
    ("LapDistPct",          "lap_dist_pct",    0.0,  1.0),
    ("LapCurrentLapTime",   "lap_time",        0.0,  None),
)

_INT_FIELD_MAP: tuple[tuple[str, str, int | None, int | None], ...] = (
    ("Gear",  "gear",       -1, 8),
    ("Lap",   "lap_number",  0, None),
)


def _sanitize(value: float, lo: float | None, hi: float | None) -> float:
    """Return value clamped to [lo, hi], with NaN/Inf replaced by lo (or 0)."""
    if not math.isfinite(value):
        value = lo if lo is not None else 0.0
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value


def _sanitize_int(value: int, lo: int | None, hi: int | None) -> int:
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value


class TelemetryParser:
    """Parses a raw iRacing telemetry dict into a :class:`TelemetryFrame`.

    The raw dict uses iRacing SDK field names (e.g. ``"Speed"``, ``"Throttle"``).
    Invalid or out-of-range values are silently clamped.
    """

    def parse(self, raw: dict) -> TelemetryFrame:
        """Convert *raw* iRacing data snapshot to a validated :class:`TelemetryFrame`."""
        kwargs: dict = {}

        for raw_key, frame_field, lo, hi in _FIELD_MAP:
            val = float(raw.get(raw_key) or 0.0)
            kwargs[frame_field] = _sanitize(val, lo, hi)

        for raw_key, frame_field, lo, hi in _INT_FIELD_MAP:
            val = int(raw.get(raw_key) or 0)
            kwargs[frame_field] = _sanitize_int(val, lo, hi)

        # G-force: iRacing gives m/s², convert to g
        lon_raw = float(raw.get("LongAccel") or 0.0)
        lat_raw = float(raw.get("LatAccel") or 0.0)
        kwargs["g_force_lon"] = _sanitize(lon_raw / _G, None, None)
        kwargs["g_force_lat"] = _sanitize(lat_raw / _G, None, None)

        return TelemetryFrame(**kwargs)
