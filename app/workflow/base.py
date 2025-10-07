"""Base classes for workflow steps.

Implements Strategy pattern for separating workflow logic into testable, composable steps.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .artifacts import GeneratedArtifact, normalize_artifacts


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    success: bool
    step_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    files_generated: List[GeneratedArtifact] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """Get data value (compatibility with dict API)."""
        return self.data.get(key, default)


@dataclass
class WorkflowContext:
    """Shared context across workflow steps."""

    run_id: str
    mode: str
    state: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[GeneratedArtifact] = field(default_factory=list)

    def set(self, key: str, value: Any) -> None:
        """Store value in context."""
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from context."""
        return self.state.get(key, default)

    def add_files(self, files: Sequence[str | GeneratedArtifact]) -> None:
        """Record generated files for later cleanup and reporting."""

        self.artifacts.extend(normalize_artifacts(files))

    def add_artifacts(self, artifacts: Sequence[GeneratedArtifact]) -> None:
        """Explicitly add normalized artifacts to the context."""

        self.artifacts.extend(artifacts)

    def mark_artifact_persisted(self, path: str) -> None:
        """Mark an existing artifact as persisted if it's already tracked."""

        normalized = str(path)
        for index, artifact in enumerate(self.artifacts):
            if artifact.path == normalized and not artifact.persisted:
                self.artifacts[index] = replace(artifact, persisted=True)

    @property
    def generated_files(self) -> List[str]:
        """Return all tracked artifact paths."""

        return [artifact.path for artifact in self.artifacts]

    def list_artifact_paths(self, *, persisted_only: bool = False) -> List[str]:
        """Return artifact paths, optionally filtering to retained entries."""

        artifacts = self.artifacts
        if persisted_only:
            artifacts = [artifact for artifact in artifacts if artifact.persisted]
        return [artifact.path for artifact in artifacts]

    def iter_artifacts(self) -> Iterable[GeneratedArtifact]:
        """Iterate over tracked artifacts."""

        return list(self.artifacts)


class WorkflowStep(ABC):
    """Abstract base class for workflow steps.

    Each step is responsible for:
    1. Executing a specific part of the workflow
    2. Updating the shared context with results
    3. Returning a StepResult indicating success/failure
    """

    @property
    @abstractmethod
    def step_name(self) -> str:
        """Human-readable step name."""
        pass

    @abstractmethod
    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the workflow step.

        Args:
            context: Shared workflow context

        Returns:
            StepResult with success status and output data
        """
        pass

    def _success(
        self,
        data: Dict[str, Any] = None,
        files: Sequence[str | GeneratedArtifact] | None = None,
    ) -> StepResult:
        """Create a success result."""
        normalized = normalize_artifacts(files, source_step=self.step_name)
        return StepResult(
            success=True,
            step_name=self.step_name,
            data=data or {},
            files_generated=normalized,
        )

    def _failure(self, error: str) -> StepResult:
        """Create a failure result."""
        return StepResult(
            success=False,
            step_name=self.step_name,
            error=error,
        )
