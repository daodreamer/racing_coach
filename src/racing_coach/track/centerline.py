"""Track centerline extraction from multi-lap telemetry position data.

S2-US1: given (lap_dist_pct, x, y) sequences from one or more laps, produce a
smooth, closed centerline suitable for curvature analysis.
"""

from __future__ import annotations

from collections import defaultdict

from racing_coach.track.models import TrackPoint


class CenterlineExtractor:
    """Extract a smooth track centerline from one or more laps of position data.

    Algorithm:
    1. Bin all sample points by ``lap_dist_pct`` into *n_bins* equal buckets.
    2. Average ``x`` and ``y`` within each bucket (multi-lap noise reduction).
    3. Apply a circular moving-average with *smooth_window* to reduce remaining jitter.

    Args:
        n_bins: Number of equally-spaced ``lap_dist_pct`` bins. Higher values give
            finer resolution at the cost of more memory.
        smooth_window: Half-width of the moving-average kernel (total kernel size =
            ``2 * smooth_window + 1``).  Use 0 to skip smoothing.
    """

    def __init__(self, n_bins: int = 512, smooth_window: int = 10) -> None:
        if n_bins < 1:
            raise ValueError("n_bins must be >= 1")
        self.n_bins = n_bins
        self.smooth_window = smooth_window

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, laps: list[list[TrackPoint]]) -> list[TrackPoint]:
        """Extract a smooth centerline from one or more laps.

        Args:
            laps: List of laps; each lap is an ordered list of :class:`TrackPoint`.

        Returns:
            List of :class:`TrackPoint` with ``n_bins`` entries, ordered by
            ``lap_dist_pct``.  May be shorter if some bins received no samples.

        Raises:
            ValueError: If *laps* is empty.
        """
        if not laps:
            raise ValueError("At least one lap is required")

        # Step 1 — collect samples per bin
        x_accum: dict[int, list[float]] = defaultdict(list)
        y_accum: dict[int, list[float]] = defaultdict(list)

        for lap in laps:
            for pt in lap:
                idx = int(pt.lap_dist_pct * self.n_bins) % self.n_bins
                x_accum[idx].append(pt.x)
                y_accum[idx].append(pt.y)

        # Step 2 — average per bin
        raw: list[TrackPoint] = []
        for i in range(self.n_bins):
            if x_accum[i]:
                x_avg = sum(x_accum[i]) / len(x_accum[i])
                y_avg = sum(y_accum[i]) / len(y_accum[i])
                t = (i + 0.5) / self.n_bins
                raw.append(TrackPoint(lap_dist_pct=t, x=x_avg, y=y_avg))

        if not raw:
            return []

        # Step 3 — smooth (skip if window == 0 or only one point)
        if self.smooth_window > 0 and len(raw) > 1:
            return self._smooth(raw)
        return raw

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _smooth(self, points: list[TrackPoint]) -> list[TrackPoint]:
        """Circular moving-average over x and y."""
        n = len(points)
        w = self.smooth_window
        kernel_size = 2 * w + 1
        smoothed: list[TrackPoint] = []

        for i in range(n):
            x_sum = 0.0
            y_sum = 0.0
            for j in range(-w, w + 1):
                pt = points[(i + j) % n]
                x_sum += pt.x
                y_sum += pt.y
            smoothed.append(TrackPoint(
                lap_dist_pct=points[i].lap_dist_pct,
                x=x_sum / kernel_size,
                y=y_sum / kernel_size,
            ))

        return smoothed
