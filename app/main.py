"""メインワークフローモジュール

YouTube動画自動生成の全工程を統合・実行します。
10ステップの処理を順序立てて実行し、エラーハンドリングと進捗通知を行います。
"""

import asyncio
import logging
import os
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from .align_subtitles import align_script_with_stt, export_srt

# 各モジュールをインポート
from .api_rotation import initialize_api_infrastructure
from .config import cfg
from .discord import discord_notifier
from .drive import upload_video_package
from .metadata import generate_youtube_metadata
from .metadata_storage import metadata_storage
from .script_gen import generate_dialogue
from .search_news import collect_news
from .sheets import load_prompts as load_prompts_from_sheets
from .sheets import sheets_manager
from .stt import transcribe_long_audio
from .thumbnail import generate_thumbnail
from .tts import synthesize_script
from .utils import FileUtils
from .video import generate_video
from .youtube import upload_video as youtube_upload

logger = logging.getLogger(__name__)

# Initialize API infrastructure once at module import
# This ensures all Gemini/Perplexity API keys are registered before any workflow runs
try:
    initialize_api_infrastructure()
    logger.info("API infrastructure initialized at startup")
except Exception as e:
    logger.warning(f"Failed to initialize API infrastructure: {e}")


class YouTubeWorkflow:
    """YouTube動画自動生成ワークフロー"""

    def __init__(self):
        self.run_id = None
        self.mode = "daily"  # デフォルトモード
        self.workflow_state = {}
        self.generated_files = []

    async def execute_full_workflow(self, mode: str = "daily") -> Dict[str, Any]:
        """完全なワークフローを実行
        """
        start_time = datetime.now()
        try:
            self.mode = mode  # モードを保存
            self.run_id = self._initialize_run(mode)
            await self._notify_workflow_start(mode)

            step1_result = await self._step1_collect_news(mode)
            if not step1_result.get("success"):
                return self._handle_workflow_failure("Step 1: News Collection", step1_result)
            self.generated_files.extend(step1_result.get("files", []))

            step2_result = await self._step2_generate_script(step1_result["news_items"])
            if not step2_result.get("success"):
                return self._handle_workflow_failure("Step 2: Script Generation", step2_result)
            self.generated_files.extend(step2_result.get("files", []))

            step3_result = await self._step3_synthesize_audio(step2_result["script"])
            if not step3_result.get("success"):
                return self._handle_workflow_failure("Step 3: Audio Synthesis", step3_result)
            self.generated_files.extend(step3_result.get("files", []))

            step4_result = await self._step4_transcribe_audio(step3_result["audio_path"])
            if not step4_result.get("success"):
                return self._handle_workflow_failure("Step 4: Audio Transcription", step4_result)

            step5_result = await self._step5_align_subtitles(step2_result["script"], step4_result["stt_words"])
            if not step5_result.get("success"):
                return self._handle_workflow_failure("Step 5: Subtitle Alignment", step5_result)
            self.generated_files.extend(step5_result.get("files", []))

            step6_result = await self._step6_generate_video(step3_result["audio_path"], step5_result["subtitle_path"])
            if not step6_result.get("success"):
                return self._handle_workflow_failure("Step 6: Video Generation", step6_result)
            self.generated_files.extend(step6_result.get("files", []))

            step7_result = await self._step7_generate_metadata(step1_result["news_items"], step2_result["script"], mode)

            step8_result = await self._step8_generate_thumbnail(
                step7_result["metadata"], step1_result["news_items"], mode
            )
            self.generated_files.extend(step8_result.get("files", []))

            step9_result = await self._step9_upload_to_drive(
                step6_result["video_path"],
                step8_result.get("thumbnail_path"),
                step5_result["subtitle_path"],
                step7_result["metadata"],
            )

            step10_result = await self._step10_upload_to_youtube(
                step6_result["video_path"], step7_result["metadata"], step8_result.get("thumbnail_path")
            )

            # 動画URLを記録に追加
            if step10_result.get("video_url"):
                try:
                    metadata_storage.update_video_stats(
                        run_id=self.run_id,
                        video_url=step10_result.get("video_url")
                    )
                    logger.info("Updated metadata storage with video URL")
                except Exception as e:
                    logger.warning(f"Failed to update video URL in storage: {e}")

            execution_time = (datetime.now() - start_time).total_seconds()
            result = self._compile_final_result(
                step1_result,
                step2_result,
                step3_result,
                step4_result,
                step5_result,
                step6_result,
                step7_result,
                step8_result,
                step9_result,
                step10_result,
                execution_time=execution_time,
            )

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

    async def _step1_collect_news(self, mode: str) -> Dict[str, Any]:
        logger.info("Step 1: Starting news collection...")
        try:
            # インスタンス変数のmodeを使用
            prompt_a = self._get_prompts(self.mode).get("prompt_a", self._default_news_prompt())

            # 使用したプロンプトを記録
            if sheets_manager and self.run_id:
                sheets_manager.record_prompt_used(self.run_id, "prompt_a", prompt_a)

            news_items = collect_news(prompt_a, mode)
            if not news_items:
                raise Exception("No news items collected")
            logger.info(f"Collected {len(news_items)} news items")

            # Store in workflow state for later use
            self.workflow_state["news_items"] = news_items

            return {
                "success": True,
                "news_items": news_items,
                "count": len(news_items),
                "step": "news_collection",
                "files": [],
            }
        except Exception as e:
            logger.error(f"Step 1 failed: {e}")
            return {"success": False, "error": str(e), "step": "news_collection"}

    async def _step2_generate_script(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info("Step 2: Starting script generation...")

        # CrewAI Flowの使用判定
        use_crewai = getattr(cfg, "use_crewai_script_generation", True)
        logger.info(f"CrewAI WOW Script Generation: {'ENABLED' if use_crewai else 'DISABLED'}")

        try:
            if use_crewai:
                # CrewAI WOW Script Creation Flowを使用
                from app.crew.flows import create_wow_script_crew

                logger.info("🚀 Using CrewAI WOW Script Creation Crew...")
                crew_result = create_wow_script_crew(
                    news_items=news_items,
                    target_duration_minutes=cfg.max_video_duration_minutes
                )

                if not crew_result.get("success"):
                    raise Exception(f"CrewAI execution failed: {crew_result.get('error', 'Unknown error')}")

                script_content = crew_result.get("final_script", "")

            else:
                # 従来の3段階品質チェックを使用
                logger.info(f"3-stage quality check: {'ENABLED' if cfg.use_three_stage_quality_check else 'DISABLED'}")

                # インスタンス変数のmodeを使用
                prompt_b = self._get_prompts(self.mode).get("prompt_b", self._default_script_prompt())

                # 使用したプロンプトを記録
                if sheets_manager and self.run_id:
                    sheets_manager.record_prompt_used(self.run_id, "prompt_b", prompt_b)

                script_content = generate_dialogue(
                    news_items,
                    prompt_b,
                    target_duration_minutes=cfg.max_video_duration_minutes,
                    use_quality_check=cfg.use_three_stage_quality_check
                )

            if not script_content or len(script_content) < 100:
                raise Exception("Generated script too short or empty")

            # Debug: Log first 1000 chars of script to verify format
            logger.info(f"Script preview (first 1000 chars): {script_content[:1000]}")

            script_path = FileUtils.get_temp_file(prefix="script_", suffix=".txt")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            # Store in workflow state for later use
            self.workflow_state["script_content"] = script_content

            logger.info(f"Generated script: {len(script_content)} characters")
            return {
                "success": True,
                "script": script_content,
                "script_path": script_path,
                "length": len(script_content),
                "step": "script_generation",
                "files": [script_path],
                "quality_checked": use_crewai or cfg.use_three_stage_quality_check,
                "used_crewai": use_crewai,
            }
        except Exception as e:
            logger.error(f"Step 2 failed: {e}")
            return {"success": False, "error": str(e), "step": "script_generation"}

    async def _step3_synthesize_audio(self, script_content: str) -> Dict[str, Any]:
        logger.info("Step 3: Starting audio synthesis...")
        try:
            audio_paths = await synthesize_script(script_content)
            if not audio_paths:
                raise Exception("Audio synthesis failed")
            main_audio_path = audio_paths[0]
            logger.info(f"Generated audio: {main_audio_path}")
            return {
                "success": True,
                "audio_path": main_audio_path,
                "audio_paths": audio_paths,
                "step": "audio_synthesis",
                "files": audio_paths,
            }
        except Exception as e:
            logger.error(f"Step 3 failed: {e}")
            return {"success": False, "error": str(e), "step": "audio_synthesis"}

    async def _step4_transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        logger.info("Step 4: Starting audio transcription...")
        try:
            stt_words = transcribe_long_audio(audio_path)
            if not stt_words:
                raise Exception("Audio transcription failed")
            logger.info(f"Transcribed {len(stt_words)} words")
            return {
                "success": True,
                "stt_words": stt_words,
                "word_count": len(stt_words),
                "step": "audio_transcription",
            }
        except Exception as e:
            logger.error(f"Step 4 failed: {e}")
            return {"success": False, "error": str(e), "step": "audio_transcription"}

    async def _step5_align_subtitles(self, script_content: str, stt_words: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info("Step 5: Starting subtitle alignment...")
        try:
            aligned_subtitles = align_script_with_stt(script_content, stt_words)
            if not aligned_subtitles:
                raise Exception("Subtitle alignment failed")
            subtitle_path = FileUtils.get_temp_file(prefix="subtitles_", suffix=".srt")
            export_srt(aligned_subtitles, subtitle_path)
            logger.info(f"Generated subtitles: {len(aligned_subtitles)} segments")
            return {
                "success": True,
                "aligned_subtitles": aligned_subtitles,
                "subtitle_path": subtitle_path,
                "segment_count": len(aligned_subtitles),
                "step": "subtitle_alignment",
                "files": [subtitle_path],
            }
        except Exception as e:
            logger.error(f"Step 5 failed: {e}")
            return {"success": False, "error": str(e), "step": "subtitle_alignment"}

    async def _step6_generate_video(self, audio_path: str, subtitle_path: str) -> Dict[str, Any]:
        logger.info("Step 6: Starting video generation...")
        try:
            # Get script and news from workflow state for stock footage keywords
            script_content = self.workflow_state.get("script_content", "")
            news_items = self.workflow_state.get("news_items", [])

            video_path = generate_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                title="Economic News Analysis",
                script_content=script_content,
                news_items=news_items,
            )
            if not video_path or not os.path.exists(video_path):
                raise Exception("Video generation failed")
            video_size = os.path.getsize(video_path)
            logger.info(f"Generated video: {video_path} ({video_size} bytes)")

            # Record which method was used
            from .video import video_generator
            generation_method = video_generator.last_generation_method

            return {
                "success": True,
                "video_path": video_path,
                "file_size": video_size,
                "step": "video_generation",
                "files": [video_path],
                "generation_method": generation_method,
                "used_stock_footage": video_generator.last_used_stock_footage,
            }
        except Exception as e:
            logger.error(f"Step 6 failed: {e}")
            return {"success": False, "error": str(e), "step": "video_generation"}

    async def _step7_generate_metadata(
        self, news_items: List[Dict[str, Any]], script_content: str, mode: str
    ) -> Dict[str, Any]:
        logger.info("Step 7: Starting metadata generation...")
        try:
            metadata = generate_youtube_metadata(news_items, script_content, mode)
            if not metadata:
                raise Exception("Metadata generation failed")
            logger.info(f"Generated metadata: {metadata.get('title', 'No title')}")

            # メタデータを記録（CSV + Google Sheets）
            try:
                metadata_storage.save_metadata(
                    metadata=metadata,
                    run_id=self.run_id,
                    mode=mode,
                    news_items=news_items
                )
                logger.info("Metadata saved to storage")
            except Exception as e:
                logger.warning(f"Failed to save metadata to storage: {e}")

            return {
                "success": True,
                "metadata": metadata,
                "title": metadata.get("title", ""),
                "step": "metadata_generation",
            }
        except Exception as e:
            logger.error(f"Step 7 failed: {e}")
            fallback_metadata = {
                "title": f"経済ニュース解説 - {datetime.now().strftime('%Y/%m/%d')}",
                "description": "経済ニュースの解説動画です。",
                "tags": ["経済ニュース", "投資", "株式市場"],
                "category": "News & Politics",
            }
            return {
                "success": True,
                "metadata": fallback_metadata,
                "title": fallback_metadata["title"],
                "step": "metadata_generation",
                "fallback": True,
            }

    async def _step8_generate_thumbnail(
        self, metadata: Dict[str, Any], news_items: List[Dict[str, Any]], mode: str
    ) -> Dict[str, Any]:
        logger.info("Step 8: Starting thumbnail generation...")
        try:
            thumbnail_path = generate_thumbnail(
                title=metadata.get("title", "Economic News"), news_items=news_items, mode=mode
            )
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"Generated thumbnail: {thumbnail_path}")
                return {
                    "success": True,
                    "thumbnail_path": thumbnail_path,
                    "step": "thumbnail_generation",
                    "files": [thumbnail_path],
                }
            else:
                logger.warning("Thumbnail generation failed, continuing without thumbnail")
                return {
                    "success": True,
                    "thumbnail_path": None,
                    "step": "thumbnail_generation",
                    "warning": "Thumbnail generation failed",
                    "files": [],
                }
        except Exception as e:
            logger.warning(f"Step 8 warning: {e}")
            return {
                "success": True,
                "thumbnail_path": None,
                "step": "thumbnail_generation",
                "error": str(e),
                "files": [],
            }

    async def _step9_upload_to_drive(
        self, video_path: str, thumbnail_path: str, subtitle_path: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("Step 9: Starting Drive upload...")
        try:
            upload_result = upload_video_package(
                video_path=video_path, thumbnail_path=thumbnail_path, subtitle_path=subtitle_path, metadata=metadata
            )
            if upload_result.get("error"):
                logger.warning(f"Drive upload warning: {upload_result['error']}")
                return {
                    "success": True,
                    "drive_result": upload_result,
                    "step": "drive_upload",
                    "warning": upload_result["error"],
                }
            logger.info(f"Uploaded to Drive: {upload_result.get('package_folder_id', 'Unknown')}")
            return {
                "success": True,
                "drive_result": upload_result,
                "folder_id": upload_result.get("package_folder_id"),
                "video_link": upload_result.get("video_link"),
                "step": "drive_upload",
            }
        except Exception as e:
            logger.warning(f"Step 9 warning: {e}")
            return {"success": True, "drive_result": {"error": str(e)}, "step": "drive_upload", "error": str(e)}

    async def _step10_upload_to_youtube(
        self, video_path: str, metadata: Dict[str, Any], thumbnail_path: str = None
    ) -> Dict[str, Any]:
        logger.info("Step 10: Starting YouTube upload...")
        try:
            youtube_result = youtube_upload(
                video_path=video_path, metadata=metadata, thumbnail_path=thumbnail_path, privacy_status="public"
            )
            if youtube_result.get("error"):
                logger.warning(f"YouTube upload warning: {youtube_result['error']}")
                return {
                    "success": True,
                    "youtube_result": youtube_result,
                    "step": "youtube_upload",
                    "warning": youtube_result["error"],
                }
            video_id = youtube_result.get("video_id")
            video_url = youtube_result.get("video_url")
            logger.info(f"Uploaded to YouTube: {video_id}")
            return {
                "success": True,
                "youtube_result": youtube_result,
                "video_id": video_id,
                "video_url": video_url,
                "step": "youtube_upload",
            }
        except Exception as e:
            logger.warning(f"Step 10 warning: {e}")
            return {"success": True, "youtube_result": {"error": str(e)}, "step": "youtube_upload", "error": str(e)}

    def _get_prompts(self, mode: str = "daily") -> Dict[str, str]:
        """モード別にプロンプトを取得

        Args:
            mode: 実行モード (daily/special/test)

        Returns:
            プロンプトの辞書
        """
        try:
            if sheets_manager:
                return load_prompts_from_sheets(mode)
            else:
                return self._default_prompts()
        except Exception:
            return self._default_prompts()

    def _default_news_prompt(self) -> str:
        return """
今日の重要な経済ニュースを3-5件収集してください。以下の基準で選択してください：

1. 市場への影響度が高い
2. 投資家が注目している
3. 日本経済との関連性がある
4. 信頼性の高い情報源からの情報

各ニュースについて、タイトル、要約、出典、重要ポイントを含めてください。
"""

    def _default_script_prompt(self) -> str:
        return """
提供されたニュース情報をもとに、経済専門家による対談形式の台本を作成してください。

要件：
- 田中氏（経済専門家）と鈴木氏（金融アナリスト）の対談形式
- 専門的だが理解しやすい内容
- 自然な会話の流れ
- 出典情報を適切に言及
- 視聴者にとって価値のある分析を含める
"""

    def _default_prompts(self) -> Dict[str, str]:
        return {
            "prompt_a": self._default_news_prompt(),
            "prompt_b": self._default_script_prompt(),
        }

    def _handle_workflow_failure(self, step_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        error_message = f"{step_name} failed: {result.get('error', 'Unknown error')}"
        logger.error(error_message)
        asyncio.create_task(self._notify_workflow_error(Exception(error_message)))
        self._update_run_status("failed", result)
        return {"success": False, "failed_step": step_name, "error": result.get("error"), "run_id": self.run_id}

    def _compile_final_result(self, *step_results, execution_time: float) -> Dict[str, Any]:
        from app.models.workflow import WorkflowResult

        # Extract data from step results
        step2 = step_results[1]  # script_generation
        step7 = step_results[6]  # metadata_generation
        step8 = step_results[7]  # thumbnail_generation
        _step9 = step_results[8]  # drive_upload (unused but kept for clarity)
        step10 = step_results[9]  # youtube_upload

        # Create WorkflowResult with rich data
        workflow_result = WorkflowResult(
            success=True,
            run_id=self.run_id,
            mode=self.mode,
            execution_time_seconds=execution_time,
            news_count=step_results[0].get("count", 0),
            script_length=step_results[1].get("length", 0),
            video_path=step_results[5].get("video_path"),
            video_id=step10.get("video_id"),
            video_url=step10.get("video_url"),
            title=step7.get("metadata", {}).get("title"),
            thumbnail_path=step8.get("thumbnail_path"),
            # Quality metrics (extract if available)
            wow_score=self._extract_wow_score(step2),
            japanese_purity=self._extract_japanese_purity(step2),
            # Hook classification
            hook_type=self._classify_hook_from_script(step2),
            topic=self._extract_topic(step_results[0]),
            completed_steps=sum(1 for s in step_results if s.get("success")),
            failed_steps=sum(1 for s in step_results if not s.get("success")),
            total_steps=10,
            generated_files=self.generated_files,
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
            "generated_files": self.generated_files,
            "steps": {},
        }
        step_names = [
            "news_collection",
            "script_generation",
            "audio_synthesis",
            "audio_transcription",
            "subtitle_alignment",
            "video_generation",
            "metadata_generation",
            "thumbnail_generation",
            "drive_upload",
            "youtube_upload",
        ]
        for i, step_result in enumerate(step_results):
            if i < len(step_names):
                result["steps"][step_names[i]] = step_result
        result["news_count"] = step_results[0].get("count", 0)
        result["script_length"] = step_results[1].get("length", 0)
        result["video_path"] = step_results[5].get("video_path")
        result["video_id"] = step_results[9].get("video_id")
        result["video_url"] = step_results[9].get("video_url")
        result["drive_folder"] = step_results[8].get("folder_id")
        return result

    def _extract_wow_score(self, script_step: Dict) -> Optional[float]:
        """Extract WOW score from script generation step."""
        # TODO: Extract from CrewAI output if available
        return None

    def _extract_japanese_purity(self, script_step: Dict) -> Optional[float]:
        """Extract Japanese purity from script generation step."""
        # TODO: Extract from quality check if available
        return None

    def _classify_hook_from_script(self, script_step: Dict) -> str:
        """Classify hook strategy from script content."""
        script_content = script_step.get("script", "")
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

    def _extract_topic(self, news_step: Dict) -> str:
        """Extract main topic from news items."""
        news_items = news_step.get("news_items", [])
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
        message = f"YouTube動画生成ワークフローを開始しました\nモード: {mode}\nRun ID: {self.run_id}"
        discord_notifier.notify(message, level="info", title="ワークフロー開始")

    async def _notify_workflow_success(self, result: Dict[str, Any]):
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
        message = f"YouTube動画生成でエラーが発生しました\nエラー: {str(error)}\nRun ID: {self.run_id}"
        discord_notifier.notify(message, level="error", title="ワークフローエラー")

    def _update_run_status(self, status: str, result: Dict[str, Any]):
        try:
            if sheets_manager and self.run_id:
                sheets_manager.update_run(self.run_id, status=status, error_log=str(result))
        except Exception as e:
            logger.warning(f"Failed to update run status: {e}")

    def _cleanup_temp_files(self):
        cleaned_count = 0
        for file_path in self.generated_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary files")


# グローバルワークフローインスタンス
workflow = YouTubeWorkflow()


async def run_daily_workflow() -> Dict[str, Any]:
    return await workflow.execute_full_workflow("daily")


async def run_special_workflow() -> Dict[str, Any]:
    return await workflow.execute_full_workflow("special")


async def run_test_workflow() -> Dict[str, Any]:
    return await workflow.execute_full_workflow("test")


if __name__ == "__main__":
    import sys

    async def main():
        mode = sys.argv[1] if len(sys.argv) > 1 else "test"
        print(f"Starting YouTube workflow in {mode} mode...")
        try:
            result = await workflow.execute_full_workflow(mode)
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
