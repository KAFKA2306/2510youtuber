"""Centralized project path resolution utilities.

This module exposes a single source of truth for filesystem layout so the
rest of the codebase can avoid hard-coded or process-relative paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class ProjectPaths:
    """Resolve well-known locations relative to the project root."""

    # Determine the repository root by climbing from this file (app/config/paths.py)
    ROOT: Path = Path(__file__).resolve().parents[2]

    # Top-level resource directories
    APP_DIR: Path = ROOT / "app"
    CONFIG_DIR: Path = ROOT / "config"
    SECRET_DIR: Path = ROOT / "secret"
    DATA_DIR: Path = ROOT / "data"
    OUTPUT_DIR: Path = ROOT / "output"
    LOGS_DIR: Path = ROOT / "logs"
    TEMP_DIR: Path = ROOT / "temp"
    ASSETS_DIR: Path = ROOT / "assets"

    CONFIG_YAML: Path = ROOT / "config.yaml"
    DOTENV_FILE: Path = ROOT / ".env"

    DEFAULT_GOOGLE_CREDENTIALS: Path = SECRET_DIR / "service-account.json"
    DEFAULT_ROBOT_ICON: Path = ASSETS_DIR / "icon" / "ChatGPT Image 2025年10月2日 19_53_38.png"

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create commonly used directories if they do not exist."""
        for path in (cls.OUTPUT_DIR, cls.LOGS_DIR, cls.TEMP_DIR, cls.DATA_DIR):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def output_path(cls, *parts: str) -> Path:
        """Build a path under the output directory."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return cls.OUTPUT_DIR.joinpath(*parts)

    @classmethod
    def data_path(cls, *parts: str) -> Path:
        """Build a path under the data directory."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return cls.DATA_DIR.joinpath(*parts)

    @classmethod
    def logs_path(cls, *parts: str) -> Path:
        """Build a path under the logs directory."""
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.LOGS_DIR.joinpath(*parts)

    @classmethod
    def temp_path(cls, *parts: str) -> Path:
        """Build a path under the temp directory."""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        return cls.TEMP_DIR.joinpath(*parts)

    @classmethod
    def resolve_relative(cls, value: str) -> Path:
        """Interpret *value* relative to the project root when not absolute."""
        candidate = Path(value)
        return candidate if candidate.is_absolute() else cls.ROOT / candidate

    @classmethod
    def resolve_google_credentials(cls, env_value: Optional[str]) -> Optional[Path]:
        """Resolve GOOGLE_APPLICATION_CREDENTIALS into a concrete path.

        The environment variable may contain an absolute path, a project-relative
        path, or be unset entirely. JSON blobs are handled elsewhere in settings.
        """

        if not env_value:
            return cls.DEFAULT_GOOGLE_CREDENTIALS if cls.DEFAULT_GOOGLE_CREDENTIALS.exists() else None

        candidate = Path(env_value)
        if candidate.exists():
            return candidate

        relative = cls.ROOT / env_value
        return relative if relative.exists() else None


# Ensure base directories exist early in the application lifecycle.
ProjectPaths.ensure_dirs()
