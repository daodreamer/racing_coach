"""Tests for S2-US1: Track centerline extraction."""

from __future__ import annotations

import math
import random

import pytest

from racing_coach.track.centerline import CenterlineExtractor
from racing_coach.track.models import TrackPoint

# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def make_circle_lap(
    n: int = 120, radius: float = 100.0, noise: float = 0.0, seed: int = 0
) -> list[TrackPoint]:
    """Return a single lap of points on a CCW circle with optional Gaussian noise."""
    rng = random.Random(seed)
    points = []
    for i in range(n):
        t = i / n
        angle = 2 * math.pi * t
        x = radius * math.cos(angle) + rng.gauss(0, noise)
        y = radius * math.sin(angle) + rng.gauss(0, noise)
        points.append(TrackPoint(lap_dist_pct=t, x=x, y=y))
    return points


def _rms_deviation_from_circle(points: list[TrackPoint], radius: float) -> float:
    """Return RMS deviation of points from the ideal circle."""
    errors = [(math.hypot(p.x, p.y) - radius) ** 2 for p in points]
    return math.sqrt(sum(errors) / len(errors))


# ---------------------------------------------------------------------------
# S2-US1: Centerline extraction
# ---------------------------------------------------------------------------

class TestCenterlineExtraction:
    def test_single_lap_circle_stays_close_to_circle(self):
        """Given one clean circular lap, extracted centerline should be near the circle."""
        lap = make_circle_lap(n=200, radius=100.0)
        extractor = CenterlineExtractor(n_bins=100, smooth_window=3)
        centerline = extractor.extract([lap])

        assert len(centerline) > 0
        rms = _rms_deviation_from_circle(centerline, radius=100.0)
        assert rms < 2.0, f"RMS deviation {rms:.3f} too large"

    def test_output_has_n_bins_points(self):
        """Extracted centerline has exactly n_bins points (one per bin)."""
        lap = make_circle_lap(n=200, radius=50.0)
        extractor = CenterlineExtractor(n_bins=64, smooth_window=3)
        centerline = extractor.extract([lap])
        assert len(centerline) == 64

    def test_lap_dist_pct_is_monotonically_increasing(self):
        """lap_dist_pct values in the output are strictly increasing."""
        lap = make_circle_lap(n=200, radius=100.0)
        extractor = CenterlineExtractor(n_bins=100, smooth_window=3)
        centerline = extractor.extract([lap])

        for i in range(len(centerline) - 1):
            assert centerline[i].lap_dist_pct < centerline[i + 1].lap_dist_pct

    def test_closed_loop_gap_is_small(self):
        """First and last points are close to each other (closed track)."""
        lap = make_circle_lap(n=500, radius=100.0)
        extractor = CenterlineExtractor(n_bins=200, smooth_window=5)
        centerline = extractor.extract([lap])

        first = centerline[0]
        last = centerline[-1]
        gap = math.hypot(first.x - last.x, first.y - last.y)

        # Gap should be at most 2 bin widths of the circle circumference
        bin_width_m = 2 * math.pi * 100.0 / 200
        assert gap < 2 * bin_width_m, (
            f"Closure gap {gap:.2f} m is too large (limit {2 * bin_width_m:.2f} m)"
        )

    def test_multi_lap_averaging_reduces_noise(self):
        """Three noisy laps averaged together give a smoother result than any single lap."""
        noise = 3.0
        radius = 100.0
        laps = [make_circle_lap(n=200, radius=radius, noise=noise, seed=i) for i in range(3)]

        extractor = CenterlineExtractor(n_bins=100, smooth_window=1)  # minimal smoothing
        centerline = extractor.extract(laps)

        rms_multi = _rms_deviation_from_circle(centerline, radius)
        rms_single = [
            _rms_deviation_from_circle(
                make_circle_lap(n=200, radius=radius, noise=noise, seed=i), radius
            )
            for i in range(3)
        ]
        avg_single_rms = sum(rms_single) / len(rms_single)

        assert rms_multi < avg_single_rms, (
            f"Multi-lap RMS {rms_multi:.3f} should be less than "
            f"avg single-lap RMS {avg_single_rms:.3f}"
        )

    def test_empty_laps_raises_value_error(self):
        """Passing an empty laps list raises ValueError."""
        extractor = CenterlineExtractor()
        with pytest.raises(ValueError):
            extractor.extract([])

    def test_single_lap_single_point_returns_empty(self):
        """A lap with only one point (no useful data) returns a list gracefully."""
        lap = [TrackPoint(lap_dist_pct=0.5, x=0.0, y=0.0)]
        extractor = CenterlineExtractor(n_bins=10, smooth_window=1)
        result = extractor.extract([lap])
        assert isinstance(result, list)
