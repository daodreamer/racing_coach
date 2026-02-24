"""Tests for MarkdownFormatter — S4-US4."""

from __future__ import annotations

import re

from racing_coach.analysis.models import ApexSpeedResult, BrakingEvent, ThrottleEvent
from racing_coach.reporting.aggregator import LapReportAggregator
from racing_coach.reporting.formatter import MarkdownFormatter
from racing_coach.reporting.models import LapReport, Suggestion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_full_report() -> LapReport:
    from racing_coach.analysis.models import CornerDelta

    agg = LapReportAggregator()
    deltas = [
        CornerDelta(1, 0.1, 0.2, 0.3, 0.5),
        CornerDelta(2, 0.0, 0.05, 0.1, 0.1),
        CornerDelta(3, -0.1, -0.05, 0.0, -0.1),
    ]
    braking = [
        BrakingEvent(1, 0.25, 0.24, 15.0, 0.9, 0.1, 0.85, True),
        BrakingEvent(2, 0.5, 0.5, 0.0, 0.7, 0.12, 0.95, False),
        BrakingEvent(3, 0.75, 0.75, -2.0, 0.8, 0.08, 0.9, False),
    ]
    throttle = [
        ThrottleEvent(1, 0.35, True, 3),
        ThrottleEvent(2, 0.6, False, 0),
        ThrottleEvent(3, 0.82, False, 0),
    ]
    apex = [
        ApexSpeedResult(1, 28.0, 33.0, -18.0, True),
        ApexSpeedResult(2, 31.0, 32.0, -3.6, False),
        ApexSpeedResult(3, 35.0, 33.0, 7.2, False),
    ]
    report = agg.aggregate("sess1", 5, "Spa-Francorchamps", "Ferrari 488 GT3", 1.8,
                           deltas, braking, throttle, apex)
    report.summary = "良好的圈速，但弯道1的刹车和出弯油门需要改进。"
    report.top_improvements = [
        Suggestion(1, "high", "弯道1刹车点偏晚，建议提前15m刹车。"),
        Suggestion(1, "medium", "弯道1过早全油门，等车头稳定后再加速。"),
        Suggestion(1, "medium", "弯道1弯心速度偏低18km/h。"),
    ]
    return report


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_format_contains_main_header():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "# " in md  # Markdown h1


def test_format_contains_track_and_car():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "Spa-Francorchamps" in md
    assert "Ferrari 488 GT3" in md


def test_format_contains_total_delta():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "1.8" in md or "+1.800" in md


def test_format_contains_summary_section():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "概要" in md
    assert "刹车" in md  # part of the summary text


def test_format_skips_summary_section_when_empty():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    report.summary = ""
    md = fmt.format(report)
    assert "概要" not in md


def test_format_contains_corner_section_for_each_corner():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    for i in range(1, 4):
        assert f"弯道 {i}" in md


def test_format_shows_lock_warning():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "抱死" in md


def test_format_shows_early_throttle_warning():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "过早全油门" in md or "早油门" in md


def test_format_shows_apex_speed_too_slow():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "偏慢" in md or "弯心速度" in md


def test_format_contains_top_improvements():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    md = fmt.format(report)
    assert "优先改进" in md or "Top 3" in md or "改进" in md


def test_format_top_improvements_at_most_3():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    report.top_improvements = [Suggestion(i, "high", f"fix {i}") for i in range(1, 6)]
    md = fmt.format(report)
    # Only the first 3 should appear as numbered items
    numbered = re.findall(r"^\d+\.", md, re.MULTILINE)
    assert len(numbered) <= 3


def test_format_no_top_improvements_skips_section():
    fmt = MarkdownFormatter()
    report = _make_full_report()
    report.top_improvements = []
    md = fmt.format(report)
    assert "优先改进" not in md


def test_write_creates_file(tmp_path):
    fmt = MarkdownFormatter()
    report = _make_full_report()
    out = tmp_path / "report.md"
    fmt.write(report, str(out))
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert len(content) > 100
    assert "Spa-Francorchamps" in content
