"""Phase 1-A 基盤整備のテスト

データモデル、設定、AI Clientの動作確認
"""

import asyncio
from pprint import pprint


def test_data_models():
    """データモデルのテスト"""
    print("=" * 60)
    print("TEST 1: Data Models")
    print("=" * 60)

    from app.models import NewsItem, NewsCollection, Script, ScriptSegment, QualityScore, WOWMetrics

    # NewsItem作成
    news = NewsItem(
        title="日経平均が年初来高値を更新",
        url="https://example.com/news1",
        summary="東京株式市場で日経平均株価が前日比2.1%上昇し、年初来高値を更新した。好調な企業決算と海外投資家の買いが支えとなった。",
        key_points=["年初来高値更新", "2.1%上昇", "好調な企業決算"],
        source="日本経済新聞",
        impact_level="high",
        category="金融"
    )

    print(f"✓ NewsItem作成成功")
    print(f"  - Title: {news.title}")
    print(f"  - High Impact: {news.is_high_impact}")

    # NewsCollection作成
    collection = NewsCollection(
        items=[news],
        mode="test"
    )

    print(f"✓ NewsCollection作成成功")
    print(f"  - Mode: {collection.mode}")
    print(f"  - Count: {collection.total_count}")
    print(f"  - Has High Impact: {collection.has_high_impact}")

    # ScriptSegment作成
    segment = ScriptSegment(
        speaker="田中",
        text="今日の市場動向について解説します",
        visual_instruction="グラフ: 日経平均推移"
    )

    print(f"✓ ScriptSegment作成成功")
    print(f"  - Speaker: {segment.speaker}")
    print(f"  - Text: {segment.text}")
    print(f"  - Char Count: {segment.char_count}")

    # QualityScore作成
    score = QualityScore(
        wow_score=8.5,
        surprise_score=9.0,
        emotion_score=8.0,
        clarity_score=8.5,
        retention_prediction=54.0,
        japanese_purity=97.5
    )

    print(f"✓ QualityScore作成成功")
    print(f"  - WOW Score: {score.wow_score}")
    print(f"  - Is Passing: {score.is_passing()}")
    print(f"  - Is Excellent: {score.is_excellent}")

    print()
    return True


def test_config():
    """設定ファイルのテスト"""
    print("=" * 60)
    print("TEST 2: Configuration")
    print("=" * 60)

    from app.config import settings

    print(f"✓ 設定読み込み成功")
    print(f"  - Speakers: {len(settings.speakers)}")
    print(f"  - Video Resolution: {settings.video.resolution_tuple}")
    print(f"  - WOW Score Min: {settings.quality_thresholds.wow_score_min}")
    print(f"  - CrewAI Enabled: {settings.crew.enabled}")

    # 話者設定
    tanaka = settings.get_speaker_config("田中")
    if tanaka:
        print(f"  - 田中: {tanaka.role}")

    # エージェント設定
    agent_config = settings.get_agent_config("deep_news_analyzer")
    if agent_config:
        print(f"  - Deep News Analyzer Model: {agent_config.model}")
        print(f"  - Temperature: {agent_config.temperature}")

    print()
    return True


def test_prompt_manager():
    """プロンプトマネージャーのテスト"""
    print("=" * 60)
    print("TEST 3: Prompt Manager")
    print("=" * 60)

    from app.config.prompts import get_prompt_manager

    manager = get_prompt_manager()

    # agents.yamlの読み込み
    try:
        agents_data = manager.load("agents.yaml")
        print(f"✓ agents.yaml読み込み成功")
        print(f"  - Agents: {len(agents_data.get('agents', {}))}")

        # エージェント設定取得
        deep_analyzer_config = manager.get_agent_config("deep_news_analyzer")
        print(f"  - Deep News Analyzer Role: {deep_analyzer_config['role']}")

    except Exception as e:
        print(f"✗ agents.yaml読み込み失敗: {e}")
        return False

    # analysis.yamlの読み込み
    try:
        analysis_data = manager.load("analysis.yaml")
        print(f"✓ analysis.yaml読み込み成功")
        print(f"  - Tasks: {len(analysis_data.get('tasks', {}))}")
    except Exception as e:
        print(f"✗ analysis.yaml読み込み失敗: {e}")
        return False

    print()
    return True


def test_ai_clients():
    """AI Clientのテスト（API Key確認のみ）"""
    print("=" * 60)
    print("TEST 4: AI Clients")
    print("=" * 60)

    from app.config import settings

    # API Keyの存在確認
    gemini_key = settings.api_keys.get('gemini')
    perplexity_key = settings.api_keys.get('perplexity')

    if gemini_key:
        print(f"✓ Gemini API Key configured: {gemini_key[:10]}...")

        # GeminiClientのインスタンス化テスト
        try:
            from app.crew.tools import get_gemini_client
            client = get_gemini_client(temperature=0.7)
            print(f"  - GeminiClient instance created successfully")
            print(f"  - Model: {client.model_name}")
            print(f"  - Temperature: {client.temperature}")
        except Exception as e:
            print(f"✗ GeminiClient creation failed: {e}")
            return False
    else:
        print(f"⚠ Gemini API Key not found (skipping client test)")

    if perplexity_key:
        print(f"✓ Perplexity API Key configured: {perplexity_key[:10]}...")
        try:
            from app.crew.tools import get_perplexity_client
            client = get_perplexity_client()
            print(f"  - PerplexityClient instance created successfully")
            print(f"  - Model: {client.model}")
        except Exception as e:
            print(f"✗ PerplexityClient creation failed: {e}")
            return False
    else:
        print(f"⚠ Perplexity API Key not found (skipping client test)")

    print()
    return True


def main():
    """全テストを実行"""
    print("\n" + "=" * 60)
    print("Phase 1-A: 基盤整備 テストスイート")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Data Models
    try:
        results.append(("Data Models", test_data_models()))
    except Exception as e:
        print(f"✗ Data Models Test Failed: {e}\n")
        results.append(("Data Models", False))

    # Test 2: Configuration
    try:
        results.append(("Configuration", test_config()))
    except Exception as e:
        print(f"✗ Configuration Test Failed: {e}\n")
        results.append(("Configuration", False))

    # Test 3: Prompt Manager
    try:
        results.append(("Prompt Manager", test_prompt_manager()))
    except Exception as e:
        print(f"✗ Prompt Manager Test Failed: {e}\n")
        results.append(("Prompt Manager", False))

    # Test 4: AI Clients
    try:
        results.append(("AI Clients", test_ai_clients()))
    except Exception as e:
        print(f"✗ AI Clients Test Failed: {e}\n")
        results.append(("AI Clients", False))

    # 結果サマリー
    print("=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print(f"\n合格: {passed}/{total} ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 Phase 1-A 基盤整備: すべてのテストに合格しました！")
        return 0
    else:
        print("\n⚠️ 一部のテストが失敗しました。")
        return 1


if __name__ == "__main__":
    exit(main())
