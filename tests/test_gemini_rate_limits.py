import pytest
from unittest.mock import patch, MagicMock
import os

# Assuming app.api_rotation and app.config.settings are correctly importable
from app.api_rotation import APIManager
from app.config.settings import settings

@pytest.fixture
def mock_settings_gemini():
    with patch('app.config.settings.AppSettings.load') as mock_load:
        mock_settings_instance = MagicMock()
        mock_settings_instance.api_keys.gemini = [
            "gemini_key_1", "gemini_key_2", "gemini_key_3", "gemini_key_4", "gemini_key_5"
        ]
        mock_settings_instance.api_keys.perplexity = "test_perplexity_key"
        mock_load.return_value = mock_settings_instance
        yield mock_settings_instance

@pytest.mark.asyncio
async def test_gemini_rate_limit_detection(mock_settings_gemini):
    """429エラー + 'Quota exceeded for metric'の検出"""
    api_manager = APIManager()
    with patch('google.generativeai.GenerativeModel') as mock_generative_model:
        mock_generative_model.return_value.generate_content.side_effect = Exception(
            "429 Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests limit: 50"
        )
        
        with pytest.raises(Exception) as excinfo:
            await api_manager.get_gemini_client().generate_content("test prompt")
        
        assert "Quota exceeded for metric" in str(excinfo.value)

@pytest.mark.asyncio
async def test_gemini_key_rotation(mock_settings_gemini):
    """5個のAPIキーの自動ローテーション機能"""
    api_manager = APIManager()
    # Simulate all keys hitting rate limit except the last one
    with patch('google.generativeai.GenerativeModel') as mock_generative_model:
        for i in range(len(mock_settings_gemini.api_keys.gemini) - 1):
            mock_generative_model.return_value.generate_content.side_effect = Exception(
                "429 Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests limit: 50"
            )
            with pytest.raises(Exception):
                await api_manager.get_gemini_client().generate_content("test prompt")
        
        # The last key should be used and not raise an exception (assuming it works)
        mock_generative_model.return_value.generate_content.side_effect = None
        await api_manager.get_gemini_client().generate_content("test prompt")
        
        # Verify that all keys were attempted
        assert api_manager.gemini_key_rotation_manager.current_key_index == len(mock_settings_gemini.api_keys.gemini) - 1

@pytest.mark.asyncio
async def test_gemini_daily_quota_management(mock_settings_gemini):
    """50リクエスト/日制限の管理機能"""
    api_manager = APIManager()
    with patch('google.generativeai.GenerativeModel') as mock_generative_model:
        # Simulate hitting the daily quota for the current key
        for _ in range(50):
            await api_manager.get_gemini_client().generate_content("test prompt")
        
        # Next request should trigger a quota exceeded error or key rotation
        mock_generative_model.return_value.generate_content.side_effect = Exception(
            "429 Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests limit: 50"
        )
        with pytest.raises(Exception) as excinfo:
            await api_manager.get_gemini_client().generate_content("test prompt")
        
        assert "Quota exceeded for metric" in str(excinfo.value)
