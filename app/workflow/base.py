"""Base classes for workflow steps.

Implements Strategy pattern for separating workflow logic into testable, composable steps.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    success: bool
    step_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    files_generated: List[str] = field(default_factory=list)

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

    def set(self, key: str, value: Any) -> None:
        """Store value in context."""
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from context."""
        return self.state.get(key, default)

    def add_files(self, files: List[str]) -> None:
        """Add generated files to tracking."""
        self.generated_files.extend(files)


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

    def _success(self, data: Dict[str, Any] = None, files: List[str] = None) -> StepResult:
        """Create a success result."""
        return StepResult(
            success=True,
            step_name=self.step_name,
            data=data or {},
            files_generated=files or [],
        )

    def _failure(self, error: str) -> StepResult:
        """Create a failure result."""
        return StepResult(
            success=False,
            step_name=self.step_name,
            error=error,
        )
