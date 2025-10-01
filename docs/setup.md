# 環境構築とセットアップガイド

## 事前準備チェックリスト

### 必要なアカウント

- [ ] **Perplexity**: ニュース収集用
- [ ] **Google Cloud**: Gemini TTS・Sheets・Drive・YouTube Data API用
- [ ] **ElevenLabs**: STT（音声認識）用
- [ ] **Discord**: 運用通知用（Webhook URL）
- [ ] **Render**: 実行基盤（Cronジョブ）用
- [ ] **GitHub**: コード管理・自動デプロイ用

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

#### Gemini API

1. [Google AI Studio](https://makersuite.google.com/)にアクセス
2. 新しいAPIキーを作成
3. **メモ**: `GEMINI_API_KEY=AIza...`

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
# Perplexity
PERPLEXITY_API_KEY=pplx-...

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GEMINI_API_KEY=AIza...
GOOGLE_SHEET_ID=1ABC...
GOOGLE_DRIVE_FOLDER_ID=1DEF...

# YouTube
YOUTUBE_CLIENT_SECRET=/path/to/client_secret.json
# または JSON 文字列を直接設定 (推奨: ファイルパス)
# YOUTUBE_CLIENT_SECRET='{"web": {"client_id": "...", "client_secret": "...", ...}}'

# ElevenLabs
ELEVENLABS_API_KEY=...

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# オプション：複数APIキー（並列処理用）
GEMINI_API_KEY_2=AIza...
GEMINI_API_KEY_3=AIza...
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

# 簡単な動作テスト
python -c "import google.oauth2.service_account; print('Google Auth OK')"
python -c "import elevenlabs; print('ElevenLabs OK')"
python -c "import pydub; print('Pydub OK')"
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

### 次のステップ

環境構築が完了したら、[実装ガイド](./implementation.md)に進んでください。
