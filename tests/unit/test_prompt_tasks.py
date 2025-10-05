import sys
import types

crewai_stub = types.ModuleType("crewai")
crewai_stub.Agent = type("Agent", (), {})
crewai_stub.Task = type("Task", (), {})
sys.modules["crewai"] = crewai_stub

from app.config_prompts.settings import settings
from app.crew.tasks import TaskFactory, create_wow_tasks


class _DummyCrewTask:
    """Lightweight stand-in for CrewAI Task during unit tests."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.description = kwargs.get("description", "")
        self.expected_output = kwargs.get("expected_output", "")
        self.context = kwargs.get("context", [])
        self.agent = kwargs.get("agent")


def test_prompt_manager_task_definitions_exist():
    pm = settings.prompt_manager

    script_task = pm.get_task_definition("script_generation", "script_writing")
    assert "対談形式の台本" in script_task.get("description", "")

    engagement_task = pm.get_task_definition("quality_check", "engagement_optimization")
    assert "エンゲージメント施策" in engagement_task.get("description", "")

    quality_task = pm.get_task_definition("quality_check", "quality_evaluation")
    assert "WOWスコア" in quality_task.get("description", "")

    japanese_task = pm.get_task_definition("quality_check", "japanese_purity_check")
    assert "日本語純度" in japanese_task.get("description", "")


def test_task_factory_renders_agent_specific_prompts(monkeypatch):
    monkeypatch.setattr("app.crew.tasks.Task", _DummyCrewTask)

    factory = TaskFactory()

    script_task = factory.create_task(
        task_name="script_generation",
        agent=object(),
        context_data={
            "surprise_points": "SURPRISE JSON",
            "curiosity_gaps": "GAP JSON",
            "story_arc": "STORY JSON",
            "continuity_prompt": "",
            "agent_improvement_notes": "",
        },
        prompt_task="script_writing",
        expected_output="Pydantic Scriptモデルに準拠したJSON形式の動画スクリプト",
        output_pydantic=object(),
    )

    assert "SURPRISE JSON" in script_task.description
    assert script_task.expected_output == "Pydantic Scriptモデルに準拠したJSON形式の動画スクリプト"

    engagement_task = factory.create_task(
        task_name="quality_check",
        agent=object(),
        context_data={
            "first_draft_script": "DRAFT",
            "continuity_prompt": "",
            "agent_improvement_notes": "",
        },
        prompt_task="engagement_optimization",
    )

    assert "エンゲージメント施策" in engagement_task.description
    assert "DRAFT" in engagement_task.description
    assert "エンゲージメント施策を組み込んだ対談スクリプト" in engagement_task.expected_output

    quality_task = factory.create_task(
        task_name="quality_check",
        agent=object(),
        context_data={
            "optimized_script": "OPTIMIZED",
            "continuity_prompt": "",
            "agent_improvement_notes": "",
        },
        prompt_task="quality_evaluation",
    )

    assert "WOWスコア" in quality_task.description

    japanese_task = factory.create_task(
        task_name="quality_check",
        agent=object(),
        context_data={
            "quality_approved_script": "OPT SCRIPT",
            "quality_evaluation_result": "EVAL JSON",
            "continuity_prompt": "",
            "agent_improvement_notes": "",
        },
        prompt_task="japanese_purity_check",
    )

    assert "OPT SCRIPT" in japanese_task.description
    assert "EVAL JSON" in japanese_task.description


def test_japanese_polisher_receives_optimized_script(monkeypatch):
    captured_calls = {}

    def fake_create_task(self, *args, **kwargs):  # noqa: D401
        task_id = kwargs.get("task_id")
        if task_id:
            captured_calls[task_id] = kwargs
        return types.SimpleNamespace()

    monkeypatch.setattr(TaskFactory, "create_task", fake_create_task, raising=False)

    agents = {name: object() for name in [
        "deep_news_analyzer",
        "curiosity_gap_researcher",
        "emotional_story_architect",
        "script_writer",
        "engagement_optimizer",
        "quality_guardian",
        "japanese_purity_polisher",
    ]}

    news_items = [
        {
            "title": "テストニュース",
            "summary": "要約",
            "source": "テスト",
            "impact_level": "medium",
        }
    ]

    create_wow_tasks(agents=agents, news_items=news_items)

    assert captured_calls["task5_engagement"]["prompt_task"] == "engagement_optimization"
    assert captured_calls["task6_quality"]["prompt_task"] == "quality_evaluation"
    assert captured_calls["task7_japanese"]["prompt_task"] == "japanese_purity_check"
    assert (
        captured_calls["task7_japanese"]["context_data"]["quality_approved_script"]
        == "{{ task5_engagement.output }}"
    )
