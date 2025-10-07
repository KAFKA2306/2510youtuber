"""Tests for extracting structured YAML from LLM responses."""

from unittest.mock import MagicMock

from app.services.script.generator import StructuredScriptGenerator


def test_extract_structured_data_handles_noise():
    generator = StructuredScriptGenerator(client=MagicMock(), allowed_speakers=("話者A", "話者B"))
    noisy_text = (
        "補足:説明\n"
        "```yaml\n"
        "title: Valid Script\ndialogues: []\n"
        "```\n"
    )

    data = generator._extract_structured_data(noisy_text)

    assert data == {"title": "Valid Script", "dialogues": []}


def test_extract_yaml_block_handles_markdown_code_blocks():
    markdown = "```yaml\ntitle: Test\ndialogues: []\n```\n補足"

    extracted = StructuredScriptGenerator._extract_yaml_block(markdown)

    assert extracted == "title: Test\ndialogues: []\n"


def test_parse_payload_handles_wrapped_yaml_string():
    generator = StructuredScriptGenerator(client=MagicMock(), allowed_speakers=("話者A", "話者B"))

    payload = generator._parse_payload('"""Here you go:\n```yaml\ntitle: Wrapped\ndialogues: []\n```\nThanks!"""')

    assert payload.title == "Wrapped"
    assert payload.dialogues == []
