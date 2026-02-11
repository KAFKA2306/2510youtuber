"""Tests for the background workflow runner used by the dashboard."""
from __future__ import annotations
import asyncio
from app.workflow_runner import WorkflowRunner
class _SuccessfulWorkflow:
    def __init__(self) -> None:
        self.initialized = False
    def _initialize_run(self, mode: str) -> str:
        self.initialized = True
        return f"{mode}-run"
    async def execute_full_workflow(self, mode: str = "test"):
        run_id = self._initialize_run(mode)
        await asyncio.sleep(0)
        return {"success": True, "run_id": run_id, "video_url": "https://example.com/video"}
class _FailingWorkflow:
    def _initialize_run(self, mode: str) -> str:
        raise RuntimeError("boom")
    async def execute_full_workflow(self, mode: str = "test"):
        raise RuntimeError("boom")
def test_runner_surfaces_run_id_immediately():
    runner = WorkflowRunner(workflow_factory=_SuccessfulWorkflow)
    execution = runner.start("daily")
    run_id = execution.wait_until_started(timeout=1)
    result = execution.wait_until_finished(timeout=1)
    runner.shutdown()
    assert run_id == "daily-run"
    assert result["success"]
    assert execution.status == "completed"
def test_runner_handles_failures_without_run_id():
    runner = WorkflowRunner(workflow_factory=_FailingWorkflow)
    execution = runner.start("daily")
    run_id = execution.wait_until_started(timeout=0.1)
    execution.wait_until_finished(timeout=1)
    runner.shutdown()
    assert run_id is None
    assert execution.status == "failed"
    assert "boom" in (execution.error or "")
