"""Wave 1 — TelemetryEventStream (4 tests)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from racing_coach.hotpath.event_stream import TelemetryEvent, TelemetryEventStream
from racing_coach.telemetry.models import TelemetryFrame


def _make_frame(**kwargs) -> TelemetryFrame:
    defaults = dict(
        speed=30.0,
        throttle=0.5,
        brake=0.0,
        steering_angle=0.0,
        gear=3,
        rpm=5000.0,
        g_force_lon=0.0,
        g_force_lat=0.0,
        lap_dist_pct=0.1,
        lap_number=1,
        lap_time=30.0,
    )
    defaults.update(kwargs)
    return TelemetryFrame(**defaults)


def test_event_stream_delivers_event():
    """Events posted by connection+parser reach get_event()."""
    frame = _make_frame()
    conn = MagicMock()
    conn.read_frame.return_value = {"speedKmh": 108.0}
    parser = MagicMock()
    parser.parse.return_value = frame

    stream = TelemetryEventStream(conn, parser, target_hz=200, queue_maxsize=10)
    stream.start()
    event = stream.get_event(timeout=1.0)
    stream.stop()

    assert isinstance(event, TelemetryEvent)
    assert event.frame is frame


def test_event_stream_no_event_when_connection_returns_none():
    """get_event returns None when the connection yields no data."""
    conn = MagicMock()
    conn.read_frame.return_value = None
    parser = MagicMock()

    stream = TelemetryEventStream(conn, parser, target_hz=10, queue_maxsize=10)
    stream.start()
    event = stream.get_event(timeout=0.2)
    stream.stop()

    assert event is None


def test_event_stream_start_stop_no_exception():
    """start()/stop() complete without raising."""
    conn = MagicMock()
    conn.read_frame.return_value = None
    parser = MagicMock()

    stream = TelemetryEventStream(conn, parser, target_hz=10)
    stream.start()
    stream.stop()  # should not raise


def test_event_stream_drop_oldest_when_full():
    """Queue size never exceeds maxsize even under rapid production."""
    frame = _make_frame()
    conn = MagicMock()
    conn.read_frame.return_value = {"x": 1}
    parser = MagicMock()
    parser.parse.return_value = frame

    stream = TelemetryEventStream(conn, parser, target_hz=1000, queue_maxsize=3)
    stream.start()
    time.sleep(0.05)  # let producer run briefly
    stream.stop()

    assert stream.queue_size() <= 3
