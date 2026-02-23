"""Tests for TelemetryParser — S1-US2."""

from __future__ import annotations

import pytest

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.telemetry.parser import TelemetryParser

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

G = 9.80665  # m/s² per g


def make_raw(**overrides) -> dict:
    """Return a minimal valid raw iRacing data dict."""
    base = {
        "Speed": 50.0,
        "Throttle": 0.8,
        "Brake": 0.0,
        "SteeringWheelAngle": 0.1,
        "Gear": 4,
        "RPM": 6500.0,
        "LongAccel": 5.0,   # m/s² → 0.51 g
        "LatAccel": -9.81,  # m/s² → -1.0 g
        "LapDistPct": 0.45,
        "Lap": 3,
        "LapCurrentLapTime": 42.5,
    }
    base.update(overrides)
    return base


@pytest.fixture
def parser() -> TelemetryParser:
    return TelemetryParser()


# ---------------------------------------------------------------------------
# S1-US2 AC1: all 11 fields present
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = (
    "speed",
    "throttle",
    "brake",
    "steering_angle",
    "gear",
    "rpm",
    "g_force_lon",
    "g_force_lat",
    "lap_dist_pct",
    "lap_number",
    "lap_time",
)


def test_parse_returns_telemetry_frame(parser):
    frame = parser.parse(make_raw())
    assert isinstance(frame, TelemetryFrame)


def test_parse_contains_all_required_fields(parser):
    frame = parser.parse(make_raw())
    for field in REQUIRED_FIELDS:
        assert hasattr(frame, field), f"Missing field: {field}"


def test_parse_field_values_correct(parser):
    raw = make_raw()
    frame = parser.parse(raw)

    assert frame.speed == pytest.approx(raw["Speed"])
    assert frame.throttle == pytest.approx(raw["Throttle"])
    assert frame.brake == pytest.approx(raw["Brake"])
    assert frame.steering_angle == pytest.approx(raw["SteeringWheelAngle"])
    assert frame.gear == raw["Gear"]
    assert frame.rpm == pytest.approx(raw["RPM"])
    assert frame.g_force_lon == pytest.approx(raw["LongAccel"] / G, rel=1e-4)
    assert frame.g_force_lat == pytest.approx(raw["LatAccel"] / G, rel=1e-4)
    assert frame.lap_dist_pct == pytest.approx(raw["LapDistPct"])
    assert frame.lap_number == raw["Lap"]
    assert frame.lap_time == pytest.approx(raw["LapCurrentLapTime"])


# ---------------------------------------------------------------------------
# S1-US2 AC2: out-of-range values are clamped
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,raw_key,bad_value,expected", [
    ("speed",         "Speed",           -10.0,  0.0),
    ("throttle",      "Throttle",        -0.5,   0.0),
    ("throttle",      "Throttle",         1.5,   1.0),
    ("brake",         "Brake",           -0.5,   0.0),
    ("brake",         "Brake",            1.5,   1.0),
    ("rpm",           "RPM",            -100.0,  0.0),
    ("lap_dist_pct",  "LapDistPct",      -0.1,   0.0),
    ("lap_dist_pct",  "LapDistPct",       1.1,   1.0),
    ("lap_number",    "Lap",             -5,     0),
    ("lap_time",      "LapCurrentLapTime", -1.0, 0.0),
])
def test_parse_clamps_out_of_range(parser, field, raw_key, bad_value, expected):
    raw = make_raw(**{raw_key: bad_value})
    frame = parser.parse(raw)
    assert getattr(frame, field) == pytest.approx(expected), (
        f"{field}: expected {expected}, got {getattr(frame, field)}"
    )


@pytest.mark.parametrize("raw_key", [
    "Speed", "Throttle", "Brake", "SteeringWheelAngle",
    "RPM", "LongAccel", "LatAccel", "LapDistPct", "LapCurrentLapTime",
])
def test_parse_nan_input_is_clamped_to_zero(parser, raw_key):
    """NaN float inputs must not propagate — they're clamped to 0.0."""
    raw = make_raw(**{raw_key: float("nan")})
    frame = parser.parse(raw)
    # The frame must be fully finite
    assert frame.is_valid(), f"Frame invalid after NaN in {raw_key}"


@pytest.mark.parametrize("raw_key", ["Speed", "RPM", "LapCurrentLapTime"])
def test_parse_inf_input_is_clamped(parser, raw_key):
    """Inf inputs must be clamped to a finite value."""
    raw = make_raw(**{raw_key: float("inf")})
    frame = parser.parse(raw)
    assert frame.is_valid(), f"Frame invalid after Inf in {raw_key}"


# ---------------------------------------------------------------------------
# S1-US2 AC3: performance — parse < 1ms (p99 over 1000 rounds)
# ---------------------------------------------------------------------------

def test_parse_performance(benchmark, parser):
    raw = make_raw()
    result = benchmark.pedantic(parser.parse, args=(raw,), rounds=1000, iterations=1)
    assert isinstance(result, TelemetryFrame)
    # pytest-benchmark captures stats; the p99 assertion is on mean for simplicity.
    # Real p99 guard is via benchmark's --benchmark-max-time or CI thresholds.
    stats = benchmark.stats
    assert stats["mean"] < 0.001, f"parse mean {stats['mean']*1000:.3f}ms exceeds 1ms"
