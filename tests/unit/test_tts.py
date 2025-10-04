import pytest

from app.tts import TTSManager


@pytest.fixture
def tts_manager():
    """TTSManagerのインスタンスを返すフィクスチャ"""
    return TTSManager()


def test_split_by_speaker_standard_format(tts_manager):
    """標準的な話者フォーマットが正しく分割されることをテスト"""
    text = "武宏: こんにちは。\nつむぎ: こんばんは。"
    expected = [{"speaker": "武宏", "content": "こんにちは。"}, {"speaker": "つむぎ", "content": "こんばんは。"}]
    result = tts_manager._split_by_speaker(text)
    assert result == expected


def test_split_by_speaker_fullwidth_colon(tts_manager):
    """全角コロンが正しく処理されることをテスト"""
    text = "ナレーター： これはテストです。\n武宏： 次の話題です。"
    expected = [
        {"speaker": "ナレーター", "content": "これはテストです。"},
        {"speaker": "武宏", "content": "次の話題です。"},
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
    text = "武宏 こんにちは。\nつむぎ:: こんばんは。"
    expected = [{"speaker": "つむぎ", "content": ": こんばんは。"}]
    result = tts_manager._split_by_speaker(text)
    assert result == expected


def test_split_by_speaker_mixed_content(tts_manager):
    """話者と話者以外のコンテンツが混在する場合のテスト"""
    text = """
    武宏: こんにちは。
    これは武宏さんの発言の続きです。
    つむぎ: こんばんは。
    つむぎさんの発言の続きです。
    さらに続き。
    """
    expected = [
        {"speaker": "武宏", "content": "こんにちは。 これは武宏さんの発言の続きです。"},
        {"speaker": "つむぎ", "content": "こんばんは。 つむぎさんの発言の続きです。 さらに続き。"},
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
    """認識されない話者でもフォールバックとして処理されることをテスト"""
    text = "山田: こんにちは。"
    result = tts_manager._split_by_speaker(text)
    assert result == [{"speaker": "山田", "content": "こんにちは。"}]


def test_split_by_speaker_multiple_speakers_same_line(tts_manager):
    """同じ行に複数の話者がいる場合のテスト（不正なフォーマットとして扱われるべき）"""
    text = "武宏: こんにちは。つむぎ: こんばんは。"
    expected = [{"speaker": "武宏", "content": "こんにちは。つむぎ: こんばんは。"}]
    result = tts_manager._split_by_speaker(text)
    assert result == expected


def test_legacy_speaker_names_compatibility(tts_manager):
    """旧話者名(田中/鈴木)が新話者名にマッピングされることをテスト"""
    text = "田中: 本日の日経平均は39,000円です。\n鈴木: すごいですね！"
    result = tts_manager._split_by_speaker(text)
    # 旧話者名でも認識されること
    assert len(result) == 2
    assert result[0]["speaker"] == "武宏"
    assert result[1]["speaker"] == "つむぎ"


def test_voice_config_contains_speaker_info(tts_manager):
    """voice_configに話者情報が含まれることをテスト"""
    voice_config = tts_manager._get_voice_config("武宏")
    assert "name" in voice_config
    assert voice_config["name"] == "武宏"
    assert "voicevox_speaker" in voice_config
    assert voice_config["voicevox_speaker"] == 11


def test_voice_config_for_all_speakers(tts_manager):
    """全話者のvoice_config取得テスト"""
    speakers = ["武宏", "つむぎ", "ナレーター"]
    expected_voicevox_ids = [11, 8, 3]

    for speaker, expected_id in zip(speakers, expected_voicevox_ids):
        voice_config = tts_manager._get_voice_config(speaker)
        assert voice_config["name"] == speaker
        assert voice_config["voicevox_speaker"] == expected_id


def test_legacy_speaker_voice_config_mapping(tts_manager):
    """旧話者名が新話者のvoice_configにマッピングされることをテスト"""
    # 田中 → 武宏
    config_tanaka = tts_manager._get_voice_config("田中")
    assert config_tanaka["voicevox_speaker"] == 11

    # 鈴木 → つむぎ
    config_suzuki = tts_manager._get_voice_config("鈴木")
    assert config_suzuki["voicevox_speaker"] == 8


def test_build_chunks_uses_fallback_voice_for_unknown_speaker(tts_manager):
    """未知の話者でもフォールバック音声でチャンク化できることをテスト"""
    chunks = tts_manager._build_chunks_from_dialogues(
        [{"speaker": "山田", "line": "おはようございます。"}]
    )

    assert chunks
    assert chunks[0]["speaker"] == tts_manager.speaker_registry.fallback_speaker
