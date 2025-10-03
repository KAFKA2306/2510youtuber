"""CrewAI エージェントとタスクの統合テスト"""

import pytest


@pytest.mark.integration
@pytest.mark.crewai
def test_agent_creation():
    """エージェントが正しく生成されるか確認"""
    from app.crew.agents import create_wow_agents

    agents = create_wow_agents()

    assert len(agents) > 0, "エージェントが作成されていません"

    # 期待されるエージェントの存在確認
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
        assert expected in agents, f"エージェント '{expected}' が見つかりません"
        assert agents[expected].role is not None, f"エージェント '{expected}' のroleが設定されていません"


@pytest.mark.integration
@pytest.mark.crewai
def test_task_creation(sample_news_items):
    """タスクが正しく生成されるか確認"""
    from app.crew.agents import create_wow_agents
    from app.crew.tasks import create_wow_tasks

    # エージェント生成
    agents = create_wow_agents()

    # タスク生成
    tasks = create_wow_tasks(agents, sample_news_items)

    assert len(tasks) > 0, "タスクが作成されていません"
    assert len(tasks) == 7, f"期待される7タスクではなく{len(tasks)}タスクが作成されました"


@pytest.mark.integration
@pytest.mark.crewai
def test_crew_initialization(sample_news_items):
    """Crewが正しく初期化されるか確認"""
    from app.crew.flows import WOWScriptFlow

    flow = WOWScriptFlow()
    flow.initialize(sample_news_items)

    assert len(flow.agents) > 0, "エージェントが初期化されていません"
    assert len(flow.tasks) > 0, "タスクが初期化されていません"
    assert len(flow.agents) == 7, f"エージェント数が期待値と異なります: {len(flow.agents)}"
    assert len(flow.tasks) == 7, f"タスク数が期待値と異なります: {len(flow.tasks)}"


@pytest.mark.integration
@pytest.mark.crewai
def test_agent_factory():
    """AgentFactoryが正しく動作するか確認"""
    from app.crew.agents import AgentFactory

    factory = AgentFactory()

    # Deep News Analyzer作成
    agent = factory.create_agent("deep_news_analyzer")

    assert agent is not None, "エージェントが作成されませんでした"
    assert agent.role is not None, "エージェントのroleが設定されていません"


@pytest.mark.integration
@pytest.mark.crewai
def test_multiple_agents_creation():
    """複数のエージェントが独立して作成されるか確認"""
    from app.crew.agents import AgentFactory

    factory = AgentFactory()

    agent1 = factory.create_agent("deep_news_analyzer")
    agent2 = factory.create_agent("script_writer")
    agent3 = factory.create_agent("japanese_purity_polisher")

    # すべて異なるエージェントであることを確認
    assert agent1 is not agent2
    assert agent2 is not agent3
    assert agent1.role != agent2.role
