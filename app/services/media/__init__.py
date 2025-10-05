"""Media services for video generation and enhancement."""

from .broll_generator import BRollGenerator
from .ffmpeg_support import FFmpegConfigurationError, ensure_ffmpeg_tooling
from .stock_footage_manager import StockFootageManager
from .visual_matcher import VisualMatcher

__all__ = [
    "StockFootageManager",
    "VisualMatcher",
    "BRollGenerator",
    "ensure_ffmpeg_tooling",
    "FFmpegConfigurationError",
]
