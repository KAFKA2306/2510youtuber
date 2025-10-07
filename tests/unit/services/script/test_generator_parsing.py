"""Tests for extracting structured JSON from LLM responses."""

from unittest.mock import MagicMock

from app.services.script.generator import StructuredScriptGenerator


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


def test_parse_payload_handles_wrapped_json_string():
    generator = StructuredScriptGenerator(client=MagicMock(), allowed_speakers=("話者A", "話者B"))

    payload = generator._parse_payload('"{\\"title\\": \\"Wrapped\\", \\"dialogues\\": []}"')

    assert payload.title == "Wrapped"
    assert payload.dialogues == []
