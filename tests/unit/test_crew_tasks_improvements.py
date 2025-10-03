from types import SimpleNamespace

from app.crew import tasks as crew_tasks


def _fake_agents():
    return {
        "deep_news_analyzer": object(),
        "curiosity_gap_researcher": object(),
        "emotional_story_architect": object(),
        "script_writer": object(),
        "engagement_optimizer": object(),
        "quality_guardian": object(),
        "japanese_purity_polisher": object(),
    }


def test_create_wow_tasks_injects_agent_key_and_notes(monkeypatch):
    captured = {}

    class DummyFactory:
        def __init__(self):
            pass

        def create_task(
            self,
            task_name,
            agent,
            context_data=None,
            context_tasks=None,
            task_id=None,
            task_config=None,
            **override_params,
        ):
            record_key = task_id or task_name
            captured[record_key] = {
                "task_name": task_name,
                "agent": agent,
                "context_data": context_data or {},
                "task_config": task_config or {},
                "context_tasks": context_tasks or [],
            }
            return SimpleNamespace(
                name=record_key,
                config=task_config or {},
                context=context_tasks or [],
                description=context_data.get("agent_improvement_notes", "") if context_data else "",
            )

    monkeypatch.setattr(crew_tasks, "TaskFactory", DummyFactory)

    improvement_notes = {
        "deep_news_analyzer": "データの比較軸を明確に",
        "engagement_optimizer": "視聴者参加を増やす",
    }

    tasks = crew_tasks.create_wow_tasks(
        agents=_fake_agents(),
        news_items=[{"title": "Test", "source": "Example", "summary": "Summary", "impact_level": "high"}],
        improvement_notes=improvement_notes,
    )

    task1_record = captured["task1_deep_analysis"]
    assert task1_record["task_config"]["agent_key"] == "deep_news_analyzer"
    assert task1_record["context_data"]["agent_improvement_notes"] == "データの比較軸を明確に"

    task5_record = captured["task5_engagement"]
    assert task5_record["task_config"]["agent_key"] == "engagement_optimizer"
    assert task5_record["context_data"]["agent_improvement_notes"] == "視聴者参加を増やす"

    task3_record = captured["task3_story_arc"]
    assert task3_record["task_config"]["agent_key"] == "emotional_story_architect"
    assert task3_record["context_data"].get("agent_improvement_notes", "") == ""

    # 依存関係が保たれているかも確認
    assert tasks["task2_curiosity_gaps"].context == [tasks["task1_deep_analysis"]]
