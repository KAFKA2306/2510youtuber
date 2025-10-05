import json
from pathlib import Path

import pytest
from pydub.generators import Sine

from app.config import cfg
from app.config.settings import MediaQAConfig
from app.services.media.qa_pipeline import MediaQAPipeline


@pytest.mark.unit
def test_media_qa_pipeline_detects_missing_inputs(tmp_path):
    config = cfg.media_quality.copy(deep=True)
    config.report_dir = str(tmp_path)
    pipeline = MediaQAPipeline(config)

    report = pipeline.run(
        run_id="run-missing",
        mode="daily",
        script_path=None,
        script_content=None,
        audio_path=None,
        subtitle_path=None,
        video_path=None,
    )

    assert {check.name for check in report.blocking_failures()} == {
        "audio_integrity",
        "subtitle_alignment",
        "video_compliance",
    }
    assert pipeline.should_block(report, mode="daily") is False
    assert report.report_path is not None
    assert (tmp_path / Path(report.report_path).name).exists()


@pytest.mark.unit
def test_media_qa_pipeline_audio_pass(tmp_path):
    config: MediaQAConfig = cfg.media_quality.copy(deep=True)
    config.report_dir = str(tmp_path)
    config.video.enabled = False
    config.subtitles.enabled = False
    config.audio.peak_dbfs_max = 0.0
    config.audio.rms_dbfs_min = -60.0
    config.audio.rms_dbfs_max = -1.0
    config.audio.max_silence_seconds = 2.0

    audio_path = tmp_path / "test.wav"
    sine = Sine(440).to_audio_segment(duration=1500).apply_gain(-6.0)
    sine.export(audio_path, format="wav")

    pipeline = MediaQAPipeline(config)
    report = pipeline.run(
        run_id="run-audio",
        mode="daily",
        script_path=None,
        script_content=None,
        audio_path=str(audio_path),
        subtitle_path=None,
        video_path=None,
    )

    assert any(check.name == "audio_integrity" and check.status.value == "passed" for check in report.checks)
    assert report.passed
    assert pipeline.should_block(report, mode="daily") is False

    saved = tmp_path / Path(report.report_path).name
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["passed"] is True
