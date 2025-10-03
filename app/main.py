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
    SynthesizeAudioStep,
    TranscribeAudioStep,
    UploadToDriveStep,
    UploadToYouTubeStep,
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

    def __init__(self):
        self.run_id = None
        self.mode = "daily"
        self.context: Optional[WorkflowContext] = None

        # Define workflow steps (dependency injection ready)
        self.steps: List[WorkflowStep] = [
            CollectNewsStep(),
            GenerateScriptStep(),
            SynthesizeAudioStep(),
            TranscribeAudioStep(),
            AlignSubtitlesStep(),
            GenerateVideoStep(),
            GenerateMetadataStep(),
            GenerateThumbnailStep(),
            UploadToDriveStep(),
            UploadToYouTubeStep(),
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

            # Execute all steps sequentially
            step_results = []
            for step in self.steps:
                logger.info(f"Executing: {step.step_name}")
                result = await step.execute(self.context)
                step_results.append(result)

                # Track generated files
                if result.files_generated:
                    self.context.add_files(result.files_generated)

                # Stop on failure
                if not result.success:
                    return self._handle_workflow_failure(step.step_name, result)

            # Update metadata storage with video URL if available
            video_url = self.context.get("video_url")
            if video_url:
                try:
                    metadata_storage.update_video_stats(
                        run_id=self.run_id,
                        video_url=video_url
                    )
                    logger.info("Updated metadata storage with video URL")
                except Exception as e:
                    logger.warning(f"Failed to update video URL in storage: {e}")

            execution_time = (datetime.now() - start_time).total_seconds()
            result = self._compile_final_result(step_results, execution_time)

            await self._notify_workflow_success(result)
            self._update_run_status("completed", result)

            return result

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

    def _handle_workflow_failure(self, step_name: str, result: Any) -> Dict[str, Any]:
        """ステップ失敗時の処理"""
        error_message = f"{step_name} failed: {result.error if hasattr(result, 'error') else 'Unknown error'}"
        logger.error(error_message)
        asyncio.create_task(self._notify_workflow_error(Exception(error_message)))
        self._update_run_status("failed", {"error": error_message})
        return {
            "success": False,
            "failed_step": step_name,
            "error": result.error if hasattr(result, 'error') else str(result),
            "run_id": self.run_id
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
                result["steps"][step_names[i]] = {
                    "success": step_result.success,
                    **step_result.data
                }

        result["news_count"] = news_count
        result["script_length"] = script_length
        result["video_path"] = video_path
        result["video_id"] = video_id
        result["video_url"] = video_url
        result["drive_folder"] = self.context.get("folder_id") if self.context else None

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
        if not script_step or not hasattr(script_step, 'data'):
            return "その他"

        script_content = script_step.data.get("script", "")
        if not script_content:
            return "その他"

        # Get first 200 chars
        first_segment = script_content[:200]

        if re.search(r'(驚き|衝撃|まさか|信じられない)', first_segment):
            return "衝撃的事実"
        elif re.search(r'(なぜ|どうして|理由|原因)', first_segment):
            return "疑問提起"
        elif re.search(r'\d+[%％]|\d+億|\d+倍', first_segment):
            return "意外な数字"
        elif re.search(r'(知らない|隠された|裏側|真実)', first_segment):
            return "隠された真実"
        return "その他"

    def _extract_topic(self, news_step: Any) -> str:
        """Extract main topic from news items."""
        if not news_step or not hasattr(news_step, 'data'):
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
