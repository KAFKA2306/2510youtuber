from types import SimpleNamespace

import pytest

from app.config import cfg
from app.models.qa import CheckStatus, MediaCheckResult, QualityGateReport
from app.workflow.base import WorkflowContext
from app.workflow.steps import QualityAssuranceStep


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quality_assurance_step_skips_when_disabled(monkeypatch):
    config = cfg.media_quality.copy(deep=True)
    config.enabled = False

    monkeypatch.setattr("app.workflow.steps.cfg", SimpleNamespace(media_quality=config))

    step = QualityAssuranceStep()
    context = WorkflowContext(run_id="skip-run", mode="daily")
    result = await step.execute(context)

    assert result.success
    assert result.data["skipped"] is True
    assert context.get("qa_passed") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quality_assurance_step_blocks_on_failure(monkeypatch):
    config = cfg.media_quality.copy(deep=True)
    config.enabled = True
    config.gating.enforce = True
    config.gating.skip_modes = []

    report = QualityGateReport(run_id="block-run", mode="daily")
    report.add_check(
        MediaCheckResult(
            name="video_compliance",
            status=CheckStatus.FAILED,
            message="resolution mismatch",
        )
    )
    report.report_path = "qa.json"

    class DummyPipeline:
        def __init__(self, _):
            pass

        def run(self, **kwargs):
            return report

        def should_block(self, report, mode):
            return True

    monkeypatch.setattr("app.workflow.steps.cfg", SimpleNamespace(media_quality=config))
    monkeypatch.setattr("app.workflow.steps.MediaQAPipeline", DummyPipeline)

    step = QualityAssuranceStep()
    context = WorkflowContext(run_id="block-run", mode="daily")
    result = await step.execute(context)

    assert result.success is False
    assert context.get("qa_passed") is False
    retry_request = context.get("qa_retry_request")
    assert retry_request["start_step"] == "script_generation"
