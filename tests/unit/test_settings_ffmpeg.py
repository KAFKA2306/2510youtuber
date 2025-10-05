import importlib

import pytest


@pytest.mark.unit
def test_app_settings_load_resolves_ffmpeg(monkeypatch, tmp_path):
    fake_binary = tmp_path / "ffmpeg"
    fake_binary.write_text("#!/bin/sh\nexit 0\n")
    fake_binary.chmod(0o755)

    settings_module = importlib.import_module("app.config.settings")
    ffmpeg_support = importlib.import_module("app.services.media.ffmpeg_support")

    def fake_which(candidate):
        return str(fake_binary) if candidate == "ffmpeg" else None

    monkeypatch.setattr(settings_module.shutil, "which", fake_which)

    captured = {}

    def fake_ensure(path=None):
        captured["path"] = path
        return "/opt/tools/resolved-ffmpeg"

    monkeypatch.setattr(ffmpeg_support, "ensure_ffmpeg_tooling", fake_ensure)

    loaded = settings_module.AppSettings.load()

    assert captured["path"] == "ffmpeg"
    assert loaded.ffmpeg_path == "/opt/tools/resolved-ffmpeg"
