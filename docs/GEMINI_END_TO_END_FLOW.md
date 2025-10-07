# GEMINI 活用フローの実践カタログ

CrewAI ベースの台本生成パイプラインで Gemini を呼び出す前後の処理を、**工程・責務・制御ポイント・致命的失敗モード**の 4 軸で破壊的に再構成したドキュメントです。単なる手順列挙ではなく、**誰が・何を・どこまで自動化し・どこで止めるべきか**が即座に把握できることを目指しています。

## 1. フェーズ別スイムレーンタイムライン

| タイムライン | ビジネスオペレーション | オーケストレーション (`YouTubeWorkflow`) | Gemini 連携 (`StructuredScriptGenerator`) | メディア処理 / 発信 |
| --- | --- | --- | --- | --- |
| 0. 事前初期化 | - 公開予定日の確定<br>- API キー棚卸し | `initialize_api_infrastructure()` でキー回転プールを構成<br>`ensure_ffmpeg_tooling()` で FFmpeg を検証 | - | - |
| 1. 素材収集 | `CollectNewsStep` がニュース API と Google Sheets を照合 | `WorkflowContext` にニュース群・制約・話者設定を保持 | - | - |
| 2. 台本生成 | - | `GenerateScriptStep` が Gemini ルートを選択 (`cfg.use_crewai_script_generation`) | `StructuredScriptGenerator` がプロンプト整形→Gemini 呼び出し→応答検証 | - |
| 3. メディア波及 | - | `WorkflowContext` に台本メタを格納し後続ステップを呼び出し | - | `SynthesizeAudioStep` 〜 `QualityAssuranceStep` が音声・字幕・動画・公開メタを生成 |
| 4. 監査とロールバック | - | 失敗時に `RETRY_CLEANUP_MAP` を参照しクリーンアップ | `record_llm_interaction()` がリクエスト/レスポンスを永続化 | 公開停止/再実行の意思決定をオペレーションが実施 |

> **判断ポイント**: フェーズ 2 完了直後に QA チェックを挟めるよう `WorkflowContext['script_quality']` を監視すると、Gemini 応答の破綻を後続工程に波及させずに遮断できる。

## 2. 制御フロー詳細 (BPMN テキスト表現)

| 番号 | イベント/タスク | 入力 | 制御 | 出力 | 中断条件 |
| --- | --- | --- | --- | --- | --- |
| G0 | API 基盤の起動 | `.env` / Secrets Manager | `APIKeyRotationManager.register_keys()` | 有効化されたキー回転プール | キー不在 → プロセス終了 |
| G1 | メディア依存検証 | システム PATH | `ensure_ffmpeg_tooling()` | FFmpeg 動作保証 | 実行ファイル欠落 → 強制停止 |
| G2 | ニュース収集 | ニュース API, Google Sheets | `CollectNewsStep.collect_news()` | 正規化されたニュース配列 | API 失敗 → リトライ 3 回後停止 |
| G3 | コンテキスト構築 | G2 の出力 | `WorkflowContext.update()` | `news_items`, `constraints` | バリデーション失敗 → G2 へロールバック |
| G4 | Gemini ルート選択 | 設定値 `cfg.use_crewai_script_generation` | 分岐: Gemini / ローカル LLM | 経路判定フラグ | False → ローカル台本で代替 |
| G5 | プロンプト生成 | `news_items`, 話者設定 | `_build_prompt()` | JSON スキーマ付きプロンプト | フォーマット失敗 → 1 回再試行後 G4 へ戻る |
| G6 | Gemini 呼び出し | G5 プロンプト, API キー | `LLMClient.completion(max_attempts=3)` | 生テキスト応答, レート制限情報 | 失敗 → キー回転 → 再試行 → G4 分岐 |
| G7 | 応答パース | G6 応答 | `_parse_payload()` + `_ensure_min_dialogues()` | `ScriptGenerationResult` (YAML, メタ含む) | JSON 破損 → フォールバック台本 |
| G8 | 台本品質ゲート | G7 出力 | `ensure_dialogue_structure()` | QA 通過済み台本 | 不合格 → G4 へ戻り再生成 |
| G9 | メディア生成連鎖 | G8 出力 | `SynthesizeAudioStep`→`TranscribeAudioStep`→`GenerateVideoStep` など | 音声, 字幕, 動画, サムネ, メタ | ステップ失敗 → `RETRY_CLEANUP_MAP` で該当成果物削除 |
| G10 | 監査ログ書き込み | G6 入出力, キー識別子 | `record_llm_interaction()` | 監査トレイル | ストレージ障害 → ローカル退避 (後述) |
| G11 | 最終公開判断 | G9 成果物, QA レポート | オペレーションレビュー | 公開 / 保留 / 再実行の決定 | QA 不合格 → G4/G9 へ巻き戻し |

## 3. 役割別 RACI マトリクス

