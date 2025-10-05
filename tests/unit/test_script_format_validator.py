import pytest

from app.services.script.validator import ScriptFormatError, ensure_dialogue_structure

ALLOWED = ["武宏", "つむぎ", "ナレーター"]


def test_validator_normalizes_common_variants():
    script = "\n".join(
        [
            "武宏：こんにちは。",
            "つむぎ「そうなんですか？",
            "(字幕: 強調テロップ)",
            "ナレーター まとめとしてお伝えします。",
        ]
    )

    result = ensure_dialogue_structure(script, allowed_speakers=ALLOWED, min_dialogue_lines=2)

    lines = result.normalized_script.splitlines()
    assert lines[0] == "武宏: こんにちは。"
    assert lines[1] == "つむぎ: そうなんですか？"
    assert lines[2] == "(字幕: 強調テロップ)"
    assert lines[3] == "ナレーター: まとめとしてお伝えします。"
    assert result.dialogue_line_count == 3
    assert result.is_valid


def test_validator_requires_multiple_speakers():
    script = "\n".join(["武宏: 解説その{}です。".format(i) for i in range(5)])

    with pytest.raises(ScriptFormatError) as exc:
        ensure_dialogue_structure(script, allowed_speakers=ALLOWED)

    message = str(exc.value)
    assert "at least two distinct speakers" in message


def test_validator_rejects_when_no_dialogue():
    script = "前回の復習を行います。\n具体的な台詞が出力されません。"

    with pytest.raises(ScriptFormatError) as exc:
        ensure_dialogue_structure(script, allowed_speakers=ALLOWED)

    result = exc.value.result
    assert result.dialogue_line_count == 0
    assert any(issue.severity == "error" for issue in result.errors)


def test_validator_flags_missing_colon():
    script = "\n".join(
        [
            "武宏 まずは市場の動きを整理しましょう。",
            "つむぎ: なるほど、続けてください。",
            "ナレーター: 以上が本日のまとめです。",
        ]
    )

    result = ensure_dialogue_structure(script, allowed_speakers=ALLOWED, min_dialogue_lines=3)

    assert "武宏: まずは市場の動きを整理しましょう。" in result.normalized_script
    assert any("Missing colon" in warning.message for warning in result.warnings)


def test_validator_handles_honorifics_and_aliases():
    script = "\n".join(
        [
            "武宏さん: 今日は米国市場の動向を整理します。",
            "つむぎ（リポーター）: まず注目ポイントを教えてください。",
            "司会: ここで一度まとめに入りましょう。",
        ]
    )

    result = ensure_dialogue_structure(script, allowed_speakers=ALLOWED, min_dialogue_lines=3)

    lines = result.normalized_script.splitlines()
    assert lines[0] == "武宏: 今日は米国市場の動向を整理します。"
    assert lines[1] == "つむぎ: まず注目ポイントを教えてください。"
    assert lines[2] == "ナレーター: ここで一度まとめに入りましょう。"
    assert result.speaker_counts["武宏"] == 1
    assert result.speaker_counts["つむぎ"] == 1
    assert result.speaker_counts["ナレーター"] == 1


def test_validator_allows_short_form_scripts_when_all_lines_are_dialogue():
    script = "\n".join(
        [
            "武宏: 速報です。",
            "つむぎ: 詳細を教えてください。",
        ]
    )

    result = ensure_dialogue_structure(script, allowed_speakers=ALLOWED)

    assert result.dialogue_line_count == 2
    assert result.nonempty_line_count == 2
    assert result.is_valid
