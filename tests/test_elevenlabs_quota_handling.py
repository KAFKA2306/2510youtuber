import pytest
from unittest.mock import patch, MagicMock
import os

# Assuming app.tts and app.config.settings are correctly importable
# You might need to adjust these imports based on your actual project structure
from app.tts import TTSManager
from app.config.settings import settings

@pytest.fixture
def mock_settings():
    with patch('app.config.settings.AppSettings.load') as mock_load:
        mock_settings_instance = MagicMock()
        mock_settings_instance.tts.elevenlabs_enabled = True
        mock_settings_instance.tts.voicevox_enabled = False
        mock_settings_instance.tts.openai_enabled = False
        mock_settings_instance.tts.gtts_enabled = False
        mock_settings_instance.api_keys.elevenlabs = "test_elevenlabs_key"
        mock_load.return_value = mock_settings_instance
        yield mock_settings_instance

@pytest.mark.asyncio
async def test_elevenlabs_quota_exceeded_detection(mock_settings):
    """401エラー + 'quota_exceeded'メッセージの検出"""
    with patch('app.tts.AsyncElevenLabs') as mock_elevenlabs:
        # Simulate a 401 error with quota_exceeded message
        mock_elevenlabs.return_value.generate.side_effect = Exception(
            "HTTP status code 401: {'status': 'quota_exceeded', 'message': 'This request exceeds your quota'}"
        )
        tts_manager = TTSManager()
        
        with pytest.raises(Exception) as excinfo:
            await tts_manager.generate_speech("test_speaker", "Hello world")
        
        assert "quota_exceeded" in str(excinfo.value)
        mock_elevenlabs.return_value.generate.assert_called_once()

@pytest.mark.asyncio
async def test_tts_fallback_mechanism(mock_settings):
    """ElevenLabs → VoiceVox → OpenAI → gTTSの多段階フォールバック"""
    # Configure settings for fallback testing
    mock_settings.tts.elevenlabs_enabled = True
    mock_settings.tts.voicevox_enabled = True
    mock_settings.tts.openai_enabled = True
    mock_settings.tts.gtts_enabled = True
    mock_settings.api_keys.elevenlabs = "test_elevenlabs_key"
    mock_settings.api_keys.openai = "test_openai_key"

    with patch('app.tts.AsyncElevenLabs') as mock_elevenlabs, \
         patch('app.tts.VoicevoxClient') as mock_voicevox, \
         patch('app.tts.OpenAIChatClient') as mock_openai, \
         patch('gtts.gTTS') as mock_gtts:

        # ElevenLabs fails with quota exceeded
        mock_elevenlabs.return_value.generate.side_effect = Exception(
            "HTTP status code 401: {'status': 'quota_exceeded', 'message': 'This request exceeds your quota'}"
        )
        # Voicevox fails
        mock_voicevox.return_value.generate_audio.side_effect = Exception("Voicevox error")
        # OpenAI fails
        mock_openai.return_value.generate_audio.side_effect = Exception("OpenAI error")
        # gTTS succeeds
        mock_gtts.return_value.save.return_value = None # gTTS.save doesn't return anything

        tts_manager = TTSManager()
        
        # Expect no exception as gTTS should succeed
        await tts_manager.generate_speech("test_speaker", "Hello world")
        
        mock_elevenlabs.return_value.generate.assert_called_once()
        mock_voicevox.return_value.generate_audio.assert_called_once()
        mock_openai.return_value.generate_audio.assert_called_once()
        mock_gtts.assert_called_once() # gTTS is a class, so assert on the class itself

@pytest.mark.asyncio
async def test_tts_credit_monitoring(mock_settings):
    """クレジット残高0の事前検出"""
    with patch('app.tts.AsyncElevenLabs') as mock_elevenlabs:
        # Simulate credit check returning 0
        mock_elevenlabs.return_value.get_remaining_characters.return_value = 0
        
        tts_manager = TTSManager()
        
        # Should raise an exception or handle gracefully if credits are 0
        with pytest.raises(Exception) as excinfo:
            await tts_manager.generate_speech("test_speaker", "Hello world")
        
        assert "ElevenLabs credits are 0" in str(excinfo.value)
        mock_elevenlabs.return_value.get_remaining_characters.assert_called_once()