"""Reporting data models — S4-US1."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from racing_coach.analysis.models import ApexSpeedResult, BrakingEvent, ThrottleEvent


@dataclass
class Suggestion:
    """A single improvement suggestion for one corner.

    Args:
        corner_id: Which corner this suggestion applies to.
        severity: ``'high'``, ``'medium'``, or ``'low'``.
        suggestion: Human-readable actionable advice.
    """

    corner_id: int
    severity: str
    suggestion: str


@dataclass
class CornerReport:
    """Aggregated analysis for a single corner.

    Combines delta timing with optional braking/throttle/apex analysis and
    any LLM-generated suggestions.
    """

    corner_id: int
    delta_entry: float
    delta_apex: float
    delta_exit: float
    delta_total: float
    braking: BrakingEvent | None = None
    throttle: ThrottleEvent | None = None
    apex_speed: ApexSpeedResult | None = None
    suggestions: list[Suggestion] = field(default_factory=list)


@dataclass
class LapReport:
    """Full analysis report for a single lap.

    ``corners`` is sorted by ``delta_total`` descending (most time lost first).
    ``top_improvements`` and ``summary`` are populated by the LLM client.
    """

    session_id: str
    lap_number: int
    track: str
    car: str
    total_delta_s: float
    corners: list[CornerReport]
    top_improvements: list[Suggestion] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict (recursive via :func:`dataclasses.asdict`)."""
        return dataclasses.asdict(self)
