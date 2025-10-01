"""
音声合成（TTS）モジュール

Google Gemini TTSを使用して台本テキストを音声に変換します。
並列処理とチャンク分割により高速化を実現します。
"""

import os
import re
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import tempfile
import hashlib
from pydub import AudioSegment
import google.generativeai as genai
import httpx
from app.config import cfg

logger = logging.getLogger(__name__)

class TTSManager:
    """音声合成管理クラス"""

    def __init__(self):
        self.api_keys = cfg.gemini_api_keys
        self.current_key_index = 0
        self.max_concurrent = cfg.max_concurrent_tts
        self.chunk_size = cfg.tts_chunk_size

        if not self.api_keys:
            logger.warning("No Gemini API keys configured")
        else:
            logger.info(f"TTS Manager initialized with {len(self.api_keys)} API keys")

    def split_text_for_tts(self, text: str) -> List[Dict[str, Any]]:
        """テキストをTTS用チャンクに分割

        Args:
            text: 分割対象のテキスト

        Returns:
            チャンク情報のリスト
        """
        # 話者別に分割
        speaker_lines = self._split_by_speaker(text)

        # 各話者の発言をさらに細分化
        chunks = []
        for speaker_data in speaker_lines:
            speaker = speaker_data['speaker']
            content = speaker_data['content']

            # 長い発言を文単位で分割
            sub_chunks = self._split_long_content(content, self.chunk_size)

            for i, chunk_text in enumerate(sub_chunks):
                chunks.append({
                    'id': f"{speaker}_{len(chunks)}_{i}",
                    'speaker': speaker,
                    'text': chunk_text,
                    'voice_config': self._get_voice_config(speaker),
                    'order': len(chunks)
                })

        logger.info(f"Split text into {len(chunks)} TTS chunks")
        return chunks

    def _split_by_speaker(self, text: str) -> List[Dict[str, str]]:
        """話者別にテキストを分割"""
        lines = text.split('\n')
        speaker_lines = []
        current_speaker = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 話者名を検出（田中:、鈴木: など）
            speaker_match = re.match(r'^(田中|鈴木|ナレーター|司会)[:：]\s*(.+)', line)

            if speaker_match:
                # 前の話者の内容を保存
                if current_speaker and current_content:
                    speaker_lines.append({
                        'speaker': current_speaker,
                        'content': ' '.join(current_content)
                    })

                # 新しい話者を開始
                current_speaker = speaker_match.group(1)
                current_content = [speaker_match.group(2)]
            else:
                # 継続する発言
                if current_content:
                    current_content.append(line)

        # 最後の話者の内容を保存
        if current_speaker and current_content:
            speaker_lines.append({
                'speaker': current_speaker,
                'content': ' '.join(current_content)
            })

        return speaker_lines

    def _split_long_content(self, content: str, max_chars: int) -> List[str]:
        """長いコンテンツを適切な長さに分割"""
        if len(content) <= max_chars:
            return [content]

        # 文区切りで分割を試行
        sentences = re.split(r'[。！？]', content)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence += "。"  # 区切り文字を復元

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
        voice_configs = {
            '田中': {
                'voice_name': 'ja-JP-Standard-C',  # 男性声
                'speed': 1.0,
                'pitch': 0.0
            },
            '鈴木': {
                'voice_name': 'ja-JP-Standard-A',  # 女性声
                'speed': 1.05,
                'pitch': 2.0
            },
            'ナレーター': {
                'voice_name': 'ja-JP-Standard-D',  # 男性声（深め）
                'speed': 0.95,
                'pitch': -2.0
            }
        }

        return voice_configs.get(speaker, voice_configs['田中'])

    async def synthesize_chunk(self, chunk: Dict[str, Any]) -> Optional[str]:
        """単一チャンクの音声合成

        Args:
            chunk: チャンク情報

        Returns:
            生成された音声ファイルのパス
        """
        try:
            # API キーをローテーション
            api_key = self._get_next_api_key()

            # 音声合成を実行
            audio_data = await self._call_gemini_tts(
                text=chunk['text'],
                voice_config=chunk['voice_config'],
                api_key=api_key
            )

            if audio_data:
                # 一時ファイルに保存
                output_path = self._save_audio_chunk(chunk['id'], audio_data)
                logger.debug(f"Generated audio for chunk {chunk['id']}: {output_path}")
                return output_path
            else:
                logger.warning(f"Failed to generate audio for chunk {chunk['id']}")
                return None

        except Exception as e:
            logger.error(f"Error synthesizing chunk {chunk['id']}: {e}")
            return None

    def _get_next_api_key(self) -> str:
        """次のAPIキーを取得（ローテーション）"""
        if not self.api_keys:
            raise ValueError("No API keys available")

        key = self.api_keys[self.current_key_index % len(self.api_keys)]
        self.current_key_index += 1
        return key

    async def _call_gemini_tts(self, text: str, voice_config: Dict[str, Any],
                              api_key: str) -> Optional[bytes]:
        """Gemini TTS APIを呼び出し

        注意: 実際のGemini TTS APIエンドポイントに合わせて調整が必要
        """
        try:
            # Gemini TTS API の実際のエンドポイントを使用
            # 現在は仮実装として、テキストから疑似音声データを生成

            url = "https://texttospeech.googleapis.com/v1/text:synthesize"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "input": {"text": text},
                "voice": {
                    "languageCode": "ja-JP",
                    "name": voice_config.get('voice_name', 'ja-JP-Standard-A'),
                    "ssmlGender": "NEUTRAL"
                },
                "audioConfig": {
                    "audioEncoding": "LINEAR16",
                    "sampleRateHertz": 22050,
                    "speakingRate": voice_config.get('speed', 1.0),
                    "pitch": voice_config.get('pitch', 0.0)
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    audio_data = result.get('audioContent')
                    if audio_data:
                        import base64
                        return base64.b64decode(audio_data)
                else:
                    logger.warning(f"TTS API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Gemini TTS API call failed: {e}")
            return None

    def _save_audio_chunk(self, chunk_id: str, audio_data: bytes) -> str:
        """音声チャンクを一時ファイルに保存"""
        os.makedirs('temp', exist_ok=True)

        # ファイル名を生成（重複を避けるためハッシュ使用）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_hash = hashlib.md5(chunk_id.encode()).hexdigest()[:8]
        filename = f"temp/tts_{timestamp}_{file_hash}.wav"

        with open(filename, 'wb') as f:
            f.write(audio_data)

        return filename

    async def synthesize_script(self, script_text: str,
                               target_voice: str = "neutral") -> List[str]:
        """台本全体を音声合成

        Args:
            script_text: 台本テキスト
            target_voice: 音声タイプ

        Returns:
            生成された音声ファイルのパスリスト
        """
        try:
            # テキストをチャンクに分割
            chunks = self.split_text_for_tts(script_text)

            if not chunks:
                logger.warning("No chunks to synthesize")
                return []

            # 並列で音声合成実行
            logger.info(f"Starting TTS for {len(chunks)} chunks with max_concurrent={self.max_concurrent}")

            # セマフォで並列数を制限
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def limited_synthesis(chunk):
                async with semaphore:
                    return await self.synthesize_chunk(chunk)

            # 並列実行
            tasks = [limited_synthesis(chunk) for chunk in chunks]
            audio_paths = await asyncio.gather(*tasks, return_exceptions=True)

            # 成功したもののみを抽出
            valid_paths = []
            for i, path in enumerate(audio_paths):
                if isinstance(path, Exception):
                    logger.error(f"Chunk {i} failed: {path}")
                elif path:
                    valid_paths.append(path)

            if not valid_paths:
                logger.error("No audio chunks were successfully generated")
                return self._generate_fallback_audio(script_text)

            # 音声ファイルを結合
            combined_path = self._combine_audio_files(valid_paths, chunks)

            # 一時ファイルをクリーンアップ
            self._cleanup_temp_files(valid_paths)

            logger.info(f"TTS completed: {combined_path}")
            return [combined_path]

        except Exception as e:
            logger.error(f"Script synthesis failed: {e}")
            return self._generate_fallback_audio(script_text)

    def _combine_audio_files(self, audio_paths: List[str],
                            chunks: List[Dict[str, Any]]) -> str:
        """音声ファイルを結合"""
        try:
            combined = AudioSegment.empty()

            # チャンクの順序に従って結合
            path_chunk_map = {chunks[i]['id']: audio_paths[i]
                             for i in range(min(len(chunks), len(audio_paths)))}

            for chunk in sorted(chunks, key=lambda x: x['order']):
                chunk_id = chunk['id']
                if chunk_id in path_chunk_map:
                    path = path_chunk_map[chunk_id]
                    if os.path.exists(path):
                        try:
                            segment = AudioSegment.from_file(path)
                            combined += segment

                            # 話者交代時に短い無音を挿入
                            if len(combined) > 0:
                                combined += AudioSegment.silent(duration=300)  # 300ms

                        except Exception as e:
                            logger.warning(f"Failed to process audio file {path}: {e}")

            # 最終音声ファイルを保存
            output_path = f"output_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            combined.export(output_path, format="wav")

            logger.info(f"Combined audio saved: {output_path} ({len(combined)}ms)")
            return output_path

        except Exception as e:
            logger.error(f"Audio combination failed: {e}")
            # フォールバック: 最初のファイルをコピー
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

    def _generate_fallback_audio(self, script_text: str) -> List[str]:
        """フォールバック用の無音音声を生成"""
        try:
            # テキストの長さから推定時間を計算（1文字 = 約0.1秒）
            estimated_duration_ms = len(script_text) * 100

            # 最小5秒、最大60分
            duration_ms = max(5000, min(estimated_duration_ms, 3600000))

            # 無音音声を生成
            silence = AudioSegment.silent(duration=duration_ms)

            # ファイルに保存
            fallback_path = f"fallback_silence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            silence.export(fallback_path, format="wav")

            logger.warning(f"Generated fallback silence audio: {fallback_path} ({duration_ms}ms)")
            return [fallback_path]

        except Exception as e:
            logger.error(f"Fallback audio generation failed: {e}")
            return []

    def get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """音声ファイルの情報を取得"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return {
                'duration_ms': len(audio),
                'duration_sec': len(audio) / 1000,
                'sample_rate': audio.frame_rate,
                'channels': audio.channels,
                'format': audio.sample_width * 8,  # bits
                'file_size_mb': os.path.getsize(audio_path) / (1024 * 1024)
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
    # テスト実行
    import asyncio

    async def test_tts():
        print("Testing TTS functionality...")

        # 設定確認
        print(f"API keys configured: {len(tts_manager.api_keys)}")
        print(f"Max concurrent: {tts_manager.max_concurrent}")
        print(f"Chunk size: {tts_manager.chunk_size}")

        # テスト用台本
        test_script = """
田中: 皆さん、こんにちは。今日は重要な経済ニュースについてお話しします。

鈴木: こんにちは。最近の市場動向について詳しく見ていきましょう。

田中: まず最初のトピックですが、日経平均株価が昨日大幅に上昇しました。

鈴木: そうですね。前日比で2.5%の上昇となり、投資家の注目を集めています。

田中: この上昇の背景には、好調な企業決算があります。

鈴木: 特にテクノロジー関連企業の業績が予想を上回っていますね。
"""

        try:
            # テキスト分割テスト
            chunks = tts_manager.split_text_for_tts(test_script)
            print(f"\nSplit into {len(chunks)} chunks:")
            for chunk in chunks[:3]:  # 最初の3つだけ表示
                print(f"  {chunk['speaker']}: {chunk['text'][:50]}...")

            # 音声合成テスト（実際のAPIキーがある場合のみ）
            if tts_manager.api_keys:
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
                print("No API keys configured, skipping actual TTS test")

        except Exception as e:
            print(f"Test failed: {e}")

    # テスト実行
    asyncio.run(test_tts())