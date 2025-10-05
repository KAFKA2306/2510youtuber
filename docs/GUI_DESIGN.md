# GUI詳細設計案

YouTube自動生成ワークフローを外部から安全に制御するためのGUI設計詳細。現行Pythonワークフローと疎結合を維持しつつ、コマンド実行・プロンプト管理・結果可視化を最小構成で実現する。

## 1. 設計指針

- **疎結合**: 既存ワークフロー (`app/main.py`, `scripts/tasks.py`) を改変せず、APIアダプタで実行する。
- **最小構成**: 初期リリースはジョブ実行とログ閲覧に集中し、段階的に機能追加。
- **観測可能性**: ステータス/ログ/成果物を統一フォーマットで収集、後続ダッシュボードへ流用可能にする。
- **拡張容易性**: 新コマンドやプロンプトをメタデータ登録だけでUIへ露出できる設定駆動型アーキテクチャとする。

## 2. コンポーネント分解

```
┌─────────────┐     WebSocket      ┌───────────────┐
│  Tauri Shell │◀──────────────────▶│ FastAPI / WS  │
│ (SvelteKit)  │     REST API       │  Job Service  │
└─────────────┘                     └──────┬────────┘
      ▲         ローカルIPC/FS               │
      │                                      ▼
┌─────────────┐                     ┌─────────────────┐
│ Prompt Store │◀──────────────┬────│ Worker Executors │
│ (SQLite+FS)  │                │    │  (asyncio)       │
└─────────────┘                │    └─────┬────────────┘
      ▲                        │          │
      │                        │          ▼
      │                        │   ┌──────────────┐
      │                        └──▶│ CLI Adapter   │─▶ 既存Pythonコマンド
      │                            └──────────────┘
      │
      └─▶ Prompt バージョン管理・エクスポート
```

### 2.0 ディレクトリ構成案

FastAPIバックエンドとTauriフロントをそれぞれ独立モジュールとして追加し、既存`app/`配下を侵さない。

```
├── app/
│   └── gui/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py              # 共通依存性 (DB Session, 設定)
│       │   ├── routes/
│       │   │   ├── jobs.py          # /jobs, /jobs/{id}, /jobs/{id}/logs
│       │   │   ├── commands.py      # /commands
│       │   │   ├── prompts.py       # /prompts, /prompts/{id}
│       │   │   └── settings.py      # /settings (GET/PUT)
│       │   └── schemas.py           # Pydanticモデル定義
│       ├── core/
│       │   ├── settings.py          # GUI専用設定 (ログ出力先, DBパス)
│       │   ├── logging.py           # JSONLロガー初期化
│       │   ├── events.py            # WebSocketブロードキャストハンドラ
│       │   └── preferences.py       # ユーザ設定の永続化・バリデーション
│       ├── jobs/
│       │   ├── manager.py           # JobManagerクラス (起動, 状態遷移)
│       │   ├── runners.py           # Python/CLI実行ロジック
│       │   └── registry.py          # commands.ymlローダー
│       └── prompts/
│           ├── repository.py        # SQLite + YAMLストア
│           └── models.py            # PromptVersion ORM/Pydantic
├── config/
│   └── gui/
│       ├── commands.yml             # UI表示コマンド一覧 (id, ラベル, パラメータ)
│       └── settings.yml             # デフォルト設定・オンオフ初期値
├── data/
│   └── prompts/
│       ├── live/                    # 現行プロンプト (YAML)
│       └── history/                 # バージョン履歴 (タイムスタンプ付き)
├── state/
│   └── gui/
│       └── preferences.json         # ユーザ設定の保存 (ラジオ選択結果)
├── logs/
│   └── gui_jobs/                    # ジョブごとのJSONLログ
└── tauri-app/
    ├── src/
    │   ├── main.ts                  # エントリポイント
    │   ├── lib/
    │   │   ├── apiClient.ts         # REST/WSクライアント
    │   │   ├── stores/
    │   │   │   ├── jobStore.ts      # ジョブ一覧状態
    │   │   │   ├── promptStore.ts   # プロンプト状態
    │   │   │   └── settingsStore.ts # 設定状態 (ラジオボタン選択)
    │   │   └── components/
    │   │       ├── JobLauncher.svelte
    │   │       ├── JobMonitor.svelte
    │   │       ├── PromptEditor.svelte
    │   │       └── PreferencesSummary.svelte
    │   └── routes/
    │       ├── jobs/+page.svelte
    │       ├── prompts/+page.svelte
    │       └── settings/+page.svelte
    ├── src-tauri/
    │   ├── Cargo.toml
    │   └── src/main.rs              # コマンド登録・ウィンドウ設定
    └── package.json
```

