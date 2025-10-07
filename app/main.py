import asyncio
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.logging_config import get_log_session, setup_logging
from app.notifications.interfaces import Notifier

from .api_rotation import initialize_api_infrastructure
from .config import cfg
from .discord import discord_notifier
from .metadata_storage import metadata_storage
from .models.workflow import WorkflowResult
from .services.media import ensure_ffmpeg_tooling
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
    StepResult,
    WorkflowStep,
)
from .workflow_runtime import AttemptOutcome, AttemptStatus, ScriptInsights, WorkflowRunState

log_level_str = os.getenv("LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_str.upper(), logging.INFO)
_LOG_SESSION = setup_logging(log_level=log_level)
logger = logging.getLogger(__name__)


_BOOTSTRAP_FFMPEG_PATH: Optional[str] = None
_BOOTSTRAP_COMPLETED = False


def _bootstrap_runtime() -> str:
    """Ensure heavy-weight dependencies are initialized exactly once."""

    global _BOOTSTRAP_COMPLETED, _BOOTSTRAP_FFMPEG_PATH

    if _BOOTSTRAP_COMPLETED and _BOOTSTRAP_FFMPEG_PATH:
        return _BOOTSTRAP_FFMPEG_PATH

    initialize_api_infrastructure()
    logger.info("API infrastructure initialized")
    _BOOTSTRAP_FFMPEG_PATH = ensure_ffmpeg_tooling(cfg.ffmpeg_path)
    _BOOTSTRAP_COMPLETED = True
    logger.info("FFmpeg binary validated: %s", _BOOTSTRAP_FFMPEG_PATH)
    return _BOOTSTRAP_FFMPEG_PATH


RETRY_CLEANUP_MAP: Dict[str, Sequence[str]] = {
    "script_generation": ("script_content", "script_path"),
    "visual_design_generation": ("visual_design", "visual_design_dict"),
    "metadata_generation": ("metadata",),
    "thumbnail_generation": ("thumbnail_path",),
    "audio_synthesis": ("audio_path",),
    "audio_transcription": ("stt_words",),
    "subtitle_alignment": ("subtitle_path", "aligned_subtitles"),
    "video_generation": (
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
    ),
    "media_quality_assurance": (
        "qa_report",
        "qa_report_path",
        "qa_passed",
        "qa_retry_request",
    ),
    "drive_upload": ("drive_result",),
    "youtube_upload": ("youtube_result", "video_id", "video_url"),
}


def _default_workflow_steps() -> List[WorkflowStep]:
    """Instantiate the standard set of workflow steps."""

    return [
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


class YouTubeWorkflow:
    """High-level orchestrator that runs the YouTube production workflow."""

    def __init__(
        self,
        steps: Optional[Iterable[WorkflowStep]] = None,
        notifier: Optional[Notifier] = None,
    ) -> None:
        _bootstrap_runtime()
        self.run_id: Optional[str] = None
        self.mode = "daily"
        self.context: Optional[WorkflowContext] = None
        self._log_session = get_log_session()
        self.steps: List[WorkflowStep] = list(steps) if steps else _default_workflow_steps()
        self.notifier: Notifier = notifier or discord_notifier
        self.failure_bus = FailureBus()
        self.failure_bus.subscribe(self._handle_failure_event)
        self.failure_bus.subscribe(self._cleanup_after_failure)

    async def execute_full_workflow(self, mode: str = "daily") -> Dict[str, Any]:
        """Run every workflow step (with QA-driven retries) and return the payload."""

        run_state, max_attempts = self._initialize_run_state(mode)
        await self._notify_workflow_start(mode)

        for attempt_number in range(1, max_attempts + 1):
            run_state.begin_attempt(attempt_number)
            logger.info("🚀 Workflow attempt %s/%s", attempt_number, max_attempts)
            outcome = await self._run_attempt(run_state, max_attempts)

            if outcome.status is AttemptStatus.SUCCESS:
                return await self._finalize_success(run_state, max_attempts)

            if outcome.status is AttemptStatus.RETRY and outcome.restart_index is not None:
                next_attempt = attempt_number + 1
                if next_attempt > max_attempts:
                    logger.error(
                        "QA requested retry from '%s' but the attempt budget is exhausted",
                        self.steps[outcome.restart_index].step_name,
                    )
                    failure_step = outcome.failure_step or "media_quality_assurance"
                    failure = await self._dispatch_failure(
                        failure_step,
                        result=outcome.failure_result
                        if isinstance(outcome.failure_result, StepResult)
                        else None,
                        error=outcome.failure_result
                        if isinstance(outcome.failure_result, BaseException)
                        else None,
                    )
                    return failure
                restart_name = self.steps[outcome.restart_index].step_name
                if outcome.reason:
                    logger.warning(outcome.reason)
                logger.warning(
                    "Retry requested by QA – restarting from '%s' (attempt %s/%s)",
                    restart_name,
                    next_attempt,
                    max_attempts,
                )
                run_state.request_retry(outcome.restart_index)
                continue

            failure_step = outcome.failure_step or "unknown"
            failure = await self._dispatch_failure(
                failure_step,
                result=outcome.failure_result
                if isinstance(outcome.failure_result, StepResult)
                else None,
                error=outcome.failure_result
                if isinstance(outcome.failure_result, BaseException)
                else None,
            )
            return failure

        logger.error("Workflow failed after exhausting QA retries")
        failure_index = max(run_state.start_index, 0)
        failure_step = (
            self.steps[failure_index].step_name
            if failure_index < len(self.steps)
            else "unknown"
        )
        failure_result = (
            run_state.results[failure_index]
            if failure_index < len(run_state.results)
            else None
        )
        failure = await self._dispatch_failure(
            failure_step,
            result=failure_result if isinstance(failure_result, StepResult) else None,
            error=failure_result if isinstance(failure_result, BaseException) else None,
        )
        return failure

    def _initialize_run_state(self, mode: str) -> tuple[WorkflowRunState, int]:
        """Create the mutable run state and determine QA retry budget."""

        _bootstrap_runtime()
        self.mode = mode
        self.run_id = self._initialize_run(mode)
        self.context = WorkflowContext(run_id=self.run_id, mode=mode)

        qa_gating = getattr(getattr(cfg, "media_quality", None), "gating", None)
        max_attempts = 1 + max(0, getattr(qa_gating, "retry_attempts", 0))

        run_state = WorkflowRunState(
            run_id=self.run_id,
            mode=mode,
            context=self.context,
            steps=self.steps,
            retry_cleanup_map=RETRY_CLEANUP_MAP,
        )
        return run_state, max_attempts

    async def _run_attempt(
        self, run_state: WorkflowRunState, max_attempts: int
    ) -> AttemptOutcome:
        """Execute steps once and describe the resulting state."""

        for index in range(run_state.start_index, len(self.steps)):
            step = self.steps[index]
            logger.info("Executing: %s", step.step_name)
            try:
                result = await step.execute(run_state.context)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Step '%s' raised an exception", step.step_name)
                return AttemptOutcome(
                    status=AttemptStatus.FAILURE,
                    failure_step=step.step_name,
                    failure_result=exc,
                )
            run_state.register_result(index, result)

            if getattr(result, "success", False):
                continue

            if isinstance(step, QualityAssuranceStep):
                retry_directive = self._evaluate_retry_request(run_state, max_attempts)
                if retry_directive is not None:
                    retry_directive.failure_step = step.step_name
                    retry_directive.failure_result = result
                    return retry_directive

            return AttemptOutcome(
                status=AttemptStatus.FAILURE,
                failure_step=step.step_name,
                failure_result=result,
            )

        return AttemptOutcome(status=AttemptStatus.SUCCESS)

    def _evaluate_retry_request(
        self, run_state: WorkflowRunState, max_attempts: int
    ) -> Optional[AttemptOutcome]:
        """Translate QA retry metadata into an actionable directive."""

        if run_state.context is None or run_state.attempt >= max_attempts:
            return None

        retry_request = run_state.context.get("qa_retry_request")
        if not retry_request:
            return None

        retry_step_name = retry_request.get("start_step")
        retry_index = self._resolve_step_index(retry_step_name)
        if retry_index is None:
            return None

        return AttemptOutcome(
            status=AttemptStatus.RETRY,
            restart_index=retry_index,
            reason=retry_request.get("reason"),
        )

    def _resolve_step_index(self, step_name: Optional[str]) -> Optional[int]:
        if not step_name:
            return None
        for idx, step in enumerate(self.steps):
            if step.step_name == step_name:
                return idx
        return None

    async def _dispatch_failure(
        self,
        step_name: str,
        *,
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
        return await self._handle_workflow_failure(step_name, result, error)

    async def _handle_failure_event(self, event: WorkflowFailureEvent) -> None:
        event.response = await self._handle_workflow_failure(event.step_name, event.result, event.error)

    async def _cleanup_after_failure(self, _: WorkflowFailureEvent) -> None:
        self._cleanup_temp_files()

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
        elif result is not None:
            error_detail = str(result)
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


    async def _finalize_success(
        self, run_state: WorkflowRunState, max_attempts: int
    ) -> Dict[str, Any]:
        step_results = run_state.results
        video_url = run_state.context.get("video_url")
        if video_url:
            metadata_storage.update_video_stats(run_id=run_state.run_id, video_url=video_url)
            logger.info("Updated metadata storage with video URL")

        execution_time = run_state.execution_time_seconds()
        result = self._compile_final_result(run_state, step_results, execution_time)

        if self._log_session:
            self._log_session.mark_status(
                "succeeded",
                execution_time_seconds=execution_time,
                attempts=run_state.attempt,
                max_attempts=max_attempts,
                steps=[step.step_name for step in self.steps],
                video_url=video_url,
                news_count=result.get("news_count"),
            )

        await self._notify_workflow_success(result)
        self._update_run_status("completed", result)
        self._cleanup_temp_files()
        return result

    def _get_step_result(
        self, results: List[Optional[Any]], target_step: str
    ) -> Optional[Any]:
        for step, result in zip(self.steps, results):
            if step.step_name == target_step:
                return result
        return None

    def _compile_final_result(
        self,
        run_state: WorkflowRunState,
        step_results: List[Optional[Any]],
        execution_time: float,
    ) -> Dict[str, Any]:
        context = run_state.context
        news_step = self._get_step_result(step_results, 'news_collection')
        script_step = self._get_step_result(step_results, 'script_generation')
        metadata_step = self._get_step_result(step_results, 'metadata_generation')

        insights = ScriptInsights.from_step(script_step)
        news_count = news_step.get("count", 0) if news_step else 0
        script_length = script_step.get("length", 0) if script_step else 0
        video_path = context.get("video_path")
        video_id = context.get("video_id")
        video_url = context.get("video_url")
        thumbnail_path = context.get("thumbnail_path")
        metadata = context.get("metadata", {}) or {}
        title = metadata.get("title")
        video_review_data = context.get("video_review")
        video_review_summary, video_review_actions = self._extract_video_review(video_review_data)

        workflow_result = WorkflowResult(
            success=True,
            run_id=run_state.run_id,
            mode=run_state.mode,
            execution_time_seconds=execution_time,
            news_count=news_count,
            script_length=script_length,
            video_path=video_path,
            video_id=video_id,
            video_url=video_url,
            title=title,
            thumbnail_path=thumbnail_path,
            wow_score=insights.wow_score,
            surprise_points=insights.surprise_points,
            emotion_peaks=insights.emotion_peaks,
            visual_instructions=insights.visual_instructions,
            retention_prediction=insights.retention_prediction,
            japanese_purity=insights.japanese_purity,
            hook_type=self._determine_hook_type(script_step, metadata_step, insights),
            topic=self._extract_topic(news_step),
            completed_steps=sum(1 for s in step_results if getattr(s, "success", False)),
            failed_steps=sum(1 for s in step_results if not getattr(s, "success", False)),
            total_steps=len(self.steps),
            generated_files=context.generated_files,
            video_review_summary=video_review_summary,
            video_review_actions=video_review_actions,
        )
        metadata_storage.log_execution(workflow_result)

        serialized_steps = {}
        for step, step_result in zip(self.steps, step_results):
            if step_result is None:
                continue
            serialized_steps[step.step_name] = {
                "success": getattr(step_result, "success", False),
                **(getattr(step_result, "data", {}) or {}),
            }

        result: Dict[str, Any] = {
            "success": True,
            "run_id": run_state.run_id,
            "execution_time": execution_time,
            "generated_files": context.generated_files,
            "steps": serialized_steps,
            "news_count": news_count,
            "script_length": script_length,
            "video_path": video_path,
            "video_id": video_id,
            "video_url": video_url,
            "drive_folder": context.get("folder_id"),
            "video_review": video_review_data,
            "script_insights": {
                "wow_score": insights.wow_score,
                "surprise_points": insights.surprise_points,
                "emotion_peaks": insights.emotion_peaks,
                "visual_instructions": insights.visual_instructions,
                "retention_prediction": insights.retention_prediction,
                "japanese_purity": insights.japanese_purity,
                "hook_variant": insights.hook_variant,
                "title_variants": insights.title_variants,
                "thumbnail_prompts": insights.thumbnail_prompts,
                "emotion_curve": insights.emotion_curve,
                "visual_calls_to_action": insights.visual_calls_to_action,
                "visual_b_roll_suggestions": insights.visual_b_roll_suggestions,
                "emotion_highlights": insights.emotion_highlights,
                "visual_guidelines": insights.visual_guidelines,
                "visual_shot_list": insights.visual_shot_list,
            },
        }
        return result

    def _extract_video_review(
        self, review_data: Optional[Dict[str, Any]]
    ) -> tuple[Optional[str], List[str]]:
        if not isinstance(review_data, dict):
            return None, []
        feedback_block = review_data.get("feedback") or {}
        if not isinstance(feedback_block, dict):
            return None, []
        summary = feedback_block.get("summary")
        actions_raw = feedback_block.get("next_video_actions") or []
        if isinstance(actions_raw, list):
            actions = [str(action) for action in actions_raw if action]
        elif actions_raw:
            actions = [str(actions_raw)]
        else:
            actions = []
        return summary, actions

    def _determine_hook_type(
        self,
        script_step: Any,
        metadata_step: Any,
        insights: ScriptInsights,
    ) -> Optional[str]:
        if insights.hook_variant:
            return insights.hook_variant
        metadata_hook = None
        if metadata_step and hasattr(metadata_step, "data"):
            metadata_hook = metadata_step.data.get("hook")
        if metadata_hook:
            return metadata_hook
        script_content = ""
        if script_step and hasattr(script_step, "data"):
            script_content = script_step.data.get("script", "")
        return self._classify_hook_from_content(script_content)

    def _classify_hook_from_content(self, script_content: str) -> str:
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
