"""Artifact domain objects and retention policies for workflow outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional


@dataclass(frozen=True)
class GeneratedArtifact:
    """Represents a file produced during workflow execution."""

    path: str
    persisted: bool = False
    kind: Optional[str] = None

    def to_payload(self) -> dict[str, object]:
        """Serialize artifact metadata for JSON-friendly payloads."""
        payload: dict[str, object] = {"path": self.path, "persisted": self.persisted}
        if self.kind:
            payload["kind"] = self.kind
        return payload


class ArtifactRetentionPolicy:
    """Determines whether generated artifacts should be deleted after execution."""

    def should_delete(self, artifact: GeneratedArtifact) -> bool:
        """Return True when the artifact is eligible for deletion."""
        return not artifact.persisted

    def iter_cleanup_targets(self, artifacts: Iterable[GeneratedArtifact]) -> Iterator[GeneratedArtifact]:
        """Yield artifacts that should be deleted according to the policy."""
        for artifact in artifacts:
            if self.should_delete(artifact):
                yield artifact

    def summarize(self, artifacts: Iterable[GeneratedArtifact]) -> dict[str, int]:
        """Provide simple metrics for logging/debugging."""
        stats = {"retained": 0, "deleted": 0}
        for artifact in artifacts:
            if self.should_delete(artifact):
                stats["deleted"] += 1
            else:
                stats["retained"] += 1
        return stats


class CompositeArtifactRetentionPolicy(ArtifactRetentionPolicy):
    """Combine multiple policies; deletion allowed only if all agree."""

    def __init__(self, *policies: ArtifactRetentionPolicy):
        self._policies: List[ArtifactRetentionPolicy] = list(policies) or [ArtifactRetentionPolicy()]

    def should_delete(self, artifact: GeneratedArtifact) -> bool:  # type: ignore[override]
        return all(policy.should_delete(artifact) for policy in self._policies)
