"""ワークフロー関連のデータモデル"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """ステップの状態"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    """ワークフローステップの実行結果"""
    step_name: str = Field(..., description="ステップ名")
    status: StepStatus = Field(..., description="ステータス")
    success: bool = Field(..., description="成功フラグ")

    # 実行時間
    started_at: Optional[datetime] = Field(default=None, description="開始時刻")
    completed_at: Optional[datetime] = Field(default=None, description="完了時刻")

    # 結果データ
    data: Dict[str, Any] = Field(default_factory=dict, description="ステップの出力データ")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    error_traceback: Optional[str] = Field(default=None, description="エラートレースバック")

    # メタ情報
    files_generated: List[str] = Field(default_factory=list, description="生成されたファイル")
    warnings: List[str] = Field(default_factory=list, description="警告メッセージ")

    @property
    def execution_time_seconds(self) -> Optional[float]:
        """実行時間（秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    @property
    def is_success(self) -> bool:
        """成功したか"""
        return self.success and self.status == StepStatus.COMPLETED

    def add_warning(self, warning: str):
        """警告を追加"""
        self.warnings.append(warning)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowState(BaseModel):
    """ワークフロー全体の状態管理"""
    run_id: str = Field(..., description="実行ID")
    mode: str = Field(..., description="実行モード (daily/special/test)")

    # 状態
    current_step: Optional[str] = Field(default=None, description="現在のステップ")
    status: StepStatus = Field(default=StepStatus.PENDING, description="全体ステータス")

    # 実行時間
    started_at: datetime = Field(default_factory=datetime.now, description="開始時刻")
    completed_at: Optional[datetime] = Field(default=None, description="完了時刻")

    # ステップ結果
    step_results: Dict[str, StepResult] = Field(default_factory=dict, description="各ステップの結果")

    # 共有データ（ステップ間でデータを受け渡し）
    shared_data: Dict[str, Any] = Field(default_factory=dict, description="ステップ間共有データ")

    # ファイル管理
    generated_files: List[str] = Field(default_factory=list, description="生成された全ファイル")

    def start_step(self, step_name: str):
        """ステップを開始"""
        self.current_step = step_name
        self.step_results[step_name] = StepResult(
            step_name=step_name,
            status=StepStatus.IN_PROGRESS,
            success=False,
            started_at=datetime.now()
        )

    def complete_step(self, step_name: str, success: bool, data: Dict[str, Any] = None,
                     error: str = None, files: List[str] = None):
        """ステップを完了"""
        if step_name not in self.step_results:
            raise ValueError(f"Step {step_name} was not started")

        result = self.step_results[step_name]
        result.status = StepStatus.COMPLETED if success else StepStatus.FAILED
        result.success = success
        result.completed_at = datetime.now()

        if data:
            result.data = data
        if error:
            result.error = error
        if files:
            result.files_generated = files
            self.generated_files.extend(files)

        # 共有データに追加
        if success and data:
            self.shared_data[step_name] = data

    def fail_step(self, step_name: str, error: str, traceback: str = None):
        """ステップを失敗"""
        self.complete_step(step_name, success=False, error=error)
        if traceback and step_name in self.step_results:
            self.step_results[step_name].error_traceback = traceback

    def get_step_result(self, step_name: str) -> Optional[StepResult]:
        """特定ステップの結果を取得"""
        return self.step_results.get(step_name)

    def get_step_data(self, step_name: str) -> Optional[Dict[str, Any]]:
        """特定ステップのデータを取得"""
        return self.shared_data.get(step_name)

    @property
    def total_execution_time_seconds(self) -> Optional[float]:
        """総実行時間（秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    @property
    def successful_steps_count(self) -> int:
        """成功したステップ数"""
        return sum(1 for result in self.step_results.values() if result.is_success)

    @property
    def failed_steps_count(self) -> int:
        """失敗したステップ数"""
        return sum(1 for result in self.step_results.values()
                  if result.status == StepStatus.FAILED)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowResult(BaseModel):
    """ワークフロー全体の最終結果"""
    success: bool = Field(..., description="全体成功フラグ")
    run_id: str = Field(..., description="実行ID")
    mode: str = Field(..., description="実行モード")

    # 実行時間
    execution_time_seconds: float = Field(..., description="実行時間（秒）")

    # 結果データ
    news_count: int = Field(default=0, description="収集したニュース数")
    script_length: int = Field(default=0, description="台本文字数")
    video_path: Optional[str] = Field(default=None, description="動画ファイルパス")
    video_url: Optional[str] = Field(default=None, description="YouTube URL")
    video_id: Optional[str] = Field(default=None, description="YouTube動画ID")

    # 品質指標
    quality_score: Optional[float] = Field(default=None, description="品質スコア")
    wow_score: Optional[float] = Field(default=None, description="WOWスコア")

    # ステップサマリー
    completed_steps: int = Field(default=0, description="完了ステップ数")
    failed_steps: int = Field(default=0, description="失敗ステップ数")
    total_steps: int = Field(default=10, description="総ステップ数")

    # ファイル
    generated_files: List[str] = Field(default_factory=list, description="生成されたファイル")

    # エラー情報
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    failed_step: Optional[str] = Field(default=None, description="失敗したステップ")

    @property
    def success_rate(self) -> float:
        """成功率（%）"""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100.0

    @classmethod
    def from_workflow_state(cls, state: WorkflowState) -> 'WorkflowResult':
        """WorkflowStateから結果を生成"""
        return cls(
            success=state.status == StepStatus.COMPLETED,
            run_id=state.run_id,
            mode=state.mode,
            execution_time_seconds=state.total_execution_time_seconds or 0.0,
            completed_steps=state.successful_steps_count,
            failed_steps=state.failed_steps_count,
            total_steps=len(state.step_results),
            generated_files=state.generated_files,
        )
