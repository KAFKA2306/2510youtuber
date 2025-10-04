# トラブルシューティングガイド

## よくある問題と解決方法

### API関連の問題

#### 1. Anthropic Claude API エラー

**症状**: `anthropic.APIError: Rate limit exceeded`

**原因**: API使用量制限に達している

**解決方法**:
```python
# app/util/retry.py
import time
import random
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"Rate limit hit, retrying in {delay:.2f}s...")
                        time.sleep(delay)
                        continue
                    raise
            return None
        return wrapper
    return decorator

# 使用例
@retry_with_backoff(max_retries=5, base_delay=2)
def call_claude_api(prompt):
    # Claude API呼び出し
    pass
```

**症状**: `anthropic.AuthenticationError`

**解決方法**:
1. APIキーの確認: `echo $ANTHROPIC_API_KEY | head -c 20`
2. キーの形式確認: `sk-ant-api03-` で始まっているか
3. Anthropic Consoleでキーの有効性を確認

#### 2. Google Gemini API エラー

**症状**: `GenerativeModel.generate_content() got an unexpected keyword argument 'timeout'`

**原因**: 新しいGoogle Generative AIライブラリでは`timeout`パラメータが`GenerativeModel.generate_content()`でサポートされなくなりました。

**解決方法**: `generate_content()`呼び出しから`timeout`パラメータを削除します。

```python
# 修正箇所1: app/crew/tools/ai_clients.py (126行目)
- response = client.generate_content(prompt, generation_config=generation_config, timeout=timeout)
+ response = client.generate_content(prompt, generation_config=generation_config)

# 修正箇所2: app/script_gen.py (225行目)
- response = client.generate_content(prompt, generation_config=generation_config, timeout=120)
+ response = client.generate_content(prompt, generation_config=generation_config)
```

#### 3. Google Gemini TTS エラー

**症状**: `google.api_core.exceptions.Forbidden: 403`

**解決方法**:
```bash
# サービスアカウントの権限確認
gcloud projects get-iam-policy YOUR_PROJECT_ID

# 必要なAPIの有効化確認
gcloud services list --enabled --filter="name:generativelanguage.googleapis.com"
```

**症状**: 音声生成がタイムアウトする

**解決方法**:
```python
# app/tts.py の改善
class TTSManager:
    def __init__(self):
        self.max_chunk_size = 1000  # より小さく分割
        self.concurrent_limit = 3   # 並列数を制限

    async def synth_script_with_timeout(self, script_text: str, timeout: int = 300):
        """タイムアウト付きTTS実行"""
        try:
            return await asyncio.wait_for(
                self.synth_script(script_text),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("TTS timeout, falling back to shorter chunks")
            return await self.synth_script_fallback(script_text)
```

#### 3. ElevenLabs STT エラー

**症状**: `HTTP 429: Too Many Requests`

**解決方法**:
```python
# app/stt.py の改善
import time

def transcribe_wav_with_retry(audio_path: str, max_retries: int = 3) -> list:
    for attempt in range(max_retries):
        try:
            return transcribe_wav(audio_path)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Rate limit hit, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise

    # フォールバックとしてWhisperXを使用
    print("ElevenLabs STT failed, falling back to WhisperX")
    return transcribe_with_whisperx(audio_path)
```

#### 4. YouTube API エラー

**症状**: `googleapiclient.errors.HttpError: 403 Forbidden`

**原因**: YouTube Data API の認証問題

**解決方法**:
```python
# app/youtube.py の認証フロー修正
def authenticate_youtube_service():
    """YouTube認証の改善版"""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle
    import os

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    creds = None

    # 保存された認証情報を読み込み
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # 認証情報が無効または期限切れの場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                cfg.YOUTUBE_CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)

        # 認証情報を保存
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

return build('youtube', 'v3', credentials=creds)
```

#### 5. Google Gemini 429（RESOURCE_EXHAUSTED）

**症状**: `litellm.RateLimitError ... quotaMetric: generativelanguage.googleapis.com/generate_content_free_tier_requests`

**原因**: 無料枠（1日 250 リクエスト）が枯渇。ローテーションキーが不足しているか、短時間に実行が集中している。

**解決方法**:
1. `secret/.env` に複数の `GEMINI_API_KEY_*` を登録し、`app/api_rotation.py` の `register_keys("gemini", [...])` に反映する。
2. `logs/workflow_*.log` の `RetryInfo.retryDelay` を確認し、その秒数だけ再試行を遅延させる。クールダウン前の即リトライは禁止。
3. Google AI Studio のクォータタブで利用状況を監視し、必要に応じて有料枠に移行する。
4. Google Sheets 実行履歴タブに 429 発生時刻が記録されるため、運用チームで共有してスケジュールを調整する。

