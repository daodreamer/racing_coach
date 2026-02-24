"""Track modeling data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrackPoint:
    """A single point on the track centerline.

    Coordinates use whatever units are consistent with the source data
    (typically metres for real telemetry).
    """

    lap_dist_pct: float
    """Fraction of lap completed [0.0, 1.0]."""

    x: float
    """X coordinate."""

    y: float
    """Y coordinate."""


@dataclass
class Corner:
    """A detected corner with entry/apex/exit three-phase division.

    Phase layout (all values are ``lap_dist_pct``):

    ::

        entry_pct ──[Entry]── apex_start ──[Apex]── apex_end ──[Exit]── exit_pct

    The three phases are adjacent and cover the full corner with no gaps.
    """

    id: int
    """Sequential corner number (1-based)."""

    entry_pct: float
    """Corner start (= entry_start of the Entry phase)."""

    apex_pct: float
    """Point of maximum curvature magnitude (within the Apex phase)."""

    exit_pct: float
    """Corner end (= exit_end of the Exit phase)."""

    direction: str
    """Turn direction: ``'L'`` (left/counterclockwise) or ``'R'`` (right/clockwise)."""

    apex_start: float
    """Start of the Apex zone (= end of the Entry phase)."""

    apex_end: float
    """End of the Apex zone (= start of the Exit phase)."""
