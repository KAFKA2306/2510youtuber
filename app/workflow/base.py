"""Base classes for workflow steps and shared workflow context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .artifacts import GeneratedArtifact


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    success: bool
    step_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    artifacts: List[GeneratedArtifact] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """Get data value (compatibility with dict API)."""
        return self.data.get(key, default)

    @property
    def files_generated(self) -> List[str]:
        """Compatibility accessor returning artifact paths."""
        return [artifact.path for artifact in self.artifacts]


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

    @property
    def generated_files(self) -> List[str]:
        """Return the paths for all tracked artifacts."""
        return [artifact.path for artifact in self.artifacts]

    def add_artifacts(self, artifacts: Iterable[GeneratedArtifact]) -> None:
        """Track workflow artifacts with retention metadata."""
        self.artifacts.extend(list(artifacts))

    def add_files(self, files: Iterable[str], *, persisted: bool = False, kind: str | None = None) -> None:
        """Backwards-compatible helper to add plain file paths."""
        generated = [GeneratedArtifact(path=file_path, persisted=persisted, kind=kind) for file_path in files]
        self.add_artifacts(generated)


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
        files: Iterable[str] | None = None,
        artifacts: Iterable[GeneratedArtifact] | None = None,
    ) -> StepResult:
        """Create a success result."""
        collected: List[GeneratedArtifact] = []
        if files:
            collected.extend(GeneratedArtifact(path=file_path) for file_path in files)
        if artifacts:
            collected.extend(list(artifacts))
        return StepResult(
            success=True,
            step_name=self.step_name,
            data=data or {},
            artifacts=collected,
        )

    def _failure(self, error: str) -> StepResult:
        """Create a failure result."""
        return StepResult(
            success=False,
            step_name=self.step_name,
            error=error,
        )
