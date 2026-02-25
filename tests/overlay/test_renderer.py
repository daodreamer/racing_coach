"""Tests for OverlayRenderer (Sprint 7 — S7-US3)."""

from __future__ import annotations

import pytest

from racing_coach.overlay.renderer import OverlayData, OverlayRenderer

# ---------------------------------------------------------------------------
# format_delta
# ---------------------------------------------------------------------------


def test_format_delta_positive():
    renderer = OverlayRenderer()
    assert renderer.format_delta(0.342) == "+0.342"


def test_format_delta_negative():
    renderer = OverlayRenderer()
    assert renderer.format_delta(-0.125) == "-0.125"


def test_format_delta_zero():
    renderer = OverlayRenderer()
    assert renderer.format_delta(0.0) == "+0.000"


def test_format_delta_three_decimal_places():
    renderer = OverlayRenderer()
    result = renderer.format_delta(1.1)
    assert result == "+1.100"


@pytest.mark.parametrize(
    "delta, expected_prefix",
    [
        (0.001, "+"),
        (-0.001, "-"),
        (0.0, "+"),
    ],
)
def test_format_delta_sign(delta, expected_prefix):
    renderer = OverlayRenderer()
    assert renderer.format_delta(delta).startswith(expected_prefix)


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def _data(**kwargs) -> OverlayData:
    defaults = dict(
        delta_s=0.0,
        throttle=0.0,
        brake=0.0,
        ref_throttle=0.0,
        ref_brake=0.0,
        lap_dist_pct=0.0,
    )
    defaults.update(kwargs)
    return OverlayData(**defaults)


def test_render_contains_required_keys():
    renderer = OverlayRenderer()
    result = renderer.render(_data())
    for key in ("delta", "throttle", "brake", "ref_throttle", "ref_brake", "lap_dist_pct"):
        assert key in result


def test_render_throttle_percentage():
    renderer = OverlayRenderer()
    result = renderer.render(_data(throttle=0.75))
    assert result["throttle"] == 75


def test_render_brake_percentage():
    renderer = OverlayRenderer()
    result = renderer.render(_data(brake=0.50))
    assert result["brake"] == 50


def test_render_ref_throttle_percentage():
    renderer = OverlayRenderer()
    result = renderer.render(_data(ref_throttle=0.30))
    assert result["ref_throttle"] == 30


def test_render_ref_brake_percentage():
    renderer = OverlayRenderer()
    result = renderer.render(_data(ref_brake=1.0))
    assert result["ref_brake"] == 100


def test_render_delta_string():
    renderer = OverlayRenderer()
    result = renderer.render(_data(delta_s=0.512))
    assert result["delta"] == "+0.512"


def test_render_lap_dist_pct_passthrough():
    renderer = OverlayRenderer()
    result = renderer.render(_data(lap_dist_pct=0.42))
    assert result["lap_dist_pct"] == pytest.approx(0.42)


def test_render_full_throttle():
    renderer = OverlayRenderer()
    result = renderer.render(_data(throttle=1.0))
    assert result["throttle"] == 100


def test_render_zero_inputs():
    renderer = OverlayRenderer()
    result = renderer.render(_data())
    assert result["throttle"] == 0
    assert result["brake"] == 0
    assert result["ref_throttle"] == 0
    assert result["ref_brake"] == 0
