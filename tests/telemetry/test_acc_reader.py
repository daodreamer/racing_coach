"""Tests for ACCLiveConnection — ACC shared memory connection management."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from racing_coach.telemetry.acc_reader import ACCLiveConnection

_PHYSICS_SAMPLE = {
    "gas": 0.8,
    "brake": 0.0,
    "gear": 4,
    "rpms": 6500,
    "steerAngle": 0.1,
    "speedKmh": 180.0,
    "accG": [0.5, 0.0, 5.0],
}

_GRAPHICS_SAMPLE = {
    "completedLaps": 3,
    "iCurrentTime": 42500,
    "normalizedCarPosition": 0.45,
}


def make_reader(available: bool = True) -> MagicMock:
    """Create a mock ACCSharedMemory."""
    reader = MagicMock()
    reader.is_available.return_value = available
    reader.read_physics.return_value = _PHYSICS_SAMPLE.copy()
    reader.read_graphics.return_value = _GRAPHICS_SAMPLE.copy()
    return reader


# ---------------------------------------------------------------------------
# connect() / is_connected
# ---------------------------------------------------------------------------


def test_connect_returns_true_when_acc_running():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    assert conn.connect() is True


def test_connect_returns_false_when_acc_not_running():
    conn = ACCLiveConnection(reader=make_reader(available=False))
    assert conn.connect() is False


def test_connect_does_not_raise_when_reader_raises():
    reader = MagicMock()
    reader.is_available.side_effect = OSError("shared memory not available")
    conn = ACCLiveConnection(reader=reader)
    result = conn.connect()  # must not raise
    assert result is False


def test_is_connected_false_before_connect():
    conn = ACCLiveConnection(reader=make_reader())
    assert conn.is_connected is False


def test_is_connected_true_after_successful_connect():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    conn.connect()
    assert conn.is_connected is True


def test_is_connected_false_after_disconnect():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    conn.connect()
    conn.disconnect()
    assert conn.is_connected is False


# ---------------------------------------------------------------------------
# callbacks
# ---------------------------------------------------------------------------


def test_register_and_fire_callback_on_connect():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    cb = MagicMock()
    conn.register_callback(cb)
    conn.connect()
    cb.assert_called_once_with(True)


def test_register_and_fire_callback_on_disconnect():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    cb = MagicMock()
    conn.register_callback(cb)
    conn.connect()
    conn.disconnect()
    assert cb.call_args_list == [call(True), call(False)]


def test_callback_not_fired_on_same_state():
    """Callback must not fire when connection state does not change."""
    conn = ACCLiveConnection(reader=make_reader(available=True))
    cb = MagicMock()
    conn.register_callback(cb)
    conn.connect()
    conn.connect()  # already connected — no second callback
    cb.assert_called_once_with(True)


def test_multiple_callbacks_all_fired():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    cb1, cb2 = MagicMock(), MagicMock()
    conn.register_callback(cb1)
    conn.register_callback(cb2)
    conn.connect()
    cb1.assert_called_once_with(True)
    cb2.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# read_frame()
# ---------------------------------------------------------------------------


def test_read_frame_returns_none_when_not_connected():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    # connect() not called
    assert conn.read_frame() is None


def test_read_frame_merges_physics_and_graphics():
    reader = make_reader(available=True)
    conn = ACCLiveConnection(reader=reader)
    conn.connect()
    frame = conn.read_frame()
    assert frame is not None
    # Physics keys
    assert frame["speedKmh"] == _PHYSICS_SAMPLE["speedKmh"]
    assert frame["gas"] == _PHYSICS_SAMPLE["gas"]
    # Graphics keys
    assert frame["completedLaps"] == _GRAPHICS_SAMPLE["completedLaps"]
    assert frame["normalizedCarPosition"] == _GRAPHICS_SAMPLE["normalizedCarPosition"]


def test_read_frame_returns_dict_when_connected():
    conn = ACCLiveConnection(reader=make_reader(available=True))
    conn.connect()
    frame = conn.read_frame()
    assert isinstance(frame, dict)


def test_disconnect_calls_reader_close():
    reader = make_reader(available=True)
    conn = ACCLiveConnection(reader=reader)
    conn.connect()
    conn.disconnect()
    reader.close.assert_called_once()
