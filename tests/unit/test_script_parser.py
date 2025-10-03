"""TTS用スクリプト解析のユニットテスト"""

import pytest


@pytest.mark.unit
def test_tts_text_splitting(sample_script):
    """TTSテキスト分割が正しく動作するか確認"""
    from app.tts import tts_manager

    chunks = tts_manager.split_text_for_tts(sample_script)

    assert len(chunks) > 0, "チャンクが生成されていません"

    # 各チャンクの構造確認
    for chunk in chunks:
        assert "id" in chunk, "チャンクにIDがありません"
        assert "speaker" in chunk, "チャンクに話者情報がありません"
        assert "text" in chunk, "チャンクにテキストがありません"
        assert "order" in chunk, "チャンクに順序情報がありません"
        assert len(chunk["text"]) > 0, "チャンクのテキストが空です"


@pytest.mark.unit
def test_tts_speaker_extraction(sample_script):
    """話者名が正しく抽出されるか確認"""
    from app.tts import tts_manager

    chunks = tts_manager.split_text_for_tts(sample_script)
    speakers = set(chunk["speaker"] for chunk in chunks)

    assert "田中" in speakers, "田中が抽出されていません"
    assert "鈴木" in speakers, "鈴木が抽出されていません"


@pytest.mark.unit
def test_tts_empty_script():
    """空のスクリプトを処理できるか確認"""
    from app.tts import tts_manager

    chunks = tts_manager.split_text_for_tts("")

    assert len(chunks) == 0, "空のスクリプトからチャンクが生成されています"


@pytest.mark.unit
def test_tts_chunk_order():
    """チャンクの順序が保持されるか確認"""
    from app.tts import tts_manager

    test_script = """
田中: 最初の発言
鈴木: 二番目の発言
田中: 三番目の発言
"""

    chunks = tts_manager.split_text_for_tts(test_script)

    assert len(chunks) >= 3, "期待される数のチャンクが生成されていません"

    # 順序が正しいか確認
    for i, chunk in enumerate(chunks):
        assert chunk["order"] == i, f"チャンク{i}の順序が不正です"