| フェーズ | CrewAI Orchestrator | Gemini SRE | メディア Ops | 法務/コンプラ |
| --- | --- | --- | --- | --- |
| 0. 事前初期化 | **R**: 初期化手順実行<br>**A**: 成功判定 | **C**: キープール充足確認 | **I** | **I** |
| 1. 素材収集 | **R**: API 呼び出し | **I** | **C**: 収集ニュースのポリシー整合性 | **C**: 著作権チェック |
| 2. 台本生成 | **R**: プロンプト構築と呼び出し<br>**A**: 応答品質判定 | **C**: レート制限監視 | **I** | **C**: 台本表現の規制適合性 |
| 3. メディア波及 | **C** | **I** | **R/A**: 音声/動画生成と QA | **I** |
| 4. 監査/ロールバック | **R**: `RETRY_CLEANUP_MAP` 運用 | **A**: キー失効対応計画 | **C** | **A**: 監査証跡保全 |

## 4. データライフサイクルと保持ポリシー

| フェーズ | 主なデータ | 保持先 | 保存期間 | 消去トリガー |
| --- | --- | --- | --- | --- |
| 0 | API キー, ローテーションメトリクス | Secrets Manager, ログ | 90 日 | キー失効 |
| 1 | ニュース素材, プロンプト要件 | Firestore / `WorkflowContext` | 7 日 | 公開後のバッチ完了 |
| 2 | Gemini 応答, YAML 台本, 品質メタ | ローカル一時ファイル, `data/` の内部ストレージ | 30 日 (再利用検証期間) | 次リリース後のクリーンアップジョブ |
| 3 | 音声, 字幕, 動画, サムネイル | Google Drive, S3 | 365 日 | 著作権/契約更新 |
| 4 | LLM 監査ログ, 失敗ログ | Firestore + ローカル冗長ログ | 365 日 | コンプラレビュー完了 |

## 5. 障害復旧パスとガードレール

| 失敗モード | 即時検出指標 | 自動復旧 | 手動介入 | SLA への影響 |
| --- | --- | --- | --- | --- |
| Gemini レート制限 (HTTP 429) | `LLMClient` のエラーカウンタ | キー回転 → バックオフ → 最大 3 回リトライ | SRE が API クォータ調整 | 20 分以内に復旧できなければ当日配信遅延 |
| JSON 解析失敗 | `_parse_payload()` の例外 | フォールバック台本要求 | 編集チームが手動で台本修正 | QA 追加 30 分 |
| FFmpeg 欠落 | 初期化時の `ensure_ffmpeg_tooling()` | - | DevOps がバイナリ配置 | 起動不可 → 配信停止 |
| 音声合成失敗 | `SynthesizeAudioStep` のリトライ記録 | 3 回まで自動リトライ | ナレーターが緊急収録 | 2 時間以内の復旧を目標 |
| 監査ログ永続化失敗 | Firestore 書き込み例外 | ローカル冗長ログ (`logs/pending_llm_audit.jsonl`) へ退避 | コンプラ担当が再投入ジョブを実行 | 監査証跡 24 時間以内に整合 |

## 6. 現行フローの致命的な欠点 (アップデート)

| 区分 | 欠点 | 発生条件 | 致命性の理由 | 応急対応 | 恒久対策 | 指標 |
| --- | --- | --- | --- | --- | --- | --- |
| キー管理 | `initialize_api_infrastructure()` が複数キー前提で、単一キー環境ではフェイルオーバーせず停止する | 新規導入時にキー本数が不足 | 429/失効で即全停止、当日配信が全滞 | `cfg.use_crewai_script_generation=False` でローカル LLM 経路を強制 | Secrets Manager に最小 3 本登録を CI で検証 | `rotation_pool_size` < 2 を Slack へ通知 |
| 生成品質 | `_parse_payload()` がヒューリスティック補修後も `ensure_dialogue_structure()` をすり抜ける | Gemini 応答が部分 JSON になる | 誤台本が音声・動画工程へ波及しリソースを浪費 | フェールクローズ: 補修失敗時は即フォールバック台本を要求 | Gemini 応答スキーマを Strict Pydantic モデルに変更し `json_schema` を Gemini に渡す | QA で `dialogue_coverage` < 0.9 をブロック |
| 監査ログ | `record_llm_interaction()` が永続化失敗時にリトライしない | Firestore/DB 障害 | コンプラ監査で証跡欠落が致命的瑕疵になる | ローカル冗長ログへ退避し、`audit_replay.py` で再投入 | Firestore 書き込みを非同期キュー化し ACK を監視 | `audit_queue_depth` > 100 を PagerDuty 通知 |

## 7. 速習チェックリスト

- [ ] `.env` と Secrets Manager の Gemini キーが **3 本以上**登録済みである。
- [ ] `uv run python -m app.verify` を実行し、API/メディア依存性が揃っている。
- [ ] Google Sheets の上書きプロンプトとニュース API が同期している。
- [ ] `WorkflowContext['script_quality']` を可視化するダッシュボードがある。
- [ ] Firestore 障害時に `logs/pending_llm_audit.jsonl` が 24 時間以内に空になる運用が定着している。

---

本カタログは、Gemini 経路の自動化と人間による監視を両立させるための**恒久的な意思決定基盤**として利用してください。初期化から監査までの各フェーズは独立した責務を持ち、致命的欠点のモニタリング指標と組み合わせることで、破壊的な改善サイクルを継続的に回せます。
