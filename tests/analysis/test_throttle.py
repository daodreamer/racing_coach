"""Tests for S3-US4: Throttle analysis."""

from __future__ import annotations

from racing_coach.analysis.models import LapFrame
from racing_coach.analysis.throttle import ThrottleAnalyzer
from racing_coach.track.models import Corner

# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def make_corner() -> Corner:
    return Corner(
        id=1,
        entry_pct=0.20,
        apex_pct=0.30,
        exit_pct=0.45,
        direction="R",
        apex_start=0.27,
        apex_end=0.33,
    )


def make_exit_lap(
    throttle_at_pct: float = 0.35,
    full_throttle_steer: float = 0.0,
    with_overlap: bool = False,
    total_frames: int = 200,
) -> list[LapFrame]:
    """Lap frames that include the corner exit zone.

    Args:
        throttle_at_pct:  Lap fraction where throttle first exceeds threshold.
        full_throttle_steer:  Steering angle applied when throttle = 1.0 (for
            early-throttle test).
        with_overlap:  If True, some frames have both brake and throttle active.
    """
    frames: list[LapFrame] = []
    for i in range(total_frames):
        pct = i / (total_frames - 1)

        if pct < throttle_at_pct:
            throttle = 0.0
            brake = 0.2 if pct < 0.30 else 0.0
        else:
            throttle = min(1.0, (pct - throttle_at_pct) / 0.10)
            brake = 0.0

        steer = full_throttle_steer if throttle >= 0.99 else 0.05

        if with_overlap and 0.34 <= pct <= 0.36:
            throttle = 0.3
            brake = 0.1  # simultaneous, both above 0.05

        frames.append(LapFrame(
            lap_dist_pct=pct,
            lap_time=pct * 60.0,
            speed=max(10.0, 80.0 - pct * 50.0),
            throttle=throttle,
            brake=brake,
            steering_angle=steer,
        ))
    return frames


# ---------------------------------------------------------------------------
# S3-US4: Throttle analysis
# ---------------------------------------------------------------------------

class TestThrottleAnalysis:
    CORNER = make_corner()

    def _analyzer(self) -> ThrottleAnalyzer:
        return ThrottleAnalyzer(throttle_threshold=0.05)

    def test_throttle_point_detected(self):
        """First throttle application after apex is detected at the expected position."""
        lap = make_exit_lap(throttle_at_pct=0.35)
        ref = make_exit_lap(throttle_at_pct=0.35)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert len(events) == 1
        assert abs(events[0].throttle_point_pct - 0.35) < 0.02

    def test_throttle_point_no_throttle_returns_default(self):
        """When no throttle is applied in exit zone, throttle_point_pct = exit_pct."""
        frames = [
            LapFrame(lap_dist_pct=i / 199, lap_time=i / 199 * 60,
                     speed=50.0, throttle=0.0, brake=0.0, steering_angle=0.0)
            for i in range(200)
        ]
        events = self._analyzer().analyze(frames, frames, [self.CORNER])
        assert events[0].throttle_point_pct == self.CORNER.exit_pct

    def test_too_early_full_throttle_detected(self):
        """Full throttle with large steering angle is flagged."""
        lap = make_exit_lap(throttle_at_pct=0.33, full_throttle_steer=0.3)
        ref = make_exit_lap(throttle_at_pct=0.35)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].too_early_full_throttle

    def test_full_throttle_with_small_steer_not_flagged(self):
        """Full throttle with small steering angle is not flagged as early."""
        lap = make_exit_lap(throttle_at_pct=0.36, full_throttle_steer=0.03)
        ref = make_exit_lap(throttle_at_pct=0.35)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert not events[0].too_early_full_throttle

    def test_no_early_throttle_without_full_throttle(self):
        """Partial throttle (< 99%) is never flagged as early full throttle."""
        frames = [
            LapFrame(lap_dist_pct=i / 199, lap_time=i / 199 * 60,
                     speed=50.0, throttle=0.7, brake=0.0, steering_angle=0.5)
            for i in range(200)
        ]
        events = self._analyzer().analyze(frames, frames, [self.CORNER])
        assert not events[0].too_early_full_throttle

    def test_overlap_detected(self):
        """Simultaneous brake > 0.05 and throttle > 0.05 increments overlap_count."""
        lap = make_exit_lap(throttle_at_pct=0.35, with_overlap=True)
        ref = make_exit_lap(throttle_at_pct=0.35)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].overlap_count > 0

    def test_no_overlap_normal_driving(self):
        """No overlap frames in clean driving yields overlap_count = 0."""
        lap = make_exit_lap(throttle_at_pct=0.35, with_overlap=False)
        ref = make_exit_lap(throttle_at_pct=0.35)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].overlap_count == 0

    def test_returns_one_event_per_corner(self):
        """analyze() returns exactly one ThrottleEvent per Corner."""
        corners = [
            Corner(id=1, entry_pct=0.10, apex_pct=0.15, exit_pct=0.20,
                   direction="L", apex_start=0.12, apex_end=0.17),
            Corner(id=2, entry_pct=0.60, apex_pct=0.65, exit_pct=0.70,
                   direction="R", apex_start=0.62, apex_end=0.67),
        ]
        lap = make_exit_lap()
        events = self._analyzer().analyze(lap, lap, corners)
        assert len(events) == 2

    def test_corner_id_matches(self):
        """ThrottleEvent.corner_id matches the input Corner.id."""
        events = self._analyzer().analyze(
            make_exit_lap(), make_exit_lap(), [self.CORNER]
        )
        assert events[0].corner_id == self.CORNER.id
