"""TTS (Text-to-Speech) module with Chain of Responsibility pattern."""
from .manager import TTSManager, split_text_for_tts, synthesize_script, tts_manager
from .providers import (
    CoquiProvider,
    ElevenLabsProvider,
    GTTSProvider,
    OpenAIProvider,
    Pyttsx3Provider,
    TTSProvider,
    VoicevoxProvider,
    create_tts_chain,
)
__all__ = [
    "TTSManager",
    "tts_manager",
    "synthesize_script",
    "split_text_for_tts",
    "TTSProvider",
    "ElevenLabsProvider",
    "VoicevoxProvider",
    "OpenAIProvider",
    "GTTSProvider",
    "CoquiProvider",
    "Pyttsx3Provider",
    "create_tts_chain",
]
