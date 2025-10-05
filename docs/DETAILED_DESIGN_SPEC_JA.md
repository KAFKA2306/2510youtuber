# 詳細設計仕様書

## 1. システム全体像
- **目的**: 日次の経済ニュースからYouTube動画を自動生成し、台本・音声・映像・公開までを一貫管理する。ワークフローは `app/main.py` の `YouTubeWorkflow` クラスが戦略パターンで統制する。【F:app/main.py†L38-L102】
- **制御フロー**: `YouTubeWorkflow.steps` に登録された `WorkflowStep` 実装を順番に実行し、`WorkflowContext` がステップ間の状態と生成ファイルを共有する。【F:app/main.py†L75-L102】【F:app/workflow/base.py†L12-L78】
- **リトライ設計**: 品質検査での再試行指示を `RETRY_CLEANUP_MAP` が明示的に定義し、再実行時に不要なコンテキストを掃除する暗黙的挙動も補助する。【F:app/main.py†L46-L63】

## 2. コア抽象コンポーネント
### 2.1 WorkflowStep 基底クラス
- **明示的定義**: `WorkflowStep` は `step_name` プロパティと `execute` メソッドを抽象化し、成功・失敗結果を `_success` と `_failure` ヘルパーで統一して返す。【F:app/workflow/base.py†L36-L77】
- **暗黙的役割**: すべてのステップは副作用として `WorkflowContext` を更新する規約を共有し、テスト容易性を確保する（インターフェースに明文化されていないが `execute` 実装が一貫して `context.set` を呼び出す）。【F:app/workflow/steps.py†L33-L200】

### 2.2 WorkflowContext / StepResult
- **StepResult**: 成功可否、データ、生成ファイルを保持し、辞書ライクなアクセスをサポートする。【F:app/workflow/base.py†L12-L34】
- **WorkflowContext**: 実行ID・モード・共有状態・生成ファイルを管理。`set`/`get`/`add_files` が明示定義されており、暗黙的に「ステップ間の通信バス」として働く。【F:app/workflow/base.py†L18-L35】

