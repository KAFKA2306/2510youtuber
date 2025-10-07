from pathlib import Path

import pytest

from app.main import YouTubeWorkflow
from app.workflow.artifacts import DefaultArtifactRetentionPolicy, GeneratedArtifact
from app.workflow.base import WorkflowContext


@pytest.mark.unit
def test_default_policy_preserves_persisted_artifacts():
    policy = DefaultArtifactRetentionPolicy()
    ephemeral = GeneratedArtifact(path="/tmp/ephemeral.txt")
    persisted = GeneratedArtifact(path="/tmp/persisted.txt", persisted=True)

    cleanup_targets = policy.select_for_cleanup([ephemeral, persisted])

    assert cleanup_targets == [ephemeral]


@pytest.mark.unit
def test_cleanup_skips_persisted_files(tmp_path: Path):
    workflow = YouTubeWorkflow(notifier=None)
    context = WorkflowContext(run_id="run-123", mode="test")
    workflow.context = context

    ephemeral_path = tmp_path / "temp.txt"
    archived_path = tmp_path / "archived.txt"
    ephemeral_path.write_text("temp")
    archived_path.write_text("archive")

    context.add_files(
        [
            GeneratedArtifact(path=str(ephemeral_path)),
            GeneratedArtifact(path=str(archived_path), persisted=True),
        ]
    )

    workflow._cleanup_temp_files()

    assert not ephemeral_path.exists()
    assert archived_path.exists()
