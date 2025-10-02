# 環境構築とセットアップガイド

## 🎉 Phase 1完了: CrewAI統合済み

このシステムは**WOW Script Creation Crew**を搭載しています。7つのAIエージェントが協力して、視聴維持率50%+を目指す高品質な台本を自動生成します。

## 事前準備チェックリスト

### 必要なアカウント

- [ ] **Perplexity**: ニュース収集用
- [ ] **Google Cloud**: Gemini API・Sheets・Drive・YouTube Data API用
  - ⚠️ **重要**: Vertex AI APIまたは直接のGemini API（CrewAI用）
- [ ] **ElevenLabs**: TTS（音声合成）用
- [ ] **Discord**: 運用通知用（Webhook URL）
- [ ] **Render**: 実行基盤（Cronジョブ）用（オプション）
- [ ] **GitHub**: コード管理・自動デプロイ用（オプション）

### 技術要件

- Python 3.8以上
- Git基本操作
- 基本的なAPIキー管理知識

## APIキー取得手順

### 1. Perplexity API

1. [Perplexity AI](https://www.perplexity.ai/)にアクセス
2. アカウント作成・ログイン
3. Settings -> API Keysセクションで新しいキーを生成
4. **メモ**: `PERPLEXITY_API_KEY=pplx-...`

### 2. Google Cloud Platform

#### Gemini API（CrewAI統合対応）

**CrewAI WOW Script Creation Crewを使用するには、以下のいずれかが必要です:**

##### オプションA: Google AI Studio（推奨・簡単）

1. [Google AI Studio](https://makersuite.google.com/)にアクセス
2. 新しいAPIキーを作成
3. **メモ**: `GEMINI_API_KEY=AIza...`

**利点**:
- セットアップが簡単
- すぐに使える
- 無料枠が大きい

**注意**:
- 一部の最新モデル（gemini-2.0-flash-exp等）はVertex AI経由でのみ利用可能な場合があります

##### オプションB: Vertex AI API（本番環境推奨）

**必要な手順**:

1. **Google Cloud Consoleでプロジェクト作成**
   ```
   https://console.cloud.google.com/
   ```

2. **Vertex AI APIを有効化**
   ```
   https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
   ```
   - プロジェクトを選択
   - 「APIを有効にする」をクリック

3. **サービスアカウント認証設定**
   - 既存のサービスアカウントにVertex AI権限を追加
   - または新規サービスアカウント作成
   - 必要な権限: `Vertex AI User`

4. **.envファイルに追加**
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=secret/probable-setup-435816-r8-96a2fbb8608e.json
   GEMINI_API_KEY=AIza...  # Google AI Studio のキーも併用可能
   ```

**利点**:
- 最新モデルへのアクセス
- エンタープライズグレードのSLA
- 高度な管理・監視機能

**現在のエラーと解決方法**:

テスト実行時に以下のエラーが出た場合:
```
Vertex AI API has not been used in project probable-setup-435816-r8
```

**解決策**:
1. 上記のVertex AI APIを有効化
2. または、直接Gemini APIを使用するよう設定変更（下記参照）

##### CrewAI設定の切り替え

**Vertex AIを使わない場合（簡易設定）**:

`app/config_prompts/prompts/agents.yaml` を編集:
```yaml
agents:
  deep_news_analyzer:
    model: gemini-pro  # gemini-2.0-flash-exp から変更
    # ...
```

または環境変数で制御:
```env
# CrewAIを一時的に無効化（従来の3段階チェック使用）
USE_CREWAI_SCRIPT_GENERATION=false
```

#### Google Services（Sheets, Drive, YouTube）

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクト作成
2. 以下のAPIを有効化：
   - Google Sheets API
   - Google Drive API
   - YouTube Data API v3
3. 「認証情報」→「サービスアカウント」を作成
4. JSON認証ファイルをダウンロード
5. **メモ**: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json`

#### YouTube Data API設定 🎥

**重要**: YouTube動画アップロードにはOAuth 2.0クライアントIDが必要です（サービスアカウントでは不可）

##### 手順

1. **Google Cloud Console にアクセス**
   ```
   https://console.cloud.google.com/apis/credentials?project=probable-setup-435816-r8
   ```

2. **OAuth 2.0 クライアント ID を作成**
   - 「+ 認証情報を作成」→「OAuth クライアント ID」をクリック
   - アプリケーションの種類: **「デスクトップ アプリ」**を選択
   - 名前: `YouTuber Automation`
   - 「作成」をクリック

3. **JSONファイルをダウンロード**
   - ダウンロードボタン（↓）をクリック
   - ファイルを `secret/youtube_oauth_client.json` として保存

4. **.envファイルを更新**
   ```env
   YOUTUBE_CLIENT_SECRET=secret/youtube_oauth_client.json
   ```

##### 初回認証（一度だけ必要）

最初にYouTube動画をアップロードする際、ブラウザ認証が必要です：

```bash
# セットアップスクリプトを実行
uv run python setup_youtube_oauth.py

# またはテストアップロードで認証
uv run python test_upload.py
```

**認証フロー**:
1. ブラウザが自動的に開きます
2. YouTubeチャンネルのGoogleアカウントでサインイン
3. アプリケーションに権限を付与（動画のアップロードと管理）
4. 認証完了後、`token.pickle`ファイルが作成されます
5. 以降は自動的に認証されます（トークンは自動更新）

**重要な注意事項**:
- ⚠️ `token.pickle`は秘密情報です。Gitにコミットしないでください
- ⚠️ サービスアカウントのJSONファイルはYouTube APIに使用できません
- ✅ OAuth clientの形式: `{"installed": {...}}` または `{"web": {...}}`
- ❌ サービスアカウントの形式: `{"type": "service_account", ...}` （これは使えません）

##### トラブルシューティング

**エラー**: "Service account credentials cannot be used for YouTube uploads"
- **原因**: サービスアカウントのJSONを使用している
- **解決**: 上記手順でOAuth 2.0クライアントIDを作成してください

**エラー**: "OAuth client file not found"
- **解決**: ファイルパスが正しいか確認してください
  ```bash
  ls -la secret/youtube_oauth_client.json
  ```

**認証トークンをリセットする場合**:
```bash
rm token.pickle
uv run python test_upload.py
```

### 3. ElevenLabs STT

1. [ElevenLabs](https://elevenlabs.io/)でアカウント作成
2. SettingsのAPI Keysからキーを取得
3. **メモ**: `ELEVENLABS_API_KEY=...`

### 4. Discord Webhook

1. DiscordサーバーでWebhookを作成
2. Webhook URLをコピー
3. **メモ**: `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...`

## Google Sheetsセットアップ

### 1. スプレッドシート作成

1. [Google Sheets](https://sheets.google.com/)で新しいシートを作成
2. シート名を設定（例：「YouTuber Automation」）
3. スプレッドシートIDをURLから取得
   - URL: `https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit`
4. **メモ**: `GOOGLE_SHEET_ID=[SHEET_ID]`

### 2. runsシート設計

シート名：`runs`

| カラム名 | 説明 | データ型 |
|---------|------|---------|
| run_id | 実行ID | 文字列 |
| status | 処理状態 | processing/done/error |
| started_at | 開始時刻 | 日時 |
| finished_at | 終了時刻 | 日時 |
| duration_sec | 処理時間（秒） | 数値 |
| mode | 実行モード | daily/special |
| prompt_a | ニュース収集プロンプト | 文字列 |
| search_results_json | 検索結果 | JSON文字列 |
| script_text | 生成台本 | 文字列 |
| audio_urls_json | 音声ファイルURL | JSON文字列 |
| stt_text | STT結果 | 文字列 |
| subtitle_srt | 字幕データ | 文字列 |
| video_url | 動画URL | 文字列 |
| title | 動画タイトル | 文字列 |
| description | 動画説明 | 文字列 |
| sources | 出典情報 | 文字列 |
| thumbnail_url | サムネイルURL | 文字列 |
| first_comment | 最初のコメント | 文字列 |
| error_log | エラーログ | 文字列 |

### 3. promptsシート設計

シート名：`prompts`

| カラム名 | 説明 | 初期値例 |
|---------|------|---------|
| prompt_a | ニュース収集 | 「今日の重要な経済ニュースを3-5件収集し、各項目について...」 |
| prompt_b | 台本生成 | 「以下のニュース要約をもとに、二人の専門家による対談形式で...」 |
| prompt_c | メタ生成 | 「動画のタイトル、説明文、タグを生成してください...」 |
| prompt_d | コメント生成 | 「この動画を聞いている女の子の立場で、最初のコメントを...」 |

### 4. 権限設定

1. サービスアカウントにシートへの編集権限を付与
2. シートの共有設定で、サービスアカウントのメールアドレスを追加
3. 権限：「編集者」に設定

## Google Drive設定

### フォルダ作成と権限

1. Google Driveで専用フォルダを作成（例：「YouTuber Content」）
2. フォルダIDをURLから取得
   - URL: `https://drive.google.com/drive/folders/[FOLDER_ID]`
3. **メモ**: `GOOGLE_DRIVE_FOLDER_ID=[FOLDER_ID]`
4. サービスアカウントにフォルダの編集権限を付与

## 環境変数設定

### .env ファイルテンプレート

```bash
# ===== AI APIs =====
# Perplexity（ニュース収集）
PERPLEXITY_API_KEY=pplx-...

# Gemini API（台本生成・CrewAI）
GEMINI_API_KEY=AIza...

# ElevenLabs（音声合成）
ELEVENLABS_API_KEY=sk_...

# オプション：複数APIキー（並列処理用）
GEMINI_API_KEY_2=AIza...
GEMINI_API_KEY_3=AIza...

# ===== Google Cloud Services =====
# サービスアカウント認証（Sheets, Drive, Vertex AI）
GOOGLE_APPLICATION_CREDENTIALS=secret/service-account-key.json

# Google Sheets（実行履歴・プロンプト管理）
GOOGLE_SHEET_ID=1ABC...

# Google Drive（動画バックアップ）
GOOGLE_DRIVE_FOLDER_ID=1DEF...

# YouTube（動画アップロード - OAuth必須）
YOUTUBE_CLIENT_SECRET=secret/youtube_oauth_client.json
# または JSON 文字列を直接設定 (推奨: ファイルパス)
# YOUTUBE_CLIENT_SECRET='{"web": {"client_id": "...", "client_secret": "...", ...}}'

# ===== CrewAI設定 =====
# CrewAI WOW Script Creation Crew の有効化
USE_CREWAI_SCRIPT_GENERATION=true

# 従来の3段階品質チェック（CrewAI無効時のみ）
USE_THREE_STAGE_QUALITY_CHECK=true

# 品質基準（オプション - config.yamlで設定推奨）
# WOW_SCORE_MIN=8.0
# JAPANESE_PURITY_MIN=95.0
# RETENTION_PREDICTION_MIN=50.0

# ===== 通知 =====
# Discord Webhook（実行結果通知）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Slack（オプション）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# ===== 開発設定 =====
DEBUG=true
LOG_LEVEL=INFO

# ローカルストレージ
LOCAL_OUTPUT_DIR=output
SAVE_LOCAL_BACKUP=true
```

### 本番環境での設定

#### Render環境変数

1. Renderダッシュボードでサービスを選択
2. Environment Variablesセクションで上記の変数を設定
3. JSONファイルは内容をそのまま環境変数として設定

#### GitHub Secretsの設定

1. GitHubリポジトリのSettings → Secrets and variables → Actions
2. Repository secretsに必要な変数を設定

## Python環境セットアップ

### requirements.txt

```txt
google-api-python-client==2.108.0
google-auth==2.23.4
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.1.1
httpx==0.25.1
elevenlabs==0.3.0
pydub==0.25.1
ffmpeg-python==0.2.0
Pillow==10.1.0
python-slugify==8.0.1
rapidfuzz==3.5.2
pandas==2.1.3
requests==2.31.0
python-dotenv==1.0.0
```

### ローカル開発環境

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# 依存関係インストール
pip install -r requirements.txt

# FFmpegのインストール（OS別）
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html からダウンロード
```

### 設定確認スクリプト

```python
# test_setup.py
import os
from google.oauth2 import service_account
import httpx

def test_apis():
    """API接続テスト"""

    # Perplexity
    perplexity_key = os.getenv('PERPLEXITY_API_KEY')
    print(f"✓ Perplexity API Key: {'設定済み' if perplexity_key else '未設定'}")

    # Google Credentials
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path and os.path.exists(creds_path):
        print("✓ Google Credentials: 設定済み")
    else:
        print("✗ Google Credentials: 未設定または不正なパス")

    # Gemini
    gemini_key = os.getenv('GEMINI_API_KEY')
    print(f"✓ Gemini API Key: {'設定済み' if gemini_key else '未設定'}")

    # ElevenLabs
    elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
    print(f"✓ ElevenLabs API Key: {'設定済み' if elevenlabs_key else '未設定'}")

    # Discord
    discord_url = os.getenv('DISCORD_WEBHOOK_URL')
    print(f"✓ Discord Webhook: {'設定済み' if discord_url else '未設定'}")

if __name__ == "__main__":
    test_apis()
```

### 実行テスト

```bash
# 設定確認
python test_setup.py

# 依存関係テスト
python -c "import google.oauth2.service_account; print('Google Auth OK')"
python -c "import elevenlabs; print('ElevenLabs OK')"
python -c "import pydub; print('Pydub OK')"
python -c "import crewai; print('CrewAI OK')"

# CrewAI統合テスト（推奨）
python3 test_crewai_flow.py
```

**期待される出力**:
```
============================================================
🧪 CrewAI WOW Script Creation Flow テスト開始
============================================================

📋 テストニュース:
  1. 日銀、金融政策の転換を示唆
  2. 新NISAが投資ブームを加速
  3. AI関連株が市場を牽引

🚀 CrewAI実行中...
✅ Created agent: deep_news_analyzer
✅ Created agent: curiosity_gap_researcher
✅ Created agent: emotional_story_architect
✅ Created agent: script_writer
✅ Created agent: engagement_optimizer
✅ Created agent: quality_guardian
✅ Created agent: japanese_purity_polisher
✅ WOW Script Creation Crew: All 7 agents created successfully
✅ Created 7 tasks for WOW Script Creation Crew
🚀 Starting WOW Script Creation Crew execution...
```

## CrewAI統合のトラブルシューティング

### エラー: "Vertex AI API has not been used"

**完全なエラーメッセージ**:
```
Vertex AI API has not been used in project probable-setup-435816-r8
before or it is disabled.
```

**解決策（3つの選択肢）**:

#### 解決策1: Vertex AI APIを有効化（推奨）

1. 以下のURLにアクセス:
   ```
   https://console.developers.google.com/apis/api/aiplatform.googleapis.com/overview?project=probable-setup-435816-r8
   ```

2. 「APIを有効にする」をクリック

3. 数分待ってから再実行:
   ```bash
   python3 test_crewai_flow.py
   ```

#### 解決策2: 直接Gemini APIを使用（簡単）

`app/config_prompts/prompts/agents.yaml` を編集:
```yaml
agents:
  deep_news_analyzer:
    model: gemini-pro  # または gemini-1.5-pro
    temperature: 0.7
    # ...他のエージェントも同様に変更
```

#### 解決策3: CrewAIを一時的に無効化

`.env` ファイルに追加:
```env
USE_CREWAI_SCRIPT_GENERATION=false
```

この場合、従来の3段階品質チェックシステムが使用されます。

### エラー: "Agent creation failed"

**原因**: プロンプトファイルが見つからない

**解決策**:
```bash
# プロンプトディレクトリの確認
ls -la app/config_prompts/prompts/

# 必要なファイル:
# - agents.yaml
# - analysis.yaml
# - script_generation.yaml
# - quality_check.yaml
```

ファイルが存在しない場合、Gitから最新版を取得してください。

### エラー: "ModuleNotFoundError: No module named 'crewai'"

**解決策**:
```bash
# CrewAIをインストール
pip install crewai crewai-tools

# または requirements.txt から
pip install -r requirements.txt
```

### CrewAI パフォーマンスの問題

**症状**: 台本生成に時間がかかりすぎる

**解決策**:

1. **並列処理を有効化**:
   `config.yaml` を編集:
   ```yaml
   crew:
     parallel_analysis: true
   ```

2. **より高速なモデルを使用**:
   ```yaml
   agents:
     deep_news_analyzer:
       model: gemini-1.5-flash  # より高速
   ```

3. **品質ループ回数を調整**:
   ```yaml
   crew:
     max_quality_iterations: 1  # デフォルト: 2
   ```

## トラブルシューティング

### よくある問題

1. **Google認証エラー**
   - サービスアカウントキーファイルのパスを確認
   - 権限設定（SheetsとDriveへのアクセス）を確認
   - **YouTube APIの場合**: OAuth 2.0 クライアントIDのJSONファイルが正しい形式（トップレベルが `web` または `installed`）であることを確認してください。サービスアカウントキーのJSONファイルはYouTube APIの認証には使用できません。

2. **API制限エラー**
   - 各APIの使用量制限を確認
   - 複数キーの設定を検討

3. **FFmpegエラー**
   - システムにFFmpegがインストールされているか確認
   - PATHが正しく設定されているか確認

## 自動実行の設定（ローカル環境）

### 概要

YouTube動画の自動生成・アップロードを毎日定時実行するシステムです。

### セットアップ方法

#### 方法1: Systemd Timer（推奨 - Linux）

**1. サービスとタイマーをインストール:**
```bash
sudo cp systemd/youtube-automation.service /etc/systemd/system/
sudo cp systemd/youtube-automation.timer /etc/systemd/system/
```

**2. Systemdをリロード:**
```bash
sudo systemctl daemon-reload
```

**3. タイマーを有効化して起動:**
```bash
sudo systemctl enable --now youtube-automation.timer
```

**4. 状態確認:**
```bash
# タイマーの状態確認
sudo systemctl status youtube-automation.timer

# 次回実行時刻の確認
sudo systemctl list-timers --all | grep youtube
```

**5. ログ確認:**
```bash
# Systemdログ
journalctl -u youtube-automation.service -f

# アプリケーションログ
tail -f logs/systemd.log
tail -f logs/daily_run_*.log
```

**6. 手動実行（テスト）:**
```bash
sudo systemctl start youtube-automation.service
```

#### 方法2: Cron（代替方法）

**1. Crontabを編集:**
```bash
crontab -e
```

**2. 毎日9時に実行する設定を追加:**
```cron
# 毎日9:00 AMに実行
0 9 * * * /home/kafka/projects/youtuber/run_daily.sh >> /home/kafka/projects/youtuber/logs/cron.log 2>&1
```

**3. Crontabを確認:**
```bash
crontab -l
```

**Cron時刻の書式:**
```
分 時 日 月 曜日 コマンド
0  9  *  *  *    実行するコマンド

例:
0 9 * * *     # 毎日9:00
0 */6 * * *   # 6時間ごと
0 9 * * 1     # 毎週月曜9:00
0 9 1 * *     # 毎月1日9:00
```

#### 方法3: 手動実行

**シェルスクリプトから:**
```bash
./run_daily.sh
```

**Pythonから直接:**
```bash
source .venv/bin/activate
python3 -m app.main daily
```

### 実行時刻の変更

#### Systemdの場合

`/etc/systemd/system/youtube-automation.timer` を編集:
```ini
[Timer]
# 毎日9:00に実行
OnCalendar=*-*-* 09:00:00

# 他の例:
# OnCalendar=*-*-* 06:00:00  # 毎日6:00
# OnCalendar=Mon *-*-* 09:00:00  # 毎週月曜9:00
# OnCalendar=*-*-01 09:00:00  # 毎月1日9:00
```

変更後は再読み込み:
```bash
sudo systemctl daemon-reload
sudo systemctl restart youtube-automation.timer
```

#### Cronの場合

`crontab -e` で時刻を編集してください。

### ログとモニタリング

**ログファイルの場所:**
- 日次実行ログ: `logs/daily_run_YYYYMMDD_HHMMSS.log`
- Systemdログ: `logs/systemd.log`
- Systemdエラーログ: `logs/systemd-error.log`
- アプリケーションログ: `logs/app.log`
- Cronログ: `logs/cron.log`（Cron使用時）

**最終実行結果の確認:**
```bash
# Systemdの場合
sudo systemctl status youtube-automation.service

# ログから確認
tail -n 100 logs/daily_run_*.log | grep -E "(Starting|completed|failed)"
```

**Discord通知:**

`.env`で`DISCORD_WEBHOOK_URL`を設定すると、実行結果が自動通知されます：
- ✅ 成功: 動画URL、実行時間、生成ファイル数
- ❌ 失敗: エラー内容、失敗したステップ

### トラブルシューティング

#### サービスが起動しない

```bash
# サービスログを確認
journalctl -u youtube-automation.service -n 50

# 手動でテスト実行
./run_daily.sh
```

**よくある原因:**
- 仮想環境のパスが間違っている
- `.env`ファイルが見つからない
- 実行権限がない: `chmod +x run_daily.sh`

#### タイマーがトリガーされない

```bash
# タイマーがアクティブか確認
sudo systemctl list-timers --all | grep youtube

# タイマーの状態確認
sudo systemctl status youtube-automation.timer
```

**確認事項:**
- タイマーが有効化されているか: `sudo systemctl enable youtube-automation.timer`
- 時刻設定が正しいか: `/etc/systemd/system/youtube-automation.timer`

#### 仮想環境のエラー

```bash
# 仮想環境を再作成
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 権限エラー

```bash
# ログディレクトリの権限確認
ls -ld logs/
chmod 755 logs/

# スクリプトの実行権限確認
chmod +x run_daily.sh
```

### 自動化の無効化

#### Systemdの場合

```bash
# タイマーを停止して無効化
sudo systemctl stop youtube-automation.timer
sudo systemctl disable youtube-automation.timer

# サービスファイルを削除（完全に削除する場合）
sudo rm /etc/systemd/system/youtube-automation.{service,timer}
sudo systemctl daemon-reload
```

#### Cronの場合

```bash
# Crontabを編集して該当行を削除またはコメントアウト
crontab -e
# 行頭に # を追加: # 0 9 * * * /home/kafka/projects/youtuber/run_daily.sh
```

### セキュリティ注意事項

**重要:**
- `.env`ファイルのパーミッションを制限: `chmod 600 .env`
- `.env`ファイルは絶対にGitにコミットしない
- APIキーが露出した場合は即座にローテーション
- ログファイルを定期的にレビュー
- `token.pickle`（YouTube認証）もGitにコミットしない

**推奨設定:**
```bash
# 機密ファイルの権限設定
chmod 600 .env
chmod 600 token.pickle
chmod 600 secret/*.json
chmod 700 secret/
```

### 次のステップ

環境構築が完了したら、[実装ガイド](./implementation.md)に進んでください。
