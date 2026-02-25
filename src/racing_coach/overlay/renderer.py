"""Overlay rendering — data formatting for the in-game HUD."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OverlayData:
    """Snapshot of data to display on the overlay.

    Parameters
    ----------
    delta_s:
        Cumulative time delta vs reference lap (seconds).
        Positive = driver is slower than reference.
    throttle:
        Current throttle input [0.0, 1.0].
    brake:
        Current brake input [0.0, 1.0].
    ref_throttle:
        Reference lap throttle at the same track position [0.0, 1.0].
    ref_brake:
        Reference lap brake at the same track position [0.0, 1.0].
    lap_dist_pct:
        Current lap distance fraction [0.0, 1.0].
    """

    delta_s: float
    throttle: float
    brake: float
    ref_throttle: float
    ref_brake: float
    lap_dist_pct: float


class OverlayRenderer:
    """Formats :class:`OverlayData` for display.

    All values are pure data transformations with no side effects — safe to
    call from any thread.
    """

    def format_delta(self, delta_s: float) -> str:
        """Format a delta value as a signed string with 3 decimal places.

        Examples
        --------
        >>> OverlayRenderer().format_delta(0.342)
        '+0.342'
        >>> OverlayRenderer().format_delta(-0.125)
        '-0.125'
        """
        sign = "+" if delta_s >= 0 else ""
        return f"{sign}{delta_s:.3f}"

    def render(self, data: OverlayData) -> dict:
        """Return a display-ready dict from an :class:`OverlayData` snapshot.

        Returns
        -------
        dict with keys:
            ``delta``         – formatted delta string (e.g. ``'+0.342'``)
            ``throttle``      – integer percentage 0–100
            ``brake``         – integer percentage 0–100
            ``ref_throttle``  – integer percentage 0–100
            ``ref_brake``     – integer percentage 0–100
            ``lap_dist_pct``  – float [0.0, 1.0]
        """
        return {
            "delta": self.format_delta(data.delta_s),
            "throttle": round(data.throttle * 100),
            "brake": round(data.brake * 100),
            "ref_throttle": round(data.ref_throttle * 100),
            "ref_brake": round(data.ref_brake * 100),
            "lap_dist_pct": data.lap_dist_pct,
        }
