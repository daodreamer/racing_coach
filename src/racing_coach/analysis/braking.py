"""Braking analysis — S3-US3.

Analyses the braking event for each corner:
  - Brake-point position (and delta vs reference)
  - Peak pressure and time to reach it
  - Trail-braking linearity (R² of the release phase)
  - Wheel-lock detection
"""

from __future__ import annotations

from racing_coach.analysis.models import BrakingEvent, LapFrame
from racing_coach.track.models import Corner

# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _linear_r_squared(values: list[float]) -> float:
    """Return R² of a linear least-squares fit to *values* (x = 0, 1, ..., n-1).

    Returns 1.0 when n < 3 (trivially linear) or when all values are constant.
    """
    n = len(values)
    if n < 3:
        return 1.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    sxy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    sxx = sum((i - x_mean) ** 2 for i in range(n))
    if sxx < 1e-12:
        return 1.0
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    ss_res = sum((v - (slope * i + intercept)) ** 2 for i, v in enumerate(values))
    ss_tot = sum((v - y_mean) ** 2 for v in values)
    if ss_tot < 1e-12:
        return 1.0
    return max(0.0, 1.0 - ss_res / ss_tot)


# ---------------------------------------------------------------------------
# Braking analyzer
# ---------------------------------------------------------------------------

class BrakingAnalyzer:
    """Analyse braking behaviour for each corner approach.

    Args:
        brake_threshold: Minimum brake value to count as "braking" [0, 1].
        lookback_fraction: How far before ``entry_pct`` to start the search
            window (as a fraction of the full lap).
        lock_decel_threshold: Deceleration rate (m/s²) above which wheel lock
            is suspected during heavy braking.
        lock_brake_min: Minimum brake pressure to trigger lock check [0, 1].
    """

    def __init__(
        self,
        brake_threshold: float = 0.05,
        lookback_fraction: float = 0.05,
        lock_decel_threshold: float = 12.0,
        lock_brake_min: float = 0.7,
    ) -> None:
        self.brake_threshold = brake_threshold
        self.lookback_fraction = lookback_fraction
        self.lock_decel_threshold = lock_decel_threshold
        self.lock_brake_min = lock_brake_min

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corners: list[Corner],
        track_length_m: float = 1000.0,
    ) -> list[BrakingEvent]:
        """Return one :class:`BrakingEvent` per corner.

        Args:
            user_lap: Ordered frames for the user's lap.
            ref_lap: Ordered frames for the reference lap.
            corners: Corners to analyse (from :class:`~racing_coach.track.models.Corner`).
            track_length_m: Track length used to convert pct differences to metres.
        """
        return [
            self._analyze_corner(user_lap, ref_lap, corner, track_length_m)
            for corner in corners
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _brake_zone(self, lap: list[LapFrame], corner: Corner) -> list[LapFrame]:
        """Extract frames in the braking window: [entry - lookback, apex_start]."""
        lo = max(0.0, corner.entry_pct - self.lookback_fraction)
        hi = corner.apex_start
        return [f for f in lap if lo <= f.lap_dist_pct <= hi]

    def _find_brake_start(self, frames: list[LapFrame], default_pct: float) -> float:
        """Return the pct of the first frame where brake > threshold."""
        for f in frames:
            if f.brake > self.brake_threshold:
                return f.lap_dist_pct
        return default_pct

    def _find_peak(self, frames: list[LapFrame]) -> tuple[float, float]:
        """Return (peak_pressure, seconds_from_brake_start_to_peak)."""
        braking = [f for f in frames if f.brake > self.brake_threshold]
        if not braking:
            return 0.0, 0.0
        peak_frame = max(braking, key=lambda f: f.brake)
        time_to_peak = peak_frame.lap_time - braking[0].lap_time
        return peak_frame.brake, max(0.0, time_to_peak)

    def _trail_brake_linearity(self, frames: list[LapFrame]) -> float:
        """R² of the brake release phase (from peak to zero).

        Returns 0.0 if the brake stays constant after the peak (step release —
        no trail braking at all), and 1.0 if the release is perfectly linear.
        """
        braking = [f for f in frames if f.brake > self.brake_threshold]
        if len(braking) < 3:
            return 1.0
        peak_idx = max(range(len(braking)), key=lambda i: braking[i].brake)
        release = [f.brake for f in braking[peak_idx:]]
        if len(release) < 3:
            return 1.0
        # A step release stays constant then drops instantly; the drop happens
        # outside the search window, so `release` is all-constant → score 0.
        total_decrease = release[0] - release[-1]
        if total_decrease < 0.1:
            return 0.0
        return _linear_r_squared(release)

    def _detect_lock(self, frames: list[LapFrame]) -> bool:
        """True if excessive deceleration is detected during any braking frame.

        Checks all frames where brake > threshold (not only peak braking), so
        a lock event during the release phase is also caught.
        """
        braking = [f for f in frames if f.brake > self.brake_threshold]
        for i in range(1, len(braking)):
            dt = braking[i].lap_time - braking[i - 1].lap_time
            if dt <= 0:
                continue
            dv = braking[i - 1].speed - braking[i].speed  # positive = deceleration
            if dv / dt > self.lock_decel_threshold:
                return True
        return False

    def _analyze_corner(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corner: Corner,
        track_length_m: float,
    ) -> BrakingEvent:
        user_zone = self._brake_zone(user_lap, corner)
        ref_zone = self._brake_zone(ref_lap, corner)

        user_bp = self._find_brake_start(user_zone, corner.entry_pct)
        ref_bp = self._find_brake_start(ref_zone, corner.entry_pct)
        delta_m = (user_bp - ref_bp) * track_length_m

        peak_pressure, time_to_peak = self._find_peak(user_zone)
        linearity = self._trail_brake_linearity(user_zone)
        lock = self._detect_lock(user_zone)

        return BrakingEvent(
            corner_id=corner.id,
            brake_point_pct=user_bp,
            ref_brake_point_pct=ref_bp,
            brake_point_delta_m=delta_m,
            peak_pressure=peak_pressure,
            time_to_peak_s=time_to_peak,
            trail_brake_linearity=linearity,
            lock_detected=lock,
        )
