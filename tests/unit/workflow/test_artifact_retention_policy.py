import pytest

from app.main import YouTubeWorkflow
from app.workflow import DefaultArtifactRetentionPolicy, GeneratedArtifact, WorkflowContext


@pytest.mark.unit
def test_cleanup_removes_only_ephemeral_artifacts(tmp_path):
    workflow = YouTubeWorkflow(artifact_policy=DefaultArtifactRetentionPolicy())
    context = WorkflowContext(run_id="run", mode="test")
    temp_file = tmp_path / "temp.txt"
    temp_file.write_text("ephemeral")
    persisted_file = tmp_path / "keep.txt"
    persisted_file.write_text("persisted")

    context.add_files([str(temp_file)])
    context.add_artifacts([GeneratedArtifact(path=str(persisted_file), persisted=True, description="archived")])
    workflow.context = context

    workflow._cleanup_temp_files()

    assert not temp_file.exists()
    assert persisted_file.exists()
    assert context.generated_files == [str(persisted_file)]


@pytest.mark.unit
def test_mark_persisted_prevents_deletion(tmp_path):
    workflow = YouTubeWorkflow(artifact_policy=DefaultArtifactRetentionPolicy())
    context = WorkflowContext(run_id="run", mode="test")
    retained_file = tmp_path / "retained.mp4"
    retained_file.write_text("video")

    context.add_files([str(retained_file)])
    context.mark_artifact_persisted(str(retained_file))
    workflow.context = context

    workflow._cleanup_temp_files()

    assert retained_file.exists()
    assert context.generated_files == [str(retained_file)]
