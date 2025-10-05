"""Contract tests for CrewAI LLM adapters."""

import pytest

import app.adapters.llm as llm_module
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


@pytest.mark.unit
def test_crewai_gemini_llm_passes_kwargs_supported_by_base(monkeypatch):
    """CrewAI Gemini LLM should forward compatible kwargs to BaseLLM.__init__."""

    captured: dict = {}

    def fake_init(self, *, model, temperature, api_key=None, custom_flag=None):  # noqa: ANN001
        captured.update(
            {
                "model": model,
                "temperature": temperature,
                "api_key": api_key,
                "custom_flag": custom_flag,
            }
        )

    monkeypatch.setattr(llm_module.BaseLLM, "__init__", fake_init)

    llm = llm_module.CrewAIGeminiLLM(
        model="unit-test",
        temperature=0.25,
        stop=["halt"],
        api_key="key-123",
        custom_flag="forward-me",
    )

    assert captured == {
        "model": "unit-test",
        "temperature": 0.25,
        "api_key": "key-123",
        "custom_flag": "forward-me",
    }
    assert llm.stop == ["halt"]
    assert llm.temperature == 0.25
