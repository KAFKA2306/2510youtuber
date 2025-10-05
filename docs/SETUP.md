# **YouTube動画自動生成システム 完全構築マニュアル（統合ガイド対応版）**

このドキュメントは従来のステップバイステップ構成を簡易チェックリストとして残しつつ、最新情報をまとめた [JAPANESE_MASTER_GUIDE.md](JAPANESE_MASTER_GUIDE.md) への導線を提供します。まずは以下のクイックスタートで環境を整え、詳細が必要になったら該当セクションを参照してください。

## クイックスタートチェックリスト

| ステップ | やること | コマンド / リンク | 詳細ガイド |
| --- | --- | --- | --- |
| 1 | リポジトリ取得と依存関係同期 | `git clone ...` → `uv sync` | [2.3 初期構築チェックリスト](JAPANESE_MASTER_GUIDE.md#23-初期構築チェックリスト) |
| 2 | `.env` を作成し API キーを登録 | `cp secret/.env.example secret/.env` | [2.4 外部サービス設定ガイド](JAPANESE_MASTER_GUIDE.md#24-外部サービス設定ガイド) |
| 3 | FFmpeg / VOICEVOX などローカル要件を整備 | システムに応じてインストール | [2.1 必要ソフトウェア・コマンド](JAPANESE_MASTER_GUIDE.md#21-必要ソフトウェアコマンド) |
| 4 | サービスアカウント JSON を配置 | `secret/service-account.json` | [Google Cloud 設定](JAPANESE_MASTER_GUIDE.md#google-cloudgemini--sheets--drive--youtube) |
| 5 | 動作確認 | `uv run python -m app.verify` | [2.3 初期構築チェックリスト](JAPANESE_MASTER_GUIDE.md#23-初期構築チェックリスト) |
| 6 | 初回ドライラン | `uv run python3 -m app.main test` | [3. 日次運用フロー](JAPANESE_MASTER_GUIDE.md#3-日次運用フロー) |

## リンク集（旧マニュアルで人気の項目）

- **Perplexity API キー取得手順** → [JAPANESE_MASTER_GUIDE.md - Perplexity AI](JAPANESE_MASTER_GUIDE.md#perplexity-aiニュース収集)
- **NewsAPI フォールバック設定** → [JAPANESE_MASTER_GUIDE.md - NewsAPI.org](JAPANESE_MASTER_GUIDE.md#newsapiorgニュースフォールバック)
- **Gemini / YouTube 用サービスアカウント** → [JAPANESE_MASTER_GUIDE.md - Google Cloud](JAPANESE_MASTER_GUIDE.md#google-cloudgemini--sheets--drive--youtube)
- **VOICEVOX Nemo の導入** → [JAPANESE_MASTER_GUIDE.md - VOICEVOX Nemo](JAPANESE_MASTER_GUIDE.md#voicevox-nemoオフライン-tts)
- **ストック映像 API 設定** → [JAPANESE_MASTER_GUIDE.md - Pexels / Pixabay](JAPANESE_MASTER_GUIDE.md#pexels--pixabayストック映像)
- **Webhook 通知設定** → [JAPANESE_MASTER_GUIDE.md - Discord / Slack](JAPANESE_MASTER_GUIDE.md#discord--slack-webhook通知)

## 旧バージョンの完全手順を参照したい場合

Git 履歴から本ファイルの過去コミットを確認することで、従来の章立て（開発フェーズ、料金比較など）も閲覧できます。`git show <commit>:docs/SETUP.md` を利用してください。

最新の環境構築情報は常に JAPANESE_MASTER_GUIDE.md に統合されるため、運用時はそちらを基準にしてください。