#### 6. CrewAI が Pydantic Script を返さない

**症状**: `CrewAI did not return a Pydantic Script object.` や `Dialogue script validation failed` が Step 2 で発生する。

**原因**: CrewAI が code fence 付き JSON や `Message(content=...)` 形式で出力し、旧パーサが台本テキストを抽出できなかった。

**解決方法**:
1. `app/crew/flows.py` の `_extract_script_text_from_string()` が最新版であることを確認し、code fence / `Message(...)` / `dialogues` 配列を正規化できるようにする。
2. raw テキストを許容するエージェントは `script_writer`, `japanese_purity_polisher` のみ。他エージェントが raw を返す場合は YAML プロンプトを修正し JSON 出力を強制する。
3. Fallback 順序（`japanese_purity_polisher` → `quality_guardian` → `engagement_optimizer` → `script_writer`）が INFO ログに出力される。適切な台本が採用されているか preview を確認する。
4. `pytest tests/unit/test_crew_flows.py` を実行して回帰テストを常時緑に保ち、パーサ変更時の破壊を検知する。

### 環境・依存関係の問題

#### 1. FFmpeg関連エラー

**症状**: `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`

**解決方法**:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg

# macOS
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg

# Docker環境
FROM python:3.9-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

**症状**: FFmpegでの字幕レンダリングエラー

**解決方法**:
```python
# app/video.py の改善
def render_video_safe(background: str, audio_path: str, srt_content: str, output_path: str):
    """安全なFFmpeg実行"""
    import subprocess
    import tempfile

    # 一時SRTファイル作成（パス名をサニタイズ）
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name

    try:
        # FFmpegコマンドを分解して安全に実行
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', background,
            '-i', audio_path,
            '-vf', f"subtitles='{srt_path}':force_style='FontSize=24,PrimaryColour=&Hffffff'",
            '-c:v', 'libx264', '-c:a', 'aac',
            '-shortest', output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise Exception(f"FFmpeg error: {result.stderr}")

        return output_path

    finally:
        # 一時ファイル削除
        if os.path.exists(srt_path):
            os.unlink(srt_path)
```

#### 2. Google認証エラー

**症状**: `google.auth.exceptions.DefaultCredentialsError`

**解決方法**:
```python
# app/config.py での認証確認
import os
import json
from google.oauth2 import service_account

def validate_google_credentials():
    """Google認証情報の検証"""
    creds_path = cfg.GOOGLE_APPLICATION_CREDENTIALS

    if not creds_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not set")

    if creds_path.startswith('{'):
        # 環境変数に直接JSON文字列が設定されている場合
        try:
            creds_data = json.loads(creds_path)
            credentials = service_account.Credentials.from_service_account_info(creds_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS")
    else:
        # ファイルパスが設定されている場合
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"Credentials file not found: {creds_path}")
        credentials = service_account.Credentials.from_service_account_file(creds_path)

    # 権限確認
    required_scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
    ]

    scoped_credentials = credentials.with_scopes(required_scopes)
    return scoped_credentials
```

#### 3. Python依存関係の問題

**症状**: `ModuleNotFoundError` または バージョン競合

**解決方法**:
```bash
# 仮想環境のクリーンインストール
python -m venv venv_clean
source venv_clean/bin/activate  # Linux/Mac
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir

# 依存関係の確認
pip check

# 具体的なバージョンの確認
pip freeze | grep -E "(google|anthropic|pydub|ffmpeg)"
```

### Render環境の問題

#### 1. デプロイエラー

**症状**: Renderでのビルドが失敗する

**解決方法**:
```yaml
# render.yaml の改善
services:
  - type: cron
    name: youtuber-automation
    env: python
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements.txt
      # システム依存パッケージの確認
      which ffmpeg || echo "FFmpeg not found"
    startCommand: "python app/main.py daily"
    # より多くのメモリを割り当て
    plan: standard
```

**症状**: 環境変数が認識されない

**解決方法**:
```python
# app/config.py でのデバッグ
def debug_env_vars():
    """環境変数の確認"""
    required_vars = [
        'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'ELEVENLABS_API_KEY',
        'SLACK_WEBHOOK_URL', 'GOOGLE_SHEET_ID'
    ]

    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: Set ({'*' * 10}{value[-10:] if len(value) > 10 else value})")
        else:
            print(f"✗ {var}: Not set")

# main.py の開始時に実行
if __name__ == "__main__":
    debug_env_vars()
    run()
```

