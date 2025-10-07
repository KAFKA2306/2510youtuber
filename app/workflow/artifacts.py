"""Workflow artifact utilities for retention-aware cleanup."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass
class GeneratedArtifact:
    """Description of a file produced during the workflow."""

    path: str
    persisted: bool = False
    description: str | None = None
    source_step: str | None = None

    def __post_init__(self) -> None:
        self.path = str(self.path)

    @property
    def name(self) -> str:
        """Return the basename of the artifact path."""

        return Path(self.path).name

    def as_dict(self) -> dict[str, object]:
        """Serialize the artifact metadata for logging or API responses."""

        return {
            "path": self.path,
            "persisted": self.persisted,
            "description": self.description,
            "source_step": self.source_step,
        }


class ArtifactRetentionPolicy:
    """Strategy interface for deciding which artifacts should be retained."""

    def should_retain(self, artifact: GeneratedArtifact) -> bool:  # pragma: no cover - interface default
        """Return True if the artifact must be preserved during cleanup."""

        raise NotImplementedError

    def select_for_deletion(self, artifacts: Iterable[GeneratedArtifact]) -> List[GeneratedArtifact]:
        """Return the subset of artifacts that should be removed."""

        return [artifact for artifact in artifacts if not self.should_retain(artifact)]


class DefaultArtifactRetentionPolicy(ArtifactRetentionPolicy):
    """Retain artifacts flagged as persisted and clean up everything else."""

    def should_retain(self, artifact: GeneratedArtifact) -> bool:
        return artifact.persisted


def normalize_artifacts(
    entries: Sequence[str | GeneratedArtifact] | None,
    *,
    source_step: str | None = None,
) -> List[GeneratedArtifact]:
    """Normalize raw file paths into :class:`GeneratedArtifact` instances."""

    artifacts: List[GeneratedArtifact] = []
    if not entries:
        return artifacts
    for entry in entries:
        if isinstance(entry, GeneratedArtifact):
            if source_step and entry.source_step is None:
                artifacts.append(replace(entry, source_step=source_step))
            else:
                artifacts.append(entry)
        else:
            artifacts.append(GeneratedArtifact(path=str(entry), source_step=source_step))
    return artifacts
