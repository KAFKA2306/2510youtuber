from __future__ import annotations

from pathlib import Path

import pytest

from app.gui.core.settings import PreferencesStore


@pytest.fixture()
def settings_files(tmp_path: Path) -> tuple[Path, Path]:
    defaults = tmp_path / "settings.yml"
    defaults.write_text(
        """
defaults:
  execution:
    mode: local
    concurrency_limit: 2
  logging:
    verbose: false
    retention_days: 7
  notifications_enabled: false
radios: {}
""".strip(),
        encoding="utf-8",
    )
    state = tmp_path / "preferences.yml"
    return defaults, state


def test_load_defaults(settings_files: tuple[Path, Path]) -> None:
    defaults_path, state_path = settings_files
    store = PreferencesStore(defaults_path, state_path)
    envelope = store.load()
    assert envelope.settings.execution.mode == "local"
    assert envelope.settings.execution.concurrency_limit == 2
    assert envelope.settings.notifications_enabled is False


def test_save_and_reload(settings_files: tuple[Path, Path]) -> None:
    defaults_path, state_path = settings_files
    store = PreferencesStore(defaults_path, state_path)
    envelope = store.load()
    updated = envelope.settings.model_copy(deep=True)
    updated.logging.verbose = True
    store.save(updated)

    reload = store.load()
    assert reload.settings.logging.verbose is True
    assert reload.settings.logging.retention_days == 7
