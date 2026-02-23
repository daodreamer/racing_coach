"""IBTReader — reads iRacing .ibt telemetry files into TelemetryFrame sequences."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.telemetry.parser import TelemetryParser


class IBTReadError(Exception):
    """Raised when an .ibt file cannot be opened or parsed."""


def _default_sdk_factory() -> Any:
    """Return a fresh ``irsdk.IRSDK()`` instance."""
    import irsdk  # lazy import — only needed for actual file reads

    return irsdk.IRSDK()


class IBTReader:
    """Reads an iRacing ``.ibt`` telemetry file frame-by-frame.

    Parameters
    ----------
    sdk_factory:
        Callable that returns an iRacing SDK instance.  Injected for
        testability; defaults to the real ``irsdk.IRSDK()``.
    """

    def __init__(self, sdk_factory: Callable[[], Any] | None = None) -> None:
        self._sdk_factory = sdk_factory or _default_sdk_factory
        self._parser = TelemetryParser()

    def read(self, path: str) -> Iterator[TelemetryFrame]:
        """Yield one :class:`TelemetryFrame` per sampled frame in *path*.

        Parameters
        ----------
        path:
            Absolute or relative path to the ``.ibt`` file.

        Raises
        ------
        IBTReadError
            If the file does not exist, is empty, is not a valid .ibt file,
            or if the SDK raises an unexpected error.
        """
        if not os.path.exists(path):
            raise IBTReadError(f"File not found: {path!r}")

        sdk = self._sdk_factory()
        try:
            initialized = sdk.startup(test_file=path)
        except Exception as exc:
            raise IBTReadError(f"SDK error opening {path!r}: {exc}") from exc

        if not initialized:
            raise IBTReadError(f"Could not open .ibt file (invalid or empty): {path!r}")

        try:
            yield from self._iter_frames(sdk)
        finally:
            sdk.shutdown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_frames(self, sdk: Any) -> Iterator[TelemetryFrame]:
        """Iterate over SDK frames, yielding a TelemetryFrame for each."""
        _KEYS = (
            "Speed", "Throttle", "Brake", "SteeringWheelAngle",
            "Gear", "RPM", "LongAccel", "LatAccel",
            "LapDistPct", "Lap", "LapCurrentLapTime",
        )
        while True:
            raw = {k: sdk[k] for k in _KEYS}
            yield self._parser.parse(raw)
            if not sdk.parse_to_next():
                break
