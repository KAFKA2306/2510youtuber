"""Unit tests for LLM output normalization helpers."""
from __future__ import annotations
import json
import pytest
from app.adapters.llm import LLMClient, extract_structured_json
from app.crew.agent_review import parse_json_from_gemini
class _DummyLLMClient(LLMClient):
    """Minimal stub overriding network calls for unit tests."""
    def __init__(self, raw_output: str) -> None:
        self._raw_output = raw_output
    def generate(self, prompt: str, generation_config=None):
        return self._raw_output
def test_extract_structured_json_with_markdown_fences() -> None:
    payload = """Gemini reply:\n```json\n{\n  \"score\": 8,\n  \"items\": [\n    {\"id\": 1}\n  ]\n}\n```\nThanks!"""
    snippet = extract_structured_json(payload)
    assert snippet is not None
    assert json.loads(snippet)["score"] == 8
def test_generate_structured_handles_preface_text() -> None:
    raw = "Here you go: {\"rating\": 4, \"notes\": [\"tighten intro\"]} Extra commentary."
    client = _DummyLLMClient(raw)
    result = client.generate_structured("prompt")
    assert isinstance(result, dict)
    assert result == {"rating": 4, "notes": ["tighten intro"]}
@pytest.mark.parametrize("agent_key", ["fact_checker", "script_writer"])
def test_parse_json_from_gemini_allows_wrapped_json(agent_key: str) -> None:
    response = """assistant: ```json\n{\n  \"score\": 6.5,\n  \"verdict\": \"Needs polish\"\n}\n``` summary"""
    parsed = parse_json_from_gemini(response, agent_key)
    if agent_key == "script_writer":
        assert parsed["score"] == 6.5
        assert parsed["verdict"] == "Needs polish"
    else:
        assert parsed == {"score": 6.5, "verdict": "Needs polish"}