### 2.1 Job Service (FastAPI)
- `uvicorn` 常駐。RESTとWebSocket (ログ配信) を提供。
- `asyncio.create_task` によりジョブ実行をバックグラウンド化。
- `ContextVar` でジョブIDをログへ埋め込み、JSONLへ出力。
- `Depends(get_preferences)` で `GuiSettings` を取得し、ルータからJobManagerやRunnerへ渡す。

主要エントリポイント。

```python
# app/gui/api/main.py
from fastapi import FastAPI
from app.gui.api.routes import commands, jobs, prompts, settings

def create_app() -> FastAPI:
    app = FastAPI(title="Crew GUI API")
    app.include_router(commands.router, prefix="/commands", tags=["commands"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
    app.include_router(settings.router, prefix="/settings", tags=["settings"])
    return app
```

`app/gui/jobs/manager.py` はジョブ実行の状態管理を担う。

```python
class JobManager:
    async def enqueue(
        self,
        command_id: str,
        params: dict[str, Any],
        *,
        settings: GuiSettings,
    ) -> Job:
        """ジョブを登録し、バックグラウンドで実行タスクを起動する。"""

    async def get(self, job_id: UUID) -> Job:
        """ステータス・成果物情報を返す。"""

    async def stream_logs(self, job_id: UUID, settings: GuiSettings) -> AsyncIterator[LogEvent]:
        """JSONLファイルをtailしつつ、WebSocketへイベントを送出する。"""
```

APIルータ (`app/gui/api/routes/jobs.py`) は `Depends(get_job_manager)` でインスタンスを受け取り、REST/WS層を薄く保つ。

### 2.2 Worker Executors
- **Pythonコール**: `YouTubeWorkflow.execute_full_workflow()` を直接呼び出し、`WorkflowContext` をDI。
- **CLIサブプロセス**: `scripts/tasks.py` に定義済コマンドを `uv run` 経由で呼び出し。`asyncio.subprocess`でstdout/stderrを逐次読み取り。
- **ジョブ登録**: 実行対象と必要パラメータを `jobs.yml` に定義しUIに同期。
- **設定反映**: `execution.target` が `container` の場合はDocker CLIを呼ぶRunnerへ切替、`logging.verbose` が `enabled` のときは `--verbose` など追加引数を注入。

`app/gui/jobs/runners.py` で実行方式をStrategyパターンとして切り替える。

```python
class BaseRunner(Protocol):
    async def run(self, job: Job, params: dict[str, Any], settings: GuiSettings) -> int:
        ...

class PythonRunner:
    async def run(self, job: Job, params: dict[str, Any], settings: GuiSettings) -> int:
        workflow = YouTubeWorkflow()
        await workflow.execute_full_workflow(**params)
        return 0

class CliRunner:
    async def run(self, job: Job, params: dict[str, Any], settings: GuiSettings) -> int:
        cmd = ["uv", "run", "python3", "-m", params["module"], *params.get("args", [])]
        if settings.verbose_logging is Toggle.ENABLED:
            cmd.append("--verbose")
        process = await asyncio.create_subprocess_exec(*cmd)
        return await process.wait()
```

Runnerの割当は `commands.yml` の `runner` 属性 (`python` or `cli`) で制御し、`registry.py` が辞書へロードする。

`config/gui/commands.yml` 例:

```yaml
daily_workflow:
  label: "デイリー自動生成"
  description: "uv run python3 -m app.main daily"
  runner: "python"
  entrypoint: "app.main"
  kwargs:
    mode: "daily"
  params_schema:
    type: object
    properties:
      mode:
        type: string
        enum: ["daily", "backfill"]
    required: [mode]

verify_config:
  label: "設定チェック"
  description: "uv run python -m app.verify"
  runner: "cli"
  module: "app.verify"
  args: []
  params_schema:
    type: object
    properties: {}
```

### 2.3 Prompt Store
- SQLiteでメタデータ、実体はYAMLファイルを `app/config/prompts/` へ保存。
- 変更時は新しいバージョンを作成し、`prompts_history/` にスナップショットを残す。
- FastAPI経由でCRUD提供。ジョブ起動時に最新リビジョンを `WorkflowContext` に注入。

