# 日本語統合ガイド

金融系YouTube自動生成システムの日本語ドキュメントを一本化しました。環境構築・日次運用・詳細設計・技術検証・障害対応をすべてこのファイルから参照できます。

## 1. システム概要とワークフロー構造
- `YouTubeWorkflow` が Strategy パターンで `WorkflowStep` 群を順番に呼び出し、ニュース収集から公開までの 11 工程を自動化します。【F:app/main.py†L38-L149】
- `WorkflowContext` はステップ間の共有状態と生成ファイルを保持し、`StepResult` が成功可否・添付ファイル・警告をまとめます。【F:app/workflow/base.py†L12-L78】
- リトライ時は `RETRY_CLEANUP_MAP` で不要な状態を掃除してから再実行し、失敗した工程を安定的にやり直します。【F:app/main.py†L46-L149】

## 2. セットアップ
### 2.1 必要ソフトウェア・コマンド
| 項目 | 推奨バージョン | 補足 |
| --- | --- | --- |
| Python | 3.11 以上 | 依存関係は `uv` で管理します。
| uv | 最新安定版 | `pip install uv` で導入。
| FFmpeg | 4.4 以上 | PATH を通し、`ffmpeg -version` を事前検証。
| VOICEVOX | Nemo 版推奨 | オフライン TTS フォールバック用。

### 2.2 必須アカウント・API キー
| サービス | 用途 | 複数キー推奨 |
| --- | --- | --- |
| Google Gemini | CrewAI 台本生成 | ✅ 3-5 本ローテーションで安定化。
| Perplexity AI | ニュース収集 | ✅ 3 本以上で429を回避。
| NewsAPI.org | ニュースフォールバック | 任意（無料枠 100 req/日）。
| ElevenLabs | 高品質 TTS | 任意。
| VOICEVOX | TTS フォールバック | 任意。
| Google Sheets / Drive / YouTube | ログ集計・公開 | サービスアカウント JSON を `secret/service-account.json` に配置。

`.env` に API キーを記載し、`config.yaml` でストック映像や品質ゲートの設定を管理します。

### 2.3 初期構築チェックリスト
1. リポジトリを取得して `uv sync` で依存を同期する。
2. `secret/.env.example` を複製し、API キーやサービスアカウントを登録する。
3. FFmpeg や VOICEVOX を導入した場合は `config.yaml` のパス設定を確認する。
4. `uv run python -m app.verify` で FFmpeg・フォント・API キーを検証する。
5. `uv run python3 -m app.main test` でドライランを実施し、本番前に動作を確認する。

### 2.4 外部サービス設定ガイド
#### Perplexity AI（ニュース収集）
1. <https://www.perplexity.ai/settings/api> にアクセスし「Create API Key」をクリック。
2. 生成されたキーをそのまま `.env` の `PERPLEXITY_API_KEYS` にカンマ区切りで貼り付けます。

#### NewsAPI.org（ニュースフォールバック）
1. <https://newsapi.org/register> で無料アカウントを作成。
2. サインアップ完了画面に表示されるキーを `.env` の `NEWSAPI_API_KEY` に設定します。

#### Google Cloud（Gemini / Sheets / Drive / YouTube）
1. <https://console.cloud.google.com/apis/dashboard> で対象プロジェクトを開き、Gemini API と Sheets/Drive/YouTube Data API を「有効化」。
2. <https://console.cloud.google.com/iam-admin/serviceaccounts> でサービスアカウントを作成し、`service-account.json` をダウンロードして `secret/service-account.json` へ配置。
3. Gemini の API キーは <https://aistudio.google.com/app/apikey> で発行し、`.env` の `GEMINI_API_KEYS` にカンマ区切りで登録します。

#### ElevenLabs（高品質 TTS）
1. <https://elevenlabs.io/app/speech-synthesis> の「Get API Key」からキーをコピー。
2. `.env` の `ELEVENLABS_API_KEY` に貼り付け、必要に応じて `config.yaml` の話者設定を更新します。

