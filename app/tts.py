"""音声合成（TTS）モジュール

ElevenLabs TTSを使用して台本テキストを音声に変換します。
並列処理とチャンク分割により高速化を実現します。
"""

import asyncio
import hashlib
import logging
import os
import re
import subprocess
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import pyttsx3
import requests
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import AsyncElevenLabs
from gtts import gTTS
from pydub import AudioSegment

from .config import cfg

# Conditional import for openai
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None

logger = logging.getLogger(__name__)


class TTSManager:
    """音声合成管理クラス"""

    def __init__(self):
        self.api_key = cfg.elevenlabs_api_key
        self.client = None
        self.max_concurrent = 2  # Directly set to 2 to handle ElevenLabs rate limit
        self.chunk_size = cfg.tts_chunk_size
        self.voicevox_port = cfg.tts_voicevox_port
        self.voicevox_speaker = cfg.tts_voicevox_speaker
        self.pyttsx3_engine = None
        self.openai_client = None

        if not self.api_key:
            logger.warning("No ElevenLabs API key configured")
        else:
            self.client = AsyncElevenLabs(api_key=self.api_key)
            logger.info("TTS Manager initialized with ElevenLabs")

        # Initialize OpenAI client if available
        if openai and os.getenv('OPENAI_API_KEY'):
            self.openai_client = OpenAI()

    async def _elevenlabs_synthesize_logic(self, text: str, output_path: str, voice_config: Dict[str, Any]) -> bool:
        """ElevenLabsによる実際の音声合成ロジック"""
        if not self.client:
            raise Exception("ElevenLabs client not initialized")
        try:
            audio_stream = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice_config["voice_id"],
                model_id="eleven_multilingual_v2",
            )

            audio_bytes = b""
            async for chunk in audio_stream:
                audio_bytes += chunk

            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            return True

        except Exception as e:
            logger.error(f"ElevenLabs TTS API call failed: {e}")
            return False

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
        """話者別にテキストを分割"""
        lines = text.split("\n")
        speaker_lines = []
        current_speaker = None
        current_content = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            speaker_match = re.match(r"^(田中|鈴木|ナレーター|司会)[:：]\s*(.+)", line)
            if speaker_match:
                if current_speaker and current_content:
                    speaker_lines.append({"speaker": current_speaker, "content": " ".join(current_content)})
                current_speaker = speaker_match.group(1)
                current_content = [speaker_match.group(2)]
            else:
                if current_content:
                    current_content.append(line)
        if current_speaker and current_content:
            speaker_lines.append({"speaker": current_speaker, "content": " ".join(current_content)})
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
        # These are example Voice IDs. Replace with your actual ElevenLabs Voice IDs.
        voice_configs = {
            "田中": {
                "voice_id": "8PfKHL4nZToWC3pbz9U9",  # Example: Adam
                "settings": VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.1, use_speaker_boost=True),
            },
            "鈴木": {
                "voice_id": "8PfKHL4nZToWC3pbz9U9",  # Example: Rachel
                "settings": VoiceSettings(stability=0.4, similarity_boost=0.8, style=0.2, use_speaker_boost=True),
            },
            "ナレーター": {
                "voice_id": "pNInz6obpgDQGcFmaJgB",  # Example: Paul
                "settings": VoiceSettings(stability=0.6, similarity_boost=0.7, style=0.0, use_speaker_boost=True),
            },
        }
        return voice_configs.get(speaker, voice_configs["田中"])

    async def synthesize_script(self, script_text: str, target_voice: str = "neutral") -> List[str]:
        """台本全体を音声合成"""
        try:
            chunks = self.split_text_for_tts(script_text)
            if not chunks:
                logger.warning("No chunks to synthesize")
                return []

            logger.info(f"Starting TTS for {len(chunks)} chunks with max_concurrent={self.max_concurrent}")
            semaphore = asyncio.Semaphore(self.max_concurrent)

            audio_paths = []
            for chunk in chunks:
                output_path = f"temp/tts_chunk_{chunk['id']}.mp3"
                elevenlabs_synthesizer_func = None
                if self.client:
                    async def elevenlabs_wrapper(text, path, vc=chunk["voice_config"]):
                        return await self._elevenlabs_synthesize_logic(text, path, vc)
                    elevenlabs_synthesizer_func = elevenlabs_wrapper

                success = await tts_fallback_manager.synthesize_with_fallback(
                    chunk["text"],
                    output_path,
                    elevenlabs_synthesizer=elevenlabs_synthesizer_func
                )
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
            # Create a map from chunk_id to its original order for sorting
            chunk_order_map = {chunk["id"]: chunk["order"] for chunk in chunks}
            
            # Create a map from output_path to chunk_id to link paths back to original chunks
            # This assumes audio_paths are generated in the order of chunks, or we need a more robust mapping
            # For now, let's assume audio_paths correspond to chunks in order of successful synthesis
            
            # Re-sort audio_paths based on original chunk order
            sorted_audio_paths_with_chunks = []
            for path in audio_paths:
                # Extract chunk_id from path (e.g., temp/tts_chunk_田中_0_0.mp3 -> 田中_0_0)
                chunk_id_match = re.search(r'tts_chunk_(.+?)\.mp3', path)
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
                            combined += AudioSegment.silent(duration=300) # Add a small pause between chunks
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


# グローバルインスタンス
tts_manager = TTSManager()


async def synthesize_script(script_text: str, voice: str = "neutral") -> List[str]:
    """台本音声合成の簡易関数"""
    return await tts_manager.synthesize_script(script_text, voice)


def split_text_for_tts(text: str) -> List[Dict[str, Any]]:
    """テキスト分割の簡易関数"""
    return tts_manager.split_text_for_tts(text)


if __name__ == "__main__":
    import asyncio

    async def test_tts():
        print("Testing TTS functionality...")
        print(f"API key configured: {bool(tts_manager.api_key)}")
        print(f"Max concurrent: {tts_manager.max_concurrent}")
        print(f"Chunk size: {tts_manager.chunk_size}")

        test_script = """
田中: 皆さん、こんにちは。今日は重要な経済ニュースについてお話しします。

鈴木: こんにちは。最近の市場動向について詳しく見ていきましょう。

田中: まず最初のトピックですが、日経平均株価が昨日大幅に上昇しました。

鈴木: そうですね。前日比で2.5%の上昇となり、投資家の注目を集めています。
"""

        try:
            chunks = tts_manager.split_text_for_tts(test_script)
            print(f"\nSplit into {len(chunks)} chunks:")
            for chunk in chunks[:3]:
                print(f"  {chunk['speaker']}: {chunk['text'][:50]}...")

            if tts_manager.api_key:
                print("\nStarting TTS synthesis...")
                audio_paths = await tts_manager.synthesize_script(test_script)
                if audio_paths:
                    print(f"Generated audio files: {audio_paths}")
                    for path in audio_paths:
                        info = tts_manager.get_audio_info(path)
                        print(f"  {path}: {info.get('duration_sec', 0):.1f}s")
                else:
                    print("No audio files generated")
            else:
                print("No API key configured, skipping actual TTS test")

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test_tts())
