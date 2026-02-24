"""Tests for S3-US5: Apex speed analysis."""

from __future__ import annotations

from racing_coach.analysis.apex_speed import ApexSpeedAnalyzer
from racing_coach.analysis.models import LapFrame
from racing_coach.track.models import Corner

# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def make_corner(apex_start: float = 0.30, apex_end: float = 0.40) -> Corner:
    return Corner(
        id=1,
        entry_pct=0.20,
        apex_pct=0.35,
        exit_pct=0.50,
        direction="R",
        apex_start=apex_start,
        apex_end=apex_end,
    )


def make_lap_with_apex_speed(
    apex_start: float = 0.30,
    apex_end: float = 0.40,
    min_speed_mps: float = 20.0,
    total_frames: int = 200,
) -> list[LapFrame]:
    """Lap where the minimum speed in the apex zone equals min_speed_mps."""
    frames: list[LapFrame] = []
    apex_mid = (apex_start + apex_end) / 2
    for i in range(total_frames):
        pct = i / (total_frames - 1)
        if apex_start <= pct <= apex_end:
            # Parabolic dip with minimum at apex midpoint
            t = (pct - apex_mid) / max(apex_end - apex_mid, 1e-9)
            speed = min_speed_mps + 20.0 * t * t  # minimum at centre
        else:
            speed = 60.0  # straight-line speed
        frames.append(LapFrame(
            lap_dist_pct=pct,
            lap_time=pct * 60.0,
            speed=speed,
            throttle=0.8 if pct > apex_end else 0.0,
            brake=0.0,
            steering_angle=0.0,
        ))
    return frames


# ---------------------------------------------------------------------------
# S3-US5: Apex speed analysis
# ---------------------------------------------------------------------------

class TestApexSpeedAnalysis:
    CORNER = make_corner()

    def _analyzer(self) -> ApexSpeedAnalyzer:
        return ApexSpeedAnalyzer()

    def test_min_speed_extracted(self):
        """Minimum speed in the apex zone is extracted accurately."""
        lap = make_lap_with_apex_speed(min_speed_mps=20.0)
        ref = make_lap_with_apex_speed(min_speed_mps=20.0)
        results = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert len(results) == 1
        assert abs(results[0].min_speed_mps - 20.0) < 1.0

    def test_ref_min_speed_extracted(self):
        """Reference lap minimum apex speed is extracted separately."""
        lap = make_lap_with_apex_speed(min_speed_mps=20.0)
        ref = make_lap_with_apex_speed(min_speed_mps=23.0)
        results = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert abs(results[0].ref_min_speed_mps - 23.0) < 1.0

    def test_delta_kph_negative_when_user_slower(self):
        """User slower at apex → delta_kph < 0."""
        lap = make_lap_with_apex_speed(min_speed_mps=18.0)
        ref = make_lap_with_apex_speed(min_speed_mps=20.0)
        results = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert results[0].delta_kph < 0

    def test_delta_kph_positive_when_user_faster(self):
        """User faster at apex → delta_kph > 0."""
        lap = make_lap_with_apex_speed(min_speed_mps=22.0)
        ref = make_lap_with_apex_speed(min_speed_mps=20.0)
        results = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert results[0].delta_kph > 0

    def test_delta_kph_value_correct(self):
        """delta_kph = (user_min - ref_min) * 3.6 with known values."""
        lap = make_lap_with_apex_speed(min_speed_mps=15.0)
        ref = make_lap_with_apex_speed(min_speed_mps=17.0)
        results = self._analyzer().analyze(lap, ref, [self.CORNER])
        expected_delta = (15.0 - 17.0) * 3.6  # = -7.2 kph
        assert abs(results[0].delta_kph - expected_delta) < 1.0

    def test_too_slow_flagged_when_delta_exceeds_threshold(self):
        """too_slow = True when user is more than 5 km/h slower."""
        lap = make_lap_with_apex_speed(min_speed_mps=14.0)  # ~50.4 kph
        ref = make_lap_with_apex_speed(min_speed_mps=16.0)  # ~57.6 kph
        # delta = -7.2 kph → exceeds 5 kph threshold
        results = self._analyzer().analyze(lap, ref, [self.CORNER], too_slow_threshold_kph=5.0)
        assert results[0].too_slow

    def test_not_too_slow_when_delta_below_threshold(self):
        """too_slow = False when user is less than 5 km/h slower."""
        lap = make_lap_with_apex_speed(min_speed_mps=19.0)
        ref = make_lap_with_apex_speed(min_speed_mps=20.0)
        # delta = -3.6 kph < 5 kph threshold
        results = self._analyzer().analyze(lap, ref, [self.CORNER], too_slow_threshold_kph=5.0)
        assert not results[0].too_slow

    def test_threshold_boundary_three_values(self):
        """Parametric: test 3/5/10 kph differences against 5 kph threshold."""
        ref = make_lap_with_apex_speed(min_speed_mps=20.0)
        for delta_kph, expect_slow in [(3.0, False), (5.5, True), (10.0, True)]:
            user_speed = 20.0 - delta_kph / 3.6
            lap = make_lap_with_apex_speed(min_speed_mps=user_speed)
            results = self._analyzer().analyze(lap, ref, [self.CORNER], too_slow_threshold_kph=5.0)
            assert results[0].too_slow == expect_slow, (
                f"delta={delta_kph} kph: expected too_slow={expect_slow}"
            )

    def test_returns_one_result_per_corner(self):
        """analyze() returns exactly one result per corner."""
        corners = [
            Corner(id=1, entry_pct=0.10, apex_pct=0.15, exit_pct=0.20,
                   direction="L", apex_start=0.12, apex_end=0.18),
            Corner(id=2, entry_pct=0.60, apex_pct=0.65, exit_pct=0.70,
                   direction="R", apex_start=0.62, apex_end=0.68),
        ]
        lap = make_lap_with_apex_speed()
        results = self._analyzer().analyze(lap, lap, corners)
        assert len(results) == 2

    def test_corner_id_matches(self):
        """ApexSpeedResult.corner_id matches the input Corner.id."""
        lap = make_lap_with_apex_speed()
        results = self._analyzer().analyze(lap, lap, [self.CORNER])
        assert results[0].corner_id == self.CORNER.id
