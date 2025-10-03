from pathlib import Path

import ffmpeg
import pytest

from app.models.video_review import ScreenshotEvidence, VideoReviewFeedback
from app.services.video_review import VideoReviewService, VideoScreenshotExtractor
from app.config.settings import settings


@pytest.mark.unit
def test_video_screenshot_extractor_generates_expected_frames(tmp_path):
    video_path = tmp_path / "sample.mp4"
    (
        ffmpeg.input("testsrc=size=320x240:rate=30", f="lavfi")
        .output(str(video_path), vcodec="mpeg4", pix_fmt="yuv420p", t=5)
        .overwrite_output()
        .run(cmd=[settings.ffmpeg_path], quiet=True)
    )

    output_dir = tmp_path / "shots"
    extractor = VideoScreenshotExtractor(ffmpeg_path=settings.ffmpeg_path)
    screenshots = extractor.extract(
        video_path=str(video_path),
        output_dir=str(output_dir),
        interval_seconds=2,
        max_screenshots=3,
        force=True,
    )

    assert len(screenshots) == 3
    assert Path(screenshots[0].path).exists()
    assert screenshots[0].timestamp_seconds == 0
    assert screenshots[1].timestamp_seconds == 2
    assert screenshots[2].timestamp_seconds == 4


class DummyCollector:
    def __init__(self):
        self.recorded = []

    def record_ai_review(self, video_id, review):
        self.recorded.append((video_id, review))


class StubExtractor(VideoScreenshotExtractor):
    def __init__(self, screenshots):
        self._screenshots = screenshots
        self.calls = []

    def extract(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self._screenshots


class StubReviewer:
    def __init__(self, feedback):
        self.feedback = feedback
        self.calls = []

    def review(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.feedback


@pytest.mark.unit
def test_video_review_service_records_feedback(tmp_path, monkeypatch):
    dummy_screenshots = [
        ScreenshotEvidence(index=0, path=str(tmp_path / "shot_000.png"), timestamp_seconds=0.0),
        ScreenshotEvidence(index=1, path=str(tmp_path / "shot_001.png"), timestamp_seconds=60.0),
    ]

    Path(dummy_screenshots[0].path).write_bytes(b"fake")
    Path(dummy_screenshots[1].path).write_bytes(b"fake")

    feedback = VideoReviewFeedback(
        summary="良い動画", 
        positive_highlights=["構成が明確"],
        improvement_suggestions=["Bロールを追加"],
        retention_risks=["画面の静止が長い"],
        next_video_actions=["グラフ表示を増やす"],
    )

    stub_extractor = StubExtractor(dummy_screenshots)
    stub_reviewer = StubReviewer(feedback)
    dummy_collector = DummyCollector()

    monkeypatch.setattr("app.services.video_review.get_feedback_collector", lambda: dummy_collector)
    original_output_dir = settings.video_review.output_dir
    monkeypatch.setattr(settings.video_review, "output_dir", str(tmp_path / "reviews"))

    service = VideoReviewService(screenshot_extractor=stub_extractor, reviewer=stub_reviewer)

    result = service.review_video(
        video_path=str(tmp_path / "input.mp4"),
        video_id="video123",
        metadata={"title": "テスト動画"},
    )

    assert result.video_id == "video123"
    assert result.feedback.summary == "良い動画"
    assert dummy_collector.recorded, "AIレビューが記録されていません"
    recorded_id, recorded_review = dummy_collector.recorded[0]
    assert recorded_id == "video123"
    assert recorded_review.feedback.summary == "良い動画"

    monkeypatch.setattr(settings.video_review, "output_dir", original_output_dir)