#### 2. 実行タイムアウト

**症状**: Renderでの実行が途中で止まる

**解決方法**:
```python
# app/main.py でのタイムアウト対策
import signal
import sys

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Execution timeout")

def run_with_timeout(mode: str = "daily", timeout_seconds: int = 1800):
    """タイムアウト付き実行"""
    # シグナルハンドラー設定
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        run(mode)
    except TimeoutException:
        print(f"Execution timed out after {timeout_seconds} seconds")
        # 部分的な結果を保存
        save_partial_results()
        sys.exit(1)
    finally:
        signal.alarm(0)  # タイマーリセット
```

### データ・ファイル関連の問題

#### 1. Google Sheets操作エラー

**症状**: `gspread.exceptions.APIError: Quota exceeded`

**解決方法**:
```python
# app/sheets.py の改善
import time
from functools import wraps

def sheets_rate_limit(func):
    """Sheets API rate limit対策"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                time.sleep(0.1)  # API呼び出し間隔を空ける
                return result
            except Exception as e:
                if "quota" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 30  # 30秒、60秒、90秒
                    print(f"Sheets quota exceeded, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise
        return None
    return wrapper

class SheetsManager:
    @sheets_rate_limit
    def update_run(self, run_id: str, **fields):
        # 既存の実装
        pass
```

#### 2. ファイルサイズ制限

**症状**: 動画ファイルが大きすぎてアップロードできない

**解決方法**:
```python
# app/video.py での圧縮設定
def render_video_compressed(background: str, audio_path: str, srt_content: str,
                          output_path: str, target_size_mb: int = 50):
    """サイズ制限付き動画生成"""

    # 音声の長さを取得
    duration = get_audio_duration(audio_path)

    # ターゲットビットレートを計算
    target_bitrate = int((target_size_mb * 8 * 1024) / duration * 0.9)  # 90%マージン

    (
        ffmpeg
        .input(background, loop=1, t=duration)
        .output(
            output_path,
            vf=f"subtitles={srt_path}:force_style='FontSize=24'",
            acodec='aac', vcodec='libx264',
            video_bitrate=f'{target_bitrate}k',
            audio_bitrate='128k',
            maxrate=f'{target_bitrate}k',
            bufsize=f'{target_bitrate * 2}k',
            audio=audio_path
        )
        .overwrite_output()
        .run(quiet=True)
    )
```

### 品質・パフォーマンスの問題

#### 1. 字幕の同期ずれ

**症状**: 字幕と音声のタイミングが合わない

**解決方法**:
```python
# app/align_subtitles.py の改善
def align_with_confidence_check(script_text: str, words: list) -> list:
    """信頼度チェック付きアライメント"""

    sentences = split_into_sentences(script_text)
    subtitle_items = []

    for i, sentence in enumerate(sentences):
        # 文の長さに基づいて予想時間を計算
        expected_duration = len(sentence) * 0.1  # 文字あたり0.1秒

        # STTデータから最適な区間を探索
        best_match = find_best_time_segment(
            sentence, words, expected_duration
        )

        if best_match['confidence'] > 0.7:  # 信頼度70%以上
            subtitle_items.append({
                "index": i + 1,
                "start": best_match['start'],
                "end": best_match['end'],
                "text": sentence.strip(),
                "confidence": best_match['confidence']
            })
        else:
            # 信頼度が低い場合は前の字幕から推定
            estimated_timing = estimate_timing_from_previous(
                subtitle_items, sentence
            )
            subtitle_items.append(estimated_timing)

    return subtitle_items
```

#### 2. 処理速度の改善

**症状**: 全体の処理時間が長すぎる

**解決方法**:
```python
# app/main.py での並列処理最適化
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def optimized_pipeline(run_id: str, mode: str):
    """最適化されたパイプライン"""

    # フェーズ1: 直列処理が必要な部分
    prompts = sheets.load_prompts()
    news_items = search_news.collect_news(prompts["prompt_a"], mode)
    script_text = script_gen.generate_dialogue(news_items, prompts["prompt_b"])

    # フェーズ2: 並列処理可能な部分
    tasks = {
        'audio': tts.synth_script(script_text),
        'metadata': metadata.generate_metadata_async(script_text, prompts["prompt_c"]),
        'comment': metadata.generate_first_comment_async(prompts["prompt_d"], script_text),
    }

    results = await asyncio.gather(*tasks.values())
    audio_paths, meta, first_comment = results

    # フェーズ3: 動画生成（前の結果に依存）
    # STT + 動画生成 + アップロードを並列化
    video_path = await generate_video_async(audio_paths[0], script_text)

    # 最終フェーズ: アップロード
    await upload_and_finalize(video_path, meta, first_comment, run_id)
```

