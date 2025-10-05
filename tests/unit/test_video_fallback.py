from pathlib import Path

import pytest

import app.video as video_module
from app.video import VideoGenerator


class DummyStream:
    def __init__(self, name: str, applied_filters: list):
        self.name = name
        self._applied_filters = applied_filters

    def filter(self, *args, **kwargs):
        self._applied_filters.append((args, kwargs))
        return self

    def overwrite_output(self):
        return self


class DummyOutput(DummyStream):
    pass


@pytest.mark.unit
def test_fallback_video_attempts_to_burn_subtitles(monkeypatch, tmp_path):
    generator = VideoGenerator()

    subtitle_path = tmp_path / "subtitles.srt"
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nテスト\n")

    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("fake audio")

    applied_filters = []

    def fake_input(source, **kwargs):
        if isinstance(source, str) and source.startswith("color="):
            return DummyStream("video", applied_filters)
        if Path(source) == audio_path:
            return DummyStream("audio", applied_filters)
        raise AssertionError(f"Unexpected input source: {source}")

    def fake_output(video_stream, audio_stream, output_path, **kwargs):
        assert isinstance(video_stream, DummyStream)
        assert audio_stream.name == "audio"
        assert output_path.endswith(".mp4")
        return DummyOutput("output", applied_filters)

    def fake_run(stream, quiet=True):
        assert isinstance(stream, DummyOutput)

    monkeypatch.setattr(generator, "_get_audio_duration", lambda _path: 1.0)
    monkeypatch.setattr(generator, "_build_subtitle_style", lambda: "FontName=Dummy")
    monkeypatch.setattr(generator, "_normalize_subtitle_path", lambda path: str(path))
    monkeypatch.setattr(video_module.ffmpeg, "input", fake_input)
    monkeypatch.setattr(video_module.ffmpeg, "output", fake_output)
    monkeypatch.setattr(video_module.ffmpeg, "run", fake_run)

    generator._generate_fallback_video(str(audio_path), str(subtitle_path), "title")

    assert any(
        args and args[0] == "subtitles" and args[1] == str(subtitle_path)
        for args, _ in applied_filters
    )
