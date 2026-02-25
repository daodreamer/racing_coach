"""Wave 1 — audio players (2 tests)."""

from __future__ import annotations

from racing_coach.hotpath.audio import AudioConfig, NullAudioPlayer, WinsoundPlayer


def test_null_audio_player_records_plays():
    player = NullAudioPlayer()
    player.play(880, 120)
    player.play(1200, 80)
    assert player.plays == [(880, 120), (1200, 80)]


def test_winsound_player_no_exception_on_non_windows(monkeypatch):
    """WinsoundPlayer.play() is a no-op on non-Windows and must not raise."""
    import sys

    monkeypatch.setattr(sys, "platform", "linux")
    player = WinsoundPlayer(AudioConfig())
    player.play(880, 120)  # should not raise
