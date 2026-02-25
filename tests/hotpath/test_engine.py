"""Wave 3 — HotPathEngine (2 tests)."""

from __future__ import annotations

from unittest.mock import MagicMock

from racing_coach.hotpath.audio import AudioConfig, NullAudioPlayer
from racing_coach.hotpath.engine import HotPathEngine
from racing_coach.hotpath.event_stream import TelemetryEvent
from racing_coach.hotpath.rules import BrakePointCue, LockAlertRule
from racing_coach.telemetry.models import TelemetryFrame


def _make_frame(**kwargs) -> TelemetryFrame:
    defaults = dict(
        speed=30.0,
        throttle=0.0,
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


def test_engine_plays_brake_cue_audio():
    """Engine fires audio when a brake cue is triggered."""
    frame = _make_frame(lap_dist_pct=0.18, lap_number=1)
    event = TelemetryEvent(frame=frame, timestamp=0.0)

    stream = MagicMock()
    stream.get_event.return_value = event

    cue = BrakePointCue(brake_pcts={1: 0.20}, track_length_m=1000.0, distance_m=50.0)
    lock = LockAlertRule(decel_threshold=12.0, brake_min=0.7, cooldown_s=0.0)
    player = NullAudioPlayer()
    cfg = AudioConfig(brake_freq=880, lock_freq=1200, duration_ms=120)

    engine = HotPathEngine(stream, cue, lock, player, cfg)
    fired = engine.tick()

    assert fired == 1
    assert player.plays == [(880, 120)]


def test_engine_no_cue_when_no_event():
    """Engine.tick() returns 0 when the queue is empty."""
    stream = MagicMock()
    stream.get_event.return_value = None

    cue = BrakePointCue(brake_pcts={}, track_length_m=4000.0)
    lock = LockAlertRule()
    player = NullAudioPlayer()

    engine = HotPathEngine(stream, cue, lock, player)
    assert engine.tick() == 0
