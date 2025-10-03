"""E2Eテスト: 台本生成の完全フロー

実際のニュースデータを使って、CrewAIで台本を生成するテスト
注意: このテストはAPI呼び出しを行うため、料金が発生します
"""

import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


def test_simple_script_generation():
    """シンプルな台本生成テスト（1エージェントのみ）"""
    print("=" * 60)
    print("TEST: Simple Script Generation (Agent 1 only)")
    print("=" * 60)

    try:
        from app.crew.agents import AgentFactory
        from app.crew.tools import get_gemini_client

        # テスト用ニュース
        test_news = {
            "title": "日経平均が年初来高値を更新",
            "summary": "東京株式市場で日経平均株価が前日比2.1%上昇し、34,500円台で年初来高値を更新した。好調な企業決算と海外投資家の買いが支えとなった。",
            "source": "日本経済新聞",
            "impact_level": "high",
            "category": "金融",
            "key_points": ["年初来高値更新", "2.1%上昇", "好調な企業決算", "海外投資家の買い"]
        }

        news_summary = f"""
■ ニュース: {test_news['title']}
  出典: {test_news['source']}
  要約: {test_news['summary']}
  重要ポイント: {', '.join(test_news['key_points'])}
  影響度: {test_news['impact_level']}
"""

        # Agent 1のみテスト（Deep News Analyzer）
        factory = AgentFactory()

        print("\n1. Creating Deep News Analyzer agent...")
        agent = factory.create_agent("deep_news_analyzer")
        print(f"✓ Agent created: {agent.role}")

        print("\n2. Creating simple analysis task...")
        simple_prompt = f"""
以下のニュースを分析し、視聴者が驚く3つのポイントを抽出してください。

{news_summary}

【出力形式】
1. 驚きポイント1: [説明]
2. 驚きポイント2: [説明]
3. 驚きポイント3: [説明]

簡潔に、各ポイント50文字以内で記述してください。
"""

        # Gemini Clientで直接呼び出し（CrewAIを使わずテスト）
        print("\n3. Calling Gemini API...")
        client = get_gemini_client(temperature=0.7)

        result = client.generate(simple_prompt, max_tokens=1024)

        print("\n" + "=" * 60)
        print("分析結果:")
        print("=" * 60)
        print(result)
        print("=" * 60)

        if len(result) > 100:
            print("\n✓ Analysis successful!")
            return True
        else:
            print("\n✗ Analysis result too short")
            return False

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_minimal_crew_execution():
    """最小構成でのCrew実行テスト（3エージェント）"""
    print("\n" + "=" * 60)
    print("TEST: Minimal Crew Execution (3 agents)")
    print("=" * 60)
    print("⚠️ このテストはAPI料金が発生します")
    print("⚠️ 実行を続けますか? (yes/no): ", end="")

    # ユーザー確認をスキップ（自動実行のため）
    # response = input().strip().lower()
    # if response != 'yes':
    #     print("テストをスキップしました")
    #     return None

    print("yes (auto)")
    print()

    try:
        from crewai import Crew, Process, Task

        from app.crew.agents import AgentFactory

        # テスト用ニュース
        test_news = [
            {
                "title": "日銀が政策金利を据え置き",
                "summary": "日本銀行は金融政策決定会合で、政策金利を0.25%に据え置くことを決定した。市場予想通りの結果となった。",
                "source": "日本経済新聞",
                "impact_level": "medium"
            }
        ]

        news_summary = "\n".join([
            f"■ {i+1}. {item['title']}\n"
            f"   出典: {item['source']}\n"
            f"   要約: {item['summary']}"
            for i, item in enumerate(test_news)
        ])

        print("1. Creating 3 agents...")
        factory = AgentFactory()

        agent1 = factory.create_agent("deep_news_analyzer")
        agent2 = factory.create_agent("script_writer")
        agent3 = factory.create_agent("japanese_purity_polisher")

        print("✓ Created agents:")
        print(f"  - {agent1.role}")
        print(f"  - {agent2.role}")
        print(f"  - {agent3.role}")

        print("\n2. Creating simplified tasks...")

        # Task 1: 分析
        task1 = Task(
            description=f"""
以下のニュースを分析し、驚きポイントを3つ抽出してください。

{news_summary}

各ポイント50文字以内で簡潔に。
""",
            expected_output="驚きポイント3つのリスト",
            agent=agent1
        )

        # Task 2: 短い台本作成（2分）
        task2 = Task(
            description="""
以下の分析結果をもとに、2分程度の短い対談台本を作成してください。

話者: 田中、鈴木
形式:
田中: [発話]
鈴木: [発話]

600文字程度で簡潔に。
""",
            expected_output="対談形式の台本（600文字）",
            agent=agent2,
            context=[task1]
        )

        # Task 3: 日本語チェック
        task3 = Task(
            description="""
台本の日本語をチェックし、英語が混じっていれば修正してください。
純粋な日本語にしてください。
""",
            expected_output="日本語純度100%の台本",
            agent=agent3,
            context=[task2]
        )

        print("✓ Tasks created")

        print("\n3. Creating Crew...")
        crew = Crew(
            agents=[agent1, agent2, agent3],
            tasks=[task1, task2, task3],
            process=Process.sequential,
            verbose=True
        )

        print("✓ Crew created")

        print("\n4. Executing Crew (this may take 1-2 minutes)...")
        print("=" * 60)

        result = crew.kickoff()

        print("=" * 60)
        print("\n✓ Crew execution completed!")

        print("\n" + "=" * 60)
        print("最終台本:")
        print("=" * 60)
        print(str(result))
        print("=" * 60)

        # 結果をファイルに保存
        output_file = "test_output_minimal_crew.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=== Minimal Crew Execution Result ===\n\n")
            f.write(str(result))

        print(f"\n✓ 結果を {output_file} に保存しました")

        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """テスト実行"""
    print("\n" + "=" * 60)
    print("E2E台本生成テストスイート")
    print("=" * 60)
    print()

    results = []

    # Test 1: Simple API call
    print("【Test 1】シンプルなAPI呼び出しテスト（料金: 小）")
    results.append(("Simple API Call", test_simple_script_generation()))

    # Test 2: Minimal Crew (オプション)
    print("\n【Test 2】最小構成Crew実行テスト（料金: 中）")
    print("このテストをスキップしますか? (skip/run): ", end="")

    # 自動実行のためスキップ
    skip_crew = True  # input().strip().lower() == 'skip'
    print("skip (auto)")

    if skip_crew:
        print("⚠️ Crew実行テストをスキップしました")
        results.append(("Minimal Crew Execution", None))
    else:
        results.append(("Minimal Crew Execution", test_minimal_crew_execution()))

    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)

    for name, result in results:
        if result is None:
            status = "⊘ SKIP"
        elif result:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        print(f"{status} - {name}")

    passed = sum(1 for _, result in results if result is True)
    total = sum(1 for _, result in results if result is not None)

    if total > 0:
        print(f"\n合格: {passed}/{total}")

    return 0


if __name__ == "__main__":
    exit(main())
