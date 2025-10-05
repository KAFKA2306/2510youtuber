"""Unit tests for FFmpeg configuration helpers."""

import pytest
from pydub import AudioSegment

from app.services.media import ffmpeg_support

pytestmark = pytest.mark.unit


def _restore_audiosegment(original_converter, original_ffmpeg, original_ffprobe):
    AudioSegment.converter = original_converter
    if original_ffmpeg is not None:
        AudioSegment.ffmpeg = original_ffmpeg
    elif hasattr(AudioSegment, "ffmpeg"):
        delattr(AudioSegment, "ffmpeg")

    if original_ffprobe is not None:
        AudioSegment.ffprobe = original_ffprobe
    elif hasattr(AudioSegment, "ffprobe"):
        delattr(AudioSegment, "ffprobe")


def test_ensure_ffmpeg_tooling_configures_audiosegment(monkeypatch, tmp_path):
    """The helper should wire AudioSegment to the validated FFmpeg binaries."""

    ffmpeg_support.ensure_ffmpeg_tooling.cache_clear()

    binary = tmp_path / "ffmpeg"
    binary.write_text("#!/bin/sh\nexit 0\n")

    ffprobe = tmp_path / "ffprobe"
    ffprobe.write_text("#!/bin/sh\nexit 0\n")

    def fake_which(candidate: str):
        if candidate in {"ffmpeg", str(binary)}:
            return str(binary)
        if candidate == "ffprobe":
            return str(ffprobe)
        return None

    monkeypatch.setattr(ffmpeg_support.shutil, "which", fake_which)

    monkeypatch.setattr(ffmpeg_support, "_run_ffmpeg_command", lambda cmd: None)

    original_converter = AudioSegment.converter
    original_ffmpeg = getattr(AudioSegment, "ffmpeg", None)
    original_ffprobe = getattr(AudioSegment, "ffprobe", None)

    try:
        resolved = ffmpeg_support.ensure_ffmpeg_tooling(str(binary))
        assert resolved == str(binary)
        assert AudioSegment.converter == str(binary)
        assert getattr(AudioSegment, "ffmpeg", None) == str(binary)
        assert getattr(AudioSegment, "ffprobe", None) == str(ffprobe)
    finally:
        _restore_audiosegment(original_converter, original_ffmpeg, original_ffprobe)
        ffmpeg_support.ensure_ffmpeg_tooling.cache_clear()


def test_ensure_ffmpeg_tooling_raises_when_binary_missing(monkeypatch):
    """A missing FFmpeg binary should raise an informative error."""

    ffmpeg_support.ensure_ffmpeg_tooling.cache_clear()

    monkeypatch.setattr(ffmpeg_support.shutil, "which", lambda candidate: None)

    with pytest.raises(FileNotFoundError):
        ffmpeg_support.ensure_ffmpeg_tooling("/nonexistent/ffmpeg")


def test_ensure_ffmpeg_tooling_falls_back_to_imageio(monkeypatch, tmp_path):
    """The helper should resolve FFmpeg via imageio-ffmpeg when available."""

    ffmpeg_support.ensure_ffmpeg_tooling.cache_clear()

    monkeypatch.setattr(ffmpeg_support.shutil, "which", lambda candidate: None)

    fallback = tmp_path / "ffmpeg"
    fallback.write_text("#!/bin/sh\nexit 0\n")
    fallback.chmod(0o755)

    monkeypatch.setattr(ffmpeg_support, "get_ffmpeg_exe", lambda: str(fallback))
    monkeypatch.setattr(ffmpeg_support, "_run_ffmpeg_command", lambda cmd: None)

    original_converter = AudioSegment.converter
    original_ffmpeg = getattr(AudioSegment, "ffmpeg", None)
    original_ffprobe = getattr(AudioSegment, "ffprobe", None)

    try:
        resolved = ffmpeg_support.ensure_ffmpeg_tooling()
        assert resolved == str(fallback)
        assert AudioSegment.converter == str(fallback)
        assert getattr(AudioSegment, "ffmpeg", None) == str(fallback)
    finally:
        _restore_audiosegment(original_converter, original_ffmpeg, original_ffprobe)
        ffmpeg_support.ensure_ffmpeg_tooling.cache_clear()

