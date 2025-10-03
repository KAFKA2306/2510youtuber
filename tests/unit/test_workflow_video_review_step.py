
import pytest

from app.config import cfg
from app.models.video_review import ScreenshotEvidence, VideoReviewFeedback, VideoReviewResult
from app.workflow.base import WorkflowContext
from app.workflow.steps import ReviewVideoStep


class StubReviewService:
    def __init__(self, result: VideoReviewResult):
        self.result = result
        self.calls = []

    def review_video(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_video_step_skips_when_disabled(monkeypatch):
    step = ReviewVideoStep()
    monkeypatch.setattr(cfg.video_review, "enabled", False)

    context = WorkflowContext(run_id="run-1", mode="daily")
    result = await step.execute(context)

    assert result.success is True
    assert result.data.get("skipped") is True
    assert result.data.get("review_enabled") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_video_step_invokes_service(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg.video_review, "enabled", True)
    monkeypatch.setattr(cfg.video_review, "output_dir", str(tmp_path / "reviews"))

    video_path = tmp_path / "final_video.mp4"
    video_path.write_bytes(b"fake video content")

    screenshot_path = tmp_path / "shot_000.png"
    screenshot_path.write_bytes(b"img")

    review_result = VideoReviewResult(
        video_path=str(video_path),
        video_id="yt123",
        model_name="test-model",
        screenshots=[
            ScreenshotEvidence(index=0, path=str(screenshot_path), timestamp_seconds=0.0)
        ],
        feedback=VideoReviewFeedback(
            summary="終盤のテンポを上げると更に良い",
            positive_highlights=["冒頭のまとめが明瞭"],
            improvement_suggestions=["中盤でグラフを追加"],
            retention_risks=["画面が静止しがち"],
            next_video_actions=["30秒ごとにB-rollを差し込む"],
        ),
    )

    stub_service = StubReviewService(review_result)
    monkeypatch.setattr("app.workflow.steps.get_video_review_service", lambda: stub_service)

    context = WorkflowContext(run_id="run-2", mode="daily")
    context.set("video_path", str(video_path))
    context.set("metadata", {"title": "テスト動画"})
    context.set("video_id", "yt999")

    step = ReviewVideoStep()
    result = await step.execute(context)

    assert result.success is True
    assert result.data.get("skipped") is False
    assert result.data.get("review_summary") == "終盤のテンポを上げると更に良い"
    assert result.data.get("screenshots_captured") == 1
    assert screenshot_path.as_posix() in result.files_generated

    stored_review = context.get("video_review")
    assert stored_review is not None
    assert stored_review["feedback"]["summary"] == "終盤のテンポを上げると更に良い"

    assert len(stub_service.calls) == 1
    call_kwargs = stub_service.calls[0]
    assert call_kwargs["video_path"] == str(video_path)
    assert call_kwargs["video_id"] == "yt999"
    assert call_kwargs["metadata"]["title"] == "テスト動画"
