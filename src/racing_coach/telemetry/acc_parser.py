"""ACCParser — converts raw ACC shared memory data to TelemetryFrame."""

from __future__ import annotations

import math

from racing_coach.telemetry.models import TelemetryFrame


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


class ACCParser:
    """Parses a raw ACC telemetry dict (from ACCLiveConnection.read_frame) into a TelemetryFrame.

    The raw dict uses ACC shared memory field names (e.g. ``"speedKmh"``, ``"gas"``).
    Invalid or out-of-range values are silently clamped.
    """

    def parse(self, raw: dict) -> TelemetryFrame:
        """Convert *raw* ACC data snapshot to a validated :class:`TelemetryFrame`."""
        speed_kmh = float(raw.get("speedKmh") or 0.0)
        speed = _sanitize(speed_kmh / 3.6, 0.0, None)

        throttle = _sanitize(float(raw.get("gas") or 0.0), 0.0, 1.0)
        brake = _sanitize(float(raw.get("brake") or 0.0), 0.0, 1.0)
        steering_angle = _sanitize(float(raw.get("steerAngle") or 0.0), None, None)
        gear = _sanitize_int(int(raw.get("gear") or 0), -1, 7)
        rpm = _sanitize(float(raw.get("rpms") or 0), 0.0, None)

        # accG is already in G units (ACC SDK stores G directly, not m/s²)
        acc_g = raw.get("accG") or [0.0, 0.0, 0.0]
        g_force_lon = _sanitize(float(acc_g[2]), None, None)
        g_force_lat = _sanitize(-float(acc_g[0]), None, None)  # positive = left → negate

        lap_dist_pct = _sanitize(float(raw.get("normalizedCarPosition") or 0.0), 0.0, 1.0)
        lap_number = _sanitize_int(int(raw.get("completedLaps") or 0), 0, None)
        lap_time_ms = float(raw.get("iCurrentTime") or 0)
        lap_time = _sanitize(lap_time_ms / 1000.0, 0.0, None)

        return TelemetryFrame(
            speed=speed,
            throttle=throttle,
            brake=brake,
            steering_angle=steering_angle,
            gear=gear,
            rpm=rpm,
            g_force_lon=g_force_lon,
            g_force_lat=g_force_lat,
            lap_dist_pct=lap_dist_pct,
            lap_number=lap_number,
            lap_time=lap_time,
        )
