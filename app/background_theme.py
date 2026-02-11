"""背景テーマ管理・フィードバック改善システム
動画背景デザインのバリエーション管理、A/Bテスト、
視聴者フィードバックに基づく継続的改善を実現します。
"""
import json
import logging
import os
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
logger = logging.getLogger(__name__)
@dataclass
class BackgroundTheme:
    """背景テーマの設定"""
    name: str
    description: str
    gradient_stops: List[float]
    gradient_colors: List[Tuple[int, int, int]]
    accent_circles: List[Dict]
    grid_enabled: bool
    grid_spacing: int
    grid_opacity: int
    diagonal_lines: bool
    robot_icon_enabled: bool
    robot_icon_position: str
    robot_icon_size: Tuple[int, int]
    robot_icon_opacity: float
    title_font_size: int
    title_position_y: int
    title_shadow_layers: int
    title_glow_enabled: bool
    accent_lines_enabled: bool
    subtitle_zone_height_ratio: float
    subtitle_zone_separator: bool
    usage_count: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    avg_view_duration: float = 0.0
    avg_retention_rate: float = 0.0
    last_used: Optional[str] = None
class BackgroundThemeManager:
    """背景テーマの管理とA/Bテスト"""
    def __init__(self, themes_file: str = "config/background_themes.json"):
        self.themes_file = themes_file
        self.themes: Dict[str, BackgroundTheme] = {}
        self.analytics_file = "data/background_analytics.json"
        self._load_themes()
        self._load_analytics()
    def _load_themes(self):
        """テーマ定義を読み込み"""
        if os.path.exists(self.themes_file):
            try:
                with open(self.themes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, theme_data in data.items():
                        if "gradient_colors" in theme_data:
                            theme_data["gradient_colors"] = [tuple(c) for c in theme_data["gradient_colors"]]
                        if "robot_icon_size" in theme_data:
                            theme_data["robot_icon_size"] = tuple(theme_data["robot_icon_size"])
                        self.themes[name] = BackgroundTheme(**theme_data)
                logger.info(f"Loaded {len(self.themes)} background themes")
            except Exception as e:
                logger.error(f"Failed to load themes: {e}")
                self._create_default_themes()
        else:
            self._create_default_themes()
    def _create_default_themes(self):
        """デフォルトテーマを作成"""
        self.themes["professional_blue"] = BackgroundTheme(
            name="professional_blue",
            description="深い青のプロフェッショナルデザイン",
            gradient_stops=[0.25, 0.60, 0.80, 1.0],
            gradient_colors=[(10, 20, 35), (20, 35, 55), (15, 50, 75), (8, 25, 45), (5, 15, 30)],
            accent_circles=[
                {"pos": (-150, -150, 500, 500), "color": (0, 140, 240, 35)},
                {"pos": (-100, -100, 450, 450), "color": (0, 180, 255, 25)},
                {"pos": (-50, -50, 400, 400), "color": (100, 200, 255, 15)},
            ],
            grid_enabled=True,
            grid_spacing=120,
            grid_opacity=4,
            diagonal_lines=True,
            robot_icon_enabled=True,
            robot_icon_position="top-left",
            robot_icon_size=(200, 200),
            robot_icon_opacity=0.7,
            title_font_size=68,
            title_position_y=120,
            title_shadow_layers=5,
            title_glow_enabled=True,
            accent_lines_enabled=True,
            subtitle_zone_height_ratio=0.80,
            subtitle_zone_separator=True,
        )
        self.themes["elegant_purple"] = BackgroundTheme(
            name="elegant_purple",
            description="高級感のある紫グラデーション",
            gradient_stops=[0.25, 0.60, 0.80, 1.0],
            gradient_colors=[(30, 15, 50), (45, 20, 70), (60, 25, 90), (40, 15, 60), (25, 10, 40)],
            accent_circles=[
                {"pos": (-150, -150, 500, 500), "color": (150, 50, 255, 30)},
                {"pos": (1420, -150, 2070, 500), "color": (255, 100, 200, 25)},
                {"pos": (1470, 630, 2020, 1180), "color": (200, 50, 255, 28)},
            ],
            grid_enabled=True,
            grid_spacing=100,
            grid_opacity=5,
            diagonal_lines=False,
            robot_icon_enabled=True,
            robot_icon_position="top-right",
            robot_icon_size=(180, 180),
            robot_icon_opacity=0.65,
            title_font_size=72,
            title_position_y=100,
            title_shadow_layers=6,
            title_glow_enabled=True,
            accent_lines_enabled=True,
            subtitle_zone_height_ratio=0.82,
            subtitle_zone_separator=True,
        )
        self.themes["dynamic_green"] = BackgroundTheme(
            name="dynamic_green",
            description="活発な印象の緑系デザイン",
            gradient_stops=[0.30, 0.65, 0.82, 1.0],
            gradient_colors=[(5, 25, 15), (10, 45, 25), (15, 65, 35), (10, 40, 20), (5, 25, 12)],
            accent_circles=[
                {"pos": (-100, -100, 450, 450), "color": (50, 255, 150, 32)},
                {"pos": (1470, -100, 2020, 450), "color": (150, 255, 50, 28)},
                {"pos": (-100, 630, 450, 1180), "color": (100, 255, 100, 25)},
            ],
            grid_enabled=True,
            grid_spacing=140,
            grid_opacity=6,
            diagonal_lines=True,
            robot_icon_enabled=True,
            robot_icon_position="bottom-right",
            robot_icon_size=(220, 220),
            robot_icon_opacity=0.75,
            title_font_size=70,
            title_position_y=110,
            title_shadow_layers=5,
            title_glow_enabled=True,
            accent_lines_enabled=True,
            subtitle_zone_height_ratio=0.78,
            subtitle_zone_separator=True,
        )
        self.themes["minimal_gray"] = BackgroundTheme(
            name="minimal_gray",
            description="シンプルで洗練されたグレートーン",
            gradient_stops=[0.35, 0.70, 0.85, 1.0],
            gradient_colors=[(40, 40, 45), (55, 55, 60), (70, 70, 75), (50, 50, 55), (35, 35, 40)],
            accent_circles=[
                {"pos": (-120, -120, 480, 480), "color": (200, 200, 210, 25)},
                {"pos": (1440, 600, 2040, 1200), "color": (180, 180, 190, 22)},
            ],
            grid_enabled=False,
            grid_spacing=0,
            grid_opacity=0,
            diagonal_lines=False,
            robot_icon_enabled=True,
            robot_icon_position="top-left",
            robot_icon_size=(160, 160),
            robot_icon_opacity=0.60,
            title_font_size=75,
            title_position_y=130,
            title_shadow_layers=4,
            title_glow_enabled=False,
            accent_lines_enabled=True,
            subtitle_zone_height_ratio=0.83,
            subtitle_zone_separator=False,
        )
        self._save_themes()
    def _save_themes(self):
        """テーマをファイルに保存"""
        os.makedirs(os.path.dirname(self.themes_file) if os.path.dirname(self.themes_file) else ".", exist_ok=True)
        try:
            data = {}
            for name, theme in self.themes.items():
                theme_dict = asdict(theme)
                theme_dict["gradient_colors"] = [list(c) for c in theme_dict["gradient_colors"]]
                theme_dict["robot_icon_size"] = list(theme_dict["robot_icon_size"])
                data[name] = theme_dict
            with open(self.themes_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.themes)} themes to {self.themes_file}")
        except Exception as e:
            logger.error(f"Failed to save themes: {e}")
    def _load_analytics(self):
        """アナリティクスデータを読み込み"""
        if os.path.exists(self.analytics_file):
            try:
                with open(self.analytics_file, "r", encoding="utf-8") as f:
                    analytics = json.load(f)
                    for name, stats in analytics.items():
                        if name in self.themes:
                            theme = self.themes[name]
                            theme.usage_count = stats.get("usage_count", 0)
                            theme.positive_feedback = stats.get("positive_feedback", 0)
                            theme.negative_feedback = stats.get("negative_feedback", 0)
                            theme.avg_view_duration = stats.get("avg_view_duration", 0.0)
                            theme.avg_retention_rate = stats.get("avg_retention_rate", 0.0)
                            theme.last_used = stats.get("last_used")
                logger.info(f"Loaded analytics for {len(analytics)} themes")
            except Exception as e:
                logger.error(f"Failed to load analytics: {e}")
    def _save_analytics(self):
        """アナリティクスデータを保存"""
        os.makedirs(
            os.path.dirname(self.analytics_file) if os.path.dirname(self.analytics_file) else ".", exist_ok=True
        )
        try:
            analytics = {}
            for name, theme in self.themes.items():
                analytics[name] = {
                    "usage_count": theme.usage_count,
                    "positive_feedback": theme.positive_feedback,
                    "negative_feedback": theme.negative_feedback,
                    "avg_view_duration": theme.avg_view_duration,
                    "avg_retention_rate": theme.avg_retention_rate,
                    "last_used": theme.last_used,
                }
            with open(self.analytics_file, "w", encoding="utf-8") as f:
                json.dump(analytics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save analytics: {e}")
    def get_theme(self, name: str) -> Optional[BackgroundTheme]:
        """テーマを取得"""
        return self.themes.get(name)
    def get_best_performing_theme(self) -> BackgroundTheme:
        """最もパフォーマンスが良いテーマを取得"""
        if not self.themes:
            return None
        best_theme = None
        best_score = -float("inf")
        for theme in self.themes.values():
            if theme.usage_count < 3:
                continue
            feedback_score = theme.positive_feedback - theme.negative_feedback
            retention_weight = theme.avg_retention_rate / 100.0 if theme.avg_retention_rate > 0 else 0.5
            score = feedback_score * retention_weight
            if score > best_score:
                best_score = score
                best_theme = theme
        return best_theme or self.themes.get("professional_blue")
    def select_theme_for_ab_test(self) -> BackgroundTheme:
        """A/Bテスト用にテーマを選択（ランダム or weighted）"""
        if random.random() < 0.8:
            theme = self.get_best_performing_theme()
            if theme:
                return theme
        sorted_themes = sorted(self.themes.values(), key=lambda t: t.usage_count)
        return sorted_themes[0] if sorted_themes else self.themes["professional_blue"]
    def record_usage(self, theme_name: str):
        """テーマ使用を記録"""
        if theme_name in self.themes:
            theme = self.themes[theme_name]
            theme.usage_count += 1
            theme.last_used = datetime.now().isoformat()
            self._save_analytics()
            logger.info(f"Recorded usage for theme: {theme_name} (total: {theme.usage_count})")
    def record_feedback(self, theme_name: str, positive: bool):
        """フィードバックを記録"""
        if theme_name in self.themes:
            theme = self.themes[theme_name]
            if positive:
                theme.positive_feedback += 1
            else:
                theme.negative_feedback += 1
            self._save_analytics()
            logger.info(f"Recorded {'positive' if positive else 'negative'} feedback for: {theme_name}")
    def update_performance_metrics(self, theme_name: str, view_duration: float, retention_rate: float):
        """パフォーマンス指標を更新"""
        if theme_name in self.themes:
            theme = self.themes[theme_name]
            if theme.usage_count > 0:
                alpha = 0.3
                theme.avg_view_duration = (1 - alpha) * theme.avg_view_duration + alpha * view_duration
                theme.avg_retention_rate = (1 - alpha) * theme.avg_retention_rate + alpha * retention_rate
            else:
                theme.avg_view_duration = view_duration
                theme.avg_retention_rate = retention_rate
            self._save_analytics()
            logger.info(
                f"Updated metrics for {theme_name}: duration={view_duration:.1f}s, retention={retention_rate:.1f}%"
            )
    def get_theme_rankings(self) -> List[Dict]:
        """テーマのランキングを取得"""
        rankings = []
        for theme in self.themes.values():
            if theme.usage_count == 0:
                score = 0.0
            else:
                feedback_score = theme.positive_feedback - theme.negative_feedback
                retention_weight = theme.avg_retention_rate / 100.0 if theme.avg_retention_rate > 0 else 0.5
                score = feedback_score * retention_weight
            rankings.append(
                {
                    "name": theme.name,
                    "description": theme.description,
                    "usage_count": theme.usage_count,
                    "positive_feedback": theme.positive_feedback,
                    "negative_feedback": theme.negative_feedback,
                    "avg_retention_rate": theme.avg_retention_rate,
                    "score": score,
                    "last_used": theme.last_used,
                }
            )
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings
    def print_analytics_report(self):
        """アナリティクスレポートを出力"""
        print("\n" + "=" * 70)
        print("背景テーマ パフォーマンスレポート")
        print("=" * 70)
        rankings = self.get_theme_rankings()
        for i, rank in enumerate(rankings, 1):
            print(f"\n{i}. {rank['name']} - {rank['description']}")
            print(f"   使用回数: {rank['usage_count']}")
            print(f"   ポジティブフィードバック: {rank['positive_feedback']}")
            print(f"   ネガティブフィードバック: {rank['negative_feedback']}")
            print(f"   平均視聴維持率: {rank['avg_retention_rate']:.1f}%")
            print(f"   総合スコア: {rank['score']:.2f}")
            if rank["last_used"]:
                print(f"   最終使用: {rank['last_used']}")
        print("\n" + "=" * 70)
theme_manager = BackgroundThemeManager()
def get_theme_manager() -> BackgroundThemeManager:
    """テーママネージャーを取得"""
    return theme_manager
if __name__ == "__main__":
    manager = BackgroundThemeManager()
    print("\n利用可能なテーマ:")
    for name, theme in manager.themes.items():
        print(f"  - {name}: {theme.description}")
    print("\nA/Bテストシミュレーション:")
    for i in range(10):
        theme = manager.select_theme_for_ab_test()
        print(f"  動画
        manager.record_usage(theme.name)
        if random.random() > 0.3:
            manager.record_feedback(theme.name, positive=True)
        else:
            manager.record_feedback(theme.name, positive=False)
        view_duration = random.uniform(120, 600)
        retention_rate = random.uniform(40, 85)
        manager.update_performance_metrics(theme.name, view_duration, retention_rate)
    manager.print_analytics_report()
