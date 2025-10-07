import logging
import os
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Dict, List

import yaml
from app.align_subtitles import align_script_with_stt, export_srt
from app.config import cfg
from app.config.settings import settings
from app.drive import upload_video_package
from app.metadata import generate_youtube_metadata
from app.metadata_storage import metadata_storage
from app.prompts import get_default_news_collection_prompt, get_default_script_generation_prompt
from app.search_news import collect_news as collect_news_sync
from app.script_gen import ScriptGenerator, generate_dialogue
from app.services.file_archival import FileArchivalManager
from app.services.media.qa_pipeline import MediaQAPipeline
from app.services.script import ScriptFormatError, ensure_dialogue_structure
from app.services.script.validator import Script
from app.services.video_review import get_video_review_service
from app.services.visual_design import create_unified_design
from app.sheets import load_prompts as load_prompts_from_sheets
from app.sheets import sheets_manager
from app.stt import transcribe_long_audio
from app.thumbnail import generate_thumbnail
from app.tts import synthesize_script
from app.utils import FileUtils
from app.video import generate_video, video_generator
from app.youtube import upload_video as youtube_upload
from .artifacts import GeneratedArtifact
from .base import StepResult, WorkflowContext, WorkflowStep
from .ports import NewsCollectionPort, SyncNewsCollectionAdapter
logger = logging.getLogger(__name__)

class CollectNewsStep(WorkflowStep):

    def __init__(self, news_port: NewsCollectionPort | None = None) -> None:
        self._news_port = news_port or SyncNewsCollectionAdapter(collect_news_sync)

    @property
    def step_name(self) -> str:
        return 'news_collection'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 1: Starting {self.step_name}...')
        try:
            prompt_a = self._get_prompt(context.mode)
            if sheets_manager and context.run_id:
                sheets_manager.record_prompt_used(context.run_id, 'prompt_a', prompt_a)
            news_items = await self._news_port.collect_news(prompt_a, context.mode)
            if not news_items:
                return self._failure('No news items collected')
            logger.info(f'Collected {len(news_items)} news items')
            context.set('news_items', news_items)
            return self._success(data={'news_items': news_items, 'count': len(news_items)})
        except Exception as e:
            logger.error(f'Step 1 failed: {e}')
            return self._failure(str(e))

    def _get_prompt(self, mode: str) -> str:
        try:
            if sheets_manager:
                prompts = load_prompts_from_sheets(mode)
                return prompts.get('prompt_a', self._default_prompt())
        except Exception:
            pass
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return get_default_news_collection_prompt()

