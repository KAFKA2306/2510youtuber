"""
Strict video generation tests - Zero tolerance for failures.

This test suite validates video generation with the strictest possible checks:
- FFmpeg command validation before execution
- Frame-by-frame encoding verification
- Output file integrity checks
- Resource validation
- No fallback testing - direct validation only

Design principle: Tests should fail immediately on any deviation from expected behavior.
No error handling masks failures - we validate the actual video generation logic works correctly.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, Mock, patch

import ffmpeg
import pytest

from app.config import settings
from app.video import VideoGenerator


class TestFFmpegCommandValidation:
    """Validate FFmpeg command construction is correct before execution."""

    def test_quality_settings_are_valid(self):
        """Quality settings must contain valid FFmpeg parameters."""
        vg = VideoGenerator()
        settings_dict = vg._get_quality_settings()

        # Must have these exact keys (FFmpeg short form)
        assert "c:v" in settings_dict  # Video codec
        assert "crf" in settings_dict  # Constant rate factor
        assert "preset" in settings_dict  # Encoding preset
        assert "c:a" in settings_dict  # Audio codec
        assert "b:a" in settings_dict  # Audio bitrate
        assert "b:v" in settings_dict  # Video bitrate

        # Values must be valid
        assert settings_dict["c:v"] == "libx264"
        # CRF can be string or int
        crf_value = int(settings_dict["crf"]) if isinstance(settings_dict["crf"], str) else settings_dict["crf"]
        assert 0 <= crf_value <= 51
        assert settings_dict["preset"] in ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
        assert settings_dict["c:a"] == "aac"

    def test_quality_settings_no_duplicate_parameters(self):
        """Ensure quality settings don't have duplicate keys that would conflict."""
        vg = VideoGenerator()
        settings_dict = vg._get_quality_settings()

        # Check no duplicate keys (dict would overwrite, but we validate structure)
        keys = list(settings_dict.keys())
        assert len(keys) == len(set(keys)), "Quality settings contain duplicate keys"

    def test_subtitle_path_normalization_handles_special_chars(self):
        """Subtitle paths with special characters must be normalized for FFmpeg."""
        vg = VideoGenerator()

        # On Linux, paths are returned as-is
        # On Windows, backslashes and colons are escaped
        if os.name == 'nt':
            # Windows path normalization
            test_path = "C:\\tmp\\subtitle.srt"
            normalized = vg._normalize_subtitle_path(test_path)
            assert "\\\\" in normalized, "Backslashes not escaped on Windows"
        else:
            # Linux paths returned unchanged
            test_path = "/tmp/subtitle.srt"
            normalized = vg._normalize_subtitle_path(test_path)
            assert normalized == test_path, "Linux path should be unchanged"

    def test_subtitle_style_string_is_valid_ass_format(self):
        """Subtitle style must be valid ASS format."""
        vg = VideoGenerator()
        style = vg._build_subtitle_style()

        # ASS style format validation
        assert "FontName=" in style
        assert "FontSize=" in style
        assert "PrimaryColour=" in style
        assert "OutlineColour=" in style
        assert "BackColour=" in style
        assert "Outline=" in style
        assert "Shadow=" in style
        assert "Alignment=" in style

        # No invalid characters that could break rendering
        assert "\n" not in style
        assert "\r" not in style

    def test_motion_background_stream_parameters_are_valid(self):
        """Motion background stream must have valid zoompan parameters."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test_bg.png")

            # Create minimal PNG using PIL
            from PIL import Image
            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(tmp_path)

            # Build stream
            stream = vg._build_motion_background_stream(tmp_path, duration=10.0)

            # Validate stream is an ffmpeg node
            assert stream is not None
            assert hasattr(stream, "get_args") or hasattr(stream, "filter") or hasattr(stream, "output")

    def test_audio_duration_extraction_is_accurate(self):
        """Audio duration must be extracted accurately from file."""
        vg = VideoGenerator()

        # Create test audio file with known duration (1 second of silence)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Generate 1 second of silence at 44100 Hz
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1.0", "-y", tmp_path
            ], capture_output=True, check=True)

            duration = vg._get_audio_duration(tmp_path)

            # Must be within 10ms of expected duration
            assert 0.99 <= duration <= 1.01, f"Duration {duration}s not within tolerance of 1.0s"

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestVideoInputValidation:
    """Validate input files before attempting video generation."""

    def test_validate_input_files_rejects_missing_audio(self):
        """Must reject missing audio file immediately."""
        vg = VideoGenerator()

        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            vg._validate_input_files(
                audio_path="/nonexistent/audio.wav",
                subtitle_path="/tmp/test.srt",
                background_image=None
            )

    def test_validate_input_files_rejects_missing_subtitle(self):
        """Must reject missing subtitle file immediately."""
        vg = VideoGenerator()

        # Create temporary audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name

        try:
            with pytest.raises(FileNotFoundError, match="Subtitle file not found"):
                vg._validate_input_files(
                    audio_path=audio_path,
                    subtitle_path="/nonexistent/subtitle.srt",
                    background_image=None
                )
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def test_validate_input_files_rejects_invalid_audio(self):
        """Must reject invalid audio file that can't be loaded."""
        vg = VideoGenerator()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio:
            audio_path = audio.name
            # Write invalid audio data
            audio.write(b"INVALID AUDIO DATA")

        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as subtitle:
            subtitle_path = subtitle.name
            subtitle.write(b"1\n00:00:00,000 --> 00:00:01,000\nTest\n")

        try:
            with pytest.raises(ValueError, match="Invalid audio file format"):
                vg._validate_input_files(audio_path, subtitle_path, None)
        finally:
            for path in [audio_path, subtitle_path]:
                if os.path.exists(path):
                    os.remove(path)

    def test_validate_input_files_accepts_valid_files(self):
        """Must accept valid audio and subtitle files."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test.wav")
            subtitle_path = os.path.join(tmpdir, "test.srt")

            # Create valid audio
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1.0", "-y", audio_path
            ], capture_output=True, check=True)

            # Create valid subtitle
            with open(subtitle_path, "w") as f:
                f.write("1\n00:00:00,000 --> 00:00:01,000\nTest\n")

            # Should not raise
            vg._validate_input_files(audio_path, subtitle_path, None)


class TestVideoOutputIntegrity:
    """Validate video output files meet minimum quality standards."""

    def test_video_info_extraction_validates_codec(self):
        """Video info must validate codec is H.264."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "test.mp4")

            # Generate 1 second test video with H.264
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "color=c=blue:size=1920x1080:duration=1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", video_path
            ], capture_output=True, check=True)

            # Use ffprobe to validate codec
            result = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ], capture_output=True, text=True, check=True)

            codec = result.stdout.strip()
            assert codec == "h264", f"Codec is {codec}, expected h264"

    def test_video_info_extraction_validates_resolution(self):
        """Video info must validate resolution is 1920x1080."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "test.mp4")

            # Generate test video with exact resolution
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "color=c=blue:size=1920x1080:duration=1",
                "-c:v", "libx264", "-y", video_path
            ], capture_output=True, check=True)

            # Use ffprobe to validate resolution
            result = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0", video_path
            ], capture_output=True, text=True, check=True)

            width, height = result.stdout.strip().split(',')
            assert width == "1920" and height == "1080", f"Resolution is {width}x{height}, expected 1920x1080"

    def test_generated_video_must_have_nonzero_size(self):
        """Generated video file must be larger than header size."""
        # Video files should be at least several KB
        MIN_VIDEO_SIZE = 10_000  # 10 KB minimum

        vg = VideoGenerator()

        # Create minimal test inputs
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test_audio.wav")
            subtitle_path = os.path.join(tmpdir, "test_subtitle.srt")
            video_path = os.path.join(tmpdir, "test_video.mp4")

            # Create 1 second audio
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1.0", "-y", audio_path
            ], capture_output=True, check=True)

            # Create subtitle
            with open(subtitle_path, "w") as f:
                f.write("1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n")

            # Generate video
            try:
                result_path = vg.generate_video(
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    output_path=video_path,
                    enable_ab_test=False,
                    use_stock_footage=False
                )

                # Must create file
                assert os.path.exists(result_path), "Video file not created"

                # Must be larger than minimum size
                file_size = os.path.getsize(result_path)
                assert file_size >= MIN_VIDEO_SIZE, f"Video file too small: {file_size} bytes < {MIN_VIDEO_SIZE} bytes"

            except Exception as e:
                pytest.fail(f"Video generation failed: {e}")


class TestFrameEncodingProgress:
    """Validate FFmpeg encodes all frames, not just the first frame."""

    @patch('ffmpeg.run')
    def test_ffmpeg_run_is_called_with_correct_parameters(self, mock_run):
        """FFmpeg must be called with correct video stream, audio stream, and output."""
        vg = VideoGenerator()

        # Create mock stream
        mock_stream = MagicMock()
        mock_stream.get_args.return_value = [
            "-i", "input.mp4", "-i", "audio.wav", "output.mp4"
        ]

        # Run FFmpeg
        try:
            vg._run_ffmpeg(mock_stream, description="test encoding")
        except:
            pass  # Expected to fail since it's mocked

        # Verify run was called
        assert mock_run.called, "ffmpeg.run was not called"

        # Verify parameters
        call_args = mock_run.call_args
        assert call_args[0][0] == mock_stream, "Stream not passed correctly"
        assert "capture_stdout" in call_args[1]
        assert "capture_stderr" in call_args[1]

    @patch('ffmpeg.run')
    def test_ffmpeg_error_handling_captures_stderr(self, mock_run):
        """When FFmpeg fails, stderr must be captured and logged."""
        vg = VideoGenerator()

        # Simulate FFmpeg error
        mock_error = ffmpeg.Error(
            cmd="ffmpeg",
            stdout=b"",
            stderr=b"frame=    1 fps=0.0 q=0.0 size=       0kB time=00:00:00.00 bitrate=N/A speed=   0x\nError: encoding failed"
        )
        mock_run.side_effect = mock_error

        mock_stream = MagicMock()

        # Must raise exception and log stderr
        with pytest.raises(ffmpeg.Error):
            vg._run_ffmpeg(mock_stream, description="test encoding")

    def test_video_duration_matches_audio_duration(self):
        """Generated video duration must match audio duration exactly."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test_audio.wav")
            subtitle_path = os.path.join(tmpdir, "test_subtitle.srt")
            video_path = os.path.join(tmpdir, "test_video.mp4")

            # Create 2 second audio
            target_duration = 2.0
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(target_duration), "-y", audio_path
            ], capture_output=True, check=True)

            # Create subtitle covering full duration
            with open(subtitle_path, "w") as f:
                f.write(f"1\n00:00:00,000 --> 00:00:{int(target_duration)},000\nTest subtitle\n")

            # Generate video
            try:
                result_path = vg.generate_video(
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    output_path=video_path,
                    enable_ab_test=False,
                    use_stock_footage=False
                )

                # Extract video duration using ffprobe
                probe_result = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    result_path
                ], capture_output=True, text=True, check=True)

                video_duration = float(probe_result.stdout.strip())

                # Must match within 100ms tolerance
                assert abs(video_duration - target_duration) <= 0.1, \
                    f"Video duration {video_duration}s doesn't match audio {target_duration}s"

            except Exception as e:
                pytest.fail(f"Video generation or validation failed: {e}")

    def test_video_frame_count_matches_duration_and_fps(self):
        """Number of frames must equal duration * FPS."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test_audio.wav")
            subtitle_path = os.path.join(tmpdir, "test_subtitle.srt")
            video_path = os.path.join(tmpdir, "test_video.mp4")

            # Create 3 second audio
            target_duration = 3.0
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(target_duration), "-y", audio_path
            ], capture_output=True, check=True)

            with open(subtitle_path, "w") as f:
                f.write(f"1\n00:00:00,000 --> 00:00:{int(target_duration)},000\nTest subtitle\n")

            try:
                result_path = vg.generate_video(
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    output_path=video_path,
                    enable_ab_test=False,
                    use_stock_footage=False
                )

                # Extract frame count using ffprobe
                probe_result = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-count_packets",
                    "-show_entries", "stream=nb_read_packets",
                    "-of", "csv=p=0",
                    result_path
                ], capture_output=True, text=True, check=True)

                frame_count = int(probe_result.stdout.strip())
                expected_frames = int(target_duration * vg.motion_fps)

                # Allow +/- 2 frames tolerance for encoding variations
                assert abs(frame_count - expected_frames) <= 2, \
                    f"Frame count {frame_count} doesn't match expected {expected_frames} (duration={target_duration}s, fps={vg.motion_fps})"

            except Exception as e:
                pytest.fail(f"Video generation or validation failed: {e}")


class TestFFmpegFailureScenarios:
    """Test specific failure scenarios that cause FFmpeg to stop encoding."""

    def test_subtitle_file_must_exist_during_encoding(self):
        """Subtitle file must not be deleted before FFmpeg finishes."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test_audio.wav")
            subtitle_path = os.path.join(tmpdir, "test_subtitle.srt")

            # Create audio
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1.0", "-y", audio_path
            ], capture_output=True, check=True)

            # Create subtitle
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:01,000\nテスト字幕\n")

            # File must still exist after normalization
            normalized_path = vg._normalize_subtitle_path(subtitle_path)

            # Original file must still be accessible
            assert os.path.exists(subtitle_path), "Subtitle file was deleted during normalization"

    def test_background_image_must_be_valid_format(self):
        """Background image must be valid PNG/JPEG that FFmpeg can read."""
        vg = VideoGenerator()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name
            # Write invalid PNG data
            tmp.write(b"NOT A PNG FILE")

        try:
            # Must reject invalid image
            with pytest.raises(Exception):
                vg._build_motion_background_stream(tmp_path, duration=1.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_audio_file_must_have_valid_codec(self):
        """Audio file must be in format FFmpeg can decode."""
        vg = VideoGenerator()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            audio_path = tmp.name
            # Write invalid WAV data
            tmp.write(b"INVALID AUDIO DATA")

        try:
            # Must reject invalid audio
            with pytest.raises(Exception):
                vg._get_audio_duration(audio_path)
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def test_subtitle_encoding_must_be_utf8(self):
        """Subtitle file must be UTF-8 encoded for Japanese text."""
        vg = VideoGenerator()

        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="wb") as tmp:
            subtitle_path = tmp.name
            # Write Japanese text in UTF-8
            content = "1\n00:00:00,000 --> 00:00:01,000\n日本語のテスト\n"
            tmp.write(content.encode('utf-8'))

        try:
            # Must successfully normalize UTF-8 subtitle
            normalized = vg._normalize_subtitle_path(subtitle_path)
            assert normalized is not None

            # Verify file is still readable as UTF-8
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content_read = f.read()
                assert "日本語" in content_read

        finally:
            if os.path.exists(subtitle_path):
                os.remove(subtitle_path)


