# LLM出力規律ガイド

このドキュメントは、CrewAIワークフローにおけるLLM出力統制の全体像と、破壊的な改善ロードマップをまとめたものです。構造化出力・会話制約・日本語純度・品質ゲート・ログ監査といった各ガードレールについて、現在の実装と失敗シグナル、次の一手を常に同期してください。

## エグゼクティブサマリー
- スクリプト生成はStrict JSON→YAMLフォールバック→品質ゲートという三層で防衛し、パース不能時は自動リカバリを図ります。【F:app/services/script/generator.py†L117-L194】
- 会話構造と話者名はPythonバリデータで静的整形し、CrewAIプロンプトは最小制約に留めています。【F:app/services/script/validator.py†L120-L210】【F:app/services/script/generator.py†L196-L200】
- 日本語純度は品質レビューと最終チェックでダブルゲートし、95点以上・英語混入ゼロを要求するテンプレートが存在します。【F:app/config_prompts/prompts/quality_check.yaml†L141-L311】
- WOWスコア8.0以上などの閾値は設定ファイルと品質パイプラインで評価され、未達時はリトライやフォールバックに接続されます。【F:config.yaml†L132-L149】【F:app/script_quality.py†L192-L353】
- `LLMInteractionLogger`が全ステージのプロンプト/レスポンスをJSONLに記録し、失敗調査と再学習データ抽出を支えています。【F:app/llm_logging.py†L1-L154】【F:app/script_quality.py†L236-L334】

## 主要ガードレール俯瞰
| 領域 | 主な実装 | 自動検知/フォールバック | 代表的な失敗シグナル | 推奨強化 |
| --- | --- | --- | --- | --- |
| 構造化出力 | `StructuredScriptGenerator` がJSONのみを要求し、バリデーション＋YAML化を実施。【F:app/services/script/generator.py†L117-L194】 | JSON抽出失敗時はテキスト→YAML変換、最終的にバックアップ台本生成。【F:app/services/script/generator.py†L133-L194】 | JSON外テキスト混入、数値型崩れ、長すぎる応答。 | JSON Schema + テンプレート化でLLMは穴埋めのみ／YAML先行提示。 |
| 会話フォーマット | CrewAIプロンプトの話者ホワイトリストと`ensure_dialogue_structure`の静的整形。【F:app/services/script/generator.py†L196-L200】【F:app/services/script/validator.py†L120-L210】 | 最低行数・話者数未達で差し戻し、alias補正で自動修正。【F:app/services/script/validator.py†L150-L210】 | 話者タグ漏れ、非会話行の氾濫、単一話者台本。 | 自動補正辞書の拡張とフォーマッタで後処理完結させ、プロンプト負荷を軽減。 |
| 日本語純度 | 品質レビューTask6/7テンプレートと最終脚本生成ステージでの指示。【F:app/config_prompts/prompts/quality_check.yaml†L163-L311】【F:app/script_quality.py†L288-L343】 | 許可語以外の英語検出、95点未満で差し戻し。 | 固有名詞の英語残留、カタカナ過多、ルビ不足。 | 静的辞書＋形態素検査で自動修正し、LLMには残差TODOのみ渡す。 |
| 品質ゲート | WOW閾値と品質スコア抽出ロジック。【F:config.yaml†L132-L149】【F:app/script_quality.py†L192-L353】 | WOW<8.0や保持率不足で再生成／フォールバックに誘導。【F:app/services/script/generator.py†L151-L188】 | 再試行ループの多発、閾値直下の停滞。 | LLM出力に依存しないスコア計算（統計計測）と自動調整ノブ導入。 |
| トレーサビリティ | `LLMInteractionLogger` と `llm_logging_context` の多段活用。【F:app/llm_logging.py†L75-L154】【F:app/script_quality.py†L236-L334】 | JSONL永続化による再現ログ。 | ログ欠損、匿名化忘れ、セッション紐付け漏れ。 | 失敗シグナルの自動ダッシュボード化とサンプリング分析。 |

## ガードレール別の現状と破壊的改善案

