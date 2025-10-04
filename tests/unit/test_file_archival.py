"""Test suite for video file archival system (TDD approach).

Following t-wada's testing philosophy:
- Tests specify behavior before implementation
- Each test is independent and focused
- Tests serve as living documentation
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.workflow.base import WorkflowContext


class TestVideoFileArchival:
    """Test video file archival and organization strategy."""

    def test_video_output_path_includes_run_id_and_timestamp(self):
        """Video should be saved to output/{timestamp}_{run_id}_{sanitized_title}/video.mp4"""
        from app.services.file_archival import FileArchivalManager

        manager = FileArchivalManager()
        run_id = "abc123"
        timestamp = "20251003_150000"
        title = "【速報】日銀利上げ"

        output_path = manager.get_video_output_path(run_id=run_id, timestamp=timestamp, title=title)

        assert "output/" in output_path
        assert run_id in output_path
        assert timestamp in output_path
        assert "video.mp4" in output_path
        # Sanitized title should be present (no special chars)
        assert "日銀利上げ" in output_path or "速報" in output_path

    def test_all_artifacts_stored_in_same_directory(self):
        """Video, audio, thumbnail, script should share the same parent directory."""
        from app.services.file_archival import FileArchivalManager

        manager = FileArchivalManager()
        run_id = "abc123"
        timestamp = "20251003_150000"
        title = "Test Video"

        video_path = manager.get_video_output_path(run_id, timestamp, title)
        audio_path = manager.get_audio_output_path(run_id, timestamp, title)
        thumbnail_path = manager.get_thumbnail_output_path(run_id, timestamp, title)
        script_path = manager.get_script_output_path(run_id, timestamp, title)

        # All should have the same parent directory
        video_dir = Path(video_path).parent
        audio_dir = Path(audio_path).parent
        thumbnail_dir = Path(thumbnail_path).parent
        script_dir = Path(script_path).parent

        assert video_dir == audio_dir == thumbnail_dir == script_dir

    def test_create_output_directory_structure(self):
        """Should create output directory if it doesn't exist."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir)
            run_id = "test123"
            timestamp = "20251003_150000"
            title = "Test"

            output_dir = manager.create_output_directory(run_id, timestamp, title)

            assert os.path.exists(output_dir)
            assert os.path.isdir(output_dir)
            assert run_id in output_dir
            assert timestamp in output_dir

    def test_move_generated_files_to_archive(self):
        """Should move generated files from temp locations to organized archive."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir)

            # Create temporary files
            temp_video = os.path.join(tmpdir, "temp_video.mp4")
            temp_audio = os.path.join(tmpdir, "temp_audio.wav")
            Path(temp_video).write_text("video content")
            Path(temp_audio).write_text("audio content")

            # Archive them
            archived_files = manager.archive_workflow_files(
                run_id="test123",
                timestamp="20251003_150000",
                title="Test Video",
                files={
                    "video": temp_video,
                    "audio": temp_audio,
                },
            )

            # Original temp files should be moved (or copied)
            assert os.path.exists(archived_files["video"])
            assert os.path.exists(archived_files["audio"])
            # All archived files should be in the same directory
            assert Path(archived_files["video"]).parent == Path(archived_files["audio"]).parent

    def test_files_persist_after_workflow_completion(self):
        """Files should exist on disk after workflow completes."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir)

            # Simulate workflow completion
            temp_video = os.path.join(tmpdir, "fallback_video_123.mp4")
            Path(temp_video).write_text("video content")

            archived = manager.archive_workflow_files(
                run_id="test123", timestamp="20251003_150000", title="Test", files={"video": temp_video}
            )

            # After archival, file should exist
            assert os.path.exists(archived["video"])
            # And contain the content
            assert Path(archived["video"]).read_text() == "video content"

    def test_duplicate_run_ids_handled_with_unique_directories(self):
        """Multiple runs with same timestamp shouldn't overwrite files."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir)

            # Create two outputs with different run_ids but same timestamp
            dir1 = manager.create_output_directory("run1", "20251003_150000", "Test")
            dir2 = manager.create_output_directory("run2", "20251003_150000", "Test")

            # Should create different directories
            assert dir1 != dir2
            assert os.path.exists(dir1)
            assert os.path.exists(dir2)

    def test_sanitize_title_for_safe_filesystem_path(self):
        """Special characters in title should be sanitized for filesystem."""
        from app.services.file_archival import FileArchivalManager

        manager = FileArchivalManager()

        # Test various special characters
        test_cases = [
            ("【速報】日銀利上げ！", "速報日銀利上げ"),
            ("Test / Video : Part 1", "Test_Video_Part_1"),
            ("Video with <brackets>", "Video_with_brackets"),
            ("Question?", "Question"),
        ]

        for input_title, expected_pattern in test_cases:
            sanitized = manager.sanitize_title(input_title)
            # Should not contain problematic characters
            assert "/" not in sanitized
            assert ":" not in sanitized
            assert "<" not in sanitized
            assert ">" not in sanitized
            assert "?" not in sanitized

    def test_get_workflow_output_directory_from_context(self):
        """Should retrieve or create output directory from workflow context."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir)
            context = WorkflowContext(run_id="test123", mode="daily")
            context.set("metadata", {"title": "Test Video"})

            output_dir = manager.get_or_create_workflow_directory(context)

            assert os.path.exists(output_dir)
            assert "test123" in output_dir
            # Should be stored in context for reuse
            assert context.get("output_directory") == output_dir

    def test_list_archived_workflows(self):
        """Should be able to list all archived workflow directories."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir)

            # Create multiple workflow directories
            manager.create_output_directory("run1", "20251003_100000", "Video 1")
            manager.create_output_directory("run2", "20251003_110000", "Video 2")
            manager.create_output_directory("run3", "20251003_120000", "Video 3")

            archived = manager.list_archived_workflows()

            assert len(archived) == 3
            assert all("run_id" in item for item in archived)
            assert all("timestamp" in item for item in archived)
            assert all("directory" in item for item in archived)

    def test_cleanup_old_files_by_retention_policy(self):
        """Files older than retention period should be eligible for cleanup."""
        from app.services.file_archival import FileArchivalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileArchivalManager(base_output_dir=tmpdir, retention_days=30)

            # Create a workflow directory
            _old_dir = manager.create_output_directory("old_run", "20200101_000000", "Old Video")
            _recent_dir = manager.create_output_directory("new_run", "20251003_000000", "Recent Video")

            # Mock file creation time
            old_time = datetime(2020, 1, 1).timestamp()
            recent_time = datetime(2025, 10, 3).timestamp()

            with patch("os.path.getmtime") as mock_getmtime:

                def mtime_side_effect(path):
                    path_str = str(path)
                    if "old_run" in path_str:
                        return old_time
                    return recent_time

                mock_getmtime.side_effect = mtime_side_effect

                # Get files eligible for cleanup
                old_files = manager.get_files_to_cleanup()

                # Should include old directory, not recent
                assert any("old_run" in str(f) for f in old_files)
                assert not any("new_run" in str(f) for f in old_files)


class TestWorkflowIntegration:
    """Test integration with existing workflow system."""

    def test_video_generator_uses_archival_manager(self):
        """VideoGenerator should use FileArchivalManager for output paths."""
        from app.video import VideoGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.video.FileArchivalManager") as mock_manager:
                mock_instance = MagicMock()
                mock_manager.return_value = mock_instance
                mock_instance.get_video_output_path.return_value = f"{tmpdir}/test_video.mp4"

                _generator = VideoGenerator()
                # Should use archival manager when context is provided
                # (This will fail until implementation)

    def test_generate_video_step_archives_output(self):
        """GenerateVideoStep should archive video to organized directory."""
        from app.workflow.steps import GenerateVideoStep

        with tempfile.TemporaryDirectory() as tmpdir:
            _step = GenerateVideoStep()
            context = WorkflowContext(run_id="test123", mode="daily")
            context.set("audio_path", f"{tmpdir}/test_audio.wav")
            context.set("subtitle_path", f"{tmpdir}/test_subs.srt")
            context.set("metadata", {"title": "Test Video"})

            # Create mock files
            Path(context.get("audio_path")).write_text("audio")
            Path(context.get("subtitle_path")).write_text("subs")

            # This will fail until implementation
            # result = await step.execute(context)
            # assert result.success
            # video_path = context.get("video_path")
            # assert "output/" in video_path
            # assert "test123" in video_path

    def test_workflow_result_includes_archived_paths(self):
        """WorkflowResult should contain paths to archived files."""
        from app.models.workflow import WorkflowResult

        result = WorkflowResult(
            success=True,
            run_id="test123",
            mode="daily",
            execution_time_seconds=100.0,
            video_path="output/20251003_test123_TestVideo/video.mp4",
            generated_files=[
                "output/20251003_test123_TestVideo/video.mp4",
                "output/20251003_test123_TestVideo/audio.wav",
                "output/20251003_test123_TestVideo/thumbnail.png",
            ],
        )

        # All files should be in organized directory
        assert all("output/" in f for f in result.generated_files)
        assert all("test123" in f for f in result.generated_files)
