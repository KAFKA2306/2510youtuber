"""Runtime helpers for orchestrating the Crew-based workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .workflow import WorkflowContext, WorkflowStep


@dataclass
class ScriptInsights:
    """Container object for metrics extracted from the script generation step."""

    wow_score: Optional[float] = None
    surprise_points: Optional[int] = None
    emotion_peaks: Optional[int] = None
    visual_instructions: Optional[int] = None
    retention_prediction: Optional[float] = None
    japanese_purity: Optional[float] = None
    hook_variant: Optional[str] = None
    title_variants: List[str] = field(default_factory=list)
    thumbnail_prompts: List[str] = field(default_factory=list)
    emotion_curve: Optional[List[Dict[str, Any]]] = None
    visual_calls_to_action: Optional[List[str]] = None
    visual_b_roll_suggestions: Optional[List[str]] = None
    emotion_highlights: Optional[List[str]] = None
    visual_guidelines: Optional[List[str]] = None
    visual_shot_list: Optional[List[str]] = None

    @classmethod
    def from_step(cls, script_step: Any) -> "ScriptInsights":
        if not script_step or not hasattr(script_step, "data"):
            return cls()

        data = script_step.data or {}
        metrics = data.get("script_metrics", {}) or {}

        def _as_list(value: Any) -> List[str]:
            if isinstance(value, list):
                return [str(item) for item in value if item is not None]
            if value:
                return [str(value)]
            return []

        return cls(
            wow_score=metrics.get("wow_score"),
            surprise_points=metrics.get("surprise_points"),
            emotion_peaks=metrics.get("emotion_peaks"),
            visual_instructions=metrics.get("visual_instructions"),
            retention_prediction=metrics.get("retention_prediction"),
            japanese_purity=data.get("japanese_purity_score")
            or metrics.get("japanese_purity"),
            hook_variant=data.get("hook_variant"),
            title_variants=_as_list(data.get("title_variants")),
            thumbnail_prompts=_as_list(data.get("thumbnail_prompts")),
            emotion_curve=metrics.get("emotion_curve")
            if isinstance(metrics.get("emotion_curve"), list)
            else None,
            visual_calls_to_action=_as_list(metrics.get("visual_calls_to_action"))
            or None,
            visual_b_roll_suggestions=_as_list(metrics.get("visual_b_roll_suggestions"))
            or None,
            emotion_highlights=_as_list(metrics.get("emotion_highlights")) or None,
            visual_guidelines=_as_list(data.get("visual_guidelines")) or None,
            visual_shot_list=_as_list(data.get("visual_shot_list")) or None,
        )


class AttemptStatus(Enum):
    """Possible outcomes for a single workflow attempt."""

    SUCCESS = "success"
    RETRY = "retry"
    FAILURE = "failure"


@dataclass
class AttemptOutcome:
    """High-level summary describing how an attempt finished."""

    status: AttemptStatus
    restart_index: Optional[int] = None
    reason: Optional[str] = None
    failure_step: Optional[str] = None
    failure_result: Optional[Any] = None


@dataclass
class WorkflowRunState:
    """State tracker for a single workflow execution attempt."""

    run_id: str
    mode: str
    context: WorkflowContext
    steps: Sequence[WorkflowStep]
    retry_cleanup_map: Dict[str, Iterable[str]]
    start_time: datetime = field(default_factory=datetime.now)
    attempt: int = 0
    start_index: int = 0
    results: List[Optional[Any]] = field(init=False)
    retry_requested: bool = False

    def __post_init__(self) -> None:
        self.results = [None] * len(self.steps)

    def begin_attempt(self, attempt_number: int) -> None:
        """Record the current attempt number and reset retry flags."""

        self.attempt = attempt_number
        self.retry_requested = False

    def register_result(self, index: int, result: Any) -> None:
        """Store the result for a step and capture any generated files."""

        self.results[index] = result
        files = getattr(result, "files_generated", None)
        if files:
            self.context.add_files(files)

    def request_retry(self, start_index: int) -> None:
        """Prepare to rerun from a specific step on the next attempt."""

        self.retry_requested = True
        self.start_index = start_index
        self._clear_state_from(start_index)

    def _clear_state_from(self, start_index: int) -> None:
        """Drop cached step outputs and context keys beyond the restart point."""

        for idx in range(start_index, len(self.results)):
            self.results[idx] = None
        for step in self.steps[start_index:]:
            keys_to_remove = self.retry_cleanup_map.get(step.step_name, [])
            for key in keys_to_remove:
                if key in self.context.state:
                    self.context.state.pop(key, None)

    def completed_results(self) -> List[Any]:
        """Return all step results recorded so far."""

        return [result for result in self.results if result is not None]

    def execution_time_seconds(self) -> float:
        """Compute the total runtime in seconds since the state was created."""

        return (datetime.now() - self.start_time).total_seconds()
