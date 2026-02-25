"""Tests for CornerCommentary (Sprint 7 — S7-US1)."""

from __future__ import annotations

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.track.models import Corner
from racing_coach.tts.commentary import CornerCommentary
from racing_coach.tts.engine import NullTTSEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _corner(
    cid: int = 1,
    entry: float = 0.10,
    apex_start: float = 0.13,
    apex_end: float = 0.17,
    exit_: float = 0.20,
) -> Corner:
    return Corner(
        id=cid,
        entry_pct=entry,
        apex_pct=(apex_start + apex_end) / 2,
        exit_pct=exit_,
        direction="R",
        apex_start=apex_start,
        apex_end=apex_end,
    )


def _frame(
    lap_dist_pct: float,
    lap_number: int = 1,
    speed: float = 30.0,
    throttle: float = 0.0,
    brake: float = 0.0,
) -> TelemetryFrame:
    return TelemetryFrame(
        speed=speed,
        throttle=throttle,
        brake=brake,
        steering_angle=0.0,
        gear=3,
        rpm=5000.0,
        g_force_lon=0.0,
        g_force_lat=0.0,
        lap_dist_pct=lap_dist_pct,
        lap_number=lap_number,
        lap_time=lap_dist_pct * 120.0,
    )


def _drive_through_corner(commentary: CornerCommentary, corner: Corner, lap: int = 1) -> None:
    """Simulate driving through a corner and past the exit."""
    for pct in [corner.entry_pct + 0.005, corner.apex_pct, corner.exit_pct - 0.005]:
        commentary.update(_frame(pct, lap_number=lap))
    # Exit the corner
    commentary.update(_frame(corner.exit_pct + 0.01, lap_number=lap))


# ---------------------------------------------------------------------------
# Basic trigger tests
# ---------------------------------------------------------------------------


def test_commentary_triggers_tts_on_corner_exit():
    engine = NullTTSEngine()
    corner = _corner()
    commentary = CornerCommentary(engine, [corner], silence_s=0.0)
    _drive_through_corner(commentary, corner)
    assert len(engine.speaks) == 1


def test_commentary_text_contains_corner_id():
    engine = NullTTSEngine()
    corner = _corner(cid=5)
    commentary = CornerCommentary(engine, [corner], silence_s=0.0)
    _drive_through_corner(commentary, corner)
    assert "5" in engine.speaks[0][0]


def test_no_tts_when_not_in_corner():
    engine = NullTTSEngine()
    corner = _corner()
    commentary = CornerCommentary(engine, [corner], silence_s=0.0)
    # Frames entirely outside the corner
    for pct in [0.01, 0.05, 0.50]:
        commentary.update(_frame(pct))
    assert len(engine.speaks) == 0


# ---------------------------------------------------------------------------
# Silence period
# ---------------------------------------------------------------------------


def test_silence_period_blocks_second_commentary():
    """Two consecutive corners within the silence window → only first fires."""
    tick = [0.0]

    def fake_time():
        return tick[0]

    engine = NullTTSEngine()
    c1 = _corner(cid=1, entry=0.10, apex_start=0.13, apex_end=0.17, exit_=0.20)
    c2 = _corner(cid=2, entry=0.30, apex_start=0.33, apex_end=0.37, exit_=0.40)
    commentary = CornerCommentary(engine, [c1, c2], silence_s=3.0, _time_fn=fake_time)

    # Drive through corner 1 at t=0
    _drive_through_corner(commentary, c1)
    # Drive through corner 2 at t=1 (within silence window)
    tick[0] = 1.0
    _drive_through_corner(commentary, c2)

    assert len(engine.speaks) == 1  # only first corner


