"""ニュース関連のデータモデル"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class NewsItem(BaseModel):
    """ニュース項目

    個別のニュース記事を表すモデル
    """
    title: str = Field(..., min_length=1, max_length=200, description="ニュースタイトル")
    url: str = Field(..., description="ニュースURL")
    summary: str = Field(..., min_length=50, max_length=1000, description="要約")
    key_points: List[str] = Field(default_factory=list, max_items=10, description="重要ポイント")
    source: str = Field(..., min_length=1, description="情報源")
    impact_level: str = Field(default="medium", description="影響度 (high/medium/low)")
    category: str = Field(default="経済", description="カテゴリ")
    collected_at: datetime = Field(default_factory=datetime.now, description="収集日時")

    # WOW要素（CrewAIで追加される）
    surprise_points: Optional[List[str]] = Field(default=None, description="驚きポイント")
    viewer_relevance: Optional[str] = Field(default=None, description="視聴者との関連性")
    hidden_factors: Optional[List[str]] = Field(default=None, description="隠れた要因")

    @validator("impact_level")
    def validate_impact_level(cls, v):
        """影響度の検証"""
        allowed = ["high", "medium", "low"]
        if v not in allowed:
            raise ValueError(f"impact_level must be one of {allowed}")
        return v

    @validator("summary")
    def validate_summary_length(cls, v):
        """要約の長さ検証"""
        if len(v) < 50:
            raise ValueError("Summary must be at least 50 characters")
        return v

    @property
    def is_high_impact(self) -> bool:
        """高影響度かどうか"""
        return self.impact_level == "high"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NewsCollection(BaseModel):
    """ニュースコレクション

    複数のニュース項目をまとめて管理
    """
    items: List[NewsItem] = Field(..., min_items=1, max_items=10, description="ニュース項目リスト")
    mode: str = Field(..., description="実行モード (daily/special/test)")
    collected_at: datetime = Field(default_factory=datetime.now, description="収集日時")
    total_count: Optional[int] = Field(default=None, description="総件数")

    def __init__(self, **data):
        super().__init__(**data)
        if self.total_count is None:
            self.total_count = len(self.items)

    @validator("mode")
    def validate_mode(cls, v):
        """モードの検証"""
        allowed = ["daily", "special", "test"]
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        return v

    @property
    def high_impact_items(self) -> List[NewsItem]:
        """高影響度のニュース項目のみ取得"""
        return [item for item in self.items if item.is_high_impact]

    @property
    def has_high_impact(self) -> bool:
        """高影響度のニュースが含まれているか"""
        return len(self.high_impact_items) > 0

    def get_by_category(self, category: str) -> List[NewsItem]:
        """カテゴリでフィルタリング"""
        return [item for item in self.items if item.category == category]

    def to_summary_dict(self) -> dict:
        """要約辞書に変換（既存コードとの互換性用）"""
        return {
            "mode": self.mode,
            "count": self.total_count,
            "items": [
                {
                    "title": item.title,
                    "url": item.url,
                    "summary": item.summary,
                    "key_points": item.key_points,
                    "source": item.source,
                    "impact_level": item.impact_level,
                    "category": item.category,
                }
                for item in self.items
            ]
        }

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
