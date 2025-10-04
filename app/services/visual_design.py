"""統一ビジュアルデザインシステム

サムネイルと動画の視覚的統一性を確保するための共通デザイン管理システム。
ニュース内容の感情分析に基づいて最適なテーマ・カラーを自動選択します。
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.background_theme import BackgroundTheme, get_theme_manager

logger = logging.getLogger(__name__)


@dataclass
class UnifiedVisualDesign:
    """サムネイルと動画で共有するビジュアルデザイン設定

    Attributes:
        theme_name: 使用するテーマ名
        background_theme: BackgroundThemeオブジェクト (動画用)
        sentiment: ニュースの感情 ("positive", "negative", "neutral")
        primary_color: メインカラー (R, G, B)
        accent_color: アクセントカラー (R, G, B)
        text_color: テキストカラー (R, G, B)
        subtitle_font_size: 字幕フォントサイズ (px)
        thumbnail_title_font_size: サムネイルタイトルフォントサイズ (px)
        robot_icon_enabled: ロボットアイコン表示フラグ
        robot_icon_path: ロボットアイコン画像パス
    """

    theme_name: str
    background_theme: BackgroundTheme
    sentiment: str

    # カラーパレット (サムネイル + 動画共通)
    primary_color: Tuple[int, int, int]
    accent_color: Tuple[int, int, int]
    text_color: Tuple[int, int, int]

    # フォント設定
    subtitle_font_size: int = 48
    thumbnail_title_font_size: int = 72

    # ブランディング
    robot_icon_enabled: bool = True
    robot_icon_path: str = "/home/kafka/projects/youtuber/assets/icon/ChatGPT Image 2025年10月2日 19_53_38.png"

    @classmethod
    def create_from_news(
        cls, news_items: List[Dict], script_content: str, mode: str = "daily"
    ) -> "UnifiedVisualDesign":
        """ニュース内容から最適なデザインを生成

        Args:
            news_items: ニュースアイテムのリスト
            script_content: 生成された台本テキスト
            mode: 動画モード (daily/special/breaking)

        Returns:
            UnifiedVisualDesign: 統一ビジュアルデザイン設定
        """
        # 感情分析
        sentiment = cls._analyze_sentiment(news_items, script_content)

        # テーママネージャーから最適なテーマを取得
        theme_manager = get_theme_manager()

        # 感情に基づいてテーマとカラーを選択
        if sentiment == "positive":
            # ポジティブ: 緑系のテーマを優先（存在すれば）
            theme = theme_manager.get_theme("modern_growth")
            if not theme:
                theme = theme_manager.select_theme_for_ab_test()
            primary = (0, 180, 80)  # 緑（成長）
            accent = (255, 215, 0)  # 金色（ポジティブ）

        elif sentiment == "negative":
            # ネガティブ: 警告系のテーマを優先（存在すれば）
            theme = theme_manager.get_theme("professional_alert")
            if not theme:
                theme = theme_manager.select_theme_for_ab_test()
            primary = (255, 70, 70)  # 赤（警告）
            accent = (255, 165, 0)  # オレンジ（注意）

        else:  # neutral
            # ニュートラル: A/Bテストで最適なテーマを選択
            theme = theme_manager.select_theme_for_ab_test()
            primary = (0, 120, 215)  # 青（信頼）
            accent = (255, 215, 0)  # 金色（クリック誘導）

        logger.info(f"Selected visual design: theme={theme.name}, sentiment={sentiment}")

        return cls(
            theme_name=theme.name,
            background_theme=theme,
            sentiment=sentiment,
            primary_color=primary,
            accent_color=accent,
            text_color=(255, 255, 255),  # 白（視認性最強）
        )

    @staticmethod
    def _analyze_sentiment(news_items: List[Dict], script_content: str) -> str:
        """ニュースと台本の感情を分析

        Args:
            news_items: ニュースアイテムのリスト
            script_content: 台本テキスト

        Returns:
            str: "positive", "negative", or "neutral"
        """
        # ポジティブ・ネガティブキーワード
        positive_keywords = [
            "上昇",
            "成長",
            "好調",
            "増加",
            "利益",
            "改善",
            "回復",
            "拡大",
            "上方修正",
            "最高",
            "記録",
            "達成",
            "成功",
            "躍進",
            "好転",
        ]
        negative_keywords = [
            "下落",
            "減少",
            "不調",
            "懸念",
            "リスク",
            "低迷",
            "悪化",
            "縮小",
            "下方修正",
            "最低",
            "損失",
            "失敗",
            "後退",
            "悪化",
            "警戒",
        ]

        # ニュースタイトルと台本を結合して分析
        text = script_content.lower()
        for item in news_items:
            if isinstance(item, dict):
                text += " " + item.get("title", "").lower()
                text += " " + item.get("content", "").lower()

        # キーワード出現回数をカウント
        positive_count = sum(1 for kw in positive_keywords if kw in text)
        negative_count = sum(1 for kw in negative_keywords if kw in text)

        logger.debug(f"Sentiment analysis: positive={positive_count}, negative={negative_count}")

        # 判定
        if positive_count > negative_count + 1:  # 閾値1で余裕を持たせる
            return "positive"
        elif negative_count > positive_count + 1:
            return "negative"
        return "neutral"

    def get_thumbnail_style(self) -> str:
        """サムネイル用のカラースキーム名を取得

        Returns:
            str: カラースキーム名 ("economic_blue", "financial_green", "market_red")
        """
        if self.sentiment == "positive":
            return "financial_green"
        elif self.sentiment == "negative":
            return "market_red"
        return "economic_blue"

    def to_dict(self) -> Dict:
        """辞書形式に変換（contextへの保存用）

        Returns:
            Dict: シリアライズ可能な辞書
        """
        return {
            "theme_name": self.theme_name,
            "sentiment": self.sentiment,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "text_color": self.text_color,
            "subtitle_font_size": self.subtitle_font_size,
            "thumbnail_title_font_size": self.thumbnail_title_font_size,
            "robot_icon_enabled": self.robot_icon_enabled,
            "robot_icon_path": self.robot_icon_path,
        }


def create_unified_design(news_items: List[Dict], script_content: str, mode: str = "daily") -> UnifiedVisualDesign:
    """統一ビジュアルデザインを生成（簡易関数）

    Args:
        news_items: ニュースアイテムのリスト
        script_content: 台本テキスト
        mode: 動画モード

    Returns:
        UnifiedVisualDesign: 統一ビジュアルデザイン設定
    """
    return UnifiedVisualDesign.create_from_news(news_items, script_content, mode)
