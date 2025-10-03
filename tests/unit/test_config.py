"""設定ファイルのユニットテスト"""

import pytest


@pytest.mark.unit
def test_settings_load():
    """設定が正しく読み込まれるか確認"""
    from app.config import settings

    assert settings is not None
    assert hasattr(settings, "speakers")
    assert hasattr(settings, "video")
    assert hasattr(settings, "quality_thresholds")


@pytest.mark.unit
def test_speakers_configuration():
    """話者設定が正しく読み込まれるか確認"""
    from app.config import settings

    assert len(settings.speakers) > 0, "話者が設定されていません"

    # 田中の設定確認
    tanaka = settings.get_speaker_config("田中")
    assert tanaka is not None, "田中の設定が見つかりません"
    assert hasattr(tanaka, "role")


@pytest.mark.unit
def test_video_configuration():
    """動画設定が正しく読み込まれるか確認"""
    from app.config import settings

    assert settings.video.resolution_tuple is not None
    assert len(settings.video.resolution_tuple) == 2
    assert isinstance(settings.video.resolution_tuple[0], int)
    assert isinstance(settings.video.resolution_tuple[1], int)


@pytest.mark.unit
def test_quality_thresholds():
    """品質閾値が正しく設定されているか確認"""
    from app.config import settings

    assert hasattr(settings.quality_thresholds, "wow_score_min")
    assert settings.quality_thresholds.wow_score_min > 0
    assert settings.quality_thresholds.wow_score_min <= 10


@pytest.mark.unit
def test_crewai_configuration():
    """CrewAI設定が正しく読み込まれるか確認"""
    from app.config import settings

    assert hasattr(settings.crew, "enabled")
    assert isinstance(settings.crew.enabled, bool)


@pytest.mark.unit
def test_agent_configuration():
    """エージェント設定が取得できるか確認"""
    from app.config import settings

    agent_config = settings.get_agent_config("deep_news_analyzer")

    if agent_config:
        assert hasattr(agent_config, "model")
        assert hasattr(agent_config, "temperature")
