"""TelemetryEventStream — 60 Hz polling loop with drop-oldest overflow handling."""

from __future__ import annotations

import contextlib
import queue
import threading
import time
from dataclasses import dataclass

from racing_coach.telemetry.models import TelemetryFrame


@dataclass
class TelemetryEvent:
    """A parsed telemetry frame with a monotonic timestamp."""

    frame: TelemetryFrame
    timestamp: float  # time.monotonic() seconds


class TelemetryEventStream:
    """Polls a connection+parser pair at *target_hz* and enqueues :class:`TelemetryEvent`.

    When the internal queue is full the *oldest* event is discarded so that
    the consumer always sees the most recent telemetry.

    Parameters
    ----------
    connection:
        Object with ``read_frame() -> dict | None``.
    parser:
        Object with ``parse(raw: dict) -> TelemetryFrame``.
    target_hz:
        Polling frequency in Hz.
    queue_maxsize:
        Maximum number of events buffered before drop-oldest kicks in.
    """

    def __init__(
        self,
        connection,
        parser,
        target_hz: float = 60.0,
        queue_maxsize: int = 120,
    ) -> None:
        self._conn = connection
        self._parser = parser
        self._interval = 1.0 / target_hz
        self._queue: queue.Queue[TelemetryEvent] = queue.Queue(maxsize=queue_maxsize)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="TelemetryStream")
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop and join it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_event(self, timeout: float = 0.1) -> TelemetryEvent | None:
        """Return the next queued event, or None if none arrives within *timeout* s."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def queue_size(self) -> int:
        """Return the current number of buffered events."""
        return self._queue.qsize()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            raw = self._conn.read_frame()
            if raw:
                try:
                    frame = self._parser.parse(raw)
                except Exception:
                    pass
                else:
                    event = TelemetryEvent(frame=frame, timestamp=t0)
                    self._enqueue(event)
            elapsed = time.monotonic() - t0
            wait = self._interval - elapsed
            if wait > 0:
                self._stop_event.wait(wait)

    def _enqueue(self, event: TelemetryEvent) -> None:
        """Put *event* in the queue; drop oldest if full."""
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait(event)
