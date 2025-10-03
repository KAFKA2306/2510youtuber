# **YouTube動画自動生成システム 完全構築マニュアル**
## **目次**
1. システム概要とアーキテクチャ
2. 開発フェーズと実装状況
3. 事前準備
4. 外部サービス連携設定
5. 環境構築
6. システム検証
7. 自動実行設定
8. トラブルシューティング
9. 運用と監視
10. API仕様と料金体系
***
## **1. システム概要とアーキテクチャ**
本システムは、AIを活用してYouTube動画を完全自動生成するエンドツーエンドのパイプラインです。
### **主要コンポーネント**
**情報収集層:**
- Perplexity AI（プライマリ）
- NewsAPI.org（フォールバック）
- 3段階フォールバック機構
**AI台本生成層:**
- CrewAI WOW Script Creation Crew（7つの専門エージェント）
- Google Gemini API（複数キーローテーション）
- 3段階品質チェックシステム
**音声合成層:**
- ElevenLabs TTS（高品質）
- VOICEVOX Nemo（無料バックアップ）
- gTTS/pyttsx3（最終フォールバック）
**動画生成層:**
- FFmpeg（動画エンコード）
- Pexels/Pixabay（HD/4K B-roll映像）
- 動的トランジション・エフェクト
**データ管理層:**
- Google Sheets（実行履歴・プロンプト管理）
- Google Drive（動画バックアップ）
- ローカルキャッシュ（TTL 24時間）
**配信層:**
- YouTube Data API v3（OAuth 2.0認証）
- 自動サムネイル生成
- メタデータ最適化
**通知層:**
- Discord/Slack Webhook
- エラーアラート
- 実行レポート
***
## **2. 開発フェーズと実装状況**
### **Phase 1: CrewAI統合（完了）**
**WOW Script Creation Crewの7つのAIエージェント:**
1. **deep_news_analyzer**: ニュースの深層分析と文脈抽出
2. **curiosity_gap_researcher**: 視聴者の知的好奇心を刺激する構成研究
3. **emotional_story_architect**: 感情的な物語設計
4. **script_writer**: 対談形式の台本執筆
5. **engagement_optimizer**: エンゲージメント最適化
6. **quality_guardian**: 品質保証（WOWスコア評価）
7. **japanese_purity_polisher**: 日本語純度向上（英語混入除去）
**目標:** 視聴維持率50%+を達成する高品質台本の自動生成
### **Phase 2: API安定性強化（2025年10月3日完了）**
**実装機能:**
1. **API Key Rotation**
   - Gemini/Perplexity複数キー自動ローテーション
   - 429エラー検知 → 5分待機 → 別キーで継続
   - 成功率ベースの最適キー選択
   - 連続5回失敗キーは10分間休止
2. **NewsAPI.org フォールバック**
   - 3段階フォールバック: Perplexity → NewsAPI → ダミーニュース
   - 無料枠: 100リクエスト/日
   - 自動切替機構
4. **Google Sheetsローカルキャッシュ**
   - TTL 24時間
   - Sheets障害時の自動フォールバック
   - オフライン実行可能
### **Stock Footage統合（完了）**
**プロフェッショナルなB-roll映像機能:**
- Pexels API: HD/4K無制限・商用利用可
- Pixabay API: フォールバック用
- 自動キーワード抽出（日本語→英語変換）
- Ken Burns効果、クロスフェード、カラーグレーディング
- 3段階フォールバック: Stock → Static → Simple

