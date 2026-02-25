"""Tests for TTS engine abstractions (Sprint 7)."""

from __future__ import annotations

from racing_coach.tts.engine import NullTTSEngine, Win32TTSEngine

# ---------------------------------------------------------------------------
# NullTTSEngine
# ---------------------------------------------------------------------------


def test_null_engine_records_speak():
    engine = NullTTSEngine()
    engine.speak("Hello driver")
    assert engine.speaks == [("Hello driver", 0)]


def test_null_engine_records_priority():
    engine = NullTTSEngine()
    engine.speak("Brake now", priority=1)
    assert engine.speaks == [("Brake now", 1)]


def test_null_engine_records_multiple_speaks():
    engine = NullTTSEngine()
    engine.speak("First")
    engine.speak("Second")
    assert len(engine.speaks) == 2
    assert engine.speaks[0][0] == "First"
    assert engine.speaks[1][0] == "Second"


def test_null_engine_records_stop():
    engine = NullTTSEngine()
    engine.stop()
    assert engine.stops == 1


def test_null_engine_stop_increments_counter():
    engine = NullTTSEngine()
    engine.stop()
    engine.stop()
    assert engine.stops == 2


def test_null_engine_not_speaking_by_default():
    engine = NullTTSEngine()
    assert engine.is_speaking() is False


def test_null_engine_shutdown_does_not_raise():
    engine = NullTTSEngine()
    engine.shutdown()  # must not raise


# ---------------------------------------------------------------------------
# Win32TTSEngine — structural tests (no actual audio playback)
# ---------------------------------------------------------------------------


def test_win32_engine_instantiates():
    engine = Win32TTSEngine()
    engine.shutdown()


def test_win32_engine_stop_before_speak_does_not_raise():
    engine = Win32TTSEngine()
    engine.stop()
    engine.shutdown()


def test_win32_engine_speaks_without_exception():
    engine = Win32TTSEngine()
    engine.speak("Test")
    engine.shutdown()


def test_win32_engine_high_priority_clears_queue():
    """High-priority speak should drain the queue before adding new text."""
    engine = Win32TTSEngine()
    # Fill queue before the thread processes anything
    for _ in range(5):
        engine._queue.put("queued")
    engine.speak("urgent", priority=1)
    # After high-priority speak, queue should have at most 1 item
    assert engine._queue.qsize() <= 1
    engine.shutdown()


def test_win32_engine_not_speaking_by_default():
    engine = Win32TTSEngine()
    # Thread is just starting up — not speaking yet
    assert engine.is_speaking() is False
    engine.shutdown()