## 3. ワークフローステップ詳細
| ステップ | 明示的な定義 | 暗黙的な意図・副作用 |
| --- | --- | --- |
| CollectNewsStep | Perplexity/NewsAPIを使いニュースを収集し、プロンプトをシートとモードに応じて切り替える。【F:app/workflow/steps.py†L33-L117】 | Sheets連携が失敗した場合のフェイルセーフとしてローカルプロンプトにフォールバックする。ニュース結果を `context` に保存する規約を他ステップが暗黙依存。【F:app/workflow/steps.py†L87-L108】 |
| GenerateScriptStep | CrewAI（構造化スクリプトジェネレータ）またはレガシー手段で台本を生成し、`ensure_dialogue_structure` で検証する。【F:app/workflow/steps.py†L120-L216】 | バリデーション警告をロギングし、`context` に品質メトリクスと構造化データを格納することで後続ステップ（字幕整合・QA）が暗黙的に活用。 |
| GenerateVisualDesignStep | 統一デザインを算出し、サムネ・動画に共通テーマを提供。【F:app/workflow/steps.py†L305-L373】 | `UnifiedVisualDesign.create_from_news` がニュース感情に基づいてテーマを選択し、背景テーマ管理のA/Bテスト結果を暗黙的に活用する。【F:app/services/visual_design.py†L17-L104】 |
| GenerateMetadataStep | Geminiを用いてタイトル・説明文等を生成し、SEO要件を満たすようバリデーションする。【F:app/workflow/steps.py†L375-L446】 | メタデータは `context` に保存され、Drive/YouTube アップロードで暗黙的に参照される。 |
| GenerateThumbnailStep | 視覚デザインとスクリプトからサムネイルを生成し、ファイルを追跡する。【F:app/workflow/steps.py†L448-L538】 | サムネイル生成サービスはデザイン設定の暗黙インターフェースを利用し、`context` に書き込んだファイルパスが後続の動画生成で利用される。 |
| SynthesizeAudioStep | TTSで台本を音声化し、生成パスを返す。【F:app/workflow/steps.py†L540-L638】 | スピーカー設定は `settings.speakers` の暗黙的制約に従い、音声品質QAの入力となる。 |
| TranscribeAudioStep | 音声からSTT結果を作成し、単語タイムスタンプを提供。【F:app/workflow/steps.py†L640-L714】 | 字幕整合が `stt_words` を必要とするため、`context` 保持が暗黙的契約。 |
| AlignSubtitlesStep | 台本とSTTを付き合わせて字幕を整列し、SRTを書き出す。【F:app/workflow/steps.py†L716-L817】【F:app/align_subtitles.py†L1-L120】 | 日本語品質チェックは存在すれば自動適用される（依存モジュールの存在チェックによる暗黙機能）。【F:app/align_subtitles.py†L13-L24】 |
| GenerateVideoStep | 音声・字幕・背景デザインを合成して動画を作成。ストック映像の使用可否を判断し、FFmpeg設定を適用。【F:app/workflow/steps.py†L819-L935】【F:app/video.py†L1-L129】 | テーマA/Bテストやストック映像切替は設定値から暗黙的に決定され、ファイルアーカイブ管理が副作用として働く。【F:app/video.py†L30-L124】 |
| QualityAssuranceStep | MediaQAPipelineで音声・字幕・動画の品質検査を実施し、ブロック条件を判定。【F:app/workflow/steps.py†L937-L1015】【F:app/services/media/qa_pipeline.py†L1-L142】 | QAレポートの永続化は例外非同期にも失敗しないよう警告に留める暗黙設計。再試行要求は `context` に `qa_retry_request` を設定する。 |
| UploadToDriveStep | 生成物をDriveへアップロードし、共有リンクを返す。【F:app/workflow/steps.py†L1017-L1077】 | `FileArchivalManager` が暗黙的にアーカイブを生成し、失敗時はローカル保持のみで進行する。 |
| UploadToYouTubeStep | YouTube Data APIで動画を公開し、動画IDとURLを記録。【F:app/workflow/steps.py†L1079-L1167】 | メタデータやサムネイルが `context` から暗黙参照される設計。 |
| ReviewVideoStep | 生成動画をAIレビューにかけ、フィードバックを生成して保存。【F:app/workflow/steps.py†L1169-L1254】 | フィードバックは次回改善のための記録として暗黙に扱われる。 |

## 4. サービス層コンポーネント
### 4.1 ニュース収集 (`NewsCollector`)
- **定義**: Perplexity APIキーのローテーション、NewsAPIフォールバック、ダミーニュース生成を管理。【F:app/search_news.py†L1-L120】
- **直観的説明**: まず複数のPerplexityキーを順番に試し、失敗すれば一般ニュースAPI、それでも駄目ならテスト用ニュースを返す「三段構えのニュース調達係」。

### 4.2 スクリプト生成 (`StructuredScriptGenerator`)
- **定義**: Geminiを呼び出しJSONスキーマで台本を取得し、`ensure_dialogue_structure` で検証する。【F:app/services/script/generator.py†L1-L135】
- **直観的説明**: ニュース要約をもとに「会話台本のテンプレ」に沿ってLLMにお願いし、万一JSON化に失敗してもテキストから復元する保険を持つ台本職人。

### 4.3 スクリプト検証 (`ensure_dialogue_structure`)
- **定義**: 台本を行単位で整形し、話者・対話比率・敬称などを確認する。【F:app/services/script/validator.py†L1-L120】【F:app/services/script/validator.py†L171-L255】
- **直観的説明**: 「話者ラベルが付いているか」「会話が十分に交互しているか」を機械的に点検する校正係。

### 4.4 字幕整合 (`SubtitleAligner`)
- **定義**: 台本の文とSTT結果を類似度でマッチングし、最大表示時間・二行表示などのガイドラインを適用してSRTを生成する。【F:app/align_subtitles.py†L1-L120】
- **直観的説明**: 音声で発話された単語のタイミングを頼りに台本の文を当てはめ、読める長さに自動調整する字幕職人。

### 4.5 動画生成 (`VideoGenerator`)
- **定義**: FFmpegで音声・字幕・背景を合成し、必要ならストック映像へ切り替える。背景テーマはA/Bテストで選択する。【F:app/video.py†L1-L124】
- **直観的説明**: まずストック映像の豪華版を試し、駄目なら自前の動く背景を用意して字幕を重ねる映像編集者。テーマの選択やアーカイブ保存も同時にこなす。

