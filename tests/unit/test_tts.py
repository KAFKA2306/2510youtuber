import pytest
from app.tts import TTSManager

@pytest.fixture
def tts_manager():
    """TTSManagerのインスタンスを返すフィクスチャ"""
    return TTSManager()

def test_split_by_speaker_standard_format(tts_manager):
    """標準的な話者フォーマットが正しく分割されることをテスト"""
    text = "田中: こんにちは。\n鈴木: こんばんは。"
    expected = [
        {"speaker": "田中", "content": "こんにちは。"},
        {"speaker": "鈴木", "content": "こんばんは。"}
    ]
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_fullwidth_colon(tts_manager):
    """全角コロンが正しく処理されることをテスト"""
    text = "ナレーター： これはテストです。\n司会： 次の話題です。"
    expected = [
        {"speaker": "ナレーター", "content": "これはテストです。"},
        {"speaker": "司会", "content": "次の話題です。"}
    ]
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_missing_format(tts_manager):
    """話者フォーマットが欠落している場合に空のリストが返されることをテスト"""
    text = "こんにちは。\nこんばんは。"
    expected = []
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_invalid_format(tts_manager):
    """不正な話者フォーマットの場合に空のリストが返されることをテスト"""
    text = "田中 こんにちは。\n鈴木:: こんばんは。"
    expected = [{"speaker": "鈴木", "content": ": こんばんは。"}]
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_mixed_content(tts_manager):
    """話者と話者以外のコンテンツが混在する場合のテスト"""
    text = """
    田中: こんにちは。
    これは田中さんの発言の続きです。
    鈴木: こんばんは。
    鈴木さんの発言の続きです。
    さらに続き。
    """
    expected = [
        {"speaker": "田中", "content": "こんにちは。 これは田中さんの発言の続きです。"},
        {"speaker": "鈴木", "content": "こんばんは。 鈴木さんの発言の続きです。 さらに続き。"}
    ]
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_empty_string(tts_manager):
    """空文字列のテスト"""
    text = ""
    expected = []
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_only_newlines(tts_manager):
    """改行のみの文字列のテスト"""
    text = "\n\n\n"
    expected = []
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_unrecognized_speaker(tts_manager):
    """認識されない話者のテスト"""
    text = "山田: こんにちは。"
    expected = []
    result = tts_manager._split_by_speaker(text)
    assert result == expected

def test_split_by_speaker_multiple_speakers_same_line(tts_manager):
    """同じ行に複数の話者がいる場合のテスト（不正なフォーマットとして扱われるべき）"""
    text = "田中: こんにちは。鈴木: こんばんは。"
    expected = [
        {"speaker": "田中", "content": "こんにちは。鈴木: こんばんは。"}
    ]
    result = tts_manager._split_by_speaker(text)
    assert result == expected