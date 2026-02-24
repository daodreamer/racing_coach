"""Tests for PromptBuilder and token estimation — S4-US2."""

from __future__ import annotations

from racing_coach.analysis.models import ApexSpeedResult, BrakingEvent, ThrottleEvent
from racing_coach.reporting.aggregator import LapReportAggregator
from racing_coach.reporting.models import LapReport
from racing_coach.reporting.prompt import PromptBuilder, estimate_tokens

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(num_corners: int = 3) -> LapReport:
    from racing_coach.analysis.models import CornerDelta

    agg = LapReportAggregator()
    deltas = [
        CornerDelta(
            corner_id=i,
            delta_entry=0.05 * i,
            delta_apex=0.1 * i,
            delta_exit=0.15 * i,
            delta_total=0.2 * i,
        )
        for i in range(1, num_corners + 1)
    ]
    braking = [
        BrakingEvent(i, 0.25, 0.24, 12.0, 0.9, 0.1, 0.85, False)
        for i in range(1, num_corners + 1)
    ]
    throttle = [
        ThrottleEvent(i, 0.35, False, 0)
        for i in range(1, num_corners + 1)
    ]
    apex = [
        ApexSpeedResult(i, 30.0, 32.0, -7.2, True)
        for i in range(1, num_corners + 1)
    ]
    return agg.aggregate("s", 1, "Spa", "Ferrari 488 GT3", 1.5, deltas, braking, throttle, apex)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_contains_track_and_car():
    builder = PromptBuilder()
    report = _make_report()
    prompt = builder.build(report)
    assert "Spa" in prompt
    assert "Ferrari 488 GT3" in prompt


def test_build_contains_total_delta():
    builder = PromptBuilder()
    report = _make_report()
    prompt = builder.build(report)
    assert "1.5" in prompt or "+1.5" in prompt


def test_build_contains_corner_ids():
    builder = PromptBuilder()
    report = _make_report(3)
    prompt = builder.build(report)
    for i in range(1, 4):
        assert str(i) in prompt


def test_build_contains_braking_info():
    builder = PromptBuilder()
    report = _make_report()
    prompt = builder.build(report)
    assert "刹车" in prompt


def test_build_contains_apex_speed_info():
    builder = PromptBuilder()
    report = _make_report()
    prompt = builder.build(report)
    assert "弯心速度" in prompt


def test_system_prompt_contains_anti_hallucination():
    builder = PromptBuilder()
    system = builder.system_prompt
    # Must contain explicit constraint against fabricating data
    assert "不得编造" in system or "严禁编造" in system


def test_system_prompt_contains_json_format_instruction():
    builder = PromptBuilder()
    system = builder.system_prompt
    assert "JSON" in system


def test_build_contains_json_output_format():
    builder = PromptBuilder()
    report = _make_report()
    prompt = builder.build(report)
    assert "summary" in prompt
    assert "suggestions" in prompt


def test_build_messages_returns_two_strings():
    builder = PromptBuilder()
    report = _make_report()
    result = builder.build_messages(report)
    assert len(result) == 2
    system, user = result
    assert isinstance(system, str) and len(system) > 0
    assert isinstance(user, str) and len(user) > 0


def test_prompt_token_estimate_under_2000():
    builder = PromptBuilder()
    report = _make_report(10)  # worst case: 10 corners
    _, user = builder.build_messages(report)
    full = builder.system_prompt + user
    assert estimate_tokens(full) < 2000


def test_estimate_tokens_scales_with_length():
    short = "abc"
    long_ = "abc" * 100
    assert estimate_tokens(long_) > estimate_tokens(short)
