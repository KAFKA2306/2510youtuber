"""Dashboard endpoints exposing artefacts and QA metrics."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from app.gui.api import schemas
from app.gui.api.deps import get_dashboard_service
from app.gui.dashboard.service import DashboardService
router = APIRouter()
@router.get("/artifacts", response_model=schemas.DashboardArtifactsResponse)
async def list_artifacts(
    limit: int = Query(default=10, ge=1, le=50),
    service: DashboardService = Depends(get_dashboard_service),
) -> schemas.DashboardArtifactsResponse:
    artefacts = service.get_artifacts(limit=limit)
    return schemas.DashboardArtifactsResponse(artifacts=artefacts)
@router.get("/metrics", response_model=schemas.DashboardMetricsResponse)
async def list_metrics(
    limit: int = Query(default=20, ge=1, le=200),
    service: DashboardService = Depends(get_dashboard_service),
) -> schemas.DashboardMetricsResponse:
    metrics = service.get_metrics(limit=limit)
    return schemas.DashboardMetricsResponse(summary=metrics.summary, runs=metrics.runs)
