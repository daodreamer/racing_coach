"""Apex speed analysis — S3-US5.

Extracts the minimum speed in each corner's apex zone and compares it with
the reference lap.
"""

from __future__ import annotations

from racing_coach.analysis.models import ApexSpeedResult, LapFrame
from racing_coach.track.models import Corner

_MPS_TO_KPH = 3.6


class ApexSpeedAnalyzer:
    """Analyse minimum speed in the apex zone for each corner."""

    def analyze(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corners: list[Corner],
        too_slow_threshold_kph: float = 5.0,
    ) -> list[ApexSpeedResult]:
        """Return one :class:`ApexSpeedResult` per corner.

        Args:
            user_lap: Ordered frames for the user lap.
            ref_lap: Ordered frames for the reference lap.
            corners: List of corners (from Sprint 2).
            too_slow_threshold_kph: Speed deficit (km/h) above which the apex
                is flagged as "too slow".  Default: 5 km/h.
        """
        return [
            self._analyze_corner(user_lap, ref_lap, corner, too_slow_threshold_kph)
            for corner in corners
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apex_min_speed(self, lap: list[LapFrame], corner: Corner) -> float:
        """Return the minimum speed in the apex zone, or 0 if no frames found."""
        apex_speeds = [
            f.speed
            for f in lap
            if corner.apex_start <= f.lap_dist_pct <= corner.apex_end
        ]
        return min(apex_speeds) if apex_speeds else 0.0

    def _analyze_corner(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corner: Corner,
        threshold_kph: float,
    ) -> ApexSpeedResult:
        user_min = self._apex_min_speed(user_lap, corner)
        ref_min = self._apex_min_speed(ref_lap, corner)
        delta_kph = (user_min - ref_min) * _MPS_TO_KPH
        too_slow = delta_kph < -threshold_kph

        return ApexSpeedResult(
            corner_id=corner.id,
            min_speed_mps=user_min,
            ref_min_speed_mps=ref_min,
            delta_kph=delta_kph,
            too_slow=too_slow,
        )