`app/gui/prompts/repository.py` はSQLModelベースで実装。

```python
class PromptRepository:
    def __init__(self, session_factory: Callable[[], Session], base_path: Path):
        self._session_factory = session_factory
        self._base_path = base_path

    def list_prompts(self) -> list[PromptSummary]:
        with self._session_factory() as session:
            return session.exec(select(Prompt)).all()

    def save_version(self, prompt_id: str, content: str, *, message: str, author: str) -> PromptVersion:
        version_path = self._write_file(prompt_id, content)
        # DBへINSERTし、最新バージョンを返却
```

APIレイヤーは `PromptRepository` を介し、直接ファイル操作を避ける。

### 2.4 Preferences Service
- `app/gui/core/preferences.py` が `settings.yml` と `preferences.json` をマージし、FastAPI依存性として提供。
- サーバ起動時にデフォルト値をロードし、ユーザ変更は都度JSONへ書き込み。ラジオボタンは `enabled`/`disabled` などの列挙値で保持。
- 設定変更イベントは `asyncio.Event` を通じてジョブマネージャへ通知し、必要に応じてランナーの挙動を切り替える (例: 詳細ログONでログレベル上げる)。

`config/gui/settings.yml` 例:

```yaml
log_streaming:
  mode: "enabled"      # enabled / disabled
artifact_handling:
  auto_open: "disabled"  # enabled / disabled
prompt_protection:
  edit_mode: "strict"   # strict / relaxed
notifications:
  desktop: "enabled"    # enabled / disabled
execution:
  target: "local"       # local / container
  container_profile: null
logging:
  verbose: "disabled"   # enabled / disabled
  retention_days: 7
concurrency:
  max_jobs: 2
```

- **log_streaming.mode**: WebSocket配信をON/OFF。OFF時はバックエンドがポーリングのみ行う。
- **artifact_handling.auto_open**: 完了時にFinder/Explorerを自動で開くか選択。
- **prompt_protection.edit_mode**: 本番プロンプト編集に承認を要求する「strict」と自由編集の「relaxed」。
- **notifications.desktop**: Tauriのデスクトップ通知を活用するかどうか。
- **execution.target**: コマンドをホストOSかDocker/コンテナに投げるか切り替え。
- **execution.container_profile**: `execution.target=container` 時に利用するDockerコンテナ名やComposeサービスID。
- **logging.verbose**: Runnerへ詳細ログを要求するフラグ。`verbose_logging` トグルとしてUIに露出。
- **logging.retention_days**: GUIで保持するジョブログの日数。
- **concurrency.max_jobs**: 同時実行ジョブの上限。

### 2.5 Tauri Shell
- Rustサイドは最小限：ウィンドウ管理、環境設定、セキュアなローカルAPI呼び出し。
- フロントはSvelteKit。IPC経由でFastAPIにアクセス。WebSocketでリアルタイムログを取得。
- `src/lib/stores/jobStore.ts` でSSE/WSステータス管理。

`src-tauri/src/main.rs` では最小のネイティブコマンドを登録。

```rust
#[tauri::command]
fn open_artifact(path: String) {
    tauri::api::shell::open(&app_handle.shell_scope(), path, None).unwrap();
}

#[tauri::command]
fn reload_commands() -> Result<(), String> {
    // FastAPIの /commands を再読込するトリガー
    Ok(())
}
```

Svelte側の `src/lib/apiClient.ts` は `fetchJson`・`postJson`・`connectJobStream(jobId: string)` を公開し、共通でトークン・Base URLを解決する。

## 3. API詳細

| HTTP Method | Path | 概要 | ペイロード例 |
|-------------|------|------|---------------|
| `POST` | `/jobs` | ジョブ開始 | `{ "command_id": "daily_workflow", "params": {"run_mode": "daily"} }` |
| `GET` | `/jobs/{job_id}` | ステータス確認 | 返却: `{ job_id, status, started_at, finished_at, artifacts[] }` |
| `GET` | `/jobs/{job_id}/logs?tail=200` | ログ取得 | 返却: 最新200行のJSONL | 
| `WS` | `/jobs/{job_id}/stream` | ログリアルタイム配信 | メッセージ: `{ level, ts, line, source }` |
| `GET` | `/commands` | UI用コマンドカタログ | 返却: `[{ id, label, description, params_schema }]` |
| `GET` | `/prompts` | プロンプト一覧 | 返却: `[{ id, latest_version, tags[] }]` |
| `POST` | `/prompts/{id}` | 新バージョン保存 | ペイロード: `{ content, message }` |
| `GET` | `/prompts/{id}/versions/{ver}` | バージョン取得 | YAML本文 |
| `GET` | `/settings` | 現在のユーザ設定取得 | 返却: `{ log_streaming: { mode }, ... }` |
| `PUT` | `/settings` | 設定更新 | ペイロード: `{ key: { value } }` |
| `POST` | `/artifacts/register` | 外部成果物追加 | `{ job_id, type, path, meta }` |

