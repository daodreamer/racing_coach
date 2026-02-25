"""Wave 3 — POST /api/analyze (4 tests, mock service)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from racing_coach.reporting.models import CornerReport, LapReport

_VALID_PAYLOAD = {
    "db_path": "/tmp/test.db",
    "session_id": "s1",
    "lap": 3,
    "ref_lap": 1,
    "track": "monza",
    "car": "ferrari",
    "track_length_m": 5793.0,
}


def _mock_report() -> LapReport:
    return LapReport(
        session_id="s1",
        lap_number=3,
        track="monza",
        car="ferrari",
        total_delta_s=0.45,
        corners=[
            CornerReport(
                corner_id=1,
                delta_entry=0.1,
                delta_apex=0.15,
                delta_exit=0.2,
                delta_total=0.2,
            )
        ],
        summary="Good lap",
    )


def _patch_service(return_value):
    """Context manager that patches AnalysisService.run_analysis."""
    mock_svc = MagicMock()
    mock_svc.run_analysis.return_value = return_value
    return patch("racing_coach.web.app.AnalysisService", return_value=mock_svc)


def test_analyze_success(client):
    with _patch_service((42, _mock_report())):
        resp = client.post("/api/analyze", json=_VALID_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] == 42
    assert data["corner_count"] == 1
    assert data["total_delta_s"] == pytest.approx(0.45)
    assert data["summary"] == "Good lap"


def test_analyze_value_error_returns_422(client):
    mock_svc = MagicMock()
    mock_svc.run_analysis.side_effect = ValueError("No telemetry frames found")
    with patch("racing_coach.web.app.AnalysisService", return_value=mock_svc):
        resp = client.post("/api/analyze", json=_VALID_PAYLOAD)
    assert resp.status_code == 422


def test_analyze_unexpected_error_returns_500(client):
    mock_svc = MagicMock()
    mock_svc.run_analysis.side_effect = RuntimeError("db locked")
    with patch("racing_coach.web.app.AnalysisService", return_value=mock_svc):
        resp = client.post("/api/analyze", json=_VALID_PAYLOAD)
    assert resp.status_code == 500


def test_analyze_missing_required_field_returns_422(client):
    payload = dict(_VALID_PAYLOAD)
    del payload["session_id"]
    resp = client.post("/api/analyze", json=payload)
    assert resp.status_code == 422
