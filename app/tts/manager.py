"""音声合成（TTS）マネージャー（Chain of Responsibilityパターン使用）

ElevenLabs TTSを使用して台本テキストを音声に変換します。
並列処理とチャンク分割により高速化を実現します。
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs
from pydub import AudioSegment

from app.config.settings import settings

from .providers import create_tts_chain

# Conditional import for openai
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class TTSManager:
    """音声合成管理クラス（リファクタリング版）

    Chain of Responsibilityパターンにより、6つのTTSプロバイダーを
    優先順位順に試行します。
    """

    def __init__(self):
        self.api_key = settings.api_keys.get("elevenlabs")
        self.elevenlabs_client = None
        self.openai_client = None
        self.max_concurrent = settings.max_concurrent_tts
        self.chunk_size = settings.tts_chunk_size
        self.voicevox_port = settings.tts_voicevox_port
        self.voicevox_speaker = settings.tts_voicevox_speaker

        # Initialize clients
        if self.api_key:
            self.elevenlabs_client = AsyncElevenLabs(api_key=self.api_key)
            logger.info("TTS Manager initialized with ElevenLabs")

        if OpenAI and os.getenv("OPENAI_API_KEY"):
            self.openai_client = OpenAI()

        # Create TTS provider chain
        self.tts_chain = create_tts_chain(
            elevenlabs_client=self.elevenlabs_client,
            openai_client=self.openai_client,
            voicevox_port=self.voicevox_port,
            voicevox_speaker=self.voicevox_speaker,
        )

        logger.info(f"TTS Manager initialized (default concurrency: {self.max_concurrent})")

    async def _synthesize_with_fallback(self, text: str, output_path: str, voice_config: Dict[str, Any]) -> bool:
        """複数の方法で音声合成を試行（Chain of Responsibilityパターン）

        Args:
            text: 合成するテキスト
            output_path: 出力ファイルパス
            voice_config: 音声設定

        Returns:
            True if synthesis succeeded, False otherwise
        """
        return await self.tts_chain.synthesize(text, output_path, voice_config=voice_config)

    def split_text_for_tts(self, text: str) -> List[Dict[str, Any]]:
        """テキストをTTS用チャンクに分割"""
        speaker_lines = self._split_by_speaker(text)
        chunks = []
        for speaker_data in speaker_lines:
            speaker = speaker_data["speaker"]
            content = speaker_data["content"]
            sub_chunks = self._split_long_content(content, self.chunk_size)
            for i, chunk_text in enumerate(sub_chunks):
                chunks.append(
                    {
                        "id": f"{speaker}_{len(chunks)}_{i}",
                        "speaker": speaker,
                        "text": chunk_text,
                        "voice_config": self._get_voice_config(speaker),
                        "order": len(chunks),
                    }
                )
        logger.info(f"Split text into {len(chunks)} TTS chunks")
        return chunks

    def _split_by_speaker(self, text: str) -> List[Dict[str, str]]:
        """話者別にテキストを分割

        認識可能な話者ラベルが含まれない場合は空リストを返す。
        """
        lines = text.split("\n")
        speaker_lines: List[Dict[str, str]] = []
        current_speaker = None
        current_content: List[str] = []
        unmatched_content: List[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            speaker_match = re.match(r"^(田中|鈴木|ナレーター|司会)\s*([:：])\s*(.*)", line)
            if speaker_match:
                if current_speaker and current_content:
                    speaker_lines.append({"speaker": current_speaker, "content": " ".join(current_content)})
                current_speaker = speaker_match.group(1)
                current_content = [speaker_match.group(3)]
            else:
                if current_speaker is not None:
                    current_content.append(line)
                else:
                    unmatched_content.append(line)

        if current_speaker and current_content:
            speaker_lines.append({"speaker": current_speaker, "content": " ".join(current_content)})

        if not speaker_lines and (unmatched_content or text.strip()):
            logger.warning("No recognizable speaker labels found; returning empty speaker list")

        return speaker_lines

    def _split_long_content(self, content: str, max_chars: int) -> List[str]:
        """長いコンテンツを適切な長さに分割"""
        if len(content) <= max_chars:
            return [content]
        sentences = re.split(r"[。！？]", content)
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence += "。"
            if len(current_chunk + sentence) <= max_chars:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    def _get_voice_config(self, speaker: str) -> Dict[str, Any]:
        """話者に応じた音声設定を取得"""
        voice_configs = settings.tts_voice_configs
        config = voice_configs.get(speaker)
        if not config:
            config = voice_configs.get("田中")  # デフォルト話者

        if not config:
            logger.warning(
                f"No voice configuration found for speaker '{speaker}' or default '田中'. Using default VoiceSettings."
            )
            return {"voice_id": "default_voice_id", "settings": VoiceSettings()}

        config_dict = config.dict()
        config_dict["settings"] = VoiceSettings(
            stability=config.stability,
            similarity_boost=config.similarity_boost,
            style=config.style,
            use_speaker_boost=True,
        )
        return config_dict

    def _calculate_optimal_concurrency(self, total_chunks: int, estimated_duration_minutes: float) -> int:
        """動画長に基づいて最適な並列度を計算"""
        if estimated_duration_minutes < 5:
            optimal = min(4, total_chunks)
        elif estimated_duration_minutes < 15:
            optimal = min(3, total_chunks)
        else:
            optimal = min(2, total_chunks)

        optimal = min(optimal, settings.max_concurrent_tts)

        logger.info(
            f"Optimal concurrency: {optimal} "
            f"(duration: {estimated_duration_minutes:.1f}min, chunks: {total_chunks})"
        )
        return optimal

    async def synthesize_script(self, script_text: str, target_voice: str = "neutral") -> List[str]:
        """台本全体を音声合成

        Args:
            script_text: 台本テキスト
            target_voice: ターゲット音声（未使用、互換性のため保持）

        Returns:
            生成された音声ファイルのパスリスト
        """
        try:
            chunks = self.split_text_for_tts(script_text)
            if not chunks:
                logger.warning("No chunks to synthesize")
                return []

            # 推定動画長を計算（平均300文字/分）
            estimated_duration_minutes = len(script_text) / 300

            # 最適な並列度を計算
            optimal_concurrency = self._calculate_optimal_concurrency(len(chunks), estimated_duration_minutes)

            logger.info(
                f"Starting TTS for {len(chunks)} chunks "
                f"(concurrency: {optimal_concurrency}, estimated: {estimated_duration_minutes:.1f}min)"
            )
            # Note: 現在の実装は順次実行
            # TODO: 並列実行を再実装する場合はasyncio.Semaphoreを使用

            audio_paths = []
            for chunk in chunks:
                output_path = f"temp/tts_chunk_{chunk['id']}.mp3"

                success = await self._synthesize_with_fallback(chunk["text"], output_path, chunk["voice_config"])
                if success:
                    audio_paths.append(output_path)
                else:
                    logger.error(f"Failed to synthesize chunk {chunk['id']} with all fallbacks.")

            if not audio_paths:
                logger.error("No audio chunks were successfully generated")
                return []

            combined_path = self._combine_audio_files(audio_paths, chunks)
            self._cleanup_temp_files(audio_paths)
            logger.info(f"TTS completed: {combined_path}")
            return [combined_path]

        except Exception as e:
            logger.error(f"Script synthesis failed: {e}")
            return []

    def _combine_audio_files(self, audio_paths: List[str], chunks: List[Dict[str, Any]]) -> str:
        """音声ファイルを結合"""
        try:
            combined = AudioSegment.empty()
            chunk_order_map = {chunk["id"]: chunk["order"] for chunk in chunks}

            sorted_audio_paths_with_chunks = []
            for path in audio_paths:
                chunk_id_match = re.search(r"tts_chunk_(.+?)\.mp3", path)
                if chunk_id_match:
                    chunk_id = chunk_id_match.group(1)
                    if chunk_id in chunk_order_map:
                        sorted_audio_paths_with_chunks.append((chunk_order_map[chunk_id], path))

            sorted_audio_paths_with_chunks.sort(key=lambda x: x[0])
            sorted_audio_paths = [path for order, path in sorted_audio_paths_with_chunks]

            for path in sorted_audio_paths:
                if os.path.exists(path):
                    try:
                        segment = AudioSegment.from_file(path, format="mp3")
                        combined += segment
                        if len(combined) > 0:
                            combined += AudioSegment.silent(duration=300)
                    except Exception as e:
                        logger.warning(f"Failed to process audio file {path}: {e}")

            output_path = f"output_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            combined.export(output_path, format="wav")
            logger.info(f"Combined audio saved: {output_path} ({len(combined)}ms)")
            return output_path

        except Exception as e:
            logger.error(f"Audio combination failed: {e}")
            if audio_paths:
                fallback_path = f"fallback_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                import shutil

                shutil.copy2(audio_paths[0], fallback_path)
                return fallback_path
            raise

    def _cleanup_temp_files(self, temp_paths: List[str]):
        """一時ファイルを削除"""
        for path in temp_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {path}: {e}")

    def get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """音声ファイルの情報を取得"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return {
                "duration_ms": len(audio),
                "duration_sec": len(audio) / 1000,
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "format": audio.sample_width * 8,
                "file_size_mb": os.path.getsize(audio_path) / (1024 * 1024),
            }
        except Exception as e:
            logger.error(f"Failed to get audio info for {audio_path}: {e}")
            return {}


# グローバルインスタンス（後方互換性のため保持）
# Deprecated: Use container.tts_manager instead
def _get_tts_manager() -> TTSManager:
    """Get TTS manager from container (backward compatibility)."""
    from app.container import get_container

    return get_container().tts_manager


# Legacy global variable (backward compatibility)
class _TTSManagerProxy:
    """Proxy object to maintain backward compatibility."""

    def __getattr__(self, name):
        return getattr(_get_tts_manager(), name)


tts_manager = _TTSManagerProxy()


async def synthesize_script(script_text: str, voice: str = "neutral") -> List[str]:
    """台本音声合成の簡易関数"""
    return await _get_tts_manager().synthesize_script(script_text, voice)


def split_text_for_tts(text: str) -> List[Dict[str, Any]]:
    """テキスト分割の簡易関数"""
    return _get_tts_manager().split_text_for_tts(text)
