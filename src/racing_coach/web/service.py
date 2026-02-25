"""AnalysisService — wraps the 6-step analysis pipeline for the Web API — S5."""

from __future__ import annotations

import json

from racing_coach.analysis.apex_speed import ApexSpeedAnalyzer
from racing_coach.analysis.braking import BrakingAnalyzer
from racing_coach.analysis.delta import DeltaCalculator
from racing_coach.analysis.models import LapFrame
from racing_coach.analysis.throttle import ThrottleAnalyzer
from racing_coach.reporting.aggregator import LapReportAggregator
from racing_coach.reporting.llm_client import MoonshotClient
from racing_coach.reporting.models import LapReport
from racing_coach.telemetry.storage import TelemetryStorage
from racing_coach.track.centerline import CenterlineExtractor
from racing_coach.track.detector import CornerDetector
from racing_coach.web.schemas import AnalyzeRequest


class AnalysisService:
    """Wraps the 6-step analysis pipeline.

    Parameters
    ----------
    db_path:
        Path to the SQLite database.
    llm_client:
        Optional LLM client for testing injection.  If None a default
        :class:`MoonshotClient` is created on first use.
    """

    def __init__(
        self,
        db_path: str,
        llm_client: MoonshotClient | None = None,
    ) -> None:
        self._db_path = db_path
        self._llm = llm_client

    def run_analysis(self, req: AnalyzeRequest) -> tuple[int, LapReport]:
        """Execute the 6-step pipeline and persist the result.

        Returns
        -------
        tuple[int, LapReport]
            ``(analysis_id, report)``

        Raises
        ------
        ValueError
            If no telemetry frames, no position data, or no corners are found.
        """
        storage = TelemetryStorage(req.db_path)
        try:
            # ------------------------------------------------------------------
            # Step 1: Load telemetry frames
            # ------------------------------------------------------------------
            user_rows = storage.get_lap(req.session_id, req.lap)
            ref_rows = storage.get_lap(req.session_id, req.ref_lap)
            if not user_rows:
                raise ValueError(
                    f"No telemetry frames found for session={req.session_id!r}, lap={req.lap}"
                )
            if not ref_rows:
                raise ValueError(
                    f"No telemetry frames found for session={req.session_id!r}, lap={req.ref_lap}"
                )
            user_frames = [LapFrame.from_storage_dict(r) for r in user_rows]
            ref_frames = [LapFrame.from_storage_dict(r) for r in ref_rows]

            # ------------------------------------------------------------------
            # Step 2: Load world coordinates → centerline → corners
            # ------------------------------------------------------------------
            user_pts = storage.get_lap_as_track_points(req.session_id, req.lap)
            ref_pts = storage.get_lap_as_track_points(req.session_id, req.ref_lap)
            if not user_pts or not ref_pts:
                raise ValueError(
                    "No position data found. "
                    "Ensure the session was recorded with world coordinates."
                )

            centerline = CenterlineExtractor().extract([user_pts, ref_pts])
            corners = CornerDetector().detect(centerline)
            if not corners:
                raise ValueError(
                    "No corners detected. "
                    "Cannot perform per-corner analysis."
                )

            # ------------------------------------------------------------------
            # Step 3: Delta analysis
            # ------------------------------------------------------------------
            corner_deltas = DeltaCalculator().compute_corner_deltas(
                user_frames, ref_frames, corners
            )
            total_delta = sum(cd.delta_total for cd in corner_deltas)

            # ------------------------------------------------------------------
            # Step 4: Detailed diagnostics
            # ------------------------------------------------------------------
            braking_events = BrakingAnalyzer().analyze(
                user_frames, ref_frames, corners, req.track_length_m
            )
            throttle_events = ThrottleAnalyzer().analyze(user_frames, ref_frames, corners)
            apex_results = ApexSpeedAnalyzer().analyze(user_frames, ref_frames, corners)

            # ------------------------------------------------------------------
            # Step 5: Aggregate + LLM feedback
            # ------------------------------------------------------------------
            report = LapReportAggregator().aggregate(
                session_id=req.session_id,
                lap_number=req.lap,
                track=req.track,
                car=req.car,
                total_delta_s=total_delta,
                corner_deltas=corner_deltas,
                braking_events=braking_events,
                throttle_events=throttle_events,
                apex_results=apex_results,
            )
            llm = self._llm if self._llm is not None else MoonshotClient()
            report = llm.analyze(report)

            # ------------------------------------------------------------------
            # Step 6: Persist to analyses table
            # ------------------------------------------------------------------
            analysis_id = storage.save_analysis(
                session_id=req.session_id,
                lap_number=req.lap,
                ref_lap=req.ref_lap,
                track=req.track,
                car=req.car,
                track_length_m=req.track_length_m,
                report_json=json.dumps(report.to_dict()),
            )
        finally:
            storage.close()

        return analysis_id, report
