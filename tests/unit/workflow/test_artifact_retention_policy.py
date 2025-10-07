import pytest

from app.main import YouTubeWorkflow
from app.workflow import ArtifactRetentionPolicy, GeneratedArtifact, WorkflowContext


class _StubNotifier:
    async def notify(self, *args, **kwargs):  # pragma: no cover - behaviour verified via workflow
        return None


def test_artifact_retention_policy_respects_persisted_flag():
    policy = ArtifactRetentionPolicy()
    transient = GeneratedArtifact(path="/tmp/transient", persisted=False)
    persisted = GeneratedArtifact(path="/tmp/persisted", persisted=True)

    assert policy.should_delete(transient) is True
    assert policy.should_delete(persisted) is False


def test_workflow_context_tracks_artifacts_with_persistence():
    context = WorkflowContext(run_id="run-1", mode="daily")

    context.add_files(["/tmp/a", "/tmp/b"])
    context.add_files(["/tmp/archive"], persisted=True, kind="archive/video")

    assert len(context.artifacts) == 3
    persisted_flags = {artifact.path: artifact.persisted for artifact in context.artifacts}
    assert persisted_flags["/tmp/archive"] is True
    assert set(context.generated_files) == {"/tmp/a", "/tmp/b", "/tmp/archive"}


@pytest.mark.asyncio
async def test_cleanup_skips_persisted_artifacts(tmp_path):
    workflow = YouTubeWorkflow(notifier=_StubNotifier())
    workflow._log_session = None  # type: ignore[assignment]

    ephemeral = tmp_path / "ephemeral.txt"
    ephemeral.write_text("tmp")
    persisted = tmp_path / "persisted.txt"
    persisted.write_text("keep")

    workflow.context = WorkflowContext(run_id="run-42", mode="daily")
    workflow.context.add_artifacts(
        [
            GeneratedArtifact(path=str(ephemeral), persisted=False),
            GeneratedArtifact(path=str(persisted), persisted=True),
        ]
    )

    workflow._cleanup_temp_files()

    assert ephemeral.exists() is False
    assert persisted.exists() is True
