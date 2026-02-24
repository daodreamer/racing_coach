"""Tests for S3-US1: Reference lap management."""

from __future__ import annotations

import pytest

from racing_coach.analysis.reference import ReferenceLapManager


class TestReferenceLapManagement:
    # ------------------------------------------------------------------
    # record + set + get
    # ------------------------------------------------------------------

    def test_record_and_get_reference(self):
        """Mark a lap as reference and retrieve it."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.5)
        mgr.set_reference("sess1", 1)
        ref = mgr.get_reference("spa", "gt3")
        assert ref is not None
        assert ref["session_id"] == "sess1"
        assert ref["lap_number"] == 1

    def test_is_reference_flag_is_true(self):
        """is_reference field equals True after set_reference."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.5)
        mgr.set_reference("sess1", 1)
        ref = mgr.get_reference("spa", "gt3")
        assert ref["is_reference"]

    def test_no_reference_returns_none(self):
        """get_reference returns None when no lap has been marked."""
        mgr = ReferenceLapManager(":memory:")
        assert mgr.get_reference("spa", "gt3") is None

    def test_get_reference_unknown_track_returns_none(self):
        """get_reference returns None for an unknown track/car combination."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.5)
        mgr.set_reference("sess1", 1)
        assert mgr.get_reference("monza", "gt3") is None

    # ------------------------------------------------------------------
    # Only one active reference per track+car combo
    # ------------------------------------------------------------------

    def test_only_one_active_reference_per_track_car(self):
        """Setting a second reference for the same track/car replaces the first."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.5)
        mgr.record_lap("sess1", 2, "spa", "gt3", 119.0)
        mgr.set_reference("sess1", 1)
        mgr.set_reference("sess1", 2)
        ref = mgr.get_reference("spa", "gt3")
        assert ref["lap_number"] == 2

    def test_previous_reference_is_cleared(self):
        """After setting a new reference, the previous lap no longer has is_reference."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.5)
        mgr.record_lap("sess1", 2, "spa", "gt3", 119.0)
        mgr.set_reference("sess1", 1)
        mgr.set_reference("sess1", 2)
        # Exactly one reference must exist for this track+car
        all_laps = mgr.get_all_laps("spa", "gt3")
        ref_count = sum(1 for r in all_laps if r["is_reference"])
        assert ref_count == 1

    def test_references_isolated_by_track(self):
        """A reference set for track A does not affect track B."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.0)
        mgr.record_lap("sess1", 2, "monza", "gt3", 100.0)
        mgr.set_reference("sess1", 1)
        assert mgr.get_reference("monza", "gt3") is None
        assert mgr.get_reference("spa", "gt3") is not None

    def test_references_isolated_by_car(self):
        """A reference set for car A does not affect car B on the same track."""
        mgr = ReferenceLapManager(":memory:")
        mgr.record_lap("sess1", 1, "spa", "gt3", 120.0)
        mgr.record_lap("sess1", 2, "spa", "gte", 118.0)
        mgr.set_reference("sess1", 1)
        assert mgr.get_reference("spa", "gte") is None

    # ------------------------------------------------------------------
    # Auto-select fastest lap
    # ------------------------------------------------------------------

    def test_auto_set_reference_selects_fastest(self):
        """auto_set_reference picks the lap with the minimum lap_time_s."""
        mgr = ReferenceLapManager(":memory:")
        for i, t in enumerate([125.0, 118.0, 121.0, 119.5], start=1):
            mgr.record_lap("sess1", i, "spa", "gt3", t)
        mgr.auto_set_reference("spa", "gt3")
        ref = mgr.get_reference("spa", "gt3")
        assert ref is not None
        assert ref["lap_number"] == 2  # 118.0 is fastest

    def test_auto_set_reference_five_laps(self):
        """auto_set_reference works correctly with five laps of varying times."""
        mgr = ReferenceLapManager(":memory:")
        times = [130.0, 128.5, 127.1, 126.8, 129.0]
        for i, t in enumerate(times, start=1):
            mgr.record_lap("sess1", i, "nordschleife", "gt3", t)
        mgr.auto_set_reference("nordschleife", "gt3")
        ref = mgr.get_reference("nordschleife", "gt3")
        assert ref["lap_number"] == 4  # 126.8 is fastest

    def test_set_reference_unknown_lap_raises(self):
        """set_reference raises ValueError when the lap has not been recorded."""
        mgr = ReferenceLapManager(":memory:")
        with pytest.raises(ValueError):
            mgr.set_reference("unknown_session", 99)
