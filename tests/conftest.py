"""Pytest共通設定とフィクスチャ

このファイルは全テストで共有される設定とフィクスチャを提供します。
"""

import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv


class _LiteLLMStub:
    """Minimal stub so tests don't require the litellm dependency."""

    @staticmethod
    def completion(*_args, **_kwargs):  # pragma: no cover - guardrail
        raise RuntimeError("litellm is not installed; stub completion invoked")


if "litellm" not in sys.modules:
    sys.modules["litellm"] = _LiteLLMStub()

if "crewai" not in sys.modules:
    crewai_module = ModuleType("crewai")
    llms_module = ModuleType("crewai.llms")
    base_llm_module = ModuleType("crewai.llms.base_llm")

    class _BaseLLMStub:  # pragma: no cover - guardrail
        pass

    base_llm_module.BaseLLM = _BaseLLMStub
    llms_module.base_llm = base_llm_module
    crewai_module.llms = llms_module

    sys.modules["crewai"] = crewai_module
    sys.modules["crewai.llms"] = llms_module
    sys.modules["crewai.llms.base_llm"] = base_llm_module

# ===== プロジェクト設定 =====

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .envファイル読み込み（secret/.envを優先）
env_path = PROJECT_ROOT / "secret" / ".env"
if not env_path.exists():
    env_path = PROJECT_ROOT / ".env"
load_dotenv(env_path)


# ===== Session-level Fixtures =====


@pytest.fixture(scope="session")
def project_root() -> Path:
    """プロジェクトルートディレクトリのパス"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """テストデータディレクトリ"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def has_gemini_key() -> bool:
    """Gemini APIキーが設定されているか確認"""
    key = os.getenv("GEMINI_API_KEY")
    return bool(key and "your-" not in key)


@pytest.fixture(scope="session")
def has_perplexity_key() -> bool:
    """Perplexity APIキーが設定されているか確認"""
    key = os.getenv("PERPLEXITY_API_KEY")
    return bool(key and "your-" not in key)


@pytest.fixture(scope="session")
def has_pixabay_key() -> bool:
    """Pixabay APIキーが設定されているか確認"""
    key = os.getenv("PIXABAY_API_KEY")
    return bool(key)


@pytest.fixture(scope="session")
def has_pexels_key() -> bool:
    """Pexels APIキーが設定されているか確認"""
    key = os.getenv("PEXELS_API_KEY")
    return bool(key)


@pytest.fixture(scope="session")
def has_newsapi_key() -> bool:
    """NewsAPI APIキーが設定されているか確認"""
    key = os.getenv("NEWSAPI_API_KEY")
    return bool(key and key != "your_newsapi_key")


# ===== Function-level Fixtures =====


@pytest.fixture
def sample_news_item() -> Dict[str, Any]:
    """サンプルニュースアイテム（単一）"""
    return {
        "title": "日経平均が年初来高値を更新",
        "url": "https://example.com/news1",
        "summary": "東京株式市場で日経平均株価が前日比2.1%上昇し、34,500円台で年初来高値を更新した。好調な企業決算と海外投資家の買いが支えとなった。",
        "key_points": ["年初来高値更新", "2.1%上昇", "好調な企業決算", "海外投資家の買い"],
        "source": "日本経済新聞",
        "impact_level": "high",
        "category": "金融",
    }


@pytest.fixture
def sample_news_items() -> List[Dict[str, Any]]:
    """サンプルニュースアイテム（複数）"""
    return [
        {
            "title": "日銀が政策金利を据え置き",
            "url": "https://example.com/news1",
            "summary": "日本銀行は金融政策決定会合で、政策金利を0.25%に据え置くことを決定した。",
            "key_points": ["政策金利据え置き", "0.25%維持", "市場予想通り"],
            "source": "日本経済新聞",
            "impact_level": "high",
            "category": "金融政策",
        },
        {
            "title": "新NISAが投資ブームを加速",
            "url": "https://example.com/news2",
            "summary": "2024年に始まった新NISA制度により、個人投資家の参入が急増しており、市場に活気をもたらしている。",
            "key_points": ["口座開設数200%増", "若年層の参加増", "長期積立人気"],
            "source": "ロイター",
            "impact_level": "medium",
            "category": "投資",
        },
        {
            "title": "AI関連株が市場を牽引",
            "url": "https://example.com/news3",
            "summary": "生成AIブームにより、AI関連企業の株価が急騰しており、市場全体の成長を牽引している。",
            "key_points": ["NVIDIA株価300%上昇", "日本AI銘柄も連動", "投資家関心集中"],
            "source": "Bloomberg",
            "impact_level": "high",
            "category": "テクノロジー",
        },
    ]


