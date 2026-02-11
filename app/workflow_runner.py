"""Background workflow orchestration utilities used by the dashboard."""
from __future__ import annotations
import asyncio
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from types import MethodType
from typing import TYPE_CHECKING, Any, Callable, Deque, Dict, Iterable, Optional
if TYPE_CHECKING:
    from app.main import YouTubeWorkflow
@dataclass
class WorkflowExecution:
    """Represents the lifecycle of a single workflow run."""
    mode: str
    status: str = "pending"
    run_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    _future: Optional[Future] = field(default=None, repr=False)
    _started_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _finished_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    def mark_started(self, run_id: str) -> None:
        self.run_id = run_id
        self.status = "running"
        self.started_at = datetime.utcnow()
        self._started_event.set()
    def mark_completed(self, result: Dict[str, Any]) -> None:
        self.result = result
        self.error = result.get("error")
        self.status = "completed" if result.get("success") else "failed"
        self.finished_at = datetime.utcnow()
        self._finished_event.set()
    def mark_failed(self, error: Exception) -> None:
        self.error = str(error)
        self.status = "failed"
        self.finished_at = datetime.utcnow()
        self._finished_event.set()
    def wait_until_started(self, timeout: Optional[float] = None) -> Optional[str]:
        if self._started_event.wait(timeout):
            return self.run_id
        return None
    def wait_until_finished(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if self._finished_event.wait(timeout):
            return self.result
        return None
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "video_url": (self.result or {}).get("video_url"),
            "error": self.error,
        }
class WorkflowRunner:
    """Runs workflows in the background while surfacing lifecycle metadata."""
    def __init__(
        self,
        *,
        workflow_factory: Callable[[], "YouTubeWorkflow"] | None = None,
        max_workers: int = 1,
        history_limit: int = 20,
    ) -> None:
        if workflow_factory is None:
            from app.main import YouTubeWorkflow
            workflow_factory = YouTubeWorkflow
        self._workflow_factory = workflow_factory
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="workflow")
        self._history: Deque[WorkflowExecution] = deque(maxlen=history_limit)
        self._active: Dict[str, WorkflowExecution] = {}
        self._lock = threading.Lock()
    def start(self, mode: str) -> WorkflowExecution:
        execution = WorkflowExecution(mode=mode)
        def on_run_started(run_id: str) -> None:
            execution.mark_started(run_id)
            with self._lock:
                self._active[run_id] = execution
        workflow = self._create_instrumented_workflow(on_run_started)
        def runner() -> None:
            try:
                result = asyncio.run(workflow.execute_full_workflow(mode))
                execution.mark_completed(result)
            except Exception as error:
                execution.mark_failed(error)
            finally:
                if execution.run_id:
                    with self._lock:
                        self._active.pop(execution.run_id, None)
        future = self._executor.submit(runner)
        execution._future = future
        with self._lock:
            self._history.appendleft(execution)
        return execution
    def list_recent(self, limit: int = 10) -> Iterable[WorkflowExecution]:
        with self._lock:
            return list(self._history)[:limit]
    def list_active(self) -> Iterable[WorkflowExecution]:
        with self._lock:
            return list(self._active.values())
    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
    def _create_instrumented_workflow(self, callback: Callable[[str], None]):
        workflow = self._workflow_factory()
        original_initialize = workflow._initialize_run
        def instrumented_initialize(self, *args: Any, **kwargs: Any) -> str:
            run_id = original_initialize.__func__(self, *args, **kwargs)
            callback(run_id)
            return run_id
        workflow._initialize_run = MethodType(instrumented_initialize, workflow)
        return workflow
__all__ = ["WorkflowExecution", "WorkflowRunner"]