`/settings` はPUTで全設定を受け取り、ラジオボタンと数値入力を同時に永続化する。部分更新はサーバ側で既存値とマージ。

- 認証はローカル用途につき初期リリースで省略。将来 `app.verify` をラップする `/health` を追加予定。

## 4. データモデル

### 4.1 Job
```python
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(BaseModel):
    id: UUID
    command_id: str
    params: dict[str, Any]
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    artifacts: list[Artifact]
    prompt_snapshot_ids: list[str]
    runner: str  # "python" or "cli"
```

### 4.2 Artifact
```python
class ArtifactType(str, Enum):
    LOG = "log"
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text"
    METADATA = "metadata"

class Artifact(BaseModel):
    id: UUID
    job_id: UUID
    type: ArtifactType
    uri: str  # 相対パス or S3 URL
    label: str
    extra: dict[str, Any]
    created_at: datetime
```

### 4.3 PromptVersion
```python
class PromptVersion(BaseModel):
    id: UUID
    prompt_id: str
    version: int
    content_path: Path
    author: str
    message: str
    created_at: datetime
    tags: list[str]
    checksum: str  # SHA256 for integrity validation
```

### 4.4 GuiSettings
```python
class Toggle(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"

class ExecutionTarget(str, Enum):
    LOCAL = "local"
    CONTAINER = "container"

class PromptEditMode(str, Enum):
    STRICT = "strict"
    RELAXED = "relaxed"

class GuiSettings(BaseModel):
    log_streaming_mode: Toggle
    artifact_auto_open: Toggle
    desktop_notifications: Toggle
    execution_target: ExecutionTarget
    prompt_edit_mode: PromptEditMode
    verbose_logging: Toggle
    max_concurrent_jobs: PositiveInt
    log_retention_days: PositiveInt
    container_profile: str | None
```

設定は `/settings` API経由で取得/更新し、`preferences.json` と同期される。各値はUIのラジオボタンに対応する。
(`PositiveInt` はPydanticの制約型を利用)

## 5. ログ・監視

- 標準ログ: `logs/gui_jobs/{job_id}.jsonl` に保存。1行1イベント形式。
- WebSocket配信時は `tail -f` 相当で最新行をpush。
- 既存 `metadata_storage` との統合: ジョブ完了時にメタデータを記録するアダプタをコール。
- 監視エンドポイント: `/healthz` でワーカー状態とディスク残量を確認。
- `app/gui/core/logging.py` で `structlog` を初期化し、`LogEvent` スキーマ (`{job_id, level, message, source, timestamp}`) を統一。

## 6. UI詳細

### 6.1 画面構成
1. **ジョブラウンチャー**
   - コマンドカード (名称・説明・必要パラメータフォーム)
   - 実行ボタンで `/jobs` POST
2. **実行モニタ**
   - 左: ジョブ一覧 (ステータスバッジ、フィルタ)
   - 右: 選択ジョブのログターミナル (リアルタイムスクロール)
   - 成果物リスト (ダウンロード・Finderで開く)
3. **プロンプト管理**
   - テーブル (ID, タグ, 最新更新日)
   - エディタ (Monaco) + Markdownプレビュー
   - 差分表示 (バージョン比較)
4. **設定/診断**
   - APIパス設定、ログ保存先、`app.verify` 実行ボタン
   - 各種機能のオン/オフをラジオボタンで制御 (リアルタイムログ、成果物自動オープン、通知、詳細ログ、プロンプト保護モード、実行ターゲット)

