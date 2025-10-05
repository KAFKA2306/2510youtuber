# **YouTube動画自動生成システム 完全構築マニュアル（統合ガイド対応版）**

このドキュメントは従来のステップバイステップ構成を簡易チェックリストとして残しつつ、最新情報をまとめた [JA_OPERATIONS_GUIDE.md](JA_OPERATIONS_GUIDE.md) への導線を提供します。まずは以下のクイックスタートで環境を整え、詳細が必要になったら該当セクションを参照してください。

## クイックスタートチェックリスト

| ステップ | やること | コマンド / リンク | 詳細ガイド |
| --- | --- | --- | --- |
| 1 | リポジトリ取得と依存関係同期 | `git clone ...` → `uv sync` | [2.3 初期セットアップ手順](JA_OPERATIONS_GUIDE.md#23-初期セットアップ手順) |
| 2 | `.env` を作成し API キーを登録 | `cp secret/.env.example secret/.env` | [2.4 外部サービス設定ガイド](JA_OPERATIONS_GUIDE.md#24-外部サービス設定ガイド) |
| 3 | FFmpeg / VOICEVOX などローカル要件を整備 | システムに応じてインストール | [2.1 必要ソフトウェア・コマンド](JA_OPERATIONS_GUIDE.md#21-必要ソフトウェアコマンド) |
| 4 | サービスアカウント JSON を配置 | `secret/service-account.json` | [Google Cloud 設定](JA_OPERATIONS_GUIDE.md#google-cloudgemini--sheets--drive--youtube) |
| 5 | 動作確認 | `uv run python -m app.verify` | [2.3 初期セットアップ手順](JA_OPERATIONS_GUIDE.md#23-初期セットアップ手順) |
| 6 | 初回ドライラン | `uv run python3 -m app.main test` | [3. 日次運用フロー](JA_OPERATIONS_GUIDE.md#3-日次運用フロー) |

## リンク集（旧マニュアルで人気の項目）

- **Perplexity API キー取得手順** → [JA_OPERATIONS_GUIDE.md - Perplexity AI](JA_OPERATIONS_GUIDE.md#perplexity-aiニュース収集)
- **NewsAPI フォールバック設定** → [JA_OPERATIONS_GUIDE.md - NewsAPI.org](JA_OPERATIONS_GUIDE.md#newsapiorgニュースフォールバック)
- **Gemini / YouTube 用サービスアカウント** → [JA_OPERATIONS_GUIDE.md - Google Cloud](JA_OPERATIONS_GUIDE.md#google-cloudgemini--sheets--drive--youtube)
- **VOICEVOX Nemo の導入** → [JA_OPERATIONS_GUIDE.md - VOICEVOX Nemo](JA_OPERATIONS_GUIDE.md#voicevox-nemoオフライン-tts)
- **ストック映像 API 設定** → [JA_OPERATIONS_GUIDE.md - Pexels / Pixabay](JA_OPERATIONS_GUIDE.md#pexels--pixabayストック映像)
- **Webhook 通知設定** → [JA_OPERATIONS_GUIDE.md - Discord / Slack](JA_OPERATIONS_GUIDE.md#discord--slack-webhook通知)

## 旧バージョンの完全手順を参照したい場合

Git 履歴から本ファイルの過去コミットを確認することで、従来の章立て（開発フェーズ、料金比較など）も閲覧できます。`git show <commit>:docs/SETUP.md` を利用してください。

最新の環境構築情報は常に JA_OPERATIONS_GUIDE.md に統合されるため、運用時はそちらを基準にしてください。