#### VOICEVOX Nemo（オフライン TTS）
1. <https://voicevox.hiroshiba.jp/> から最新バージョンをダウンロード（Docker 利用なら <https://hub.docker.com/r/voicevox/voicevox_engine>）。
2. 展開後に `scripts/voicevox_manager.sh start` を実行し、`VOICEVOX_HOST` / `VOICEVOX_PORT` を環境に合わせて設定します。

#### Pexels / Pixabay（ストック映像）
- Pexels: <https://www.pexels.com/api/new/> でキーを取得し、`.env` の `PEXELS_API_KEY` に追加。
- Pixabay: <https://pixabay.com/api/docs/> の「Get API Key」から取得し、`.env` の `PIXABAY_API_KEY` に追加。

#### Discord / Slack Webhook（通知）
- Discord: <https://support.discord.com/hc/ja/articles/228383668> の手順で Webhook URL を生成し、`.env` の `ALERT_WEBHOOK_URL` に登録。
- Slack: <https://api.slack.com/messaging/webhooks> から Incoming Webhook を作成し、同様に `ALERT_WEBHOOK_URL` に設定します。

## 3. 日次運用フロー
1. **前日準備**: `git pull` で最新化し、`uv run python -m app.verify` で依存を検証します。
2. **ワークフロー実行**: 通常は `uv run python3 -m app.main daily`。検証用途は `test`、特集は `special` モードを指定します。
3. **成果物確認**: 台本・音声・字幕・動画は `output/`、QA レポートは `data/qa_reports/`、レビュー結果は `output/video_reviews/` に保存されます。
4. **フィードバックとアーカイブ**: Google Sheets の品質メトリクスを確認し、必要に応じて `python scripts/analytics_report.py` で週次レポートを生成します。

## 4. 品質保証とトラブルシューティング
### 4.1 監視ポイント
- `config.yaml` の `media_quality` で字幕同期・音量などの閾値を調整できます。既定では `gating.enforce=false` なのでワークフローは停止しません。【F:config.yaml†L59-L94】
- Gemini / Perplexity の API キーは自動ローテーションされますが、429 が続く場合は `.env` のキー数と失敗回数を確認します。【F:app/search_news.py†L13-L118】
- VOICEVOX の話者 ID は `settings.speakers` で管理され、欠落は QA ログで検知されます。【F:app/config/settings.py†L1-L120】【F:app/workflow/steps.py†L540-L638】
- `GenerateMetadataStep` が出力する `metadata.json` を基に YouTube Studio で微調整できます。【F:app/workflow/steps.py†L375-L446】

### 4.2 典型的な症状と対処
| 症状 | チェックポイント | 対処 |
| --- | --- | --- |
| ニュースが取得できない | ログに `All news collection methods failed` | `.env` の Perplexity/NewsAPI キーを更新し、必要なら `mode=test` で QA を緩和。 |
| 台本が短すぎる／空になる | QA ログの `Generated script too short` | ニュース件数と `config.yaml.crew` を確認し、CrewAI の再試行回数を増やす。 |
| 字幕と音声がずれる | `data/qa_reports` の `subtitle_alignment` | `TranscribeAudioStep` を再実行し、閾値を調整。 |
| 動画生成が失敗する | FFmpeg ログ / `Failed to create B-roll sequence` | 一時的に `stock_footage.enabled=false` にし、FFmpeg パスとテンプレートを確認。 |
| QA レポートが赤字だらけ | レポートの `metrics` や `message` | 閾値を見直すか該当ステップを手動修正して再実行。 |
| CrewAI 起動時に `BaseLLM.__init__()` エラー | `uv run python -m app.verify` のバージョン確認 | `settings.llm_model` を設定し、CrewAI を最新化してから再実行。 |

