"""メインワークフローモジュール (Refactored with Strategy Pattern)

YouTube動画自動生成の全工程を統合・実行します。
WorkflowStepパターンにより、各ステップが独立してテスト可能になりました。
"""

import asyncio
import logging
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from .api_rotation import initialize_api_infrastructure
from .config import cfg
from .discord import discord_notifier
from .metadata_storage import metadata_storage
from .models.workflow import WorkflowResult
from .sheets import sheets_manager
from .workflow import (
    AlignSubtitlesStep,
    CollectNewsStep,
    GenerateMetadataStep,
    GenerateScriptStep,
    GenerateThumbnailStep,
    GenerateVideoStep,
    GenerateVisualDesignStep,
    QualityAssuranceStep,
    SynthesizeAudioStep,
    TranscribeAudioStep,
    UploadToDriveStep,
    UploadToYouTubeStep,
    ReviewVideoStep,
    WorkflowContext,
    WorkflowStep,
)

logger = logging.getLogger(__name__)

# Initialize API infrastructure once at module import
try:
    initialize_api_infrastructure()
    logger.info("API infrastructure initialized at startup")
except Exception as e:
    logger.warning(f"Failed to initialize API infrastructure: {e}")


class YouTubeWorkflow:
    """YouTube動画自動生成ワークフロー (Strategy Pattern)

    各ステップはWorkflowStepインターフェースを実装した独立したクラスとして定義され、
    このクラスはオーケストレーションのみを担当します。
    """

    RETRY_CLEANUP_MAP = {
        "script_generation": {"script_content", "script_path"},
        "visual_design_generation": {"visual_design", "visual_design_dict"},
        "metadata_generation": {"metadata"},
        "thumbnail_generation": {"thumbnail_path"},
        "audio_synthesis": {"audio_path"},
        "audio_transcription": {"stt_words"},
        "subtitle_alignment": {"subtitle_path", "aligned_subtitles"},
        "video_generation": {"video_path", "archived_audio_path", "archived_subtitle_path"},
        "media_quality_assurance": {"qa_report", "qa_report_path", "qa_passed", "qa_retry_request"},
        "drive_upload": {"drive_result"},
        "youtube_upload": {"youtube_result", "video_id", "video_url"},
    }

    def __init__(self):
        self.run_id = None
        self.mode = "daily"
        self.context: Optional[WorkflowContext] = None

        # Define workflow steps (dependency injection ready)
        # NOTE: 視覚デザイン生成→サムネイル/メタデータ→動画生成の順序で視覚的統一性を確保
        self.steps: List[WorkflowStep] = [
            CollectNewsStep(),           # Step 1: ニュース収集
            GenerateScriptStep(),        # Step 2: 台本生成
            GenerateVisualDesignStep(),  # Step 2.5: 統一ビジュアルデザイン生成 (NEW)
            GenerateMetadataStep(),      # Step 3: メタデータ生成
            GenerateThumbnailStep(),     # Step 4: サムネイル生成
            SynthesizeAudioStep(),       # Step 5: 音声合成
            TranscribeAudioStep(),       # Step 6: 音声認識
            AlignSubtitlesStep(),        # Step 7: 字幕整合
            GenerateVideoStep(),         # Step 8: 動画生成 (統一デザインを使用)
            QualityAssuranceStep(),      # Step 8.5: 自動QAゲート
            UploadToDriveStep(),         # Step 9: Drive アップロード
            UploadToYouTubeStep(),       # Step 10: YouTube アップロード
            ReviewVideoStep(),           # Step 11: AIレビューで改善ログ生成
        ]

    async def execute_full_workflow(self, mode: str = "daily") -> Dict[str, Any]:
        """完全なワークフローを実行

        Args:
            mode: 実行モード (daily/special/test)

        Returns:
            実行結果の辞書
        """
        start_time = datetime.now()

        try:
            self.mode = mode
            self.run_id = self._initialize_run(mode)
            self.context = WorkflowContext(run_id=self.run_id, mode=mode)

            await self._notify_workflow_start(mode)

            qa_gating = getattr(getattr(cfg, "media_quality", None), "gating", None)
            max_attempts = 1 + max(0, getattr(qa_gating, "retry_attempts", 0))
            start_index = 0
            step_results: List[Optional[Any]] = [None] * len(self.steps)

            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                logger.info(f"🚀 Workflow attempt {attempt}/{max_attempts}")

                retry_triggered = False

                for index in range(start_index, len(self.steps)):
                    step = self.steps[index]
                    logger.info(f"Executing: {step.step_name}")
                    result = await step.execute(self.context)
                    step_results[index] = result

                    if result.files_generated:
                        self.context.add_files(result.files_generated)

                    if not result.success:
                        if isinstance(step, QualityAssuranceStep):
                            retry_request = self.context.get("qa_retry_request")
                            if retry_request and attempt < max_attempts:
                                retry_step_name = retry_request.get("start_step")
                                retry_index = self._resolve_step_index(retry_step_name)
                                if retry_index is None:
                                    logger.error(
                                        "QA retry requested an unknown step '%s'",
                                        retry_step_name,
                                    )
                                    return await self._handle_workflow_failure(step.step_name, result)

                                reason = retry_request.get("reason")
                                if reason:
                                    logger.warning(reason)

                                logger.warning(
                                    "Retrying workflow from step '%s' (attempt %s/%s)",
                                    self.steps[retry_index].step_name,
                                    attempt + 1,
                                    max_attempts,
                                )

                                self._prepare_context_for_retry(retry_index)
                                self._clear_step_results(step_results, retry_index)
                                start_index = retry_index
                                retry_triggered = True
                                break

                        logger.error(f"Step {step.step_name} failed on attempt {attempt}")
                        return await self._handle_workflow_failure(step.step_name, result)

                if retry_triggered:
                    continue

                final_results = [res for res in step_results if res is not None]

                video_url = self.context.get("video_url")
                if video_url:
                    try:
                        metadata_storage.update_video_stats(run_id=self.run_id, video_url=video_url)
                        logger.info("Updated metadata storage with video URL")
                    except Exception as e:
                        logger.warning(f"Failed to update video URL in storage: {e}")

                execution_time = (datetime.now() - start_time).total_seconds()
                result = self._compile_final_result(final_results, execution_time)

                await self._notify_workflow_success(result)
                self._update_run_status("completed", result)

                return result

            logger.error("Workflow failed after exhausting QA retries")
            failure_index = max(start_index, 0)
            failure_step = self.steps[failure_index].step_name if failure_index < len(self.steps) else "unknown"
            failure_result = step_results[failure_index] if failure_index < len(step_results) else None
            return await self._handle_workflow_failure(failure_step, failure_result)

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_result = {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time,
                "run_id": self.run_id,
            }
            await self._notify_workflow_error(e)
            self._update_run_status("failed", error_result)
            return error_result
        finally:
            self._cleanup_temp_files()

    def _resolve_step_index(self, step_name: Optional[str]) -> Optional[int]:
        """Given a step name, return its index within the workflow."""
        if not step_name:
            return None
        for idx, step in enumerate(self.steps):
            if step.step_name == step_name:
                return idx
        return None

    def _prepare_context_for_retry(self, start_index: int) -> None:
        """Remove context state produced by steps at or after start_index."""
        if not self.context:
            return

        keys_to_remove = set()
        for step in self.steps[start_index:]:
            keys_to_remove.update(self.RETRY_CLEANUP_MAP.get(step.step_name, set()))

        for key in keys_to_remove:
            if key in self.context.state:
                self.context.state.pop(key, None)

    def _clear_step_results(self, step_results: List[Optional[Any]], start_index: int) -> None:
        """Clear cached StepResult objects for retry region."""
        for idx in range(start_index, len(step_results)):
            step_results[idx] = None

    def _initialize_run(self, mode: str) -> str:
        """ワークフロー実行IDを初期化"""
        try:
            if sheets_manager:
                run_id = sheets_manager.create_run(mode)
                logger.info(f"Initialized workflow run: {run_id}")
                return run_id
            else:
                run_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                logger.warning(f"Sheets not available, using local run ID: {run_id}")
                return run_id
        except Exception as e:
            logger.error(f"Failed to initialize run: {e}")
            return f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def _handle_workflow_failure(self, step_name: str, result: Any) -> Dict[str, Any]:
        """ステップ失敗時の処理"""
        error_message = f"{step_name} failed: {result.error if hasattr(result, 'error') else 'Unknown error'}"
        logger.error(error_message)
        await self._notify_workflow_error(RuntimeError(error_message))
        self._update_run_status("failed", {"error": error_message})
        return {
            "success": False,
            "failed_step": step_name,
            "error": result.error if hasattr(result, "error") else str(result),
            "run_id": self.run_id,
        }

    def _compile_final_result(self, step_results: List[Any], execution_time: float) -> Dict[str, Any]:
        """最終結果を集約してWorkflowResultを生成"""

        # Extract key data from steps
        news_count = step_results[0].get("count", 0) if step_results else 0
        script_length = step_results[1].get("length", 0) if len(step_results) > 1 else 0

        video_path = self.context.get("video_path")
        video_id = self.context.get("video_id")
        video_url = self.context.get("video_url")
        thumbnail_path = self.context.get("thumbnail_path")

        metadata = self.context.get("metadata", {})
        title = metadata.get("title") if metadata else None

        video_review_data = self.context.get("video_review") if self.context else None
        video_review_summary = None
        video_review_actions: List[str] = []
        if isinstance(video_review_data, dict):
            feedback_block = video_review_data.get("feedback") or {}
            if isinstance(feedback_block, dict):
                video_review_summary = feedback_block.get("summary")
                actions = feedback_block.get("next_video_actions") or []
                if isinstance(actions, list):
                    video_review_actions = [str(action) for action in actions if action]
                elif actions:
                    video_review_actions = [str(actions)]

        # Create WorkflowResult with rich data
        workflow_result = WorkflowResult(
            success=True,
            run_id=self.run_id,
            mode=self.mode,
            execution_time_seconds=execution_time,
            news_count=news_count,
            script_length=script_length,
            video_path=video_path,
            video_id=video_id,
            video_url=video_url,
            title=title,
            thumbnail_path=thumbnail_path,
            # Quality metrics (extract if available)
            wow_score=self._extract_wow_score(step_results[1] if len(step_results) > 1 else None),
            japanese_purity=self._extract_japanese_purity(step_results[1] if len(step_results) > 1 else None),
            # Hook classification
            hook_type=self._classify_hook_from_script(step_results[1] if len(step_results) > 1 else None),
            topic=self._extract_topic(step_results[0] if step_results else None),
            completed_steps=sum(1 for s in step_results if s.success),
            failed_steps=sum(1 for s in step_results if not s.success),
            total_steps=len(self.steps),
            generated_files=self.context.generated_files if self.context else [],
            video_review_summary=video_review_summary,
            video_review_actions=video_review_actions,
        )

        # Log to feedback system
        try:
            metadata_storage.log_execution(workflow_result)
        except Exception as e:
            logger.warning(f"Failed to log execution to feedback system: {e}")

        # Return dict for backward compatibility
        result = {
            "success": True,
            "run_id": self.run_id,
            "execution_time": execution_time,
            "generated_files": self.context.generated_files if self.context else [],
            "steps": {},
        }

        step_names = [step.step_name for step in self.steps]
        for i, step_result in enumerate(step_results):
            if i < len(step_names):
                result["steps"][step_names[i]] = {"success": step_result.success, **step_result.data}

        result["news_count"] = news_count
        result["script_length"] = script_length
        result["video_path"] = video_path
        result["video_id"] = video_id
        result["video_url"] = video_url
        result["drive_folder"] = self.context.get("folder_id") if self.context else None
        result["video_review"] = video_review_data

        return result

    def _extract_wow_score(self, script_step: Any) -> Optional[float]:
        """Extract WOW score from script generation step."""
        # TODO: Extract from CrewAI output if available
        return None

    def _extract_japanese_purity(self, script_step: Any) -> Optional[float]:
        """Extract Japanese purity from script generation step."""
        # TODO: Extract from quality check if available
        return None

    def _classify_hook_from_script(self, script_step: Any) -> str:
        """Classify hook strategy from script content."""
        if not script_step or not hasattr(script_step, "data"):
            return "その他"

        script_content = script_step.data.get("script", "")
        if not script_content:
            return "その他"

        # Get first 200 chars
        first_segment = script_content[:200]

        if re.search(r"(驚き|衝撃|まさか|信じられない)", first_segment):
            return "衝撃的事実"
        elif re.search(r"(なぜ|どうして|理由|原因)", first_segment):
            return "疑問提起"
        elif re.search(r"\d+[%％]|\d+億|\d+倍", first_segment):
            return "意外な数字"
        elif re.search(r"(知らない|隠された|裏側|真実)", first_segment):
            return "隠された真実"
        return "その他"

    def _extract_topic(self, news_step: Any) -> str:
        """Extract main topic from news items."""
        if not news_step or not hasattr(news_step, "data"):
            return "一般"

        news_items = news_step.data.get("news_items", [])
        if not news_items:
            return "一般"

        # Simple extraction from first news title
        first_title = news_items[0].get("title", "") if news_items else ""
        if "株" in first_title or "日経" in first_title:
            return "株式市場"
        elif "金利" in first_title or "利上げ" in first_title or "日銀" in first_title:
            return "金融政策"
        elif "円安" in first_title or "円高" in first_title or "為替" in first_title:
            return "為替"
        elif "GDP" in first_title or "景気" in first_title:
            return "経済指標"
        return "一般"

    async def _notify_workflow_start(self, mode: str):
        """ワークフロー開始通知"""
        message = f"YouTube動画生成ワークフローを開始しました\nモード: {mode}\nRun ID: {self.run_id}"
        discord_notifier.notify(message, level="info", title="ワークフロー開始")

    async def _notify_workflow_success(self, result: Dict[str, Any]):
        """ワークフロー成功通知"""
        execution_time = result.get("execution_time", 0)
        video_url = result.get("video_url", "N/A")
        message = f"YouTube動画生成が完了しました！\n実行時間: {execution_time:.1f}秒\n動画URL: {video_url}"
        fields = {
            "ニュース件数": result.get("news_count", 0),
            "台本文字数": result.get("script_length", 0),
            "生成ファイル数": len(result.get("generated_files", [])),
        }
        discord_notifier.notify(message, level="success", title="ワークフロー完了", fields=fields)

    async def _notify_workflow_error(self, error: Exception):
        """ワークフローエラー通知"""
        message = f"YouTube動画生成でエラーが発生しました\nエラー: {str(error)}\nRun ID: {self.run_id}"
        discord_notifier.notify(message, level="error", title="ワークフローエラー")

    def _update_run_status(self, status: str, result: Dict[str, Any]):
        """実行ステータスを更新"""
        try:
            if sheets_manager and self.run_id:
                sheets_manager.update_run(self.run_id, status=status, error_log=str(result))
        except Exception as e:
            logger.warning(f"Failed to update run status: {e}")

    def _cleanup_temp_files(self):
        """一時ファイルをクリーンアップ"""
        if not self.context:
            return

        cleaned_count = 0
        for file_path in self.context.generated_files:
            try:
                import os

                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary files")


