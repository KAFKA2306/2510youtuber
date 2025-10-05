# 日本語運用ハンドブック

金融系YouTube自動生成システムを日常運用するための実務的な手引きです。環境構築から日次運用、品質監視、障害対応までを1本のドキュメントに統合しました。詳細な設計情報は末尾の参考資料セクションを参照してください。

## 1. システム概要

- **ワークフロー全体像**: `uv run python3 -m app.main <mode>` をエントリーポイントとして、ニュース収集→台本生成→音声合成→動画編集→YouTube投稿までを自動実行します。
- **コンポーネント構成**:
  - 情報収集: Perplexity AI を中心に NewsAPI をフォールバックとして使用。
  - 台本生成: CrewAI 上の 7 エージェントが台本を共同生成し、品質チェックと日本語純度ガードを通過したものだけが採用されます。
  - 音声合成: ElevenLabs → VOICEVOX → gTTS の順に最大 6 段階までフォールバック。
  - 映像生成: FFmpeg とストック動画（Pexels/Pixabay）を組み合わせた B-roll シーケンスとテンプレート映像を合成します。
  - 品質保証: 自動 QA パイプライン、Google Sheets ダッシュボード、Gemini Vision による動画レビューでモニタリング。
- **モード切替**: `daily`（通常運用）、`special`（特集モード）、`test`（QA 緩和）の3種類を `YouTubeWorkflow.execute_full_workflow()` に渡す `mode` で制御します。

## 2. セットアップ手順

### 2.1 必要ソフトウェア・コマンド

| 項目 | 推奨バージョン | 補足 |
| --- | --- | --- |
| Python | 3.11 以上 | `uv` で依存を管理します。
| uv | 最新安定版 | `pip install uv` で導入します。
| FFmpeg | 4.4 以上 | PATH に登録し、`ffmpeg -version` が通ることを確認してください。
| VOICEVOX | Nemo 版推奨 | オフライン TTS フォールバック用。Docker/バイナリどちらでも構いません。

### 2.2 必須アカウント・API キー

| サービス | 用途 | 複数キー推奨 |
| --- | --- | --- |
| Google Gemini | 台本生成（CrewAI） | ✅ 3-5 本でローテーション安定化 |
| Perplexity AI | ニュース収集 | ✅ 3 本以上でレート制限を回避 |
| NewsAPI.org | ニュースフォールバック | 任意（無料枠 100 req/日） |
| ElevenLabs | TTS（高品質） | 任意 |
| VOICEVOX | TTS フォールバック | 任意 |
| Google Sheets / Drive / YouTube | ログ集計・公開 | サービスアカウント JSON を `secret/service-account.json` に配置 |

`.env` に API キーを記載し、`config.yaml` でストック映像や品質ゲートなどの設定を管理します。

### 2.3 初期セットアップ手順

```bash
# リポジトリを取得
git clone https://github.com/your-org/youtuber.git
cd youtuber

# 依存関係を同期
uv sync

# 環境変数テンプレートをコピー
cp secret/.env.example secret/.env
# secret/.env を編集して API キーを登録

# 動作検証（必須）
uv run python -m app.verify

# 初回のドライラン（test モード推奨）
uv run python3 -m app.main test
```

#### 手順の流れ

