"""FastAPI Web application — S5."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from racing_coach.telemetry.storage import TelemetryStorage
from racing_coach.web.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    LapRecord,
    LapsResponse,
)
from racing_coach.web.service import AnalysisService

load_dotenv()  # loads .env from project root; must run before env vars are consumed

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent

app = FastAPI(title="AI Racing Coach", version="0.1.0")

app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
templates = Jinja2Templates(directory=str(_HERE / "templates"))

_DEFAULT_DB = os.environ.get("RACING_COACH_DB", "session.db")


def _storage(db_path: str | None = None) -> TelemetryStorage:
    return TelemetryStorage(db_path or _DEFAULT_DB)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    return RedirectResponse(url="/progress")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Run the 6-step analysis pipeline and persist the result."""
    svc = AnalysisService(req.db_path)
    try:
        analysis_id, report = svc.run_analysis(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AnalyzeResponse(
        analysis_id=analysis_id,
        total_delta_s=report.total_delta_s,
        corner_count=len(report.corners),
        summary=report.summary,
    )


@app.get("/api/laps", response_model=LapsResponse)
def list_laps(track: str = "", car: str = "", db: str | None = None) -> LapsResponse:
    """Return historical analyses filtered by track and car."""
    storage = _storage(db)
    try:
        rows = storage.list_analyses(track, car)
    finally:
        storage.close()

    laps = [
        LapRecord(
            id=r["id"],
            session_id=r["session_id"],
            lap_number=r["lap_number"],
            ref_lap=r["ref_lap"],
            total_delta_s=float(r["total_delta_s"] or 0.0),
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return LapsResponse(track=track, car=car, laps=laps)


@app.get("/report/{analysis_id}", response_class=HTMLResponse)
def report_page(request: Request, analysis_id: int, db: str | None = None) -> HTMLResponse:
    """Render the per-lap analysis report page."""
    storage = _storage(db)
    try:
        row = storage.get_analysis(analysis_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Analysis not found")

        report_data = json.loads(row["report_json"])

        # Build position data for the track map — merge user lap + ref lap so the
        # full circuit outline is visible even if one lap has sparse sections.
        user_pts = storage.get_lap_as_track_points(row["session_id"], row["lap_number"])
        ref_pts  = storage.get_lap_as_track_points(row["session_id"], row["ref_lap"])

        # Deduplicate by rounding pct to 4 dp; prefer user lap points.
        seen: dict[float, tuple[float, float]] = {}
        for p in ref_pts:
            seen[round(p.lap_dist_pct, 4)] = (p.x, p.y)
        for p in user_pts:
            seen[round(p.lap_dist_pct, 4)] = (p.x, p.y)

        positions_list = [
            {"pct": k, "x": v[0], "y": v[1]}
            for k, v in sorted(seen.items())
        ]

        # Corners from the report for chart/map colouring
        corners_list = [
            {
                "corner_id": c["corner_id"],
                "delta_total": c["delta_total"],
                "entry_pct": c.get("entry_pct", 0),
                "exit_pct": c.get("exit_pct", 1),
            }
            for c in report_data.get("corners", [])
        ]
    finally:
        storage.close()

    # Build a simple namespace for the template (avoid importing dataclasses)
    class _ReportProxy:
        def __init__(self, d: dict) -> None:
            self.__dict__.update(d)
            self.corners = [_CornerProxy(c) for c in d.get("corners", [])]
            self.top_improvements = [_SuggProxy(s) for s in d.get("top_improvements", [])]

    class _CornerProxy:
        def __init__(self, d: dict) -> None:
            self.__dict__.update(d)

    class _SuggProxy:
        def __init__(self, d: dict) -> None:
            self.__dict__.update(d)

    report_proxy = _ReportProxy(report_data)

    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "analysis_id": analysis_id,
            "report": report_proxy,
            "positions_json": json.dumps(positions_list),
            "corners_json": json.dumps(corners_list),
        },
    )


@app.get("/progress", response_class=HTMLResponse)
def progress_page(
    request: Request,
    track: str = "",
    car: str = "",
    date_from: str = "",
    date_to: str = "",
    db: str | None = None,
) -> HTMLResponse:
    """Render the progress trend page."""
    storage = _storage(db)
    try:
        rows = storage.list_analyses(track, car)
    finally:
        storage.close()

    # Apply date filters (Python-side, no JS)
    if date_from:
        rows = [r for r in rows if r["created_at"] >= date_from]
    if date_to:
        # Include the whole day: compare against date_to + 'T23:59:59Z'
        rows = [r for r in rows if r["created_at"] <= date_to + "T23:59:59Z"]

    class _LapProxy:
        def __init__(self, r: dict) -> None:
            self.id = r["id"]
            self.lap_number = r["lap_number"]
            self.total_delta_s = float(r["total_delta_s"] or 0.0)
            self.created_at = r["created_at"]

    laps = [_LapProxy(r) for r in rows]
    laps_json = json.dumps(
        [
            {
                "id": r["id"],
                "lap_number": r["lap_number"],
                "total_delta_s": float(r["total_delta_s"] or 0.0),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    )

    return templates.TemplateResponse(
        request,
        "progress.html",
        {
            "track": track,
            "car": car,
            "date_from": date_from,
            "date_to": date_to,
            "laps": laps,
            "laps_json": laps_json,
        },
    )
