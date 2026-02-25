"""Audio player — winsound wrapper with NullAudioPlayer for tests."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass


@dataclass
class AudioConfig:
    """Frequency and duration settings for audio cues."""

    brake_freq: int = 880   # Hz — approaching brake point
    lock_freq: int = 1200   # Hz — wheel lock alert
    duration_ms: int = 120  # ms


class NullAudioPlayer:
    """No-op player; records calls for test assertions."""

    def __init__(self) -> None:
        self.plays: list[tuple[int, int]] = []

    def play(self, freq: int, duration_ms: int) -> None:
        self.plays.append((freq, duration_ms))


class WinsoundPlayer:
    """Plays beeps via winsound.Beep in a daemon thread (non-blocking)."""

    def __init__(self, config: AudioConfig | None = None) -> None:
        self._cfg = config or AudioConfig()

    def play(self, freq: int, duration_ms: int) -> None:
        if sys.platform != "win32":
            return
        import winsound

        threading.Thread(
            target=winsound.Beep, args=(freq, duration_ms), daemon=True
        ).start()
