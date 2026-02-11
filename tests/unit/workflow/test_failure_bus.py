import asyncio
import pytest
from app.main import YouTubeWorkflow
from app.workflow import FailureBus, WorkflowContext, WorkflowFailureEvent, WorkflowStep
@pytest.mark.asyncio
async def test_failure_bus_notifies_subscribers():
    bus = FailureBus()
    observed = []
    async def subscriber(event: WorkflowFailureEvent) -> None:
        observed.append((event.step_name, event.error))
        event.response = {"handled": True}
    bus.subscribe(subscriber)
    event = WorkflowFailureEvent(step_name="unit", context=None)
    enriched = await bus.notify(event)
    assert observed == [("unit", None)]
    assert enriched.response == {"handled": True}
class _ExplodingStep(WorkflowStep):
    step_name = "exploding_step"
    async def execute(self, context: WorkflowContext):
        raise RuntimeError("boom")
@pytest.mark.asyncio
async def test_workflow_exception_routes_through_failure_bus(monkeypatch):
    workflow = YouTubeWorkflow()
    workflow.steps = [_ExplodingStep()]
    workflow._log_session = None
    monkeypatch.setattr(workflow, "_initialize_run", lambda mode: "run-123", raising=False)
    async def noop(*args, **kwargs):
        return None
    monkeypatch.setattr(workflow, "_notify_workflow_start", noop, raising=False)
    monkeypatch.setattr(workflow, "_notify_workflow_success", noop, raising=False)
    notified_errors = []
    async def capture_error(error):
        notified_errors.append(str(error))
    monkeypatch.setattr(workflow, "_notify_workflow_error", capture_error, raising=False)
    monkeypatch.setattr(workflow, "_update_run_status", lambda *args, **kwargs: None, raising=False)
    cleanup_called = asyncio.Event()
    def record_cleanup():
        cleanup_called.set()
    monkeypatch.setattr(workflow, "_cleanup_temp_files", record_cleanup, raising=False)
    result = await workflow.execute_full_workflow("unit-test")
    assert result["success"] is False
    assert result["failed_step"] == "exploding_step"
    assert result["error"] == "boom"
    assert result["run_id"] == "run-123"
    assert notified_errors and "boom" in notified_errors[0]
    assert cleanup_called.is_set()
