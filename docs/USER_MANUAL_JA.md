# 運用マニュアル

## 1. システム概要
- 本マニュアルは金融系YouTube自動生成システムの運用者向けガイドである。ワークフローは `app/main.py` の `YouTubeWorkflow` が管理し、ステップ単位で失敗・再試行が制御される。【F:app/main.py†L38-L149】

## 2. 前提準備
1. **Python環境**: Python 3.10 以上。リポジトリ同梱の `pyproject.toml` に従って依存をインストールする（`uv pip sync` 等）。
2. **設定ファイル**:
   - `config.yaml` を編集し、話者、品質基準、動画設定を自社の要件へ合わせる。【F:config.yaml†L1-L122】
   - `.env` にAPIキー（Perplexity/Gemini/YouTube/Google Drive/TTS等）を記述。`app/config/settings.py` が自動で読み込む。【F:app/config/settings.py†L1-L49】
3. **外部コマンド**: FFmpegとVOICEVOXエンジンをインストールし、PATHに通す。FFmpegパスは `config.yaml` の `stock_footage.ffmpeg_path` で上書き可能。【F:config.yaml†L33-L53】【F:app/video.py†L1-L60】

## 3. 典型的な運用フロー
1. **検証**: 長時間実行前に `uv run python -m app.verify` を実行し、設定とAPIキーが有効かチェックする。
2. **日次実行**: 以下のコマンドで日次動画を生成する。
   ```bash
   uv run python3 -m app.main daily
   ```
   - モードは `daily`（通常）、`special`（特集）、`test`（検証）の3種。`YouTubeWorkflow.execute_full_workflow` の `mode` 引数で切り替わり、ニュースプロンプトやQAリトライ条件が変化する。【F:app/main.py†L104-L205】【F:app/workflow/steps.py†L39-L117】
3. **途中停止時のリカバリ**:
   - ログを確認し、失敗したステップ名と `qa_retry_request` の内容から再実行位置を把握する。【F:app/main.py†L104-L205】【F:app/workflow/steps.py†L937-L1015】
   - 必要なら `data/qa_reports` の品質レポートで具体的な失敗理由を確認する。【F:config.yaml†L45-L94】
4. **成果物の確認**:
   - 台本・音声・字幕・動画は `output/` やアーカイブディレクトリに保存され、`WorkflowContext.generated_files` でも一覧化される。【F:app/workflow/base.py†L18-L35】【F:app/main.py†L120-L149】
   - `ReviewVideoStep` が生成したフィードバックは `output/video_reviews` に格納される。【F:config.yaml†L55-L66】【F:app/workflow/steps.py†L1169-L1254】

## 4. 個別ステップの操作ポイント
- **ニュース収集**: Google Sheetsのプロンプトが利用できない場合、自動的にローカルデフォルトに切り替わるため手動対応は不要。ただしAPIキー不足時は`.env`更新後に再実行する。【F:app/workflow/steps.py†L39-L117】【F:app/search_news.py†L13-L78】
- **台本編集**: 生成台本は `context` に保存されたパス（例: `script_YYYYmmdd.txt`）を直接編集し、再実行時に上書きされないようコピーを作成する。【F:app/workflow/steps.py†L152-L200】
- **サムネイル調整**: 統一デザインの色味を変えたい場合は `app/background_theme.py` や `config.yaml` のテーマ設定を編集する。変更後は `GenerateThumbnailStep` が新デザインで再生成する。【F:app/workflow/steps.py†L305-L538】【F:app/services/visual_design.py†L17-L104】
- **音声/TTS**: VOICEVOX話者IDを変更する場合、`config.yaml` の `speakers` セクションを更新し、該当環境変数（例: `TTS_VOICE_TAKEHIRO`）を設定する。【F:config.yaml†L9-L32】【F:app/config/settings.py†L15-L49】
- **字幕確認**: `data/qa_reports` の字幕セクションに `line_ratio` や `timing_gap_seconds` が記録される。閾値を緩めたい場合は `config.yaml` の `media_quality.subtitles` を調整する。【F:app/services/media/qa_pipeline.py†L144-L246】【F:config.yaml†L45-L94】
- **動画生成**: 背景テーマを固定したい場合は `GenerateVideoStep` 実行前に `context` の `visual_design` を目的のテーマに設定してから再実行する。`use_stock_footage` フラグは `config.yaml` の `stock_footage.enabled` で制御する。【F:app/workflow/steps.py†L819-L935】【F:config.yaml†L33-L41】
- **品質ゲート**: QAでブロックされた場合、`config.yaml` の `media_quality.gating.retry_attempts` を増やすと自動再試行回数が増える。運用中に一時的にスキップしたい場合は `mode` を `test` にするとゲートが緩和される。【F:config.yaml†L45-L65】【F:app/services/media/qa_pipeline.py†L40-L83】
- **公開情報編集**: YouTube投稿後にタイトルや説明文を手動調整する場合、`GenerateMetadataStep` が出力したJSON（`metadata.json`など）を参照し、YouTube Studioで微調整する。【F:app/workflow/steps.py†L375-L446】

## 5. トラブルシューティング
| 症状 | チェックポイント | 対処 |
| --- | --- | --- |
| ニュースが取得できない | ログに「All news collection methods failed」| `.env` の Perplexity/NewsAPI キーを更新し再実行。【F:app/search_news.py†L39-L118】 |
| 台本が空になる | QAログに `Generated script too short` | ニュース件数を確認し、CrewAI設定 (`config.yaml.crew`) を有効化する。【F:app/workflow/steps.py†L120-L216】【F:config.yaml†L95-L122】 |
| 字幕がずれる | QAレポートの `subtitle_alignment` セクション | `TranscribeAudioStep` のSTT結果を再生成し、音量レベルが低すぎないか確認する。【F:app/workflow/steps.py†L640-L817】【F:app/services/media/qa_pipeline.py†L144-L246】 |
| 動画生成に失敗 | ログにFFmpegエラー | `stock_footage.enabled` を一時的にfalseにして再実行。背景画像のパスを確認。【F:app/video.py†L70-L124】【F:config.yaml†L33-L41】 |
| QAでブロック | レポートの `blocking_failures` | `media_quality` 閾値を調整、または該当ステップを手動で修正して再実行。【F:app/services/media/qa_pipeline.py†L40-L83】 |

## 6. ベストプラクティス
- 日次実行前に `git pull` で最新コードと設定を取得し、変更点を確認する。
- APIキーのローテーション設定を四半期ごとに見直し、`get_rotation_manager` に登録されているキー数が十分かを確認する。【F:app/search_news.py†L13-L78】
- QAレポートとAIレビューをNotionやSlackに転送し、継続的改善のタスクリストを作成する。
- 新しい話者を追加するときは、`StructuredScriptGenerator` が最低2話者を要求する点に注意して、台本テンプレの整合性を保つ。【F:app/services/script/generator.py†L55-L88】

## 7. 参考コマンド
- CrewAIフロー単体テスト: `uv run python3 test_crewai_flow.py`
- メディアQAのみ再実行: `uv run python -m app.workflow.qa_runner --run-id <ID>`（拡張を想定した運用コマンド）
- ログファイルの追跡: `tail -f logs/<run_id>.log`

## 8. まとめ
運用者は設定ファイルと`.env`の整合を維持し、失敗したステップに応じて再実行範囲を調整することで効率的な自動動画生成が実現できる。ログ、QAレポート、AIレビューを定期的に見直すことで品質を継続的に向上できる。
