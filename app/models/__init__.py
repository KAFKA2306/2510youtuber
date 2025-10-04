"""データモデルモジュール

型安全性を確保するためのPydanticモデル群
"""

from app.services.script.validator import DialogueEntry, QualityScore, Script, ScriptSegment, WOWMetrics

from .news import NewsCollection, NewsItem
from .qa import CheckStatus, MediaCheckResult, QualityGateReport
from .video_review import ScreenshotEvidence, VideoReviewFeedback, VideoReviewResult
from .workflow import StepResult, WorkflowResult, WorkflowState

__all__ = [
    # News models
    "NewsItem",
    "NewsCollection",
    # Script models
    "Script",
    "DialogueEntry",
    "ScriptSegment",
    "QualityScore",
    "WOWMetrics",
    # Workflow models
    "WorkflowState",
    "StepResult",
    "WorkflowResult",
    # Video review models
    "ScreenshotEvidence",
    "VideoReviewFeedback",
    "VideoReviewResult",
    # QA models
    "CheckStatus",
    "MediaCheckResult",
    "QualityGateReport",
]
