"""Tests for unified visual design thumbnail style selection."""

from app.background_theme import BackgroundTheme
from app.services import visual_design
from app.services.visual_design import UnifiedVisualDesign


def _make_theme(name: str) -> BackgroundTheme:
    """Create a minimal BackgroundTheme for testing."""

    return BackgroundTheme(
        name=name,
        description="",
        gradient_stops=[0.25, 0.6, 0.8, 1.0],
        gradient_colors=[(10, 20, 30), (20, 30, 40), (30, 40, 50), (40, 50, 60), (50, 60, 70)],
        accent_circles=[],
        grid_enabled=False,
        grid_spacing=0,
        grid_opacity=0,
        diagonal_lines=False,
        robot_icon_enabled=True,
        robot_icon_position="top-left",
        robot_icon_size=(100, 100),
        robot_icon_opacity=1.0,
        title_font_size=60,
        title_position_y=120,
        title_shadow_layers=3,
        title_glow_enabled=False,
        accent_lines_enabled=False,
        subtitle_zone_height_ratio=0.8,
        subtitle_zone_separator=False,
    )


def test_get_thumbnail_style_prefers_theme_mapping():
    """Explicit thumbnail_style should be returned even if sentiment differs."""

    theme = _make_theme("professional_blue")
    design = UnifiedVisualDesign(
        theme_name=theme.name,
        background_theme=theme,
        sentiment="positive",
        primary_color=(0, 0, 0),
        accent_color=(0, 0, 0),
        text_color=(255, 255, 255),
        thumbnail_style="economic_blue",
    )

    assert design.get_thumbnail_style() == "economic_blue"


def test_get_thumbnail_style_falls_back_to_sentiment():
    """When no theme mapping is present, sentiment fallback is used."""

    theme = _make_theme("professional_blue")
    design = UnifiedVisualDesign(
        theme_name=theme.name,
        background_theme=theme,
        sentiment="negative",
        primary_color=(0, 0, 0),
        accent_color=(0, 0, 0),
        text_color=(255, 255, 255),
    )

    assert design.get_thumbnail_style() == "market_red"


def test_create_from_news_uses_theme_specific_style(monkeypatch):
    """create_from_news should attach a theme-appropriate thumbnail style."""

    base_theme = _make_theme("professional_blue")

    class _StubThemeManager:
        def get_theme(self, name: str):
            return base_theme if name == base_theme.name else None

        def select_theme_for_ab_test(self):
            return base_theme

    monkeypatch.setattr(visual_design, "get_theme_manager", lambda: _StubThemeManager())

    news_items = [{"title": "株価が上昇"}]
    script_content = "世界的に株価が上昇し投資家心理も改善している。"

    design = UnifiedVisualDesign.create_from_news(news_items, script_content, mode="daily")

    assert design.thumbnail_style == "economic_blue"
