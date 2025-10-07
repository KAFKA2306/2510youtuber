# コードレビュー所見（批判的レビュー）

## 1. Perplexityニュース収集が構成キーに強く依存しすぎており、実質的に無効化されている
- `app/search_news.py` のグローバル初期化は `cfg.perplexity_api_key` が設定されている場合にしか `NewsCollector` を作成しません。【F:app/search_news.py†L337-L346】
- ところが `NewsCollector` 自体は `PERPLEXITY_API_KEY_2` 以降の環境変数をサポートしており、キーローテーション前提の設計です。【F:app/search_news.py†L52-L109】
- `cfg.perplexity_api_key`（=設定ファイル内の `api_keys.perplexity`）が空でも、環境変数側にキーがセットされていることは十分にあり得ます。その場合でもグローバルは `None` なので、`collect_news` は強制的にフォールバックニュースを返してしまい、本番環境で常にダミーデータしか得られません。【F:app/search_news.py†L337-L346】
- 少なくとも lazy 初期化で `NewsCollector` を試行するか、ローテーションマネージャーにキーが1件でも登録されていれば API 呼び出しへ進むよう修正すべきです。

### 推奨対策（疎結合・テスト容易性）
- `NewsCollector` を生成するファクトリ関数を新設し、設定値と環境変数の両方からキーを集約する `KeyProvider` インターフェースを切り出します。これにより依存箇所は `KeyProvider` の抽象に依存し、ユニットテストではフェイク実装を差し替え可能です。
- グローバル状態ではなく、ステップ実行時にファクトリから `NewsCollector` を取得する設計へ変更し、`pytest` で `KeyProvider` の戻り値をモックしてキー探索の分岐をテストします。
- キー未設定時にフォールバックへ切り替わる挙動を `tests/unit/search_news/test_collector_factory.py` のようなファイルでカバレッジします。

## 2. ワークフローステップの例外処理が欠落し、1ステップの未捕捉例外で全体が異常終了する
- `YouTubeWorkflow.execute_full_workflow` のループでは各ステップを `await step.execute(...)` で呼び出していますが、例外を捕捉していません。【F:app/main.py†L106-L141】
- どこかのステップが `StepResult` を返す前に例外を送出すると、`_handle_workflow_failure` や `self._cleanup_temp_files()` が実行されず、ログ/Discord通知/リトライ処理が一切走らないままコルーチンが失敗します。
- 実際に各ステップは広範囲で `except Exception` を握り潰していますが、新規ステップや外部ライブラリの変更で例外が漏れると致命的です。最低限、`step.execute` 呼び出し自体を try/except で囲い、`_handle_workflow_failure` を通して失敗を一元処理する必要があります。

### 推奨対策（疎結合・テスト容易性）
- ステップを `WorkflowStep` 抽象でラップし、例外発生時には `WorkflowFailure` イベントを発行する `FailureBus` を導入します。`FailureBus` はサブスクライバ（通知、クリーンアップ）に依存性注入で渡すことで疎結合になります。
- `execute_full_workflow` は `try/except` 内で `FailureBus.notify()` を呼ぶのみとし、副作用はリスナーへ委譲することでテストではフェイクリスナーで検証可能です。
- ユニットテストで `MockStep` が例外を送出した際に `FailureBus` が通知したか、`_cleanup_temp_files` が呼ばれたかを `tests/unit/workflow/test_failure_bus.py` のようなモジュールで確認します。

## 3. Discord 通知は同期 HTTP 呼び出しのため、イベントループをブロックする
- `_notify_workflow_start` / `_notify_workflow_success` / `_notify_workflow_error` はすべて `discord_notifier.notify(...)` を直接呼びますが、`discord_notifier` は内部で `httpx.post` を同期で実行しています。【F:app/main.py†L440-L475】【F:app/discord.py†L47-L84】
- ワークフローは asyncio ベースなのに、各ステップ間で10秒タイムアウトの同期 HTTP を行うため、その間イベントループ全体がブロックされます。メディア生成など重い処理と平行してログ送信を行いたい場面でレスポンス遅延やタイムアウトを引き起こしかねません。
- 少なくとも `asyncio.to_thread` でオフロードするか、`httpx.AsyncClient` に置き換えて await するべきです。

### 推奨対策（疎結合・テスト容易性）
- `Notifier` プロトコルを定義し、Discord 実装と将来の Slack/メール実装を同一インターフェースで扱えるようにします。ワークフロー側は `Notifier` にのみ依存し、同期・非同期実装を DI で差し替え可能とします。
- HTTP 呼び出しは `httpx.AsyncClient` を使った非同期クライアントに置き換え、`AsyncNotifier` は `Notifier` プロトコルを実装した `Async` クラスとしてテストで `respx` などの HTTP モックを利用できるようにします。
- `tests/unit/notifications/test_async_notifier.py` を作成し、イベントループがブロックされないことを `asyncio` テストで検証します。

