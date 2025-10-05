"""Tests for the structured script generator service."""

import json

import pytest

from app.config.settings import settings
from app.services.script.generator import ScriptQualityReport, StructuredScriptGenerator
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
    assert isinstance(result.metadata.quality_report, ScriptQualityReport)
    assert result.metadata.quality_report.dialogue_lines == 4


def test_generator_uses_fallback_when_quality_gate_disabled(monkeypatch):
    raw_script = "武宏: 今朝のマーケットは大きく動きました。\nつむぎ: 具体的にはどの指標ですか？"
    response = {"choices": [{"message": {"content": raw_script}}]}

    monkeypatch.setattr(
        settings.script_generation,
        "quality_gate_llm_enabled",
        False,
        raising=False,
    )

    generator = StructuredScriptGenerator(client=DummyClient([response]), max_attempts=1)

    result = generator.generate(
        news_items=[
            {
                "title": "日経平均が急伸",
                "summary": "米国株高を受けて東京市場が反発した。",
                "source": "日経",
                "impact_level": "medium",
            }
        ]
    )

    assert isinstance(result.script, Script)
    assert len(result.script.dialogues) >= 2
    assert result.script.dialogues[0].speaker == "武宏"
    assert result.metadata.wow_score is None
    assert result.metadata.quality_report is not None
    assert result.metadata.quality_report.dialogue_lines >= 1
    assert result.metadata.quality_report.errors


def test_generator_returns_fallback_when_quality_gate_enabled(monkeypatch):
    raw_script = "武宏: リスクイベントを振り返りましょう。\n解析: 補助テキストのみ。"
    response = {"choices": [{"message": {"content": raw_script}}]}

    monkeypatch.setattr(
        settings.script_generation,
        "quality_gate_llm_enabled",
        True,
        raising=False,
    )

    generator = StructuredScriptGenerator(client=DummyClient([response]), max_attempts=1)

    result = generator.generate(
        news_items=[
            {
                "title": "TOPIXが続伸",
                "summary": "好決算を受けた買いで幅広い銘柄が上昇。",
                "source": "Bloomberg",
                "impact_level": "medium",
            }
        ]
    )

    assert result.script.dialogues[0].speaker == "武宏"
    assert result.metadata.quality_report is not None
    assert result.metadata.quality_report.dialogue_lines >= 1
    assert result.metadata.quality_report.errors


def test_generator_returns_backup_script_when_all_attempts_fail(monkeypatch):
    responses = [
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": ""}}]},
    ]

    monkeypatch.setattr(
        settings.script_generation,
        "quality_gate_llm_enabled",
        True,
        raising=False,
    )

    generator = StructuredScriptGenerator(client=DummyClient(responses), max_attempts=2)

    result = generator.generate(
        news_items=[
            {
                "title": "円相場が急伸",
                "summary": "安全通貨への買いが強まり、一時1ドル=145円台まで円高が進行。",
                "source": "ロイター",
                "impact_level": "high",
            }
        ],
        target_duration_minutes=5,
    )

    assert result.raw_response == ""
    assert result.script.title.startswith("バックアップ台本")
    assert len(result.script.dialogues) >= 24
    assert result.metadata.quality_report.dialogue_lines >= 24
