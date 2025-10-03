# テストスイート

このディレクトリには、YouTuberプロジェクトのテストスイートが含まれています。

## 📁 ディレクトリ構造

```
tests/
├── conftest.py              # Pytest共通設定・フィクスチャ
├── pytest.ini               # Pytest設定ファイル（プロジェクトルートに配置）
│
├── unit/                    # ユニットテスト（高速・外部依存なし）
│   ├── test_models.py       # データモデル
│   ├── test_config.py       # 設定ファイル
│   └── test_script_parser.py # スクリプト解析
│
├── integration/             # 統合テスト（モック使用）
│   └── test_crewai_agents.py # CrewAI エージェント・タスク
│
├── e2e/                     # E2Eテスト（実API使用・遅い）
│   └── (今後追加予定)
│
├── api/                     # API安定性テスト
│   ├── test_api_rotation.py  # APIキーローテーション
│   ├── test_pixabay.py       # Pixabay API
│   └── test_prompt_cache.py  # プロンプトキャッシュ
│
├── fixtures/                # テストデータ・フィクスチャ
│   └── sample_news.json     # サンプルニュースデータ
│
└── helpers/                 # テストヘルパー・ユーティリティ
    └── (今後追加予定)
```

## 🚀 テスト実行方法

### 全テスト実行

```bash
# すべてのテストを実行
pytest

# 詳細表示
pytest -v

# 並列実行（高速化）
pytest -n auto
```

### カテゴリ別実行

```bash
# ユニットテストのみ
pytest tests/unit -v

# 統合テストのみ
pytest tests/integration -v

# APIテストのみ
pytest tests/api -v

# E2Eテストのみ（実API呼び出しあり）
pytest tests/e2e --run-e2e -v
```

### マーカー指定実行

```bash
# ユニットテストマーカー
pytest -m unit

# CrewAI関連テストのみ
pytest -m crewai

# 遅いテストをスキップ
pytest -m "not slow"

# APIキー必須テストのみ
pytest -m requires_api_key
```

### カバレッジ測定

```bash
# カバレッジ付きテスト実行
pytest --cov=app --cov-report=html

# カバレッジレポートをブラウザで確認
open htmlcov/index.html
```

## 🏷️ テストマーカー

| マーカー | 説明 |
|---------|------|
| `unit` | ユニットテスト（高速・外部依存なし） |
| `integration` | 統合テスト（モック使用） |
| `e2e` | E2Eテスト（実API使用・遅い・課金発生） |
| `api` | API安定性テスト（実API使用） |
| `slow` | 実行に時間がかかるテスト（1分以上） |
| `requires_api_key` | APIキー必須のテスト |
| `crewai` | CrewAI関連テスト |
| `stock_footage` | ストックフッテージ関連テスト |
| `youtube` | YouTube関連テスト |

## 📝 テスト作成ガイドライン

### 1. ユニットテスト (`tests/unit/`)

- **目的**: 個々の関数・クラスの動作確認
- **実行時間**: < 1秒/テスト
- **外部依存**: なし（モックを使用）
- **マーカー**: `@pytest.mark.unit`

**例:**
```python
@pytest.mark.unit
def test_news_item_creation(sample_news_item):
    """NewsItemが正しく作成できるか確認"""
    from app.models import NewsItem

    news = NewsItem(**sample_news_item)
    assert news.title == sample_news_item["title"]
```

### 2. 統合テスト (`tests/integration/`)

- **目的**: 複数のコンポーネント間の連携確認
- **実行時間**: < 10秒/テスト
- **外部依存**: モックで代替
- **マーカー**: `@pytest.mark.integration`

**例:**
```python
@pytest.mark.integration
@pytest.mark.crewai
def test_agent_creation():
    """エージェントが正しく生成されるか確認"""
    from app.crew.agents import create_wow_agents

    agents = create_wow_agents()
    assert len(agents) == 7
```

### 3. E2Eテスト (`tests/e2e/`)

- **目的**: 実際のワークフロー全体の動作確認
- **実行時間**: 制限なし
- **外部依存**: 実APIを使用（課金発生）
- **マーカー**: `@pytest.mark.e2e`

**実行には `--run-e2e` フラグが必要:**
```bash
pytest tests/e2e --run-e2e -v
```

### 4. APIテスト (`tests/api/`)

- **目的**: 外部API統合の動作確認
- **実行時間**: 制限なし
- **外部依存**: 実APIを使用
- **マーカー**: `@pytest.mark.api`, `@pytest.mark.requires_api_key`

**例:**
```python
@pytest.mark.api
@pytest.mark.requires_api_key
def test_pixabay_api_key_loaded(has_pixabay_key):
    """Pixabay APIキーが読み込まれているか確認"""
    if not has_pixabay_key:
        pytest.skip("Pixabay APIキーが設定されていません")
    # テストロジック
```

## 🔧 共通フィクスチャ

`conftest.py` で定義されている共通フィクスチャ:

| フィクスチャ | 説明 |
|------------|------|
| `project_root` | プロジェクトルートパス |
| `test_data_dir` | テストデータディレクトリ |
| `sample_news_item` | サンプルニュースアイテム（単一） |
| `sample_news_items` | サンプルニュースアイテム（複数） |
| `sample_script` | サンプル台本（対談形式） |
| `sample_script_segments` | サンプル台本セグメント |
| `temp_output_dir` | 一時出力ディレクトリ |
| `temp_cache_dir` | 一時キャッシュディレクトリ |
| `has_gemini_key` | Gemini APIキーの存在確認 |
| `has_pixabay_key` | Pixabay APIキーの存在確認 |

## 📊 カバレッジ目標

- **全体**: 80%以上
- **ユニットテスト**: 90%以上
- **統合テスト**: 70%以上

## 🔄 CI/CD統合

### GitHub Actions（今後追加予定）

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/unit tests/integration -v --cov=app
```

## 🐛 トラブルシューティング

### APIキーが見つからない

```bash
# .envファイルを確認
cat secret/.env

# APIキーが設定されているか確認
pytest tests/api -v --tb=short
```

### テストが遅い

```bash
# 遅いテストをスキップ
pytest -m "not slow" -v

# 並列実行で高速化
pytest -n auto
```

### E2Eテストが実行されない

E2Eテストは明示的なフラグが必要です:

```bash
pytest tests/e2e --run-e2e -v
```

## 📚 参考資料

- [Pytest公式ドキュメント](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)

## 🎯 次のステップ

1. **E2Eテストの追加** - 実際のワークフロー全体をテスト
2. **モッククライアントの実装** - `tests/helpers/mock_clients.py`
3. **CI/CD統合** - GitHub Actionsで自動テスト
4. **カバレッジ80%達成** - 未カバー領域のテスト追加
