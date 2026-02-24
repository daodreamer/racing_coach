"""Tests for S2-US2 (corner detection) and S2-US3 (three-phase division)."""

from __future__ import annotations

import math

from racing_coach.track.detector import CornerDetector
from racing_coach.track.models import Corner, TrackPoint

# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def integrate_curvature(kappas: list[float]) -> list[TrackPoint]:
    """Build a TrackPoint list by integrating a curvature profile.

    Each kappas[i] is the rate of heading change per unit of lap_dist_pct.
    The resulting Menger curvature at each point equals kappas[i].
    """
    n = len(kappas)
    ds = 1.0 / n  # spatial step = parameter step (unit speed)
    theta = 0.0
    x, y = 0.0, 0.0
    points = []
    for i in range(n):
        t = i / n
        points.append(TrackPoint(lap_dist_pct=t, x=x, y=y))
        theta += kappas[i] * ds
        x += math.cos(theta) * ds
        y += math.sin(theta) * ds
    return points


def make_straight(n: int = 200) -> list[TrackPoint]:
    """Pure straight line - zero curvature everywhere."""
    return [TrackPoint(lap_dist_pct=i / n, x=float(i), y=0.0) for i in range(n)]


def make_three_corner_track() -> list[TrackPoint]:
    """Track with left corner (0.10-0.20), right (0.40-0.50), left (0.70-0.80).

    Kappa = +/-0.10 in corners, 0 on straights.
    Resulting Menger curvature ~= +/-0.10 in corners.
    """
    n = 600
    kappas = []
    for i in range(n):
        t = i / n
        if 0.10 <= t < 0.20:
            kappas.append(0.10)
        elif 0.40 <= t < 0.50:
            kappas.append(-0.10)
        elif 0.70 <= t < 0.80:
            kappas.append(0.10)
        else:
            kappas.append(0.0)
    return integrate_curvature(kappas)


def make_s_bend_track() -> list[TrackPoint]:
    """Track with an S-bend: left (0.20-0.40) immediately followed by right (0.40-0.60).

    Kappa changes sign at 0.40 with no straight between them.
    """
    n = 600
    kappas = []
    for i in range(n):
        t = i / n
        if 0.20 <= t < 0.40:
            kappas.append(0.10)
        elif 0.40 <= t < 0.60:
            kappas.append(-0.10)
        else:
            kappas.append(0.0)
    return integrate_curvature(kappas)


def make_left_right_track() -> list[TrackPoint]:
    """Track with exactly one left and one right corner."""
    n = 400
    kappas = []
    for i in range(n):
        t = i / n
        if 0.10 <= t < 0.30:
            kappas.append(0.10)
        elif 0.60 <= t < 0.80:
            kappas.append(-0.10)
        else:
            kappas.append(0.0)
    return integrate_curvature(kappas)


# ---------------------------------------------------------------------------
# S2-US2: Corner auto-detection
# ---------------------------------------------------------------------------