def test_commentary_allowed_after_silence_expires():
    """Commentary fires again after the silence period elapses."""
    tick = [0.0]

    def fake_time():
        return tick[0]

    engine = NullTTSEngine()
    c1 = _corner(cid=1, entry=0.10, apex_start=0.13, apex_end=0.17, exit_=0.20)
    c2 = _corner(cid=2, entry=0.30, apex_start=0.33, apex_end=0.37, exit_=0.40)
    commentary = CornerCommentary(engine, [c1, c2], silence_s=3.0, _time_fn=fake_time)

    _drive_through_corner(commentary, c1)
    tick[0] = 4.0  # past silence window
    _drive_through_corner(commentary, c2)

    assert len(engine.speaks) == 2


def test_no_duplicate_commentary_same_lap_corner():
    """Same corner on the same lap should only get one commentary."""
    engine = NullTTSEngine()
    corner = _corner()
    commentary = CornerCommentary(engine, [corner], silence_s=0.0)

    _drive_through_corner(commentary, corner, lap=1)
    _drive_through_corner(commentary, corner, lap=1)  # same lap, same corner

    assert len(engine.speaks) == 1


def test_commentary_fires_again_next_lap():
    """Same corner on a different lap should produce another commentary."""
    engine = NullTTSEngine()
    corner = _corner()
    commentary = CornerCommentary(engine, [corner], silence_s=0.0)

    _drive_through_corner(commentary, corner, lap=1)
    _drive_through_corner(commentary, corner, lap=2)

    assert len(engine.speaks) == 2


# ---------------------------------------------------------------------------
# Interrupt
# ---------------------------------------------------------------------------


def test_interrupt_calls_stop_then_speak():
    engine = NullTTSEngine()
    commentary = CornerCommentary(engine, [], silence_s=0.0)
    commentary.interrupt("Wheel lock!")
    assert engine.stops >= 1
    assert any("Wheel lock" in s[0] for s in engine.speaks)


def test_interrupt_uses_high_priority():
    engine = NullTTSEngine()
    commentary = CornerCommentary(engine, [], silence_s=0.0)
    commentary.interrupt("Brake!")
    assert engine.speaks[-1][1] == 1  # priority=1


# ---------------------------------------------------------------------------
# Commentary text content
# ---------------------------------------------------------------------------


def test_commentary_slow_apex_mentions_speed():
    engine = NullTTSEngine()
    corner = _corner()
    # Reference apex speed much faster than user
    commentary = CornerCommentary(
        engine, [corner], silence_s=0.0, ref_apex_speeds={1: 100.0}
    )
    # Drive with low speed (20 m/s = 72 km/h, ref = 100 km/h → -28 km/h)
    for pct in [corner.entry_pct + 0.005, corner.apex_pct]:
        commentary.update(_frame(pct, speed=20.0))
    commentary.update(_frame(corner.exit_pct + 0.01))
    text = engine.speaks[0][0]
    assert "below reference" in text.lower() or "k-p-h" in text.lower()


def test_commentary_late_throttle_suggests_earlier():
    engine = NullTTSEngine()
    # Wide corner gives enough room to place ref and user throttle points inside exit phase
    wide_corner = _corner(cid=1, entry=0.10, apex_start=0.15, apex_end=0.20, exit_=0.35)
    # Reference applies throttle at 0.21, user applies at 0.25 → diff 0.04 > threshold 0.02
    commentary = CornerCommentary(
        engine, [wide_corner], silence_s=0.0, ref_throttle_pcts={1: 0.21}
    )
    frames = [
        _frame(0.12),                       # entry
        _frame(0.17),                       # apex
        _frame(0.25, throttle=0.8),         # exit — throttle applied late
    ]
    for f in frames:
        commentary.update(f)
    commentary.update(_frame(0.36))         # past exit → triggers on_exit
    text = engine.speaks[0][0]
    assert "throttle" in text.lower()


def test_commentary_empty_corners_no_crash():
    engine = NullTTSEngine()
    commentary = CornerCommentary(engine, [], silence_s=0.0)
    commentary.update(_frame(0.5))
    assert len(engine.speaks) == 0
