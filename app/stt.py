"""
音声認識（STT）モジュール

ElevenLabs STTを使用して音声ファイルから正確なタイムスタンプ付きテキストを生成します。
字幕生成の精度向上のために設計されています。
"""

import os
import logging
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydub import AudioSegment
from elevenlabs.client import ElevenLabs
from app.config import cfg

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

    def transcribe_audio(self, audio_path: str,
                        language: str = "ja",
                        model: str = "eleven_multilingual_v2") -> List[Dict[str, Any]]:
        """
        音声ファイルを文字起こし
        """
        if not self.client:
            logger.error("STT client not initialized")
            return self._generate_fallback_transcription(audio_path)

        try:
            processed_audio_path = self._preprocess_audio(audio_path)
            with open(processed_audio_path, "rb") as audio_file:
                response = self.client.speech_to_text.convert(
                    audio=audio_file,
                    model=model,
                    language=language,
                    timestamp_granularities=["word"],
                )
            words = self._process_transcription_result(response.dict())
            logger.info(f"Transcribed {len(words)} words from {audio_path}")
            return words
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return self._generate_fallback_transcription(audio_path)
        finally:
            if 'processed_audio_path' in locals() and processed_audio_path != audio_path:
                try:
                    os.remove(processed_audio_path)
                except Exception:
                    pass

    def _preprocess_audio(self, audio_path: str) -> str:
        """音声ファイルの前処理"""
        try:
            audio = AudioSegment.from_file(audio_path)
            audio = audio.set_frame_rate(16000)
            audio = audio.set_channels(1)
            audio = audio.normalize()
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
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
            if "words" in result:
                for word_data in result["words"]:
                    word_info = {
                        "word": word_data.get("word", ""),
                        "start": float(word_data.get("start", 0)),
                        "end": float(word_data.get("end", 0)),
                        "confidence": float(word_data.get("confidence", 1.0))
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
            estimated_words.append({
                "word": word,
                "start": current_time,
                "end": current_time + word_duration,
                "confidence": 0.5
            })
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
                validated_words.append({
                    "word": word,
                    "start": start_time,
                    "end": end_time,
                    "confidence": min(1.0, max(0.0, confidence))
                })
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping invalid word data: {e}")
                continue
        return validated_words

    def _generate_fallback_transcription(self, audio_path: str) -> List[Dict[str, Any]]:
        """フォールバック用の転写データを生成"""
        try:
            audio = AudioSegment.from_file(audio_path)
            duration_sec = len(audio) / 1000.0
            fallback_words = []
            dummy_text = "音声認識に失敗しました。手動での確認が必要です。"
            words = dummy_text.split()
            word_duration = duration_sec / len(words) if words else 1.0
            for i, word in enumerate(words):
                start_time = i * word_duration
                end_time = (i + 1) * word_duration
                fallback_words.append({
                    "word": word,
                    "start": start_time,
                    "end": end_time,
                    "confidence": 0.1
                })
            logger.warning(f"Generated fallback transcription with {len(fallback_words)} words")
            return fallback_words
        except Exception as e:
            logger.error(f"Fallback transcription generation failed: {e}")
            return []

    def split_audio_for_stt(self, audio_path: str,
                           max_duration_minutes: int = 10) -> List[str]:
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
                chunk_filename = f"temp/audio_chunk_{chunk_count}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                os.makedirs('temp', exist_ok=True)
                chunk.export(chunk_filename, format="wav")
                chunks.append(chunk_filename)
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
                        except Exception:
                            pass
            logger.info(f"Transcribed long audio: {len(all_words)} total words")
            return all_words
        except Exception as e:
            logger.error(f"Long audio transcription failed: {e}")
            return self._generate_fallback_transcription(audio_path)

# グローバルインスタンス
stt_manager = STTManager()

def transcribe_audio(audio_path: str, language: str = "ja") -> List[Dict[str, Any]]:
    """音声転写の簡易関数"""
    if stt_manager.api_key:
        return stt_manager.transcribe_audio(audio_path, language)
    else:
        logger.warning("STT not available, using fallback")
        return stt_manager._generate_fallback_transcription(audio_path)

def transcribe_long_audio(audio_path: str) -> List[Dict[str, Any]]:
    """長い音声転写の簡易関数"""
    if stt_manager.api_key:
        return stt_manager.transcribe_long_audio(audio_path)
    else:
        logger.warning("STT not available, using fallback")
        return stt_manager._generate_fallback_transcription(audio_path)

if __name__ == "__main__":
    print("Testing STT functionality...")
    if stt_manager.api_key:
        test_audio_paths = [
            "test_audio.wav",
            "sample.mp3",
            "output_audio.wav"
        ]
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
                        print(f"  '{word['word']}' [{word['start']:.2f}s-{word['end']:.2f}s] (conf: {word['confidence']:.2f})")
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
        fallback_words = stt_manager._generate_fallback_transcription("dummy.wav")
        print(f"Fallback generated {len(fallback_words)} words")
    except Exception as e:
        print(f"Fallback test failed: {e}")
