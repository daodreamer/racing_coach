"""LiveTelemetryConnection — connects to iRacing shared memory and tracks state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class LiveTelemetryConnection:
    """Manages the connection to the iRacing shared-memory SDK.

    Parameters
    ----------
    sdk:
        An iRacing SDK instance (``irsdk.IRSDK()``). Injected for testability;
        defaults to the real SDK when not provided.
    """

    def __init__(self, sdk: Any | None = None) -> None:
        if sdk is None:
            import irsdk  # lazy import — irsdk is only needed at runtime

            sdk = irsdk.IRSDK()
        self._sdk = sdk
        self._connected: bool = False
        self._callbacks: list[Callable[[bool], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """True when the SDK has successfully connected to iRacing."""
        return self._connected

    def connect(self) -> bool:
        """Attempt to connect to iRacing.

        Returns
        -------
        bool
            True if iRacing is running and the connection succeeded.
            False otherwise (never raises).
        """
        try:
            initialized = bool(self._sdk.startup())
        except Exception:
            initialized = False

        if initialized != self._connected:
            self._connected = initialized
            self._fire_callbacks(initialized)

        return self._connected

    def disconnect(self) -> None:
        """Disconnect from iRacing and notify callbacks."""
        self._sdk.shutdown()
        if self._connected:
            self._connected = False
            self._fire_callbacks(False)

    def register_callback(self, callback: Callable[[bool], None]) -> None:
        """Register *callback* to be called whenever connection state changes.

        The callback receives a single bool argument: True = connected,
        False = disconnected.
        """
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fire_callbacks(self, state: bool) -> None:
        for cb in self._callbacks:
            cb(state)
