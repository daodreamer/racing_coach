"""Wave 4 — GET /report/{id} HTML page (5 tests)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.web.conftest import make_analysis_row


def _patch_storage(row):
    mock_store = MagicMock()
    mock_store.get_analysis.return_value = row
    mock_store.get_lap_as_track_points.return_value = []
    return patch("racing_coach.web.app.TelemetryStorage", return_value=mock_store)


def test_report_404_when_not_found(client):
    mock_store = MagicMock()
    mock_store.get_analysis.return_value = None
    with patch("racing_coach.web.app.TelemetryStorage", return_value=mock_store):
        resp = client.get("/report/999")
    assert resp.status_code == 404


def test_report_200(client):
    row = make_analysis_row()
    with _patch_storage(row):
        resp = client.get("/report/1")
    assert resp.status_code == 200


def test_report_contains_track_name(client):
    row = make_analysis_row(track="monza")
    with _patch_storage(row):
        resp = client.get("/report/1")
    assert "monza" in resp.text


def test_report_contains_delta_chart(client):
    row = make_analysis_row()
    with _patch_storage(row):
        resp = client.get("/report/1")
    assert "deltaChart" in resp.text


def test_report_contains_summary(client):
    row = make_analysis_row()
    with _patch_storage(row):
        resp = client.get("/report/1")
    assert "Test summary" in resp.text