### 6.2 状態管理
- Svelte stores (`writable`) でジョブ一覧と選択状態を共有。
- WebSocket接続は `onMount` で確立し、ジョブ切替時に再接続。
- ジョブカードは `/commands` レスポンスをキャッシュし、設定ファイル更新時に再読込。
- `src/lib/stores/jobStore.ts` では `loadJobs()` が `GET /jobs?limit=100` を叩き、`subscribeJob(jobId)` が `connectJobStream` を呼ぶ。
- プロンプト画面では `src/lib/stores/promptStore.ts` が `loadPrompt(promptId)` と `savePromptVersion(form)` を提供し、UIフォームと双方向バインド。
- 設定は `src/lib/stores/settingsStore.ts` が `/settings` を読み書きし、ラジオボタン・数値入力をまとめて管理。ジョブストアへイベントをDispatchし、`log_streaming_mode` 変更時にストリーム購読を更新。

### 6.3 バリデーション
- パラメータスキーマは `JSON Schema` として `/commands` に含め、UI側でフォーム自動生成。
- 実行前に`prompt` が存在するかFastAPIで検証し、エラー時はトースト表示。

### 6.4 設定ラジオボタンUI
- `settings/+page.svelte` に6つのラジオボタングループを配置し、各グループは `writable` ストアを介して `GuiSettings` とバインド。
- ラジオ構成: `log_streaming_mode`、`artifact_auto_open`、`desktop_notifications`、`verbose_logging`、`prompt_edit_mode`、`execution_target`。
- 選択変更で即時に `/settings` へ `PUT` し、成功時にトースト表示。失敗時はラジオを元の状態にロールバック。
- 設定変更は `JobMonitor` にも伝搬し、例としてリアルタイムログOFF時はWebSocket接続を閉じ、ポーリングに切替。
- `PreferencesSummary.svelte` コンポーネントで現在値を一覧表示し、オン/オフ状態を色付きバッジで可視化。
- ラジオの下に数値/テキスト入力 (最大同時ジョブ数、ログ保持日数、コンテナプロファイル) を配置し、保存ボタンでまとめて送信。

## 7. 非機能要件

| 項目 | 内容 |
|------|------|
| パフォーマンス | 同時ジョブ5件を上限。ログ配信レイテンシ < 500ms。 |
| 信頼性 | FastAPI側でジョブキューの永続化は行わず、クラッシュ時は再実行で回復。 |
| セキュリティ | ローカル専用。将来的にAPI Token導入を検討。 |
| テスト | FastAPIエンドポイントは`pytest` + `httpx.AsyncClient`で単体・統合テスト。UIはPlaywrightでE2E。 |

## 8. ロードマップ

1. **Phase 0: 骨組み**
   - FastAPIスケルトン、`/commands` ハードコードレスポンス、モックジョブ実行。
   - Tauriプロジェクト作成、REST接続確認。
2. **Phase 1: 実ジョブ実行**
   - CLIサブプロセスアダプタ実装 (`uv run python3 -m app.main daily` など)。
   - ログJSONL整備、WebSocketストリーム実装。
3. **Phase 2: プロンプト管理**
   - SQLiteメタデータ、YAMLスナップショット保存。
   - 差分表示・タグ管理導入。
4. **Phase 3: 成果物ダッシュボード**
   - `app/gui/dashboard/service.py` で `output/execution_log.jsonl` と `data/metadata_history.csv` を集約し、`RunArtifacts`・`RunMetrics` を構築。
   - FastAPIに `/dashboard/artifacts`（成果物カード）と `/dashboard/metrics`（QAメトリクス）ルートを追加し、外部ビューアURL・音声/テキストファイルを含むJSONを返却。
   - 平均WOWスコア・視聴数などを `DashboardSummary` に集計し、GUIのカード/グラフ表示へ供給。
5. **Phase 4: 配布と運用**
   - Tauriビルド (macOS/Windows/Linux)。
   - 自動更新チャネル、Crashログ収集、将来の多ユーザ対応検討。

## 9. リスクと対策

| リスク | 対策 |
|--------|------|
| 長時間ジョブでTauriがフリーズ | バックエンドで処理、UIはWebSocket受信のみで非同期化。 |
| CLIコマンドの仕様変更 | `/commands` を設定ファイルベースにし、UIを再ビルドせず更新可能にする。 |
| ログ肥大化 | 一定サイズでローテーション、古いログは圧縮。 |
| プロンプト編集ミス | 自動バージョン管理と差分プレビューで回復容易にする。 |

## 10. 今後の検討事項

- APIキーなど秘密情報のUI編集可否 (現状CLIのみ)。
- Gradioによる軽量モードの併設 (FastAPIバックエンド共有)。
- CrewAIエージェントのステート可視化 (トレーシング連携)。
- LLMプロンプトの自動検証 (Lintルール/テストケース)。

