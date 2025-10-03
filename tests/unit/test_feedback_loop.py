"""Unit tests for feedback loop system."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.analytics import FeedbackAnalyzer
from app.metadata_storage import MetadataStorage
from app.models.workflow import WorkflowResult, YouTubeFeedback


class TestWorkflowResultModel:
    """Test WorkflowResult extended model."""

    def test_create_basic_workflow_result(self):
        """Test creating a basic WorkflowResult."""
        result = WorkflowResult(
            success=True,
            run_id="test_001",
            mode="test",
            execution_time_seconds=120.5,
        )

        assert result.success is True
        assert result.run_id == "test_001"
        assert result.mode == "test"
        assert result.execution_time_seconds == 120.5

    def test_workflow_result_with_quality_metrics(self):
        """Test WorkflowResult with quality metrics."""
        result = WorkflowResult(
            success=True,
            run_id="test_002",
            mode="daily",
            execution_time_seconds=150.0,
            title="Test Video Title",
            wow_score=8.5,
            japanese_purity=96.2,
            retention_prediction=52.0,
            surprise_points=6,
            emotion_peaks=7,
            hook_type="衝撃的事実",
            topic="株式市場",
        )

        assert result.wow_score == 8.5
        assert result.japanese_purity == 96.2
        assert result.hook_type == "衝撃的事実"
        assert result.topic == "株式市場"

    def test_script_grade_calculation(self):
        """Test script grade calculation from WOW score."""
        # Grade S (>= 8.5)
        result_s = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0, wow_score=8.7
        )
        assert result_s.script_grade == "S"

        # Grade A (>= 8.0)
        result_a = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0, wow_score=8.2
        )
        assert result_a.script_grade == "A"

        # Grade B (>= 7.5)
        result_b = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0, wow_score=7.8
        )
        assert result_b.script_grade == "B"

        # Grade C (< 7.5)
        result_c = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0, wow_score=7.0
        )
        assert result_c.script_grade == "C"

        # N/A (no score)
        result_na = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0
        )
        assert result_na.script_grade == "N/A"

    def test_status_icon(self):
        """Test status icon calculation."""
        # Success with good retention
        result_good = WorkflowResult(
            success=True,
            run_id="test",
            mode="test",
            execution_time_seconds=1.0,
            retention_prediction=52.0,
        )
        assert result_good.status_icon == "✅"

        # Success with good WOW score
        result_wow = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0, wow_score=8.5
        )
        assert result_wow.status_icon == "✅"

        # Success but no metrics
        result_warning = WorkflowResult(
            success=True, run_id="test", mode="test", execution_time_seconds=1.0
        )
        assert result_warning.status_icon == "⚠️"

        # Failed
        result_failed = WorkflowResult(
            success=False, run_id="test", mode="test", execution_time_seconds=1.0
        )
        assert result_failed.status_icon == "❌"

    def test_workflow_result_serialization(self):
        """Test WorkflowResult can be serialized to JSON."""
        result = WorkflowResult(
            success=True,
            run_id="test_003",
            mode="daily",
            execution_time_seconds=100.0,
            title="Test Title",
            wow_score=8.0,
        )

        # Should serialize without error
        json_str = result.model_dump_json()
        assert json_str is not None
        assert "test_003" in json_str

        # Should deserialize
        data = json.loads(json_str)
        result2 = WorkflowResult(**data)
        assert result2.run_id == "test_003"
        assert result2.wow_score == 8.0


class TestYouTubeFeedbackModel:
    """Test YouTubeFeedback model."""

    def test_create_youtube_feedback(self):
        """Test creating YouTubeFeedback."""
        feedback = YouTubeFeedback(
            video_id="test_video_123",
            views=1000,
            views_24h=250,
            likes=50,
            comments_count=10,
            ctr=4.5,
            avg_view_duration=180.5,
            avg_view_percentage=55.0,
        )

        assert feedback.video_id == "test_video_123"
        assert feedback.views == 1000
        assert feedback.ctr == 4.5

    def test_engagement_rate_calculation(self):
        """Test engagement rate calculation."""
        feedback = YouTubeFeedback(
            video_id="test", views=1000, likes=50, comments_count=30
        )

        # Engagement = (likes + comments) / views * 100
        expected = (50 + 30) / 1000 * 100
        assert feedback.engagement_rate == expected

    def test_engagement_rate_no_views(self):
        """Test engagement rate with no views."""
        feedback = YouTubeFeedback(video_id="test", views=0)
        assert feedback.engagement_rate is None


class TestMetadataStorageLogging:
    """Test MetadataStorage logging functionality."""

    def test_save_to_jsonl(self, tmp_path):
        """Test saving WorkflowResult to JSONL."""
        jsonl_path = tmp_path / "test_log.jsonl"

        storage = MetadataStorage(jsonl_path=str(jsonl_path))

        result = WorkflowResult(
            success=True,
            run_id="test_001",
            mode="test",
            execution_time_seconds=100.0,
            title="Test Title",
        )

        # Save
        storage._save_to_jsonl(result)

        # Verify file exists and contains data
        assert jsonl_path.exists()

        with open(jsonl_path, "r") as f:
            line = f.readline()
            data = json.loads(line)
            assert data["run_id"] == "test_001"
            assert data["title"] == "Test Title"

    def test_multiple_executions_to_jsonl(self, tmp_path):
        """Test appending multiple executions."""
        jsonl_path = tmp_path / "test_log.jsonl"
        storage = MetadataStorage(jsonl_path=str(jsonl_path))

        # Save 3 executions
        for i in range(3):
            result = WorkflowResult(
                success=True,
                run_id=f"test_{i:03d}",
                mode="test",
                execution_time_seconds=100.0,
            )
            storage._save_to_jsonl(result)

        # Verify 3 lines
        with open(jsonl_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 3

            # Verify each line
            for i, line in enumerate(lines):
                data = json.loads(line)
                assert data["run_id"] == f"test_{i:03d}"

    def test_format_dashboard_row(self):
        """Test formatting dashboard row."""
        storage = MetadataStorage()

        result = WorkflowResult(
            success=True,
            run_id="test_042",
            mode="daily",
            execution_time_seconds=120.0,
            title="Test Video Title",
            video_id="youtube_123",
            wow_score=8.5,
            retention_prediction=52.0,
            hook_type="衝撃的事実",
            topic="株式市場",
        )

        row = storage._format_dashboard_row(result)

        # Check row structure
        assert len(row) == 12  # All columns
        assert row[2] == "Test Video Title"  # title
        assert row[3] == "株式市場"  # topic
        assert row[4] == "衝撃的事実"  # hook
        assert "8.5" in row[5]  # wow_score
        assert "52.0%" in row[6]  # retention
        assert row[10] == "✅"  # status icon
        assert "youtube_123" in row[11]  # YouTube link

    def test_format_quality_row(self):
        """Test formatting quality row."""
        storage = MetadataStorage()

        result = WorkflowResult(
            success=True,
            run_id="test_001",
            mode="daily",
            execution_time_seconds=100.0,
            wow_score=8.5,
            surprise_points=6,
            emotion_peaks=7,
            curiosity_gap_score=4.0,
            visual_instructions=18,
            japanese_purity=96.2,
        )

        row = storage._format_quality_row(result)

        assert len(row) == 9
        assert "8.5" in row[1]  # wow_score
        assert row[2] == 6  # surprise_points
        assert row[3] == 7  # emotion_peaks
        assert "96.2%" in row[6]  # japanese_purity
        assert row[7] == "S"  # grade

    def test_format_number(self):
        """Test number formatting."""
        storage = MetadataStorage()

        assert storage._format_number(500) == "500"
        assert storage._format_number(1234) == "1.2K"
        assert storage._format_number(15678) == "15.7K"

    def test_format_duration(self):
        """Test duration formatting."""
        storage = MetadataStorage()

        assert storage._format_duration(65) == "1m 05s"
        assert storage._format_duration(204) == "3m 24s"
        assert storage._format_duration(3661) == "61m 01s"


class TestFeedbackAnalyzer:
    """Test FeedbackAnalyzer functionality."""

    def test_load_executions_empty(self, tmp_path):
        """Test loading from empty JSONL."""
        jsonl_path = tmp_path / "empty.jsonl"
        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))

        executions = analyzer.load_executions()
        assert executions == []

    def test_load_executions_with_data(self, tmp_path):
        """Test loading executions from JSONL."""
        jsonl_path = tmp_path / "test.jsonl"

        # Create test data
        results = [
            WorkflowResult(
                success=True,
                run_id=f"test_{i:03d}",
                mode="daily",
                execution_time_seconds=100.0,
                wow_score=8.0 + i * 0.1,
            )
            for i in range(5)
        ]

        # Write to JSONL
        with open(jsonl_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

        # Load
        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))
        loaded = analyzer.load_executions()

        assert len(loaded) == 5
        assert loaded[0].run_id == "test_000"
        assert loaded[4].wow_score == 8.4

    def test_analyze_hook_performance(self, tmp_path):
        """Test hook performance analysis."""
        jsonl_path = tmp_path / "test.jsonl"

        # Create test data with different hooks
        results = [
            WorkflowResult(
                success=True,
                run_id="test_1",
                mode="daily",
                execution_time_seconds=100.0,
                hook_type="衝撃的事実",
                wow_score=8.5,
                retention_prediction=52.0,
            ),
            WorkflowResult(
                success=True,
                run_id="test_2",
                mode="daily",
                execution_time_seconds=100.0,
                hook_type="衝撃的事実",
                wow_score=8.7,
                retention_prediction=54.0,
            ),
            WorkflowResult(
                success=True,
                run_id="test_3",
                mode="daily",
                execution_time_seconds=100.0,
                hook_type="疑問提起",
                wow_score=8.0,
                retention_prediction=48.0,
            ),
        ]

        with open(jsonl_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))
        hook_perf = analyzer.analyze_hook_performance()

        # Check 衝撃的事実
        assert "衝撃的事実" in hook_perf
        assert hook_perf["衝撃的事実"]["count"] == 2
        assert hook_perf["衝撃的事実"]["avg_wow"] == 8.6  # (8.5 + 8.7) / 2
        assert hook_perf["衝撃的事実"]["avg_retention"] == 53.0  # (52 + 54) / 2

        # Check 疑問提起
        assert "疑問提起" in hook_perf
        assert hook_perf["疑問提起"]["count"] == 1
        assert hook_perf["疑問提起"]["avg_wow"] == 8.0

    def test_analyze_topic_distribution(self, tmp_path):
        """Test topic distribution analysis."""
        jsonl_path = tmp_path / "test.jsonl"

        results = [
            WorkflowResult(
                success=True,
                run_id="test_1",
                mode="daily",
                execution_time_seconds=100.0,
                topic="株式市場",
            ),
            WorkflowResult(
                success=True,
                run_id="test_2",
                mode="daily",
                execution_time_seconds=100.0,
                topic="株式市場",
            ),
            WorkflowResult(
                success=True,
                run_id="test_3",
                mode="daily",
                execution_time_seconds=100.0,
                topic="金融政策",
            ),
        ]

        with open(jsonl_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))
        topics = analyzer.analyze_topic_distribution()

        assert topics["株式市場"] == 2
        assert topics["金融政策"] == 1

    def test_get_best_performing_videos(self, tmp_path):
        """Test getting best performing videos by WOW score."""
        jsonl_path = tmp_path / "test.jsonl"

        results = [
            WorkflowResult(
                success=True,
                run_id="test_1",
                mode="daily",
                execution_time_seconds=100.0,
                title="Video 1",
                wow_score=7.5,
            ),
            WorkflowResult(
                success=True,
                run_id="test_2",
                mode="daily",
                execution_time_seconds=100.0,
                title="Video 2",
                wow_score=8.8,
            ),
            WorkflowResult(
                success=True,
                run_id="test_3",
                mode="daily",
                execution_time_seconds=100.0,
                title="Video 3",
                wow_score=8.2,
            ),
        ]

        with open(jsonl_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))
        best = analyzer.get_best_performing_videos(limit=2)

        assert len(best) == 2
        assert best[0].title == "Video 2"  # Highest WOW (8.8)
        assert best[1].title == "Video 3"  # Second highest (8.2)

    def test_calculate_success_rate(self, tmp_path):
        """Test success rate calculation."""
        jsonl_path = tmp_path / "test.jsonl"

        results = [
            WorkflowResult(
                success=True, run_id="test_1", mode="daily", execution_time_seconds=100.0
            ),
            WorkflowResult(
                success=True, run_id="test_2", mode="daily", execution_time_seconds=100.0
            ),
            WorkflowResult(
                success=False, run_id="test_3", mode="daily", execution_time_seconds=100.0
            ),
            WorkflowResult(
                success=True, run_id="test_4", mode="daily", execution_time_seconds=100.0
            ),
        ]

        with open(jsonl_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))
        success_rate = analyzer.calculate_success_rate()

        assert success_rate == 75.0  # 3 out of 4 successful

    def test_generate_weekly_report_no_data(self, tmp_path):
        """Test weekly report with no data."""
        jsonl_path = tmp_path / "empty.jsonl"
        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))

        report = analyzer.generate_weekly_report()
        assert "No execution data available" in report

    def test_generate_weekly_report_with_data(self, tmp_path):
        """Test weekly report generation."""
        jsonl_path = tmp_path / "test.jsonl"

        results = [
            WorkflowResult(
                success=True,
                run_id=f"test_{i}",
                mode="daily",
                execution_time_seconds=100.0,
                title=f"Video {i}",
                wow_score=8.0 + i * 0.1,
                hook_type="衝撃的事実",
            )
            for i in range(5)
        ]

        with open(jsonl_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

        analyzer = FeedbackAnalyzer(jsonl_path=str(jsonl_path))
        report = analyzer.generate_weekly_report()

        # Check report contains key sections
        assert "週次パフォーマンスレポート" in report
        assert "全体統計" in report
        assert "実行回数" in report
        assert "フック戦略パフォーマンス" in report
        assert "トップパフォーマンス動画" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
