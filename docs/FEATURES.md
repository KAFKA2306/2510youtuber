# 機能一覧

YouTube自動生成システムの全機能詳細ドキュメント

## 目次

- [1. Stock Footage B-roll](#1-stock-footage-b-roll)
- [2. Feedback Loop System](#2-feedback-loop-system)
- [3. File Archival](#3-file-archival)
- [4. Google Sheets Integration](#4-google-sheets-integration)
- [5. Japanese Quality System](#5-japanese-quality-system)
- [6. Video Quality Validation](#6-video-quality-validation)
- [7. Video Review AI](#7-video-review-ai)

---

## 1. Stock Footage B-roll

プロフェッショナルなストック映像によるB-roll自動生成機能

### 概要

無料のストックビデオAPI（Pexels/Pixabay）を使用して、スクリプト内容に合った映像を自動的に検索・ダウンロードし、B-rollシーケンスを生成します。

### 設定

**config.yaml:**
```yaml
stock_footage:
  enabled: true
  clips_per_video: 5
  ffmpeg_path: ffmpeg
```

**環境変数（.env）:**
```bash
PEXELS_API_KEY=your_key_here      # 推奨（無料・無制限）
PIXABAY_API_KEY=your_key_here     # フォールバック
```

### 主要コンポーネント

#### StockFootageManager (`app/services/media/stock_footage_manager.py`)
- **Pexels API**: 無料・無制限でHD動画を取得
- **Pixabay API**: フォールバック
- **キャッシュ管理**: 24時間キャッシュでAPI呼び出しを削減
- **自動ダウンロード**: 複数クリップの並列ダウンロード

#### VisualMatcher (`app/services/media/visual_matcher.py`)
- **日英キーワード変換**: 経済 → economy, 株式 → stock market等
- **50+キーワードマッピング**: 金融ニュース特化
- **カテゴリ検出**: スクリプトから視覚的キーワードを抽出
- **カスタム対応**: visual_instructions対応

#### BRollGenerator (`app/services/media/broll_generator.py`)
- **FFmpeg合成**: 複数クリップをシームレスに結合
- **クロスフェード**: 1秒のトランジション
- **Ken Burns効果**: ズーム・パン効果
- **カラーグレーディング**: プロフェッショナルな見た目

### フォールバック戦略

```
1. Stock Footage B-roll（有効時）
   ↓ 失敗
2. Enhanced Static Background（テーマベース）
   ↓ 失敗
3. Simple Fallback（単色背景）
```

### 使用例

```python
from app.video import VideoGenerator

gen = VideoGenerator()
video_path = gen.generate_video(
    audio_path="audio.wav",
    subtitle_path="subs.srt",
    script_content="日本経済の最新動向...",
    news_items=[{"title": "日銀政策..."}],
    use_stock_footage=True  # または None で設定から自動取得
)
```

### パフォーマンス

- **クリップ数**: 5clips（デフォルト）
- **ダウンロード時間**: ~10-30秒（ネットワーク依存）
- **生成時間**: ~20-40秒（6分動画の場合）
- **キャッシュヒット**: 2回目以降は即座

### トラブルシューティング

**問題**: Stock footage generation failedエラー
- **原因1**: API keyが未設定
  - **解決**: PEXELS_API_KEYを.envに追加
- **原因2**: ネットワークエラー
  - **解決**: 自動的にstatic backgroundにフォールバック
- **原因3**: キーワードマッチなし
  - **解決**: visual_matcherのキーワードマッピング追加

---

## 2. Feedback Loop System

継続的改善のためのフィードバックループシステム

### 概要

ワークフロー実行ログ、品質指標、YouTube統計を統合管理し、分析による継続的改善を実現します。

### データフロー

```
Workflow Execution
       ↓
WorkflowResult (rich metrics)
       ↓
   ┌─────┴─────┐
   ↓           ↓
JSONL Log   Google Sheets (3 tabs)
(analytics)   (human-friendly)
   ↓
Analytics Engine
   ↓
Insights & Recommendations
```

### ストレージ

#### 1. JSONL Log
**ファイル**: `output/execution_log.jsonl`
- 完全な実行データ（プログラム分析用）
- 1行 = 1ワークフロー実行
- 追記のみ（append-only）

#### 2. Google Sheets
**3つのタブ**:
1. **performance_dashboard**: サマリービュー
   - run_id, timestamp, mode, title, video_id
   - wow_score, japanese_purity, retention_prediction
   - execution_time, total_cost
2. **quality_metrics**: CrewAI品質指標
   - surprise_points, emotion_peaks, curiosity_gaps
   - visual_instructions, concrete_numbers
3. **production_insights**: 実行時間・コスト詳細
   - step毎の実行時間とコスト
   - API使用量内訳

### データモデル

**WorkflowResult** (`app/models/workflow.py`):
```python
class WorkflowResult:
    # 基本データ
    run_id: str
    mode: str
    title: str
    video_id: str

    # 品質指標
    wow_score: float
    japanese_purity: float
    retention_prediction: float
    surprise_points: int
    emotion_peaks: int
    curiosity_gaps: int
    visual_instructions: int
    concrete_numbers: int

    # 実行データ
    execution_time: float
    total_cost: float
    step_costs: Dict[str, float]
    hook_type: str  # 衝撃的事実/疑問提起/意外な数字
    topic_tags: List[str]
```

**YouTubeFeedback** (クーロンジョブで更新):
```python
class YouTubeFeedback:
    views: int
    likes: int
    comments: int
    watch_time_hours: float
    ctr: float
    retention_30s: float
    top_comments: List[str]
```

### 分析機能

**FeedbackAnalyzer** (`app/analytics.py`):
```python
from app.analytics import FeedbackAnalyzer

analyzer = FeedbackAnalyzer("output/execution_log.jsonl")

# 週次レポート
weekly = analyzer.generate_weekly_report()
print(f"平均WOWスコア: {weekly['avg_wow_score']}")
print(f"最高パフォーマンス動画: {weekly['top_performer']}")

# フック戦略分析
hooks = analyzer.analyze_hooks()
print(f"最も効果的なフック: {hooks['best_hook']}")

# トピック分布
topics = analyzer.topic_distribution()
```

### CLI使用例

```bash
# 週次レポート
python scripts/analytics_report.py

# フック戦略分析
python scripts/analytics_report.py --hooks

# トピック分布
python scripts/analytics_report.py --topics

# 特定期間のレポート
python scripts/analytics_report.py --start 2025-01-01 --end 2025-01-31
```

### 設定

**Google Sheets認証**:
```bash
# サービスアカウントJSON（推奨）
export GOOGLE_APPLICATION_CREDENTIALS=secret/service-account.json

# Sheet ID
export GOOGLE_SHEET_ID=1P-L4Pt06iwySy0EMx7HdqGT2x0kLMGLvx-P-H8CzqoE

> **HINT:** 環境変数に相対パスを設定する場合は、コマンド実行前にプロジェクトルートへ移動してください。`ProjectPaths` がリポジトリ基準でパスを解決します。
```

詳細: [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

### YouTube統計更新

**クーロンジョブ** (`scripts/update_youtube_stats.py`):
```bash
# 毎日午前3時に実行
0 3 * * * cd /path/to/youtuber && uv run python scripts/update_youtube_stats.py
```

---

## 3. File Archival

動画ファイルの永続的な保存システム

### 問題

- 生成された動画ファイルが2時間後に消える
- `fallback_video_TIMESTAMP.mp4` として一時ファイル扱い
- YouTube投稿後にソースファイルが消失

### 解決策

TDD（Test-Driven Development）アプローチで実装:
1. **RED**: 13個のテストを先に作成（全て失敗）
2. **GREEN**: 最小限のコードで全テスト通過
3. **REFACTOR**: クリーンアップと最適化

### ディレクトリ構造

```
output/{timestamp}_{run_id}_{sanitized_title}/
  ├── video.mp4
  ├── audio.wav
  ├── thumbnail.png
  ├── script.txt
  └── subtitles.srt
```

**例**:
```
output/20251004_013514_63ad55ae_警告あなたのNISAが円安を加速/
  ├── video.mp4
  ├── audio.wav
  ├── thumbnail.png
  └── subtitles.srt
```

### API

**FileArchivalManager** (`app/services/file_archival.py`):

```python
from app.services.file_archival import FileArchivalManager

manager = FileArchivalManager()

# ファイルをアーカイブ
archived = manager.archive_workflow_files(
    run_id="abc123",
    timestamp="20251004_150000",
    title="Video Title",
    files={
        "video": "/tmp/video.mp4",
        "audio": "/tmp/audio.wav",
        "thumbnail": "/tmp/thumbnail.png"
    }
)
# Returns: {"video": "output/.../video.mp4", ...}

# 過去のワークフロー一覧
workflows = manager.list_archived_workflows()
for wf in workflows:
    print(f"{wf['run_id']}: {wf['title']} ({wf['timestamp']})")

# 古いファイルのクリーンアップ（オプション）
to_cleanup = manager.get_files_to_cleanup(retention_days=30)
```

### 自動統合

**GenerateVideoStep** (`app/workflow/steps.py`):
- 動画生成後に自動的にアーカイブ
- WorkflowResultに保存パスを記録
- エラー時も部分的なファイルを保存

### 保持ポリシー

**デフォルト**: 無期限保持
**カスタム**:
```python
# 30日以上古いファイルをリスト
old_files = manager.get_files_to_cleanup(retention_days=30)

# 手動削除
for path in old_files:
    os.remove(path)
```

---

## 4. Google Sheets Integration

実行ログのGoogle Sheets同期機能

### セットアップ

#### 1. サービスアカウント作成

1. [Google Cloud Console](https://console.cloud.google.com)
2. プロジェクト作成
3. Google Sheets API有効化
4. サービスアカウント作成 → JSONキーダウンロード

#### 2. 環境変数設定

```bash
# .envに追加
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_SHEET_ID=your_sheet_id_here
```

#### 3. Sheet共有

サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）を「編集者」として追加

### Sheet構造

#### performance_dashboard
| run_id | timestamp | mode | title | video_id | wow_score | japanese_purity | retention_prediction | execution_time | total_cost |
|--------|-----------|------|-------|----------|-----------|-----------------|---------------------|----------------|------------|

#### quality_metrics
| run_id | surprise_points | emotion_peaks | curiosity_gaps | visual_instructions | concrete_numbers | hook_type | topic_tags |
|--------|----------------|---------------|----------------|-------------------|-----------------|-----------|------------|

#### production_insights
| run_id | timestamp | step_1_time | step_1_cost | step_2_time | step_2_cost | ... | api_calls | errors |
|--------|-----------|-------------|-------------|-------------|-------------|-----|-----------|--------|

### 使用例

```python
from app.metadata_storage import metadata_storage
from app.models.workflow import WorkflowResult

result = WorkflowResult(
    run_id="abc123",
    mode="daily",
    title="経済ニュース",
    wow_score=8.5,
    # ... その他のフィールド
)

# JSONL + Google Sheets に同時記録
metadata_storage.store(result)
```

### 手動同期

```bash
# 既存のJSONLデータをSheetsに再同期
python scripts/sync_to_sheets.py
```

### トラブルシューティング

**エラー**: `Permission denied`
- **原因**: サービスアカウントがSheetにアクセスできない
- **解決**: Sheet設定で`client_email`を編集者として追加

**エラー**: `GOOGLE_APPLICATION_CREDENTIALS not found`
- **原因**: 環境変数が未設定
- **解決**: `source secret/.env` または `.env`ファイル確認

---

## 5. Japanese Quality System

日本語純度チェックシステム

### 概要

生成過程で日本語純度が低下しないよう、自動的に改善・リグレッション防止を行います。

### 品質基準

**config.yaml**:
```yaml
quality_thresholds:
  # 日本語純度は改善処理で元のスクリプトより悪化しないことのみ保証
```

### チェックポイント

1. **Agent 7実行後**: Japanese Purity Polisher完了時
2. **最終検証**: スクリプト生成完了時
3. **字幕生成時**: 字幕テキストのクリーニング

### 許可されるパターン

- 英数字（数値・記号）
- 句読点（。、！？）
- 括弧（「」『』（））
- スペース・改行

### クリーニング機能

**japanese_quality.py**:
```python
from app.japanese_quality import clean_subtitle_text, validate_subtitle_text

# 検証
text = "これはテストtext"
is_valid = validate_subtitle_text(text)  # False (英語混入)

# クリーニング
cleaned = clean_subtitle_text(text)  # "これはテスト"
```

### CrewAI統合

**Agent 7: Japanese Purity Polisher**:
- 英語メタデータ（"wow_score", "json"等）を除去
- 自然な日本語に置換
- 改善結果が元の純度を下回る場合は自動的に元の原稿へロールバック

### 字幕統合

**SubtitleAligner** (`app/align_subtitles.py`):
```python
# 字幕生成時に自動クリーニング
if HAS_JAPANESE_QUALITY_CHECK:
    if not validate_subtitle_text(original_text):
        cleaned_text = clean_subtitle_text(original_text)
        subtitle["text"] = cleaned_text
```

---

## 6. Video Quality Validation

動画・音声・字幕の品質検証システム

### 概要

生成された動画ファイルの品質を自動検証し、問題を早期検出します。

### 設定

**config.yaml**:
```yaml
media_quality:
  enabled: true
  report_dir: "data/qa_reports"
  gating:
    enforce: true                    # 品質基準を強制
    fail_on_missing_inputs: true     # 入力ファイル不足でエラー
    retry_attempts: 1                # 失敗時のリトライ回数
    retry_start_step: script_generation  # リトライ開始ステップ

  audio:
    enabled: true
    peak_dbfs_max: -1.0              # ピーク音量（クリッピング防止）
    rms_dbfs_min: -24.0              # RMS音量最小値
    rms_dbfs_max: -10.0              # RMS音量最大値
    max_silence_seconds: 1.5         # 最大無音時間

  video:
    enabled: true
    expected_resolution:
      width: 1920
      height: 1080
    min_fps: 24.0
    max_fps: 61.0
    min_bitrate_kbps: 3500           # 最低ビットレート

  subtitles:
    enabled: true
    min_line_coverage: 0.9           # 字幕カバレッジ90%
    max_timing_gap_seconds: 1.5      # 字幕間の最大ギャップ
```

### 検証項目

#### Audio
- **Peak DBFS**: クリッピング検出（-1.0 dB以下）
- **RMS DBFS**: 音量レベル（-24.0 ~ -10.0 dB）
- **無音検出**: 1.5秒以上の無音区間をチェック

#### Video
- **解像度**: 1920x1080を期待
- **FPS**: 24-60の範囲
- **ビットレート**: 最低3.5 Mbps
- **コーデック**: H.264推奨

#### Subtitles
- **カバレッジ**: 音声の90%以上に字幕
- **タイミングギャップ**: 字幕間の空白が1.5秒以下
- **フォーマット**: SRT形式

### レポート

**出力先**: `data/qa_reports/{run_id}_qa_report.json`

```json
{
  "run_id": "abc123",
  "timestamp": "2025-01-04T10:30:00",
  "overall_status": "PASS",
  "audio": {
    "status": "PASS",
    "peak_dbfs": -2.3,
    "rms_dbfs": -18.5,
    "max_silence": 0.8,
    "issues": []
  },
  "video": {
    "status": "PASS",
    "resolution": "1920x1080",
    "fps": 30.0,
    "bitrate_kbps": 4500,
    "issues": []
  },
  "subtitles": {
    "status": "WARNING",
    "coverage": 0.92,
    "max_gap": 1.2,
    "issues": ["Gap at 02:30 (1.8s)"]
  }
}
```

### ゲーティング

**enforce: true** の場合:
- **FAIL**: ワークフロー停止、エラー通知
- **WARNING**: 続行、警告ログ
- **PASS**: 正常続行

**リトライロジック**:
```python
if qa_result.status == "FAIL" and gating.retry_attempts > 0:
    # script_generation ステップからリトライ
    workflow.restart_from(gating.retry_start_step)
```

### CLI使用例

```bash
# 動画の品質チェック
uv run python -m app.services.media.qa_pipeline /path/to/video.mp4

# レポート確認
cat data/qa_reports/abc123_qa_report.json | jq .
```

---

## 7. Video Review AI

生成済み動画のAIレビューシステム

### 概要

完成した動画をGemini Vision APIで分析し、次回制作への改善提案を生成します。

### 設定

**config.yaml**:
```yaml
video_review:
  enabled: true
  screenshot_interval_seconds: 60   # スクリーンショット間隔
  max_screenshots: 15               # 最大スクリーンショット数
  output_dir: "output/video_reviews"
  model: gemini-2.5-pro
  temperature: 0.4
  max_output_tokens: 2048
  store_feedback: true              # フィードバックをDBに保存
```

### 使用方法

#### CLI

```bash
# 動画をレビュー
uv run python -m scripts.video_review "output/video.mp4" \
    --title "経済ニュース解説" \
    --duration "8分12秒"

# JSONで出力
uv run python -m scripts.video_review "output/video.mp4" --json

# 既存のスクリーンショットを再生成
uv run python -m scripts.video_review "output/video.mp4" --force
```

#### Python API

```python
from app.services.video_review import get_video_review_service

service = get_video_review_service()

result = service.review_video(
    video_path="output/video.mp4",
    video_id="abc123",  # オプション
    metadata={"title": "動画タイトル", "duration": "8:12"},
    force_capture=False  # スクリーンショット再生成
)

print(result.feedback.summary)
for item in result.feedback.improvement_suggestions:
    print(f"- {item}")
```

### レビュー内容

**VideoReviewFeedback** (`app/models/video_review.py`):
```python
class VideoReviewFeedback:
    summary: str                         # 総合評価（1-2文）
    positive_highlights: List[str]       # 良かった点
    improvement_suggestions: List[str]   # 改善提案
    retention_risks: List[str]           # 離脱リスク箇所
    next_video_actions: List[str]        # 次回試すべきこと
    visual_variety_score: int            # 視覚バリエーション（1-10）
    text_readability_score: int          # テキスト可読性（1-10）
    pacing_score: int                    # テンポ（1-10）
```

### スクリーンショット

**保存先**: `output/video_reviews/{video_name}/`
```
output/video_reviews/video/
  ├── shot_001.png  (00:00)
  ├── shot_002.png  (01:00)
  ├── shot_003.png  (02:00)
  └── ...
```

### レビュー例

```
=============================================================
レビュー結果: video.mp4
=============================================================
要約: 動画全体として統一感があり、字幕も読みやすい。ただし、視覚的なバリエーションが少なく、単調な印象を与える可能性がある。

◎ 良かった点
  - 字幕が大きく、読みやすいフォントで表示されている
  - 背景色が落ち着いており、長時間視聴に適している

△ 改善提案
  - グラフやチャートなど、視覚的な資料を追加する
  - 30秒ごとに画面変化（アニメーション、画像切り替え）を入れる
  - 重要な数字を強調表示する

⚠ 離脱リスク
  - 開始30秒で画面変化がなく、視聴者が離脱する可能性が高い
  - 中盤（3-5分）でペースが落ち、飽きられやすい

▶ 次の動画で試すこと
  - Stock Footage機能を有効化してB-roll映像を追加
  - 重要な数値をテロップで大きく表示
  - 話者の切り替わりで画面効果を入れる

スクリーンショット保存先: output/video_reviews/video
```

### 統合

**WorkflowResult拡張** (`app/models/workflow.py`):
```python
class WorkflowResult:
    # ... 既存フィールド

    video_review: Optional[VideoReviewFeedback] = None
```

**自動レビュー** (`app/workflow/steps.py`):
```python
# 動画生成後に自動レビュー（オプション）
if settings.video_review.enabled:
    result.video_review = review_service.review_video(
        video_path=result.video_path,
        metadata={"title": result.title}
    )
```

---

## 関連ドキュメント

- [SETUP.md](SETUP.md) - 環境構築
- [API_REFERENCE.md](API_REFERENCE.md) - API管理・レート制限
- [VOICEVOX.md](VOICEVOX.md) - VOICEVOX設定
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - トラブルシューティング
- [README_CREWAI.md](README_CREWAI.md) - CrewAI詳細
