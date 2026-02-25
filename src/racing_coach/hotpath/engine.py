"""HotPathEngine — connects TelemetryEventStream to rules and audio output."""

from __future__ import annotations

from racing_coach.hotpath.audio import AudioConfig


class HotPathEngine:
    """Integrates the event stream, alert rules, and audio player.

    Parameters
    ----------
    stream:
        A :class:`~racing_coach.hotpath.event_stream.TelemetryEventStream`.
    brake_cue:
        A :class:`~racing_coach.hotpath.rules.BrakePointCue`.
    lock_rule:
        A :class:`~racing_coach.hotpath.rules.LockAlertRule`.
    audio_player:
        A player with ``play(freq, duration_ms)`` — either
        :class:`~racing_coach.hotpath.audio.WinsoundPlayer` or
        :class:`~racing_coach.hotpath.audio.NullAudioPlayer`.
    audio_config:
        Frequency/duration configuration for cues.
    """

    def __init__(
        self,
        stream,
        brake_cue,
        lock_rule,
        audio_player,
        audio_config: AudioConfig | None = None,
    ) -> None:
        self._stream = stream
        self._brake_cue = brake_cue
        self._lock_rule = lock_rule
        self._player = audio_player
        self._cfg = audio_config or AudioConfig()

    def start(self) -> None:
        """Start the underlying telemetry stream."""
        self._stream.start()

    def stop(self) -> None:
        """Stop the underlying telemetry stream."""
        self._stream.stop()

    def tick(self) -> int:
        """Process one event from the queue and fire any triggered cues.

        Returns the number of audio cues fired (0 if no event was available).
        """
        event = self._stream.get_event(timeout=0.0)
        if event is None:
            return 0

        fired = 0
        frame = event.frame

        for _ in self._brake_cue.check(frame):
            self._player.play(self._cfg.brake_freq, self._cfg.duration_ms)
            fired += 1

        if self._lock_rule.check(frame):
            self._player.play(self._cfg.lock_freq, self._cfg.duration_ms)
            fired += 1

        return fired
