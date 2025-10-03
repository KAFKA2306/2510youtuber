"""台本関連のデータモデル"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ScriptSegment(BaseModel):
    """台本セグメント

    個別の発話単位を表すモデル
    """

    speaker: str = Field(..., description="話者名（田中/鈴木/ナレーター）")
    text: str = Field(..., min_length=1, description="発話テキスト")
    timestamp_start: Optional[float] = Field(default=None, description="開始時刻（秒）")
    timestamp_end: Optional[float] = Field(default=None, description="終了時刻（秒）")
    visual_instruction: Optional[str] = Field(default=None, description="視覚指示")
    emotion_tag: Optional[str] = Field(default=None, description="感情タグ")

    @validator("speaker")
    def validate_speaker(cls, v):
        """話者名の検証"""
        allowed = ["田中", "鈴木", "ナレーター"]
        if v not in allowed:
            raise ValueError(f"speaker must be one of {allowed}")
        return v

    @property
    def duration(self) -> Optional[float]:
        """発話時間（秒）"""
        if self.timestamp_start is not None and self.timestamp_end is not None:
            return self.timestamp_end - self.timestamp_start
        return None

    @property
    def char_count(self) -> int:
        """文字数"""
        return len(self.text)

    def to_dialogue_line(self) -> str:
        """対談形式の1行に変換"""
        line = f"{self.speaker}: {self.text}"
        if self.visual_instruction:
            line += f"\n({self.visual_instruction})"
        return line


class WOWMetrics(BaseModel):
    """WOW要素の指標

    台本の驚き・感動・エンゲージメント要素を数値化
    """

    surprise_points_count: int = Field(default=0, ge=0, description="驚きポイント数")
    emotion_peaks_count: int = Field(default=0, ge=0, description="感情ピーク数")
    curiosity_gaps_count: int = Field(default=0, ge=0, description="好奇心ギャップ数")
    visual_instructions_count: int = Field(default=0, ge=0, description="視覚指示数")
    concrete_numbers_count: int = Field(default=0, ge=0, description="具体的数値数")
    viewer_questions_count: int = Field(default=0, ge=0, description="視聴者への質問数")

    @property
    def total_wow_elements(self) -> int:
        """WOW要素の合計数"""
        return (
            self.surprise_points_count
            + self.emotion_peaks_count
            + self.curiosity_gaps_count
            + self.visual_instructions_count
            + self.concrete_numbers_count
            + self.viewer_questions_count
        )

    @property
    def is_wow_rich(self) -> bool:
        """WOW要素が豊富か（基準: 合計20以上）"""
        return self.total_wow_elements >= 20


class QualityScore(BaseModel):
    """品質スコア

    台本の品質を多次元で評価
    """

    wow_score: float = Field(..., ge=0.0, le=10.0, description="総合WOWスコア")
    surprise_score: float = Field(..., ge=0.0, le=10.0, description="驚き度")
    emotion_score: float = Field(..., ge=0.0, le=10.0, description="感動度")
    clarity_score: float = Field(..., ge=0.0, le=10.0, description="明瞭度")
    retention_prediction: float = Field(..., ge=0.0, le=100.0, description="保持率予測（%）")
    japanese_purity: float = Field(..., ge=0.0, le=100.0, description="日本語純度（%）")
    evidence_score: float = Field(default=0.0, ge=0.0, le=10.0, description="データ裏付け度")
    action_score: float = Field(default=0.0, ge=0.0, le=10.0, description="行動喚起度")

    # WOW要素の詳細
    wow_metrics: Optional[WOWMetrics] = Field(default=None, description="WOW要素の詳細指標")

    @property
    def average_score(self) -> float:
        """平均スコア（8軸）"""
        scores = [
            self.wow_score,
            self.surprise_score,
            self.emotion_score,
            self.clarity_score,
            self.retention_prediction / 10.0,  # 0-100 を 0-10 に正規化
            self.japanese_purity / 10.0,  # 0-100 を 0-10 に正規化
            self.evidence_score,
            self.action_score,
        ]
        return sum(scores) / len(scores)

    def is_passing(self, wow_threshold: float = 8.0, purity_threshold: float = 95.0) -> bool:
        """合格基準を満たしているか"""
        return self.wow_score >= wow_threshold and self.japanese_purity >= purity_threshold

    @property
    def is_excellent(self) -> bool:
        """優秀な品質か（WOW 9.0+, 日本語純度 98.0+）"""
        return self.wow_score >= 9.0 and self.japanese_purity >= 98.0

    def to_report(self) -> str:
        """品質レポート文字列生成"""
        return f"""
品質評価レポート
================
総合WOWスコア: {self.wow_score:.1f}/10.0
驚き度: {self.surprise_score:.1f}/10.0
感動度: {self.emotion_score:.1f}/10.0
明瞭度: {self.clarity_score:.1f}/10.0
保持率予測: {self.retention_prediction:.1f}%
日本語純度: {self.japanese_purity:.1f}%
データ裏付け: {self.evidence_score:.1f}/10.0
行動喚起: {self.action_score:.1f}/10.0
平均スコア: {self.average_score:.1f}/10.0

判定: {'✅ 合格' if self.is_passing() else '❌ 不合格'}
        """.strip()


class Script(BaseModel):
    """台本

    完全な動画台本を表すモデル
    """

    segments: List[ScriptSegment] = Field(..., min_items=1, description="台本セグメント")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="メタデータ")
    quality_score: Optional[QualityScore] = Field(default=None, description="品質スコア")
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")

    # CrewAI処理の履歴
    processing_history: List[Dict[str, Any]] = Field(default_factory=list, description="処理履歴")
    iterations_count: int = Field(default=0, ge=0, description="改善反復回数")

    @property
    def total_char_count(self) -> int:
        """総文字数"""
        return sum(seg.char_count for seg in self.segments)

    @property
    def estimated_duration_minutes(self) -> float:
        """推定動画長（分） - 300文字/分換算"""
        return self.total_char_count / 300.0

    @property
    def speaker_distribution(self) -> Dict[str, int]:
        """話者ごとの発話回数"""
        distribution = {}
        for seg in self.segments:
            distribution[seg.speaker] = distribution.get(seg.speaker, 0) + 1
        return distribution

    def to_text(self) -> str:
        """対談形式テキストに変換"""
        lines = []
        for seg in self.segments:
            lines.append(seg.to_dialogue_line())
        return "\n\n".join(lines)

    def get_segments_by_speaker(self, speaker: str) -> List[ScriptSegment]:
        """特定の話者のセグメントのみ取得"""
        return [seg for seg in self.segments if seg.speaker == speaker]

    def count_visual_instructions(self) -> int:
        """視覚指示の数をカウント"""
        return sum(1 for seg in self.segments if seg.visual_instruction)

    def add_processing_step(self, step_name: str, details: Dict[str, Any]):
        """処理ステップを履歴に追加"""
        self.processing_history.append({"step": step_name, "timestamp": datetime.now().isoformat(), "details": details})

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
