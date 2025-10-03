import json
import logging

import pytest

from app.crew.flows import WOWScriptFlow


# ロガーの出力をキャプチャするためのフィクスチャ
@pytest.fixture
def caplog_for_warnings(caplog):
    caplog.set_level(logging.WARNING)
    return caplog

@pytest.fixture
def wow_script_flow():
    """WOWScriptFlowのインスタンスを返すフィクスチャ"""
    return WOWScriptFlow()

def test_parse_crew_result_standard_format(wow_script_flow, caplog_for_warnings):
    """標準的な話者フォーマットを含むスクリプトが警告なしに処理されることをテスト"""
    script_content = """田中: こんにちは。
鈴木: こんばんは。
ナレーター: これはナレーションです。"""
    crew_result_json = {
        "final_script": script_content,
        "quality_guarantee": {"score": 9.5},
        "japanese_purity_score": 90,
        "character_count": len(script_content)
    }
    crew_result_str = f"```json\n{json.dumps(crew_result_json, ensure_ascii=False)}\n```"

    result = wow_script_flow._parse_crew_result(crew_result_str)

    assert result["success"] is True
    assert result["final_script"] == script_content
    assert result["japanese_purity_score"] == 90
    assert not caplog_for_warnings.records # 警告がないことを確認

def test_parse_crew_result_missing_speaker_format(wow_script_flow, caplog_for_warnings):
    """話者フォーマットが欠落しているスクリプトが警告を発生させることをテスト"""
    script_content = "こんにちは。\nこんばんは。\nこれはナレーションです。"
    crew_result_json = {
        "final_script": script_content,
        "quality_guarantee": {"score": 7.0},
        "japanese_purity_score": 75,
        "character_count": len(script_content)
    }
    crew_result_str = f"```json\n{json.dumps(crew_result_json, ensure_ascii=False)}\n```"

    result = wow_script_flow._parse_crew_result(crew_result_str)

    assert result["success"] is True
    assert result["final_script"] == script_content
    assert result["japanese_purity_score"] == 75
    assert len(caplog_for_warnings.records) == 2 # 2つの警告があることを確認
    assert "Script does not have proper speaker format" in caplog_for_warnings.records[0].message
    assert "This indicates CrewAI did not follow the output format instructions" in caplog_for_warnings.records[1].message

def test_parse_crew_result_invalid_speaker_format(wow_script_flow, caplog_for_warnings):
    """不正な話者フォーマットを含むスクリプトが警告を発生させることをテスト"""
    script_content = "田中 こんにちは。\n鈴木:: こんばんは。\nナレーター:これはナレーションです。"
    crew_result_json = {
        "final_script": script_content,
        "quality_guarantee": {"score": 6.0},
        "japanese_purity_score": 60,
        "character_count": len(script_content)
    }
    crew_result_str = f"```json\n{json.dumps(crew_result_json, ensure_ascii=False)}\n```"

    result = wow_script_flow._parse_crew_result(crew_result_str)

    assert result["success"] is True
    assert result["final_script"] == script_content
    assert result["japanese_purity_score"] == 60
    assert len(caplog_for_warnings.records) == 2 # 2つの警告があることを確認
    assert "Script does not have proper speaker format" in caplog_for_warnings.records[0].message
    assert "This indicates CrewAI did not follow the output format instructions" in caplog_for_warnings.records[1].message

def test_parse_crew_result_no_json_in_output(wow_script_flow, caplog_for_warnings):
    """CrewAIの出力にJSONが含まれていない場合のテスト"""
    crew_result_str = "これはCrewAIの生の出力です。JSONは含まれていません。"

    result = wow_script_flow._parse_crew_result(crew_result_str)

    assert result["success"] is True
    assert result["final_script"] == crew_result_str
    assert "crew_output" in result
    assert len(caplog_for_warnings.records) == 1 # 1つの警告があることを確認
    assert "No JSON found in CrewAI output, using raw text" in caplog_for_warnings.records[0].message

def test_parse_crew_result_malformed_json(wow_script_flow, caplog_for_warnings):
    """不正な形式のJSONが含まれている場合のテスト"""
    crew_result_str = '```json\n{"final_script": "テスト", "malformed": \n```'

    result = wow_script_flow._parse_crew_result(crew_result_str)

    assert result["success"] is True
    assert result["final_script"] == crew_result_str # JSONパース失敗のため、生のテキストが返される
    assert "crew_output" in result
    assert len(caplog_for_warnings.records) == 1 # 1つの警告があることを確認
    assert "Failed to parse CrewAI output as JSON" in caplog_for_warnings.records[0].message

def test_parse_crew_result_fullwidth_colon_speaker_format(wow_script_flow, caplog_for_warnings):
    """全角コロンを含む話者フォーマットが警告なしに処理されることをテスト"""
    script_content = """田中： こんにちは。
鈴木： こんばんは。
ナレーター： これはナレーションです。"""
    crew_result_json = {
        "final_script": script_content,
        "quality_guarantee": {"score": 9.8},
        "japanese_purity_score": 95,
        "character_count": len(script_content)
    }
    crew_result_str = f"```json\n{json.dumps(crew_result_json, ensure_ascii=False)}\n```"

    result = wow_script_flow._parse_crew_result(crew_result_str)

    assert result["success"] is True
    assert result["final_script"] == script_content
    assert result["japanese_purity_score"] == 95
    assert not caplog_for_warnings.records # 警告がないことを確認