### 4.6 メディアQA (`MediaQAPipeline`)
- **定義**: 音声レベル、字幕カバレッジ、動画ビットレートなどを検査し、結果を `QualityGateReport` にまとめる。【F:app/services/media/qa_pipeline.py†L1-L142】【F:app/services/media/qa_pipeline.py†L144-L246】
- **直観的説明**: 生成物を受け取り「音が割れていないか」「字幕が追いついているか」「動画が高解像度か」をチェックする検品担当。基準を満たさなければ再実行を要求する。

### 4.7 ビジュアルデザイン (`UnifiedVisualDesign`)
- **定義**: ニュースの感情解析からテーマ色と背景テーマを選び、サムネイル・動画双方に渡す。【F:app/services/visual_design.py†L1-L104】
- **直観的説明**: ニュースがポジティブなら緑、警告なら赤といった感情に合わせてブランド一貫性を保つアートディレクター。

## 5. 設定と外部依存
- **設定読み込み**: `app/config/settings.py` が `config.yaml` と `.env` を統合し、Pydanticモデルで構造化する。話者・動画・QA設定などが明示的フィールドとして定義され、バリデーションで環境変数から音声IDを補完する。【F:app/config/settings.py†L1-L120】
- **暗黙的依存**: Geminiモデル名や話者数など、設定が成立していることを `StructuredScriptGenerator` が前提としており、2人以上の話者がいなければ初期化時にエラーを投げる。【F:app/services/script/generator.py†L55-L88】
- **外部サービス**: Perplexity/Gemini/YouTube/Google Drive/VOICEVOX/FFmpeg/Pydub 等を利用。APIキーは `initialize_api_infrastructure` でローテーション管理を初期化する。【F:app/main.py†L24-L37】【F:app/search_news.py†L13-L78】

## 6. エラーハンドリング戦略
- **ニュース取得失敗**: 例外を捕捉しつつ段階的フォールバック。最終的にダミーデータを返し、ワークフロー継続を優先。【F:app/search_news.py†L39-L118】
- **スクリプト生成失敗**: JSON解析失敗時はテキスト整形へフォールバックし、品質ゲートが有効なら再試行する。【F:app/services/script/generator.py†L89-L148】
- **QA失敗**: `MediaQAPipeline.should_block` が `config.media_quality.gating` を参照し、再試行許可モード以外では即停止する。【F:app/services/media/qa_pipeline.py†L40-L83】
- **アップロード失敗**: 例外はログ出力しつつ `StepResult` で失敗を返す。`YouTubeWorkflow` 側でエラーを拾い、Discord通知やクリーンアップを行う暗黙設計（`execute_full_workflow` 内でハンドリング）。【F:app/main.py†L104-L205】

## 7. データ永続化とアーカイブ
- **ファイルトラッキング**: 各ステップは生成ファイルパスを `StepResult.files_generated` に積み、`WorkflowContext.add_files` が集約して最終的な後処理を容易にする。【F:app/workflow/base.py†L12-L35】【F:app/main.py†L120-L149】
- **アーカイブ**: 動画生成時に `FileArchivalManager` が原稿・音声・字幕をコピーし、再利用に備える暗黙機能。【F:app/video.py†L30-L60】

## 8. 品質・改善ループ
- **WOW/日本語純度閾値**: `config.yaml` の `quality_thresholds` がスクリプト品質指標の目標を定義し、CrewAIメタデータ経由で検査する暗黙仕様。【F:config.yaml†L69-L122】
- **動画レビュー**: `ReviewVideoStep` が AI モデルにスクリーンショットを解析させ、フィードバックを `context` に保存することで次回改修の材料を残す。【F:app/workflow/steps.py†L1169-L1254】

## 9. まとめ
本システムは戦略パターンで分解されたワークフローを、設定駆動・品質ゲート付きで統合する。各ステップは明示的なインターフェース (`WorkflowStep`) に従う一方、`WorkflowContext` に値を格納する暗黙契約で連携し、エラーフォールバックと再試行により信頼性を確保する。
