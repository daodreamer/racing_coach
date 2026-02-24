"""Corner detection and three-phase division for race track centerlines.

S2-US2: automatically detect corners (entry, apex, exit position; direction L/R).
S2-US3: subdivide each corner into Entry / Apex / Exit phases.
"""

from __future__ import annotations

import math

from racing_coach.track.models import Corner, TrackPoint

# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

def _menger_signed_curvature(p1: TrackPoint, p2: TrackPoint, p3: TrackPoint) -> float:
    """Signed Menger curvature at *p2* given three consecutive track points.

    Returns the physical curvature κ = 1/R with sign:
      * positive → left turn (counterclockwise)
      * negative → right turn (clockwise)

    Returns 0.0 if any two points are coincident (degenerate triangle).
    """
    ax, ay = p2.x - p1.x, p2.y - p1.y  # vector P1→P2
    bx, by = p3.x - p2.x, p3.y - p2.y  # vector P2→P3
    cx, cy = p3.x - p1.x, p3.y - p1.y  # vector P1→P3

    d12 = math.hypot(ax, ay)
    d23 = math.hypot(bx, by)
    d13 = math.hypot(cx, cy)

    denom = d12 * d23 * d13
    if denom < 1e-12:
        return 0.0

    # z-component of cross(P2-P1, P3-P2): positive means CCW (left turn)
    cross_z = ax * by - ay * bx
    return 2.0 * cross_z / denom


def _moving_average(values: list[float], half_window: int) -> list[float]:
    """Circular moving average with kernel size ``2 * half_window + 1``."""
    n = len(values)
    if n == 0:
        return []
    w = half_window
    kernel = 2 * w + 1
    result: list[float] = []
    for i in range(n):
        total = sum(values[(i + j) % n] for j in range(-w, w + 1))
        result.append(total / kernel)
    return result


# ---------------------------------------------------------------------------
# Corner detector
# ---------------------------------------------------------------------------

