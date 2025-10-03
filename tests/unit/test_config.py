"""設定ファイルのユニットテスト"""

import pytest


@pytest.mark.unit
def test_settings_load():
    from app.config.settings import settings

    assert settings is not None
    assert hasattr(settings, "speakers")
    assert hasattr(settings, "video")
    assert hasattr(settings, "quality")  # Changed from quality_thresholds to quality


@pytest.mark.unit
def test_speakers_configuration():
    """話者設定が正しく読み込まれるか確認"""
    from app.config.settings import settings

    assert len(settings.speakers) > 0, "話者が設定されていません"

    # 田中の設定確認 - tts_voice_configs dict経由でアクセス
    assert "田中" in settings.tts_voice_configs, "田中の設定が見つかりません"
    tanaka = settings.tts_voice_configs["田中"]
    assert hasattr(tanaka, "role")


@pytest.mark.unit
def test_video_configuration():
    """動画設定が正しく読み込まれるか確認"""
    from app.config.settings import settings

    assert settings.video.resolution is not None
    assert settings.video.resolution.width > 0
    assert settings.video.resolution.height > 0
    assert isinstance(settings.video.resolution.width, int)
    assert isinstance(settings.video.resolution.height, int)


@pytest.mark.unit
def test_quality_thresholds():
    """品質閾値が正しく設定されているか確認"""
    from app.config.settings import settings

    assert hasattr(settings.quality, "wow_score_min")  # Changed from quality_thresholds to quality
    assert settings.quality.wow_score_min > 0
    assert settings.quality.wow_score_min <= 10


@pytest.mark.unit
def test_crewai_configuration():
    """CrewAI設定が正しく読み込まれるか確認"""
    from app.config.settings import settings

    assert hasattr(settings.crew, "enabled")
    assert isinstance(settings.crew.enabled, bool)


@pytest.mark.unit
def test_agent_configuration():
    """エージェント設定が取得できるか確認"""
    import os

    import yaml

    # Load agent config directly from config.yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if "crew" in config and "agents" in config["crew"]:
        assert "deep_news_analyzer" in config["crew"]["agents"]
        agent_config = config["crew"]["agents"]["deep_news_analyzer"]
        assert "model" in agent_config
        assert "temperature" in agent_config