class GenerateScriptStep(WorkflowStep):

    def __init__(
        self,
        *,
        script_generator: ScriptGenerator | None = None,
        legacy_generator: Callable[[List[Dict[str, Any]], str, int | None, bool], str] | None = None,
    ) -> None:
        self._script_generator: ScriptGenerator | None = script_generator
        self._legacy_generator = legacy_generator or generate_dialogue

    @property
    def step_name(self) -> str:
        return 'script_generation'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 2: Starting {self.step_name}...')
        news_items = context.get('news_items')
        if not news_items:
            return self._failure('No news items in context')
        use_crewai = getattr(cfg, 'use_crewai_script_generation', True)
        logger.info(f"CrewAI WOW Script Generation: {('ENABLED' if use_crewai else 'DISABLED')}")
        try:
            script_payload: Dict[str, Any] = {}
            if use_crewai:
                script_payload = await self._generate_with_crewai(news_items)
                script_content = script_payload['script']
            else:
                script_content = await self._generate_legacy(context, news_items)
            if not script_content or len(script_content) < 100:
                return self._failure('Generated script too short or empty')
            try:
                validation = ensure_dialogue_structure(script_content)
            except ScriptFormatError as err:
                logger.error(f'Script format validation failed: {err}')
                return self._failure(str(err))
            script_content = validation.normalized_script
            if validation.warnings:
                for issue in validation.warnings[:5]:
                    logger.warning('Script normalization warning (line %s): %s', issue.line_number, issue.message)
            script_path = FileUtils.get_temp_file(prefix='script_', suffix='.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            crew_result = script_payload.get('crew_result')
            crew_mapping = crew_result if isinstance(crew_result, Mapping) else {}
            structured_script = script_payload.get('structured_script') or crew_mapping.get('structured_script')
            structured_script_yaml = script_payload.get('structured_script_yaml') or crew_mapping.get('structured_script_yaml')
            context_updates = {
                'script_content': script_content,
                'script_path': script_path,
                'script_validation': validation.to_dict(),
            }
            if crew_result:
                context_updates['crew_result'] = crew_result
            if structured_script:
                context_updates['script_structured'] = structured_script
            if isinstance(structured_script_yaml, str):
                context_updates['script_structured_yaml'] = structured_script_yaml
            for key, value in context_updates.items():
                context.set(key, value)
            logger.info(f'Generated script: {len(script_content)} characters')
            result_data = {'script': script_content, 'script_path': script_path, 'length': len(script_content), 'quality_checked': use_crewai or cfg.use_three_stage_quality_check, 'used_crewai': use_crewai, 'validation': validation.to_dict()}
            metadata = crew_mapping.get('metadata') if crew_mapping else {}
            if metadata:
                result_data['script_metrics'] = metadata
                if 'japanese_purity_score' in metadata:
                    result_data['japanese_purity_score'] = metadata['japanese_purity_score']
            if structured_script:
                result_data['structured_script'] = structured_script
            if isinstance(structured_script_yaml, str):
                result_data['structured_script_yaml'] = structured_script_yaml
            return self._success(data=result_data, files=[script_path])
        except Exception as e:
            logger.error(f'Step 2 failed: {e}')
            return self._failure(str(e))

    async def _generate_with_crewai(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info('🚀 Using CrewAI WOW Script Creation Crew...')
        payload = self._get_script_generator().generate_crewai_payload(
            news_items,
            target_duration_minutes=cfg.max_video_duration_minutes,
        )
        logger.info('Script preview (first 200 chars): %r', payload['script'][:200])
        return payload

    async def _generate_legacy(self, context: WorkflowContext, news_items: List[Dict[str, Any]]) -> str:
        logger.info(f"3-stage quality check: {('ENABLED' if cfg.use_three_stage_quality_check else 'DISABLED')}")
        prompt_b = self._get_prompt(context.mode)
        if sheets_manager and context.run_id:
            sheets_manager.record_prompt_used(context.run_id, 'prompt_b', prompt_b)
        return self._legacy_generator(
            news_items,
            prompt_b,
            target_duration_minutes=cfg.max_video_duration_minutes,
            use_quality_check=cfg.use_three_stage_quality_check,
        )

    def _get_prompt(self, mode: str) -> str:
        try:
            if sheets_manager:
                prompts = load_prompts_from_sheets(mode)
                return prompts.get('prompt_b', self._default_prompt())
        except Exception:
            pass
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return get_default_script_generation_prompt()

    def _get_script_generator(self) -> ScriptGenerator:
        if self._script_generator is None:
            self._script_generator = ScriptGenerator(api_key=settings.api_keys.get('gemini'))
        return self._script_generator

class GenerateVisualDesignStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'visual_design_generation'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 2.5: Starting {self.step_name}...')
        news_items = context.get('news_items')
        script_content = context.get('script_content')
        if not news_items or not script_content:
            logger.warning('Missing news_items or script_content, using default design')
            from app.background_theme import get_theme_manager
            from app.services.visual_design import UnifiedVisualDesign
            theme_manager = get_theme_manager()
            default_theme = theme_manager.select_theme_for_ab_test()
            design = UnifiedVisualDesign(theme_name=default_theme.name, background_theme=default_theme, sentiment='neutral', primary_color=(0, 120, 215), accent_color=(255, 215, 0), text_color=(255, 255, 255))
        else:
            try:
                design = create_unified_design(news_items=news_items, script_content=script_content, mode=context.mode)
            except Exception as e:
                logger.error(f'Failed to create unified design: {e}, using default')
                from app.background_theme import get_theme_manager
                from app.services.visual_design import UnifiedVisualDesign
                theme_manager = get_theme_manager()
                default_theme = theme_manager.select_theme_for_ab_test()
                design = UnifiedVisualDesign(theme_name=default_theme.name, background_theme=default_theme, sentiment='neutral', primary_color=(0, 120, 215), accent_color=(255, 215, 0), text_color=(255, 255, 255))
        context.set('visual_design', design)
        context.set('visual_design_dict', design.to_dict())
        logger.info(f'Generated visual design: theme={design.theme_name}, sentiment={design.sentiment}, primary={design.primary_color}')
        return self._success(data={'theme_name': design.theme_name, 'sentiment': design.sentiment, 'primary_color': design.primary_color})

class SynthesizeAudioStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'audio_synthesis'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 5: Starting {self.step_name}...')
        script_content = context.get('script_content')
        if not script_content:
            return self._failure('No script content in context')
        try:
            validation = ensure_dialogue_structure(script_content)
            if validation.normalized_script != script_content:
                script_content = validation.normalized_script
                context.set('script_content', script_content)
                logger.info('Script content re-normalized before TTS synthesis')
        except ScriptFormatError as err:
            logger.error(f'Script format validation failed before TTS: {err}')
            return self._failure(str(err))
        try:
            structured_script = context.get('script_structured')
            structured_yaml = context.get('script_structured_yaml')
            dialogues = None
            if not structured_script and isinstance(structured_yaml, str):
                try:
                    structured_script = yaml.safe_load(structured_yaml) or {}
                    context.set('script_structured', structured_script)
                except yaml.YAMLError as exc:
                    logger.debug(f'Failed to restore structured script from YAML: {exc}')
            if structured_script:
                try:
                    script_model = Script.model_validate(structured_script)
                    dialogues = script_model.dialogues
                except Exception as exc:
                    logger.debug(f'Failed to restore structured script for TTS: {exc}')
            audio_paths = await synthesize_script(script_content, dialogues=dialogues)
            if not audio_paths:
                return self._failure('Audio synthesis failed')
            main_audio_path = audio_paths[0]
            context.set('audio_path', main_audio_path)
            logger.info(f'Generated audio: {main_audio_path}')
            return self._success(data={'audio_path': main_audio_path, 'audio_paths': audio_paths}, files=audio_paths)
        except Exception as e:
            logger.error(f'Step 5 failed: {e}')
            return self._failure(str(e))

class TranscribeAudioStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'audio_transcription'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 6: Starting {self.step_name}...')
        audio_path = context.get('audio_path')
        if not audio_path:
            return self._failure('No audio path in context')
        try:
            stt_words = transcribe_long_audio(audio_path)
            if not stt_words:
                return self._failure('Audio transcription failed')
            context.set('stt_words', stt_words)
            logger.info(f'Transcribed {len(stt_words)} words')
            return self._success(data={'stt_words': stt_words, 'word_count': len(stt_words)})
        except Exception as e:
            logger.error(f'Step 6 failed: {e}')
            return self._failure(str(e))

class AlignSubtitlesStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'subtitle_alignment'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 7: Starting {self.step_name}...')
        script_content = context.get('script_content')
        stt_words = context.get('stt_words')
        if not script_content:
            return self._failure('No script content in context')
        if not stt_words:
            return self._failure('No STT words in context')
        try:
            aligned_subtitles = align_script_with_stt(script_content, stt_words)
            if not aligned_subtitles:
                return self._failure('Subtitle alignment failed')
            subtitle_path = FileUtils.get_temp_file(prefix='subtitles_', suffix='.srt')
            export_srt(aligned_subtitles, subtitle_path)
            context.set('subtitle_path', subtitle_path)
            context.set('aligned_subtitles', aligned_subtitles)
            logger.info(f'Generated subtitles: {len(aligned_subtitles)} segments')
            return self._success(data={'aligned_subtitles': aligned_subtitles, 'subtitle_path': subtitle_path, 'segment_count': len(aligned_subtitles)}, files=[subtitle_path])
        except Exception as e:
            logger.error(f'Step 7 failed: {e}')
            return self._failure(str(e))

class GenerateVideoStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'video_generation'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 8: Starting {self.step_name}...')
        audio_path = context.get('audio_path')
        subtitle_path = context.get('subtitle_path')
        script_content = context.get('script_content', '')
        news_items = context.get('news_items', [])
        metadata = context.get('metadata', {})
        broll_path = context.get('broll_path')
        use_stock_override = context.get('use_stock_footage')
        if not audio_path or not subtitle_path:
            return self._failure('Missing audio_path or subtitle_path in context')
        try:
            broll_metadata = None
            generated_files: List[GeneratedArtifact] = []
            should_attempt_broll = settings.enable_stock_footage and use_stock_override is not False and (not broll_path)
            if should_attempt_broll:
                if not (settings.pexels_api_key or settings.pixabay_api_key):
                    logger.info('No stock footage API keys configured; continuing without B-roll')
                    context.set('use_stock_footage', False)
                    use_stock_override = False
                else:
                    try:
                        broll_result = video_generator.prepare_broll_assets(audio_path=audio_path, script_content=script_content, news_items=news_items)
                    except Exception as exc:
                        logger.warning('B-roll preparation failed but workflow will continue: %s', exc)
                        context.set('use_stock_footage', False)
                        use_stock_override = False
                    else:
                        if broll_result and broll_result.get('broll_path'):
                            candidate_path = broll_result.get('broll_path')
                            if candidate_path and os.path.exists(candidate_path):
                                broll_path = candidate_path
                                broll_metadata = broll_result
                                context.set('broll_path', broll_path)
                                context.set('broll_metadata', broll_result)
                                context.set('broll_keywords', broll_result.get('keywords', []))
                                context.set('broll_clip_paths', broll_result.get('clip_paths', []))
                                context.set('broll_source', broll_result.get('source'))
                                context.set('use_stock_footage', True)
                                use_stock_override = True
                                logger.info(f'Prepared B-roll sequence: {broll_path}')
                            else:
                                logger.info('B-roll assets were returned without a valid path; using static background')
                                context.set('use_stock_footage', False)
                                use_stock_override = False
                        else:
                            logger.info('B-roll assets unavailable; continuing with static background')
                            context.set('use_stock_footage', False)
                            use_stock_override = False
            video_path = generate_video(audio_path=audio_path, subtitle_path=subtitle_path, title=metadata.get('title', 'Economic News Analysis'), script_content=script_content, news_items=news_items, use_stock_footage=use_stock_override, broll_path=broll_path)
            if not video_path or not os.path.exists(video_path):
                return self._failure('Video generation failed')
            archival_manager = FileArchivalManager()
            timestamp = context.get('output_timestamp') or datetime.now().strftime('%Y%m%d_%H%M%S')
            title = metadata.get('title', 'Untitled')
            thumbnail_path = context.get('thumbnail_path')
            files_to_archive = {'video': video_path, 'audio': audio_path, 'subtitle': subtitle_path, 'script': context.get('script_path')}
            if thumbnail_path and os.path.exists(thumbnail_path):
                files_to_archive['thumbnail'] = thumbnail_path
            if broll_path and os.path.exists(broll_path):
                files_to_archive['broll'] = broll_path
            archived_files = archival_manager.archive_workflow_files(run_id=context.run_id, timestamp=timestamp, title=title, files=files_to_archive)
            archived_video = archived_files.get('video', video_path)
            context.set('video_path', archived_video)
            context.set('archived_audio_path', archived_files.get('audio'))
            context.set('archived_subtitle_path', archived_files.get('subtitle'))
            if 'broll' in archived_files:
                context.set('archived_broll_path', archived_files['broll'])
            if 'thumbnail' in archived_files:
                context.set('thumbnail_path', archived_files['thumbnail'])
            video_size = os.path.getsize(archived_video)
            from app.video import video_generator
            generation_method = video_generator.last_generation_method
            logger.info(f'Generated and archived video: {archived_video} ({video_size} bytes)')
            generated_files.append(
                GeneratedArtifact(
                    path=video_path,
                    kind="video_raw",
                    description="Pre-archive render output",
                )
            )
            archived_broll = archived_files.get('broll')
            if broll_path and os.path.exists(broll_path):
                generated_files.append(
                    GeneratedArtifact(
                        path=broll_path,
                        kind="broll_raw",
                        description="Generated B-roll sequence",
                    )
                )
            generated_files.append(
                GeneratedArtifact(
                    path=archived_video,
                    persisted=True,
                    cleanup=False,
                    kind="video_archived",
                    description="Archived video master",
                )
            )
            if archived_broll:
                generated_files.append(
                    GeneratedArtifact(
                        path=archived_broll,
                        persisted=True,
                        cleanup=False,
                        kind="broll_archived",
                        description="Archived B-roll sequence",
                    )
                )
            return self._success(data={'video_path': archived_video, 'file_size': video_size, 'generation_method': generation_method, 'used_stock_footage': video_generator.last_used_stock_footage, 'archived_files': archived_files, 'archived_broll_path': archived_broll, 'broll_metadata': broll_metadata or video_generator.last_broll_metadata, 'broll_path': broll_path}, files=generated_files)
        except Exception as e:
            logger.error(f'Step 8 failed: {e}')
            return self._failure(str(e))

class QualityAssuranceStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'media_quality_assurance'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 9: Starting {self.step_name}...')
        qa_config = getattr(cfg, 'media_quality', None)
        if not qa_config or not qa_config.enabled:
            context.set('qa_passed', True)
            context.set('qa_retry_request', None)
            return self._success(data={'qa_passed': True, 'qa_enabled': False, 'skipped': True})
        pipeline = MediaQAPipeline(qa_config)
        attempt_count = context.get('qa_attempt', 0) + 1
        context.set('qa_attempt', attempt_count)
        context.set('qa_retry_request', None)
        report = pipeline.run(run_id=context.run_id, mode=context.mode, script_path=context.get('script_path'), script_content=context.get('script_content'), audio_path=context.get('archived_audio_path') or context.get('audio_path'), subtitle_path=context.get('archived_subtitle_path') or context.get('subtitle_path'), video_path=context.get('video_path'))
        context.set('qa_report', report.dict())
        context.set('qa_report_path', report.report_path)
        context.set('qa_passed', report.passed)
        if report.warnings():
            warning_names = ', '.join((check.name for check in report.warnings()))
            logger.warning(f'Media QA warnings: {warning_names}')
        blocking = pipeline.should_block(report, mode=context.mode)
        failures = report.blocking_failures()
        if failures and (not blocking):
            failure_names = ', '.join((check.name for check in failures))
            logger.warning('Blocking QA failures detected but bypassed due to configuration: %s', failure_names)
        if blocking:
            failed_names = ', '.join((check.name for check in failures)) or 'unknown'
            message = f'QA gate blocked publication due to: {failed_names}'
            logger.error(message)
            if qa_config.gating.retry_attempts > 0:
                context.set('qa_retry_request', {'start_step': qa_config.gating.retry_start_step, 'reason': message, 'attempt': attempt_count})
            return self._failure(message)
        context.set('qa_retry_request', None)
        return self._success(data={'qa_passed': report.passed, 'qa_report_path': report.report_path, 'qa_blocking': blocking})

class GenerateMetadataStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'metadata_generation'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 3: Starting {self.step_name}...')
        news_items = context.get('news_items')
        script_content = context.get('script_content')
        if not news_items or not script_content:
            return self._failure('Missing news_items or script_content in context')
        try:
            metadata = generate_youtube_metadata(news_items, script_content, context.mode)
            if not metadata:
                return self._failure('Metadata generation failed')
            context.set('metadata', metadata)
            metadata_storage.save_metadata(metadata=metadata, run_id=context.run_id, mode=context.mode, news_items=news_items)
            logger.info('Metadata saved to storage')
            logger.info(f"Generated metadata: {metadata.get('title', 'No title')}")
            return self._success(data={'metadata': metadata, 'title': metadata.get('title', '')})
        except Exception as e:
            logger.error(f'Step 3 failed: {e}')
            fallback_metadata = {'title': f"経済ニュース解説 - {datetime.now().strftime('%Y/%m/%d')}", 'description': '経済ニュースの解説動画です。', 'tags': ['経済ニュース', '投資', '株式市場'], 'category': 'News & Politics'}
            context.set('metadata', fallback_metadata)
            return self._success(data={'metadata': fallback_metadata, 'title': fallback_metadata['title'], 'fallback': True})

class GenerateThumbnailStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'thumbnail_generation'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 4: Starting {self.step_name}...')
        metadata = context.get('metadata')
        news_items = context.get('news_items')
        visual_design = context.get('visual_design')
        if not metadata or not news_items:
            logger.warning('Missing metadata or news_items, skipping thumbnail')
            return self._success(data={'thumbnail_path': None, 'warning': 'Missing metadata or news_items'})
        try:
            style = visual_design.get_thumbnail_style() if visual_design else 'economic_blue'
            thumbnail_path = generate_thumbnail(title=metadata.get('title', 'Economic News'), news_items=news_items, mode=context.mode, style=style)
            logger.info(f'Using visual design style: {style}')
            if thumbnail_path and os.path.exists(thumbnail_path):
                context.set('thumbnail_path', thumbnail_path)
                logger.info(f'Generated thumbnail: {thumbnail_path}')
                return self._success(data={'thumbnail_path': thumbnail_path}, files=[thumbnail_path])
            else:
                logger.warning('Thumbnail generation failed, continuing without thumbnail')
                return self._success(data={'thumbnail_path': None, 'warning': 'Thumbnail generation failed'})
        except Exception as e:
            logger.warning(f'Step 4 warning: {e}')
            return self._success(data={'thumbnail_path': None, 'error': str(e)})

class UploadToDriveStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'drive_upload'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 10: Starting {self.step_name}...')
        video_path = context.get('video_path')
        thumbnail_path = context.get('thumbnail_path')
        subtitle_path = context.get('subtitle_path')
        metadata = context.get('metadata')
        if not video_path:
            return self._failure('No video_path in context')
        try:
            upload_result = upload_video_package(video_path=video_path, thumbnail_path=thumbnail_path, subtitle_path=subtitle_path, metadata=metadata)
            if upload_result.get('error'):
                logger.warning(f"Drive upload warning: {upload_result['error']}")
                return self._success(data={'drive_result': upload_result, 'warning': upload_result['error']})
            logger.info(f"Uploaded to Drive: {upload_result.get('package_folder_id', 'Unknown')}")
            return self._success(data={'drive_result': upload_result, 'folder_id': upload_result.get('package_folder_id'), 'video_link': upload_result.get('video_link')})
        except Exception as e:
            logger.warning(f'Step 10 warning: {e}')
            return self._success(data={'drive_result': {'error': str(e)}, 'error': str(e)})

class UploadToYouTubeStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'youtube_upload'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 11: Starting {self.step_name}...')
        video_path = context.get('video_path')
        metadata = context.get('metadata')
        thumbnail_path = context.get('thumbnail_path')
        subtitle_path = context.get('subtitle_path')
        if not video_path or not metadata:
            return self._failure('Missing video_path or metadata in context')
        try:
            youtube_result = youtube_upload(video_path=video_path, metadata=metadata, thumbnail_path=thumbnail_path, subtitle_path=subtitle_path, privacy_status='public')
            if youtube_result.get('error'):
                logger.warning(f"YouTube upload warning: {youtube_result['error']}")
                return self._success(data={'youtube_result': youtube_result, 'warning': youtube_result['error']})
            video_id = youtube_result.get('video_id')
            video_url = youtube_result.get('video_url')
            context.set('video_id', video_id)
            context.set('video_url', video_url)
            logger.info(f'Uploaded to YouTube: {video_id}')
            return self._success(data={'youtube_result': youtube_result, 'video_id': video_id, 'video_url': video_url})
        except Exception as e:
            logger.warning(f'Step 11 warning: {e}')
            return self._success(data={'youtube_result': {'error': str(e)}, 'error': str(e)})

class ReviewVideoStep(WorkflowStep):

    @property
    def step_name(self) -> str:
        return 'video_review'

    async def execute(self, context: WorkflowContext) -> StepResult:
        logger.info(f'Step 12: Starting {self.step_name}...')
        review_config = getattr(cfg, 'video_review', None)
        if not review_config or not getattr(review_config, 'enabled', False):
            return self._success(data={'review_enabled': False, 'skipped': True})
        video_path = context.get('video_path')
        if not video_path or not os.path.exists(video_path):
            logger.warning('Video review skipped: video file missing')
            return self._success(data={'review_enabled': True, 'skipped': True, 'reason': 'missing_video'})
        metadata = context.get('metadata') or {}
        meta_payload = {}
        title = metadata.get('title')
        if title:
            meta_payload['title'] = str(title)
        duration_hint = metadata.get('duration') or metadata.get('estimated_watch_time')
        if duration_hint:
            meta_payload['duration'] = str(duration_hint)
        video_id = context.get('video_id') or context.run_id
        review_service = get_video_review_service()
        try:
            review_result = review_service.review_video(video_path=video_path, video_id=video_id, metadata=meta_payload or None)
        except Exception as exc:
            logger.warning(f'Video review failed: {exc}')
            return self._success(data={'review_enabled': True, 'skipped': True, 'error': str(exc)})
        review_dict = review_result.to_dict()
        context.set('video_review', review_dict)
        if review_result.feedback:
            context.set('video_review_summary', review_result.feedback.summary)
        screenshot_paths = [shot.path for shot in review_result.screenshots if shot.path]
        context.set('video_review_screenshots', screenshot_paths)
        return self._success(data={'review_enabled': True, 'skipped': False, 'review_summary': review_result.feedback.summary if review_result.feedback else None, 'screenshots_captured': len(screenshot_paths)}, files=screenshot_paths)