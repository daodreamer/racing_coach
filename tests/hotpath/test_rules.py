"""Wave 2 — BrakePointCue and LockAlertRule (6 tests)."""

from __future__ import annotations

from racing_coach.hotpath.rules import BrakePointCue, CooldownTracker, LockAlertRule
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


def test_cooldown_allows_fire_initially():
    tracker = CooldownTracker(cooldown_s=3.0)
    assert tracker.can_fire() is True


def test_cooldown_blocks_after_fire():
    tracker = CooldownTracker(cooldown_s=10.0)
    tracker.mark_fired()
    assert tracker.can_fire() is False


def test_brake_cue_fires_within_window():
    """Cue fires when car is inside the distance window before the brake point."""
    # brake_pct=0.20, window = 50/1000 = 0.05 → fires when pos in (0.15, 0.20)
    cue = BrakePointCue(
        brake_pcts={1: 0.20},
        track_length_m=1000.0,
        distance_m=50.0,
    )
    frame = _make_frame(lap_dist_pct=0.17, lap_number=1)
    result = cue.check(frame)
    assert result == [1]


def test_brake_cue_no_fire_outside_window():
    """Cue does not fire when the car is too far from the brake point."""
    cue = BrakePointCue(
        brake_pcts={1: 0.20},
        track_length_m=1000.0,
        distance_m=50.0,
    )
    frame = _make_frame(lap_dist_pct=0.10, lap_number=1)  # 100m away
    assert cue.check(frame) == []


def test_brake_cue_deduplicates_per_corner_per_lap():
    """The same (corner, lap) combination fires at most once."""
    cue = BrakePointCue(
        brake_pcts={1: 0.20},
        track_length_m=1000.0,
        distance_m=50.0,
    )
    frame = _make_frame(lap_dist_pct=0.18, lap_number=1)
    first = cue.check(frame)
    second = cue.check(frame)
    assert first == [1]
    assert second == []


def test_lock_alert_fires_on_sudden_decel():
    """LockAlertRule fires when decel exceeds threshold under heavy braking."""
    dt = 1.0 / 60.0
    rule = LockAlertRule(decel_threshold=12.0, brake_min=0.7, cooldown_s=0.0, sample_dt=dt)
    # Prime prev_speed
    rule.check(_make_frame(speed=30.0, brake=0.9))
    # Next frame: speed drops by more than decel_threshold * dt
    new_speed = 30.0 - (12.5 * dt)  # > 12 m/s² deceleration
    result = rule.check(_make_frame(speed=new_speed, brake=0.9))
    assert result is True


def test_lock_alert_no_fire_below_brake_threshold():
    """LockAlertRule does not fire when brake pressure is below minimum."""
    dt = 1.0 / 60.0
    rule = LockAlertRule(decel_threshold=12.0, brake_min=0.7, cooldown_s=0.0, sample_dt=dt)
    rule.check(_make_frame(speed=30.0, brake=0.3))
    new_speed = 30.0 - (15.0 * dt)
    result = rule.check(_make_frame(speed=new_speed, brake=0.3))
    assert result is False
