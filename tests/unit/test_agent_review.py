import json
import os

import pytest

from app.crew.agent_review import AgentReviewCycle, AgentReviewResult, AgentReviewStorage


class _StubWorkflowLogger:
    """Lightweight stub so tests avoid depending on the full logging stack."""

    def __init__(self) -> None:
        self.logger = self

    def agent_start(self, *_args, **_kwargs) -> None:  # pragma: no cover - test helper
        return None

    def agent_end(self, *_args, **_kwargs) -> None:  # pragma: no cover - test helper
        return None

    def debug(self, *_args, **_kwargs) -> None:  # pragma: no cover - test helper
        return None


@pytest.fixture
def storage_path(tmp_path):
    return tmp_path / "agent_reviews.json"


def test_agent_review_storage_persists_and_focus(storage_path):
    storage = AgentReviewStorage(str(storage_path))

    result = AgentReviewResult(
        agent_key="script_writer",
        agent_role="Script Writer",
        task_name="task4_script_writing",
        score=8.2,
        verdict="テンポ良好",
        strengths=["テンポが自然"],
        issues=["数値が少ない"],
        action_items=["数値例を追加"],
        compliance={"previous_focus_addressed": "partial", "notes": "改善余地あり"},
        raw_feedback="{}",
    )

    storage.append(result)
    storage.save()

    reloaded = AgentReviewStorage(str(storage_path))
    focus = reloaded.get_focus_notes("script_writer")

    assert focus is not None
    assert "改善: 数値例を追加" in focus
    assert reloaded._data["script_writer"]["rolling_average"] == pytest.approx(8.2, abs=0.01)


def test_agent_review_cycle_uses_storage_focus(monkeypatch, storage_path):
    os.environ["DISABLE_AGENT_REVIEW"] = "1"
    storage = AgentReviewStorage(str(storage_path))
    storage.append(
        AgentReviewResult(
            agent_key="quality_guardian",
            agent_role="Quality Guardian",
            task_name="task6_quality",
            score=7.5,
            verdict="要改善",
            strengths=["評価軸は網羅"],
            issues=["WOWスコア算出根拠が薄い"],
            action_items=["保持率コメントを具体化"],
            compliance={"previous_focus_addressed": "no", "notes": ""},
            raw_feedback="{}",
        )
    )
    storage.save()

    cycle = AgentReviewCycle(storage=storage)
    notes = cycle.prepare_improvement_notes()

    try:
        assert "quality_guardian" in notes
        assert "改善: 保持率コメントを具体化" in notes["quality_guardian"]
    finally:
        os.environ.pop("DISABLE_AGENT_REVIEW", None)


def test_agent_review_cycle_normalizes_llm_output(monkeypatch, storage_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class DummyPromptManager:
        def load(self, filename):
            if filename == "agents.yaml":
                return {
                    "agents": {
                        "script_writer": {
                            "role": "Script Writer",
                            "goal": "",
                            "backstory": "",
                        }
                    }
                }
            if filename == "evaluation_rubrics.yaml":
                return {"evaluation_rubrics": {}}
            return {}

    monkeypatch.setattr("app.crew.agent_review.get_prompt_manager", lambda: DummyPromptManager())
    monkeypatch.setattr("app.crew.agent_review.workflow_logger", _StubWorkflowLogger())

    storage = AgentReviewStorage(str(storage_path))
    cycle = AgentReviewCycle(storage=storage)

    class StubClient:
        def generate_structured(self, _prompt):
            payload = {
                "score": 7.0,
                "verdict": "solid",
                "strengths": ["clear pacing"],
                "issues": "missing concrete stats",
                "action_items": [],
                "compliance": {"previous_focus_addressed": "yes", "notes": ""},
            }
            return json.dumps(payload)

    cycle._client = StubClient()  # type: ignore[attr-defined]

    class DummyAgent:
        role = "Script Writer"

    class DummyTask:
        agent = DummyAgent()
        description = ""
        expected_output = ""

        class Output:
            raw = "Sample task output"

        output = Output()

    agent_config = cycle._agents_config["script_writer"]
    result = cycle._evaluate_single(
        agent_key="script_writer",
        task_name="task4_script_writing",
        task=DummyTask(),
        task_output="Sample task output",
        agent_config=agent_config,
    )

    assert isinstance(result, AgentReviewResult)
    assert result.score == pytest.approx(7.0)
    assert result.issues == ["missing concrete stats"]
    assert result.action_items == []