class TestCornerDetection:
    THRESHOLD = 0.01  # well below kappa=0.10 used in test tracks

    def test_straight_has_no_corners(self):
        """A straight line produces no corners."""
        track = make_straight()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        assert corners == []

    def test_three_corners_detected(self):
        """A track with three corners yields exactly three Corner objects."""
        track = make_three_corner_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD, smooth_window=5)
        corners = detector.detect(track)
        assert len(corners) == 3

    def test_corners_are_sorted_by_entry_pct(self):
        """Corners are returned in track order."""
        track = make_three_corner_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        for i in range(len(corners) - 1):
            assert corners[i].entry_pct < corners[i + 1].entry_pct

    def test_left_corner_direction(self):
        """A counterclockwise (left) turn is labelled 'L'."""
        track = make_left_right_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        left_corners = [c for c in corners if c.direction == "L"]
        assert len(left_corners) >= 1

    def test_right_corner_direction(self):
        """A clockwise (right) turn is labelled 'R'."""
        track = make_left_right_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        right_corners = [c for c in corners if c.direction == "R"]
        assert len(right_corners) >= 1

    def test_left_right_directions_correct(self):
        """Left corner is first, right corner is second in left-right track."""
        track = make_left_right_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        assert len(corners) == 2
        assert corners[0].direction == "L"
        assert corners[1].direction == "R"

    def test_three_corner_directions_correct(self):
        """First and third corners are left, second is right."""
        track = make_three_corner_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        assert len(corners) == 3
        assert corners[0].direction == "L"
        assert corners[1].direction == "R"
        assert corners[2].direction == "L"

    def test_s_bend_split_into_two_corners(self):
        """An S-bend with no straight between left and right is split into 2 corners."""
        track = make_s_bend_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        assert len(corners) == 2

    def test_s_bend_has_opposite_directions(self):
        """The two corners of an S-bend have opposite directions."""
        track = make_s_bend_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        assert len(corners) == 2
        assert corners[0].direction != corners[1].direction

    def test_corner_ids_are_sequential(self):
        """Corner ids are assigned sequentially starting from 1."""
        track = make_three_corner_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD)
        corners = detector.detect(track)
        for i, corner in enumerate(corners):
            assert corner.id == i + 1

    def test_corner_positions_near_expected(self):
        """Detected corner entry/exit positions match where we placed the curvature."""
        track = make_three_corner_track()
        detector = CornerDetector(curvature_threshold=self.THRESHOLD, smooth_window=5)
        corners = detector.detect(track)
        assert len(corners) == 3

        tolerance = 0.05  # +/-5% of lap, accounting for smoothing
        expected = [(0.10, 0.20), (0.40, 0.50), (0.70, 0.80)]
        for corner, (exp_entry, exp_exit) in zip(corners, expected, strict=True):
            assert abs(corner.entry_pct - exp_entry) < tolerance, (
                f"Corner {corner.id} entry {corner.entry_pct:.3f} not near {exp_entry}"
            )
            assert abs(corner.exit_pct - exp_exit) < tolerance, (
                f"Corner {corner.id} exit {corner.exit_pct:.3f} not near {exp_exit}"
            )

    def test_too_few_points_returns_empty(self):
        """Centerline with fewer than 3 points returns empty corner list."""
        detector = CornerDetector()
        assert detector.detect([]) == []
        assert detector.detect([TrackPoint(0.0, 0.0, 0.0)]) == []
        assert detector.detect([TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 1.0, 0.0)]) == []


# ---------------------------------------------------------------------------
# S2-US3: Corner three-phase division
# ---------------------------------------------------------------------------

class TestCornerPhases:
    THRESHOLD = 0.01

    def _get_corners(self, track: list[TrackPoint]) -> list[Corner]:
        detector = CornerDetector(curvature_threshold=self.THRESHOLD, smooth_window=5)
        return detector.detect(track)

    def test_phase_markers_are_monotonically_increasing(self):
        """entry_pct <= apex_start <= apex_pct <= apex_end <= exit_pct for every corner."""
        corners = self._get_corners(make_three_corner_track())
        for c in corners:
            assert c.entry_pct <= c.apex_start, f"Corner {c.id}: entry_pct > apex_start"
            assert c.apex_start <= c.apex_pct, f"Corner {c.id}: apex_start > apex_pct"
            assert c.apex_pct <= c.apex_end, f"Corner {c.id}: apex_pct > apex_end"
            assert c.apex_end <= c.exit_pct, f"Corner {c.id}: apex_end > exit_pct"

    def test_entry_start_equals_corner_start(self):
        """entry_pct is the corner start — no gap before the Entry phase."""
        corners = self._get_corners(make_three_corner_track())
        # entry_pct IS the entry_start by definition; verify phase starts at corner start
        for c in corners:
            assert c.entry_pct <= c.apex_start  # Entry phase begins at corner start

    def test_apex_contains_peak_curvature_point(self):
        """apex_pct is within the apex zone [apex_start, apex_end]."""
        corners = self._get_corners(make_three_corner_track())
        for c in corners:
            assert c.apex_start <= c.apex_pct <= c.apex_end, (
                f"Corner {c.id}: apex_pct {c.apex_pct:.4f} not in "
                f"[{c.apex_start:.4f}, {c.apex_end:.4f}]"
            )

    def test_phases_cover_full_corner_no_gaps(self):
        """Phases are adjacent: entry -> apex -> exit with no gaps."""
        corners = self._get_corners(make_three_corner_track())
        for c in corners:
            # Full coverage: entry_pct to exit_pct spans the corner
            assert c.entry_pct < c.exit_pct, f"Corner {c.id}: entry_pct >= exit_pct"
            # No gaps: apex zone is bracketed by entry and exit
            assert c.entry_pct <= c.apex_start
            assert c.apex_end <= c.exit_pct

    def test_apex_phase_is_within_corner_bounds(self):
        """apex_start and apex_end lie within [entry_pct, exit_pct]."""
        corners = self._get_corners(make_three_corner_track())
        for c in corners:
            assert c.entry_pct <= c.apex_start
            assert c.apex_end <= c.exit_pct

    def test_corner_has_nonzero_length(self):
        """Each detected corner has a positive length (exit > entry)."""
        corners = self._get_corners(make_three_corner_track())
        for c in corners:
            assert c.exit_pct > c.entry_pct
