"""Tests for extracting structured JSON from LLM responses."""

from types import SimpleNamespace

from app.services.script.generator import StructuredScriptGenerator


def _make_generator() -> StructuredScriptGenerator:
    dummy_client = SimpleNamespace(completion=None)
    return StructuredScriptGenerator(client=dummy_client, allowed_speakers=('ナビゲーター', 'アナリスト', 'リポーター'))


def test_extract_json_block_skips_non_json_braces():
    noisy_text = (
        "補足:{説明}\n"
        "\n"
        '{"title": "Valid Script", "dialogues": []}'
    )

    extracted = StructuredScriptGenerator._extract_json_block(noisy_text)

    assert extracted == '{"title": "Valid Script", "dialogues": []}'


def test_extract_json_block_handles_markdown_code_blocks():
    markdown = "```json\n{\n  \"title\": \"Test\",\n  \"dialogues\": []\n}\n```\n補足"

    extracted = StructuredScriptGenerator._extract_json_block(markdown)

    assert extracted == '{\n  "title": "Test",\n  "dialogues": []\n}'


def test_build_script_from_text_recovers_structured_payload():
    generator = _make_generator()
    response_text = (
        "```json\n"
        '{\n'
        '  "title": "最新ニュース徹底解説",\n'
        '  "dialogues": [\n'
        '    {"speaker": "ナビゲーター", "line": "こんばんは、きょうのマーケットを整理します。"},\n'
        '    {"speaker": "アナリスト", "line": "まずは日経平均の動きから見ていきましょう。"}\n'
        '  ]\n'
        '}\n'
        "```"
    )

    script, report = generator._build_script_from_text(response_text)

    assert script.title == '最新ニュース徹底解説'
    assert [entry.line for entry in script.dialogues[:2]] == [
        'こんばんは、きょうのマーケットを整理します。',
        'まずは日経平均の動きから見ていきましょう。',
    ]
    assert report.dialogue_lines >= 2
