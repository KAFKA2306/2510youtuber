import math
import shutil
import struct
import wave
from pathlib import Path

import ffmpeg
import pytest
from PIL import Image

from app.video import VideoGenerator


def _write_sine_wave(path: Path, duration: float = 1.0, frequency: float = 440.0, sample_rate: int = 44100) -> None:
    """Create a small WAV file for testing."""
    amplitude = 0.3
    total_frames = int(sample_rate * duration)

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for frame_index in range(total_frames):
            sample = math.sin(2 * math.pi * frequency * frame_index / sample_rate)
            value = int(32767 * amplitude * sample)
            wav_file.writeframes(struct.pack("<h", value))


@pytest.mark.integration
def test_fallback_video_burns_subtitles_with_style(tmp_path, monkeypatch):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg binary required for fallback rendering test")

    generator = VideoGenerator()
    monkeypatch.chdir(tmp_path)

    audio_path = tmp_path / "tone.wav"
    _write_sine_wave(audio_path)

    subtitle_path = tmp_path / "subtitles.srt"
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nテスト字幕\n", encoding="utf-8")

    output_path = generator._generate_fallback_video(str(audio_path), str(subtitle_path), "テストタイトル")

    assert output_path, "Fallback video path should be returned"
    output_file = Path(output_path)
    assert output_file.exists(), "Fallback video file should exist"

    frame_path = tmp_path / "frame.png"
    (
        ffmpeg
        .input(str(output_file), ss=0.5)
        .output(str(frame_path), vframes=1)
        .overwrite_output()
        .run(quiet=True)
    )

    assert frame_path.exists(), "Expected snapshot frame from fallback video"

    with Image.open(frame_path) as frame:
        bottom_region = frame.crop((0, frame.height - 240, frame.width, frame.height))
        bright_pixel_found = any(
            sum(bottom_region.getpixel((x, y))) / 3 > 200
            for x in range(0, bottom_region.width, 6)
            for y in range(0, bottom_region.height, 6)
        )

    assert bright_pixel_found, "Expected bright subtitle pixels in fallback video frame"
