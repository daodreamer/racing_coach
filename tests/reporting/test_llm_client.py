"""Tests for MoonshotClient, response parsing, and fallback — S4-US3."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

from racing_coach.analysis.models import ApexSpeedResult, BrakingEvent, ThrottleEvent
from racing_coach.reporting.aggregator import LapReportAggregator
from racing_coach.reporting.llm_client import (
    MoonshotClient,
    fallback_suggestions,
    parse_llm_response,
)
from racing_coach.reporting.models import LapReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report() -> LapReport:
    from racing_coach.analysis.models import CornerDelta

    agg = LapReportAggregator()
    deltas = [
        CornerDelta(corner_id=1, delta_entry=0.1, delta_apex=0.2, delta_exit=0.3, delta_total=0.5),
        CornerDelta(corner_id=2, delta_entry=0.0, delta_apex=0.1, delta_exit=0.2, delta_total=0.2),
    ]
    braking = [
        BrakingEvent(1, 0.25, 0.24, 15.0, 0.9, 0.1, 0.85, True),   # lock_detected
        BrakingEvent(2, 0.50, 0.49, 5.0, 0.7, 0.1, 0.9, False),
    ]
    throttle = [
        ThrottleEvent(1, 0.35, True, 2),   # too_early_full_throttle
        ThrottleEvent(2, 0.60, False, 0),
    ]
    apex = [
        ApexSpeedResult(1, 28.0, 33.0, -18.0, True),  # too_slow
        ApexSpeedResult(2, 32.0, 33.0, -3.6, False),
    ]
    return agg.aggregate("s", 1, "Spa", "Ferrari", 0.7, deltas, braking, throttle, apex)


def _make_openai_response(content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    mock = MagicMock()
    mock.choices[0].message.content = content
    mock.usage.prompt_tokens = prompt_tokens
    mock.usage.completion_tokens = completion_tokens
    mock.usage.total_tokens = prompt_tokens + completion_tokens
    return mock


# ---------------------------------------------------------------------------
# parse_llm_response tests
# ---------------------------------------------------------------------------


def test_parse_llm_response_valid():
    raw = json.dumps({
        "summary": "Good lap overall.",
        "suggestions": [
            {"corner_id": 1, "severity": "high", "suggestion": "Brake earlier."},
            {"corner_id": 2, "severity": "low", "suggestion": "Smooth throttle."},
        ],
    })
    summary, suggestions = parse_llm_response(raw)
    assert summary == "Good lap overall."
    assert len(suggestions) == 2
    assert suggestions[0].corner_id == 1
    assert suggestions[0].severity == "high"
    assert suggestions[1].corner_id == 2


def test_parse_llm_response_invalid_json_returns_empty():
    summary, suggestions = parse_llm_response("not json {{")
    assert summary == ""
    assert suggestions == []


def test_parse_llm_response_missing_fields_returns_empty():
    summary, suggestions = parse_llm_response("{}")
    assert summary == ""
    assert suggestions == []


def test_parse_llm_response_invalid_severity_normalized_to_medium():
    raw = json.dumps({
        "summary": "ok",
        "suggestions": [{"corner_id": 1, "severity": "EXTREME", "suggestion": "x"}],
    })
    _, suggestions = parse_llm_response(raw)
    assert suggestions[0].severity == "medium"


# ---------------------------------------------------------------------------
# fallback_suggestions tests
# ---------------------------------------------------------------------------


def test_fallback_generates_high_for_lock():
    report = _make_report()
    suggestions = fallback_suggestions(report)
    # Corner 1 has lock_detected → at least one "high" suggestion for it
    high_for_1 = [s for s in suggestions if s.corner_id == 1 and s.severity == "high"]
    assert len(high_for_1) >= 1


def test_fallback_generates_suggestion_for_early_throttle():
    report = _make_report()
    suggestions = fallback_suggestions(report)
    texts = [s.suggestion for s in suggestions if s.corner_id == 1]
    assert any("油门" in t or "全油门" in t for t in texts)


def test_fallback_generates_suggestion_for_too_slow_apex():
    report = _make_report()
    suggestions = fallback_suggestions(report)
    texts = [s.suggestion for s in suggestions if s.corner_id == 1]
    assert any("弯心" in t or "速度" in t for t in texts)


def test_fallback_no_errors_returns_empty():
    from racing_coach.analysis.models import CornerDelta

    agg = LapReportAggregator()
    deltas = [CornerDelta(1, 0.0, 0.0, 0.0, 0.0)]
    clean_braking = [BrakingEvent(1, 0.25, 0.25, 0.0, 0.8, 0.1, 0.9, False)]
    clean_throttle = [ThrottleEvent(1, 0.35, False, 0)]
    clean_apex = [ApexSpeedResult(1, 32.0, 32.0, 0.0, False)]
    report = agg.aggregate("s", 1, "T", "C", 0.0, deltas, clean_braking, clean_throttle, clean_apex)
    suggestions = fallback_suggestions(report)
    assert suggestions == []


# ---------------------------------------------------------------------------
# MoonshotClient tests (mocked)
# ---------------------------------------------------------------------------


def test_generate_success_returns_text_and_usage():
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        payload = json.dumps({"summary": "ok", "suggestions": []})
        mock_client.chat.completions.create.return_value = _make_openai_response(
            payload, prompt_tokens=80, completion_tokens=40
        )

        client = MoonshotClient(api_key="test-key")
        text, usage = client.generate("sys", "user")

    assert text == payload
    assert usage["prompt_tokens"] == 80
    assert usage["completion_tokens"] == 40
    assert usage["total_tokens"] == 120


def test_generate_logs_usage(caplog):
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response(
            "{}", prompt_tokens=50, completion_tokens=20
        )

        with caplog.at_level(logging.INFO, logger="racing_coach.reporting.llm_client"):
            client = MoonshotClient(api_key="test-key")
            client.generate("sys", "user")

    assert any("50" in r.message and "20" in r.message for r in caplog.records)


def test_generate_timeout_returns_empty_and_no_exception():
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        from openai import OpenAIError

        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("timeout")

        client = MoonshotClient(api_key="test-key")
        text, usage = client.generate("sys", "user")

    assert text == ""
    assert usage == {}


def test_generate_api_error_returns_empty():
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        from openai import OpenAIError

        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("server error")

        client = MoonshotClient(api_key="test-key")
        text, usage = client.generate("sys", "user")

    assert text == ""
    assert usage == {}


def test_analyze_applies_suggestions_from_llm():
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        payload = json.dumps({
            "summary": "Good braking, improve corner 1 exit.",
            "suggestions": [
                {"corner_id": 1, "severity": "high", "suggestion": "Brake 15m earlier."},
            ],
        })
        mock_client.chat.completions.create.return_value = _make_openai_response(payload)

        report = _make_report()
        client = MoonshotClient(api_key="test-key")
        result = client.analyze(report)

    assert result.summary == "Good braking, improve corner 1 exit."
    corner_map = {c.corner_id: c for c in result.corners}
    assert len(corner_map[1].suggestions) == 1
    assert corner_map[1].suggestions[0].severity == "high"


def test_analyze_falls_back_on_api_failure():
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        from openai import OpenAIError

        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("down")

        report = _make_report()
        client = MoonshotClient(api_key="test-key")
        result = client.analyze(report)

    # fallback should still produce suggestions for the detected errors
    assert len(result.top_improvements) > 0
    assert "LLM" in result.summary or "规则" in result.summary


def test_analyze_top_improvements_at_most_3():
    with patch("racing_coach.reporting.llm_client.OpenAI") as MockOpenAI:
        from openai import OpenAIError

        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("down")

        report = _make_report()
        client = MoonshotClient(api_key="test-key")
        result = client.analyze(report)

    assert len(result.top_improvements) <= 3