---
## **3. 事前準備**
### **必要なアカウント一覧**
| サービス | 用途 | 料金 | 優先度 | 複数キー推奨 |
|---------|------|------|--------|-------------|
| Perplexity | ニュース収集 | 有料 | 必須 | ✅ 3キー |
| NewsAPI.org | フォールバック | 無料100req/日 | 推奨 | - |
| Google Cloud | Gemini/Sheets/Drive/YouTube | 従量課金 | 必須 | ✅ 3-5キー |
| ElevenLabs | 音声合成 | $5/月〜 | 必須 | - |
| Pexels | B-roll映像 | 無料無制限 | 推奨 | - |
| Pixabay | B-roll映像 | 無料 | オプション | - |
| Discord | 通知 | 無料 | 推奨 | - |
**注意:** SerpAPIは認証が複雑なため使用しません。ニュース収集はPerplexity/NewsAPIで行います。
### **技術要件**
- Python 3.8以上
- FFmpeg（動画エンコード）
- Docker（VOICEVOX Nemo用、オプション）
- WSL2（Windows環境の場合）
- Git基本操作
- 基本的なLinuxコマンド知識
***
## **4. 外部サービス連携設定**
### **4.1. Perplexity API（ニュース収集）**
**取得手順:**
1. [Perplexity AI](https://www.perplexity.ai/) でアカウント作成
2. Settings → API Keys → 新しいキーを生成
**複数キー設定:**
```bash
PERPLEXITY_API_KEY=pplx-key1
```
**動作:**
- Rate limit検知時に自動的に次のキーに切り替え
- 成功率ベースで最適なキーを選択
- 連続5回失敗したキーは10分間休止

### **4.2. NewsAPI.org（フォールバック）**
**取得手順:**
1. [NewsAPI.org](https://newsapi.org/register) で無料アカウント作成
2. APIキーをコピー
**制限:**
- 100リクエスト/日（開発用十分）
- クレジットカード不要
```bash
NEWSAPI_API_KEY=your_newsapi_key
```
**フォールバック動作:**
- Perplexity全失敗時に自動的にNewsAPIへ切替
- 日本語ニュースを自動収集

### **4.3. Google Cloud Platform**
#### **A. Gemini API設定（台本生成用）**
**オプション1: Google AI Studio（推奨・簡単）**
1. [Google AI Studio](https://makersuite.google.com/) にアクセス
2. 新しいAPIキーを作成
3. **推奨:** 3-5個のキーを発行（台本生成安定化）
```bash
GEMINI_API_KEY=AIza-key1
GEMINI_API_KEY_2=AIza-key2
GEMINI_API_KEY_3=AIza-key3
GEMINI_API_KEY_4=AIza-key4
GEMINI_API_KEY_5=AIza-key5
```
**複数キー動作:**
- Rate limit/504タイムアウト検知時に自動キー切替
#### **B. Google Services設定（Sheets/Drive/YouTube）**
**Google Sheets/Drive用サービスアカウント:**
1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクト作成
2. 以下のAPIを有効化:
   - Google Sheets API
   - Google Drive API
   - YouTube Data API v3
3. 「認証情報」→「サービスアカウント」作成
4. JSON認証ファイルをダウンロード → `secret/service-account-key.json`に配置
5. `.env`に設定:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=secret/service-account-key.json
   ```

#### **C. YouTube Data API設定（重要）**
**⚠️ 注意:** YouTube動画アップロードにはOAuth 2.0クライアントIDが必要です（サービスアカウントでは不可）
**手順:**
1. **Google Cloud Consoleにアクセス**
   ```
   https://console.cloud.google.com/apis/credentials?project=your-project-id
   ```
2. **OAuth 2.0 クライアントIDを作成**
   - 「+ 認証情報を作成」→「OAuth クライアント ID」
   - アプリケーションの種類: **「デスクトップ アプリ」**を選択
   - 名前: `YouTuber Automation`
   - 「作成」をクリック
3. **JSONファイルをダウンロード**
   - ダウンロードボタン（↓）をクリック
   - ファイルを `secret/youtube_oauth_client.json` として保存
4. **.envファイルを更新**
   ```bash
   YOUTUBE_CLIENT_SECRET=secret/youtube_oauth_client.json
   ```
**初回認証（一度だけ必要）:**
```bash
# セットアップスクリプトを実行
uv run python setup_youtube_oauth.py
# またはテストアップロードで認証
uv run python test_upload.py
```
**認証フロー:**
1. ブラウザが自動的に開く
2. YouTubeチャンネルのGoogleアカウントでサインイン
3. アプリケーションに権限を付与（動画のアップロードと管理）
4. 認証完了後、`token.pickle`ファイルが作成される
5. 以降は自動的に認証される（トークンは自動更新）
**重要な注意事項:**
- ⚠️ `token.pickle`は秘密情報です。Gitにコミットしないでください
- ⚠️ サービスアカウントのJSONファイルはYouTube APIに使用できません
- ✅ OAuth clientの形式: `{"installed": {...}}` または `{"web": {...}}`
- ❌ サービスアカウントの形式: `{"type": "service_account", ...}`（これは使えません）

### **4.4. ElevenLabs TTS（音声合成）**
**取得手順:**
1. [ElevenLabs](https://elevenlabs.io/) でアカウント作成
2. Settings → API Keys からキーを取得
```bash
ELEVENLABS_API_KEY=sk_your_key
```
**推奨プラン:** Starter（$5/月、30,000文字）
**音声ID（Voice ID）の取得:**
1. ElevenLabsの「Voices」タブから音声を選択
2. Voice IDをコピー
3. `.env`に設定:
```bash
TTS_VOICE_TANAKA=voice_id_here
TTS_VOICE_SUZUKI=voice_id_here
TTS_VOICE_NARRATOR=voice_id_here
```

### **4.5. Stock Footage APIs（完全無料）**
#### **Pexels API（推奨）**
1. [Pexels API](https://www.pexels.com/api/) で無料登録
2. APIキーをコピー
```bash
PEXELS_API_KEY=YOUR_PEXELS_KEY
```
**特徴:**
- ✅ 完全無料・無制限
- ✅ HD/4K品質のストック映像
- ✅ 商用利用可能
- ✅ 著作権表示不要

#### **Pixabay API（フォールバック）**
1. [Pixabay API](https://pixabay.com/api/docs/) で登録
2. APIキーをコピー
```bash
PIXABAY_API_KEY=YOUR_PIXABAY_KEY
```
**動作の仕組み:**
1. スクリプトから自動的にキーワードを抽出（例：「経済」→ "economy, finance, business"）
2. Pexels/Pixabay APIから関連する映像を検索
3. 複数クリップを自動ダウンロード
4. FFmpegでプロフェッショナルなB-rollシーケンスを生成
   - スムーズなクロスフェードトランジション
   - Ken Burns効果（ズーム/パン）
   - カラーグレーディング
5. 音声+字幕を合成して最終動画を出力

### **4.6. VOICEVOX Nemo（無料TTSバックアップ）**
**推奨:** ElevenLabs制限時の無料バックアップとして設定
VOICEVOX Nemoは完全無料のオープンソース日本語音声合成エンジンです。Dockerで実行します。
**クイックスタート:**
```bash
# VOICEVOX Nemo専用管理スクリプトを使用
# 起動
./scripts/voicevox_manager.sh start
# 停止
./scripts/voicevox_manager.sh stop
# ステータス確認
./scripts/voicevox_manager.sh status
# 再起動
./scripts/voicevox_manager.sh restart
# ログ表示
./scripts/voicevox_manager.sh logs
# 音声合成テスト
./scripts/voicevox_manager.sh test

**安定化ポイント:**
- デフォルトで `voicevox/voicevox_engine:cpu-ubuntu20.04-0.24.1` を使用し、Dockerリスタートポリシー `unless-stopped` を付与
- 起動時にヘルスチェック(`/health`)とポート競合検査を行い、失敗時は安全に停止/削除
- `VOICEVOX_IMAGE`, `VOICEVOX_CONTAINER_NAME`, `VOICEVOX_PORT`, `VOICEVOX_SPEAKER`, `VOICEVOX_CPU_LIMIT`, `VOICEVOX_MEMORY_LIMIT` などの環境変数で挙動を上書き可能
- 画像取得は最大3回リトライし、詳細ログは `logs/voicevox_nemo.log` に出力
```
**設定（`config.yaml`）:**
```yaml
tts:
  voicevox:
    enabled: true
    port: 50121
    speaker: 1  # 話者ID（1: 四国めたん）
```
**特徴:**
- ✅ 完全無料・オープンソース
- ✅ 日本語音声合成に最適
- ✅ ElevenLabs失敗時に自動フォールバック
- ✅ 専用管理スクリプトで安定稼働
- ✅ ログ管理・ヘルスチェック機能付き

#### **Docker Engine インストール（WSL2環境）**
**前提条件:**
- WSL2 Ubuntu 22.04以上
**リポジトリのセットアップ:**
```bash
# GPGキーの追加
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# aptリポジトリの追加
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```
**Dockerパッケージのインストール:**
```bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
**動作確認:**
```bash
sudo docker run hello-world
```
**権限設定（重要）:**
```bash
# dockerグループにユーザーを追加
sudo usermod -aG docker $USER
# グループ変更を即座に反映
newgrp docker
# docker.sockのパーミッション設定
sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock
# 動作確認（sudoなしで実行できることを確認）
docker ps
```
### **4.7. Discord Webhook（通知）**
**取得手順:**
1. Discordサーバーで「サーバー設定」→「連携サービス」→「ウェブフック」を開く
2. 「新しいウェブフック」をクリック
3. ウェブフック名とチャンネルを設定
4. 「ウェブフックURLをコピー」をクリック
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook
```

***
## **5. 環境構築**
### **5.1. Google Sheetsセットアップ**
#### **スプレッドシート作成**
1. [Google Sheets](https://sheets.google.com/) で新しいシートを作成
2. シート名を設定（例：「YouTuber Automation」）
3. スプレッドシートIDをURLから取得
   - URL: `https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit`
4. `.env`に設定:
   ```bash
   GOOGLE_SHEET_ID=[SHEET_ID]
   ```

#### **runsシート設計**
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

#### **promptsシート設計**
シート名：`prompts`
| カラム名 | 説明 | 初期値例 |
|---------|------|---------|
| prompt_a | ニュース収集 | 「今日の重要な経済ニュースを3-5件収集し、各項目について...」 |
| prompt_b | 台本生成 | 「以下のニュース要約をもとに、二人の専門家による対談形式で...」 |
| prompt_c | メタ生成 | 「動画のタイトル、説明文、タグを生成してください...」 |
| prompt_d | コメント生成 | 「この動画を聞いている女の子の立場で、最初のコメントを...」 |

#### **権限設定**
1. サービスアカウントにシートへの編集権限を付与
2. シートの共有設定で、サービスアカウントのメールアドレスを追加
3. 権限：「編集者」に設定

### **5.2. Google Drive設定**
**フォルダ作成と権限:**
1. Google Driveで専用フォルダを作成（例：「YouTuber Content」）
2. フォルダIDをURLから取得
   - URL: `https://drive.google.com/drive/folders/[FOLDER_ID]`
3. `.env`に設定:
   ```bash
   GOOGLE_DRIVE_FOLDER_ID=[FOLDER_ID]
   ```
4. サービスアカウントにフォルダの編集権限を付与

### **5.3. 環境変数設定（.envファイル）**
プロジェクトのルートディレクトリに`.env`ファイルを作成します。
**完全な.envファイルテンプレート:**
```bash
# ===== AI APIs =====
# 注意: SerpAPIは認証が複雑なため使用しません
# Perplexity（ニュース収集 - 推奨）
PERPLEXITY_API_KEY=pplx-key1
# Gemini API（台本生成・CrewAI）- 複数キー設定推奨
GEMINI_API_KEY=AIza-key1
GEMINI_API_KEY_2=AIza-key2
GEMINI_API_KEY_3=AIza-key3
GEMINI_API_KEY_4=AIza-key4
GEMINI_API_KEY_5=AIza-key5
# NewsAPI.org（Perplexityフォールバック - 無料100リクエスト/日）
NEWSAPI_API_KEY=your_newsapi_key
# ElevenLabs（音声合成）
ELEVENLABS_API_KEY=sk_your_key
# ElevenLabsで使用するボイスID
TTS_VOICE_TANAKA=voice_id_here
TTS_VOICE_SUZUKI=voice_id_here
TTS_VOICE_NARRATOR=voice_id_here
# ===== Stock Footage APIs（無料・無制限） =====
# Pexels API（プロフェッショナルなB-roll映像）
PEXELS_API_KEY=YOUR_PEXELS_API_KEY
# Pixabay API（フォールバック用）
PIXABAY_API_KEY=YOUR_PIXABAY_API_KEY
# ===== Google Cloud Services =====
# サービスアカウント認証（Sheets, Drive, Vertex AI）
GOOGLE_APPLICATION_CREDENTIALS=secret/service-account-key.json
# Google Sheets（実行履歴・プロンプト管理）
GOOGLE_SHEET_ID=1ABC_your_sheet_id
# Google Drive（動画バックアップ）
GOOGLE_DRIVE_FOLDER_ID=1DEF_your_folder_id
# YouTube（動画アップロード - OAuth必須）
YOUTUBE_CLIENT_SECRET=secret/youtube_oauth_client.json
# ===== CrewAI設定 =====
# CrewAI WOW Script Creation Crew の有効化
USE_CREWAI_SCRIPT_GENERATION=true
# 従来の3段階品質チェック（CrewAI無効時のみ）
USE_THREE_STAGE_QUALITY_CHECK=true
# ===== Video Generation Settings =====
# ストック映像B-rollを使用するか（無料、プロフェッショナル品質）
ENABLE_STOCK_FOOTAGE=true
# 動画あたりのストック映像クリップ数（1-10推奨）
STOCK_CLIPS_PER_VIDEO=5
# ===== 通知 =====
# Discord Webhook（実行結果通知）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook
# Slack（オプション）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your_webhook
# ===== 開発設定 =====
DEBUG=true
LOG_LEVEL=INFO
# ローカルストレージ
LOCAL_OUTPUT_DIR=output
SAVE_LOCAL_BACKUP=true
```

**セキュリティ設定（重要）:**
```bash
# ファイル権限を制限
chmod 600 .env
chmod 600 token.pickle  # YouTube認証トークン
chmod 600 secret/*.json  # Google Cloudキー
chmod 700 secret/
```

### **5.4. Python環境セットアップ**
#### **仮想環境の作成**
uv sync

#### **FFmpegのインストール**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg
# macOS
brew install ffmpeg
# Windows
# https://ffmpeg.org/download.html からダウンロード
```

***
## **6. システム検証**
### **6.1. 統合検証スクリプト（推奨）**
全ての環境設定を自動で検証します:
```bash
# システム全体の検証（VOICEVOX Nemo自動起動含む）
python -m app.verify
```
**検証内容:**
- ✅ .envファイルの存在確認
- ✅ 必須APIキーの設定確認（Gemini, Pixabay）
- ✅ オプションAPIキーの確認（Perplexity, NewsAPI, ElevenLabs等）
- ✅ VOICEVOX Nemoサーバーの起動と動作確認
- ✅ 必要なディレクトリの作成
- ✅ 仮想環境の確認
- ✅ 音声合成のテスト

### **6.2. 個別環境確認**
```bash
# 設定確認
python test_setup.py
# 依存関係テスト
python -c "import google.oauth2.service_account; print('Google Auth OK')"
python -c "import elevenlabs; print('ElevenLabs OK')"
python -c "import pydub; print('Pydub OK')"
python -c "import crewai; print('CrewAI OK')"
```

### **6.3. CrewAI統合テスト**
```bash
# サンプルニュースでCrewAI実行
uv run python3 test_crewai_flow.py
```
**期待される出力:**
```
🧪 CrewAI WOW Script Creation Flow テスト開始
✅ Created agent: deep_news_analyzer
✅ Created 7 tasks for WOW Script Creation Crew
🚀 Starting WOW Script Creation Crew execution...
```

### **6.4. Stock Footage テスト**
```bash
# Stock Footage統合テスト
python test_stock_footage.py
```
**期待される出力:**
```
🧪 Stock Footage Integration Test Suite
✓ Pexels API Key: ✓ Configured
✓ Found 3 clips
✓ Downloaded: pexels_12345.mp4 (15.3 MB)
✅ 3/3 tests passed
```

***
## **7. 自動実行設定**
### **7.1. Systemd Timer（推奨 - Linux）**
**サービスとタイマーをインストール:**
```bash
sudo cp systemd/youtube-automation.service /etc/systemd/system/
sudo cp systemd/youtube-automation.timer /etc/systemd/system/
```
**Systemdをリロード:**
```bash
sudo systemctl daemon-reload
```
**タイマーを有効化して起動:**
```bash
sudo systemctl enable --now youtube-automation.timer
```
**状態確認:**
```bash
# タイマーの状態確認
sudo systemctl status youtube-automation.timer
# 次回実行時刻の確認
sudo systemctl list-timers --all | grep youtube
```
**ログ確認:**
```bash
# Systemdログ
journalctl -u youtube-automation.service -f
# アプリケーションログ
tail -f logs/systemd.log
tail -f logs/daily_run_*.log
```
**手動実行（テスト）:**
```bash
sudo systemctl start youtube-automation.service
```

#### **実行時刻の変更**
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

### **7.2. Cron（代替方法）**
**Crontabを編集:**
```bash
crontab -e
```
**毎日9時に実行する設定を追加:**
```cron
# 毎日9:00 AMに実行
0 9 * * * /home/kafka/projects/youtuber/run_daily.sh >> /home/kafka/projects/youtuber/logs/cron.log 2>&1
```
**Crontabを確認:**
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

### **7.3. 手動実行**
**シェルスクリプトから:**
```bash
./run_daily.sh
```
**Pythonから直接:**
```bash
source .venv/bin/activate
python3 -m app.main daily
```

### **7.4. ログとモニタリング**
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
`.env`で`DISCORD_WEBHOOK_URL`を設定すると、実行結果が自動通知されます:
- ✅ 成功: 動画URL、実行時間、生成ファイル数
- ❌ 失敗: エラー内容、失敗したステップ

***
### **8.2. CrewAI統合のトラブルシューティング**
#### **エラー: "Vertex AI API has not been used"**
**完全なエラーメッセージ:**
```
Vertex AI API has not been used in project probable-setup-435816-r8
before or it is disabled.
```
**解決策:**

`app/config_prompts/prompts/agents.yaml` を編集:
```yaml
agents:
  deep_news_analyzer:
    model: gemini-pro  # または gemini-1.5-pro
    temperature: 0.7
```

#### **エラー: "ModuleNotFoundError: No module named 'crewai'"**
**解決策:**
```bash
# CrewAIをインストール
pip install crewai crewai-tools
# または requirements.txt から
pip install -r requirements.txt
```

### **8.3. よくある問題**
#### **問題: Google認証エラー**
**確認事項:**
- サービスアカウントキーファイルのパスを確認
- 権限設定（SheetsとDriveへのアクセス）を確認
- **YouTube APIの場合**: OAuth 2.0 クライアントIDのJSONファイルが正しい形式（トップレベルが `web` または `installed`）であることを確認してください。サービスアカウントキーのJSONファイルはYouTube APIの認証には使用できません。

#### **問題: API制限エラー（429 Error）**
**対処法:**
- 各APIの使用量制限を確認
- 複数キーの設定を検討（Perplexity, Gemini）
- 実行頻度を見直す（CronやSystemd Timerの設定を変更する）

#### **問題: FFmpegエラー**
**確認事項:**
- システムにFFmpegがインストールされているか確認: `ffmpeg -version`
- PATHが正しく設定されているか確認
- `logs/app.log` でffmpegの具体的なエラーメッセージを確認

#### **問題: サービスが起動しない（Systemd）**
**対処法:**
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

#### **問題: 権限エラー**
**対処法:**
```bash
# ログディレクトリの権限確認
ls -ld logs/
chmod 755 logs/
# スクリプトの実行権限確認
chmod +x run_daily.sh
# 機密ファイルの権限設定
chmod 600 .env
chmod 600 token.pickle
chmod 600 secret/*.json
chmod 700 secret/
```

***
## **9. 運用と監視**
### **9.1. モニタリング項目**
**APIキー成功率:**
- 各プロバイダー（Gemini, Perplexity）の成功率を追跡
- `logs/api_rotation.log` で確認
**キャッシュヒット率:**
- Google Sheetsキャッシュの効果測定
- TTL 24時間の有効性確認
**Stock Footage品質:**
- B-roll取得成功率
- Pexels/Pixabay からのクリップダウンロード成功率
- HD/4K品質の維持状況
**コスト追跡:**
- 月次API使用料金監視
- ElevenLabs: 文字数カウント
- Gemini API: トークン使用量
- YouTube Data API: クォータ消費状況

### **9.2. ログ確認コマンド**
```bash
# API統計確認
tail -f logs/daily_run_*.log | grep -E "(API|キー|成功率)"
# Stock Footage動作確認
tail -f logs/app.log | grep -E "(stock|footage|clips)"
# エラーのみ抽出
grep -i error logs/app.log | tail -n 50
# 実行時間の分析
grep "duration_sec" logs/daily_run_*.log | awk '{print $NF}' | sort -n
```

### **9.3. 自動化の無効化**
#### **Systemdの場合**
```bash
# タイマーを停止して無効化
sudo systemctl stop youtube-automation.timer
sudo systemctl disable youtube-automation.timer
# サービスファイルを削除（完全に削除する場合）
sudo rm /etc/systemd/system/youtube-automation.{service,timer}
sudo systemctl daemon-reload
```
#### **Cronの場合**
```bash
# Crontabを編集して該当行を削除またはコメントアウト
crontab -e
# 行頭に # を追加: # 0 9 * * * /home/kafka/projects/youtuber/run_daily.sh
```

***
## **10. API仕様と料金体系**
### **10.1. ElevenLabs TTS API**
| プラン | 月額料金 | 文字数制限 | オーバーエージ料金 | 推奨用途 |
|--------|----------|------------|-------------------|----------|
| **Free** | $0 | 10,000文字 | 利用不可 | 開発・テスト |
| **Starter** | $5 | 30,000文字 | $0.30/1,000文字 | 小規模運用 |
| **Creator** | $22 | 100,000文字 | $0.24/1,000文字 | 中規模運用 |
| **Pro** | $99 | 500,000文字 | $0.18/1,000文字 | 大規模運用 |
**推奨対応:** 
- 開発時: Freeプランで動作確認
- 本番運用: Starter プラン（$5/月）が最もコスパが良い
- 大規模運用: Creator以上を検討
**検出されたエラー例:** `quota_exceeded - You have 0 credits remaining`

### **10.2. Google Gemini API**
| ティア | 条件 | RPM制限 | 日次制限 | 料金体系 |
|--------|------|---------|----------|----------|
| **Free** | なし | 15 RPM | 50-1,500 RPD | 無料 |
| **Tier 1** | 課金設定 | 150 RPM | 1,000 RPD | $0.000625/1Kトークン |
| **Tier 2** | $250以上 | 1,000 RPM | 50,000 RPD | 従量課金 |
| **Tier 3** | $1,000以上 | 2,000 RPM | 無制限 | 従量課金 |
**注意:**
- RPM = Requests Per Minute（1分あたりのリクエスト数）
- RPD = Requests Per Day（1日あたりのリクエスト数）
- CrewAIの7エージェントは複数回のAPI呼び出しを行うため、複数キー推奨
**検出されたエラー例:** `429 Too Many Requests - limit: 50`
**実装済み対策:** 複数キー自動ローテーション（3-5キー推奨）

### **10.3. Google Sheets API**
- **料金:** **完全無料**（超過時も課金なし）
- **制限:** 
  - 読み取り: 300リクエスト/分
  - 書き込み: 100リクエスト/分/プロジェクト
- **実装済み対策:** ローカルキャッシュ（TTL 24時間）

### **10.4. YouTube Data API v3**
- **料金:** 無料（クォータ制限あり）
- **クォータ:** 10,000ユニット/日
- **動画アップロード:** 1,600ユニット/回
- **推定:** 1日約6本の動画アップロード可能
- **注意:** OAuth 2.0認証必須（サービスアカウント不可）

### **10.5. Perplexity API**
- **料金:** 有料プランのみ
- **制限:** プランによって異なる
- **推奨:** 複数アカウントで3キー用意
- **フォールバック:** NewsAPI.org（無料100リクエスト/日）

### **10.6. NewsAPI.org**
- **料金:** 無料
- **制限:** 100リクエスト/日
- **用途:** Perplexity失敗時のフォールバック
- **制約:** 開発用途のみ（本番は有料プラン）

### **10.7. Stock Footage APIs**
#### **Pexels API**
- **料金:** 完全無料・無制限
- **品質:** HD/4K
- **制約:** なし（商用利用可、著作権表示不要）
#### **Pixabay API**
- **料金:** 完全無料
- **制限:** あり（具体的な数値は要確認）
- **用途:** Pexelsのフォールバック

### **10.8. VOICEVOX Nemo**
- **料金:** **完全無料**のオープンソース
- **制限:** なし（ローカル実行）
- **要件:** Docker環境
- **リソース:** CPU版 500MB-1GB、メモリ50-100MB
- **用途:** ElevenLabs制限時のバックアップTTS

### **10.9. 月額コスト試算**
**最小構成（開発・小規模運用）:**
- ElevenLabs Starter: $5/月
- Google Gemini: 無料（Free Tier内）
- 他のサービス: 無料
- **合計:** $5/月
**推奨構成（安定運用）:**
- ElevenLabs Starter: $5/月
- Google Gemini Tier 1: ~$5-10/月（使用量による）
- Perplexity: ~$20/月（プランによる）
- 他のサービス: 無料
- **合計:** $30-35/月
**大規模構成（高可用性・高頻度）:**
- ElevenLabs Creator: $22/月
- Google Gemini Tier 2: ~$50/月
- Perplexity Pro: ~$40/月
- 他のサービス: 無料
- **合計:** $112/月
***
## **12. プロジェクトファイル構造**
```
youtuber-automation/
├── .env                          # 環境変数（Gitに含めない）
├── .gitignore
├── requirements.txt
├── README.md
├── IMPLEMENTATION_SUMMARY.md     # Phase 2実装サマリー
├── VOICEVOX_SETUP.md            # VOICEVOX詳細ガイド
│
├── app/
│   ├── __init__.py
│   ├── main.py                  # メインエントリーポイント
│   ├── verify.py                # システム検証スクリプト
│   ├── video.py                 # 動画生成（ffmpeg）
│   ├── api_rotation.py          # APIキーローテーション
│   ├── japanese_quality.py      # 日本語純度チェック
│   │
│   ├── config/
│   │   └── prompts/
│   │       ├── agents.yaml      # CrewAI エージェント定義
│   │       ├── analysis.yaml    # 分析タスク定義
│   │       ├── script_generation.yaml  # 台本生成タスク
│   │       └── quality_check.yaml      # 品質チェックタスク
│   │
│   └── crew/
│       └── flows.py             # CrewAI実行フロー
│
├── secret/
│   ├── service-account-key.json       # Google Cloud認証
│   └── youtube_oauth_client.json      # YouTube OAuth
│
├── scripts/
│   └── voicevox_manager.sh      # VOICEVOX管理スクリプト
│
├── systemd/
│   ├── youtube-automation.service
│   └── youtube-automation.timer
│
├── logs/                         # ログディレクトリ
│   ├── daily_run_*.log
│   ├── app.log
│   ├── systemd.log
│   └── cron.log
│
├── output/                       # 生成ファイル
│   ├── videos/
│   ├── audio/
│   └── thumbnails/
│
├── test_setup.py                # 環境確認スクリプト
├── test_crewai_flow.py          # CrewAIテスト
├── test_stock_footage.py        # Stock Footageテスト
├── setup_youtube_oauth.py       # YouTube認証セットアップ
├── test_upload.py               # YouTubeアップロードテスト
├── run_daily.sh                 # 日次実行スクリプト
└── token.pickle                 # YouTube認証トークン（Gitに含めない）
```

***
## **13. よくある質問（FAQ）**
### **Q1: SerpAPIは使わないのですか？**
A: 認証が複雑で安定性に欠けるため、本システムではPerplexity AI + NewsAPI.orgを使用します。これにより高可用性（99.99%）を実現しています。
### **Q2: サービスアカウントでYouTubeにアップロードできますか？**
A: できません。YouTube Data API v3は個人アカウントの委任が必要なため、OAuth 2.0クライアントIDを使用する必要があります。サービスアカウントはSheets/Driveのみで使用します。
### **Q3: 無料で運用できますか？**
A: 一部可能ですが、以下の制約があります：
- ElevenLabs Free: 10,000文字/月（約2-3本の動画）
- Gemini Free Tier: 15 RPM（CrewAIでは不十分）
- **推奨:** 最低$5/月（ElevenLabs Starter）での運用

### **Q4: 1日何本の動画を生成できますか？**
A: 以下の要因によります：
- YouTube Data APIクォータ: 1日約6本まで
- ElevenLabs制限: Starterプランで1日約10本（1本=3,000文字として）
- Gemini API制限: Tier 1で1日約50本（複数キー使用時）
**実用的な推奨:** 1日1-3本の安定運用

### **Q6: VOICEVOX Nemoは必須ですか？**
A: オプションです。ElevenLabsのバックアップとして推奨しますが、以下のフォールバックチェーンが自動的に機能します：
1. ElevenLabs TTS（プライマリ）
2. VOICEVOX Nemo（無料バックアップ）
3. gTTS（Google TTS Free）
4. pyttsx3（オフライン・最終フォールバック）

### **Q7: WindowsでもDocker無しで動きますか？**
A: はい。VOICEVOX Nemoを使用しない場合、Windows上で直接実行可能です。gTTS/pyttsx3が自動的に使用されます。

### **Q8: エラー時の通知は自動ですか？**
A: はい。Discord WebhookまたはSlack Webhookを設定すると、以下の通知が自動送信されます：
- ✅ 成功: 動画URL、実行時間、生成ファイル数
- ❌ 失敗: エラー内容、失敗したステップ

### **Q10: 本番環境へのデプロイ方法は？**
A: 以下のオプションがあります：
1. **ローカル環境 + Systemd Timer**: 最もシンプル
2. **Render Cron Jobs**: クラウド環境
3. **Heroku Scheduler**: PaaS環境
4. **AWS Lambda + EventBridge**: サーバーレス
本ガイドではSystemd Timer（ローカル）を推奨しています。

***
## **14. まとめ**
本システムにより、**月額$0程度で安定した大規模YouTubeコンテンツ生成**が実現できます。
