"""データモデルモジュール
型安全性を確保するためのPydanticモデル群
"""
from app.services.script.validator import DialogueEntry, QualityScore, Script, ScriptSegment, WOWMetrics
from .news import NewsCollection, NewsItem
from .qa import CheckStatus, MediaCheckResult, QualityGateReport
from .video_review import ScreenshotEvidence, VideoReviewFeedback, VideoReviewResult
from .workflow import StepResult, WorkflowResult, WorkflowState
__all__ = [
    "NewsItem",
    "NewsCollection",
    "Script",
    "DialogueEntry",
    "ScriptSegment",
    "QualityScore",
    "WOWMetrics",
    "WorkflowState",
    "StepResult",
    "WorkflowResult",
    "ScreenshotEvidence",
    "VideoReviewFeedback",
    "VideoReviewResult",
    "CheckStatus",
    "MediaCheckResult",
    "QualityGateReport",
]
