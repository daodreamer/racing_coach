"""Tests for LiveTelemetryConnection — S1-US1."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from racing_coach.telemetry.connection import LiveTelemetryConnection


def make_sdk(is_initialized: bool = True, is_connected: bool = True) -> MagicMock:
    """Create a mock iRacing SDK."""
    sdk = MagicMock()
    sdk.startup.return_value = is_initialized
    sdk.is_initialized = is_initialized
    sdk.is_connected = is_connected
    return sdk


# ---------------------------------------------------------------------------
# S1-US1 AC1: connect() returns True when iRacing is running
# ---------------------------------------------------------------------------

def test_connect_returns_true_when_iracing_running():
    sdk = make_sdk(is_initialized=True)
    conn = LiveTelemetryConnection(sdk=sdk)
    assert conn.connect() is True


def test_connect_calls_sdk_startup():
    sdk = make_sdk()
    conn = LiveTelemetryConnection(sdk=sdk)
    conn.connect()
    sdk.startup.assert_called_once()


# ---------------------------------------------------------------------------
# S1-US1 AC2: connect() returns False when iRacing not running, no exception
# ---------------------------------------------------------------------------

def test_connect_returns_false_when_iracing_not_running():
    sdk = make_sdk(is_initialized=False)
    conn = LiveTelemetryConnection(sdk=sdk)
    assert conn.connect() is False


def test_connect_does_not_raise_when_sdk_fails():
    sdk = MagicMock()
    sdk.startup.side_effect = OSError("shared memory not available")
    conn = LiveTelemetryConnection(sdk=sdk)
    result = conn.connect()  # must not raise
    assert result is False


# ---------------------------------------------------------------------------
# S1-US1 AC3: callbacks are triggered on connection state change
# ---------------------------------------------------------------------------

def test_register_and_fire_callback_on_connect():
    sdk = make_sdk(is_initialized=True)
    conn = LiveTelemetryConnection(sdk=sdk)
    cb = MagicMock()
    conn.register_callback(cb)
    conn.connect()
    cb.assert_called_once_with(True)


def test_register_and_fire_callback_on_disconnect():
    sdk = make_sdk(is_initialized=True)
    conn = LiveTelemetryConnection(sdk=sdk)
    cb = MagicMock()
    conn.register_callback(cb)
    conn.connect()
    conn.disconnect()
    assert cb.call_args_list == [call(True), call(False)]


def test_callback_not_fired_on_same_state():
    """Callback should not fire if state doesn't change."""
    sdk = make_sdk(is_initialized=True)
    conn = LiveTelemetryConnection(sdk=sdk)
    cb = MagicMock()
    conn.register_callback(cb)
    conn.connect()
    conn.connect()  # already connected — no second callback
    cb.assert_called_once_with(True)


def test_multiple_callbacks_all_fired():
    sdk = make_sdk(is_initialized=True)
    conn = LiveTelemetryConnection(sdk=sdk)
    cb1, cb2 = MagicMock(), MagicMock()
    conn.register_callback(cb1)
    conn.register_callback(cb2)
    conn.connect()
    cb1.assert_called_once_with(True)
    cb2.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# is_connected state tracking
# ---------------------------------------------------------------------------

def test_is_connected_false_before_connect():
    conn = LiveTelemetryConnection(sdk=make_sdk())
    assert conn.is_connected is False


def test_is_connected_true_after_successful_connect():
    conn = LiveTelemetryConnection(sdk=make_sdk(is_initialized=True))
    conn.connect()
    assert conn.is_connected is True


def test_is_connected_false_after_disconnect():
    conn = LiveTelemetryConnection(sdk=make_sdk(is_initialized=True))
    conn.connect()
    conn.disconnect()
    assert conn.is_connected is False


def test_disconnect_calls_sdk_shutdown():
    sdk = make_sdk(is_initialized=True)
    conn = LiveTelemetryConnection(sdk=sdk)
    conn.connect()
    conn.disconnect()
    sdk.shutdown.assert_called_once()
