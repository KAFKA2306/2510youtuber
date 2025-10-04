"""Tests for the structured script generator service."""

import json

import pytest

from app.services.script.generator import StructuredScriptGenerator
from app.services.script.validator import Script


class DummyClient:
    """Minimal LiteLLM client stub used in tests."""

    def __init__(self, responses):
        self._responses = responses
        self.calls = 0

    def completion(self, *_, **__):  # pragma: no cover - interface compatibility
        if self.calls >= len(self._responses):
            pytest.fail("DummyClient received more calls than expected")
        response = self._responses[self.calls]
        self.calls += 1
        return response


def _build_response(payload: dict, wrap: bool = False):
    content = json.dumps(payload, ensure_ascii=False)
    if wrap:
        content = f"Thought: ...\n\nHere is the script as requested:\n{content}\nEND"
    return {"choices": [{"message": {"content": content}}]}


def test_extract_json_block_handles_wrapped_text():
    payload = {"title": "test", "dialogues": []}
    response = _build_response(payload, wrap=True)
    generator = StructuredScriptGenerator(client=DummyClient([response]))

    blob = generator._extract_json_block(generator._extract_message_text(response))
    assert blob is not None
    assert json.loads(blob)["title"] == "test"


def test_structured_generator_returns_script(monkeypatch):
    payload = {
        "title": "【速報】日銀サプライズの真相",
        "summary": "マイナス金利解除の裏にある為替と家計へのインパクトを解説",
        "dialogues": [
            {"speaker": "武宏", "line": "日銀の決定は大きな驚きでしたね。"},
            {"speaker": "つむぎ", "line": "視聴者の皆さんにも影響が出そうですか？"},
            {"speaker": "武宏", "line": "変動金利ローンの方は準備が必要です。"},
            {"speaker": "ナレーター", "line": "最後に行動ステップを整理します。"},
        ],
        "wow_score": 8.4,
        "japanese_purity_score": 97.2,
        "retention_prediction": 0.56,
    }

    response = _build_response(payload)
    generator = StructuredScriptGenerator(client=DummyClient([response]))

    result = generator.generate(
        news_items=[
            {
                "title": "日銀がマイナス金利を解除",
                "summary": "物価動向と為替圧力を受けてマイナス金利を終了。長期金利が即座に反応した。",
                "source": "NHK",
                "impact_level": "high",
            }
        ]
    )

    assert isinstance(result.script, Script)
    assert result.script.title == payload["title"]
    assert len(result.script.dialogues) == 4
    assert result.metadata.wow_score == pytest.approx(8.4)
    assert result.metadata.japanese_purity_score == pytest.approx(97.2)
    assert result.metadata.retention_prediction == pytest.approx(0.56)