## 4. ffprobe の `r_frame_rate` が "N/A" の場合に QA ステップがクラッシュする
- `MediaQAPipeline._parse_fraction` は入力を無条件で `float(...)` に変換しており、`ffprobe` が "N/A" を返すケース（可変フレームレートなど）を考慮していません。【F:app/services/media/qa_pipeline.py†L401-L408】
- その結果 `ValueError` が発生し、`_run_video_checks` 全体が例外で終わるため、`QualityAssuranceStep` が失敗してワークフロー全体が停止します。`subprocess.CalledProcessError` などは捕捉しているのに、解析結果の欠損まではハンドリングしていないのは危険です。
- 想定外の値は 0fps 扱いにフォールバックする、あるいは `try/except ValueError` を追加してワーニングのみに留めるべきです。

### 推奨対策（疎結合・テスト容易性）
- `_parse_fraction` を純粋関数として切り出し、入力バリデーションを `FractionParser` のような小さなユーティリティに移します。これによりメディア QA 本体からロジックが分離され、ユニットテストしやすくなります。
- `OptionalFraction` 型（`typing.Protocol` でも可）で `N/A` のような非数値文字列も受け取り、`Result` オブジェクトでエラーと成功を表現することで、呼び出し側は例外ではなく戻り値で分岐可能になります。
- `tests/unit/media/test_fraction_parser.py` を追加し、`"30000/1001"` や `"N/A"` のケースを網羅して回帰テストを実施します。

## 5. 主要ステップが非同期 API なのにすべて同期 I/O を内部で呼び出している
- 代表例として `CollectNewsStep` は `collect_news` をそのまま呼びますが、内部で `httpx.Client` を同期利用しておりネットワーク I/O がイベントループをブロックします。【F:app/workflow/steps.py†L34-L69】【F:app/search_news.py†L100-L163】
- 同様に TTS や動画生成ステップも同期的な重処理を直接呼び出しており、`async` の表面 API でありながら本質的にブロッキングです。今後 UI や API から並列実行した場合にスループットが大幅に低下し、タイムアウトやデッドロックにつながる懸念があります。
- すくなくともネットワーク/ディスク I/O は `asyncio.to_thread` ないし専用の非同期クライアントで実装し直すことを推奨します。

### 推奨対策（疎結合・テスト容易性）
- I/O を伴う処理を `Port` / `Adapter` パターンで分離し、`CollectNewsPort` や `TTSPort` を抽象化します。ワークフローステップは `Port` の抽象メソッドを await するだけにし、実装は同期・非同期の差分を隠蔽します。
- 同期処理を残す場合も `asyncio.to_thread` をラップしたアダプタに封じ込めることで、ユニットテストではインメモリフェイクを注入し、非同期テストでも `pytest.mark.asyncio` で検証可能です。
- `tests/unit/workflow/test_collect_news_step.py` を追加し、`Port` のフェイクを注入してステップの状態遷移と戻り値を検証します。

## 6. QA リトライ時のコンテキストクリーンアップはファイルを削除してもアーカイブ先を考慮していない
- `GenerateVideoStep` では `FileArchivalManager` で生成物を `output/` にコピーした後、`result.files_generated` に元の一時ファイル（例: B-roll 含む）パスを入れています。【F:app/workflow/steps.py†L232-L324】
- `_cleanup_temp_files` は `context.generated_files` を無条件に削除するため、QA リトライ後に必要な中間生成物まで消えてしまう可能性があります。特に B-roll 生成を再利用する仕組みがなく、リトライごとに高コストな再生成が走る設計です。【F:app/main.py†L488-L500】
- アーカイブ後に参照するファイルと、再生成が安価なテンポラリを区別する仕組みを導入すべきです。

### 推奨対策（疎結合・テスト容易性）
- `GeneratedArtifact` エンティティを導入し、`persisted=True/False` などのメタデータを持たせることで、クリーンアップロジックはメタデータに従って削除可否を判断できます。`WorkflowContext` は単純なデータコンテナとし、削除ポリシーは `ArtifactRetentionPolicy` クラスへ委譲することで責務を分離します。
- `ArtifactRetentionPolicy` を `Strategy` パターンで差し替えられるようにし、テストでは `InMemoryFileSystem` を利用して削除対象を検証します。
- `tests/unit/workflow/test_artifact_retention_policy.py` を追加し、QA リトライ時にアーカイブ済みファイルが保持されることを保証します。

## 7. 例外時の Discord 通知がエラーオブジェクト文字列依存で詳細が欠落する
- `_handle_workflow_failure` は `result.error` が存在しない場合 `str(result)` を使いますが、未捕捉例外で `result` が `None` の場合 "None" という情報量ゼロのメッセージになります。【F:app/main.py†L195-L217】
- `traceback` や `exc_info` を Discord 通知へ含めないと、運用時に原因解析が困難です。

### 推奨対策（疎結合・テスト容易性）
- エラー通知生成を `FailureReportBuilder` として独立させ、`Exception` と `WorkflowContext` からサマリ・詳細・トレースバックを組み立てる責務を切り出します。通知システムは `Report` の抽象にのみ依存し、将来的な通知チャネル追加時にもロジックを再利用できます。
- 生成されたレポートは JSON などシリアライズ可能な形式にし、ユニットテストでトレースバックが含まれることをアサートします。
- `tests/unit/notifications/test_failure_report_builder.py` を追加し、例外が `None` の場合やメッセージのみの場合などをカバーします。

---

上記の問題は可用性・保守性に直接影響し、特に 1〜4 は即時修正を推奨します。
