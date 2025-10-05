# データ管理システム

実行ログ、メタデータ、YouTube統計の記録・管理システム

## 目次

- [1. 概要](#1-概要)
- [2. Google Sheets セットアップ](#2-google-sheets-セットアップ)
- [3. データ記録](#3-データ記録)
- [4. データ形式](#4-データ形式)
- [5. 分析・活用](#5-分析活用)
- [6. トラブルシューティング](#6-トラブルシューティング)

---

## 1. 概要

### データフロー

```
Workflow Execution
       ↓
WorkflowResult + Metadata
       ↓
   ┌─────┴─────┐
   ↓           ↓
JSONL Log   Google Sheets (3 tabs)
(分析用)     (人間向け)
   ↓           ↓
CSV Backup  Dashboard View
```

### 記録内容

1. **実行ログ** (`output/execution_log.jsonl`)
   - run_id, timestamp, mode
   - 品質指標（WOWスコア、日本語純度、保持率予測）
   - 実行時間、コスト
   - YouTube統計（views, CTR, retention）

2. **メタデータ** (`data/metadata_history.csv`)
   - タイトル、説明文、タグ
   - SEOキーワード、ターゲット視聴者
   - ニュースト ピック

3. **Google Sheets** (3タブ)
   - `performance_dashboard`: サマリービュー
   - `quality_metrics`: CrewAI品質指標
   - `production_insights`: 実行時間・コスト詳細

---

## 2. Google Sheets セットアップ

### 前提条件

- Google Cloud Project
- サービスアカウント（Service Account）
- スプレッドシートID

### 手順1: サービスアカウント作成

#### Google Cloud Console

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを選択（または新規作成）
3. **IAM & Admin** > **Service Accounts** に移動
4. **CREATE SERVICE ACCOUNT** をクリック

#### サービスアカウント設定

- **Name**: `youtuber-automation`（任意）
- **Role**: `Editor` または `Owner`（推奨: 最小権限で `Sheets Editor`）
- **CREATE AND CONTINUE** をクリック

#### 認証キーの作成

1. 作成したサービスアカウントを選択
2. **KEYS** タブに移動
3. **ADD KEY** > **Create new key**
4. **JSON** を選択
5. ダウンロードされたJSONファイルを保存

   例: `secret/service-account.json`

### 手順2: Google Sheets API 有効化

1. [Google Cloud Console](https://console.cloud.google.com/) に戻る
2. **APIs & Services** > **Library** に移動
3. 「Google Sheets API」を検索
4. **ENABLE** をクリック

### 手順3: スプレッドシートの共有設定

#### 共有権限の付与

1. スプレッドシートを開く
   - 新規作成: [Google Sheets](https://sheets.google.com/)
   - または既存のスプレッドシートを使用

2. **共有** ボタンをクリック

3. サービスアカウントのメールアドレスを追加
   - JSONファイルの `client_email` フィールドを確認
   - 例: `youtuber-automation@project-id.iam.gserviceaccount.com`

4. 権限を **編集者** に設定

5. **送信** をクリック

6. スプレッドシートのIDをコピー
   - URL: `https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit`
   - `[SHEET_ID]` 部分をコピー

### 手順4: 環境変数の設定

#### 方法A: ファイルパスを指定（推奨）

`secret/.env` ファイルに追加:

```bash
# Google Sheets認証
GOOGLE_APPLICATION_CREDENTIALS=secret/service-account.json
GOOGLE_SHEET_ID=1P-L4Pt06iwySy0EMx7HdqGT2x0kLMGLvx-P-H8CzqoE
```

**注意**:
- `app/config/paths.py` の `ProjectPaths` がリポジトリルートから相対パスを解決します
- JSONファイルは `secret/` ディレクトリに配置（`.gitignore` 済み）

**例**（絶対パス指定が必要な場合）:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/youtuber/secret/service-account.json
```

> **TIP:** 自動化ジョブから実行する場合は `cd /path/to/youtuber` を行ってからスクリプトを呼び出し、相対パスが `ProjectPaths` と一致するようにしてください。

#### 方法B: JSON文字列を直接設定

`secret/.env` ファイルに追加:

```bash
GOOGLE_APPLICATION_CREDENTIALS='{"type":"service_account","project_id":"your-project","private_key_id":"xxx","private_key":"-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----\n","client_email":"xxx@xxx.iam.gserviceaccount.com","client_id":"xxx","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/xxx"}'
GOOGLE_SHEET_ID=1P-L4Pt06iwySy0EMx7HdqGT2x0kLMGLvx-P-H8CzqoE
```

**注意**:
- JSON内の改行は `\n` でエスケープ
- シングルクォートで囲む
- private_keyの `\n` は必須

### 手順5: 設定の反映

```bash
# 環境変数を読み込む
source secret/.env

# 設定確認
echo $GOOGLE_APPLICATION_CREDENTIALS
echo $GOOGLE_SHEET_ID

# または
uv run python -c "from app.config import settings; print(settings.google_sheet_id)"
```

### 手順6: 動作確認

```bash
# ワークフロー実行（自動的にSheetsに記録される）
uv run python3 -m app.main daily

# Google Sheetsを確認
# 3つのタブが自動作成されます:
# - performance_dashboard
# - quality_metrics
# - production_insights
```

---

## 3. データ記録

### 自動記録

**ワークフロー実行時に自動記録**:

```python
# app/main.py
from app.metadata_storage import metadata_storage

# Step 10: Feedback Logging
result = WorkflowResult(
    run_id="abc123",
    mode="daily",
    title="経済ニュース",
    # ... その他のフィールド
)

# JSONL + Google Sheets + CSV に自動保存
metadata_storage.store(result)
```

### 手動記録

```python
from app.metadata_storage import metadata_storage
from app.models.workflow import WorkflowResult

result = WorkflowResult(
    run_id="manual_001",
    mode="special",
    title="臨時ニュース",
    wow_score=8.5,
    japanese_purity=97.0,
    retention_prediction=55.0,
    execution_time=480.0,
    total_cost=0.15,
    # ...
)

metadata_storage.store(result)
```

### YouTube統計の更新

**クーロンジョブで定期更新**:

```bash
# crontab -e
# 毎日午前3時に実行
0 3 * * * cd /path/to/youtuber && uv run python scripts/update_youtube_stats.py
```

**手動更新**:

```bash
uv run python scripts/update_youtube_stats.py
```

---

## 4. データ形式

### JSONL Log (`output/execution_log.jsonl`)

**1行 = 1ワークフロー実行**

```json
{
  "run_id": "abc123",
  "timestamp": "2025-01-04T10:30:00",
  "mode": "daily",
  "title": "経済ニュース解説",
  "video_id": "xyz789",
  "video_path": "output/.../video.mp4",
  "wow_score": 8.5,
  "japanese_purity": 97.0,
  "retention_prediction": 55.0,
  "surprise_points": 6,
  "emotion_peaks": 7,
  "curiosity_gaps": 4,
  "visual_instructions": 18,
  "concrete_numbers": 12,
  "execution_time": 480.0,
  "total_cost": 0.15,
  "step_costs": {
    "news_collection": 0.01,
    "script_generation": 0.12,
    "metadata_generation": 0.01
  },
  "hook_type": "衝撃的事実",
  "topic_tags": ["日銀政策", "円安", "株価"],
  "youtube_feedback": {
    "views": 10000,
    "likes": 500,
    "comments": 50,
    "watch_time_hours": 150.0,
    "ctr": 8.5,
    "retention_30s": 85.0,
    "top_comments": ["勉強になりました", "わかりやすい"]
  }
}
```

### CSV (`data/metadata_history.csv`)

| カラム | 説明 | 例 |
|--------|------|-----|
| timestamp | 生成日時 | 2025-10-03T13:54:24.503090 |
| run_id | 実行ID | abc123 |
| mode | モード | daily/special/breaking |
| title | タイトル | 【速報】日経平均10%急騰！ |
| description | 説明文 | 本日の日経平均株価の急騰について... |
| tags | タグ（JSON） | ["経済ニュース", "株価"] |
| category | カテゴリ | News & Politics |
| thumbnail_text | サムネイルテキスト | 10%急騰 |
| seo_keywords | SEOキーワード（JSON） | ["日経平均", "株価急騰"] |
| target_audience | ターゲット視聴者 | 投資家 |
| estimated_watch_time | 推定視聴時間 | 15分 |
| news_count | ニュース件数 | 3 |
| news_topics | ニューストピック | 日経平均が年初来高値を更新 |
| video_url | 動画URL | https://youtu.be/xxx |
| view_count | 視聴回数 | 10000 |
| like_count | いいね数 | 500 |
| comment_count | コメント数 | 50 |
| ctr | クリック率 | 8.5% |
| avg_view_duration | 平均視聴時間 | 450.5s |

### Google Sheets (3タブ)

#### performance_dashboard

| run_id | timestamp | mode | title | video_id | wow_score | japanese_purity | retention_prediction | execution_time | total_cost |
|--------|-----------|------|-------|----------|-----------|-----------------|---------------------|----------------|------------|
| abc123 | 2025-01-04 10:30 | daily | 経済ニュース | xyz789 | 8.5 | 97.0 | 55.0 | 480.0 | 0.15 |

#### quality_metrics

| run_id | surprise_points | emotion_peaks | curiosity_gaps | visual_instructions | concrete_numbers | hook_type | topic_tags |
|--------|----------------|---------------|----------------|-------------------|-----------------|-----------|------------|
| abc123 | 6 | 7 | 4 | 18 | 12 | 衝撃的事実 | 日銀政策,円安 |

#### production_insights

| run_id | timestamp | news_collection_time | news_collection_cost | script_generation_time | script_generation_cost | ... |
|--------|-----------|---------------------|---------------------|----------------------|----------------------|-----|
| abc123 | 2025-01-04 | 5.0 | 0.01 | 180.0 | 0.12 | ... |

---

## 5. 分析・活用

### 分析ツール

**FeedbackAnalyzer** (`app/analytics.py`):

```python
from app.analytics import FeedbackAnalyzer

analyzer = FeedbackAnalyzer("output/execution_log.jsonl")

# 週次レポート
weekly = analyzer.generate_weekly_report()
print(f"平均WOWスコア: {weekly['avg_wow_score']}")
print(f"総動画数: {weekly['total_videos']}")
print(f"平均実行時間: {weekly['avg_execution_time']}s")

# フック戦略分析
hooks = analyzer.analyze_hooks()
print(f"最も効果的なフック: {hooks['best_hook']}")
print(f"平均視聴回数: {hooks['衝撃的事実']['avg_views']}")

# トピック分布
topics = analyzer.topic_distribution()
for topic, count in topics.items():
    print(f"{topic}: {count}本")
```

### CLI レポート

```bash
# 週次レポート
python scripts/tasks.py analytics

# フック戦略分析
python scripts/tasks.py analytics --hooks

# トピック分布
python scripts/tasks.py analytics --topics

```

### 過去データの活用

**高パフォーマンス動画の分析**:

```python
from app.metadata_storage import metadata_storage

# 視聴回数トップ10
top_videos = metadata_storage.get_top_performing(limit=10)
for video in top_videos:
    print(f"{video['title']}: {video['view_count']} views")

# 高WOWスコア動画
high_wow = metadata_storage.filter_by_wow_score(min_score=9.0)
print(f"WOW 9.0+動画: {len(high_wow)}本")

# モード別集計
daily_videos = metadata_storage.filter_by_mode("daily")
special_videos = metadata_storage.filter_by_mode("special")
```

### 手動でのデータ参照

**JSONL**:
```bash
# 最新10件
tail -10 output/execution_log.jsonl | jq .

# WOWスコア8.5以上
cat output/execution_log.jsonl | jq 'select(.wow_score >= 8.5)'

# 特定日付
cat output/execution_log.jsonl | jq 'select(.timestamp | startswith("2025-01-04"))'
```

**CSV**:
```bash
# csvkitでクエリ
csvstat data/metadata_history.csv

# 視聴回数トップ10
csvsort -c view_count -r data/metadata_history.csv | head -11

# 特定モードのみ
csvgrep -c mode -m daily data/metadata_history.csv
```

---

## 6. トラブルシューティング

### エラー: Permission denied

**原因**: サービスアカウントがSheetにアクセスできない

**解決**:
1. Google Sheetsの共有設定を確認
2. `client_email` を編集者として追加
3. スプレッドシートIDが正しいか確認

```bash
# 環境変数確認
echo $GOOGLE_SHEET_ID

# サービスアカウントメール確認
cat secret/service-account.json | jq -r .client_email
```

### エラー: GOOGLE_APPLICATION_CREDENTIALS not found

**原因**: 環境変数が未設定または読み込まれていない

**解決**:
```bash
# .envファイル確認
cat secret/.env | grep GOOGLE_APPLICATION_CREDENTIALS

# 環境変数読み込み
source secret/.env

# 確認
echo $GOOGLE_APPLICATION_CREDENTIALS
```

### エラー: Invalid credentials

**原因**: JSONファイルが壊れているか、権限不足

**解決**:
1. JSONファイルの構文確認
   ```bash
   cat secret/service-account.json | jq .
   ```
2. サービスアカウントに `Sheets Editor` ロールが付与されているか確認
3. Google Sheets APIが有効化されているか確認

### データが記録されない

**原因1**: Google Sheets連携が無効

**確認**:
```python
from app.config import settings
print(settings.google_sheet_id)  # Noneでないか確認
```

**原因2**: metadata_storage.store()が呼ばれていない

**確認**:
```bash
# ログ確認
tail -f logs/daily_run_*.log | grep "metadata_storage"
```

### シートタブが作成されない

**原因**: 初回実行時にタブ作成に失敗

**解決**:
1. 手動でタブ作成:
   - `performance_dashboard`
   - `quality_metrics`
   - `production_insights`
2. ヘッダー行を追加（app/metadata_storage.pyの`_ensure_sheet_tabs()`参照）

### JSONLファイルが破損

**原因**: 書き込み中のクラッシュ

**復旧**:
```bash
# 有効な行のみ抽出
cat output/execution_log.jsonl | jq -c . > output/execution_log_fixed.jsonl 2>/dev/null

# バックアップ作成
cp output/execution_log.jsonl output/execution_log_backup.jsonl
mv output/execution_log_fixed.jsonl output/execution_log.jsonl
```

---

## 関連ドキュメント

- [FEATURES.md](FEATURES.md#2-feedback-loop-system) - Feedback Loop詳細
- [SETUP.md](SETUP.md) - 環境構築
- [API_REFERENCE.md](API_REFERENCE.md) - API設定
- [ARCHITECTURE.md](ARCHITECTURE.md) - システム構成