### 1. 構造化出力
**現状の制御**
- LLMへのシステムメッセージとユーザープロンプトで「JSONのみ」出力を強制し、余分なテキストを拒否します。【F:app/services/script/generator.py†L123-L200】
- レスポンスは`_extract_json_block`で抽出し、Pydanticモデルでスキーマ検証後に品質レポートを再計算します。【F:app/services/script/generator.py†L202-L214】

**検出とフォールバック**
- JSON化に失敗した場合はテキストをスクリプトへ整形し、YAMLに直列化したうえで品質メタデータを付与します。【F:app/services/script/generator.py†L133-L150】
- それでも失敗すればバックアップ台本を生成し、最悪ケースでも構造化データを維持します。【F:app/services/script/generator.py†L181-L194】

**破壊的改善方針**
- JSON SchemaベースのテンプレートをJinjaで生成し、LLMには変動フィールドのみ埋めさせるワンショット穴埋め形式にする。
- `_build_prompt`で提示するスキーマ例を、実際のスキーマ定義ファイルに差し替えて単一ソース化する。
- `_parse_payload`の失敗内容を`LLMInteractionLogger`へ構造化フィールドで記録し、失敗傾向をダッシュボード化する。【F:app/llm_logging.py†L75-L154】

### 2. 会話フォーマットと話者管理
**現状の制御**
- プロンプトで話者ホワイトリストと24ターン以上の会話構成を指示しています。【F:app/services/script/generator.py†L196-L200】
- `ensure_dialogue_structure`が話者タグの正規化、最小行数、複数話者の存在を静的に検証します。【F:app/services/script/validator.py†L120-L210】

**検出とフォールバック**
- alias辞書で話者名を補正し、最小ライン数に満たない場合は自動生成で補填します。【F:app/services/script/validator.py†L150-L210】
- `StructuredScriptGenerator`はバリデーションエラー時に自動的にダイアログを補強します。【F:app/services/script/generator.py†L155-L167】

**破壊的改善方針**
- `_build_prompt`の会話制約を最小限に絞り、整形とチェックはすべて`ensure_dialogue_structure`＋専用フォーマッタに移管。
- 話者名辞書を`config.yaml`やCrew設定に連動させ、設定変更時に自動同期するユーティリティを追加。
- LLMに返すTODOは「不足した話者ターン数」「不自然な構成」のみを短いYAMLで提示する運用に統一。

### 3. 日本語純度と用語統制
**現状の制御**
- 品質レビューTask6/7が許可語彙リスト、英語禁止、カタカナ最小化、ルビ指示を詳細に定義し、95点以上を要求します。【F:app/config_prompts/prompts/quality_check.yaml†L212-L311】
- 最終稿生成ステージでも純日本語指示を強制し、改善事項を反映したうえで会話形式を維持させています。【F:app/script_quality.py†L288-L343】

**検出とフォールバック**
- 品質レビューで純度が未達の場合は差し戻し、再生成前に改善指示を抽出します。【F:app/script_quality.py†L250-L264】
- `config.yaml`が「入力より悪化させない」ポリシーを明示し、指標が低下した場合は自動で再試行します。【F:config.yaml†L132-L149】

**破壊的改善方針**
- 許可語・禁止語の辞書をコードで管理し、形態素解析器での静的チェック→自動置換をパイプライン化。
- `japanese_purity_check`出力から差分抽出し、LLMへは修正未完了箇所だけをYAML TODOで返す再試行フローを実装。
- 監視指標にルビ挿入率・カタカナ密度などの数値スコアを追加してLLM出力を定量監視。【F:app/config_prompts/prompts/quality_check.yaml†L232-L305】

### 4. WOWスコアと品質ゲート
**現状の制御**
- 品質タスクはWOWスコア算出式と8軸スコアを強制し、8.0未満は差し戻しとなります。【F:app/config_prompts/prompts/quality_check.yaml†L163-L207】
- `StructuredScriptGenerator`は品質ゲートが有効な場合にフォールバック稿の採用を遅延し、再試行にかけます。【F:app/services/script/generator.py†L151-L188】
- `ScriptQualityPipeline`が各ステージでログとスコア抽出を行い、失敗時は初稿のまま戻すなどのセーフティネットを備えます。【F:app/script_quality.py†L192-L353】

