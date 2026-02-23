"""Smoke test to verify the toolchain works."""


def test_import_racing_coach():
    """Verify the racing_coach package can be imported."""
    import racing_coach

    assert racing_coach is not None


def test_subpackages_importable():
    """Verify all subpackages can be imported."""
    import racing_coach.analysis
    import racing_coach.reporting
    import racing_coach.telemetry
    import racing_coach.track

    assert racing_coach.telemetry is not None
    assert racing_coach.track is not None
    assert racing_coach.analysis is not None
    assert racing_coach.reporting is not None
