"""Dependency wiring for the GUI FastAPI application."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.gui.core import settings as settings_module
from app.gui.core.settings import GuiSettingsEnvelope, PreferencesStore
from app.gui.dashboard.service import DashboardService
from app.gui.jobs.manager import JobManager
from app.gui.jobs.registry import CommandRegistry
from app.gui.prompts import models as prompt_models  # noqa: F401 - ensure table registration
from app.gui.prompts.repository import PromptRepository

DEFAULT_COMMANDS_PATH = Path("config/gui/commands.yml")
DEFAULT_LOG_DIR = Path("logs/gui_jobs")
DEFAULT_PROMPTS_DB_PATH = Path("state/gui/prompts.db")
DEFAULT_PROMPTS_BASE_PATH = Path("data/prompts")
DEFAULT_EXECUTION_LOG_PATH = Path("output/execution_log.jsonl")
DEFAULT_METADATA_HISTORY_PATH = Path("data/metadata_history.csv")


@lru_cache()
def get_command_registry(path: Path | None = None) -> CommandRegistry:
    return CommandRegistry.from_yaml(path or DEFAULT_COMMANDS_PATH)


@lru_cache()
def _get_preferences_store_cached(
    defaults_path: Path = settings_module.DEFAULT_SETTINGS_PATH,
    state_path: Path = settings_module.DEFAULT_STATE_PATH,
) -> PreferencesStore:
    return settings_module.get_preferences_store(defaults_path=defaults_path, state_path=state_path)


def get_preferences_store() -> PreferencesStore:
    return _get_preferences_store_cached()


def get_settings(store: PreferencesStore = Depends(get_preferences_store)) -> GuiSettingsEnvelope:
    return store.load()


_JOB_MANAGER: JobManager | None = None
def get_job_manager(
    registry: CommandRegistry = Depends(get_command_registry),
) -> JobManager:
    global _JOB_MANAGER
    if _JOB_MANAGER is None:
            _JOB_MANAGER = JobManager(registry=registry, log_dir=DEFAULT_LOG_DIR)
    return _JOB_MANAGER


@lru_cache()
def _get_prompt_engine(db_path: Path) -> Engine:
    normalized = db_path.expanduser().resolve()
    normalized.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{normalized}", echo=False, future=True)
    SQLModel.metadata.create_all(engine)
    return engine


@lru_cache()
def get_prompt_repository(
    db_path: Path | None = None,
    base_path: Path | None = None,
) -> PromptRepository:
    engine = _get_prompt_engine((db_path or DEFAULT_PROMPTS_DB_PATH))
    target_base = (base_path or DEFAULT_PROMPTS_BASE_PATH).expanduser().resolve()
    target_base.mkdir(parents=True, exist_ok=True)

    def session_factory() -> Session:
        return Session(engine)

    return PromptRepository(session_factory=session_factory, base_path=target_base)


@lru_cache()
def get_dashboard_service(
    execution_log_path: Path | None = None,
    metadata_history_path: Path | None = None,
) -> DashboardService:
    return DashboardService(
        execution_log_path=(execution_log_path or DEFAULT_EXECUTION_LOG_PATH).expanduser().resolve(),
        metadata_history_path=(metadata_history_path or DEFAULT_METADATA_HISTORY_PATH).expanduser().resolve(),
    )
