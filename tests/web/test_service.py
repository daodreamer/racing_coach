"""Wave 2 — AnalysisService (4 tests)."""

from __future__ import annotations

import math
import time

import pytest

from racing_coach.telemetry.models import TelemetryFrame
from racing_coach.telemetry.storage import TelemetryStorage
from racing_coach.track.models import TrackPoint
from racing_coach.web.schemas import AnalyzeRequest
from racing_coach.web.service import AnalysisService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SESSION = "test_session"
LAP = 2
REF = 1
N_FRAMES = 120  # enough frames for the analysis pipeline


class _PassthroughLLM:
    """Mock LLM that returns the report unchanged (no API call)."""

    def analyze(self, report):
        return report


def _make_frame(lap_dist_pct: float, lap_time: float) -> TelemetryFrame:
    return TelemetryFrame(
        speed=50.0,
        throttle=0.8,
        brake=0.0,
        steering_angle=0.0,
        gear=4,
        rpm=6500.0,
        g_force_lon=0.5,
        g_force_lat=0.0,
        lap_dist_pct=lap_dist_pct,
        lap_number=1,  # ignored by storage; lap_number arg to save_frame is used
        lap_time=lap_time,
    )


def _populate_frames(storage: TelemetryStorage, lap: int, lap_time_total: float) -> None:
    """Write N_FRAMES evenly distributed across [0, 1] for *lap*."""
    ts = time.time()
    for i in range(N_FRAMES):
        pct = i / N_FRAMES
        t = pct * lap_time_total
        storage.save_frame(SESSION, lap, ts + i * 0.1, _make_frame(pct, t))


def _integrate_curvature(kappas: list[float]) -> list[TrackPoint]:
    n = len(kappas)
    ds = 1.0 / n
    theta = 0.0
    x, y = 0.0, 0.0
    points = []
    for i in range(n):
        points.append(TrackPoint(lap_dist_pct=i / n, x=x, y=y))
        theta += kappas[i] * ds
        x += math.cos(theta) * ds
        y += math.sin(theta) * ds
    return points


def _make_3corner_track() -> list[TrackPoint]:
    n = 600
    kappas = [
        0.10 if (0.10 <= i / n < 0.20 or 0.70 <= i / n < 0.80)
        else (-0.10 if 0.40 <= i / n < 0.50 else 0.0)
        for i in range(n)
    ]
    return _integrate_curvature(kappas)


def _make_straight(n: int = 200) -> list[TrackPoint]:
    return [TrackPoint(lap_dist_pct=i / n, x=float(i), y=0.0) for i in range(n)]


def _populate_positions(
    storage: TelemetryStorage, lap: int, points: list[TrackPoint]
) -> None:
    for pt in points:
        storage.save_position(SESSION, lap, pt.lap_dist_pct, pt.x, pt.y)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "svc_test.db")


@pytest.fixture
def populated_db(db_path):
    """DB with frames + 3-corner positions for both laps."""
    track = _make_3corner_track()
    s = TelemetryStorage(db_path)
    _populate_frames(s, REF, 90.0)
    _populate_frames(s, LAP, 91.5)
    _populate_positions(s, REF, track)
    _populate_positions(s, LAP, track)
    s.close()
    return db_path


@pytest.fixture
def straight_db(db_path):
    """DB with frames + straight positions (no corners)."""
    track = _make_straight()
    s = TelemetryStorage(db_path)
    _populate_frames(s, REF, 90.0)
    _populate_frames(s, LAP, 91.5)
    _populate_positions(s, REF, track)
    _populate_positions(s, LAP, track)
    s.close()
    return db_path


@pytest.fixture
def empty_db(db_path):
    """DB with no frames at all."""
    s = TelemetryStorage(db_path)
    s.close()
    return db_path


@pytest.fixture
def frames_only_db(db_path):
    """DB with frames but no position data."""
    s = TelemetryStorage(db_path)
    _populate_frames(s, REF, 90.0)
    _populate_frames(s, LAP, 91.5)
    s.close()
    return db_path


def _req(db: str) -> AnalyzeRequest:
    return AnalyzeRequest(
        db_path=db,
        session_id=SESSION,
        lap=LAP,
        ref_lap=REF,
        track="test_track",
        car="test_car",
        track_length_m=4000.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_telemetry_raises(empty_db):
    svc = AnalysisService(empty_db, llm_client=_PassthroughLLM())
    with pytest.raises(ValueError, match="No telemetry frames"):
        svc.run_analysis(_req(empty_db))


def test_no_positions_raises(frames_only_db):
    svc = AnalysisService(frames_only_db, llm_client=_PassthroughLLM())
    with pytest.raises(ValueError, match="No position data"):
        svc.run_analysis(_req(frames_only_db))


def test_no_corners_raises(straight_db):
    svc = AnalysisService(straight_db, llm_client=_PassthroughLLM())
    with pytest.raises(ValueError, match="No corners"):
        svc.run_analysis(_req(straight_db))


def test_normal_path_returns_id_and_report(populated_db):
    from racing_coach.reporting.models import LapReport

    svc = AnalysisService(populated_db, llm_client=_PassthroughLLM())
    analysis_id, report = svc.run_analysis(_req(populated_db))

    assert isinstance(analysis_id, int)
    assert analysis_id > 0
    assert isinstance(report, LapReport)
    assert report.track == "test_track"
    assert report.car == "test_car"
    assert len(report.corners) > 0
