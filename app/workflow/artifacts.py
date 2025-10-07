"""Workflow artifact modeling and retention policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class GeneratedArtifact:
    """Represents a file produced by the workflow."""

    path: str
    persisted: bool = False
    cleanup: bool = True
    kind: str | None = None
    description: str | None = None

    @classmethod
    def from_path(cls, path: str, *, persisted: bool = False, cleanup: bool = True, **kwargs: object) -> "GeneratedArtifact":
        """Convenience constructor that mirrors the dataclass signature."""

        return cls(path=path, persisted=persisted, cleanup=cleanup, **kwargs)

    @property
    def should_cleanup(self) -> bool:
        """Return True when the artifact is eligible for deletion."""

        return self.cleanup and not self.persisted


class ArtifactRetentionPolicy:
    """Strategy for selecting which artifacts should be removed."""

    def select_for_cleanup(self, artifacts: Sequence[GeneratedArtifact]) -> List[GeneratedArtifact]:
        """Return artifacts that should be deleted."""

        raise NotImplementedError


class DefaultArtifactRetentionPolicy(ArtifactRetentionPolicy):
    """Retention strategy that preserves persisted artifacts."""

    def select_for_cleanup(self, artifacts: Sequence[GeneratedArtifact]) -> List[GeneratedArtifact]:
        return [artifact for artifact in artifacts if artifact.should_cleanup]


def ensure_artifact(item: str | GeneratedArtifact) -> GeneratedArtifact:
    """Normalize raw file specs into :class:`GeneratedArtifact` objects."""

    if isinstance(item, GeneratedArtifact):
        return item
    return GeneratedArtifact(path=item)


def ensure_artifacts(items: Iterable[str | GeneratedArtifact]) -> List[GeneratedArtifact]:
    """Normalize an iterable of artifact specs."""

    return [ensure_artifact(item) for item in items]
