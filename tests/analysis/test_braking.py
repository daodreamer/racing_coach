"""Tests for S3-US3: Braking analysis."""

from __future__ import annotations

from racing_coach.analysis.braking import BrakingAnalyzer
from racing_coach.analysis.models import LapFrame
from racing_coach.track.models import Corner

# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def make_corner() -> Corner:
    return Corner(
        id=1,
        entry_pct=0.30,
        apex_pct=0.35,
        exit_pct=0.40,
        direction="R",
        apex_start=0.33,
        apex_end=0.37,
    )


def make_approach_lap(
    brake_start_pct: float,
    peak_at_pct: float,
    release_end_pct: float,
    total_frames: int = 200,
    speed_at_start: float = 60.0,
    inject_lock_at: int | None = None,
) -> list[LapFrame]:
    """Generate a lap with a braking event defined by three pct positions.

    The brake ramps up from 0 → 1 between brake_start_pct and peak_at_pct,
    then linearly releases from 1 → 0 between peak_at_pct and release_end_pct.
    """
    frames: list[LapFrame] = []
    for i in range(total_frames):
        t = i / (total_frames - 1)
        pct = t

        if pct < brake_start_pct:
            brake = 0.0
        elif pct <= peak_at_pct:
            frac = (pct - brake_start_pct) / max(peak_at_pct - brake_start_pct, 1e-9)
            brake = frac
        elif pct <= release_end_pct:
            frac = (pct - peak_at_pct) / max(release_end_pct - peak_at_pct, 1e-9)
            brake = 1.0 - frac
        else:
            brake = 0.0

        speed = max(0.0, speed_at_start - t * speed_at_start * 0.5)
        if inject_lock_at is not None and i == inject_lock_at:
            speed = max(0.0, speed - 15.0)  # sudden speed drop simulating lock

        frames.append(LapFrame(
            lap_dist_pct=pct,
            lap_time=t * 60.0,
            speed=speed,
            throttle=0.0,
            brake=brake,
            steering_angle=0.05,
        ))
    return frames


def make_step_release_lap(
    brake_start_pct: float = 0.25,
    peak_at_pct: float = 0.28,
    release_end_pct: float = 0.32,
    total_frames: int = 200,
) -> list[LapFrame]:
    """Brake that ramps up then drops instantly (step release, non-linear)."""
    frames: list[LapFrame] = []
    for i in range(total_frames):
        pct = i / (total_frames - 1)

        if pct < brake_start_pct:
            brake = 0.0
        elif pct <= peak_at_pct:
            frac = (pct - brake_start_pct) / max(peak_at_pct - brake_start_pct, 1e-9)
            brake = frac
        elif pct < release_end_pct:
            brake = 1.0  # stays at peak (no linear release)
        else:
            brake = 0.0  # instant drop

        frames.append(LapFrame(
            lap_dist_pct=pct,
            lap_time=pct * 60.0,
            speed=max(0.0, 60.0 - pct * 30.0),
            throttle=0.0,
            brake=brake,
            steering_angle=0.05,
        ))
    return frames


# ---------------------------------------------------------------------------
# S3-US3: Braking analysis
# ---------------------------------------------------------------------------

class TestBrakingAnalysis:
    CORNER = make_corner()

    def _analyzer(self) -> BrakingAnalyzer:
        return BrakingAnalyzer(brake_threshold=0.05)

    def test_brake_start_detected(self):
        """Braking start position is detected near the expected pct."""
        lap = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert len(events) == 1
        assert abs(events[0].brake_point_pct - 0.25) < 0.02

    def test_brake_start_delta_when_braking_later(self):
        """User brakes later (higher pct) → positive brake_point_delta_m."""
        user = make_approach_lap(brake_start_pct=0.28, peak_at_pct=0.31, release_end_pct=0.34)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.28, release_end_pct=0.33)
        events = self._analyzer().analyze(user, ref, [self.CORNER], track_length_m=1000.0)
        assert events[0].brake_point_delta_m > 0

    def test_brake_start_delta_when_braking_earlier(self):
        """User brakes earlier (lower pct) → negative brake_point_delta_m."""
        user = make_approach_lap(brake_start_pct=0.22, peak_at_pct=0.26, release_end_pct=0.30)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        events = self._analyzer().analyze(user, ref, [self.CORNER], track_length_m=1000.0)
        assert events[0].brake_point_delta_m < 0

    def test_peak_pressure_detected(self):
        """Peak brake pressure is reported accurately."""
        lap = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        # Peak should be close to 1.0 (the max brake value in our generated data)
        assert events[0].peak_pressure > 0.8

    def test_time_to_peak_is_positive(self):
        """time_to_peak_s is non-negative when braking is detected."""
        lap = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].time_to_peak_s >= 0.0

    def test_trail_brake_linear_release_scores_high(self):
        """Smooth linear brake release yields linearity score close to 1.0."""
        lap = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.28, release_end_pct=0.33)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.28, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].trail_brake_linearity > 0.7

    def test_trail_brake_step_release_scores_low(self):
        """Step brake release (stays at peak then drops) yields low linearity score."""
        lap = make_step_release_lap(brake_start_pct=0.25, peak_at_pct=0.28, release_end_pct=0.33)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.28, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].trail_brake_linearity < 0.6

    def test_wheel_lock_detected(self):
        """Frame with sudden speed drop during heavy braking triggers lock_detected."""
        lap = make_approach_lap(
            brake_start_pct=0.25,
            peak_at_pct=0.28,
            release_end_pct=0.33,
            inject_lock_at=60,  # sudden speed drop at frame 60 (~pct 0.30)
        )
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.28, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert events[0].lock_detected

    def test_no_lock_on_smooth_braking(self):
        """Normal smooth braking does not trigger lock_detected."""
        lap = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        ref = make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33)
        events = self._analyzer().analyze(lap, ref, [self.CORNER])
        assert not events[0].lock_detected

    def test_returns_one_event_per_corner(self):
        """analyze() returns exactly one BrakingEvent per Corner."""
        corners = [
            Corner(id=1, entry_pct=0.10, apex_pct=0.15, exit_pct=0.20,
                   direction="L", apex_start=0.13, apex_end=0.17),
            Corner(id=2, entry_pct=0.50, apex_pct=0.55, exit_pct=0.60,
                   direction="R", apex_start=0.53, apex_end=0.57),
        ]
        lap = make_approach_lap(brake_start_pct=0.06, peak_at_pct=0.10, release_end_pct=0.15)
        events = self._analyzer().analyze(lap, lap, corners)
        assert len(events) == 2

    def test_corner_id_matches(self):
        """BrakingEvent.corner_id matches the input Corner.id."""
        events = self._analyzer().analyze(
            make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33),
            make_approach_lap(brake_start_pct=0.25, peak_at_pct=0.29, release_end_pct=0.33),
            [self.CORNER],
        )
        assert events[0].corner_id == self.CORNER.id
