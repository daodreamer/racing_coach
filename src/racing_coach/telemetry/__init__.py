"""Telemetry data acquisition from iRacing.

Public API
----------
TelemetryFrame      - single frame of telemetry data
TelemetryParser     - raw iRacing dict → TelemetryFrame
LiveTelemetryConnection - connects to iRacing shared memory
TelemetryStorage    - SQLite persistence
IBTReader           - reads .ibt files
IBTReadError        - raised on invalid .ibt files
"""

from racing_coach.telemetry.connection import LiveTelemetryConnection
from racing_coach.telemetry.ibt_reader import IBTReader, IBTReadError
from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.telemetry.parser import TelemetryParser
from racing_coach.telemetry.storage import TelemetryStorage

__all__ = [
    "IBTReadError",
    "IBTReader",
    "LiveTelemetryConnection",
    "TelemetryFrame",
    "TelemetryParser",
    "TelemetryStorage",
]
