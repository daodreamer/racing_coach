"""Analysis result aggregation — S4-US1."""

from __future__ import annotations

from racing_coach.analysis.models import (
    ApexSpeedResult,
    BrakingEvent,
    CornerDelta,
    ThrottleEvent,
)
from racing_coach.reporting.models import CornerReport, LapReport


class LapReportAggregator:
    """Combine Sprint 3 analysis results into a single :class:`LapReport`.

    All analysis lists are optional; missing data simply leaves the
    corresponding :class:`CornerReport` field as ``None``.
    """

    def aggregate(
        self,
        session_id: str,
        lap_number: int,
        track: str,
        car: str,
        total_delta_s: float,
        corner_deltas: list[CornerDelta],
        braking_events: list[BrakingEvent] | None = None,
        throttle_events: list[ThrottleEvent] | None = None,
        apex_results: list[ApexSpeedResult] | None = None,
    ) -> LapReport:
        """Build a :class:`LapReport` from per-corner analysis results.

        ``corners`` in the returned report are sorted by ``delta_total``
        descending so the biggest time losses appear first.
        """
        braking_map = {b.corner_id: b for b in (braking_events or [])}
        throttle_map = {t.corner_id: t for t in (throttle_events or [])}
        apex_map = {a.corner_id: a for a in (apex_results or [])}

        corners = [
            CornerReport(
                corner_id=cd.corner_id,
                delta_entry=cd.delta_entry,
                delta_apex=cd.delta_apex,
                delta_exit=cd.delta_exit,
                delta_total=cd.delta_total,
                braking=braking_map.get(cd.corner_id),
                throttle=throttle_map.get(cd.corner_id),
                apex_speed=apex_map.get(cd.corner_id),
            )
            for cd in corner_deltas
        ]

        corners.sort(key=lambda c: c.delta_total, reverse=True)

        return LapReport(
            session_id=session_id,
            lap_number=lap_number,
            track=track,
            car=car,
            total_delta_s=total_delta_s,
            corners=corners,
        )
