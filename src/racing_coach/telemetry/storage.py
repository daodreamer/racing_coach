"""TelemetryStorage — persists telemetry frames to SQLite.

Schema design notes:
  - No AUTOINCREMENT: ``INTEGER PRIMARY KEY`` is a rowid alias, stored in the
    B-tree key — zero record payload overhead.
  - ``sessions`` lookup table: avoids repeating the session_id string on every
    row (typical UUID/timestamp strings are 10-40 bytes each).
  - ``throttle``, ``brake``, ``lap_dist_pct`` stored as scaled INTEGER x 10 000:
    values 0-10 000 fit in 2 bytes vs 8 bytes for REAL.  Precision is 0.0001
    which exceeds sensor resolution.
  - ``positions`` is a separate table for world coordinates (used for track
    geometry / corner detection only); kept separate so the main
    ``telemetry_frames`` table stays compact.
"""

from __future__ import annotations

import sqlite3

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.track.models import TrackPoint

_SCALE = 10_000  # scaling factor for bounded [0,1] floats

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA page_size    = 4096;

CREATE TABLE IF NOT EXISTS sessions (
    idx        INTEGER PRIMARY KEY,
    session_id TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS telemetry_frames (
    session_idx    INTEGER NOT NULL,
    lap_number     INTEGER NOT NULL,
    timestamp      REAL    NOT NULL,
    speed          REAL,
    throttle       INTEGER,
    brake          INTEGER,
    steering_angle REAL,
    gear           INTEGER,
    rpm            REAL,
    g_force_lon    REAL,
    g_force_lat    REAL,
    lap_dist_pct   INTEGER,
    lap_time       REAL
);

CREATE INDEX IF NOT EXISTS idx_session_lap
    ON telemetry_frames (session_idx, lap_number);

CREATE TABLE IF NOT EXISTS positions (
    session_idx  INTEGER NOT NULL,
    lap_number   INTEGER NOT NULL,
    lap_dist_pct REAL    NOT NULL,
    car_x        REAL    NOT NULL,
    car_y        REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_positions_session_lap
    ON positions (session_idx, lap_number);
"""

_INSERT_SESSION = "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)"
_SELECT_SESSION = "SELECT idx FROM sessions WHERE session_id = ?"

_INSERT_FRAME = """
INSERT INTO telemetry_frames (
    session_idx, lap_number, timestamp,
    speed, throttle, brake, steering_angle, gear, rpm,
    g_force_lon, g_force_lat, lap_dist_pct, lap_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_POSITION = """
INSERT INTO positions (session_idx, lap_number, lap_dist_pct, car_x, car_y)
VALUES (?, ?, ?, ?, ?)
"""

_SELECT_TRACK_POINTS = """
SELECT lap_dist_pct, car_x, car_y
FROM   positions
WHERE  session_idx = (SELECT idx FROM sessions WHERE session_id = ?)
  AND  lap_number  = ?
ORDER  BY lap_dist_pct
"""

_SELECT_LAP = """
SELECT s.session_id,
       f.lap_number,
       f.timestamp,
       f.speed,
       f.throttle,
       f.brake,
       f.steering_angle,
       f.gear,
       f.rpm,
       f.g_force_lon,
       f.g_force_lat,
       f.lap_dist_pct,
       f.lap_time
FROM   telemetry_frames f
JOIN   sessions s ON s.idx = f.session_idx
WHERE  s.session_id = ? AND f.lap_number = ?
ORDER  BY f.timestamp
"""


class TelemetryStorage:
    """Stores and retrieves telemetry frames from a SQLite database.

    Parameters
    ----------
    db_path:
        Path to the SQLite file.  Pass ``":memory:"`` for in-process testing.
    """

    def __init__(self, db_path: str = "telemetry.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(stmt)
        self._conn.commit()
        self._session_cache: dict[str, int] = {}
        self._batch: list[tuple] = []
        self._pos_batch: list[tuple] = []
        self._batch_size = 600  # flush every ~10 seconds at 60 Hz

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_frame(
        self,
        session_id: str,
        lap_number: int,
        timestamp: float,
        frame: TelemetryFrame,
    ) -> None:
        """Persist one telemetry frame.  Writes are batched for performance."""
        self._batch.append((
            self._session_idx(session_id),
            lap_number,
            timestamp,
            frame.speed,
            round(frame.throttle * _SCALE),
            round(frame.brake * _SCALE),
            frame.steering_angle,
            frame.gear,
            frame.rpm,
            frame.g_force_lon,
            frame.g_force_lat,
            round(frame.lap_dist_pct * _SCALE),
            frame.lap_time,
        ))
        if len(self._batch) >= self._batch_size:
            self._flush()

    def save_position(
        self,
        session_id: str,
        lap_number: int,
        lap_dist_pct: float,
        x: float,
        y: float,
    ) -> None:
        """Persist one world-coordinate sample.  Writes are batched with frames."""
        self._pos_batch.append((
            self._session_idx(session_id),
            lap_number,
            lap_dist_pct,
            x,
            y,
        ))
        if len(self._pos_batch) >= self._batch_size:
            self._flush()

    def get_lap_as_track_points(
        self, session_id: str, lap_number: int
    ) -> list[TrackPoint]:
        """Return all saved positions for *session_id* / *lap_number* as :class:`TrackPoint`.

        Points are ordered by ``lap_dist_pct``.
        """
        self._flush()
        cursor = self._conn.execute(_SELECT_TRACK_POINTS, (session_id, lap_number))
        return [
            TrackPoint(
                lap_dist_pct=float(row["lap_dist_pct"]),
                x=float(row["car_x"]),
                y=float(row["car_y"]),
            )
            for row in cursor.fetchall()
        ]

    def get_lap(self, session_id: str, lap_number: int) -> list[dict]:
        """Return all frames for *session_id* / *lap_number*, ordered by timestamp."""
        self._flush()
        cursor = self._conn.execute(_SELECT_LAP, (session_id, lap_number))
        result = []
        for row in cursor.fetchall():
            d = dict(row)
            # Restore scaled integers to floats
            d["throttle"] = d["throttle"] / _SCALE
            d["brake"] = d["brake"] / _SCALE
            d["lap_dist_pct"] = d["lap_dist_pct"] / _SCALE
            result.append(d)
        return result

    def close(self) -> None:
        """Flush buffered writes and close the database connection."""
        self._flush()
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _session_idx(self, session_id: str) -> int:
        """Return the integer PK for *session_id*, creating a row if needed."""
        if session_id not in self._session_cache:
            self._flush()  # commit any pending batch before touching sessions
            self._conn.execute(_INSERT_SESSION, (session_id,))
            self._conn.commit()
            row = self._conn.execute(_SELECT_SESSION, (session_id,)).fetchone()
            self._session_cache[session_id] = row[0]
        return self._session_cache[session_id]

    def _flush(self) -> None:
        if self._batch:
            self._conn.executemany(_INSERT_FRAME, self._batch)
            self._conn.commit()
            self._batch.clear()
        if self._pos_batch:
            self._conn.executemany(_INSERT_POSITION, self._pos_batch)
            self._conn.commit()
            self._pos_batch.clear()
