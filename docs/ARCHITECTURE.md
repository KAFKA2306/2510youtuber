# システムアーキテクチャ

YouTube自動生成システムの全体構成とデータフロー

## 目次

- [1. システム概要](#1-システム概要)
- [2. ディレクトリ構造](#2-ディレクトリ構造)
- [3. ワークフロー（10ステップ）](#3-ワークフロー10ステップ)
- [4. CrewAI エージェントパイプライン](#4-crewai-エージェントパイプライン)
- [5. データモデル](#5-データモデル)
- [6. 外部API連携](#6-外部api連携)
- [7. 設定管理](#7-設定管理)
- [8. エラーハンドリング](#8-エラーハンドリング)

---

## 1. システム概要

### アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────┐
│                    YouTube自動生成システム                          │
└─────────────────────────────────────────────────────────────────┘
                                ↓
        ┌───────────────────────────────────────────────┐
        │  Workflow Orchestrator (app/main.py)          │
        │  - 10ステップの実行制御                          │
        │  - エラーハンドリング・リトライ                    │
        │  - 実行ログ・メトリクス収集                       │
        └───────────────────────────────────────────────┘
                                ↓
    ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┐
    │Step1 │Step2 │Step3 │Step4 │Step5 │Step6 │Step7 │Step8 │...
    │News  │Script│Audio │STT   │Subs  │Video │Meta  │Upload│
    └──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘
       ↓      ↓      ↓      ↓      ↓      ↓      ↓      ↓
    [External APIs]  [CrewAI]  [FFmpeg]  [Google APIs]
```

### 主要コンポーネント

1. **ワークフローエンジン** (`app/main.py`, `app/workflow/`)
   - 10ステップの順次実行
   - ステップ間のデータ受け渡し
   - エラー時のリトライ・フォールバック

2. **CrewAI エージェントシステム** (`app/crew/`)
   - 7つの専門AIエージェント
   - LiteLLM経由でGemini APIを使用（`GeminiAdapter`で統一設定を注入）
   - プロンプトの外部化（YAML）

3. **メディア処理サービス** (`app/services/media/`)
   - TTS（音声合成）
   - STT（音声認識）
   - 動画生成（FFmpeg）
   - B-roll生成（Stock Footage）

4. **データ永続化** (`app/services/`, `app/metadata_storage.py`)
   - ファイルアーカイブ（output/）
   - 実行ログ（JSONL + Google Sheets）
   - メタデータ管理

5. **外部連携** (`app/youtube.py`, `app/sheets.py`)
   - YouTube Data API（アップロード）
   - Google Sheets API（ログ記録）
   - Stock Footage API（Pexels/Pixabay）

---

## 2. ディレクトリ構造

### プロジェクト全体

```
youtuber/
├── app/                          # アプリケーションコード
│   ├── main.py                   # メインエントリーポイント
│   ├── config/                   # 設定管理
│   │   ├── settings.py           # Pydantic設定（config.yaml読み込み）
│   │   ├── paths.py              # ProjectPaths（パス解決の単一情報源）
│   │   └── prompts/              # CrewAIプロンプト（YAML）
│   ├── crew/                     # CrewAI関連
│   │   ├── agents.py             # エージェント定義
│   │   ├── tasks.py              # タスク定義
│   │   ├── flows.py              # Flowロジック
│   │   └── tools/                # カスタムツール
│   ├── models/                   # データモデル（Pydantic）
│   │   ├── script.py             # Script, WOWMetrics
│   │   ├── news.py               # NewsItem
│   │   ├── workflow.py           # WorkflowResult, StepResult
│   │   ├── qa.py                 # QA結果モデル
│   │   └── video_review.py       # VideoReviewFeedback
│   ├── services/                 # ビジネスロジック
│   │   ├── media/                # メディア処理
│   │   │   ├── stock_footage_manager.py
│   │   │   ├── visual_matcher.py
│   │   │   ├── broll_generator.py
│   │   │   └── qa_pipeline.py
│   │   ├── script/               # スクリプト処理
│   │   │   └── continuity.py
│   │   ├── video_review.py       # 動画レビューAI
│   │   └── file_archival.py      # ファイル管理
│   ├── workflow/                 # ワークフロー実装
│   │   └── steps.py              # 各ステップの実装
│   ├── api_rotation.py           # APIキーローテーション
│   ├── metadata_storage.py       # メタデータ永続化
│   ├── analytics.py              # フィードバック分析
│   ├── tts.py                    # 音声合成
│   ├── stt.py                    # 音声認識
│   ├── align_subtitles.py        # 字幕整合
│   ├── video.py                  # 動画生成
│   ├── thumbnail.py              # サムネイル生成
│   ├── youtube.py                # YouTube連携
│   ├── sheets.py                 # Google Sheets連携
│   └── utils.py                  # ユーティリティ
│
├── tests/                        # テストコード
│   ├── unit/                     # ユニットテスト
│   ├── integration/              # 統合テスト
│   ├── e2e/                      # E2Eテスト
│   └── api/                      # API安定性テスト
│
├── scripts/                      # スクリプト
│   ├── analytics_report.py       # 分析レポート生成
│   ├── video_review.py           # 動画レビューCLI
│   └── voicevox_manager.sh       # VOICEVOX管理
│
├── config.yaml                   # 統合設定ファイル
├── secret/.env                   # 環境変数（APIキー）
├── output/                       # 生成ファイル（gitignore）
├── cache/                        # キャッシュ（gitignore）
├── data/                         # データファイル
│   ├── metadata_history.csv      # レガシーメタデータ
│   └── qa_reports/               # 品質レポート
├── docs/                         # ドキュメント
└── logs/                         # ログファイル
```

### 重要ファイル

| ファイル | 役割 |
|---------|------|
| `app/main.py` | ワークフロー実行のエントリーポイント |
| `app/config/settings.py` | 統一設定管理（Pydantic） |
| `app/config/paths.py` | パス解決ユーティリティ（ProjectPaths） |
| `app/crew/flows.py` | CrewAI エージェントパイプライン |
| `app/workflow/steps.py` | 10ステップの実装 |
| `app/api_rotation.py` | APIレート制限対策 |
| `config.yaml` | 全設定の中央管理 |
| `secret/.env` | APIキー・認証情報 |

---

## 3. ワークフロー（10ステップ）

### フロー図

```
START
  ↓
[1] News Collection (search_news.py)
  ├─ Perplexity AI → NewsAPI → Fallback
  ↓
[2] Script Generation (crew/flows.py)
  ├─ CrewAI 7エージェント
  ├─ WOW Script Creation
  ├─ Japanese Purity Guard (no regression)
  ↓
[3] Audio Synthesis (tts.py)
  ├─ ElevenLabs → VOICEVOX → OpenAI → gTTS → Coqui → pyttsx3
  ↓
[4] STT for Alignment (stt.py)
  ├─ Whisper (word-level timestamps)
  ↓
[5] Subtitle Alignment (align_subtitles.py)
  ├─ Script + STT → Aligned SRT
  ↓
[6] B-roll Generation (services/media/)
  ├─ Stock Footage (Pexels/Pixabay) OR Static Background
  ↓
[7] Video Rendering (video.py)
  ├─ FFmpeg Compositing (video + audio + subs)
  ↓
[8] Metadata Generation (metadata.py)
  ├─ Title, Description, Tags
  ↓
[9] YouTube Upload (youtube.py)
  ├─ OAuth 2.0 認証
  ├─ Video Upload API
  ↓
[10] Feedback Logging (metadata_storage.py)
  ├─ JSONL + Google Sheets (3 tabs)
  ↓
END
```

### ステップ詳細

#### Step 1: News Collection
**モジュール**: `app/search_news.py`
**処理**:
1. Perplexity AI でニュース検索（優先）
2. 失敗時 → NewsAPI フォールバック
3. 両方失敗 → ダミーニュース生成
**出力**: `List[NewsItem]`

#### Step 2: Script Generation
**モジュール**: `app/crew/flows.py`
**処理**:
1. CrewAI Flow起動
2. 7エージェントによる台本生成
3. 日本語純度ガード（原稿より悪化しないことを保証）
4. WOWスコア検証（8.0+）
**出力**: `Script` (Pydantic model)

#### Step 3: Audio Synthesis
**モジュール**: `app/tts.py`
**処理**:
1. 6段階フォールバック（ElevenLabs → ... → pyttsx3）
2. 話者ごとに音声合成
3. WAVファイル結合
**出力**: `audio.wav`

#### Step 4: STT for Alignment
**モジュール**: `app/stt.py`
**処理**:
1. Whisper APIで音声認識
2. Word-level timestamps取得
**出力**: `List[Dict]` (words with timestamps)

#### Step 5: Subtitle Alignment
**モジュール**: `app/align_subtitles.py`
**処理**:
1. Script text + STT words → マッチング
2. タイムスタンプ付き字幕生成
3. 読み速度考慮（8文字/秒）
**出力**: `subtitles.srt`

#### Step 6: B-roll Generation
**モジュール**: `app/services/media/`, `app/video.py`
**処理**:
1. Stock Footage有効時:
   - キーワード抽出 → API検索 → ダウンロード → B-roll合成
2. 無効時:
   - テーマベース静的背景生成
**出力**: `broll_video.mp4` or `background.png`

#### Step 7: Video Rendering
**モジュール**: `app/video.py`
**処理**:
1. FFmpeg: video + audio + subtitles 合成
2. 品質設定適用（H.264, 1920x1080）
3. 字幕オーバーレイ
**出力**: `video.mp4`

#### Step 8: Metadata Generation
**モジュール**: `app/metadata.py`
**処理**:
1. Gemini APIでタイトル・説明文生成
2. SEO最適化されたタグ生成
**出力**: `Metadata` dict

#### Step 9: YouTube Upload
**モジュール**: `app/youtube.py`
**処理**:
1. OAuth 2.0 認証
2. YouTube Data API v3 でアップロード
3. Video IDを取得
**出力**: `video_id` (str)

#### Step 10: Feedback Logging
**モジュール**: `app/metadata_storage.py`
**処理**:
1. WorkflowResult構築
2. JSONL追記
3. Google Sheets 3タブに同期
**出力**: ログ記録完了

---

## 4. CrewAI エージェントパイプライン

### 7エージェント構成

```
News Items
    ↓
┌──────────────────────────────────────┐
│  並列実行（agents 1-3）                │
│  ┌────────────────────────────────┐  │
│  │ Agent 1: Deep News Analyzer    │  │
│  │ - 隠れた驚き・裏の意味を発掘    │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ Agent 2: Curiosity Gap Researcher│ │
│  │ - "続きが知りたい"フック設計   │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ Agent 3: Emotional Story Architect││
│  │ - 感情曲線の設計              │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
    ↓ (分析結果統合)
┌────────────────────────────────┐
│ Agent 4: Script Writer         │
│ - 3話者の台本生成              │
│ - PREP法・パターンインタラプト │
└────────────────────────────────┘
    ↓
┌────────────────────────────────┐
│ Agent 5: Engagement Optimizer  │
│ - 保持率予測・改善             │
│ - 30秒ごとのフック配置         │
└────────────────────────────────┘
    ↓
┌────────────────────────────────┐
│ Agent 6: Quality Guardian      │
│ - WOWスコア検証（8.0+）        │
│ - メトリクス計測               │
└────────────────────────────────┘
    ↓
┌────────────────────────────────┐
│ Agent 7: Japanese Purity Polisher│
│ - 日本語純度のリグレッション防止 │
│ - 英語混入除去                 │
└────────────────────────────────┘
    ↓
Final Script (JSON)
```

### エージェント詳細

| Agent | Model | Temp | Max Tokens | Timeout |
|-------|-------|------|-----------|---------|
| Deep News Analyzer | gemini-2.5-pro | 0.7 | 4096 | 120s |
| Curiosity Gap Researcher | gemini-2.5-pro | 0.8 | 2048 | 90s |
| Emotional Story Architect | gemini-2.5-pro | 0.8 | 3072 | 100s |
| Script Writer | gemini-2.5-pro | 0.9 | 8192 | 180s |
| Engagement Optimizer | gemini-2.5-pro | 0.7 | 6144 | 120s |
| Quality Guardian | gemini-2.5-pro | 0.5 | 4096 | 90s |
| Japanese Purity Polisher | gemini-2.5-pro | 0.6 | 8192 | 120s |

### 重要実装詳細

**LiteLLM + Google AI Studio**:
```python
# flows.py
import os

# Vertex AI環境変数を削除（Google AI Studio強制）
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

# LiteLLMでGemini API呼び出し
import litellm
response = litellm.completion(
    model="gemini/gemini-2.5-pro",
    messages=[...],
    api_key=rotation_manager.get_key("gemini")
)
```

**プロンプト外部化**:
```yaml
# app/config/prompts/agents.yaml
deep_news_analyzer:
  role: 経済ニュース深層分析の専門家
  goal: ニュースの裏にある驚きと示唆を発掘する
  backstory: |
    あなたは15年のキャリアを持つ経済ジャーナリストです。
    表面的な情報の裏に隠れた本質的な意味を見抜く能力に長けています。
```

---

## 5. データモデル

### 主要モデル（Pydantic v2）

#### Script
```python
# app/models/script.py
class ScriptSegment:
    speaker: str               # 田中/鈴木/ナレーター
    text: str                  # セリフ
    timestamp_start: float     # 開始時間（秒）
    timestamp_end: float       # 終了時間
    visual_instruction: str    # 視覚指示

class WOWMetrics:
    wow_score: float           # 10点満点
    surprise_points: int       # 驚きポイント数
    emotion_peaks: int         # 感情ピーク数
    curiosity_gaps: int        # 好奇心ギャップ数
    visual_instructions: int   # 視覚指示数
    concrete_numbers: int      # 具体的数字数
    viewer_questions: int      # 視聴者質問数

class Script:
    segments: List[ScriptSegment]
    metrics: WOWMetrics
    retention_predictions: Dict[str, float]
```

#### WorkflowResult
```python
# app/models/workflow.py
class WorkflowResult:
    run_id: str
    mode: str
    title: str
    video_id: str
    video_path: str

    # Quality
    wow_score: float
    japanese_purity: float
    retention_prediction: float
    surprise_points: int
    emotion_peaks: int

    # Execution
    execution_time: float
    total_cost: float
    step_costs: Dict[str, float]

    # Strategy
    hook_type: str             # 衝撃的事実/疑問提起/意外な数字
    topic_tags: List[str]

    # Optional
    youtube_feedback: Optional[YouTubeFeedback]
    video_review: Optional[VideoReviewFeedback]
```

---

## 6. 外部API連携

### API一覧と用途

| API | 用途 | レート制限 | フォールバック |
|-----|------|-----------|--------------|
| **Gemini API** | CrewAI, Metadata生成 | 60 req/min | 5キーローテーション |
| **Perplexity AI** | ニュース検索 | 50 req/day (free) | NewsAPI → Dummy |
| **ElevenLabs** | TTS | 10k chars/month (free) | VOICEVOX → OpenAI → gTTS |
| **VOICEVOX** | TTS (ローカル) | 無制限 | - |
| **Pexels** | Stock Footage | 無制限 (free) | Pixabay → Static BG |
| **Pixabay** | Stock Footage | 100 req/min | Static Background |
| **YouTube Data API** | 動画アップロード | 10,000 units/day | - |
| **Google Sheets API** | ログ記録 | 300 req/min | - |

### GeminiAdapter（LLMアダプタ層）

- 所在: `app/crew/tools/ai_clients.py`, `app/adapters/llm.py`
- 役割: Gemini SDK / LiteLLM のインターフェース差分、`timeout` 非対応問題、モデル名の固定化を**単一地点で吸収**する。
- 実装ポイント:
  - `settings.llm.model` と `api_rotation` を必ず経由し、コード中のモデル名直書きを禁止。
  - `generate_json()` が CrewAI/レビューで要求されるスキーマを返す。code fence や `Message(content=...)` でラップされた応答は `_extract_script_text_from_string()` で正規化。
  - 429 (RESOURCE_EXHAUSTED) は `APIKeyRotationManager.execute_with_rotation()` の再試行に委譲し、失敗時は詳細ログ＋`RetryInfo` を記録する。

### API Key Rotation

**実装**: `app/api_rotation.py`

```python
class APIKeyRotationManager:
    def register_keys(self, provider: str, keys: List[str]):
        # 複数キーを登録

    def get_key(self, provider: str) -> str:
        # 使用可能なキーを返す（クールダウン考慮）

    def execute_with_rotation(
        self,
        provider: str,
        api_call: Callable,
        max_attempts: int = 3
    ):
        # 429エラー時に自動ローテーション
```

**Gemini ローテーション設定**:
- 5分クールダウン（per key）
- 全キー使用後は10分待機
- 自動リセット（1日1回）

---

## 7. 設定管理

### 統一設定システム

**config.yaml** (中央管理):
```yaml
speakers:
  - name: 武宏
    voicevox_speaker: 11
    speaking_style: 落ち着いた、論理的

video:
  resolution: {width: 1920, height: 1080}
  quality_preset: high

stock_footage:
  enabled: true
  clips_per_video: 5

quality_thresholds:
  wow_score_min: 8.0
  # 日本語純度は原稿より悪化しないことのみ保証（閾値なし）
```

**secret/.env** (APIキー):
```bash
GEMINI_API_KEY=AIza...
GEMINI_API_KEY_2=AIza...
PEXELS_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=secret/service-account.json
```

**Pydantic読み込み**:
```python
# app/config/settings.py
import yaml
from pydantic_settings import BaseSettings

from app.config.paths import ProjectPaths

class Settings(BaseSettings):
    # ... フィールド定義

    @classmethod
    def load(cls) -> "Settings":
        with open(ProjectPaths.CONFIG_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # ... 追加処理（環境変数マージなど）
        return cls(**data)

settings = Settings.load()
```

> **NOTE:** `ProjectPaths` が `.env`、`config.yaml`、`output/` などのルートディレクトリを集約管理します。パスを追加する際は `app/config/paths.py` に定義してから利用することで移植性を維持できます。

---

## 8. エラーハンドリング

### リトライ戦略

**ステップレベル**:
```python
# app/workflow/steps.py
class GenerateScriptStep:
    def execute(self, context):
        for attempt in range(3):  # 最大3回
            try:
                result = self._generate_script(context)
                if result.wow_score >= 8.0:
                    return result
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))  # Exponential backoff
```

**APIレベル**:
```python
# app/api_rotation.py
def execute_with_rotation(self, provider, api_call, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            key = self.get_key(provider)
            return api_call(key)
        except RateLimitError:
            self.mark_cooldown(provider, key)
            if attempt == max_attempts - 1:
                raise
```

### フォールバック

**TTS 6段階**:
```
ElevenLabs
  ↓ (quota exhausted)
VOICEVOX
  ↓ (server down)
OpenAI TTS
  ↓ (API error)
gTTS
  ↓ (network error)
Coqui TTS
  ↓ (model load failed)
pyttsx3
```

**動画生成 3段階**:
```
Stock Footage B-roll
  ↓ (API error / no clips)
Static Background (theme-based)
  ↓ (rendering error)
Simple Fallback (solid color)
```

### 監視ポイント / 再発防止の要点

| カテゴリ | 再発防止策 | ログ出力 |
|-----------|------------|-----------|
| LLM引数ズレ | `GeminiAdapter` が SDK 呼び出しを一元化（`timeout` 等は吸収） | `app/crew/tools/ai_clients.py` DEBUG ログ |
| CrewAI出力崩れ | `_extract_script_text_from_string` で JSON / dialogues を再構成し、fallback 優先順位で必ず台本を確保 | `app/crew/flows.py` WARN/INFO（raw preview と fallback source）|
| Pydantic extra forbid | `AppSettings` は `extra="allow"` で起動阻害を回避し、順次サブモデル化して厳格化 | 起動ログ + `test_settings_schema` |
| Gemini 429 | `APIKeyRotationManager` が `RetryInfo` を記録し、キーをクールダウン | Step2 ERROR ログ + Google Sheets 実行履歴 |

---

## 関連ドキュメント

- [SETUP.md](SETUP.md) - 環境構築
- [FEATURES.md](FEATURES.md) - 機能詳細
- [API_REFERENCE.md](API_REFERENCE.md) - API管理
- [README_CREWAI.md](README_CREWAI.md) - CrewAI詳細
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - トラブルシューティング
