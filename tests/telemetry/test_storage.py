"""Tests for TelemetryStorage — S1-US3."""

from __future__ import annotations

import os
import time

import pytest

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.telemetry.storage import TelemetryStorage
from racing_coach.track.models import TrackPoint


def make_frame(**overrides) -> TelemetryFrame:
    defaults = dict(
        speed=50.0,
        throttle=0.8,
        brake=0.0,
        steering_angle=0.1,
        gear=4,
        rpm=6500.0,
        g_force_lon=0.5,
        g_force_lat=-1.0,
        lap_dist_pct=0.45,
        lap_number=3,
        lap_time=42.5,
    )
    defaults.update(overrides)
    return TelemetryFrame(**defaults)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_telemetry.db")


@pytest.fixture
def storage(db_path):
    s = TelemetryStorage(db_path)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# S1-US3 AC1: write a lap, query returns same number of rows
# ---------------------------------------------------------------------------

def test_save_and_query_lap_row_count(storage):
    frames = [make_frame(lap_dist_pct=i / 100) for i in range(60)]
    ts_base = time.time()
    for i, frame in enumerate(frames):
        storage.save_frame("session_1", 1, ts_base + i / 60.0, frame)

    result = storage.get_lap("session_1", 1)
    assert len(result) == 60


# ---------------------------------------------------------------------------
# S1-US3 AC2: get_lap isolates by session_id + lap_number
# ---------------------------------------------------------------------------

def test_get_lap_isolates_sessions(storage):
    for lap in (1, 2):
        for i in range(10):
            storage.save_frame("session_A", lap, float(i), make_frame(lap_number=lap))
    storage.save_frame("session_B", 1, 0.0, make_frame())

    assert len(storage.get_lap("session_A", 1)) == 10
    assert len(storage.get_lap("session_A", 2)) == 10
    assert len(storage.get_lap("session_B", 1)) == 1


def test_get_lap_returns_correct_values(storage):
    frame = make_frame(speed=99.9, throttle=0.5, lap_number=7)
    storage.save_frame("sess", 7, 1.0, frame)
    rows = storage.get_lap("sess", 7)
    assert len(rows) == 1
    assert rows[0]["speed"] == pytest.approx(99.9)
    assert rows[0]["throttle"] == pytest.approx(0.5)
    assert rows[0]["lap_number"] == 7
    assert rows[0]["session_id"] == "sess"


def test_get_lap_returns_empty_for_missing(storage):
    assert storage.get_lap("no_such_session", 99) == []


# ---------------------------------------------------------------------------
# S1-US3 AC3: file size < 50MB for 100 laps x 60s x 60Hz
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Positions table: save_position / get_lap_as_track_points
# ---------------------------------------------------------------------------


def test_save_position_and_get_lap_as_track_points(storage):
    """Round-trip: save positions, retrieve as TrackPoints."""
    for i in range(10):
        pct = i / 10.0
        storage.save_position("sess", 1, pct, x=float(i * 10), y=float(i * 5))

    points = storage.get_lap_as_track_points("sess", 1)
    assert len(points) == 10
    assert all(isinstance(p, TrackPoint) for p in points)


def test_get_lap_as_track_points_values(storage):
    storage.save_position("sess", 1, 0.5, x=123.4, y=-56.7)
    points = storage.get_lap_as_track_points("sess", 1)
    assert points[0].lap_dist_pct == pytest.approx(0.5)
    assert points[0].x == pytest.approx(123.4)
    assert points[0].y == pytest.approx(-56.7)


def test_get_lap_as_track_points_empty_for_missing(storage):
    assert storage.get_lap_as_track_points("no_such", 99) == []


def test_positions_ordered_by_lap_dist_pct(storage):
    """Points should come back sorted by lap_dist_pct."""
    for pct in [0.9, 0.1, 0.5, 0.3]:
        storage.save_position("sess", 1, pct, x=pct * 100, y=0.0)
    points = storage.get_lap_as_track_points("sess", 1)
    pcts = [p.lap_dist_pct for p in points]
    assert pcts == sorted(pcts)


def test_positions_isolated_by_session_and_lap(storage):
    storage.save_position("sessA", 1, 0.1, 10.0, 0.0)
    storage.save_position("sessA", 2, 0.1, 20.0, 0.0)
    storage.save_position("sessB", 1, 0.1, 30.0, 0.0)

    assert len(storage.get_lap_as_track_points("sessA", 1)) == 1
    assert len(storage.get_lap_as_track_points("sessA", 2)) == 1
    assert storage.get_lap_as_track_points("sessA", 1)[0].x == pytest.approx(10.0)


def test_file_size_under_50mb_for_100_laps(tmp_path):
    db_file = str(tmp_path / "big_test.db")
    storage = TelemetryStorage(db_file)

    # 100 laps x 90 seconds x 60 Hz = 540 000 frames
    total = 0
    ts = 0.0
    for lap in range(100):
        for _ in range(90 * 60):  # 90s lap at 60Hz
            storage.save_frame("session_x", lap, ts, make_frame(lap_number=lap))
            ts += 1 / 60.0
            total += 1

    storage.close()

    size_mb = os.path.getsize(db_file) / (1024 * 1024)
    assert size_mb < 50, f"DB size {size_mb:.1f}MB exceeds 50MB limit (wrote {total} frames)"
