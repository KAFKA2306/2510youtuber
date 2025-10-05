"""Unit tests for video generator motion and subtitle helpers."""

import importlib
import os
import sys
import types

import pytest
from ffmpeg.nodes import FilterableStream

pytestmark = pytest.mark.unit


@pytest.fixture()
def video_components(monkeypatch):
    """Load app.video with lightweight stubbed workflow steps."""
    stub_ensure = lambda path=None: "ffmpeg"
    monkeypatch.setattr("app.services.media.ffmpeg_support.ensure_ffmpeg_tooling", stub_ensure)

    preloaded = "app.video" in sys.modules
    if preloaded:
        module = sys.modules["app.video"]
        monkeypatch.setattr(module, "ensure_ffmpeg_tooling", stub_ensure)
        yield module, module.VideoGenerator
        return

    stub_steps = types.ModuleType("app.workflow.steps")
    step_names = [
        "AlignSubtitlesStep",
        "CollectNewsStep",
        "GenerateMetadataStep",
        "GenerateScriptStep",
        "GenerateThumbnailStep",
        "GenerateVideoStep",
        "GenerateVisualDesignStep",
        "SynthesizeAudioStep",
        "TranscribeAudioStep",
        "UploadToDriveStep",
        "UploadToYouTubeStep",
        "QualityAssuranceStep",
    ]

    for name in step_names:
        setattr(stub_steps, name, type(name, (), {}))

    monkeypatch.setitem(sys.modules, "app.workflow.steps", stub_steps)

    module = importlib.import_module("app.video")
    monkeypatch.setattr(module, "ensure_ffmpeg_tooling", stub_ensure)
    try:
        yield module, module.VideoGenerator
    finally:
        sys.modules.pop("app.video", None)


def test_subtitle_style_contains_core_fields(video_components):
    module, VideoGenerator = video_components
    generator = VideoGenerator()

    style = generator._build_subtitle_style()

    assert "FontName=" in style
    assert "FontSize=" in style
    assert "BackColour=" in style
    assert "MarginV=" in style


def test_normalize_subtitle_path_handles_windows(video_components, monkeypatch):
    module, VideoGenerator = video_components
    generator = VideoGenerator()
    monkeypatch.setattr(module.os, "name", "nt")

    path = "C:\\temp\\subs.srt"
    normalized = generator._normalize_subtitle_path(path)
    expected = path.replace("\\", "\\\\").replace(":", "\\:")

    assert normalized == expected


def test_motion_background_stream_builds_filter(video_components):
    _, VideoGenerator = video_components
    generator = VideoGenerator()
    background_path = generator._create_default_background("Test Title")

    try:
        stream = generator._build_motion_background_stream(background_path, duration=3.0)
        assert isinstance(stream, FilterableStream)
    finally:
        if background_path and os.path.exists(background_path):
            os.remove(background_path)
