"""
メインワークフローモジュール

YouTube動画自動生成の全工程を統合・実行します。
10ステップの処理を順序立てて実行し、エラーハンドリングと進捗通知を行います。
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import traceback

# 各モジュールをインポート
from app.config import cfg
from app.slack import discord_notifier
from app.sheets import sheets_manager
from app.search_news import collect_news
from app.script_gen import generate_dialogue
from app.tts import synthesize_script
from app.stt import transcribe_long_audio
from app.align_subtitles import align_script_with_stt, export_srt
from app.video import generate_video
from app.metadata import generate_youtube_metadata
from app.thumbnail import generate_thumbnail
from app.drive import upload_video_package
from app.youtube import upload_video as youtube_upload

logger = logging.getLogger(__name__)

class YouTubeWorkflow:
    """YouTube動画自動生成ワークフロー"""

    def __init__(self):
        self.run_id = None
        self.workflow_state = {}
        self.generated_files = []

    async def execute_full_workflow(self, mode: str = "daily") -> Dict[str, Any]:
        """
        完全なワークフローを実行

        Args:
            mode: 実行モード (daily/special/test)

        Returns:
            実行結果の詳細
        """
        start_time = datetime.now()

        try:
            # 実行開始の準備
            self.run_id = self._initialize_run(mode)
            await self._notify_workflow_start(mode)

            # Step 1: ニュース収集
            step1_result = await self._step1_collect_news(mode)
            if not step1_result.get('success'):
                return self._handle_workflow_failure("Step 1: News Collection", step1_result)

            # Step 2: 台本生成
            step2_result = await self._step2_generate_script(step1_result['news_items'])
            if not step2_result.get('success'):
                return self._handle_workflow_failure("Step 2: Script Generation", step2_result)

            # Step 3: 音声合成
            step3_result = await self._step3_synthesize_audio(step2_result['script'])
            if not step3_result.get('success'):
                return self._handle_workflow_failure("Step 3: Audio Synthesis", step3_result)

            # Step 4: 音声認識（字幕用）
            step4_result = await self._step4_transcribe_audio(step3_result['audio_path'])
            if not step4_result.get('success'):
                return self._handle_workflow_failure("Step 4: Audio Transcription", step4_result)

            # Step 5: 字幕整合
            step5_result = await self._step5_align_subtitles(
                step2_result['script'], step4_result['stt_words']
            )
            if not step5_result.get('success'):
                return self._handle_workflow_failure("Step 5: Subtitle Alignment", step5_result)

            # Step 6: 動画生成
            step6_result = await self._step6_generate_video(
                step3_result['audio_path'], step5_result['subtitle_path']
            )
            if not step6_result.get('success'):
                return self._handle_workflow_failure("Step 6: Video Generation", step6_result)

            # Step 7: メタデータ生成
            step7_result = await self._step7_generate_metadata(
                step1_result['news_items'], step2_result['script'], mode
            )

            # Step 8: サムネイル生成
            step8_result = await self._step8_generate_thumbnail(
                step7_result['metadata'], step1_result['news_items'], mode
            )

            # Step 9: Google Drive アップロード
            step9_result = await self._step9_upload_to_drive(
                step6_result['video_path'],
                step8_result.get('thumbnail_path'),
                step5_result['subtitle_path'],
                step7_result['metadata']
            )

            # Step 10: YouTube アップロード
            step10_result = await self._step10_upload_to_youtube(
                step6_result['video_path'],
                step7_result['metadata'],
                step8_result.get('thumbnail_path')
            )

            # ワークフロー完了
            execution_time = (datetime.now() - start_time).total_seconds()
            result = self._compile_final_result(
                step1_result, step2_result, step3_result, step4_result, step5_result,
                step6_result, step7_result, step8_result, step9_result, step10_result,
                execution_time
            )

            await self._notify_workflow_success(result)
            self._update_run_status("completed", result)

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_result = {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
                'execution_time': execution_time,
                'run_id': self.run_id
            }

            await self._notify_workflow_error(e)
            self._update_run_status("failed", error_result)

            return error_result

        finally:
            # 一時ファイルのクリーンアップ
            self._cleanup_temp_files()

    def _initialize_run(self, mode: str) -> str:
        """実行の初期化"""
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
        """Step 1: ニュース収集"""
        logger.info("Step 1: Starting news collection...")

        try:
            # プロンプトを取得
            prompt_a = self._get_news_collection_prompt(mode)

            # ニュース収集実行
            news_items = collect_news(prompt_a, mode)

            if not news_items:
                raise Exception("No news items collected")

            logger.info(f"Collected {len(news_items)} news items")

            return {
                'success': True,
                'news_items': news_items,
                'count': len(news_items),
                'step': 'news_collection'
            }

        except Exception as e:
            logger.error(f"Step 1 failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'news_collection'
            }

    async def _step2_generate_script(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Step 2: 台本生成"""
        logger.info("Step 2: Starting script generation...")

        try:
            # プロンプトを取得
            prompt_b = self._get_script_generation_prompt()

            # 台本生成実行
            script_content = generate_dialogue(
                news_items,
                prompt_b,
                target_duration=cfg.max_video_duration_minutes
            )

            if not script_content or len(script_content) < 100:
                raise Exception("Generated script too short or empty")

            # 台本をファイルに保存
            script_path = f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            self.generated_files.append(script_path)
            logger.info(f"Generated script: {len(script_content)} characters")

            return {
                'success': True,
                'script': script_content,
                'script_path': script_path,
                'length': len(script_content),
                'step': 'script_generation'
            }

        except Exception as e:
            logger.error(f"Step 2 failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'script_generation'
            }

    async def _step3_synthesize_audio(self, script_content: str) -> Dict[str, Any]:
        """Step 3: 音声合成"""
        logger.info("Step 3: Starting audio synthesis...")

        try:
            # 音声合成実行
            audio_paths = await synthesize_script(script_content)

            if not audio_paths:
                raise Exception("Audio synthesis failed")

            main_audio_path = audio_paths[0]
            self.generated_files.extend(audio_paths)

            logger.info(f"Generated audio: {main_audio_path}")

            return {
                'success': True,
                'audio_path': main_audio_path,
                'audio_paths': audio_paths,
                'step': 'audio_synthesis'
            }

        except Exception as e:
            logger.error(f"Step 3 failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'audio_synthesis'
            }

    async def _step4_transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Step 4: 音声認識"""
        logger.info("Step 4: Starting audio transcription...")

        try:
            # 音声認識実行
            stt_words = transcribe_long_audio(audio_path)

            if not stt_words:
                raise Exception("Audio transcription failed")

            logger.info(f"Transcribed {len(stt_words)} words")

            return {
                'success': True,
                'stt_words': stt_words,
                'word_count': len(stt_words),
                'step': 'audio_transcription'
            }

        except Exception as e:
            logger.error(f"Step 4 failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'audio_transcription'
            }

    async def _step5_align_subtitles(self, script_content: str,
                                   stt_words: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Step 5: 字幕整合"""
        logger.info("Step 5: Starting subtitle alignment...")

        try:
            # 字幕整合実行
            aligned_subtitles = align_script_with_stt(script_content, stt_words)

            if not aligned_subtitles:
                raise Exception("Subtitle alignment failed")

            # SRTファイル出力
            subtitle_path = f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt"
            export_srt(aligned_subtitles, subtitle_path)

            self.generated_files.append(subtitle_path)
            logger.info(f"Generated subtitles: {len(aligned_subtitles)} segments")

            return {
                'success': True,
                'aligned_subtitles': aligned_subtitles,
                'subtitle_path': subtitle_path,
                'segment_count': len(aligned_subtitles),
                'step': 'subtitle_alignment'
            }

        except Exception as e:
            logger.error(f"Step 5 failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'subtitle_alignment'
            }

    async def _step6_generate_video(self, audio_path: str, subtitle_path: str) -> Dict[str, Any]:
        """Step 6: 動画生成"""
        logger.info("Step 6: Starting video generation...")

        try:
            # 動画生成実行
            video_path = generate_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                title="Economic News Analysis"
            )

            if not video_path or not os.path.exists(video_path):
                raise Exception("Video generation failed")

            self.generated_files.append(video_path)

            # 動画情報を取得
            video_size = os.path.getsize(video_path)
            logger.info(f"Generated video: {video_path} ({video_size} bytes)")

            return {
                'success': True,
                'video_path': video_path,
                'file_size': video_size,
                'step': 'video_generation'
            }

        except Exception as e:
            logger.error(f"Step 6 failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'video_generation'
            }

    async def _step7_generate_metadata(self, news_items: List[Dict[str, Any]],
                                     script_content: str, mode: str) -> Dict[str, Any]:
        """Step 7: メタデータ生成"""
        logger.info("Step 7: Starting metadata generation...")

        try:
            # メタデータ生成実行
            metadata = generate_youtube_metadata(news_items, script_content, mode)

            if not metadata:
                raise Exception("Metadata generation failed")

            logger.info(f"Generated metadata: {metadata.get('title', 'No title')}")

            return {
                'success': True,
                'metadata': metadata,
                'title': metadata.get('title', ''),
                'step': 'metadata_generation'
            }

        except Exception as e:
            logger.error(f"Step 7 failed: {e}")
            # フォールバック用の基本メタデータ
            fallback_metadata = {
                'title': f"経済ニュース解説 - {datetime.now().strftime('%Y/%m/%d')}",
                'description': "経済ニュースの解説動画です。",
                'tags': ['経済ニュース', '投資', '株式市場'],
                'category': 'News & Politics'
            }
            return {
                'success': True,
                'metadata': fallback_metadata,
                'title': fallback_metadata['title'],
                'step': 'metadata_generation',
                'fallback': True
            }

    async def _step8_generate_thumbnail(self, metadata: Dict[str, Any],
                                      news_items: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        """Step 8: サムネイル生成"""
        logger.info("Step 8: Starting thumbnail generation...")

        try:
            # サムネイル生成実行
            thumbnail_path = generate_thumbnail(
                title=metadata.get('title', 'Economic News'),
                news_items=news_items,
                mode=mode
            )

            if thumbnail_path and os.path.exists(thumbnail_path):
                self.generated_files.append(thumbnail_path)
                logger.info(f"Generated thumbnail: {thumbnail_path}")

                return {
                    'success': True,
                    'thumbnail_path': thumbnail_path,
                    'step': 'thumbnail_generation'
                }
            else:
                logger.warning("Thumbnail generation failed, continuing without thumbnail")
                return {
                    'success': True,
                    'thumbnail_path': None,
                    'step': 'thumbnail_generation',
                    'warning': 'Thumbnail generation failed'
                }

        except Exception as e:
            logger.warning(f"Step 8 warning: {e}")
            return {
                'success': True,
                'thumbnail_path': None,
                'step': 'thumbnail_generation',
                'error': str(e)
            }

    async def _step9_upload_to_drive(self, video_path: str, thumbnail_path: str,
                                   subtitle_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Step 9: Google Drive アップロード"""
        logger.info("Step 9: Starting Drive upload...")

        try:
            # Drive アップロード実行
            upload_result = upload_video_package(
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                subtitle_path=subtitle_path,
                metadata=metadata
            )

            if upload_result.get('error'):
                logger.warning(f"Drive upload warning: {upload_result['error']}")
                return {
                    'success': True,
                    'drive_result': upload_result,
                    'step': 'drive_upload',
                    'warning': upload_result['error']
                }

            logger.info(f"Uploaded to Drive: {upload_result.get('package_folder_id', 'Unknown')}")

            return {
                'success': True,
                'drive_result': upload_result,
                'folder_id': upload_result.get('package_folder_id'),
                'video_link': upload_result.get('video_link'),
                'step': 'drive_upload'
            }

        except Exception as e:
            logger.warning(f"Step 9 warning: {e}")
            return {
                'success': True,
                'drive_result': {'error': str(e)},
                'step': 'drive_upload',
                'error': str(e)
            }

    async def _step10_upload_to_youtube(self, video_path: str, metadata: Dict[str, Any],
                                      thumbnail_path: str = None) -> Dict[str, Any]:
        """Step 10: YouTube アップロード"""
        logger.info("Step 10: Starting YouTube upload...")

        try:
            # YouTube アップロード実行
            youtube_result = youtube_upload(
                video_path=video_path,
                metadata=metadata,
                thumbnail_path=thumbnail_path,
                privacy_status="private"  # 初期は非公開
            )

            if youtube_result.get('error'):
                logger.warning(f"YouTube upload warning: {youtube_result['error']}")
                return {
                    'success': True,
                    'youtube_result': youtube_result,
                    'step': 'youtube_upload',
                    'warning': youtube_result['error']
                }

            video_id = youtube_result.get('video_id')
            video_url = youtube_result.get('video_url')

            logger.info(f"Uploaded to YouTube: {video_id}")

            return {
                'success': True,
                'youtube_result': youtube_result,
                'video_id': video_id,
                'video_url': video_url,
                'step': 'youtube_upload'
            }

        except Exception as e:
            logger.warning(f"Step 10 warning: {e}")
            return {
                'success': True,
                'youtube_result': {'error': str(e)},
                'step': 'youtube_upload',
                'error': str(e)
            }

    def _get_news_collection_prompt(self, mode: str) -> str:
        """ニュース収集用プロンプトを取得"""
        try:
            if sheets_manager:
                prompts = sheets_manager.get_prompts()
                return prompts.get('prompt_a', self._default_news_prompt())
            else:
                return self._default_news_prompt()
        except Exception:
            return self._default_news_prompt()

    def _get_script_generation_prompt(self) -> str:
        """台本生成用プロンプトを取得"""
        try:
            if sheets_manager:
                prompts = sheets_manager.get_prompts()
                return prompts.get('prompt_b', self._default_script_prompt())
            else:
                return self._default_script_prompt()
        except Exception:
            return self._default_script_prompt()

    def _default_news_prompt(self) -> str:
        """デフォルトニュース収集プロンプト"""
        return """
今日の重要な経済ニュースを3-5件収集してください。以下の基準で選択してください：

1. 市場への影響度が高い
2. 投資家が注目している
3. 日本経済との関連性がある
4. 信頼性の高い情報源からの情報

各ニュースについて、タイトル、要約、出典、重要ポイントを含めてください。
"""

    def _default_script_prompt(self) -> str:
        """デフォルト台本生成プロンプト"""
        return """
提供されたニュース情報をもとに、経済専門家による対談形式の台本を作成してください。

要件：
- 田中氏（経済専門家）と鈴木氏（金融アナリスト）の対談形式
- 専門的だが理解しやすい内容
- 自然な会話の流れ
- 出典情報を適切に言及
- 視聴者にとって価値のある分析を含める
"""

    def _handle_workflow_failure(self, step_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """ワークフロー失敗時の処理"""
        error_message = f"{step_name} failed: {result.get('error', 'Unknown error')}"
        logger.error(error_message)

        # 失敗通知
        asyncio.create_task(self._notify_workflow_error(Exception(error_message)))

        # 実行状態を更新
        self._update_run_status("failed", result)

        return {
            'success': False,
            'failed_step': step_name,
            'error': result.get('error'),
            'run_id': self.run_id
        }

    def _compile_final_result(self, *step_results, execution_time: float) -> Dict[str, Any]:
        """最終結果をコンパイル"""
        result = {
            'success': True,
            'run_id': self.run_id,
            'execution_time': execution_time,
            'generated_files': self.generated_files,
            'steps': {}
        }

        step_names = [
            'news_collection', 'script_generation', 'audio_synthesis',
            'audio_transcription', 'subtitle_alignment', 'video_generation',
            'metadata_generation', 'thumbnail_generation', 'drive_upload', 'youtube_upload'
        ]

        for i, step_result in enumerate(step_results):
            if i < len(step_names):
                result['steps'][step_names[i]] = step_result

        # 重要な結果を抽出
        result['news_count'] = step_results[0].get('count', 0)
        result['script_length'] = step_results[1].get('length', 0)
        result['video_path'] = step_results[5].get('video_path')
        result['video_id'] = step_results[9].get('video_id')
        result['video_url'] = step_results[9].get('video_url')
        result['drive_folder'] = step_results[8].get('folder_id')

        return result

    async def _notify_workflow_start(self, mode: str):
        """ワークフロー開始通知"""
        message = f"YouTube動画生成ワークフローを開始しました\nモード: {mode}\nRun ID: {self.run_id}"
        discord_notifier.notify(message, level="info", title="ワークフロー開始")

    async def _notify_workflow_success(self, result: Dict[str, Any]):
        """ワークフロー成功通知"""
        execution_time = result.get('execution_time', 0)
        video_url = result.get('video_url', 'N/A')

        message = f"YouTube動画生成が完了しました！\n実行時間: {execution_time:.1f}秒\n動画URL: {video_url}"

        fields = {
            'ニュース件数': result.get('news_count', 0),
            '台本文字数': result.get('script_length', 0),
            '生成ファイル数': len(result.get('generated_files', []))
        }

        discord_notifier.notify(message, level="success", title="ワークフロー完了", fields=fields)

    async def _notify_workflow_error(self, error: Exception):
        """ワークフローエラー通知"""
        message = f"YouTube動画生成でエラーが発生しました\nエラー: {str(error)}\nRun ID: {self.run_id}"
        discord_notifier.notify(message, level="error", title="ワークフローエラー")

    def _update_run_status(self, status: str, result: Dict[str, Any]):
        """実行状態を更新"""
        try:
            if sheets_manager and self.run_id:
                sheets_manager.update_run_status(
                    self.run_id,
                    status,
                    result.get('video_url', ''),
                    str(result)
                )
        except Exception as e:
            logger.warning(f"Failed to update run status: {e}")

    def _cleanup_temp_files(self):
        """一時ファイルをクリーンアップ"""
        cleaned_count = 0
        for file_path in self.generated_files:
            try:
                if os.path.exists(file_path) and file_path.startswith(('temp/', '/tmp/')):
                    os.remove(file_path)
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary files")

# グローバルワークフローインスタンス
workflow = YouTubeWorkflow()

async def run_daily_workflow() -> Dict[str, Any]:
    """日次ワークフロー実行"""
    return await workflow.execute_full_workflow("daily")

async def run_special_workflow() -> Dict[str, Any]:
    """特集ワークフロー実行"""
    return await workflow.execute_full_workflow("special")

async def run_test_workflow() -> Dict[str, Any]:
    """テストワークフロー実行"""
    return await workflow.execute_full_workflow("test")

if __name__ == "__main__":
    # コマンドライン実行
    import sys

    async def main():
        mode = sys.argv[1] if len(sys.argv) > 1 else "test"

        print(f"Starting YouTube workflow in {mode} mode...")

        try:
            result = await workflow.execute_full_workflow(mode)

            if result.get('success'):
                print(f"✅ Workflow completed successfully!")
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

    # 実行
    asyncio.run(main())