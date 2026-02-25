"""Wave 1 — TelemetryStorage analyses table (6 tests)."""

from __future__ import annotations

import json

import pytest

from racing_coach.telemetry.storage import TelemetryStorage


@pytest.fixture
def store():
    s = TelemetryStorage(":memory:")
    yield s
    s.close()


def _report_json(delta: float = 0.5) -> str:
    return json.dumps({"total_delta_s": delta, "summary": "test", "corners": []})


class TestSaveAnalysis:
    def test_returns_integer_id(self, store):
        aid = store.save_analysis(
            session_id="s1",
            lap_number=3,
            ref_lap=1,
            track="monza",
            car="ferrari",
            track_length_m=5793.0,
            report_json=_report_json(),
        )
        assert isinstance(aid, int)
        assert aid > 0

    def test_roundtrip(self, store):
        aid = store.save_analysis(
            session_id="s1",
            lap_number=3,
            ref_lap=1,
            track="monza",
            car="ferrari",
            track_length_m=5793.0,
            report_json=_report_json(1.23),
        )
        row = store.get_analysis(aid)
        assert row is not None
        assert row["session_id"] == "s1"
        assert row["lap_number"] == 3
        assert row["ref_lap"] == 1
        assert row["track"] == "monza"
        assert row["car"] == "ferrari"
        assert row["track_length_m"] == pytest.approx(5793.0)
        assert json.loads(row["report_json"])["total_delta_s"] == pytest.approx(1.23)

    def test_get_missing_returns_none(self, store):
        assert store.get_analysis(9999) is None


class TestListAnalyses:
    def test_filters_by_track_and_car(self, store):
        store.save_analysis("s1", 1, 0, "monza", "ferrari", 5793.0, _report_json())
        store.save_analysis("s1", 1, 0, "spa", "porsche", 7004.0, _report_json())
        results = store.list_analyses("monza", "ferrari")
        assert len(results) == 1
        assert results[0]["track"] == "monza"

    def test_extracts_total_delta_s(self, store):
        store.save_analysis("s1", 1, 0, "monza", "ferrari", 5793.0, _report_json(2.5))
        results = store.list_analyses("monza", "ferrari")
        assert results[0]["total_delta_s"] == pytest.approx(2.5)

    def test_ordered_newest_first(self, store):
        store.save_analysis("s1", 1, 0, "monza", "ferrari", 5793.0, _report_json(1.0))
        store.save_analysis("s1", 2, 1, "monza", "ferrari", 5793.0, _report_json(0.5))
        results = store.list_analyses("monza", "ferrari")
        # Both exist; newest-first ordering guaranteed by created_at DESC.
        # Since both inserted within same second, at minimum both should be returned.
        assert len(results) == 2
        # The second insertion should come first (same-second ties: higher id = later)
        assert results[0]["lap_number"] == 2
