"""Tests for LapReportAggregator — S4-US1."""

from __future__ import annotations

import json

import pytest

from racing_coach.analysis.models import (
    ApexSpeedResult,
    BrakingEvent,
    CornerDelta,
    ThrottleEvent,
)
from racing_coach.reporting.aggregator import LapReportAggregator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _delta(corner_id: int, delta_total: float = 0.5) -> CornerDelta:
    return CornerDelta(
        corner_id=corner_id,
        delta_entry=0.1,
        delta_apex=0.2,
        delta_exit=0.3,
        delta_total=delta_total,
    )


def _braking(corner_id: int) -> BrakingEvent:
    return BrakingEvent(
        corner_id=corner_id,
        brake_point_pct=0.25,
        ref_brake_point_pct=0.24,
        brake_point_delta_m=12.0,
        peak_pressure=0.9,
        time_to_peak_s=0.1,
        trail_brake_linearity=0.85,
        lock_detected=False,
    )


def _throttle(corner_id: int) -> ThrottleEvent:
    return ThrottleEvent(
        corner_id=corner_id,
        throttle_point_pct=0.35,
        too_early_full_throttle=False,
        overlap_count=0,
    )


def _apex(corner_id: int, too_slow: bool = False) -> ApexSpeedResult:
    return ApexSpeedResult(
        corner_id=corner_id,
        min_speed_mps=30.0,
        ref_min_speed_mps=32.0,
        delta_kph=-7.2,
        too_slow=too_slow,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_aggregate_creates_report_with_metadata():
    agg = LapReportAggregator()
    report = agg.aggregate("sess1", 3, "Spa", "Ferrari", 1.5, [_delta(1)])
    assert report.session_id == "sess1"
    assert report.lap_number == 3
    assert report.track == "Spa"
    assert report.car == "Ferrari"
    assert report.total_delta_s == pytest.approx(1.5)


def test_aggregate_correct_corner_count():
    agg = LapReportAggregator()
    deltas = [_delta(1), _delta(2), _delta(3)]
    report = agg.aggregate("s", 1, "T", "C", 1.0, deltas)
    assert len(report.corners) == 3


def test_corners_sorted_by_delta_total_descending():
    agg = LapReportAggregator()
    deltas = [_delta(1, 0.3), _delta(2, 0.8), _delta(3, 0.1)]
    report = agg.aggregate("s", 1, "T", "C", 1.2, deltas)
    totals = [c.delta_total for c in report.corners]
    assert totals == sorted(totals, reverse=True)
    assert report.corners[0].corner_id == 2


def test_braking_events_attached_by_corner_id():
    agg = LapReportAggregator()
    report = agg.aggregate(
        "s", 1, "T", "C", 1.0,
        [_delta(1), _delta(2)],
        braking_events=[_braking(1)],
    )
    corner_map = {c.corner_id: c for c in report.corners}
    assert corner_map[1].braking is not None
    assert corner_map[1].braking.corner_id == 1
    assert corner_map[2].braking is None


def test_throttle_events_attached():
    agg = LapReportAggregator()
    report = agg.aggregate(
        "s", 1, "T", "C", 1.0,
        [_delta(1), _delta(2)],
        throttle_events=[_throttle(2)],
    )
    corner_map = {c.corner_id: c for c in report.corners}
    assert corner_map[2].throttle is not None
    assert corner_map[1].throttle is None


def test_apex_results_attached():
    agg = LapReportAggregator()
    report = agg.aggregate(
        "s", 1, "T", "C", 1.0,
        [_delta(1), _delta(2)],
        apex_results=[_apex(2)],
    )
    corner_map = {c.corner_id: c for c in report.corners}
    assert corner_map[2].apex_speed is not None
    assert corner_map[1].apex_speed is None


def test_no_analysis_events_gives_none_fields():
    agg = LapReportAggregator()
    report = agg.aggregate("s", 1, "T", "C", 1.0, [_delta(1)])
    assert report.corners[0].braking is None
    assert report.corners[0].throttle is None
    assert report.corners[0].apex_speed is None


def test_report_json_serializable():
    agg = LapReportAggregator()
    report = agg.aggregate(
        "s", 1, "Spa", "Ferrari", 1.0,
        [_delta(1), _delta(2)],
        braking_events=[_braking(1)],
        throttle_events=[_throttle(2)],
        apex_results=[_apex(1)],
    )
    d = report.to_dict()
    raw = json.dumps(d)
    restored = json.loads(raw)
    assert restored["session_id"] == "s"
    assert len(restored["corners"]) == 2


def test_empty_corner_list():
    agg = LapReportAggregator()
    report = agg.aggregate("s", 1, "T", "C", 0.0, [])
    assert report.corners == []
    assert report.total_delta_s == pytest.approx(0.0)


def test_top_improvements_initially_empty():
    agg = LapReportAggregator()
    report = agg.aggregate("s", 1, "T", "C", 1.0, [_delta(1)])
    assert report.top_improvements == []


def test_summary_initially_empty():
    agg = LapReportAggregator()
    report = agg.aggregate("s", 1, "T", "C", 1.0, [_delta(1)])
    assert report.summary == ""
