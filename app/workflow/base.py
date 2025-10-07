"""Base classes for workflow steps.

Implements Strategy pattern for separating workflow logic into testable, composable steps.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .artifacts import (
    ArtifactRetentionPolicy,
    DefaultArtifactRetentionPolicy,
    GeneratedArtifact,
    ensure_artifacts,
)


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    success: bool
    step_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    files_generated: List[str | GeneratedArtifact] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """Get data value (compatibility with dict API)."""
        return self.data.get(key, default)


@dataclass
class WorkflowContext:
    """Shared context across workflow steps."""

    run_id: str
    mode: str
    state: Dict[str, Any] = field(default_factory=dict)
    generated_files: List[str] = field(default_factory=list)
    artifacts: List[GeneratedArtifact] = field(default_factory=list)
    retention_policy: ArtifactRetentionPolicy = field(default_factory=DefaultArtifactRetentionPolicy)

    def set(self, key: str, value: Any) -> None:
        """Store value in context."""
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from context."""
        return self.state.get(key, default)

    def add_files(self, files: Sequence[str | GeneratedArtifact]) -> None:
        """Add generated files to tracking."""

        for artifact in ensure_artifacts(files):
            self._register_artifact(artifact)

    def register_artifact(self, artifact: GeneratedArtifact) -> None:
        """Register a single artifact with the workflow context."""

        self._register_artifact(artifact)

    def _register_artifact(self, artifact: GeneratedArtifact) -> None:
        if artifact.path in self.generated_files:
            # Preserve insertion order but avoid duplicate bookkeeping entries.
            for existing in self.artifacts:
                if existing.path == artifact.path:
                    return
        self.generated_files.append(artifact.path)
        self.artifacts.append(artifact)


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
        return StepResult(
            success=True,
            step_name=self.step_name,
            data=data or {},
            files_generated=list(files) if files else [],
        )

    def _failure(self, error: str) -> StepResult:
        """Create a failure result."""
        return StepResult(
            success=False,
            step_name=self.step_name,
            error=error,
        )
