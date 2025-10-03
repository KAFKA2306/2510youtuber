import asyncio
from unittest.mock import AsyncMock

import pytest

from app.config import cfg
from app.workflow.base import StepResult, WorkflowContext, WorkflowStep
from app.workflow.steps import QualityAssuranceStep
from app.main import YouTubeWorkflow


class StubNewsStep(WorkflowStep):
    def __init__(self):
        self.calls = 0

    @property
    def step_name(self) -> str:
        return "news_collection"

    async def execute(self, context: WorkflowContext) -> StepResult:
        self.calls += 1
        context.set("news_items", [{"title": "Test"}])
        return self._success(data={"count": 1, "news_items": context.get("news_items")})


class StubScriptStep(WorkflowStep):
    def __init__(self):
        self.calls = 0

    @property
    def step_name(self) -> str:
        return "script_generation"

    async def execute(self, context: WorkflowContext) -> StepResult:
        self.calls += 1
        context.set("script_content", f"script-{self.calls}")
        context.set("script_path", f"/tmp/script-{self.calls}.txt")
        return self._success(data={"length": 100})


class StubQualityAssuranceStep(QualityAssuranceStep):
    def __init__(self):
        super().__init__()
        self.calls = 0

    async def execute(self, context: WorkflowContext) -> StepResult:
        self.calls += 1
        if self.calls == 1:
            context.set(
                "qa_retry_request",
                {"start_step": "script_generation", "reason": "qa failed", "attempt": self.calls},
            )
            context.set("qa_passed", False)
            return self._failure("qa failed")

        context.set("qa_passed", True)
        context.set("qa_retry_request", None)
        return self._success(data={"qa_passed": True})

    @property
    def step_name(self) -> str:
        return "media_quality_assurance"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workflow_retries_after_qa_failure(monkeypatch):
    workflow = YouTubeWorkflow()

    news_step = StubNewsStep()
    script_step = StubScriptStep()
    qa_step = StubQualityAssuranceStep()

    workflow.steps = [news_step, script_step, qa_step]

    monkeypatch.setattr(cfg.media_quality.gating, "retry_attempts", 1, raising=False)
    monkeypatch.setattr(cfg.media_quality.gating, "retry_start_step", "script_generation", raising=False)

    monkeypatch.setattr(workflow, "_initialize_run", lambda mode: "retry-run")
    monkeypatch.setattr(workflow, "_notify_workflow_start", AsyncMock())
    monkeypatch.setattr(workflow, "_notify_workflow_success", AsyncMock())
    monkeypatch.setattr(workflow, "_notify_workflow_error", AsyncMock())
    monkeypatch.setattr(workflow, "_update_run_status", lambda status, result: None)

    # Avoid external storage calls
    monkeypatch.setattr("app.main.metadata_storage.update_video_stats", lambda **kwargs: None)
    monkeypatch.setattr("app.main.metadata_storage.log_execution", lambda result: None)

    result = await workflow.execute_full_workflow(mode="daily")

    assert result["success"] is True
    assert news_step.calls == 1
    assert script_step.calls == 2  # retried once
    assert qa_step.calls == 2
