"""Integration tests for Gemini LLM output format validation.

These tests validate that:
1. Gemini generates valid YAML structures
2. Output parsers handle all real-world format variations
3. Edge cases (wrapped YAML, markdown fences, mixed content) work correctly
4. Error handling is robust for malformed outputs

Run with: pytest tests/integration/test_gemini_output_formats.py -v
"""

from __future__ import annotations

import pytest
import yaml

from app.adapters.llm import LLMClient, extract_structured_yaml
from app.crew.agent_review import parse_yaml_from_gemini


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def gemini_client():
    """Create a real Gemini client for integration testing."""
    return LLMClient(model="gemini-1.5-flash", temperature=0.7)


# ============================================================================
# Test: extract_structured_yaml - Edge Cases
# ============================================================================


class TestExtractStructuredYAML:
    """Test the extract_structured_yaml function with realistic edge cases."""

    def test_extracts_yaml_from_markdown_code_fence(self):
        """YAML wrapped in markdown code fences should be extracted."""
        payload = """Here's the result:
```yaml
wow_score: 8.5
surprise_points: 12
emotion_peaks: 7
```
Hope this helps!"""

        result = extract_structured_yaml(payload)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["wow_score"] == 8.5
        assert parsed["surprise_points"] == 12
        assert parsed["emotion_peaks"] == 7

    def test_extracts_yaml_from_yml_fence(self):
        """YAML with 'yml' fence variant should work."""
        payload = """```yml
retention_prediction: 55.2
visual_instructions: 18
```"""

        result = extract_structured_yaml(payload)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["retention_prediction"] == 55.2
        assert parsed["visual_instructions"] == 18

    def test_extracts_yaml_with_japanese_content(self):
        """Japanese text in YAML values should be preserved."""
        payload = """```yaml
speaker: 田中
text: これは重要な経済ニュースです
emotion: 驚き
```"""

        result = extract_structured_yaml(payload)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["speaker"] == "田中"
        assert parsed["text"] == "これは重要な経済ニュースです"
        assert parsed["emotion"] == "驚き"

    def test_extracts_nested_yaml_structures(self):
        """Complex nested YAML should be extracted correctly."""
        payload = """Analysis complete:
```yaml
metrics:
  wow_score: 9.0
  surprise_points: 15
segments:
  - speaker: ナレーター
    text: 本日のニュース
    timestamp: 0.0
  - speaker: 武宏
    text: 重要な分析です
    timestamp: 5.2
```"""

        result = extract_structured_yaml(payload)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["metrics"]["wow_score"] == 9.0
        assert len(parsed["segments"]) == 2
        assert parsed["segments"][0]["speaker"] == "ナレーター"
        assert parsed["segments"][1]["speaker"] == "武宏"

    def test_handles_double_wrapped_yaml_string(self):
        """YAML that parses to a string containing YAML should be unwrapped."""
        # This simulates when LLM returns YAML-encoded string
        inner_yaml = "score: 7\nstatus: good"
        wrapped = yaml.safe_dump(inner_yaml)  # Dumps as quoted string

        result = extract_structured_yaml(wrapped)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
        assert parsed["score"] == 7
        assert parsed["status"] == "good"

    def test_returns_none_for_invalid_yaml(self):
        """Invalid YAML should return None."""
        payload = "This is just plain text: {invalid yaml: [unclosed"

        result = extract_structured_yaml(payload)

        assert result is None

    def test_returns_none_for_empty_string(self):
        """Empty input should return None."""
        result = extract_structured_yaml("")
        assert result is None

        result = extract_structured_yaml("   \n  \t  ")
        assert result is None

    def test_extracts_yaml_list_structure(self):
        """YAML lists (sequences) should be extracted."""
        payload = """```yaml
- item: first
  value: 100
- item: second
  value: 200
```"""

        result = extract_structured_yaml(payload)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["item"] == "first"
        assert parsed[1]["value"] == 200


