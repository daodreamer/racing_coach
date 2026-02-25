"""Pydantic request/response schemas for the Web API — S5."""

from __future__ import annotations

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    db_path: str
    session_id: str
    lap: int
    ref_lap: int
    track: str = "unknown_track"
    car: str = "unknown_car"
    track_length_m: float = 4000.0


class HealthResponse(BaseModel):
    status: str
    version: str


class AnalyzeResponse(BaseModel):
    analysis_id: int
    total_delta_s: float
    corner_count: int
    summary: str


class LapRecord(BaseModel):
    id: int
    session_id: str
    lap_number: int
    ref_lap: int
    total_delta_s: float
    created_at: str


class LapsResponse(BaseModel):
    track: str
    car: str
    laps: list[LapRecord]
