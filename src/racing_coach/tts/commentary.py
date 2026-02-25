"""Corner commentary — generates TTS feedback after each corner exit."""

from __future__ import annotations

import time
from dataclasses import dataclass

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.track.models import Corner


@dataclass
class CornerResult:
    """Per-corner performance summary used for TTS commentary generation."""

    corner_id: int

    min_apex_speed_kmh: float
    """Minimum speed in the apex zone (km/h)."""

    throttle_start_pct: float | None
    """lap_dist_pct of first throttle application in the exit phase (None if never applied)."""

    brake_start_pct: float | None
    """lap_dist_pct of first braking application in the corner (None if never braked)."""

    ref_apex_speed_kmh: float | None = None
    """Reference lap apex speed (km/h), or None if unavailable."""

    ref_throttle_start_pct: float | None = None
    """Reference lap throttle application point, or None if unavailable."""

    ref_brake_start_pct: float | None = None
    """Reference lap braking start point, or None if unavailable."""


class CornerCommentary:
    """Orchestrates per-corner TTS feedback.

    Processes telemetry frames via :meth:`update`.  When the driver exits a
    corner the class analyzes the buffered frames, generates a short text
    comment, and speaks it through the TTS engine — subject to a mandatory
    silence period between consecutive commentaries.

    High-priority alerts (e.g., wheel lock) can interrupt any pending or
    current commentary via :meth:`interrupt`.

    Parameters
    ----------
    tts_engine:
        Object with ``speak(text, priority)``, ``stop()``, ``is_speaking()``.
    corners:
        List of :class:`~racing_coach.track.models.Corner` objects.
    silence_s:
        Minimum seconds between consecutive commentaries.
    ref_apex_speeds:
        corner_id → apex speed (km/h) from the reference lap.
    ref_brake_pcts:
        corner_id → lap_dist_pct of reference braking start.
    ref_throttle_pcts:
        corner_id → lap_dist_pct of reference throttle application.
    _time_fn:
        Callable returning monotonic time — injectable for testing.
    """

    def __init__(
        self,
        tts_engine,
        corners: list[Corner],
        silence_s: float = 3.0,
        ref_apex_speeds: dict[int, float] | None = None,
        ref_brake_pcts: dict[int, float] | None = None,
        ref_throttle_pcts: dict[int, float] | None = None,
        _time_fn=time.monotonic,
    ) -> None:
        self._tts = tts_engine
        self._corners = corners
        self._silence_s = silence_s
        self._ref_apex = ref_apex_speeds or {}
        self._ref_brake = ref_brake_pcts or {}
        self._ref_throttle = ref_throttle_pcts or {}
        self._time_fn = _time_fn

        self._last_spoken: float = float("-inf")
        self._current_corner: Corner | None = None
        self._corner_frames: list[TelemetryFrame] = []
        self._spoken: set[tuple[int, int]] = set()  # (lap_number, corner_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, frame: TelemetryFrame) -> None:
        """Process a telemetry frame; fires TTS commentary on corner exit."""
        corner = self._corner_at(frame.lap_dist_pct)

        if corner is not self._current_corner:
            if self._current_corner is not None:
                self._on_exit(self._current_corner, self._corner_frames, frame.lap_number)
            self._current_corner = corner
            self._corner_frames = []

        if corner is not None:
            self._corner_frames.append(frame)

    def interrupt(self, text: str) -> None:
        """Fire a high-priority alert that interrupts current commentary.

        Stops any ongoing speech, resets the silence timer, and immediately
        speaks *text* at elevated priority.
        """
        self._tts.stop()
        self._tts.speak(text, priority=1)
        self._last_spoken = self._time_fn()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _corner_at(self, lap_dist_pct: float) -> Corner | None:
        """Return the Corner the driver is currently in, or None."""
        for corner in self._corners:
            if corner.entry_pct <= lap_dist_pct <= corner.exit_pct:
                return corner
        return None

    def _on_exit(
        self,
        corner: Corner,
        frames: list[TelemetryFrame],
        lap_number: int,
    ) -> None:
        """Handle corner exit: analyze frames and fire TTS if allowed."""
        key = (lap_number, corner.id)
        if key in self._spoken:
            return

        now = self._time_fn()
        if now - self._last_spoken < self._silence_s:
            return

        result = self._analyze(corner, frames)
        text = self._generate_text(result)
        self._tts.speak(text)
        self._last_spoken = now
        self._spoken.add(key)

    def _analyze(self, corner: Corner, frames: list[TelemetryFrame]) -> CornerResult:
        """Extract key metrics from the corner's buffered frames."""
        if not frames:
            return CornerResult(
                corner_id=corner.id,
                min_apex_speed_kmh=0.0,
                throttle_start_pct=None,
                brake_start_pct=None,
                ref_apex_speed_kmh=self._ref_apex.get(corner.id),
                ref_brake_start_pct=self._ref_brake.get(corner.id),
                ref_throttle_start_pct=self._ref_throttle.get(corner.id),
            )

        # Minimum speed in the apex zone
        apex_frames = [
            f for f in frames if corner.apex_start <= f.lap_dist_pct <= corner.apex_end
        ]
        speed_source = apex_frames if apex_frames else frames
        min_speed_kmh = min(f.speed * 3.6 for f in speed_source)

        # First throttle application in the exit phase
        throttle_start: float | None = None
        for f in frames:
            if f.lap_dist_pct >= corner.apex_end and f.throttle > 0.05:
                throttle_start = f.lap_dist_pct
                break

        # First braking in the corner
        brake_start: float | None = None
        for f in frames:
            if f.brake > 0.05:
                brake_start = f.lap_dist_pct
                break

        return CornerResult(
            corner_id=corner.id,
            min_apex_speed_kmh=min_speed_kmh,
            throttle_start_pct=throttle_start,
            brake_start_pct=brake_start,
            ref_apex_speed_kmh=self._ref_apex.get(corner.id),
            ref_brake_start_pct=self._ref_brake.get(corner.id),
            ref_throttle_start_pct=self._ref_throttle.get(corner.id),
        )

    def _generate_text(self, result: CornerResult) -> str:
        """Generate a short commentary string from the corner analysis."""
        parts: list[str] = [f"Turn {result.corner_id}."]

        # Apex speed vs reference
        if result.ref_apex_speed_kmh is not None and result.min_apex_speed_kmh > 0:
            diff = result.min_apex_speed_kmh - result.ref_apex_speed_kmh
            if diff < -5.0:
                parts.append(f"Apex speed {abs(diff):.0f} k-p-h below reference.")
            elif diff > 5.0:
                parts.append("Apex speed faster than reference, good.")

        # Throttle timing vs reference
        if result.throttle_start_pct is not None and result.ref_throttle_start_pct is not None:
            diff = result.throttle_start_pct - result.ref_throttle_start_pct
            if diff > 0.02:
                parts.append("Apply throttle earlier on exit.")
            elif diff < -0.02:
                parts.append("Good throttle timing.")

        # Generic fallback
        if len(parts) == 1:
            parts.append("Keep it up.")

        return " ".join(parts)
