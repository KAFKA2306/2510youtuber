"""CrewAI基本動作テスト

エージェントとタスクの生成を確認
"""

import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_agent_creation():
    """エージェント生成テスト"""
    print("=" * 60)
    print("TEST 1: Agent Creation")
    print("=" * 60)

    try:
        from app.crew.agents import create_wow_agents

        agents = create_wow_agents()

        print(f"✓ Created {len(agents)} agents")
        for name, agent in agents.items():
            print(f"  - {name}: {agent.role}")

        # 期待される7エージェントが全て作成されたか
        expected_agents = [
            "deep_news_analyzer",
            "curiosity_gap_researcher",
            "emotional_story_architect",
            "script_writer",
            "engagement_optimizer",
            "quality_guardian",
            "japanese_purity_polisher",
        ]

        for expected in expected_agents:
            if expected not in agents:
                print(f"✗ Missing agent: {expected}")
                return False

        print("✓ All 7 required agents created successfully")
        return True

    except Exception as e:
        print(f"✗ Agent creation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_task_creation():
    """タスク生成テスト"""
    print("\n" + "=" * 60)
    print("TEST 2: Task Creation")
    print("=" * 60)

    try:
        from app.crew.agents import create_wow_agents
        from app.crew.tasks import create_wow_tasks

        # エージェント生成
        agents = create_wow_agents()

        # テスト用ニュースデータ
        test_news = [
            {
                "title": "日経平均が年初来高値を更新",
                "summary": "東京株式市場で日経平均株価が前日比2.1%上昇し、年初来高値を更新した。",
                "source": "日本経済新聞",
                "impact_level": "high",
                "category": "金融",
                "key_points": ["年初来高値更新", "2.1%上昇", "好調な企業決算"],
            },
            {
                "title": "円相場が急騰、1ドル140円台に",
                "summary": "外国為替市場で円相場が急騰し、約3ヶ月ぶりに1ドル140円台をつけた。",
                "source": "ロイター",
                "impact_level": "medium",
                "category": "為替",
                "key_points": ["円急騰", "140円台", "3ヶ月ぶり"],
            },
        ]

        # タスク生成
        tasks = create_wow_tasks(agents, test_news)

        print(f"✓ Created {len(tasks)} tasks")
        for name, task in tasks.items():
            print(f"  - {name}")

        # 期待される7タスクが全て作成されたか
        expected_count = 7
        if len(tasks) != expected_count:
            print(f"✗ Expected {expected_count} tasks, got {len(tasks)}")
            return False

        print(f"✓ All {expected_count} tasks created successfully")
        return True

    except Exception as e:
        print(f"✗ Task creation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_crew_initialization():
    """Crew初期化テスト"""
    print("\n" + "=" * 60)
    print("TEST 3: Crew Initialization")
    print("=" * 60)

    try:
        from app.crew.flows import WOWScriptFlow

        flow = WOWScriptFlow()

        # テスト用ニュースデータ
        test_news = [
            {
                "title": "日銀が政策金利を据え置き",
                "summary": "日本銀行は金融政策決定会合で、政策金利の据え置きを決定した。",
                "source": "日本経済新聞",
                "impact_level": "high",
                "category": "金融政策",
            }
        ]

        # 初期化
        flow.initialize(test_news)

        print("✓ Flow initialized successfully")
        print(f"  - Agents: {len(flow.agents)}")
        print(f"  - Tasks: {len(flow.tasks)}")

        if len(flow.agents) == 7 and len(flow.tasks) == 7:
            print("✓ Flow ready for execution")
            return True
        else:
            print("✗ Unexpected agent/task count")
            return False

    except Exception as e:
        print(f"✗ Crew initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """全テストを実行"""
    print("\n" + "=" * 60)
    print("CrewAI 基本動作テストスイート")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Agent Creation
    results.append(("Agent Creation", test_agent_creation()))

    # Test 2: Task Creation
    results.append(("Task Creation", test_task_creation()))

    # Test 3: Crew Initialization
    results.append(("Crew Initialization", test_crew_initialization()))

    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print(f"\n合格: {passed}/{total} ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 CrewAI基本動作テスト: すべて合格！")
        print("✅ WOW Script Creation Crewの準備が整いました")
        return 0
    else:
        print("\n⚠️ 一部のテストが失敗しました。")
        return 1


if __name__ == "__main__":
    exit(main())