### 4.3 VideoGenerator の根本原因
- **FFmpeg バイナリの不統一**: `settings.ffmpeg_path` を明示し、`AudioSegment.converter` を同じパスに揃えます。【F:app/video.py†L1-L124】
- **B-roll クロスフェードの境界条件**: クリップが短い場合は `transition_duration` を動的に調整するか `concat` にフォールバックします。【F:app/workflow/steps.py†L819-L935】
- **字幕フォント解決エラー**: Noto Sans などを同梱し、`subtitle_font_path` を設定。`app.verify` にフォント検証を追加すると予防できます。【F:app/video.py†L30-L124】

### 4.4 リトライ戦略
- QA が差し戻しを要求した場合は `WorkflowStep.retry()` が該当ステップを再実行し、`RETRY_CLEANUP_MAP` のキーをクリアします。【F:app/main.py†L46-L149】
- `MediaQAPipeline` は `should_block` が `True` のときのみワークフローを停止させる設計で、既定の `false` 設定ではレポートのみを出力します。【F:app/services/media/qa_pipeline.py†L40-L176】【F:config.yaml†L59-L94】

## 5. 詳細設計ハイライト
### 5.1 コア抽象コンポーネント
| 要素 | 定義 | 役割のイメージ |
| --- | --- | --- |
| `YouTubeWorkflow` | ステップ配列とリトライ戦略を保持し、実行を制御します。【F:app/main.py†L59-L174】 | プロジェクトマネージャー。 |
| `WorkflowContext` | 実行 ID・共有状態・生成ファイルを管理します。【F:app/workflow/base.py†L18-L45】 | 旅のしおり。 |
| `StepResult` | 成功可否・データ・ファイル一覧を返却します。【F:app/workflow/base.py†L12-L34】 | 成果報告書。 |
| `WorkflowStep` | `execute` と `_success`/`_failure` を共通化します。【F:app/workflow/base.py†L36-L77】 | 担当者のテンプレート。 |

### 5.2 ステップ別の責務
| ステップ | 主要処理 | 暗黙的な副作用 |
| --- | --- | --- |
| CollectNewsStep | Perplexity/NewsAPI を用いてニュースを収集し、Sheets プロンプトを解決します。【F:app/workflow/steps.py†L33-L117】 | 成功ニュースを `context` に保存し、後続ステップの入力とします。 |
| GenerateScriptStep | CrewAI/Gemini で台本を生成し、構造検証を通します。【F:app/workflow/steps.py†L120-L216】 | 品質メトリクスを `context` に格納し、字幕整合が利用します。 |
| GenerateVisualDesignStep | ニュース感情からテーマを決定します。【F:app/workflow/steps.py†L305-L373】 | サムネイルと動画生成が同じテーマを共有します。 |
| GenerateMetadataStep | タイトル・説明文を生成し、SEO バリデーションを行います。【F:app/workflow/steps.py†L375-L446】 | 生成した JSON を `context` に保存し、公開処理で参照します。 |
| GenerateThumbnailStep | 統一デザインを使ってサムネイルを作成します。【F:app/workflow/steps.py†L448-L538】 | 失敗時は警告を残しつつ既定テンプレートへフォールバックします。 |
| SynthesizeAudioStep | 台本を再正規化して TTS を実行します。【F:app/workflow/steps.py†L540-L638】 | 話者設定が不足すると警告を記録します。 |
| TranscribeAudioStep | 長尺音声を STT し、タイムスタンプ付き単語列を返します。【F:app/workflow/steps.py†L640-L714】 | 字幕整合に必要な `stt_words` を保存します。 |
| AlignSubtitlesStep | 台本と STT を類似度でマッチングし、SRT を出力します。【F:app/workflow/steps.py†L716-L817】【F:app/align_subtitles.py†L1-L120】 | 字幕の日本語品質チェックを暗黙適用します。 |
| GenerateVideoStep | FFmpeg フィルタを構築し、音声・字幕・B-roll を合成します。【F:app/workflow/steps.py†L819-L935】【F:app/video.py†L1-L124】 | `FileArchivalManager` が成果物をアーカイブに整理します。 |
| QualityAssuranceStep | `MediaQAPipeline` でメディア品質を検査します。【F:app/workflow/steps.py†L585-L633】【F:app/services/media/qa_pipeline.py†L1-L176】 | レポートを保存し、必要なら差し戻しを要求します。 |
| UploadToDriveStep | 生成物を Drive にアップロードし、共有リンクを返します。【F:app/workflow/steps.py†L1017-L1077】 | 失敗してもローカルファイルは保持されます。 |
| UploadToYouTubeStep | YouTube Data API で公開し、動画 ID / URL を記録します。【F:app/workflow/steps.py†L1079-L1167】 | メタデータやサムネイルを `context` から参照します。 |
| ReviewVideoStep | Gemini Vision でレビューを実施し、フィードバックを保存します。【F:app/workflow/steps.py†L1169-L1254】 | 改善点とスクリーンショットをアーカイブします。 |

