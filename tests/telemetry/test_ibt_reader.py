"""Tests for IBTReader — S1-US4."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from racing_coach.telemetry.ibt_reader import IBTReader, IBTReadError
from racing_coach.telemetry.models import TelemetryFrame

# ---------------------------------------------------------------------------
# Helpers: build a fake SDK that simulates a multi-frame .ibt file
# ---------------------------------------------------------------------------

_FRAME_DATA = [
    {
        "Speed": 40.0, "Throttle": 0.5, "Brake": 0.0,
        "SteeringWheelAngle": 0.05, "Gear": 3, "RPM": 5000.0,
        "LongAccel": 3.0, "LatAccel": -5.0,
        "LapDistPct": 0.10, "Lap": 1, "LapCurrentLapTime": 10.0,
    },
    {
        "Speed": 55.0, "Throttle": 1.0, "Brake": 0.0,
        "SteeringWheelAngle": 0.0, "Gear": 4, "RPM": 6200.0,
        "LongAccel": 8.0, "LatAccel": 0.0,
        "LapDistPct": 0.20, "Lap": 1, "LapCurrentLapTime": 12.0,
    },
    {
        "Speed": 30.0, "Throttle": 0.0, "Brake": 0.8,
        "SteeringWheelAngle": 0.3, "Gear": 2, "RPM": 3500.0,
        "LongAccel": -15.0, "LatAccel": -8.0,
        "LapDistPct": 0.30, "Lap": 1, "LapCurrentLapTime": 15.0,
    },
]


def _make_mock_sdk(frames: list[dict] | None = None) -> MagicMock:
    """Return a mock SDK that produces the given frames when iterated."""
    frames = frames or _FRAME_DATA
    sdk = MagicMock()
    sdk.__enter__ = MagicMock(return_value=sdk)
    sdk.__exit__ = MagicMock(return_value=False)

    call_count = {"n": 0}

    def fake_getitem(key):
        idx = call_count["n"]
        return frames[idx].get(key)

    def fake_parse_to_next():
        idx = call_count["n"]
        if idx < len(frames) - 1:
            call_count["n"] += 1
            return True
        return False

    sdk.__getitem__ = MagicMock(side_effect=fake_getitem)
    sdk.parse_to_next = MagicMock(side_effect=fake_parse_to_next)
    sdk.startup = MagicMock(return_value=True)
    sdk.shutdown = MagicMock()
    return sdk


# ---------------------------------------------------------------------------
# S1-US4 AC1: output structure matches S1-US2 (all 11 fields, correct types)
# ---------------------------------------------------------------------------

def test_read_yields_telemetry_frames(tmp_path):
    fake_path = str(tmp_path / "fake.ibt")
    Path(fake_path).touch()

    mock_sdk = _make_mock_sdk()
    reader = IBTReader(sdk_factory=lambda: mock_sdk)
    frames = list(reader.read(fake_path))

    assert len(frames) == len(_FRAME_DATA)
    for frame in frames:
        assert isinstance(frame, TelemetryFrame)


def test_read_frame_has_all_required_fields(tmp_path):
    fake_path = str(tmp_path / "fake.ibt")
    Path(fake_path).touch()

    mock_sdk = _make_mock_sdk()
    reader = IBTReader(sdk_factory=lambda: mock_sdk)
    frame = next(iter(reader.read(fake_path)))

    required = (
        "speed", "throttle", "brake", "steering_angle", "gear",
        "rpm", "g_force_lon", "g_force_lat",
        "lap_dist_pct", "lap_number", "lap_time",
    )
    for field in required:
        assert hasattr(frame, field), f"Missing field: {field}"


def test_read_frame_values_match_raw_data(tmp_path):
    fake_path = str(tmp_path / "fake.ibt")
    Path(fake_path).touch()

    mock_sdk = _make_mock_sdk()
    reader = IBTReader(sdk_factory=lambda: mock_sdk)
    frames = list(reader.read(fake_path))

    first = _FRAME_DATA[0]
    assert frames[0].speed == pytest.approx(first["Speed"])
    assert frames[0].throttle == pytest.approx(first["Throttle"])
    assert frames[0].gear == first["Gear"]
    assert frames[0].lap_number == first["Lap"]


def test_read_all_frames_returned(tmp_path):
    """All frames in the file should be yielded, not just the first."""
    fake_path = str(tmp_path / "fake.ibt")
    Path(fake_path).touch()

    mock_sdk = _make_mock_sdk()
    reader = IBTReader(sdk_factory=lambda: mock_sdk)
    frames = list(reader.read(fake_path))

    assert len(frames) == 3
    assert frames[0].speed == pytest.approx(_FRAME_DATA[0]["Speed"])
    assert frames[1].speed == pytest.approx(_FRAME_DATA[1]["Speed"])
    assert frames[2].speed == pytest.approx(_FRAME_DATA[2]["Speed"])


# ---------------------------------------------------------------------------
# S1-US4 AC2: invalid files raise IBTReadError (not a raw crash)
# ---------------------------------------------------------------------------

def test_read_nonexistent_file_raises_ibt_read_error(tmp_path):
    reader = IBTReader()
    with pytest.raises(IBTReadError, match="not found"):
        list(reader.read(str(tmp_path / "nonexistent.ibt")))


def test_read_empty_file_raises_ibt_read_error(tmp_path):
    empty_file = tmp_path / "empty.ibt"
    empty_file.write_bytes(b"")

    failing_sdk = MagicMock()
    failing_sdk.startup = MagicMock(return_value=False)

    reader = IBTReader(sdk_factory=lambda: failing_sdk)
    with pytest.raises(IBTReadError, match=r"[Cc]ould not open|[Ff]ailed|not open"):
        list(reader.read(str(empty_file)))


def test_read_non_ibt_file_raises_ibt_read_error(tmp_path):
    bad_file = tmp_path / "notanIBT.txt"
    bad_file.write_text("this is not an ibt file")

    failing_sdk = MagicMock()
    failing_sdk.startup = MagicMock(return_value=False)

    reader = IBTReader(sdk_factory=lambda: failing_sdk)
    with pytest.raises(IBTReadError):
        list(reader.read(str(bad_file)))


def test_read_sdk_exception_wrapped_as_ibt_read_error(tmp_path):
    fake_path = str(tmp_path / "fake.ibt")
    Path(fake_path).touch()

    broken_sdk = MagicMock()
    broken_sdk.startup = MagicMock(side_effect=OSError("mmap failed"))

    reader = IBTReader(sdk_factory=lambda: broken_sdk)
    with pytest.raises(IBTReadError):
        list(reader.read(fake_path))
