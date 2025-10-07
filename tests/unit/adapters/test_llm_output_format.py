"""Unit tests for LLM output normalization helpers."""

from __future__ import annotations

import pytest

import yaml

from app.adapters.llm import LLMClient, extract_structured_yaml
from app.crew.agent_review import parse_yaml_from_gemini


class _DummyLLMClient(LLMClient):
    """Minimal stub overriding network calls for unit tests."""

    def __init__(self, raw_output: str) -> None:  # noqa: D401 - simple holder
        self._raw_output = raw_output

    def generate(self, prompt: str, generation_config=None):  # type: ignore[override]
        return self._raw_output


def test_extract_structured_yaml_with_markdown_fences() -> None:
    payload = """Gemini reply:\n```yaml\nscore: 8\nitems:\n  - id: 1\n```\nThanks!"""

    snippet = extract_structured_yaml(payload)

    assert snippet is not None
    assert yaml.safe_load(snippet)["score"] == 8


def test_generate_structured_handles_preface_text() -> None:
    raw = "Here you go:\n```yaml\nrating: 4\nnotes:\n  - tighten intro\n```\nExtra commentary."
    client = _DummyLLMClient(raw)

    result = client.generate_structured("prompt")

    assert isinstance(result, dict)
    assert result == {"rating": 4, "notes": ["tighten intro"]}


@pytest.mark.parametrize("agent_key", ["fact_checker", "script_writer"])
def test_parse_yaml_from_gemini_allows_wrapped_yaml(agent_key: str) -> None:
    response = """assistant: ```yaml\nscore: 6.5\nverdict: Needs polish\n``` summary"""

    parsed = parse_yaml_from_gemini(response, agent_key)

    if agent_key == "script_writer":
        # RAW agents return dict with success flag when JSON parsing fails, but
        # in this case we still expect structured data because parsing succeeds.
        assert parsed["score"] == 6.5
        assert parsed["verdict"] == "Needs polish"
    else:
        assert parsed == {"score": 6.5, "verdict": "Needs polish"}