## デバッグのためのツール

### 1. ログ出力の強化

```python
# app/util/logging.py
import logging
import sys
from datetime import datetime

def setup_logging(level=logging.INFO):
    """ログ設定"""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # ファイルハンドラー
    file_handler = logging.FileHandler(
        f"logs/youtuber_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)

    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger
```

### 2. ヘルスチェック機能

```python
# scripts/health_check.py
#!/usr/bin/env python3
"""システムの健全性をチェック"""

import asyncio
from app.config import cfg
from app import sheets, slack

async def health_check():
    """全コンポーネントの動作確認"""

    results = {}

    # API接続テスト
    tests = [
        ("Anthropic", test_anthropic_api),
        ("Gemini", test_gemini_api),
        ("ElevenLabs", test_elevenlabs_api),
        ("Google Sheets", test_sheets_api),
        ("Slack", test_slack_notification),
    ]

    for name, test_func in tests:
        try:
            await test_func()
            results[name] = "✓ OK"
        except Exception as e:
            results[name] = f"✗ Error: {str(e)[:50]}"

    # 結果を出力
    print("\n=== Health Check Results ===")
    for service, status in results.items():
        print(f"{service:15s}: {status}")

    # Slack通知
    summary = "\n".join([f"{k}: {v}" for k, v in results.items()])
    slack.notify(f"Health Check Results:\n{summary}")

if __name__ == "__main__":
    asyncio.run(health_check())
```

### 3. 性能測定ツール

```python
# app/util/profiler.py
import time
import psutil
from functools import wraps

def profile_performance(func):
    """実行時間とリソース使用量を測定"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 開始時の状態
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        try:
            result = func(*args, **kwargs)

            # 終了時の状態
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024

            # 統計出力
            duration = end_time - start_time
            memory_delta = end_memory - start_memory

            print(f"Performance [{func.__name__}]:")
            print(f"  Duration: {duration:.2f}s")
            print(f"  Memory: {start_memory:.1f}MB → {end_memory:.1f}MB (Δ{memory_delta:+.1f}MB)")

            return result

        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            raise

    return wrapper
```

## 緊急時の対応

### 1. 手動実行手順

```bash
# 緊急時の手動実行
export ANTHROPIC_API_KEY="your_key"
export GEMINI_API_KEY="your_key"
# その他必要な環境変数...

# デバッグモードで実行
python app/main.py daily --debug

# 特定のステップのみ実行
python -c "from app.main import *; execute_specific_step('news_collection')"
```

### 2. バックアップシステム

```python
# scripts/emergency_backup.py
"""緊急時のバックアップ実行"""

def emergency_run():
    """最小構成での動画生成"""
    try:
        # 簡素化されたフロー
        news = get_fallback_news()  # 事前準備されたニュース
        script = generate_simple_script(news)  # シンプルな台本
        audio = synthesize_with_fallback(script)  # 代替TTS
        video = create_basic_video(audio, script)  # 最小限の動画
        upload_emergency_video(video)  # 緊急アップロード

    except Exception as e:
        # 最後の手段: エラー報告動画
        create_error_notification_video(str(e))
```

## サポートとコミュニティ

### 問題が解決しない場合

1. **ログの収集**: 詳細なエラーログを保存
2. **環境情報**: OS、Pythonバージョン、依存関係のバージョンを記録
3. **再現手順**: 問題が発生する具体的な手順を文書化
4. **GitHub Issues**: リポジトリのIssuesセクションで報告

### 定期メンテナンス

```bash
# 週次メンテナンススクリプト
#!/bin/bash
# maintenance.sh

echo "=== Weekly Maintenance ==="

# ログローテーション
find logs/ -name "*.log" -mtime +7 -delete

# 一時ファイル削除
find . -name "temp_*" -mtime +1 -delete

# API制限確認
python scripts/check_api_quotas.py

# システムヘルスチェック
python scripts/health_check.py

echo "Maintenance completed"
```

このトラブルシューティングガイドを参考に、システムの安定運用を維持してください。
