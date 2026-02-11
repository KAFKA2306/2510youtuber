"""Job orchestration endpoints."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from app.gui.api import schemas
from app.gui.api.deps import get_job_manager, get_settings
from app.gui.core.settings import GuiSettingsEnvelope
from app.gui.jobs.manager import JobManager, JobResponse
router = APIRouter()
@router.get("/", response_model=schemas.JobListResponse)
async def list_jobs(manager: JobManager = Depends(get_job_manager)) -> schemas.JobListResponse:
    jobs = [JobResponse.from_job(job) for job in await manager.list()]
    return schemas.JobListResponse(jobs=jobs)
@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def enqueue_job(
    payload: schemas.JobCreateRequest,
    manager: JobManager = Depends(get_job_manager),
    envelope: GuiSettingsEnvelope = Depends(get_settings),
) -> JobResponse:
    try:
        job = await manager.enqueue(payload.command_id, payload.parameters, settings=envelope.settings)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    return JobResponse.from_job(job)
@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, manager: JobManager = Depends(get_job_manager)) -> JobResponse:
    try:
        job = await manager.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JobResponse.from_job(job)
@router.get("/{job_id}/logs", response_model=schemas.JobLogResponse)
async def get_job_logs(
    job_id: UUID,
    manager: JobManager = Depends(get_job_manager),
    tail: int | None = Query(default=None, ge=1, le=1000),
) -> schemas.JobLogResponse:
    try:
        entries_raw = await manager.stream_logs(job_id, tail=tail)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    entries = [schemas.JobLogEntry(**entry) for entry in entries_raw]
    return schemas.JobLogResponse(entries=entries)
@router.websocket("/{job_id}/stream")
async def stream_job_logs(
    websocket: WebSocket,
    job_id: UUID,
    manager: JobManager = Depends(get_job_manager),
) -> None:
    await websocket.accept()
    try:
        await manager.get(job_id)
    except KeyError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Job not found")
        return
    try:
        async for event in manager.follow_logs(job_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
    await websocket.close()
