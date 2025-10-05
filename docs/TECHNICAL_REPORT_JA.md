# 技術報告書

## 1. 実行目的とスコープ
- 本報告書は、金融系YouTube自動生成システムの技術的成立性と改善余地を説明する。対象は `YouTubeWorkflow` に含まれるニュース収集から動画公開までの全ステップ。【F:app/main.py†L75-L102】
- 実装はPython 3.10準拠で、Pydantic設定、CrewAI/Gemini API、FFmpeg、VOICEVOXなど複数の外部サービスを統合している。【F:app/config/settings.py†L1-L120】【F:app/video.py†L1-L60】

## 2. パイプライン処理の技術詳細
### 2.1 ニュース→台本フェーズ
1. **ニュース収集**: `NewsCollector.collect_news` がPerplexity APIキーのローテーションを行い、JSON形式のニュース要約を取得。失敗時はNewsAPIおよびダミーデータへ段階的にフォールバックする。【F:app/search_news.py†L33-L118】
2. **台本生成**: `StructuredScriptGenerator.generate` がニュース要約をプロンプトに整形し、GeminiへJSONのみの回答を要求。JSONが解析できない場合はテキスト再構成で保険を掛ける。【F:app/services/script/generator.py†L62-L148】
3. **台本検証**: `ensure_dialogue_structure` が話者名の整形・敬称の補正・対話比率の検査を実施。Pydanticモデル `Script` が最低2名の話者を保証する。【F:app/services/script/validator.py†L1-L120】【F:app/services/script/validator.py†L130-L170】

### 2.2 メディア生成フェーズ
1. **音声合成**: `SynthesizeAudioStep` が設定内の話者ごとにTTSを実行し、音声ファイルを保存。生成されたパスは `WorkflowContext` へ渡される。【F:app/workflow/steps.py†L540-L638】
2. **STT・字幕整合**: `TranscribeAudioStep` が長尺音声向けのSTT（`transcribe_long_audio`）を呼び出し、単語タイムスタンプを生成。その後 `SubtitleAligner.align_script_with_stt` が類似度マッチングで字幕を分割する。【F:app/workflow/steps.py†L640-L817】【F:app/align_subtitles.py†L1-L120】
3. **動画生成**: `VideoGenerator.generate_video` がFFmpegフィルタを構築し、ストック映像が利用可能なら優先的に合成する。背景テーマのA/Bテストとアーカイブ保存も同時に行う。【F:app/video.py†L1-L124】
4. **ビジュアルデザイン統一**: `UnifiedVisualDesign.create_from_news` がニュース感情を分析し、テーマ色とフォントサイズを決定。サムネイルと動画で共有することでブランド一貫性を担保する。【F:app/services/visual_design.py†L17-L104】

### 2.3 品質・公開フェーズ
1. **メディアQA**: `MediaQAPipeline.run` が音声のRMS/ピーク、字幕行数比、動画解像度を検査し、`QualityGateReport` に結果を記録する。しきい値は `config.media_quality` によって調整可能。【F:app/services/media/qa_pipeline.py†L1-L142】【F:config.yaml†L45-L94】
2. **再試行判定**: QAの失敗が発生すると `QualityAssuranceStep` が `qa_retry_request` を `WorkflowContext` に書き込み、`YouTubeWorkflow` が指定ステップからの再開を準備する。【F:app/workflow/steps.py†L937-L1015】【F:app/main.py†L104-L205】
3. **アップロード**: `UploadToDriveStep` と `UploadToYouTubeStep` がそれぞれDriveとYouTube APIへファイルを送信。成功時は共有URL・動画IDを `WorkflowContext` に格納する。【F:app/workflow/steps.py†L1017-L1167】
4. **AIレビュー**: `ReviewVideoStep` が生成動画から一定間隔でスクリーンショットを抽出し、Geminiモデルによる内容評価を保存する。【F:app/workflow/steps.py†L1169-L1254】

## 3. 主要技術要素の分析
- **APIキー管理**: `initialize_api_infrastructure` および `get_rotation_manager` がAPIキーのローテーションを統括。これによりPerplexity/Geminiのレート制限に耐性がある。【F:app/main.py†L24-L37】【F:app/search_news.py†L13-L78】
- **設定駆動性**: `settings` オブジェクトが `.env` と `config.yaml` を統合し、話者の音声IDは環境変数から自動取得されるバリデータで補完される。【F:app/config/settings.py†L1-L49】
- **品質ゲート**: `MediaQAPipeline.should_block` がモード別のスキップや失敗時のブロック判定を行い、動画品質の最低ラインを保証する。【F:app/services/media/qa_pipeline.py†L40-L83】
- **フォールトトレランス**: 各ステップが例外を捕捉してフォールバックを返し、システム全体が止まることを避ける設計となっている。例: ニュース収集のダミーデータ、スクリプト再生成、字幕推定など。【F:app/search_news.py†L39-L118】【F:app/services/script/generator.py†L110-L148】【F:app/align_subtitles.py†L73-L120】

## 4. 技術リスクと改善提案
1. **外部API依存**: レート制限はローテーションで緩和しているが、全キーが失効した場合の通知経路が未整備。Discord通知や監視メトリクスの追加が望ましい。【F:app/search_news.py†L39-L118】
2. **字幕品質**: 現状は類似度閾値で整合しているため、話者推定の誤差が残る可能性がある。Speaker diarizationの導入で改善可能。【F:app/align_subtitles.py†L25-L120】
3. **QAカバレッジ**: 音声の主観的品質（イントネーション等）は検知できないため、人力レビューや追加モデルの導入を検討する。
4. **設定整合性**: 設定変更時の整合チェックが初期化フェーズに分散している。`app.verify` の拡張で自動検証を強化すると運用負担が減る可能性がある。

## 5. 運用インパクト
- **ログと監視**: `setup_logging` と `get_log_session` が実行ごとにログセッションIDを付与し、障害追跡を容易にする。【F:app/main.py†L10-L34】
- **ファイルアーカイブ**: `FileArchivalManager` が生成物を保管し、再編集や再公開を支援する。失敗時でもワークフロー継続が可能なため、運用コストを抑制できる。【F:app/video.py†L30-L60】
- **品質指標**: `quality_thresholds` に基づくWOWスコア等は、CrewAIから取得したメタデータを用いてモニタリングできる設計であり、日々の改善サイクルを回しやすい。【F:config.yaml†L69-L122】【F:app/workflow/steps.py†L120-L216】

## 6. まとめ
本システムは、設定駆動・フォールバック重視のアーキテクチャで自動動画生成を実現している。API依存への冗長化、字幕品質向上、QA拡張が今後の重点改善項目である。ワークフロー分割と品質ゲートにより、初見でも各ステップの役割を追跡しやすい実装となっている。
