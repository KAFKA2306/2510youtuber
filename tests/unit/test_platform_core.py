"""Static smoke checks for core workflow schemas."""
from __future__ import annotations
import pytest
from app.models.workflow import StepStatus, WorkflowResult
@pytest.mark.unit
def test_workflow_result_core_fields_static():
    """The essential WorkflowResult fields should remain available."""
    fields = set(WorkflowResult.model_fields)
    assert {
        "success",
        "run_id",
        "mode",
        "execution_time_seconds",
        "wow_score",
        "retention_prediction",
    }.issubset(fields)
@pytest.mark.unit
def test_step_status_value_order_static():
    """StepStatus enum exposes the canonical lifecycle ordering."""
    values = [status.value for status in StepStatus]
    assert values == [
        "pending",
        "in_progress",
        "completed",
        "failed",
        "skipped",
    ]
