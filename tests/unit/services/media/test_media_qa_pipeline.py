"""Tests for MediaQAPipeline gating behaviour."""

from app.config.settings import MediaQAGatingConfig, MediaQAConfig
from app.models.qa import CheckStatus, MediaCheckResult, QualityGateReport
from app.services.media.qa_pipeline import MediaQAPipeline


def _build_report(*checks: MediaCheckResult) -> QualityGateReport:
    report = QualityGateReport(run_id="run", mode="daily")
    for check in checks:
        report.add_check(check)
    return report


def test_should_block_when_critical_failure_even_if_enforce_disabled():
    gating = MediaQAGatingConfig(enforce=False)
    config = MediaQAConfig(enabled=True, gating=gating)
    pipeline = MediaQAPipeline(config)

    report = _build_report(
        MediaCheckResult(name="audio_integrity", status=CheckStatus.FAILED)
    )

    assert pipeline.should_block(report, mode="daily") is True


def test_should_not_block_for_non_critical_failure_when_enforce_disabled():
    gating = MediaQAGatingConfig(enforce=False)
    config = MediaQAConfig(enabled=True, gating=gating)
    pipeline = MediaQAPipeline(config)

    report = _build_report(
        MediaCheckResult(name="subtitle_alignment", status=CheckStatus.FAILED)
    )

    assert pipeline.should_block(report, mode="daily") is False


def test_critical_failures_are_skipped_in_configured_modes():
    gating = MediaQAGatingConfig(enforce=True, skip_modes=["test"])
    config = MediaQAConfig(enabled=True, gating=gating)
    pipeline = MediaQAPipeline(config)

    report = _build_report(
        MediaCheckResult(name="video_compliance", status=CheckStatus.FAILED)
    )

    assert pipeline.should_block(report, mode="test") is False
    assert pipeline.should_block(report, mode="daily") is True
