"""Tests for S3-US2: Point-by-point delta calculation."""

from __future__ import annotations

from racing_coach.analysis.delta import DeltaCalculator
from racing_coach.analysis.models import LapFrame
from racing_coach.track.models import Corner

# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def make_uniform_lap(n: int = 101, total_time: float = 60.0, speed: float = 50.0) -> list[LapFrame]:
    """Lap with uniform speed: lap_time grows linearly from 0 to total_time."""
    return [
        LapFrame(
            lap_dist_pct=i / (n - 1),
            lap_time=i / (n - 1) * total_time,
            speed=speed,
            throttle=0.8,
            brake=0.0,
            steering_angle=0.0,
        )
        for i in range(n)
    ]


def make_three_corners() -> list[Corner]:
    return [
        Corner(id=1, entry_pct=0.10, apex_pct=0.15, exit_pct=0.20,
               direction="L", apex_start=0.13, apex_end=0.17),
        Corner(id=2, entry_pct=0.40, apex_pct=0.45, exit_pct=0.50,
               direction="R", apex_start=0.43, apex_end=0.47),
        Corner(id=3, entry_pct=0.70, apex_pct=0.75, exit_pct=0.80,
               direction="L", apex_start=0.73, apex_end=0.77),
    ]


# ---------------------------------------------------------------------------
# S3-US2: Point-by-point delta
# ---------------------------------------------------------------------------

class TestDeltaCalculator:
    def test_same_lap_zero_delta(self):
        """Comparing a lap to itself gives delta ≈ 0 everywhere."""
        lap = make_uniform_lap()
        calc = DeltaCalculator()
        deltas = calc.compute_point_deltas(lap, lap)
        for _, d in deltas:
            assert abs(d) < 0.01

    def test_all_positive_when_slower(self):
        """User lap slower than reference → positive delta at every position p > 0."""
        ref = make_uniform_lap(total_time=60.0)
        user = make_uniform_lap(total_time=62.0)
        calc = DeltaCalculator()
        deltas = calc.compute_point_deltas(user, ref)
        for p, d in deltas:
            if p > 1e-6:
                assert d > 0, f"Expected positive delta at p={p:.3f}, got {d:.4f}"

    def test_all_negative_when_faster(self):
        """User lap faster than reference → negative delta at every position p > 0."""
        ref = make_uniform_lap(total_time=60.0)
        user = make_uniform_lap(total_time=58.0)
        calc = DeltaCalculator()
        deltas = calc.compute_point_deltas(user, ref)
        for p, d in deltas:
            if p > 1e-6:
                assert d < 0, f"Expected negative delta at p={p:.3f}, got {d:.4f}"

    def test_delta_matches_known_value_at_midpoint(self):
        """For 1-second-slower lap, delta at p=0.5 is approximately 0.5 s."""
        ref = make_uniform_lap(n=101, total_time=60.0)
        user = make_uniform_lap(n=101, total_time=61.0)
        calc = DeltaCalculator()
        deltas = calc.compute_point_deltas(user, ref)
        mid_delta = next(d for p, d in deltas if abs(p - 0.5) < 0.02)
        assert abs(mid_delta - 0.5) < 0.05

    def test_different_sample_rates(self):
        """Interpolation works when user (100 frames) and ref (60 frames) differ."""
        ref = make_uniform_lap(n=61, total_time=60.0)
        user = make_uniform_lap(n=101, total_time=61.0)
        calc = DeltaCalculator()
        deltas = calc.compute_point_deltas(user, ref)
        assert len(deltas) > 0
        for p, d in deltas:
            if p > 1e-6:
                assert d > 0

    def test_output_length_equals_grid_size(self):
        """The returned deltas list has n_grid entries."""
        lap = make_uniform_lap()
        calc = DeltaCalculator(n_grid=50)
        deltas = calc.compute_point_deltas(lap, lap)
        assert len(deltas) == 50

    # ------------------------------------------------------------------
    # Per-corner delta summary
    # ------------------------------------------------------------------

    def test_three_corner_delta_summary(self):
        """compute_corner_deltas returns one CornerDelta per corner."""
        ref = make_uniform_lap()
        user = make_uniform_lap(total_time=61.0)
        corners = make_three_corners()
        calc = DeltaCalculator()
        result = calc.compute_corner_deltas(user, ref, corners)
        assert len(result) == 3

    def test_corner_delta_ids_match(self):
        """CornerDelta.corner_id matches the input Corner.id."""
        ref = make_uniform_lap()
        user = make_uniform_lap(total_time=61.0)
        corners = [Corner(id=7, entry_pct=0.2, apex_pct=0.25, exit_pct=0.3,
                          direction="L", apex_start=0.23, apex_end=0.27)]
        calc = DeltaCalculator()
        result = calc.compute_corner_deltas(user, ref, corners)
        assert result[0].corner_id == 7

    def test_corner_delta_has_all_fields(self):
        """CornerDelta contains delta_entry, delta_apex, delta_exit, delta_total."""
        ref = make_uniform_lap()
        user = make_uniform_lap(total_time=61.0)
        corners = make_three_corners()
        calc = DeltaCalculator()
        for cd in calc.compute_corner_deltas(user, ref, corners):
            assert hasattr(cd, "delta_entry")
            assert hasattr(cd, "delta_apex")
            assert hasattr(cd, "delta_exit")
            assert hasattr(cd, "delta_total")

    def test_delta_total_equals_exit_minus_entry(self):
        """delta_total = delta_exit - delta_entry (time gained/lost in this corner)."""
        ref = make_uniform_lap()
        user = make_uniform_lap(total_time=62.0)
        corners = make_three_corners()
        calc = DeltaCalculator()
        for cd in calc.compute_corner_deltas(user, ref, corners):
            assert abs(cd.delta_total - (cd.delta_exit - cd.delta_entry)) < 0.01
