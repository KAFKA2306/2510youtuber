"""Media processing utilities and services."""

from .align_subtitles import SubtitleAligner
from .background_theme import BackgroundThemeManager
from .stt import STTManager as SpeechToTextEngine, transcribe_long_audio
from .stt_fallback import STTFallbackManager as BasicTranscriber
from .thumbnail import ThumbnailGenerator
from .video import VideoGenerator
from .video_feedback import VideoFeedbackCollector as VideoFeedbackAnalyzer

__all__ = [
    "SubtitleAligner",
    "BackgroundThemeManager",
    "SpeechToTextEngine",
    "transcribe_long_audio",
    "BasicTranscriber",
    "ThumbnailGenerator",
    "VideoGenerator",
    "VideoFeedbackAnalyzer",
]
