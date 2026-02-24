"""ACCReader — reads ACC shared memory and manages connection state."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Shared memory layout constants (ACC SDK offsets, all bytes)
# ---------------------------------------------------------------------------

_PHYS_MAP_NAME = "Local\\acpmf_physics"
_PHYS_SIZE = 1560  # safe upper bound for SPageFilePhysics

_OFF_GAS = 4        # float
_OFF_BRAKE = 8      # float
_OFF_GEAR = 16      # int32
_OFF_RPMS = 20      # int32
_OFF_STEER = 24     # float
_OFF_SPEED = 28     # float (km/h)
_OFF_ACCG = 44      # float[3]: [lat, vert, lon]

_GRAP_MAP_NAME = "Local\\acpmf_graphics"
_GRAP_SIZE = 2276  # safe upper bound for SPageFileGraphics

_OFF_COMPLETED_LAPS = 132   # int32
_OFF_CURRENT_TIME_MS = 140  # int32 (ms)
_OFF_LAP_POS = 248          # float [0, 1]

_FILE_MAP_READ = 0x0004


# ---------------------------------------------------------------------------
# Low-level helpers — ctypes only, no mmap module
# ---------------------------------------------------------------------------


def _read_shared_memory(name: str, size: int) -> bytes | None:
    """Open a named shared memory mapping, copy *size* bytes, then close.

    Uses ``OpenFileMappingW`` + ``MapViewOfFile`` + ``ctypes.string_at``
    so it works with ACC's existing mappings without creating new ones.
    Returns ``None`` if the mapping does not exist (ACC not running).
    """
    if sys.platform != "win32":
        return None

    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    # Set correct types so 64-bit pointers are not truncated on 64-bit Windows.
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.c_size_t,
    ]
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.UnmapViewOfFile.restype = ctypes.wintypes.BOOL

    handle = k32.OpenFileMappingW(_FILE_MAP_READ, False, name)
    if not handle:
        return None

    ptr = k32.MapViewOfFile(handle, _FILE_MAP_READ, 0, 0, size)
    k32.CloseHandle(handle)

    if not ptr:
        return None

    data: bytes = ctypes.string_at(ptr, size)
    k32.UnmapViewOfFile(ptr)
    return data


def _mapping_exists(name: str) -> bool:
    """Return True if the named mapping exists (ACC is running)."""
    if sys.platform != "win32":
        return False
    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = k32.OpenFileMappingW(_FILE_MAP_READ, False, name)
    if handle:
        k32.CloseHandle(handle)
        return True
    return False


def _read_float(buf: bytes, offset: int) -> float:
    return ctypes.c_float.from_buffer_copy(buf[offset : offset + 4]).value


def _read_int(buf: bytes, offset: int) -> int:
    return ctypes.c_int32.from_buffer_copy(buf[offset : offset + 4]).value


# ---------------------------------------------------------------------------
# Public classes
# ---------------------------------------------------------------------------


class ACCSharedMemory:
    """Reads ACC telemetry from Windows named shared memory.

    Uses standard-library ``ctypes`` only — no third-party dependencies,
    no persistent handles held between reads.
    An instance can be replaced with a mock for unit testing.
    """

    def is_available(self) -> bool:
        """True if ACC shared memory exists (ACC process is running)."""
        return _mapping_exists(_PHYS_MAP_NAME)

    def read_physics(self) -> dict:
        """Read physics fields and return as a plain dict."""
        buf = _read_shared_memory(_PHYS_MAP_NAME, _PHYS_SIZE)
        if buf is None:
            return {}
        return {
            "gas": _read_float(buf, _OFF_GAS),
            "brake": _read_float(buf, _OFF_BRAKE),
            "gear": _read_int(buf, _OFF_GEAR),
            "rpms": _read_int(buf, _OFF_RPMS),
            "steerAngle": _read_float(buf, _OFF_STEER),
            "speedKmh": _read_float(buf, _OFF_SPEED),
            "accG": [
                _read_float(buf, _OFF_ACCG),
                _read_float(buf, _OFF_ACCG + 4),
                _read_float(buf, _OFF_ACCG + 8),
            ],
        }

    def read_graphics(self) -> dict:
        """Read graphics/session fields and return as a plain dict."""
        buf = _read_shared_memory(_GRAP_MAP_NAME, _GRAP_SIZE)
        if buf is None:
            return {}
        return {
            "completedLaps": _read_int(buf, _OFF_COMPLETED_LAPS),
            "iCurrentTime": _read_int(buf, _OFF_CURRENT_TIME_MS),
            "normalizedCarPosition": _read_float(buf, _OFF_LAP_POS),
        }

    def close(self) -> None:
        """No-op: no persistent handles are held between reads."""


class ACCLiveConnection:
    """Manages the connection to ACC shared memory and tracks connection state.

    Parameters
    ----------
    reader:
        An :class:`ACCSharedMemory` instance. Injected for testability;
        defaults to the real implementation when not provided.
    """

    def __init__(self, reader: ACCSharedMemory | None = None) -> None:
        if reader is None:
            reader = ACCSharedMemory()
        self._reader = reader
        self._connected: bool = False
        self._callbacks: list[Callable[[bool], None]] = []

    @property
    def is_connected(self) -> bool:
        """True when ACC shared memory is accessible."""
        return self._connected

    def connect(self) -> bool:
        """Attempt to connect to ACC shared memory.

        Returns True if ACC is running, False otherwise (never raises).
        """
        try:
            available = bool(self._reader.is_available())
        except Exception:
            available = False

        if available != self._connected:
            self._connected = available
            self._fire_callbacks(available)

        return self._connected

    def disconnect(self) -> None:
        """Disconnect and notify callbacks."""
        self._reader.close()
        if self._connected:
            self._connected = False
            self._fire_callbacks(False)

    def register_callback(self, callback: Callable[[bool], None]) -> None:
        """Register *callback(connected: bool)* for connection state changes."""
        self._callbacks.append(callback)

    def read_frame(self) -> dict | None:
        """Return merged physics + graphics dict, or None if not connected."""
        if not self._connected:
            return None
        return {**self._reader.read_physics(), **self._reader.read_graphics()}

    def _fire_callbacks(self, state: bool) -> None:
        for cb in self._callbacks:
            cb(state)
