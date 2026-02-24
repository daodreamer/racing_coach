"""Point-by-point delta calculation — S3-US2.

Computes the time gap between a user lap and a reference lap at every position
on track, and summarises results per corner.
"""

from __future__ import annotations

import bisect

from racing_coach.analysis.models import CornerDelta, LapFrame
from racing_coach.track.models import Corner


def _interpolate_time(frames: list[LapFrame], query_pct: float) -> float:
    """Linear interpolation of ``lap_time`` at *query_pct*.

    If *query_pct* is out of range it is clamped to the first/last frame.
    """
    if not frames:
        return 0.0
    pcts = [f.lap_dist_pct for f in frames]
    if query_pct <= pcts[0]:
        return frames[0].lap_time
    if query_pct >= pcts[-1]:
        return frames[-1].lap_time
    idx = bisect.bisect_right(pcts, query_pct)
    f0, f1 = frames[idx - 1], frames[idx]
    span = f1.lap_dist_pct - f0.lap_dist_pct
    if span < 1e-12:
        return f0.lap_time
    t = (query_pct - f0.lap_dist_pct) / span
    return f0.lap_time + t * (f1.lap_time - f0.lap_time)


class DeltaCalculator:
    """Compute time deltas between a user lap and a reference lap.

    Args:
        n_grid: Number of equally-spaced ``lap_dist_pct`` positions used for
            the point-by-point delta output.
    """

    def __init__(self, n_grid: int = 101) -> None:
        self.n_grid = n_grid

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_point_deltas(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
    ) -> list[tuple[float, float]]:
        """Return ``(lap_dist_pct, delta_seconds)`` for *n_grid* evenly spaced positions.

        ``delta > 0`` means the user is slower; ``delta < 0`` means faster.
        Both laps are interpolated onto the same position grid so different
        sample rates are handled transparently.
        """
        step = 1.0 / (self.n_grid - 1) if self.n_grid > 1 else 1.0
        result: list[tuple[float, float]] = []
        for i in range(self.n_grid):
            p = i * step
            delta = _interpolate_time(user_lap, p) - _interpolate_time(ref_lap, p)
            result.append((p, delta))
        return result

    def compute_corner_deltas(
        self,
        user_lap: list[LapFrame],
        ref_lap: list[LapFrame],
        corners: list[Corner],
    ) -> list[CornerDelta]:
        """Return one :class:`CornerDelta` per corner in *corners*.

        * ``delta_entry / apex / exit``: point delta at each phase boundary.
        * ``delta_total = delta_exit - delta_entry``: time gained/lost *within*
          this corner (positive = time lost here).
        """
        def d(pct: float) -> float:
            return _interpolate_time(user_lap, pct) - _interpolate_time(ref_lap, pct)

        result: list[CornerDelta] = []
        for corner in corners:
            de = d(corner.entry_pct)
            da = d(corner.apex_pct)
            dx = d(corner.exit_pct)
            result.append(CornerDelta(
                corner_id=corner.id,
                delta_entry=de,
                delta_apex=da,
                delta_exit=dx,
                delta_total=dx - de,
            ))
        return result
