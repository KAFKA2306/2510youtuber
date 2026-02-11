"""Dependency Injection Container for YouTube Video Generation System.
Provides centralized dependency management and allows easy testing with mock objects.
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)
class AppContainer:
    """Application-wide dependency injection container.
    Singleton pattern for managing service instances throughout the application lifecycle.
    """
    _instance: Optional["AppContainer"] = None
    def __init__(self):
        """Initialize container with lazy-loaded dependencies."""
        self._tts_manager = None
        self._video_generator = None
        self._metadata_storage = None
        self._sheets_manager = None
        self._discord_notifier = None
        self._workflow = None
        logger.info("AppContainer initialized (lazy loading enabled)")
    @classmethod
    def get_instance(cls) -> "AppContainer":
        """Get or create singleton instance.
        Returns:
            Singleton AppContainer instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (useful for testing)."""
        cls._instance = None
    @property
    def tts_manager(self):
        """Get TTS manager instance (lazy-loaded)."""
        if self._tts_manager is None:
            from app.tts import TTSManager
            self._tts_manager = TTSManager()
            logger.debug("TTSManager created")
        return self._tts_manager
    def set_tts_manager(self, manager):
        """Set TTS manager (for testing/DI)."""
        self._tts_manager = manager
    @property
    def video_generator(self):
        """Get video generator instance (lazy-loaded)."""
        if self._video_generator is None:
            from app.video import VideoGenerator
            self._video_generator = VideoGenerator()
            logger.debug("VideoGenerator created")
        return self._video_generator
    def set_video_generator(self, generator):
        """Set video generator (for testing/DI)."""
        self._video_generator = generator
    @property
    def metadata_storage(self):
        """Get metadata storage instance (lazy-loaded)."""
        if self._metadata_storage is None:
            from app.metadata_storage import MetadataStorage
            self._metadata_storage = MetadataStorage()
            logger.debug("MetadataStorage created")
        return self._metadata_storage
    def set_metadata_storage(self, storage):
        """Set metadata storage (for testing/DI)."""
        self._metadata_storage = storage
    @property
    def sheets_manager(self):
        """Get sheets manager instance (lazy-loaded)."""
        if self._sheets_manager is None:
            from app.config import settings
            if settings.google_sheet_id:
                from app.sheets import SheetsManager
                self._sheets_manager = SheetsManager()
                logger.debug("SheetsManager created")
            else:
                logger.debug("SheetsManager disabled (no google_sheet_id)")
                self._sheets_manager = None
        return self._sheets_manager
    def set_sheets_manager(self, manager):
        """Set sheets manager (for testing/DI)."""
        self._sheets_manager = manager
    @property
    def discord_notifier(self):
        """Get discord notifier instance (lazy-loaded)."""
        if self._discord_notifier is None:
            from app.discord import DiscordNotifier
            self._discord_notifier = DiscordNotifier()
            logger.debug("DiscordNotifier created")
        return self._discord_notifier
    def set_discord_notifier(self, notifier):
        """Set discord notifier (for testing/DI)."""
        self._discord_notifier = notifier
    @property
    def workflow(self):
        """Get workflow instance (lazy-loaded)."""
        if self._workflow is None:
            from app.main import YouTubeWorkflow
            self._workflow = YouTubeWorkflow(notifier=self.discord_notifier)
            logger.debug("YouTubeWorkflow created")
        return self._workflow
    def set_workflow(self, workflow):
        """Set workflow (for testing/DI)."""
        self._workflow = workflow
container = AppContainer.get_instance()
def get_container() -> AppContainer:
    """Get the global container instance.
    Returns:
        AppContainer singleton instance
    """
    return AppContainer.get_instance()
