import pytest
from unittest.mock import patch, MagicMock
import httpx

# Assuming app.tts is correctly importable
from app.tts import TTSManager

@pytest.fixture
def mock_settings_voicevox():
    with patch('app.config.settings.AppSettings.load') as mock_load:
        mock_settings_instance = MagicMock()
        mock_settings_instance.tts.elevenlabs_enabled = False
        mock_settings_instance.tts.voicevox_enabled = True
        mock_settings_instance.tts.openai_enabled = False
        mock_settings_instance.tts.gtts_enabled = False
        mock_settings_instance.tts.voicevox.port = 50121
        mock_load.return_value = mock_settings_instance
        yield mock_settings_instance

@pytest.mark.asyncio
async def test_voicevox_server_availability(mock_settings_voicevox):
    """localhost:50121接続・ヘルスチェック"""
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        tts_manager = TTSManager()
        # Assuming there's a method to check voicevox availability
        # For now, we'll just check if the client is initialized without error
        # A more robust test would involve calling a specific health check method
        assert tts_manager.voicevox_client is not None
        mock_get.assert_called_once_with("http://localhost:50121/health")

@pytest.mark.asyncio
async def test_voicevox_tts_fallback(mock_settings_voicevox):
    """VoiceVox TTS代替処理"""
    mock_settings_voicevox.tts.elevenlabs_enabled = True
    mock_settings_voicevox.tts.openai_enabled = True
    mock_settings_voicevox.tts.gtts_enabled = True

    with patch('app.tts.AsyncElevenLabs') as mock_elevenlabs, \
         patch('app.tts.VoicevoxClient') as mock_voicevox, \
         patch('app.tts.OpenAIChatClient') as mock_openai, \
         patch('gtts.gTTS') as mock_gtts:

        # ElevenLabs fails
        mock_elevenlabs.return_value.generate.side_effect = Exception("ElevenLabs error")
        # Voicevox succeeds
        mock_voicevox.return_value.generate_audio.return_value = b"dummy_audio_data"

        tts_manager = TTSManager()
        await tts_manager.generate_speech("test_speaker", "Hello world")

        mock_elevenlabs.return_value.generate.assert_called_once()
        mock_voicevox.return_value.generate_audio.assert_called_once()
        mock_openai.return_value.generate_audio.assert_not_called()
        mock_gtts.assert_not_called()