**破壊的改善方針**
- WOWスコアの計算をLLMレスに置き換える（例: 台詞解析→統計スコアリング）モジュールを追加し、閾値調整を自動化。
- 品質ゲート失敗時のログを`LLMInteractionLogger`へタグ付きで格納し、品質低下の因果分析を高速化。【F:app/llm_logging.py†L75-L154】
- 再試行上限に達した場合でも、未達要件を列挙したYAML TODOを生成して人間監視に回す仕組みを追加。

### 5. 出力トレーサビリティとログ
**現状の制御**
- `LLMInteractionLogger`はプロンプト・レスポンス・コンテキストをJSONLに保存し、スレッドローカルで追跡メタデータを管理します。【F:app/llm_logging.py†L75-L154】
- `llm_logging_context`がステージ情報を注入し、`record_llm_interaction`が例外時も運用停止させない設計です。【F:app/llm_logging.py†L94-L154】
- Script品質ステージは全呼び出しをログ経由で記録し、後段の分析や回帰テストに使える形で残します。【F:app/script_quality.py†L236-L334】

**破壊的改善方針**
- 失敗時の`last_error`やバリデータ出力をログに同梱し、BigQuery等へ流せるETLを整備。
- ログのサンプリングポリシーと匿名化ルールをドキュメント化し、ユーザーデータ保護と再現性を両立。
- ログから異常スパイクを検知したら自動でSlack/Discordに通知する観測ジョブを追加。

## 改善バックログ（常時更新）
| 優先度 | アクション | 説明 | オーナー/次の一手 |
| --- | --- | --- | --- |
| P0 | JSON Schema＋Jinjaテンプレートの導入 | スクリプト構造を静的定義し、LLMは穴埋めのみ。 `_build_prompt`のハードコードを除去。【F:app/services/script/generator.py†L196-L200】 | Schema設計: 🟦（未アサイン） / 次: 設計レビューをArchitecture WGで実施。 |
| P0 | 日本語純度自動補正パイプライン | 形態素解析でNG語を検出し、自動置換後の差分をLLMにTODOで返す。【F:app/config_prompts/prompts/quality_check.yaml†L232-L305】 | 実装: 🟥（要担当） / 次: `services/text_cleaning`モジュールを新設。 |
| P1 | 品質スコアの統計算出 | WOWスコアをLLMに依存せず算出する補助モジュールを追加。【F:app/script_quality.py†L250-L264】 | リサーチ: 🟩（進行中） / 次: サンプル台本10本で精度ベンチ。 |
| P1 | LLMログ分析ダッシュボード | JSONLを解析し、失敗パターンと再試行率を可視化。【F:app/llm_logging.py†L75-L154】 | DataOps: 🟨（相談中） / 次: BigQueryスキーマ草案を共有。 |
| P2 | 話者辞書の自動同期 | `ensure_dialogue_structure`のalias辞書を設定ファイルから生成。【F:app/services/script/validator.py†L150-L210】 | DevOps: ⬜️（未着手） / 次: `config/speakers.yaml`の追加を検討。 |

> **運用メモ**: バックログの列は各スプリントで見直し、完了したアイテムは履歴セクションへ移動すること。未割当タスクはレビューミーティングで必ずアサイン先を決め、破壊的改善のスピードを落とさないでください。

## 更新フロー
1. 新しいガードレールや失敗シグナルを追加したら、表とバックログに即反映し、AGENTS.mdに定めた3点（実装面・失敗面・次アクション）が揃っているか確認する。
2. プロンプトに制約を増やす前に、静的バリデーション・自動修正・ログ活用のいずれかで対処できないか検討する。
3. 変更内容を`LLMInteractionLogger`にタグ付けして記録し、効果測定のためのログクエリを追加する。

破壊的な改善は、静的化・自動化・可観測性の3軸を同時に進めることで実現できます。常に「LLMが失敗してもシステム全体で安全側に倒れるか」を問い続け、ドキュメントと実装を同期してください。
