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
import httpx
from pydub import AudioSegment
from app.config import cfg

logger = logging.getLogger(__name__)

class STTManager:
    """音声認識管理クラス"""

    def __init__(self):
        self.api_key = cfg.elevenlabs_api_key
        self.api_base_url = "https://api.elevenlabs.io/v1"

        if not self.api_key:
            logger.warning("ElevenLabs API key not configured")
        else:
            logger.info("STT Manager initialized")

    def transcribe_audio(self, audio_path: str,
                        language: str = "ja",
                        model: str = "eleven_multilingual_v2") -> List[Dict[str, Any]]:
        """
        音声ファイルを文字起こし

        Args:
            audio_path: 音声ファイルのパス
            language: 言語コード
            model: 使用するモデル

        Returns:
            単語レベルのタイムスタンプ付きデータ
        """
        try:
            # 音声ファイルの前処理
            processed_audio_path = self._preprocess_audio(audio_path)

            # ElevenLabs STT APIを呼び出し
            transcription_result = self._call_elevenlabs_stt(
                processed_audio_path, language, model
            )

            if transcription_result:
                # 結果を処理
                words = self._process_transcription_result(transcription_result)
                logger.info(f"Transcribed {len(words)} words from {audio_path}")
                return words
            else:
                logger.warning("STT API returned no results")
                return self._generate_fallback_transcription(audio_path)

        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return self._generate_fallback_transcription(audio_path)

        finally:
            # 一時ファイルをクリーンアップ
            if 'processed_audio_path' in locals() and processed_audio_path != audio_path:
                try:
                    os.remove(processed_audio_path)
                except Exception:
                    pass

    def _preprocess_audio(self, audio_path: str) -> str:
        """音声ファイルの前処理"""
        try:
            # 音声ファイルを読み込み
            audio = AudioSegment.from_file(audio_path)

            # STTに最適な形式に変換
            # - サンプルレート: 16kHz
            # - チャンネル数: モノラル
            # - フォーマット: WAV
            audio = audio.set_frame_rate(16000)
            audio = audio.set_channels(1)

            # 音量正規化
            audio = audio.normalize()

            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

            audio.export(temp_path, format="wav")
            logger.debug(f"Preprocessed audio saved to: {temp_path}")

            return temp_path

        except Exception as e:
            logger.warning(f"Audio preprocessing failed, using original file: {e}")
            return audio_path

    def _call_elevenlabs_stt(self, audio_path: str, language: str,
                            model: str) -> Optional[Dict[str, Any]]:
        """ElevenLabs STT APIを呼び出し"""
        try:
            url = f"{self.api_base_url}/speech-to-text"

            headers = {
                "Accept": "application/json",
                "xi-api-key": self.api_key
            }

            # ファイルサイズをチェック
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            if file_size_mb > 25:  # ElevenLabsの制限に合わせて調整
                logger.warning(f"Audio file too large ({file_size_mb:.1f}MB), may need splitting")

            with open(audio_path, 'rb') as audio_file:
                files = {
                    "audio": audio_file
                }

                data = {
                    "model": model,
                    "language": language,
                    "timestamp_granularities": "word",  # 単語レベルのタイムスタンプ
                    "response_format": "verbose_json"
                }

                response = httpx.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120.0  # 長めのタイムアウト
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.debug("STT API call successful")
                    return result
                else:
                    logger.error(f"STT API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"ElevenLabs STT API call failed: {e}")
            return None

    def _process_transcription_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """転写結果を処理して標準形式に変換"""
        words = []

        try:
            # ElevenLabs API の応答形式に合わせて調整
            if "words" in result:
                for word_data in result["words"]:
                    word_info = {
                        "word": word_data.get("word", ""),
                        "start": float(word_data.get("start", 0)),
                        "end": float(word_data.get("end", 0)),
                        "confidence": float(word_data.get("confidence", 1.0))
                    }
                    words.append(word_info)

            elif "segments" in result:
                # セグメント形式の場合
                for segment in result["segments"]:
                    if "words" in segment:
                        for word_data in segment["words"]:
                            word_info = {
                                "word": word_data.get("word", ""),
                                "start": float(word_data.get("start", 0)),
                                "end": float(word_data.get("end", 0)),
                                "confidence": float(word_data.get("confidence", 1.0))
                            }
                            words.append(word_info)

            elif "text" in result:
                # テキストのみの場合、推定タイムスタンプを生成
                text = result["text"]
                words = self._generate_estimated_timestamps(text)

            # 品質チェック
            words = self._validate_word_data(words)

        except Exception as e:
            logger.error(f"Failed to process transcription result: {e}")
            return []

        return words

    def _generate_estimated_timestamps(self, text: str) -> List[Dict[str, Any]]:
        """テキストから推定タイムスタンプを生成"""
        words = text.split()
        estimated_words = []

        # 平均的な話速を仮定（1分間に150語）
        avg_word_duration = 60 / 150  # 0.4秒/語

        current_time = 0.0
        for word in words:
            # 単語の長さに基づいて時間を調整
            word_duration = max(0.2, len(word) * 0.05 + avg_word_duration)

            estimated_words.append({
                "word": word,
                "start": current_time,
                "end": current_time + word_duration,
                "confidence": 0.5  # 推定値であることを示す
            })

            current_time += word_duration + 0.1  # 語間の間隔

        return estimated_words

    def _validate_word_data(self, words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """単語データの検証とクリーニング"""
        validated_words = []

        for word_data in words:
            try:
                # 必須フィールドのチェック
                if not all(key in word_data for key in ["word", "start", "end"]):
                    continue

                # データ型の確認と修正
                word = str(word_data["word"]).strip()
                start_time = float(word_data["start"])
                end_time = float(word_data["end"])
                confidence = float(word_data.get("confidence", 1.0))

                # 論理的なチェック
                if start_time < 0 or end_time < start_time:
                    continue

                if not word or len(word) > 50:  # 異常に長い単語を除外
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
            # 音声ファイルの長さを取得
            audio = AudioSegment.from_file(audio_path)
            duration_sec = len(audio) / 1000.0

            # ダミーの単語データを生成
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
                    "confidence": 0.1  # 低い信頼度
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
                return [audio_path]  # 分割不要

            # チャンクに分割
            chunks = []
            chunk_count = 0

            for start_ms in range(0, duration_ms, max_duration_ms):
                end_ms = min(start_ms + max_duration_ms, duration_ms)
                chunk = audio[start_ms:end_ms]

                # 一時ファイルに保存
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
            # 音声を分割
            chunk_paths = self.split_audio_for_stt(audio_path)

            all_words = []
            time_offset = 0.0

            for chunk_path in chunk_paths:
                try:
                    # チャンクを転写
                    chunk_words = self.transcribe_audio(chunk_path)

                    # タイムスタンプにオフセットを適用
                    for word in chunk_words:
                        word["start"] += time_offset
                        word["end"] += time_offset

                    all_words.extend(chunk_words)

                    # 次のチャンクのオフセットを計算
                    if chunk_words:
                        time_offset = chunk_words[-1]["end"]
                    else:
                        # チャンクの実際の長さを使用
                        chunk_audio = AudioSegment.from_file(chunk_path)
                        time_offset += len(chunk_audio) / 1000.0

                except Exception as e:
                    logger.error(f"Failed to transcribe chunk {chunk_path}: {e}")
                    continue

                finally:
                    # 一時ファイルを削除
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
    # テスト実行
    print("Testing STT functionality...")

    # 設定確認
    print(f"ElevenLabs API configured: {bool(stt_manager.api_key)}")

    if stt_manager.api_key:
        # テスト用音声ファイルが存在する場合
        test_audio_paths = [
            "test_audio.wav",
            "sample.mp3",
            "output_audio.wav"
        ]

        for test_path in test_audio_paths:
            if os.path.exists(test_path):
                print(f"\nTesting with: {test_path}")
                try:
                    # 音声情報を表示
                    audio = AudioSegment.from_file(test_path)
                    duration = len(audio) / 1000.0
                    print(f"Audio duration: {duration:.1f}s")

                    # 転写実行
                    words = stt_manager.transcribe_audio(test_path)
                    print(f"Transcribed {len(words)} words:")

                    # 最初の5つの単語を表示
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

    # フォールバック機能のテスト
    print("\nTesting fallback functionality...")
    try:
        fallback_words = stt_manager._generate_fallback_transcription("dummy.wav")
        print(f"Fallback generated {len(fallback_words)} words")
    except Exception as e:
        print(f"Fallback test failed: {e}")