import pytest

from app.config import cfg
from app.workflow.steps import GenerateScriptStep


@pytest.mark.asyncio
async def test_generate_with_crewai_accepts_raw_string(monkeypatch):
    step = GenerateScriptStep()

    from app.services.script.validator import DialogueEntry, Script

    dummy_script_model = Script(
        title="テストタイトル",
        dialogues=[
            DialogueEntry(speaker="武宏", line="こんにちは。"),
            DialogueEntry(speaker="つむぎ", line="こんばんは。"),
        ],
    )

    def fake_create_wow_script_crew(*, news_items, target_duration_minutes):
        assert news_items == ["news"]
        assert target_duration_minutes == 8
        return {
            "success": True,
            "final_script": dummy_script_model,
            "metadata": {"wow_score": 9.2},
        }

    monkeypatch.setattr("app.crew.flows.create_wow_script_crew", fake_create_wow_script_crew)
    monkeypatch.setattr(cfg, "max_video_duration_minutes", 8, raising=False)

    result = await step._generate_with_crewai(["news"])

    assert dummy_script_model.dialogues[0].line in result["script"]
    assert result["crew_result"]["metadata"]["wow_score"] == 9.2
