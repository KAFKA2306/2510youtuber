import importlib
import importlib.util
import json
import logging
import os
import subprocess
from typing import Any, Dict, List

import speech_recognition as sr
from pydub import AudioSegment


class STTFallbackManager:
    """音声認識のフォールバックシステム"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.recognizer = sr.Recognizer()

    def transcribe_with_fallback(self, audio_path: str) -> List[Dict[str, Any]]:
        """複数の方法で音声認識を試行

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            単語レベルのタイムスタンプ付きデータ
        """

        # Method 1: ElevenLabs (Primary) - handled externally by STTManager
        # ElevenLabs is the primary method but handled by the main STTManager
        # Skip it here as this is called from STTManager which already tried it
        self.logger.info("Starting fallback transcription methods")

        # Method 2: OpenAI Whisper Local
        try:
            self.logger.info("Attempting transcription with OpenAI Whisper Local")
            result = self._whisper_transcribe(audio_path)
            if result:
                return result
        except Exception as e:
            self.logger.warning(f"Whisper failed: {e}")

        # Method 3: Google Speech Recognition (Free)
        try:
            self.logger.info("Attempting transcription with Google Speech Recognition (Free)")
            result = self._google_free_transcribe(audio_path)
            if result:
                return result
        except Exception as e:
            self.logger.warning(f"Google free failed: {e}")

        # Method 4: SpeechRecognition Library
        try:
            self.logger.info("Attempting transcription with SpeechRecognition Library")
            result = self._speechrecognition_transcribe(audio_path)
            if result:
                return result
        except Exception as e:
            self.logger.warning(f"SpeechRecognition failed: {e}")

        # Final Fallback: Generate dummy transcript
        self.logger.warning("All STT methods failed, generating fallback transcription.")
        return self._generate_fallback_transcription(audio_path)

    def _whisper_transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Whisper による音声認識"""
        if importlib.util.find_spec("whisper") is None:
            self.logger.warning("whisper library not installed, trying CLI.")
            return self._whisper_cli_transcribe(audio_path)

        whisper = importlib.import_module("whisper")
        try:
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, word_timestamps=True)

            words = []
            for segment in result.get("segments", []):
                for word_data in segment.get("words", []):
                    words.append(
                        {
                            "word": word_data["word"].strip(),
                            "start": word_data["start"],
                            "end": word_data["end"],
                            "confidence": 0.9,  # Whisper doesn't provide confidence
                        }
                    )
            return words
        except Exception as e:
            self.logger.error(f"Whisper library transcription failed: {e}")
            return []

    def _whisper_cli_transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Whisper CLI による音声認識"""
        try:
            # Ensure ffmpeg is available for whisper CLI
            subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)

            # Use a temporary file for JSON output
            temp_json_path = f"{audio_path}.json"
            result = subprocess.run(
                [
                    "whisper",
                    audio_path,
                    "--model",
                    "base",
                    "--output_format",
                    "json",
                    "--word_timestamps",
                    "True",
                    "--output_dir",
                    os.path.dirname(temp_json_path),  # Specify output directory
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            if os.path.exists(temp_json_path):
                with open(temp_json_path, "r") as f:
                    data = json.load(f)
                os.remove(temp_json_path)  # Clean up temp file

                words = []
                for segment in data.get("segments", []):
                    for word_data in segment.get("words", []):
                        words.append(
                            {
                                "word": word_data["word"].strip(),
                                "start": word_data["start"],
                                "end": word_data["end"],
                                "confidence": 0.9,
                            }
                        )
                return words
            else:
                self.logger.error(
                    f"Whisper CLI did not produce expected JSON output at {temp_json_path}. Stderr: {result.stderr}"
                )
                return []
        except FileNotFoundError:
            self.logger.warning("Whisper CLI or ffmpeg not found. Please install them.")
            return []
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Whisper CLI failed with error: {e.stderr}")
            return []
        except Exception as e:
            self.logger.error(f"Whisper CLI transcription failed: {e}")
            return []

    def _google_free_transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Google無料音声認識（SpeechRecognition経由）"""
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)

            text = self.recognizer.recognize_google(audio, language="ja-JP")
            return self._text_to_words_with_timestamps(text, audio_path)
        except sr.UnknownValueError:
            self.logger.warning("Google Speech Recognition could not understand audio")
            return []
        except sr.RequestError as e:
            self.logger.warning(f"Could not request results from Google Speech Recognition service; {e}")
            return []
        except Exception as e:
            self.logger.error(f"Google free transcription failed: {e}")
            return []

    def _speechrecognition_transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """SpeechRecognition ライブラリによる認識"""
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)

            # Try multiple engines
            engines = [
                ("google", lambda: self.recognizer.recognize_google(audio, language="ja-JP")),
                # ('sphinx', lambda: self.recognizer.recognize_sphinx(audio, language='ja-JP')), # Sphinx requires separate installation
            ]

            for engine_name, recognize_func in engines:
                try:
                    text = recognize_func()
                    self.logger.info(f"Recognition successful with {engine_name} via SpeechRecognition")
                    return self._text_to_words_with_timestamps(text, audio_path)
                except sr.UnknownValueError:
                    self.logger.warning(f"{engine_name} Speech Recognition could not understand audio")
                except sr.RequestError as e:
                    self.logger.warning(f"Could not request results from {engine_name} Speech Recognition service; {e}")
                except Exception as e:
                    self.logger.error(f"{engine_name} SpeechRecognition failed: {e}")
                    continue

            return []
        except Exception as e:
            self.logger.error(f"SpeechRecognition library transcription failed: {e}")
            return []

    def _text_to_words_with_timestamps(self, text: str, audio_path: str) -> List[Dict[str, Any]]:
        """テキストから推定タイムスタンプ付き単語リストを生成"""
        try:
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            words = text.split()

            if not words:
                return []

            word_duration = duration / len(words) if words else 0.0
            word_list = []

            current_time = 0.0
            for word in words:
                start_time = current_time
                end_time = current_time + word_duration
                word_list.append({"word": word, "start": start_time, "end": end_time, "confidence": 0.7})
                current_time = end_time

            return word_list
        except Exception as e:
            self.logger.error(f"Error generating estimated timestamps: {e}")
            return []

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
                fallback_words.append({"word": word, "start": start_time, "end": end_time, "confidence": 0.1})
            self.logger.warning(f"Generated fallback transcription with {len(fallback_words)} words")
            return fallback_words
        except Exception as e:
            self.logger.error(f"Fallback transcription generation failed: {e}")
            return []


# グローバルインスタンス
stt_fallback_manager = STTFallbackManager()
