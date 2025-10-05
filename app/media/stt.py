import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List

from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

from app.config.paths import ProjectPaths

from app.config import cfg
from .stt_fallback import stt_fallback_manager

logger = logging.getLogger(__name__)


class STTManager:
    """音声認識管理クラス"""

    def __init__(self):
        self.api_key = cfg.elevenlabs_api_key
        self.client = None
        if not self.api_key:
            logger.warning("ElevenLabs API key not configured")
        else:
            self.client = ElevenLabs(api_key=self.api_key)
            logger.info("STT Manager initialized")

    def _elevenlabs_transcribe_logic(self, audio_path: str) -> List[Dict[str, Any]]:
        """ElevenLabsによる実際の文字起こしロジック"""
        if not self.client:
            raise Exception("ElevenLabs client not initialized")

        processed_audio_path = self._preprocess_audio(audio_path)
        try:
            with open(processed_audio_path, "rb") as audio_file:
                response = self.client.speech_to_text.convert(file=audio_file, model_id="scribe_v1")
            words = self._process_transcription_result(response.dict())
            logger.info(f"ElevenLabs transcribed {len(words)} words from {audio_path}")
            return words
        finally:
            if processed_audio_path != audio_path:
                try:
                    os.remove(processed_audio_path)
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"Could not remove temporary file {processed_audio_path}: {e}")

    def transcribe_audio(self, audio_path: str, language: str = "ja") -> List[Dict[str, Any]]:
        """音声ファイルを文字起こし（フォールバック付き）"""
        return stt_fallback_manager.transcribe_with_fallback(audio_path)

    def _preprocess_audio(self, audio_path: str) -> str:
        """音声ファイルの前処理"""
        try:
            audio = AudioSegment.from_file(audio_path)
            audio = audio.set_frame_rate(16000)
            audio = audio.set_channels(1)
            audio = audio.normalize()
            temp_dir = ProjectPaths.temp_path()
            temp_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(temp_dir)) as temp_file:
                temp_path = temp_file.name
            audio.export(temp_path, format="wav")
            logger.debug(f"Preprocessed audio saved to: {temp_path}")
            return temp_path
        except Exception as e:
            logger.warning(f"Audio preprocessing failed, using original file: {e}")
            return audio_path

    def _process_transcription_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """転写結果を処理して標準形式に変換"""
        words = []
        try:
            logger.debug(f"STT API response: {result}")
            if "words" in result:
                for word_data in result["words"]:
                    word_info = {
                        "word": word_data.get("word", ""),
                        "start": float(word_data.get("start", 0)),
                        "end": float(word_data.get("end", 0)),
                        "confidence": float(word_data.get("confidence", 1.0)),
                    }
                    words.append(word_info)
            elif "text" in result:
                text = result["text"]
                words = self._generate_estimated_timestamps(text)
            words = self._validate_word_data(words)
        except Exception as e:
            logger.error(f"Failed to process transcription result: {e}")
            return []
        return words

    def _generate_estimated_timestamps(self, text: str) -> List[Dict[str, Any]]:
        """テキストから推定タイムスタンプを生成"""
        words = text.split()
        estimated_words = []
        avg_word_duration = 60 / 150
        current_time = 0.0
        for word in words:
            word_duration = max(0.2, len(word) * 0.05 + avg_word_duration)
            estimated_words.append(
                {"word": word, "start": current_time, "end": current_time + word_duration, "confidence": 0.5}
            )
            current_time += word_duration + 0.1
        return estimated_words

    def _validate_word_data(self, words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """単語データの検証とクリーニング"""
        validated_words = []
        for word_data in words:
            try:
                if not all(key in word_data for key in ["word", "start", "end"]):
                    continue
                word = str(word_data["word"]).strip()
                start_time = float(word_data["start"])
                end_time = float(word_data["end"])
                confidence = float(word_data.get("confidence", 1.0))
                if start_time < 0 or end_time < start_time:
                    continue
                if not word or len(word) > 50:
                    continue
                validated_words.append(
                    {"word": word, "start": start_time, "end": end_time, "confidence": min(1.0, max(0.0, confidence))}
                )
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping invalid word data: {e}")
                continue
        return validated_words

    def split_audio_for_stt(self, audio_path: str, max_duration_minutes: int = 10) -> List[str]:
        """長い音声ファイルをSTT用に分割"""
        try:
            audio = AudioSegment.from_file(audio_path)
            duration_ms = len(audio)
            max_duration_ms = max_duration_minutes * 60 * 1000
            if duration_ms <= max_duration_ms:
                return [audio_path]
            chunks = []
            chunk_count = 0
            for start_ms in range(0, duration_ms, max_duration_ms):
                end_ms = min(start_ms + max_duration_ms, duration_ms)
                chunk = audio[start_ms:end_ms]
                chunk_filename = ProjectPaths.temp_path(
                    f"audio_chunk_{chunk_count}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                )
                chunk.export(str(chunk_filename), format="wav")
                chunks.append(str(chunk_filename))
                chunk_count += 1
            logger.info(f"Split audio into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"Audio splitting failed: {e}")
            return [audio_path]

    def transcribe_long_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        """長い音声ファイルの転写（分割処理付き）"""
        try:
            chunk_paths = self.split_audio_for_stt(audio_path)
            all_words = []
            time_offset = 0.0
            for chunk_path in chunk_paths:
                try:
                    # Use the fallback manager for each chunk
                    chunk_words = self.transcribe_audio(chunk_path)
                    for word in chunk_words:
                        word["start"] += time_offset
                        word["end"] += time_offset
                    all_words.extend(chunk_words)
                    if chunk_words:
                        time_offset = chunk_words[-1]["end"]
                    else:
                        chunk_audio = AudioSegment.from_file(chunk_path)
                        time_offset += len(chunk_audio) / 1000.0
                except Exception as e:
                    logger.error(f"Failed to transcribe chunk {chunk_path}: {e}")
                    continue
                finally:
                    if chunk_path != audio_path:
                        try:
                            os.remove(chunk_path)
                        except (OSError, FileNotFoundError) as e:
                            logger.debug(f"Could not remove chunk file {chunk_path}: {e}")
            logger.info(f"Transcribed long audio: {len(all_words)} total words")
            return all_words
        except Exception as e:
            logger.error(f"Long audio transcription failed: {e}")
            return stt_fallback_manager.stt_fallback_manager._generate_fallback_transcription(audio_path)


# グローバルインスタンス
stt_manager = STTManager()


def transcribe_audio(audio_path: str, language: str = "ja") -> List[Dict[str, Any]]:
    """音声転写の簡易関数"""
    return stt_manager.transcribe_audio(audio_path, language)


def transcribe_long_audio(audio_path: str) -> List[Dict[str, Any]]:
    """長い音声転写の簡易関数"""
    return stt_manager.transcribe_long_audio(audio_path)


if __name__ == "__main__":
    print("Testing STT functionality...")
    if stt_manager.api_key:
        test_audio_paths = ["test_audio.wav", "sample.mp3", "output_audio.wav"]
        for test_path in test_audio_paths:
            if os.path.exists(test_path):
                print(f"\nTesting with: {test_path}")
                try:
                    audio = AudioSegment.from_file(test_path)
                    duration = len(audio) / 1000.0
                    print(f"Audio duration: {duration:.1f}s")
                    words = stt_manager.transcribe_audio(test_path)
                    print(f"Transcribed {len(words)} words:")
                    for word in words[:5]:
                        print(
                            f"  '{word['word']}' [{word['start']:.2f}s-{word['end']:.2f}s] (conf: {word['confidence']:.2f})"
                        )
                    if len(words) > 5:
                        print("  ...")
                except Exception as e:
                    print(f"Test failed for {test_path}: {e}")
                break
        else:
            print("No test audio files found")
    else:
        print("ElevenLabs API not configured, skipping tests")

    print("\nTesting fallback functionality...")
    try:
        # This will now use the fallback manager's fallback
        fallback_words = stt_fallback_manager.stt_fallback_manager._generate_fallback_transcription("dummy.wav")
        print(f"Fallback generated {len(fallback_words)} words")
    except Exception as e:
        print(f"Fallback test failed: {e}")
