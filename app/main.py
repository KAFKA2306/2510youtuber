import asyncio
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.logging_config import get_log_session, setup_logging
from app.notifications.interfaces import Notifier

from .api_rotation import initialize_api_infrastructure
from .config import cfg
from .services.media import ensure_ffmpeg_tooling
from .discord import discord_notifier
from .metadata_storage import metadata_storage
from .models.workflow import WorkflowResult
from .sheets import sheets_manager
from .workflow import (
    AlignSubtitlesStep,
    CollectNewsStep,
    FailureBus,
    GenerateMetadataStep,
    GenerateScriptStep,
    GenerateThumbnailStep,
    GenerateVideoStep,
    GenerateVisualDesignStep,
    QualityAssuranceStep,
    ReviewVideoStep,
    SynthesizeAudioStep,
    TranscribeAudioStep,
    UploadToDriveStep,
    UploadToYouTubeStep,
    WorkflowContext,
    WorkflowFailureEvent,
    WorkflowStep,
)

log_level_str = os.getenv("LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_str.upper(), logging.INFO)
_LOG_SESSION = setup_logging(log_level=log_level)
logger = logging.getLogger(__name__)
initialize_api_infrastructure()
logger.info("API infrastructure initialized at startup")
_STARTUP_FFMPEG_PATH = ensure_ffmpeg_tooling(cfg.ffmpeg_path)
logger.info("FFmpeg binary validated at startup: %s", _STARTUP_FFMPEG_PATH)


class YouTubeWorkflow:
    RETRY_CLEANUP_MAP = {
        "script_generation": {"script_content", "script_path"},
        "visual_design_generation": {"visual_design", "visual_design_dict"},
        "metadata_generation": {"metadata"},
        "thumbnail_generation": {"thumbnail_path"},
        "audio_synthesis": {"audio_path"},
        "audio_transcription": {"stt_words"},
        "subtitle_alignment": {"subtitle_path", "aligned_subtitles"},
        "video_generation": {
            "video_path",
            "archived_audio_path",
            "archived_subtitle_path",
            "broll_path",
            "broll_metadata",
            "broll_keywords",
            "broll_clip_paths",
            "broll_source",
            "use_stock_footage",
            "archived_broll_path",
        },
        "media_quality_assurance": {"qa_report", "qa_report_path", "qa_passed", "qa_retry_request"},
        "drive_upload": {"drive_result"},
        "youtube_upload": {"youtube_result", "video_id", "video_url"},
    }

    def __init__(self, notifier: Optional[Notifier] = None):
        self.run_id = None
        self.mode = "daily"
        self.context: Optional[WorkflowContext] = None
        self._log_session = get_log_session()
        self.notifier: Notifier = notifier or discord_notifier
        self.failure_bus = FailureBus()
        self.failure_bus.subscribe(self._handle_failure_event)
        self.failure_bus.subscribe(self._cleanup_after_failure)
        self.steps: List[WorkflowStep] = [
            CollectNewsStep(),
            GenerateScriptStep(),
            GenerateVisualDesignStep(),
            GenerateMetadataStep(),
            GenerateThumbnailStep(),
            SynthesizeAudioStep(),
            TranscribeAudioStep(),
            AlignSubtitlesStep(),
            GenerateVideoStep(),
            QualityAssuranceStep(),
            UploadToDriveStep(),
            UploadToYouTubeStep(),
            ReviewVideoStep(),
        ]

    async def execute_full_workflow(self, mode: str = "daily") -> Dict[str, Any]:
        start_time = datetime.now()
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
                try:
                    result = await step.execute(self.context)
                except Exception as exc:  # noqa: BLE001 - funnel via failure bus
                    logger.exception("Step '%s' raised an exception", step.step_name)
                    return await self._dispatch_failure(step.step_name, error=exc)
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
                                return await self._dispatch_failure(step.step_name, result=result)
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
                    return await self._dispatch_failure(step.step_name, result=result)
            if retry_triggered:
                continue
            final_results = [res for res in step_results if res is not None]
            video_url = self.context.get("video_url")
            if video_url:
                metadata_storage.update_video_stats(run_id=self.run_id, video_url=video_url)
                logger.info("Updated metadata storage with video URL")
            execution_time = (datetime.now() - start_time).total_seconds()
            result = self._compile_final_result(final_results, execution_time)
            if self._log_session:
                self._log_session.mark_status(
                    "succeeded",
                    execution_time_seconds=execution_time,
                    attempts=attempt,
                    max_attempts=max_attempts,
                    steps=[step.step_name for step in self.steps],
                    video_url=video_url,
                    news_count=result.get("news_count"),
                )
            await self._notify_workflow_success(result)
            self._update_run_status("completed", result)
            self._cleanup_temp_files()
            return result
        logger.error("Workflow failed after exhausting QA retries")
        failure_index = max(start_index, 0)
        failure_step = self.steps[failure_index].step_name if failure_index < len(self.steps) else "unknown"
        failure_result = step_results[failure_index] if failure_index < len(step_results) else None
        return await self._dispatch_failure(failure_step, result=failure_result)

    def _resolve_step_index(self, step_name: Optional[str]) -> Optional[int]:
        if not step_name:
            return None
        for idx, step in enumerate(self.steps):
            if step.step_name == step_name:
                return idx
        return None

    def _prepare_context_for_retry(self, start_index: int) -> None:
        if not self.context:
            return
        keys_to_remove = set()
        for step in self.steps[start_index:]:
            keys_to_remove.update(self.RETRY_CLEANUP_MAP.get(step.step_name, set()))
        for key in keys_to_remove:
            if key in self.context.state:
                self.context.state.pop(key, None)

    def _clear_step_results(self, step_results: List[Optional[Any]], start_index: int) -> None:
        for idx in range(start_index, len(step_results)):
            step_results[idx] = None

    async def _dispatch_failure(
        self,
        step_name: str,
        result: Optional[Any] = None,
        error: Optional[BaseException] = None,
    ) -> Dict[str, Any]:
        event = WorkflowFailureEvent(
            step_name=step_name,
            context=self.context,
            result=result,
            error=error,
        )
        enriched_event = await self.failure_bus.notify(event)
        if enriched_event.response is not None:
            return enriched_event.response
        failure_error = None
        if result and hasattr(result, "error") and getattr(result, "error"):
            failure_error = getattr(result, "error")
        elif error:
            failure_error = str(error)
        else:
            failure_error = "Unknown error"
        enriched_event.response = {
            "success": False,
            "failed_step": step_name,
            "error": failure_error,
            "run_id": self.run_id,
        }
        return enriched_event.response

    def _initialize_run(self, mode: str) -> str:
        if sheets_manager:
            run_id = sheets_manager.create_run(mode)
            logger.info(f"Initialized workflow run: {run_id}")
            if self._log_session:
                self._log_session.bind_workflow_run(run_id, mode=mode)
            return run_id
        run_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.warning(f"Sheets not available, using local run ID: {run_id}")
        if self._log_session:
            self._log_session.bind_workflow_run(run_id, mode=mode)
        return run_id

    async def _handle_failure_event(self, event: WorkflowFailureEvent) -> None:
        event.response = await self._handle_workflow_failure(event.step_name, event.result, event.error)

    async def _cleanup_after_failure(self, _: WorkflowFailureEvent) -> None:
        self._cleanup_temp_files()

    async def _handle_workflow_failure(
        self,
        step_name: str,
        result: Optional[Any],
        error: Optional[BaseException] = None,
    ) -> Dict[str, Any]:
        error_detail: Optional[str] = None
        if result and hasattr(result, "error") and getattr(result, "error"):
            error_detail = getattr(result, "error")
        elif error:
            error_detail = str(error)
        else:
            error_detail = "Unknown error"
        error_message = f"{step_name} failed: {error_detail}"
        logger.error(error_message)
        exc_to_notify = error if isinstance(error, Exception) else RuntimeError(error_message)
        await self._notify_workflow_error(exc_to_notify)
        self._update_run_status("failed", {"error": error_message})
        if self._log_session:
            self._log_session.mark_status(
                "failed",
                failed_step=step_name,
                error=error_message,
                run_id=self.run_id,
            )
        return {
            "success": False,
            "failed_step": step_name,
            "error": error_detail or "Unknown error",
            "run_id": self.run_id,
        }

    def _compile_final_result(self, step_results: List[Any], execution_time: float) -> Dict[str, Any]:
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
        script_step = step_results[1] if len(step_results) > 1 else None
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
            wow_score=self._extract_wow_score(script_step),
            surprise_points=self._extract_surprise_points(script_step),
            emotion_peaks=self._extract_emotion_peaks(script_step),
            visual_instructions=self._extract_visual_instructions(script_step),
            retention_prediction=self._extract_retention_prediction(script_step),
            japanese_purity=self._extract_japanese_purity(script_step),
            hook_type=self._classify_hook_from_script(script_step),
            topic=self._extract_topic(step_results[0] if step_results else None),
            completed_steps=sum(1 for s in step_results if s.success),
            failed_steps=sum(1 for s in step_results if not s.success),
            total_steps=len(self.steps),
            generated_files=self.context.generated_files if self.context else [],
            video_review_summary=video_review_summary,
            video_review_actions=video_review_actions,
        )
        metadata_storage.log_execution(workflow_result)
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
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        if not metrics:
            return None
        return metrics.get("wow_score")

    def _extract_japanese_purity(self, script_step: Any) -> Optional[float]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        purity = script_step.data.get("japanese_purity_score")
        if purity:
            return purity
        metrics = script_step.data.get("script_metrics", {})
        return metrics.get("japanese_purity")

    def _extract_surprise_points(self, script_step: Any) -> Optional[int]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        return metrics.get("surprise_points")

    def _extract_emotion_peaks(self, script_step: Any) -> Optional[int]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        return metrics.get("emotion_peaks")

    def _extract_visual_instructions(self, script_step: Any) -> Optional[int]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        return metrics.get("visual_instructions")

    def _extract_retention_prediction(self, script_step: Any) -> Optional[float]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        return metrics.get("retention_prediction")

    def _classify_hook_from_script(self, script_step: Any) -> str:
        if not script_step or not hasattr(script_step, "data"):
            return "その他"
        script_content = script_step.data.get("script", "")
        if not script_content:
            return "その他"
        first_segment = script_content[:200]
        if re.search(r"(驚き|衝撃|まさか|信じられない)", first_segment):
            return "衝撃的事実"
        if re.search(r"(なぜ|どうして|理由|原因)", first_segment):
            return "疑問提起"
        if re.search(r"\d+[%％]|\d+億|\d+倍", first_segment):
            return "意外な数字"
        if re.search(r"(知らない|隠された|裏側|真実)", first_segment):
            return "隠された真実"
        return "その他"

    def _extract_emotion_curve(self, script_step: Any) -> Optional[List[Dict[str, Any]]]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        curve = metrics.get("emotion_curve")
        if isinstance(curve, list):
            return curve
        return None

    def _extract_visual_calls_to_action(self, script_step: Any) -> Optional[List[str]]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        calls = metrics.get("visual_calls_to_action")
        if isinstance(calls, list):
            return [str(item) for item in calls]
        if calls:
            return [str(calls)]
        return None

    def _extract_visual_b_roll_suggestions(self, script_step: Any) -> Optional[List[str]]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        suggestions = metrics.get("visual_b_roll_suggestions")
        if isinstance(suggestions, list):
            return [str(item) for item in suggestions]
        if suggestions:
            return [str(suggestions)]
        return None

    def _extract_emotion_highlights(self, script_step: Any) -> Optional[List[str]]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        metrics = script_step.data.get("script_metrics", {})
        highlights = metrics.get("emotion_highlights")
        if isinstance(highlights, list):
            return [str(item) for item in highlights]
        if highlights:
            return [str(highlights)]
        return None

    def _extract_visual_guidelines(self, script_step: Any) -> Optional[List[str]]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        guidelines = script_step.data.get("visual_guidelines")
        if isinstance(guidelines, list):
            return [str(item) for item in guidelines]
        if guidelines:
            return [str(guidelines)]
        return None

    def _extract_visual_shot_list(self, script_step: Any) -> Optional[List[str]]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        shot_list = script_step.data.get("visual_shot_list")
        if isinstance(shot_list, list):
            return [str(item) for item in shot_list]
        if shot_list:
            return [str(shot_list)]
        return None

    def _extract_hook_variant(self, script_step: Any) -> Optional[str]:
        if not script_step or not hasattr(script_step, "data"):
            return None
        return script_step.data.get("hook_variant")

    def _extract_title_variants(self, script_step: Any) -> List[str]:
        if not script_step or not hasattr(script_step, "data"):
            return []
        variants = script_step.data.get("title_variants")
        if isinstance(variants, list):
            return [str(item) for item in variants]
        if variants:
            return [str(variants)]
        return []

    def _extract_thumbnail_prompts(self, script_step: Any) -> List[str]:
        if not script_step or not hasattr(script_step, "data"):
            return []
        prompts = script_step.data.get("thumbnail_prompts")
        if isinstance(prompts, list):
            return [str(item) for item in prompts]
        if prompts:
            return [str(prompts)]
        return []

    def _extract_hook_from_metadata(self, metadata_step: Any) -> Optional[str]:
        if not metadata_step or not hasattr(metadata_step, "data"):
            return None
        return metadata_step.data.get("hook")

    def _extract_hook_from_script(self, script_step: Any) -> Optional[str]:
        hook = self._extract_hook_variant(script_step)
        if hook:
            return hook
        return self._extract_hook_from_metadata(script_step)

    def _extract_topic(self, news_step: Any) -> str:
        if not news_step or not hasattr(news_step, "data"):
            return "一般"
        news_items = news_step.data.get("news_items", [])
        if not news_items:
            return "一般"
        first_title = news_items[0].get("title", "") if news_items else ""
        if "株" in first_title or "日経" in first_title:
            return "株式市場"
        if "金利" in first_title or "利上げ" in first_title or "日銀" in first_title:
            return "金融政策"
        if "円安" in first_title or "円高" in first_title or "為替" in first_title:
            return "為替"
        if "GDP" in first_title or "景気" in first_title:
            return "経済指標"
        return "一般"

    async def _notify_workflow_start(self, mode: str):
        message = f"YouTube動画生成ワークフローを開始しました\nモード: {mode}\nRun ID: {self.run_id}"
        await self.notifier.notify(message, level="info", title="ワークフロー開始")

    async def _notify_workflow_success(self, result: Dict[str, Any]):
        execution_time = result.get("execution_time", 0)
        video_url = result.get("video_url", "N/A")
        message = f"YouTube動画生成が完了しました！\n実行時間: {execution_time:.1f}秒\n動画URL: {video_url}"
        fields = {
            "ニュース件数": result.get("news_count", 0),
            "台本文字数": result.get("script_length", 0),
            "生成ファイル数": len(result.get("generated_files", [])),
        }
        await self.notifier.notify(message, level="success", title="ワークフロー完了", fields=fields)

    async def _notify_workflow_error(self, error: Exception):
        message = f"YouTube動画生成でエラーが発生しました\nエラー: {str(error)}\nRun ID: {self.run_id}"
        await self.notifier.notify(message, level="error", title="ワークフローエラー")

    def _update_run_status(self, status: str, result: Dict[str, Any]):
        if sheets_manager and self.run_id:
            sheets_manager.update_run(self.run_id, status=status, error_log=str(result))

    def _cleanup_temp_files(self):
        if not self.context:
            return
        cleaned_count = 0
        for file_path in self.context.generated_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleaned_count += 1
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary files")


def _get_workflow() -> YouTubeWorkflow:
    from .container import get_container

    return get_container().workflow


class _WorkflowProxy:
    def __getattr__(self, name):
        return getattr(_get_workflow(), name)


workflow = _WorkflowProxy()


async def run_daily_workflow() -> Dict[str, Any]:
    return await _get_workflow().execute_full_workflow("daily")


async def run_special_workflow() -> Dict[str, Any]:
    return await _get_workflow().execute_full_workflow("special")


async def run_test_workflow() -> Dict[str, Any]:
    return await _get_workflow().execute_full_workflow("test")


if __name__ == "__main__":
    import sys

    async def main():
        mode = sys.argv[1] if len(sys.argv) > 1 else "test"
        logger.info(f"🚀 Starting YouTube Workflow ({mode} mode)")
        start_time = time.time()
        result = await _get_workflow().execute_full_workflow(mode)
        duration = time.time() - start_time
        if result.get("success"):
            logger.info(f"✅ Workflow completed successfully! (Execution time: {duration:.1f}s)")
            logger.info(f"Video URL: {result.get('video_url', 'N/A')}")
            logger.info(f"Files generated: {len(result.get('generated_files', []))}")
        else:
            logger.error(f"❌ Workflow failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    asyncio.run(main())