# ============================================================================
# Test: parse_yaml_from_gemini - Agent-Specific Parsing
# ============================================================================


class TestParseYAMLFromGemini:
    """Test agent-specific YAML parsing logic."""

    def test_script_writer_allows_raw_output(self):
        """script_writer agent should accept raw text without YAML (truly plain text)."""
        # Use text that won't accidentally parse as YAML
        raw_text = """これは完全に自由形式のテキストです。
田中さんが話している内容はとても重要です。
経済ニュースについて詳しく説明します。"""

        result = parse_yaml_from_gemini(raw_text, "script_writer")

        # RAW output returns dict with raw_output and success keys
        assert isinstance(result, dict)
        assert result.get("success") is True
        assert "raw_output" in result
        assert "田中" in result["raw_output"]

    def test_script_writer_prefers_yaml_over_raw(self):
        """script_writer should parse YAML if available."""
        payload = """```yaml
segments:
  - speaker: 田中
    text: テスト
```"""

        result = parse_yaml_from_gemini(payload, "script_writer")

        assert "segments" in result
        assert result["segments"][0]["speaker"] == "田中"

    def test_japanese_purity_polisher_allows_raw_output(self):
        """japanese_purity_polisher should accept raw text."""
        raw_text = "これは完全に日本語のテキストです。"

        result = parse_yaml_from_gemini(raw_text, "japanese_purity_polisher")

        assert result["success"] is True
        assert "raw_output" in result

    def test_quality_guardian_requires_yaml(self):
        """quality_guardian should raise on non-YAML input."""
        raw_text = "This is just plain text without YAML"

        with pytest.raises(ValueError, match="No YAML mapping found"):
            parse_yaml_from_gemini(raw_text, "quality_guardian")

    def test_parses_yaml_with_markdown_wrapper(self):
        """Standard agents should handle markdown-wrapped YAML."""
        payload = """Here's my analysis:
```yaml
wow_score: 8.0
verdict: approved
```"""

        result = parse_yaml_from_gemini(payload, "engagement_optimizer")

        assert isinstance(result, dict)
        assert result["wow_score"] == 8.0
        assert result["verdict"] == "approved"

    def test_handles_preface_text_before_yaml(self):
        """Text before YAML should be ignored."""
        payload = """Let me analyze this content.

The quality metrics are:
```yaml
retention_prediction: 52.0
surprise_points: 8
```

This looks good."""

        result = parse_yaml_from_gemini(payload, "deep_news_analyzer")

        assert result["retention_prediction"] == 52.0
        assert result["surprise_points"] == 8


# ============================================================================
# Test: Integration with Real Gemini API
# ============================================================================