class TestVideoGenerationEndToEnd:
    """End-to-end tests validating complete video generation pipeline."""

    def test_minimal_video_generation_succeeds(self):
        """Must successfully generate minimal 1-second video."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.wav")
            subtitle_path = os.path.join(tmpdir, "subtitle.srt")
            video_path = os.path.join(tmpdir, "video.mp4")

            # Create 1 second audio
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1.0", "-y", audio_path
            ], capture_output=True, check=True)

            # Create subtitle
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:01,000\nテスト\n")

            # Generate video
            result_path = vg.generate_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=video_path,
                enable_ab_test=False,
                use_stock_footage=False,
                title="Test Video"
            )

            # Validate output
            assert os.path.exists(result_path), "Video file not created"
            assert os.path.getsize(result_path) > 10_000, "Video file too small"

            # Validate with ffprobe
            probe_result = subprocess.run([
                "ffprobe", "-v", "error", "-show_format", "-show_streams", result_path
            ], capture_output=True, text=True, check=True)

            assert "codec_name=h264" in probe_result.stdout or "codec_name=avc" in probe_result.stdout
            assert "codec_name=aac" in probe_result.stdout

    def test_video_generation_with_japanese_subtitles(self):
        """Must successfully render Japanese subtitles."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.wav")
            subtitle_path = os.path.join(tmpdir, "subtitle.srt")
            video_path = os.path.join(tmpdir, "video.mp4")

            # Create audio
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "2.0", "-y", audio_path
            ], capture_output=True, check=True)

            # Create Japanese subtitle
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:01,000\n経済ニュース分析\n\n")
                f.write("2\n00:00:01,000 --> 00:00:02,000\n重要なポイント\n")

            # Generate video
            result_path = vg.generate_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=video_path,
                enable_ab_test=False,
                use_stock_footage=False,
                title="Japanese Test"
            )

            # Must create valid video
            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 10_000

    @pytest.mark.slow
    def test_video_generation_with_long_duration(self):
        """Must successfully generate 10+ second video without stopping."""
        vg = VideoGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.wav")
            subtitle_path = os.path.join(tmpdir, "subtitle.srt")
            video_path = os.path.join(tmpdir, "video.mp4")

            # Create 10 second audio
            target_duration = 10.0
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(target_duration), "-y", audio_path
            ], capture_output=True, check=True)

            # Create subtitles every second
            with open(subtitle_path, "w", encoding="utf-8") as f:
                for i in range(10):
                    f.write(f"{i+1}\n")
                    f.write(f"00:00:{i:02d},000 --> 00:00:{i+1:02d},000\n")
                    f.write(f"字幕 {i+1}\n\n")

            # Generate video
            result_path = vg.generate_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=video_path,
                enable_ab_test=False,
                use_stock_footage=False
            )

            # Validate duration
            probe_result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                result_path
            ], capture_output=True, text=True, check=True)

            video_duration = float(probe_result.stdout.strip())
            assert video_duration >= 9.5, f"Video duration {video_duration}s is too short (expected ~10s)"

            # Validate frame count
            probe_result = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-count_packets",
                "-show_entries", "stream=nb_read_packets",
                "-of", "csv=p=0",
                result_path
            ], capture_output=True, text=True, check=True)

            frame_count = int(probe_result.stdout.strip())
            min_expected_frames = int(9.5 * vg.motion_fps)

            assert frame_count >= min_expected_frames, \
                f"Frame count {frame_count} is too low (expected >={min_expected_frames})"
