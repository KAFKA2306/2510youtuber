"""TTS Provider implementations using Chain of Responsibility pattern.

Each provider tries to synthesize audio and passes to the next provider on failure.
"""

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Optional

import pyttsx3
import requests
from gtts import gTTS

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    """Abstract base class for TTS providers.

    Implements Chain of Responsibility pattern for TTS fallback handling.
    """

    def __init__(self, next_provider: Optional["TTSProvider"] = None):
        """Initialize provider with optional next provider in chain.

        Args:
            next_provider: Next provider to try if this one fails
        """
        self.next_provider = next_provider

    async def synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        """Attempt to synthesize audio, falling back to next provider on failure.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            **kwargs: Provider-specific configuration

        Returns:
            True if synthesis succeeded (by this or a fallback provider), False otherwise
        """
        try:
            if await self._try_synthesize(text, output_path, **kwargs):
                logger.info(f"✓ {self.__class__.__name__} synthesis succeeded")
                return True
        except Exception as e:
            logger.warning(f"✗ {self.__class__.__name__} failed: {e}")

        # Try next provider in chain
        if self.next_provider:
            logger.debug(f"Falling back to {self.next_provider.__class__.__name__}")
            return await self.next_provider.synthesize(text, output_path, **kwargs)

        return False

    @abstractmethod
    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        """Attempt synthesis with this specific provider.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            **kwargs: Provider-specific configuration

        Returns:
            True if successful, False otherwise

        Raises:
            Exception: On synthesis error (will be caught by synthesize())
        """
        pass


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs TTS provider (premium, high quality)."""

    def __init__(self, client, next_provider: Optional[TTSProvider] = None):
        super().__init__(next_provider)
        self.client = client

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        if not self.client:
            return False

        voice_config = kwargs.get("voice_config", {})
        voice_id = voice_config.get("voice_id")

        if not voice_id or voice_id == "None":
            logger.debug("No voice_id configured for ElevenLabs")
            return False

        audio_stream = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
        )

        audio_bytes = b""
        async for chunk in audio_stream:
            audio_bytes += chunk

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return True


class VoicevoxProvider(TTSProvider):
    """VOICEVOX Nemo TTS provider (free, local, high quality Japanese)."""

    def __init__(self, port: int = 50121, speaker: int = 3, next_provider: Optional[TTSProvider] = None):
        super().__init__(next_provider)
        self.port = port
        self.speaker = speaker

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        # voice_configからvoicevox_speakerを取得（話者ごとに異なる声）
        voice_config = kwargs.get("voice_config", {})
        speaker_id = voice_config.get("voicevox_speaker", self.speaker)

        logger.debug(f"VOICEVOX synthesis: speaker_id={speaker_id}, text_length={len(text)}")

        # Health check
        health_response = requests.get(f"http://localhost:{self.port}/health", timeout=3)
        if health_response.status_code != 200:
            raise Exception("VOICEVOX server not healthy")

        # Generate audio query
        query_params = {"text": text, "speaker": speaker_id}
        query_response = requests.post(f"http://localhost:{self.port}/audio_query", params=query_params, timeout=10)

        if query_response.status_code != 200:
            raise Exception(f"Audio query failed: {query_response.status_code}")

        # Synthesize audio
        synthesis_params = {"speaker": speaker_id}
        synthesis_response = requests.post(
            f"http://localhost:{self.port}/synthesis", params=synthesis_params, json=query_response.json(), timeout=30
        )

        if synthesis_response.status_code != 200:
            raise Exception(f"Synthesis failed: {synthesis_response.status_code}")

        with open(output_path, "wb") as f:
            f.write(synthesis_response.content)

        return True


class OpenAIProvider(TTSProvider):
    """OpenAI TTS provider (paid, good quality)."""

    def __init__(self, client=None, next_provider: Optional[TTSProvider] = None):
        super().__init__(next_provider)
        self.client = client

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        if not self.client:
            return False

        response = self.client.audio.speech.create(model="tts-1", voice="nova", input=text)

        with open(output_path, "wb") as f:
            f.write(response.content)

        return True


class GTTSProvider(TTSProvider):
    """Google TTS provider (free, decent quality)."""

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        tts = gTTS(text=text, lang="ja")
        audio_buffer = BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        with open(output_path, "wb") as f:
            f.write(audio_buffer.read())

        return True


class CoquiProvider(TTSProvider):
    """Coqui TTS provider (free, local, requires CLI installation)."""

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        result = subprocess.run(
            ["tts", "--text", text, "--out_path", output_path, "--model_name", "tts_models/ja/kokoro/tacotron2-DDC"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            return True
        else:
            raise Exception(f"Coqui CLI failed: {result.stderr}")


class Pyttsx3Provider(TTSProvider):
    """Pyttsx3 TTS provider (free, always works, lowest quality).

    This is the final fallback and should not have a next_provider.
    """

    def __init__(self):
        super().__init__(next_provider=None)  # Final fallback
        self.engine = None

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        if self.engine is None:
            self.engine = pyttsx3.init()

        voices = self.engine.getProperty("voices")
        if voices:
            japanese_voice = None
            for voice in voices:
                if "japanese" in voice.name.lower() or "ja" in voice.id.lower():
                    japanese_voice = voice
                    break

            if japanese_voice:
                self.engine.setProperty("voice", japanese_voice.id)
            else:
                self.engine.setProperty("voice", voices[0].id)

        self.engine.setProperty("rate", 150)
        self.engine.setProperty("volume", 0.9)

        self.engine.save_to_file(text, output_path)
        self.engine.runAndWait()

        return True


def create_tts_chain(
    elevenlabs_client=None,
    openai_client=None,
    voicevox_port: int = 50121,
    voicevox_speaker: int = 3,
) -> TTSProvider:
    """Create the TTS provider chain.

    Chain order (highest to lowest quality):
    1. ElevenLabs (premium)
    2. VOICEVOX (free, high quality Japanese)
    3. OpenAI (paid, good quality)
    4. gTTS (free, decent quality)
    5. Coqui (free, local)
    6. pyttsx3 (free, always works)

    Args:
        elevenlabs_client: ElevenLabs client (optional)
        openai_client: OpenAI client (optional)
        voicevox_port: VOICEVOX server port
        voicevox_speaker: VOICEVOX speaker ID

    Returns:
        Head of the provider chain
    """
    # Build chain from end to start
    chain = Pyttsx3Provider()  # Final fallback
    chain = CoquiProvider(next_provider=chain)
    chain = GTTSProvider(next_provider=chain)
    chain = OpenAIProvider(client=openai_client, next_provider=chain)
    chain = VoicevoxProvider(port=voicevox_port, speaker=voicevox_speaker, next_provider=chain)
    chain = ElevenLabsProvider(client=elevenlabs_client, next_provider=chain)

    return chain