class CornerDetector:
    """Detect corners in a track centerline and divide them into three phases.

    Args:
        curvature_threshold: Minimum |κ| required to classify a point as "in a corner".
            Points below this threshold are treated as straights.
        smooth_window: Half-window size for curvature smoothing
            (kernel = ``2 * smooth_window + 1`` points).
        min_corner_fraction: Minimum corner length as a fraction of the full lap [0, 1].
            Shorter regions are discarded as noise.
        apex_fraction: A point belongs to the *Apex zone* if its |κ| exceeds
            ``apex_fraction * peak_κ`` for that corner.  Must be in (0, 1].
        merge_gap: Two adjacent same-direction corner regions separated by less than
            this lap-fraction are merged into one corner.
    """

    def __init__(
        self,
        curvature_threshold: float = 0.005,
        smooth_window: int = 5,
        min_corner_fraction: float = 0.005,
        apex_fraction: float = 0.7,
        merge_gap: float = 0.02,
    ) -> None:
        self.curvature_threshold = curvature_threshold
        self.smooth_window = smooth_window
        self.min_corner_fraction = min_corner_fraction
        self.apex_fraction = apex_fraction
        self.merge_gap = merge_gap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, centerline: list[TrackPoint]) -> list[Corner]:
        """Detect all corners in *centerline*.

        Args:
            centerline: Ordered list of :class:`TrackPoint` (the track centerline).

        Returns:
            List of :class:`Corner` sorted by ``entry_pct``.  Empty list if the
            track is a straight or if *centerline* has fewer than 3 points.
        """
        if len(centerline) < 3:
            return []

        n = len(centerline)

        # 1. Signed curvature at each point (with circular wraparound at endpoints)
        raw_k: list[float] = [0.0] * n
        raw_k[0] = _menger_signed_curvature(centerline[-1], centerline[0], centerline[1])
        for i in range(1, n - 1):
            raw_k[i] = _menger_signed_curvature(centerline[i - 1], centerline[i], centerline[i + 1])
        raw_k[-1] = _menger_signed_curvature(centerline[-2], centerline[-1], centerline[0])

        # 2. Smooth curvature
        curvatures: list[float] = _moving_average(raw_k, self.smooth_window)

        # 3. Find corner regions (above threshold, split at sign changes)
        regions = self._find_regions(curvatures, centerline)

        # 4. Filter short regions
        regions = [(s, e) for s, e in regions if (e - s) >= self.min_corner_fraction]

        # 5. Merge nearby same-direction regions
        regions = self._merge_regions(regions, curvatures, centerline)

        # 6. Build Corner objects with three-phase division
        corners: list[Corner] = []
        for cid, (start_pct, end_pct) in enumerate(regions, start=1):
            corner = self._build_corner(cid, start_pct, end_pct, centerline, curvatures)
            if corner is not None:
                corners.append(corner)

        return corners

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_regions(
        self,
        curvatures: list[float],
        centerline: list[TrackPoint],
    ) -> list[tuple[float, float]]:
        """Return (start_pct, end_pct) pairs where |κ| > threshold.

        Regions are split whenever the curvature sign changes, so that an S-bend
        yields two separate regions with opposite directions.
        """
        n = len(curvatures)
        regions: list[tuple[float, float]] = []
        i = 0

        while i < n:
            # Skip below-threshold points
            while i < n and abs(curvatures[i]) <= self.curvature_threshold:
                i += 1
            if i >= n:
                break

            # Start of a corner region
            start_i = i
            current_positive = curvatures[i] > 0

            # Extend while above threshold AND same sign
            while i < n:
                k = curvatures[i]
                if abs(k) <= self.curvature_threshold:
                    break  # dropped below threshold
                if (k > 0) != current_positive:
                    break  # sign change → start a new region next iteration
                i += 1

            end_i = i - 1
            start_pct = centerline[start_i].lap_dist_pct
            end_pct = centerline[end_i].lap_dist_pct
            if end_pct > start_pct:
                regions.append((start_pct, end_pct))
            # Do NOT increment i here; the loop re-enters at the sign-change boundary

        return regions

    def _region_direction(
        self,
        region: tuple[float, float],
        curvatures: list[float],
        centerline: list[TrackPoint],
    ) -> str:
        """Return ``'L'`` or ``'R'`` for the dominant curvature sign in a region."""
        start_pct, end_pct = region
        total = sum(
            curvatures[i]
            for i, pt in enumerate(centerline)
            if start_pct <= pt.lap_dist_pct <= end_pct
        )
        return "L" if total >= 0 else "R"

    def _merge_regions(
        self,
        regions: list[tuple[float, float]],
        curvatures: list[float],
        centerline: list[TrackPoint],
    ) -> list[tuple[float, float]]:
        """Merge adjacent same-direction regions separated by a tiny gap."""
        if not regions:
            return regions

        merged = [regions[0]]
        for r in regions[1:]:
            prev = merged[-1]
            gap = r[0] - prev[1]
            prev_dir = self._region_direction(prev, curvatures, centerline)
            curr_dir = self._region_direction(r, curvatures, centerline)
            if gap < self.merge_gap and prev_dir == curr_dir:
                merged[-1] = (prev[0], r[1])
            else:
                merged.append(r)
        return merged

    def _build_corner(
        self,
        cid: int,
        entry_pct: float,
        exit_pct: float,
        centerline: list[TrackPoint],
        curvatures: list[float],
    ) -> Corner | None:
        """Construct a :class:`Corner` with three-phase division."""
        indices = [
            i
            for i, pt in enumerate(centerline)
            if entry_pct <= pt.lap_dist_pct <= exit_pct
        ]
        if not indices:
            return None

        # Apex = point of maximum |curvature|
        apex_idx = max(indices, key=lambda i: abs(curvatures[i]))
        apex_pct = centerline[apex_idx].lap_dist_pct
        direction = "L" if curvatures[apex_idx] >= 0 else "R"

        # Apex zone = all indices within the corner where |κ| >= fraction * peak
        peak_k = abs(curvatures[apex_idx])
        apex_threshold = self.apex_fraction * peak_k

        apex_zone = [i for i in indices if abs(curvatures[i]) >= apex_threshold]
        if apex_zone:
            apex_start = centerline[min(apex_zone)].lap_dist_pct
            apex_end = centerline[max(apex_zone)].lap_dist_pct
        else:
            apex_start = apex_pct
            apex_end = apex_pct

        # Clamp to corner bounds for numerical safety
        apex_start = max(apex_start, entry_pct)
        apex_end = min(apex_end, exit_pct)

        return Corner(
            id=cid,
            entry_pct=entry_pct,
            apex_pct=apex_pct,
            exit_pct=exit_pct,
            direction=direction,
            apex_start=apex_start,
            apex_end=apex_end,
        )
