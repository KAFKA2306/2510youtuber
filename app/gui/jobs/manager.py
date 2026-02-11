"""Asynchronous job management for the GUI backend."""
from __future__ import annotations
import asyncio
import json
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel
from app.gui.core.settings import GuiSettings
from app.gui.jobs.registry import Command, CommandRegistry
from app.gui.jobs.runners import execute_command
class JobLogWriter:
    """Persists job log events to disk and notifies subscribers."""
    def __init__(self, job: "Job", manager: "JobManager") -> None:
        if not job.log_path:
            raise ValueError("Job log path must be defined before writing logs")
        self._job = job
        self._manager = manager
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._path = job.log_path
        self._file = self._path.open("a", encoding="utf-8")
        self._closed = False
    async def __aenter__(self) -> "JobLogWriter":
        return self
    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
    async def write_event(self, payload: Mapping[str, Any]) -> None:
        event = {
            "job_id": str(self._job.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence": self._sequence,
            **payload,
        }
        event.setdefault("event", "line")
        self._sequence += 1
        line = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            if self._closed:
                return
            self._file.write(line + "\n")
            self._file.flush()
        await self._manager._append_log_event(self._job.id, event)
    async def close(self) -> None:
        async with self._lock:
            if not self._closed:
                self._file.close()
                self._closed = True
class JobStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
@dataclass
class Job:
    """Job metadata persisted in memory."""
    id: UUID
    command: Command
    parameters: Mapping[str, Any]
    status: str = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    log_path: Path | None = None
    def serialize(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "command_id": self.command.id,
            "command_name": self.command.name,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "exit_code": self.exit_code,
            "error": self.error,
            "log_path": str(self.log_path) if self.log_path else None,
        }
class JobResponse(BaseModel):
    """API response schema for jobs."""
    id: UUID
    command_id: str
    command_name: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    exit_code: Optional[int]
    error: Optional[str]
    @classmethod
    def from_job(cls, job: Job) -> "JobResponse":
        return cls(
            id=job.id,
            command_id=job.command.id,
            command_name=job.command.name,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            exit_code=job.exit_code,
            error=job.error,
        )
class JobManager:
    """Registers and executes jobs asynchronously."""
    def __init__(self, registry: CommandRegistry, log_dir: Path) -> None:
        self._registry = registry
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[UUID, Job] = {}
        self._lock = asyncio.Lock()
        self._jobs_lock = threading.Lock()
        self._log_buffers: Dict[UUID, List[Dict[str, Any]]] = {}
        self._buffer_lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._tasks: Dict[UUID, Future[Any]] = {}
    async def enqueue(
        self,
        command_id: str,
        params: Mapping[str, Any],
        *,
        settings: GuiSettings,
    ) -> Job:
        command = self._registry.get(command_id)
        async with self._lock:
            with self._jobs_lock:
                running = sum(
                    job.status in {JobStatus.PENDING, JobStatus.RUNNING} for job in self._jobs.values()
                )
                if running >= settings.execution.concurrency_limit:
                    raise RuntimeError("Concurrency limit reached")
                job_id = uuid4()
                job = Job(id=job_id, command=command, parameters=dict(params))
                job.log_path = self._log_dir / f"{job_id}.jsonl"
                self._log_buffers[job_id] = []
                self._jobs[job_id] = job
            future = asyncio.run_coroutine_threadsafe(
                self._run(job, settings=settings), self._loop
            )
            self._tasks[job_id] = future
            return job
    async def _run(self, job: Job, *, settings: GuiSettings) -> None:
        with self._jobs_lock:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
        log_path = job.log_path
        assert log_path is not None
        log_path.parent.mkdir(parents=True, exist_ok=True)
        async with JobLogWriter(job=job, manager=self) as writer:
            await writer.write_event(
                {
                    "stream": "status",
                    "event": "job_started",
                    "message": f"Starting command '{job.command.id}'",
                }
            )
            try:
                exit_code = await execute_command(
                    command=job.command,
                    params=job.parameters,
                    settings=settings,
                    writer=writer,
                )
            except Exception as exc:
                with self._jobs_lock:
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
                    job.finished_at = datetime.now(timezone.utc)
                await writer.write_event(
                    {
                        "stream": "status",
                        "event": "job_failed",
                        "message": str(exc),
                        "status": job.status,
                    }
                )
            else:
                with self._jobs_lock:
                    job.exit_code = exit_code
                    job.status = JobStatus.SUCCEEDED if exit_code == 0 else JobStatus.FAILED
                    if exit_code != 0:
                        job.error = f"Command exited with status {exit_code}"
                    job.finished_at = datetime.now(timezone.utc)
                await writer.write_event(
                    {
                        "stream": "status",
                        "event": "job_finished",
                        "message": f"Command finished with exit code {exit_code}",
                        "status": job.status,
                        "exit_code": exit_code,
                    }
                )
        if job.finished_at is None:
            with self._jobs_lock:
                job.finished_at = datetime.now(timezone.utc)
        self._tasks.pop(job.id, None)
        self._schedule_notify(job.id)
    async def get(self, job_id: UUID) -> Job:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job '{job_id}' not found")
        return job
    async def list(self) -> List[Job]:
        with self._jobs_lock:
            return list(self._jobs.values())
    async def stream_logs(self, job_id: UUID, *, tail: Optional[int] = None) -> List[Dict[str, Any]]:
        job = await self.get(job_id)
        if not job.log_path or not job.log_path.exists():
            return []
        lines = job.log_path.read_text(encoding="utf-8").splitlines()
        if tail is not None and tail > 0:
            lines = lines[-tail:]
        events: List[Dict[str, Any]] = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"message": line})
        return events
    async def follow_logs(self, job_id: UUID) -> AsyncIterator[Dict[str, Any]]:
        await self.get(job_id)
        index = 0
        while True:
            with self._buffer_lock:
                buffer_snapshot = list(self._log_buffers.get(job_id, []))
            while index < len(buffer_snapshot):
                yield buffer_snapshot[index]
                index += 1
            job = await self.get(job_id)
            if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED} and index >= len(buffer_snapshot):
                break
            await asyncio.sleep(0.05)
    async def _append_log_event(self, job_id: UUID, event: Dict[str, Any]) -> None:
        with self._buffer_lock:
            buffer = self._log_buffers.setdefault(job_id, [])
            buffer.append(event)
    def _schedule_notify(self, job_id: UUID) -> None:
        """Notify listeners that buffered logs changed.
        Phase 1 relies on polling `follow_logs`, so there is no dedicated
        notification mechanism yet. Keep the hook in place for future
        integration with condition variables or WebSocket push loops.
        """
        _ = job_id
def get_job_manager(registry: CommandRegistry, log_dir: Path) -> JobManager:
    return JobManager(registry=registry, log_dir=log_dir)
