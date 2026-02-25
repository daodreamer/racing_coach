"""Wave 3 — GET /api/laps (3 tests, mock storage)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.web.conftest import make_analysis_row


def _patch_storage(rows):
    mock_store = MagicMock()
    mock_store.list_analyses.return_value = rows
    return patch("racing_coach.web.app.TelemetryStorage", return_value=mock_store)


def test_laps_returns_200(client):
    with _patch_storage([]):
        resp = client.get("/api/laps", params={"track": "monza", "car": "ferrari"})
    assert resp.status_code == 200


def test_laps_empty(client):
    with _patch_storage([]):
        resp = client.get("/api/laps", params={"track": "monza", "car": "ferrari"})
    data = resp.json()
    assert data["laps"] == []
    assert data["track"] == "monza"
    assert data["car"] == "ferrari"


def test_laps_with_rows(client):
    rows = [
        make_analysis_row(analysis_id=1, lap_number=3, total_delta_s=0.5),
        make_analysis_row(analysis_id=2, lap_number=4, total_delta_s=0.3),
    ]
    with _patch_storage(rows):
        resp = client.get("/api/laps", params={"track": "monza", "car": "ferrari"})
    data = resp.json()
    assert len(data["laps"]) == 2
    assert data["laps"][0]["id"] == 1
    assert data["laps"][1]["lap_number"] == 4
