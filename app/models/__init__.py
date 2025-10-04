"""データモデルモジュール

型安全性を確保するためのPydanticモデル群
"""

from .news import NewsCollection, NewsItem
from .qa import CheckStatus, MediaCheckResult, QualityGateReport
from app.services.script.validator import QualityScore, Script, ScriptSegment, WOWMetrics
from .video_review import ScreenshotEvidence, VideoReviewFeedback, VideoReviewResult
from .workflow import StepResult, WorkflowResult, WorkflowState

__all__ = [
    # News models
    "NewsItem",
    "NewsCollection",
    # Script models
    "Script",
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
