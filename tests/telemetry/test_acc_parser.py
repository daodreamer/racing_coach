"""Tests for ACCParser — ACC telemetry field conversions."""

from __future__ import annotations

import pytest

from racing_coach.telemetry.acc_parser import ACCParser
from racing_coach.telemetry.models import TelemetryFrame


def make_raw(**overrides) -> dict:
    """Return a minimal valid raw ACC data dict (merged physics + graphics)."""
    base = {
        "speedKmh": 180.0,  # → speed = 50.0 m/s
        "gas": 0.8,
        "brake": 0.0,
        "steerAngle": 0.1,
        "gear": 4,
        "rpms": 6500,
        "accG": [0.5, 0.0, 0.5],  # [lat, vert, lon] already in G units
        "normalizedCarPosition": 0.45,
        "completedLaps": 3,
        "iCurrentTime": 42500,  # ms → 42.5 s
    }
    base.update(overrides)
    return base


@pytest.fixture
def parser() -> ACCParser:
    return ACCParser()


# ---------------------------------------------------------------------------
# AC1: all 11 fields present and correct types
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


# ---------------------------------------------------------------------------
# AC2: field conversions are correct
# ---------------------------------------------------------------------------


def test_parse_speed_kmh_to_ms(parser):
    """speedKmh ÷ 3.6 → speed in m/s."""
    frame = parser.parse(make_raw(speedKmh=180.0))
    assert frame.speed == pytest.approx(50.0, rel=1e-4)


def test_parse_throttle_direct(parser):
    frame = parser.parse(make_raw(gas=0.75))
    assert frame.throttle == pytest.approx(0.75)


def test_parse_brake_direct(parser):
    frame = parser.parse(make_raw(brake=0.5))
    assert frame.brake == pytest.approx(0.5)


def test_parse_steering_angle_direct(parser):
    frame = parser.parse(make_raw(steerAngle=0.3))
    assert frame.steering_angle == pytest.approx(0.3)


def test_parse_gear_direct(parser):
    frame = parser.parse(make_raw(gear=3))
    assert frame.gear == 3


def test_parse_rpm_int_to_float(parser):
    """rpms (int) → rpm (float)."""
    frame = parser.parse(make_raw(rpms=8000))
    assert frame.rpm == pytest.approx(8000.0)
    assert isinstance(frame.rpm, float)


def test_parse_g_force_lon_from_accg2(parser):
    """accG[2] is already in G — direct mapping."""
    frame = parser.parse(make_raw(accG=[0.0, 0.0, 1.0]))
    assert frame.g_force_lon == pytest.approx(1.0, rel=1e-4)


def test_parse_g_force_lat_negated(parser):
    """accG[0] positive = left → negate → g_force_lat (positive = right)."""
    frame = parser.parse(make_raw(accG=[1.0, 0.0, 0.0]))
    assert frame.g_force_lat == pytest.approx(-1.0, rel=1e-4)


def test_parse_lap_dist_pct_direct(parser):
    frame = parser.parse(make_raw(normalizedCarPosition=0.75))
    assert frame.lap_dist_pct == pytest.approx(0.75)


def test_parse_lap_number_direct(parser):
    frame = parser.parse(make_raw(completedLaps=5))
    assert frame.lap_number == 5


def test_parse_lap_time_ms_to_s(parser):
    """iCurrentTime (ms) ÷ 1000 → lap_time in seconds."""
    frame = parser.parse(make_raw(iCurrentTime=65500))
    assert frame.lap_time == pytest.approx(65.5)


# ---------------------------------------------------------------------------
# AC3: out-of-range values are clamped
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,key,bad_value,expected",
    [
        ("speed", "speedKmh", -36.0, 0.0),
        ("throttle", "gas", -0.1, 0.0),
        ("throttle", "gas", 1.5, 1.0),
        ("brake", "brake", -0.1, 0.0),
        ("brake", "brake", 1.5, 1.0),
        ("rpm", "rpms", -100, 0.0),
        ("lap_dist_pct", "normalizedCarPosition", -0.1, 0.0),
        ("lap_dist_pct", "normalizedCarPosition", 1.1, 1.0),
        ("lap_number", "completedLaps", -1, 0),
        ("lap_time", "iCurrentTime", -1000, 0.0),
    ],
)
def test_parse_clamps_out_of_range(parser, field, key, bad_value, expected):
    raw = make_raw(**{key: bad_value})
    frame = parser.parse(raw)
    assert getattr(frame, field) == pytest.approx(expected), (
        f"{field}: expected {expected}, got {getattr(frame, field)}"
    )


def test_parse_nan_speed_clamped(parser):
    raw = make_raw(speedKmh=float("nan"))
    frame = parser.parse(raw)
    assert frame.is_valid()


def test_parse_inf_rpm_clamped(parser):
    raw = make_raw(rpms=float("inf"))
    frame = parser.parse(raw)
    assert frame.is_valid()


# ---------------------------------------------------------------------------
# AC4: performance — parse < 1ms mean over 1000 rounds
# ---------------------------------------------------------------------------


def test_parse_performance(benchmark, parser):
    raw = make_raw()
    result = benchmark.pedantic(parser.parse, args=(raw,), rounds=1000, iterations=1)
    assert isinstance(result, TelemetryFrame)
    stats = benchmark.stats
    assert stats["mean"] < 0.001, f"parse mean {stats['mean'] * 1000:.3f}ms exceeds 1ms"
