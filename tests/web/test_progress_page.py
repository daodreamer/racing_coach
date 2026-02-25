"""Wave 4 — GET /progress HTML page (3 tests)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.web.conftest import make_analysis_row


def _patch_storage(rows):
    mock_store = MagicMock()
    mock_store.list_analyses.return_value = rows
    return patch("racing_coach.web.app.TelemetryStorage", return_value=mock_store)


def test_progress_200(client):
    with _patch_storage([]):
        resp = client.get("/progress", params={"track": "monza", "car": "ferrari"})
    assert resp.status_code == 200


def test_progress_shows_track_name(client):
    with _patch_storage([]):
        resp = client.get("/progress", params={"track": "monza", "car": "ferrari"})
    assert "monza" in resp.text


def test_progress_shows_history_table_with_data(client):
    rows = [
        make_analysis_row(analysis_id=1, lap_number=3, total_delta_s=0.5),
        make_analysis_row(analysis_id=2, lap_number=4, total_delta_s=0.3),
    ]
    with _patch_storage(rows):
        resp = client.get("/progress", params={"track": "monza", "car": "ferrari"})
    # Table should appear and contain a report link
    assert "VIEW" in resp.text
    assert "trendChart" in resp.text
