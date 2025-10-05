import importlib
import sys

def test_main_validates_ffmpeg_on_import(monkeypatch):
    """app.main should validate FFmpeg availability during module import."""

    # Ensure a clean import of app.main
    sys.modules.pop("app.main", None)

    # Stub API infrastructure initialization to avoid external side effects
    import app.api_rotation as api_rotation

    monkeypatch.setattr(api_rotation, "initialize_api_infrastructure", lambda: None)

    # Patch FFmpeg tooling validation to observe the startup check
    import app.services.media as media_pkg
    import app.services.media.ffmpeg_support as ffmpeg_support

    def fake_ensure(path):
        return "stub-ffmpeg"

    monkeypatch.setattr(ffmpeg_support, "ensure_ffmpeg_tooling", fake_ensure)
    monkeypatch.setattr(media_pkg, "ensure_ffmpeg_tooling", fake_ensure)

    module = importlib.import_module("app.main")

    try:
        assert getattr(module, "_STARTUP_FFMPEG_PATH") == "stub-ffmpeg"
    finally:
        # Clean up to avoid impacting other tests
        sys.modules.pop("app.main", None)
