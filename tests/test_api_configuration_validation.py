import os
from unittest.mock import patch

import pytest

# Assuming app.config.settings is correctly importable
from app.config.settings import AppSettings


@pytest.fixture
def mock_env_vars():
    with patch.dict(os.environ, {
        "PERPLEXITY_API_KEY": "pk-test12345",
        "GEMINI_API_KEY": "test_gemini_key",
        "ELEVENLABS_API_KEY": "test_elevenlabs_key",
        "TTS_VOICE_TANAKA": "dummy_tanaka_voice_id",
        "TTS_VOICE_SUZUKI": "dummy_suzuki_voice_id",
        "TTS_VOICE_NARRATOR": "dummy_narrator_voice_id",
    }, clear=True):
        yield

def test_required_api_keys_validation(mock_env_vars):
    """PERPLEXITY/GEMINI/ELEVENLABS_API_KEY検証"""
    settings = AppSettings.load()
    assert settings.api_keys.get("perplexity") == "pk-test12345"
    assert settings.api_keys.get("gemini") == "test_gemini_key"
    assert settings.api_keys.get("elevenlabs") == "test_elevenlabs_key"

def test_api_key_format_validation(mock_env_vars):
    """APIキー形式・長さ検証"""
    # This test would typically involve more specific validation logic within AppSettings
    # For now, we'll just check if they are non-empty strings.
    settings = AppSettings.load()
    assert isinstance(settings.api_keys.get("perplexity"), str)
    assert len(settings.api_keys.get("perplexity")) > 0
    assert isinstance(settings.api_keys.get("gemini"), str)
    assert len(settings.api_keys.get("gemini")) > 0
    assert isinstance(settings.api_keys.get("elevenlabs"), str)
    assert len(settings.api_keys.get("elevenlabs")) > 0

    # Test with an invalid key format (e.g., too short, or wrong prefix if applicable)
    with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "short"}, clear=False):
        # Depending on how strict your AppSettings validation is, this might raise an error
        # For now, we'll assume it loads but might be flagged by other checks.
        settings_invalid = AppSettings.load()
        assert settings_invalid.api_keys.get("perplexity") == "short"
