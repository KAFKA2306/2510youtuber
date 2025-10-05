"""Settings management for the GUI backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping, Optional

import yaml
from pydantic import BaseModel, Field, PositiveInt, model_validator


class ExecutionSettings(BaseModel):
    """Execution related preferences exposed to the GUI."""

    mode: Literal["local", "container"] = Field(
        default="local",
        description="Preferred execution environment for workflow commands.",
    )
    concurrency_limit: PositiveInt = Field(
        default=1,
        description="Number of jobs allowed to run concurrently.",
    )


class LoggingSettings(BaseModel):
    """Logging related configuration toggles."""

    verbose: bool = Field(
        default=False,
        description="Enable verbose logging for launched commands.",
    )
    retention_days: PositiveInt = Field(
        default=14,
        description="Number of days to retain job logs on disk.",
    )


class GuiSettings(BaseModel):
    """Aggregate GUI preferences consumed by the backend."""

    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    notifications_enabled: bool = Field(
        default=False,
        description="Whether desktop notifications should be sent on job completion.",
    )

    @model_validator(mode="after")
    def _validate_container(self) -> "GuiSettings":
        if self.execution.mode == "container" and self.execution.concurrency_limit > 1:
            object.__setattr__(self.execution, "concurrency_limit", 1)
        return self


class RadioOption(BaseModel):
    """Display metadata for a radio-button option."""

    id: str
    label: str
    description: Optional[str] = None


class RadioToggle(BaseModel):
    """Metadata describing a radio button configuration."""

    id: str
    label: str
    options: list[RadioOption]
    default: str


class SettingsDocument(BaseModel):
    """Full settings document loaded from ``config/gui/settings.yml``."""

    defaults: GuiSettings
    radios: dict[str, RadioToggle] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "SettingsDocument":
        if not path.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Settings file must contain a top-level mapping")
        defaults = data.get("defaults", {})
        radios = data.get("radios", {})
        return cls(
            defaults=GuiSettings.model_validate(defaults),
            radios={key: RadioToggle.model_validate(value) for key, value in radios.items()},
        )


class GuiSettingsEnvelope(BaseModel):
    """Return type combining settings values and radio metadata."""

    settings: GuiSettings
    radios: dict[str, RadioToggle] = Field(default_factory=dict)


class PreferencesStore:
    """Persisted GUI preferences.

    The defaults are sourced from ``config/gui/settings.yml`` and user overrides
    are stored in ``state/gui/preferences.yml``.
    """

    def __init__(self, defaults_path: Path, state_path: Path) -> None:
        self._defaults_path = defaults_path
        self._state_path = state_path
        self._document: Optional[SettingsDocument] = None

    def _load_document(self) -> SettingsDocument:
        if self._document is None:
            self._document = SettingsDocument.from_yaml(self._defaults_path)
        return self._document

    def load(self) -> GuiSettingsEnvelope:
        document = self._load_document()
        settings_dict = document.defaults.model_dump()
        if self._state_path.exists():
            raw = yaml.safe_load(self._state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                _deep_update(settings_dict, raw)
        settings = GuiSettings.model_validate(settings_dict)
        return GuiSettingsEnvelope(settings=settings, radios=document.radios)

    def save(self, settings: GuiSettings) -> GuiSettingsEnvelope:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump()
        self._state_path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        document = self._load_document()
        document.defaults = settings
        return GuiSettingsEnvelope(settings=settings, radios=document.radios)


DEFAULT_SETTINGS_PATH = Path("config/gui/settings.yml")
DEFAULT_STATE_PATH = Path("state/gui/preferences.yml")


def get_preferences_store(
    *,
    defaults_path: Path = DEFAULT_SETTINGS_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
) -> PreferencesStore:
    """Construct a :class:`PreferencesStore` using repository defaults."""

    return PreferencesStore(defaults_path=defaults_path, state_path=state_path)


def _deep_update(base: dict[str, Any], updates: Mapping[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
