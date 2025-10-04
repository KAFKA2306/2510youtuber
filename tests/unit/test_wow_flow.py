"""Unit tests for the simplified WOW script flow wrapper."""

from app.crew.flows import WOWScriptFlow, create_wow_script_crew
from app.services.script.generator import ScriptGenerationMetadata, ScriptGenerationResult
from app.services.script.validator import DialogueEntry, Script


class DummyGenerator:
    def __init__(self, result: ScriptGenerationResult):
        self.result = result
        self.calls = 0

    def generate(self, news_items, target_duration_minutes=None):  # pragma: no cover - simple wrapper
        self.calls += 1
        assert news_items, "news_items should be forwarded"
        return self.result


def _build_sample_result() -> ScriptGenerationResult:
    script = Script(
        title="テスト動画の台本",
        dialogues=[
            DialogueEntry(speaker="武宏", line="サンプルのセリフです。"),
            DialogueEntry(speaker="つむぎ", line="視聴者にわかりやすく説明します。"),
        ],
    )
    metadata = ScriptGenerationMetadata(wow_score=8.3, japanese_purity_score=97.0, retention_prediction=0.58)
    return ScriptGenerationResult(script=script, metadata=metadata, raw_response="{...}")


def test_flow_execute_returns_expected_structure():
    dummy = DummyGenerator(_build_sample_result())
    flow = WOWScriptFlow(generator=dummy)

    result = flow.execute(news_items=[{"title": "dummy", "summary": "dummy"}])

    assert result["success"] is True
    assert isinstance(result["final_script"], Script)
    assert result["final_script"].title == "テスト動画の台本"
    assert result["metadata"]["wow_score"] == dummy.result.metadata.wow_score
    assert dummy.calls == 1


def test_create_wow_script_crew_uses_flow(monkeypatch):
    calls = {}

    def fake_execute(self, news_items, target_duration_minutes=None):  # pragma: no cover - patched call
        calls["news_items"] = list(news_items)
        return {"success": True, "final_script": _build_sample_result().script, "metadata": {}}

    monkeypatch.setattr(WOWScriptFlow, "execute", fake_execute, raising=True)

    result = create_wow_script_crew(news_items=[{"title": "dummy"}])

    assert result["success"] is True
    assert "news_items" in calls
