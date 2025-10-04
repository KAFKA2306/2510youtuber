import pytest

from app.config import cfg
from app.workflow.steps import GenerateScriptStep


@pytest.mark.asyncio
async def test_generate_with_crewai_accepts_raw_string(monkeypatch):
    step = GenerateScriptStep()

    dummy_script = "武宏: こんにちは。\nつむぎ: こんばんは。"

    def fake_create_wow_script_crew(*, news_items, target_duration_minutes):
        assert news_items == ["news"]
        assert target_duration_minutes == 8
        return {
            "success": True,
            "final_script": dummy_script,
            "quality_data": {"wow_score": 9.2},
        }

    monkeypatch.setattr("app.crew.flows.create_wow_script_crew", fake_create_wow_script_crew)
    monkeypatch.setattr(cfg, "max_video_duration_minutes", 8, raising=False)

    result = await step._generate_with_crewai(["news"])

    assert result["script"] == dummy_script
    assert result["crew_result"]["quality_data"]["wow_score"] == 9.2
