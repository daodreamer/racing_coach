"""Throttle analysis — S3-US4.

Analyses throttle behaviour in each corner's exit phase:
  - Throttle application point
  - "Too early full throttle" detection
  - Throttle/brake overlap detection
"""

from __future__ import annotations

from racing_coach.analysis.models import LapFrame, ThrottleEvent
from racing_coach.track.models import Corner


class ThrottleAnalyzer:
    """Analyse throttle usage for each corner exit.

    Args:
        throttle_threshold: Minimum throttle to count as "applied" [0, 1].
        full_throttle_level: Throttle value considered "full throttle" [0, 1].
        full_throttle_steer_threshold: Steering angle (radians) above which
            full throttle is flagged as "too early".
        brake_overlap_min: Minimum brake value for overlap detection.
        throttle_overlap_min: Minimum throttle value for overlap detection.
    """

    def __init__(
        self,
        throttle_threshold: float = 0.05,
        full_throttle_level: float = 0.99,
        full_throttle_steer_threshold: float = 0.1,
        brake_overlap_min: float = 0.05,
        throttle_overlap_min: float = 0.05,
    ) -> None:
        self.throttle_threshold = throttle_threshold
        self.full_throttle_level = full_throttle_level
        self.full_throttle_steer_threshold = full_throttle_steer_threshold
        self.brake_overlap_min = brake_overlap_min
        self.throttle_overlap_min = throttle_overlap_min

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corners: list[Corner],
    ) -> list[ThrottleEvent]:
        """Return one :class:`ThrottleEvent` per corner."""
        return [self._analyze_corner(user_lap, ref_lap, corner) for corner in corners]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _exit_frames(self, lap: list[LapFrame], corner: Corner) -> list[LapFrame]:
        """Extract frames in the exit zone: [apex_end, exit_pct]."""
        return [f for f in lap if corner.apex_end <= f.lap_dist_pct <= corner.exit_pct]

    def _find_throttle_point(self, frames: list[LapFrame], default_pct: float) -> float:
        """Return the pct of the first frame where throttle > threshold."""
        for f in frames:
            if f.throttle > self.throttle_threshold:
                return f.lap_dist_pct
        return default_pct

    def _detect_early_full_throttle(self, frames: list[LapFrame]) -> bool:
        """True if any frame has throttle >= full_throttle_level AND |steer| > threshold."""
        for f in frames:
            if (f.throttle >= self.full_throttle_level
                    and abs(f.steering_angle) > self.full_throttle_steer_threshold):
                return True
        return False

    def _count_overlap(self, lap: list[LapFrame], corner: Corner) -> int:
        """Count frames in the full corner range where both brake and throttle are active."""
        return sum(
            1
            for f in lap
            if corner.entry_pct <= f.lap_dist_pct <= corner.exit_pct
            and f.brake > self.brake_overlap_min
            and f.throttle > self.throttle_overlap_min
        )

    def _analyze_corner(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corner: Corner,
    ) -> ThrottleEvent:
        user_exit = self._exit_frames(user_lap, corner)

        throttle_pct = self._find_throttle_point(user_exit, corner.exit_pct)
        early_full = self._detect_early_full_throttle(user_exit)
        overlap = self._count_overlap(user_lap, corner)

        return ThrottleEvent(
            corner_id=corner.id,
            throttle_point_pct=throttle_pct,
            too_early_full_throttle=early_full,
            overlap_count=overlap,
        )
