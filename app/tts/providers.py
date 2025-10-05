"""TTS Provider implementations using Chain of Responsibility pattern.

Each provider tries to synthesize audio and passes to the next provider on failure.
"""

import logging
import os
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Optional

import pyttsx3
import requests
from gtts import gTTS
from requests import RequestException

logger = logging.getLogger(__name__)


VOICEVOX_MANAGER_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "voicevox_manager.sh"
_VOICEVOX_BOOTSTRAP_ATTEMPTED = False


def _voicevox_auto_start_disabled() -> bool:
    flag = os.getenv("VOICEVOX_AUTO_START", "").strip().lower()
    return flag in {"0", "false", "no", "off"}


def _maybe_bootstrap_voicevox() -> None:
    global _VOICEVOX_BOOTSTRAP_ATTEMPTED

    if _VOICEVOX_BOOTSTRAP_ATTEMPTED:
        return

    if _voicevox_auto_start_disabled():
        _VOICEVOX_BOOTSTRAP_ATTEMPTED = True
        logger.debug("VOICEVOX auto-start disabled via VOICEVOX_AUTO_START")
        return

    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        _VOICEVOX_BOOTSTRAP_ATTEMPTED = True
        logger.debug("Skipping VOICEVOX auto-start during pytest runs")
        return

    if not VOICEVOX_MANAGER_SCRIPT.exists():
        _VOICEVOX_BOOTSTRAP_ATTEMPTED = True
        logger.debug("VOICEVOX manager script not found at %s", VOICEVOX_MANAGER_SCRIPT)
        return

    if shutil.which("docker") is None:
        _VOICEVOX_BOOTSTRAP_ATTEMPTED = True
        logger.debug("Docker binary not available; skipping VOICEVOX auto-start")
        return

    _VOICEVOX_BOOTSTRAP_ATTEMPTED = True

    try:
        status = subprocess.run(
            [str(VOICEVOX_MANAGER_SCRIPT), "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Failed to check VOICEVOX status via manager script: %s", exc)
        return

    if status.returncode == 0:
        logger.debug("VOICEVOX Nemo already running (manager status succeeded)")
        return

    logger.info("VOICEVOX Nemo not running; attempting to start via manager script")

    try:
        start = subprocess.run(
            [str(VOICEVOX_MANAGER_SCRIPT), "start"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Failed to start VOICEVOX Nemo via manager script: %s", exc)
        return

    if start.returncode != 0:
        stderr = (start.stderr or "").strip()
        stdout = (start.stdout or "").strip()
        logger.warning(
            "VOICEVOX Nemo start command exited with %s: %s",
            start.returncode,
            stderr or stdout,
        )
        return

    logger.info("VOICEVOX Nemo start command executed successfully")


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

    def __init__(
        self,
        port: int = 50121,
        speaker: int = 3,
        next_provider: Optional[TTSProvider] = None,
        health_cooldown_seconds: int = 300,
    ):
        super().__init__(next_provider)
        self.port = port
        self.speaker = speaker
        self._health_cooldown_seconds = max(1, health_cooldown_seconds)
        self._unhealthy_since: Optional[float] = None

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        # voice_configからvoicevox_speakerを取得（話者ごとに異なる声）
        voice_config = kwargs.get("voice_config", {})
        speaker_id = voice_config.get("voicevox_speaker", self.speaker)

        logger.debug(f"VOICEVOX synthesis: speaker_id={speaker_id}, text_length={len(text)}")

        if self._is_in_cooldown():
            logger.debug("Skipping VOICEVOX synthesis because server is marked unhealthy")
            return False

        # Health check
        if not self._server_is_healthy():
            return False

        # Generate audio query
        query_params = {"text": text, "speaker": speaker_id}
        try:
            query_response = requests.post(
                f"http://localhost:{self.port}/audio_query", params=query_params, timeout=10
            )
        except RequestException as exc:
            self._mark_unhealthy(f"Audio query request failed: {exc}")
            return False

        if query_response.status_code != 200:
            self._mark_unhealthy(f"Audio query failed: {query_response.status_code}")
            return False

        # Synthesize audio
        synthesis_params = {"speaker": speaker_id}
        try:
            synthesis_response = requests.post(
                f"http://localhost:{self.port}/synthesis",
                params=synthesis_params,
                json=query_response.json(),
                timeout=30,
            )
        except RequestException as exc:
            self._mark_unhealthy(f"Synthesis request failed: {exc}")
            return False

        if synthesis_response.status_code != 200:
            self._mark_unhealthy(f"Synthesis failed: {synthesis_response.status_code}")
            return False

        with open(output_path, "wb") as f:
            f.write(synthesis_response.content)

        self._unhealthy_since = None
        return True

    def _server_is_healthy(self) -> bool:
        try:
            health_response = requests.get(f"http://localhost:{self.port}/health", timeout=3)
        except RequestException as exc:
            self._mark_unhealthy(f"VOICEVOX health check failed: {exc}")
            _maybe_bootstrap_voicevox()
            return False

        if health_response.status_code != 200:
            self._mark_unhealthy("VOICEVOX server not healthy")
            _maybe_bootstrap_voicevox()
            return False

        return True

    def _is_in_cooldown(self) -> bool:
        if self._unhealthy_since is None:
            return False

        elapsed = time.monotonic() - self._unhealthy_since
        if elapsed < self._health_cooldown_seconds:
            return True

        self._unhealthy_since = None
        return False

    def _mark_unhealthy(self, reason: str) -> None:
        if self._unhealthy_since is None:
            logger.warning(f"✗ VOICEVOX unavailable: {reason}")
        else:
            logger.debug("VOICEVOX remains unavailable: %s", reason)
        self._unhealthy_since = time.monotonic()


class OpenAIProvider(TTSProvider):
    """OpenAI TTS provider (paid, good quality).

    Available voices:
    - alloy: Neutral and balanced
    - echo: Male voice
    - fable: British accent
    - onyx: Deep male voice
    - nova: Female voice
    - shimmer: Warm female voice
    """

    def __init__(self, client=None, next_provider: Optional[TTSProvider] = None):
        super().__init__(next_provider)
        self.client = client
        # 話者名からOpenAI voiceへのマッピング
        self.speaker_voice_map = {
            "武宏": "onyx",  # Deep male voice
            "つむぎ": "nova",  # Female voice
            "ナレーター": "alloy",  # Neutral voice
            # 旧話者名の互換性
            "田中": "onyx",
            "鈴木": "nova",
        }

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        if not self.client:
            return False

        # voice_configから話者名を取得してvoiceを選択
        voice_config = kwargs.get("voice_config", {})
        speaker_name = voice_config.get("name", "")
        openai_voice = self.speaker_voice_map.get(speaker_name, "alloy")

        logger.debug(f"OpenAI synthesis: speaker={speaker_name}, voice={openai_voice}")

        response = self.client.audio.speech.create(model="tts-1", voice=openai_voice, input=text)

        with open(output_path, "wb") as f:
            f.write(response.content)

        return True


class GTTSProvider(TTSProvider):
    """Google TTS provider (free, decent quality).

    Note: gTTS doesn't support different voices, but we can adjust speed
    to create slight variation between speakers.
    """

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        # voice_configから話者名を取得
        voice_config = kwargs.get("voice_config", {})
        speaker_name = voice_config.get("name", "")

        # 話者ごとにslowパラメータを調整（疑似的な声の違い）
        # 武宏: 通常速度, つむぎ: やや早口, ナレーター: 明瞭な速度
        slow_map = {
            "武宏": False,
            "つむぎ": False,
            "ナレーター": False,
            "田中": False,
            "鈴木": False,
        }
        use_slow = slow_map.get(speaker_name, False)

        logger.debug(f"gTTS synthesis: speaker={speaker_name}, slow={use_slow}")

        tts = gTTS(text=text, lang="ja", slow=use_slow)
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
    Attempts to use different rates/pitches for different speakers.
    """

    def __init__(self):
        super().__init__(next_provider=None)  # Final fallback
        self.engine = None
        # 話者ごとの音声パラメータ
        self.speaker_params = {
            "武宏": {"rate": 140, "volume": 0.9},  # 落ち着いた男性
            "つむぎ": {"rate": 160, "volume": 0.95},  # 活発な女性
            "ナレーター": {"rate": 150, "volume": 0.9},  # 標準的なナレーション
            # 旧話者名の互換性
            "田中": {"rate": 140, "volume": 0.9},
            "鈴木": {"rate": 160, "volume": 0.95},
        }

    async def _try_synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        if self.engine is None:
            self.engine = pyttsx3.init()

        # voice_configから話者名を取得
        voice_config = kwargs.get("voice_config", {})
        speaker_name = voice_config.get("name", "")
        params = self.speaker_params.get(speaker_name, {"rate": 150, "volume": 0.9})

        logger.debug(f"pyttsx3 synthesis: speaker={speaker_name}, rate={params['rate']}")

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

        self.engine.setProperty("rate", params["rate"])
        self.engine.setProperty("volume", params["volume"])

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
    1. VOICEVOX (free, high quality Japanese)
    2. ElevenLabs (premium)
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

    # Define providers in explicit priority order for readability.
    providers: list[TTSProvider] = [
        VoicevoxProvider(port=voicevox_port, speaker=voicevox_speaker),
        ElevenLabsProvider(client=elevenlabs_client),
        OpenAIProvider(client=openai_client),
        GTTSProvider(),
        CoquiProvider(),
        Pyttsx3Provider(),
    ]

    for current, next_provider in zip(providers, providers[1:]):
        current.next_provider = next_provider

    return providers[0]