### 5.3 サービス層コンポーネント
- **NewsCollector**: Perplexity → NewsAPI → ダミーデータの三段構えでニュースを返します。【F:app/search_news.py†L1-L120】
- **StructuredScriptGenerator**: Gemini へ JSON スキーマで台本を依頼し、失敗時はテキスト再構成します。【F:app/services/script/generator.py†L1-L148】
- **ensure_dialogue_structure**: 話者比率や敬称をチェックし、整形済みテキストを返します。【F:app/services/script/validator.py†L1-L170】
- **SubtitleAligner**: 台本文と STT を類似度マッチングで整列し、表示時間ガイドラインを適用します。【F:app/align_subtitles.py†L1-L120】
- **VideoGenerator**: FFmpeg フィルタグラフを構築し、背景テーマ選択とアーカイブを同時に行います。【F:app/video.py†L1-L124】
- **MediaQAPipeline**: 音声レベル・字幕カバレッジ・動画ビットレートなどを検査し、`QualityGateReport` を生成します。【F:app/services/media/qa_pipeline.py†L1-L246】
- **UnifiedVisualDesign**: ニュース感情からテーマカラーを決定し、サムネイルと動画へ渡します。【F:app/services/visual_design.py†L17-L104】

## 6. 技術評価と改善課題
- **API キー管理**: `initialize_api_infrastructure` と `get_rotation_manager` がキーをローテーションし、レート制限への耐性を高めます。【F:app/main.py†L24-L37】【F:app/search_news.py†L13-L78】
- **設定駆動性**: `settings` が `.env` と `config.yaml` を統合し、話者 ID を環境変数から補完します。【F:app/config/settings.py†L1-L120】
- **メディアパイプライン**: TTS → STT → 字幕整合 → FFmpeg 合成の直列フローで早期失敗を検出し、`_failure` で停止します。【F:app/workflow/steps.py†L540-L935】
- **品質レポート**: `MediaQAPipeline.should_block` でブロック判定を制御し、助言モードと強制モードを切り替えられます。【F:app/services/media/qa_pipeline.py†L40-L176】
- **改善提案**: API 失効時の通知経路整備、字幕 diarization の導入、`app.verify` の拡張で設定変更の自動検証を強化する余地があります。【F:app/search_news.py†L39-L118】【F:app/align_subtitles.py†L25-L120】【F:app/services/media/qa_pipeline.py†L1-L176】

## 7. 参考資料
| ファイル | 内容 |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | システム全体のアーキテクチャとデータフロー。
| [API_REFERENCE.md](API_REFERENCE.md) | 外部 API のレート制限と認証仕様。
| [FEATURES.md](FEATURES.md) | B-roll 生成やフィードバックループの詳細。
| [DATA_MANAGEMENT.md](DATA_MANAGEMENT.md) | ログ・アーカイブの取り扱い方針。
| [README_CREWAI.md](README_CREWAI.md) | CrewAI エージェント構成と品質メトリクス。
| [VOICEVOX.md](VOICEVOX.md) | VOICEVOX のセットアップと話者一覧。
| [agent_requirement_review.md](agent_requirement_review.md) | エージェント要件レビュー履歴。