@pytest.fixture
def sample_script() -> str:
    """サンプル台本（対談形式）"""
    return """## オープニング

武宏: こんにちは。今回は日銀の金融政策について解説します。

つむぎ: よろしくお願いします。結論から教えてください。

武宏: 結論から言うと、日銀が政策金利を引き上げる可能性が高まっています。

つむぎ: え、それって私たちの生活にも影響があるってことですか？

武宏: その通りです。詳しく見ていきましょう。

## 本編

武宏: まず第一の要因として、インフレ率の上昇が挙げられます。

つむぎ: なるほど。具体的にどれくらい上昇しているんですか？

武宏: 前年比で2.5パーセントの上昇となっています。

つむぎ: それは結構大きな数字ですね。

武宏: そうなんです。日銀の目標である2パーセントを超えています。

## クロージング

武宏: 今回のポイントをまとめます。

つむぎ: ありがとうございました。次回もよろしくお願いします。
"""


@pytest.fixture
def sample_script_segments() -> List[Dict[str, str]]:
    """サンプル台本セグメント"""
    return [
        {"speaker": "武宏", "text": "今日は重要なニュースについて解説します。"},
        {"speaker": "つむぎ", "text": "よろしくお願いします。"},
        {"speaker": "武宏", "text": "まず第一のポイントは経済成長率です。"},
        {"speaker": "つむぎ", "text": "具体的にどれくらいですか？"},
        {"speaker": "武宏", "text": "前年比2.1パーセントの成長となっています。"},
    ]


@pytest.fixture
def temp_output_dir(tmp_path) -> Path:
    """一時出力ディレクトリ"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def temp_cache_dir(tmp_path) -> Path:
    """一時キャッシュディレクトリ"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


# ===== Mock Fixtures (基本的なモック) =====


@pytest.fixture
def mock_gemini_response():
    """Gemini APIのモックレスポンス"""
    return """
## オープニング

武宏: こんにちは。今回は経済ニュースについて解説します。

つむぎ: よろしくお願いします。

武宏: 今日の重要なポイントは3つあります。
"""


# ===== Pytest Hooks =====


def pytest_configure(config):
    """pytest設定時のカスタマイズ"""
    # カスタムマーカーの説明（pytest.iniと重複するが、動的に追加する場合はここで）
    pass


def pytest_collection_modifyitems(config, items):
    """テスト収集後の処理（自動スキップなど）"""
    # E2Eテストは明示的なフラグがない限りスキップ
    run_e2e = config.getoption("--run-e2e", default=False)

    for item in items:
        # E2Eテストの処理
        if "e2e" in item.keywords and not run_e2e:
            item.add_marker(pytest.mark.skip(reason="E2Eテストは --run-e2e フラグが必要"))

        # APIキー必須テストの処理
        if "requires_api_key" in item.keywords:
            # 必要なAPIキーが設定されているか確認
            # （実際の確認ロジックは各テストで実装）
            pass


def pytest_addoption(parser):
    """カスタムコマンドラインオプション追加"""
    parser.addoption(
        "--run-e2e", action="store_true", default=False, help="E2Eテストを実行する（実API呼び出しあり・課金注意）"
    )
    parser.addoption("--skip-slow", action="store_true", default=False, help="遅いテストをスキップする")


def pytest_report_header(config):
    """テスト実行前のヘッダー情報表示"""
    return [
        f"プロジェクトルート: {PROJECT_ROOT}",
        f"Python実行環境: {sys.executable}",
    ]
