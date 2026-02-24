"""Telemetry data acquisition from ACC (Assetto Corsa Competizione).

Public API
----------
TelemetryFrame      - single frame of telemetry data
ACCParser           - raw ACC shared memory dict → TelemetryFrame
ACCLiveConnection   - connects to ACC shared memory
TelemetryStorage    - SQLite persistence
"""

from racing_coach.telemetry.acc_parser import ACCParser
from racing_coach.telemetry.acc_reader import ACCLiveConnection
from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.telemetry.storage import TelemetryStorage

__all__ = [
    "ACCLiveConnection",
    "ACCParser",
    "TelemetryFrame",
    "TelemetryStorage",
]