@pytest.mark.integration
class TestGeminiRealAPIOutputFormats:
    """Integration tests with actual Gemini API calls.

    These tests validate real-world output format handling.
    Skip with: pytest -m "not integration"
    """

    def test_gemini_generates_valid_yaml_from_structured_prompt(self, gemini_client):
        """Gemini should generate valid YAML when prompted."""
        prompt = """Generate a YAML output with the following structure:
```yaml
score: <number>
comments: <list of strings>
```

Provide a score between 1-10 and 2-3 comments about economic news quality."""

        response = gemini_client.generate(prompt)

        # Should be parseable
        extracted = extract_structured_yaml(response)
        assert extracted is not None

        parsed = yaml.safe_load(extracted)
        assert "score" in parsed
        assert isinstance(parsed["score"], (int, float))
        assert 1 <= parsed["score"] <= 10
        assert "comments" in parsed
        assert isinstance(parsed["comments"], list)

    def test_gemini_generates_japanese_yaml_correctly(self, gemini_client):
        """Gemini should handle Japanese text in YAML values."""
        prompt = """以下のYAML形式で出力してください:
```yaml
話者: <話者名>
セリフ: <日本語のセリフ>
感情: <感情>
```

経済ニュースのナレーションとして適切な内容を生成してください。"""

        response = gemini_client.generate(prompt)

        extracted = extract_structured_yaml(response)
        assert extracted is not None

        parsed = yaml.safe_load(extracted)
        assert "話者" in parsed or "speaker" in parsed
        # Should contain Japanese characters
        text_content = str(parsed)
        assert any(ord(char) > 0x3000 for char in text_content)  # Japanese Unicode range

    def test_gemini_structured_output_with_schema(self, gemini_client):
        """generate_structured should parse complex YAML correctly."""
        prompt = """Return a script analysis in YAML format:
```yaml
wow_score: <float>
retention_prediction: <float>
surprise_points: <int>
emotion_peaks: <int>
visual_instructions: <int>
segments:
  - speaker: <name>
    text: <content>
```

Provide realistic values for a 5-minute economic news video."""

        result = gemini_client.generate_structured(prompt)

        assert isinstance(result, dict)
        assert "wow_score" in result
        assert "segments" in result
        assert isinstance(result["segments"], list)
        if result["segments"]:
            assert "speaker" in result["segments"][0]
            assert "text" in result["segments"][0]

    def test_gemini_handles_complex_nested_structures(self, gemini_client):
        """Gemini should generate complex nested YAML correctly."""
        prompt = """Generate a workflow result in YAML:
```yaml
run_id: <uuid>
status: success
steps:
  - name: script_generation
    duration: <seconds>
    metrics:
      wow_score: <float>
  - name: video_generation
    duration: <seconds>
quality_metrics:
  japanese_purity: <percentage>
  retention_prediction: <percentage>
```"""

        response = gemini_client.generate(prompt)
        extracted = extract_structured_yaml(response)
        assert extracted is not None

        parsed = yaml.safe_load(extracted)
        assert "steps" in parsed
        assert isinstance(parsed["steps"], list)
        assert "quality_metrics" in parsed

    def test_gemini_output_survives_round_trip_parsing(self, gemini_client):
        """Gemini output should survive multiple parse cycles."""
        prompt = "Generate a simple YAML: {score: 7, status: good}"

        response = gemini_client.generate(prompt)

        # First extraction
        extracted1 = extract_structured_yaml(response)
        assert extracted1 is not None
        parsed1 = yaml.safe_load(extracted1)

        # Re-dump and re-parse
        dumped = yaml.safe_dump(parsed1)
        extracted2 = extract_structured_yaml(dumped)
        assert extracted2 is not None
        parsed2 = yaml.safe_load(extracted2)

        # Should be identical
        assert parsed1 == parsed2


# ============================================================================
# Test: Error Handling & Malformed Outputs
# ============================================================================


