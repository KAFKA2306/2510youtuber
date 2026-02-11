"""動画レビュー用Pydanticモデル"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
class ScreenshotEvidence(BaseModel):
    """AIレビューに使用したスクリーンショットの情報"""
    index: int = Field(ge=0)
    path: str
    timestamp_seconds: float = Field(ge=0)
    @property
    def timestamp_label(self) -> str:
        """人間が読みやすい形式のタイムスタンプ"""
        minutes, seconds = divmod(int(self.timestamp_seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"
class VideoReviewFeedback(BaseModel):
    """AIが生成した動画レビューの内容"""
    summary: str
    positive_highlights: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    retention_risks: List[str] = Field(default_factory=list)
    next_video_actions: List[str] = Field(default_factory=list)
class VideoReviewResult(BaseModel):
    """動画レビューAIの出力結果"""
    video_path: str
    video_id: Optional[str] = None
    model_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    screenshots: List[ScreenshotEvidence] = Field(default_factory=list)
    feedback: Optional[VideoReviewFeedback] = None
    def to_dict(self) -> dict:
        """JSONシリアライズしやすい辞書形式に変換"""
        return {
            "video_path": self.video_path,
            "video_id": self.video_id,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat(),
            "screenshots": [shot.model_dump() for shot in self.screenshots],
            "feedback": self.feedback.model_dump() if self.feedback else None,
        }