1. `git clone` 後に `uv sync` を実行すると、Python 依存関係と VOICEVOX 用ユーティリティが一括でインストールされます。
2. `secret/.env.example` を複製したら、[2.4 外部サービス設定ガイド](#24-外部サービス設定ガイド)を参考に API キーやサービスアカウントを登録してください。
3. 追加で FFmpeg や VOICEVOX のバイナリを導入した場合は、`config.yaml` のパス設定が正しいか確認します。
4. `uv run python -m app.verify` を実行して API キー、FFmpeg、フォント類の存在をチェックします。エラーになった項目はログに補足が出るので、修正後に再度実行してください。
5. 本番運用に入る前に `uv run python3 -m app.main test` を一度実行し、ストック映像や QA が期待どおり動作するか確認します。`test` モードでは YouTube への投稿は行われません。

`app.verify` は FFmpeg や API キーの欠落を起動前に検出します。VOICEVOX を利用する場合は、別途付属スクリプト `./scripts/voicevox_manager.sh start` でエンジンを起動してください。

### 2.4 外部サービス設定ガイド

各サービスの取得手順と `.env` への記述例をまとめました。旧セットアップドキュメントの詳細ステップを引き継いでいます。

#### Perplexity AI（ニュース収集）
1. [Perplexity AI](https://www.perplexity.ai/) にログインし、`Settings > API Keys` から新しいキーを発行します。
2. `.env` に `PERPLEXITY_API_KEYS="key1,key2,key3"` のようにカンマ区切りで複数登録すると自動ローテーションが有効になります。

#### NewsAPI.org（ニュースフォールバック）
1. [NewsAPI.org/register](https://newsapi.org/register) で無料アカウントを作成します。
2. 発行されたキーを `.env` の `NEWSAPI_API_KEY` に設定します（無料枠は 1 日 100 リクエストまで）。

#### Google Cloud（Gemini / Sheets / Drive / YouTube）
1. Google Cloud Console で新規プロジェクトを作成し、Gemini API、Sheets API、Drive API、YouTube Data API v3 を有効化します。
2. サービスアカウントを作成して JSON をダウンロードし、`secret/service-account.json` として配置します。Gemini の API キーは `GEMINI_API_KEYS="key1,key2"` の形式で `.env` に登録してください。

#### ElevenLabs（高品質 TTS）
1. [ElevenLabs](https://elevenlabs.io/) のダッシュボードで API キーを発行します。
2. `.env` に `ELEVENLABS_API_KEY` を追加し、必要に応じて `config.yaml` の話者設定を更新します。

#### VOICEVOX Nemo（オフライン TTS）
1. [VOICEVOX Nemo リリースページ](https://voicevox.hiroshiba.jp/) から対応バイナリまたは Docker イメージを取得します。
2. `./scripts/voicevox_manager.sh start` でエンジンを起動し、`.env` の `VOICEVOX_HOST` / `VOICEVOX_PORT` を環境に合わせて更新します。

#### Pexels / Pixabay（ストック映像）
1. [Pexels API](https://www.pexels.com/api/) と [Pixabay API](https://pixabay.com/api/docs/) でそれぞれキーを取得します。
2. `.env` の `PEXELS_API_KEY` / `PIXABAY_API_KEY` を設定すると、B-roll 取得のフォールバックが自動化されます。

#### Discord / Slack Webhook（通知）
1. 任意のチャンネルで Incoming Webhook を作成します。
2. `.env` に `ALERT_WEBHOOK_URL` を登録すると、動画生成失敗時の通知が届きます。

## 3. 日次運用フロー

1. **前日準備**
   - `git pull` で最新コードと設定を取得。
   - `uv run python -m app.verify` を実行して API キー、FFmpeg、フォントなどの依存を検証。
2. **ワークフロー実行**
   - 通常運用は `uv run python3 -m app.main daily`。
   - 検証目的でアップロードを抑止したい場合は `test` モード、特集用のプロンプトを使う場合は `special` モードを指定します。QA レポートは全モード共通で通知のみです。
3. **成果物の確認**
   - 台本・音声・字幕・動画は `output/` 配下に保存され、`WorkflowContext.generated_files` に一覧化されます。
   - Gemini Vision によるレビュー結果は `output/video_reviews/`、QA レポートは `data/qa_reports/` に格納されます。
4. **フィードバックとアーカイブ**
   - Google Sheets に同期された品質メトリクスを確認し、視聴維持率予測や WOW スコアの推移をレビューします。
   - 必要に応じて `python scripts/analytics_report.py` で週次レポートやフック戦略別分析を出力します。

## 4. 品質保証と監視ポイント

- **QA レポート**: `config.yaml` の `media_quality` セクションで字幕同期・音量レベル・日本語純度などの閾値を調整します。既定では `gating.enforce=false` のためレポートはブロックを伴わず、指摘内容を参考に該当ステップを手動で修正して再実行します。必要であれば `enforce=true` に戻して自動差し戻しを再開できます。
- **ローテーション管理**: Gemini / Perplexity のキーは自動ローテーションされますが、429 エラーが続いた場合は `.env` のキー数や失敗回数を確認してください。
- **TTS 設定**: VOICEVOX の話者 ID は `config.yaml.speakers` で管理します。新しい話者を追加する際は placeholder が自動補完されるため、設定漏れがあれば QA ログで検知できます。
- **メタデータ調整**: `GenerateMetadataStep` が出力する JSON（例: `metadata.json`）を基に、YouTube Studio でタイトルや説明文を微調整可能です。

## 5. トラブルシューティング

### 5.1 典型的な症状

| 症状 | チェックポイント | 対処 |
| --- | --- | --- |
| ニュースが取得できない | ログに `All news collection methods failed` | `.env` の Perplexity/NewsAPI キーを更新し再実行。必要なら `mode=test` で QA を緩和。 |
| 台本が短すぎる／空になる | QA ログの `Generated script too short` | 収集ニュース件数と `config.yaml.crew` の設定を確認し、CrewAI の再試行回数を増やす。 |
| 字幕と音声がずれる | `data/qa_reports` の `subtitle_alignment` セクション | `TranscribeAudioStep` を再実行し、音量レベルや `media_quality.subtitles` の閾値を調整。 |
| 動画生成が失敗する | FFmpeg のエラーログ / `Failed to create B-roll sequence` | 一時的に `stock_footage.enabled=false` にして再実行し、FFmpeg パスとテンプレート画像の有無を確認。 |
| QA レポートに赤字が多い | レポートの `metrics` や `message` | 閾値を見直すか、該当ステップ（字幕・音量など）を手動で修正して再実行。 |
| CrewAI Gemini 起動時に `BaseLLM.__init__() missing 1 required positional argument: 'model'` | `uv run python -m app.verify` のログで CrewAI バージョンが 0.74 以降か確認 | CrewAI 側の `BaseLLM` が `model` 引数を必須化したことが原因。`settings.llm_model` を設定し、`app.adapters.llm.CrewAIGeminiLLM` を最新コミットに更新してから `uv sync` → `app.verify` を再実行。 |

### 5.2 VideoGenerator で頻発する根本原因

- **FFmpeg バイナリの不統一**
  - `AudioSegment` が PATH 上に存在しない FFmpeg を参照すると動画生成全体が停止します。
  - 対策: `settings.ffmpeg_path` を明示し、`app.verify` または起動スクリプトで `ffmpeg -version` を強制チェック。必要に応じて `AudioSegment.converter` を同じパスに上書きしてください。
- **B-roll クロスフェードの境界条件**
  - 短尺クリップで `transition_duration` が長すぎると `xfade` フィルタの offset が負になり失敗します。旧 FFmpeg では `xfade` 非対応なため同様に失敗します。
  - 対策: クリップ長に応じて `transition_duration` を自動調整する、または `concat` ベースへフォールバックする設定を追加します。
- **字幕フォント解決エラー**
  - `fc-list` がフォントを検出できない環境では `Fontconfig error` により字幕焼き込みが失敗します。
  - 対策: OSS 日本語フォント（例: Noto Sans CJK）を同梱し、`config.yaml` で `subtitle_font_path` を指定。`app.verify` にフォントチェックを追加すると起動前に検知できます。

## 6. 参考資料

| ファイル | 内容 |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | システム全体のアーキテクチャとデータフローの詳細。 |
| [API_REFERENCE.md](API_REFERENCE.md) | 利用している外部 API のレート制限や認証仕様を整理。 |
| [FEATURES.md](FEATURES.md) | B-roll 生成、フィードバックループなど機能別の深掘り解説。 |
| [DATA_MANAGEMENT.md](DATA_MANAGEMENT.md) | ログ・メタデータ・アーカイブの管理方針。 |
| [README_CREWAI.md](README_CREWAI.md) | CrewAI エージェント構成と品質メトリクスの収集方法。 |
| [VOICEVOX.md](VOICEVOX.md) | VOICEVOX のセットアップと話者 ID 一覧。 |
| [TECHNICAL_REPORT_JA.md](TECHNICAL_REPORT_JA.md) | 技術検証の背景とパフォーマンス測定結果。 |
| [DETAILED_DESIGN_SPEC_JA.md](DETAILED_DESIGN_SPEC_JA.md) | 詳細設計書（ユースケースとコンポーネント仕様）。 |
| [agent_requirement_review.md](agent_requirement_review.md) | CrewAI エージェント要件のレビュー履歴。 |

このハンドブックと参考資料を併用することで、初期導入から日次運用、障害対応までを一貫して遂行できます。