# Backward compatibility: expose workflow via container
def _get_workflow() -> YouTubeWorkflow:
    """Get workflow instance from container (backward compatibility)."""
    from .container import get_container

    return get_container().workflow


# Legacy global variable (backward compatibility)
# Deprecated: Use _get_workflow() or container.workflow instead
class _WorkflowProxy:
    """Proxy object to maintain backward compatibility with 'workflow' global."""

    def __getattr__(self, name):
        return getattr(_get_workflow(), name)


workflow = _WorkflowProxy()


async def run_daily_workflow() -> Dict[str, Any]:
    """日次ワークフロー実行"""
    return await _get_workflow().execute_full_workflow("daily")


async def run_special_workflow() -> Dict[str, Any]:
    """特別ワークフロー実行"""
    return await _get_workflow().execute_full_workflow("special")


async def run_test_workflow() -> Dict[str, Any]:
    """テストワークフロー実行"""
    return await _get_workflow().execute_full_workflow("test")


if __name__ == "__main__":
    import sys

    async def main():
        mode = sys.argv[1] if len(sys.argv) > 1 else "test"
        print(f"Starting YouTube workflow in {mode} mode...")
        try:
            result = await _get_workflow().execute_full_workflow(mode)
            if result.get("success"):
                print("✅ Workflow completed successfully!")
                print(f"Execution time: {result.get('execution_time', 0):.1f}s")
                print(f"Video URL: {result.get('video_url', 'N/A')}")
                print(f"Files generated: {len(result.get('generated_files', []))}")
            else:
                print(f"❌ Workflow failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\n⚠️ Workflow interrupted by user")
            sys.exit(130)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)

    asyncio.run(main())
