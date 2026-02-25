"""TTS engine abstractions — NullTTSEngine for tests, Win32TTSEngine for Windows runtime."""

from __future__ import annotations

import queue
import threading


class NullTTSEngine:
    """No-op TTS engine; records calls for test assertions."""

    def __init__(self) -> None:
        self.speaks: list[tuple[str, int]] = []
        self.stops: int = 0

    def speak(self, text: str, priority: int = 0) -> None:
        """Record a speak call."""
        self.speaks.append((text, priority))

    def stop(self) -> None:
        """Record a stop call."""
        self.stops += 1

    def is_speaking(self) -> bool:
        """Return False — null engine never actually speaks."""
        return False

    def shutdown(self) -> None:
        """No-op shutdown."""


class Win32TTSEngine:
    """Windows SAPI5 TTS engine via win32com — reliable, reusable per-session.

    Bypasses pyttsx3 entirely to avoid two known SAPI5 bugs:

    1. **One-shot silence** — pyttsx3 caches engine instances in
       ``_activeEngines``; the "new" engine returned by ``pyttsx3.init()`` on
       subsequent calls is the same stale COM object, which silently produces
       no audio after the first ``runAndWait()``.

    2. **Hang on interrupt** — calling ``pyttsx3_engine.stop()`` while
       ``runAndWait()`` is blocking can cause the COM message pump to never
       return, permanently killing the TTS thread.

    This engine creates a single ``SAPI.SpVoice`` COM object in a dedicated
    STA thread and reuses it for all utterances.  ``Speak()`` blocks until the
    speech is complete, so the thread naturally serialises utterances.

    Gracefully degrades to silence if ``win32com`` / ``pythoncom`` are not
    available.

    Parameters
    ----------
    volume:
        Volume 0–100 (default 100).
    """

    def __init__(self, volume: int = 100) -> None:
        self._volume = volume
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop_flag = threading.Event()
        self._speaking = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="Win32TTSThread")
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def speak(self, text: str, priority: int = 0) -> None:
        """Queue text for speech.  High-priority (> 0) drains the queue first."""
        if priority > 0:
            self.stop()
        self._queue.put(text)

    def stop(self) -> None:
        """Drain the speech queue (current utterance finishes naturally)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def is_speaking(self) -> bool:
        """Return True if the TTS thread is currently producing speech."""
        return self._speaking.is_set()

    def shutdown(self) -> None:
        """Stop the background thread cleanly."""
        self._stop_flag.set()
        self._queue.put(None)  # Unblock any pending queue.get()
        self._thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            return

        try:
            pythoncom.CoInitialize()  # STA apartment for SAPI COM object
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Volume = self._volume
        except Exception:
            return

        while not self._stop_flag.is_set():
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if text is None:
                break
            try:
                self._speaking.set()
                speaker.Speak(text)  # synchronous — blocks until complete
            except Exception:
                pass
            finally:
                self._speaking.clear()
