"""Reference lap management — S3-US1.

Stores completed laps with metadata (track, car, lap_time) in a SQLite table
and supports marking one lap per track+car combination as the *reference lap*.
"""

from __future__ import annotations

import contextlib
import sqlite3

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;

CREATE TABLE IF NOT EXISTS laps (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    lap_number  INTEGER NOT NULL,
    track       TEXT    NOT NULL,
    car         TEXT    NOT NULL,
    lap_time_s  REAL    NOT NULL,
    is_reference INTEGER NOT NULL DEFAULT 0,
    UNIQUE (session_id, lap_number)
);

CREATE INDEX IF NOT EXISTS idx_laps_track_car ON laps (track, car);
"""

_INSERT_LAP = """
INSERT OR IGNORE INTO laps (session_id, lap_number, track, car, lap_time_s)
VALUES (?, ?, ?, ?, ?)
"""

_CLEAR_REFERENCE = """
UPDATE laps SET is_reference = 0
WHERE track = (SELECT track FROM laps WHERE session_id = ? AND lap_number = ?)
  AND car   = (SELECT car   FROM laps WHERE session_id = ? AND lap_number = ?)
"""

_SET_REFERENCE = """
UPDATE laps SET is_reference = 1
WHERE session_id = ? AND lap_number = ?
"""

_SELECT_REFERENCE = """
SELECT session_id, lap_number, track, car, lap_time_s, is_reference
FROM   laps
WHERE  track = ? AND car = ? AND is_reference = 1
LIMIT  1
"""

_SELECT_ALL = """
SELECT session_id, lap_number, track, car, lap_time_s, is_reference
FROM   laps
WHERE  track = ? AND car = ?
ORDER  BY lap_time_s
"""

_SELECT_FASTEST = """
SELECT session_id, lap_number
FROM   laps
WHERE  track = ? AND car = ?
ORDER  BY lap_time_s ASC
LIMIT  1
"""

_EXISTS = "SELECT 1 FROM laps WHERE session_id = ? AND lap_number = ?"


class ReferenceLapManager:
    """Manage reference lap selection for track + car combinations.

    Args:
        db_path: Path to the SQLite file. Use ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str = "reference.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(stmt)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_lap(
        self,
        session_id: str,
        lap_number: int,
        track: str,
        car: str,
        lap_time_s: float,
    ) -> None:
        """Register a completed lap in the database.

        Silently ignored if (session_id, lap_number) already exists.
        """
        self._conn.execute(_INSERT_LAP, (session_id, lap_number, track, car, lap_time_s))
        self._conn.commit()

    def set_reference(self, session_id: str, lap_number: int) -> None:
        """Mark *session_id / lap_number* as the reference lap for its track+car.

        Clears any existing reference for the same track+car combination first.

        Raises:
            ValueError: If the lap has not been recorded.
        """
        row = self._conn.execute(_EXISTS, (session_id, lap_number)).fetchone()
        if row is None:
            raise ValueError(
                f"Lap not found: session_id={session_id!r}, lap_number={lap_number}"
            )
        # Clear all references for this track+car
        self._conn.execute(_CLEAR_REFERENCE, (session_id, lap_number, session_id, lap_number))
        # Set the new reference
        self._conn.execute(_SET_REFERENCE, (session_id, lap_number))
        self._conn.commit()

    def get_reference(self, track: str, car: str) -> dict | None:
        """Return the active reference lap for *track* / *car*, or ``None``."""
        row = self._conn.execute(_SELECT_REFERENCE, (track, car)).fetchone()
        return dict(row) if row else None

    def auto_set_reference(self, track: str, car: str) -> None:
        """Auto-select the fastest recorded lap for *track* / *car* as reference."""
        row = self._conn.execute(_SELECT_FASTEST, (track, car)).fetchone()
        if row:
            self.set_reference(row["session_id"], row["lap_number"])

    def get_all_laps(self, track: str, car: str) -> list[dict]:
        """Return all recorded laps for *track* / *car* ordered by lap time."""
        rows = self._conn.execute(_SELECT_ALL, (track, car)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self._conn.close()
