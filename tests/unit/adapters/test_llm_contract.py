"""Contract tests for CrewAI LLM adapters."""

import pytest

from app.adapters.llm import GeminiClient, get_crewai_gemini_llm


@pytest.mark.unit
def test_crewai_gemini_llm_declares_function_calling(monkeypatch):
    """CrewAI Gemini adapter must expose CrewAI capability hooks."""

    llm = get_crewai_gemini_llm(model="unit-test", api_key="dummy-key")

    assert hasattr(llm, "supports_function_calling"), "CrewAI LLM must expose supports_function_calling"
    assert llm.supports_function_calling() is True


@pytest.mark.unit
def test_gemini_client_generate_structured_parses_json(monkeypatch):
    """GeminiClient.generate_structured should return parsed dict when possible."""

    client = GeminiClient(api_key="dummy", model="gemini/test")

    monkeypatch.setattr(
        client,
        "generate",
        lambda prompt, generation_config=None: '```json\n{\n  "foo": "bar"\n}\n```',
    )

    result = client.generate_structured("dummy prompt")

    assert isinstance(result, dict)
    assert result["foo"] == "bar"
