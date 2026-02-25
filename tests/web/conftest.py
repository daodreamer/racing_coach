"""Shared fixtures for web tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from racing_coach.web.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c


def make_analysis_row(
    analysis_id: int = 1,
    session_id: str = "s1",
    lap_number: int = 3,
    ref_lap: int = 1,
    track: str = "monza",
    car: str = "ferrari",
    total_delta_s: float = 0.5,
    created_at: str = "2026-02-25T10:00:00Z",
) -> dict:
    """Build a fake analyses table row dict."""
    report = {
        "session_id": session_id,
        "lap_number": lap_number,
        "track": track,
        "car": car,
        "total_delta_s": total_delta_s,
        "summary": "Test summary",
        "top_improvements": [],
        "corners": [
            {
                "corner_id": 1,
                "delta_entry": 0.1,
                "delta_apex": 0.15,
                "delta_exit": 0.2,
                "delta_total": 0.2,
                "entry_pct": 0.1,
                "exit_pct": 0.2,
                "braking": None,
                "throttle": None,
                "apex_speed": None,
                "suggestions": [],
            }
        ],
    }
    return {
        "id": analysis_id,
        "session_id": session_id,
        "lap_number": lap_number,
        "ref_lap": ref_lap,
        "track": track,
        "car": car,
        "track_length_m": 5793.0,
        "created_at": created_at,
        "report_json": json.dumps(report),
        "total_delta_s": total_delta_s,
    }