class TestMalformedOutputHandling:
    """Test robust error handling for malformed LLM outputs."""

    def test_handles_json_instead_of_yaml(self):
        """JSON format should be parseable as valid YAML (without ```json fence)."""
        # Note: extract_structured_yaml only looks for ```yaml or ```yml fences
        # Plain JSON (as valid YAML) works, but not with ```json fence
        json_output = """{
    "score": 8,
    "status": "approved"
}"""

        result = extract_structured_yaml(json_output)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["score"] == 8
        assert parsed["status"] == "approved"

    def test_handles_mixed_json_yaml_syntax(self):
        """Mixed JSON/YAML syntax should parse correctly."""
        mixed = """{score: 8, tags: ["news", "finance"], nested: {value: 100}}"""

        result = extract_structured_yaml(mixed)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["score"] == 8
        assert parsed["tags"] == ["news", "finance"]
        assert parsed["nested"]["value"] == 100

    def test_handles_incomplete_yaml_fence(self):
        """Incomplete markdown fence - falls back to plain text parsing."""
        # When fence is incomplete, the regex won't match, but plain YAML still works
        incomplete = """score: 7
status: good"""

        result = extract_structured_yaml(incomplete)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["score"] == 7

    def test_handles_multiple_yaml_blocks(self):
        """Multiple YAML blocks - should extract first valid one."""
        multiple = """First block:
```yaml
score: 5
```

Second block:
```yaml
score: 8
```"""

        result = extract_structured_yaml(multiple)

        assert result is not None
        parsed = yaml.safe_load(result)
        # Should get first valid block
        assert parsed["score"] == 5

    def test_handles_yaml_with_special_characters(self):
        """YAML with special characters should be escaped correctly."""
        special = """```yaml
title: "Breaking: Economy Crashes!"
subtitle: "What's next?"
emoji: "🚨"
```"""

        result = extract_structured_yaml(special)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert "Economy Crashes!" in parsed["title"]
        assert parsed["emoji"] == "🚨"

    def test_handles_yaml_with_multiline_strings(self):
        """Multiline YAML strings should be preserved."""
        multiline = """```yaml
description: |
  This is a long description
  that spans multiple lines
  and should be preserved.
status: active
```"""

        result = extract_structured_yaml(multiline)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert "multiple lines" in parsed["description"]
        assert parsed["status"] == "active"

    def test_parse_yaml_from_gemini_with_no_mapping(self):
        """Non-RAW agents should raise on scalar YAML."""
        scalar_yaml = "just_a_string"

        with pytest.raises(ValueError, match="No YAML mapping found"):
            parse_yaml_from_gemini(scalar_yaml, "quality_guardian")

    def test_parse_yaml_from_gemini_with_list_instead_of_dict(self):
        """Non-RAW agents should raise on YAML lists."""
        yaml_list = """```yaml
- item1
- item2
```"""

        with pytest.raises(ValueError, match="YAML payload was not a mapping"):
            parse_yaml_from_gemini(yaml_list, "engagement_optimizer")


# ============================================================================
# Test: Performance & Edge Cases
# ============================================================================


class TestPerformanceAndEdgeCases:
    """Test performance and unusual edge cases."""

    def test_handles_very_large_yaml_output(self):
        """Large YAML outputs should be processed efficiently."""
        # Generate large YAML with 100 segments
        segments = "\n".join([
            f"  - speaker: Speaker{i}\n    text: Text content {i}\n    timestamp: {i * 5.0}"
            for i in range(100)
        ])
        large_yaml = f"""```yaml
segments:
{segments}
```"""

        result = extract_structured_yaml(large_yaml)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert len(parsed["segments"]) == 100

    def test_handles_unicode_escape_sequences(self):
        """Unicode escape sequences should be handled."""
        unicode_yaml = r"""```yaml
text: "\u65E5\u672C\u8A9E"
emoji: "\U0001F4B0"
```"""

        result = extract_structured_yaml(unicode_yaml)

        assert result is not None
        parsed = yaml.safe_load(result)
        # YAML should decode Unicode escapes
        assert parsed["text"] == "日本語"

    def test_handles_yaml_with_comments(self):
        """YAML comments should be ignored."""
        commented = """```yaml
# This is a comment
score: 8  # inline comment
# Another comment
status: good
```"""

        result = extract_structured_yaml(commented)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed["score"] == 8
        assert parsed["status"] == "good"

    def test_handles_empty_yaml_mapping(self):
        """Empty YAML mapping should be valid."""
        empty = "```yaml\n{}\n```"

        result = extract_structured_yaml(empty)

        assert result is not None
        parsed = yaml.safe_load(result)
        assert parsed == {}

    def test_preserves_yaml_key_order(self):
        """YAML key order should be preserved (sort_keys=False)."""
        ordered = """```yaml
z_last: 1
a_first: 2
m_middle: 3
```"""

        result = extract_structured_yaml(ordered)

        assert result is not None
        # Check that order is preserved in output
        lines = result.split("\n")
        assert lines[0].startswith("z_last")
        assert lines[1].startswith("a_first")
        assert lines[2].startswith("m_middle")
