"""サムネイル生成モジュール

YouTube動画用の魅力的なサムネイル画像を自動生成します。
視覚的インパクトとクリック率向上を目的とした高品質なサムネイルを作成します。
"""

import logging
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """サムネイル生成クラス"""

    def __init__(self):
        self.output_size = (1280, 720)  # YouTube推奨サイズ
        self.font_paths = self._get_available_fonts()
        self.color_schemes = self._load_color_schemes()

        try:
            from PIL import Image, ImageDraw, ImageFont

            self.has_pil = True
            logger.info("Thumbnail generator initialized with PIL")
        except ImportError:
            self.has_pil = False
            logger.warning("PIL not available, thumbnail generation will be limited")

    def _get_available_fonts(self) -> Dict[str, str]:
        """利用可能なフォントパスを取得"""
        font_paths = {}

        # システムフォントパスの候補
        font_candidates = [
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Bold.ttc",
            # macOS
            "/System/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]

        for font_path in font_candidates:
            if os.path.exists(font_path):
                font_name = Path(font_path).stem.lower()
                font_paths[font_name] = font_path

        return font_paths

    def _load_color_schemes(self) -> Dict[str, Dict[str, Any]]:
        """カラースキームを定義"""
        return {
            "economic_blue": {
                "background": (25, 35, 45),
                "primary": (70, 130, 180),
                "secondary": (255, 255, 255),
                "accent": (255, 215, 0),
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 180),
            },
            "financial_green": {
                "background": (15, 45, 25),
                "primary": (50, 150, 80),
                "secondary": (255, 255, 255),
                "accent": (255, 193, 7),
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 180),
            },
            "market_red": {
                "background": (45, 15, 15),
                "primary": (220, 50, 47),
                "secondary": (255, 255, 255),
                "accent": (255, 165, 0),
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 180),
            },
            "neutral_gray": {
                "background": (40, 40, 40),
                "primary": (128, 128, 128),
                "secondary": (255, 255, 255),
                "accent": (0, 191, 255),
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 180),
            },
        }

    def generate_thumbnail(
        self,
        title: str,
        news_items: List[Dict[str, Any]] = None,
        mode: str = "daily",
        style: str = "economic_blue",
        output_path: str = None,
    ) -> str:
        """サムネイル画像を生成

        Args:
            title: メインタイトルテキスト
            news_items: ニュース項目（サブテキスト用）
            mode: 動画モード (daily/special/breaking)
            style: カラースキーム
            output_path: 出力パス

        Returns:
            生成されたサムネイル画像のパス

        """
        try:
            if not self.has_pil:
                return self._generate_fallback_thumbnail(title, output_path)

            from PIL import Image

            # 出力パスを決定
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"thumbnail_{timestamp}.png"

            # 画像を作成
            image = Image.new("RGB", self.output_size, self.color_schemes[style]["background"])

            # 背景グラデーション/パターンを追加
            image = self._add_background_effects(image, style, mode)

            # テキストを描画
            image = self._draw_text_elements(image, title, news_items, style, mode)

            # 装飾要素を追加
            image = self._add_decorative_elements(image, style, mode)

            # 品質最適化
            image = self._optimize_image_quality(image)

            # 保存
            image.save(output_path, "PNG", quality=95)

            logger.info(f"Thumbnail generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return self._generate_fallback_thumbnail(title, output_path)

    def _add_background_effects(self, image, style: str, mode: str):
        """背景エフェクトを追加"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        colors = self.color_schemes[style]
        width, height = self.output_size

        try:
            # グラデーション背景
            for y in range(height):
                # 縦方向のグラデーション
                ratio = y / height
                if mode == "breaking":
                    # 緊急感のある急激なグラデーション
                    r = int(colors["background"][0] + (colors["primary"][0] - colors["background"][0]) * ratio * 2)
                    g = int(colors["background"][1] + (colors["primary"][1] - colors["background"][1]) * ratio * 0.5)
                    b = int(colors["background"][2] + (colors["primary"][2] - colors["background"][2]) * ratio * 0.8)
                else:
                    # 通常のスムーズなグラデーション
                    r = int(colors["background"][0] + (colors["primary"][0] - colors["background"][0]) * ratio * 0.3)
                    g = int(colors["background"][1] + (colors["primary"][1] - colors["background"][1]) * ratio * 0.3)
                    b = int(colors["background"][2] + (colors["primary"][2] - colors["background"][2]) * ratio * 0.3)

                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))

                draw.line([(0, y), (width, y)], fill=(r, g, b))

            # 幾何学模様を追加
            self._add_geometric_patterns(draw, colors, mode)

        except Exception as e:
            logger.warning(f"Failed to add background effects: {e}")

        return image

    def _add_geometric_patterns(self, draw, colors: Dict, mode: str):
        """幾何学模様を追加"""
        width, height = self.output_size

        try:
            if mode == "breaking":
                # 緊急感のある斜線
                for i in range(0, width + height, 60):
                    draw.line([(i, 0), (i - height, height)], fill=(*colors["accent"], 30), width=3)
            elif mode == "special":
                # 特集感のある円形
                center_x, center_y = width // 4, height // 4
                for radius in range(50, 200, 25):
                    draw.ellipse(
                        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                        outline=(*colors["primary"], 40),
                        width=2,
                    )
            else:
                # 日常的な矩形パターン
                for i in range(3):
                    x = width - 150 + i * 20
                    y = height - 100 + i * 15
                    draw.rectangle([x, y, x + 100, y + 60], outline=(*colors["primary"], 60), width=2)

        except Exception as e:
            logger.warning(f"Failed to add geometric patterns: {e}")

    def _draw_text_elements(self, image, title: str, news_items: List[Dict], style: str, mode: str):
        """テキスト要素を描画"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        colors = self.color_schemes[style]
        width, height = self.output_size

        try:
            # メインタイトル
            main_title = self._prepare_main_title(title, mode)
            self._draw_main_title(draw, main_title, colors, mode)

            # 日付表示
            date_text = datetime.now().strftime("%Y.%m.%d")
            self._draw_date(draw, date_text, colors)

            # モード表示
            mode_text = self._get_mode_text(mode)
            self._draw_mode_badge(draw, mode_text, colors, mode)

            # キーワード表示（ニュースがある場合）
            if news_items:
                keywords = self._extract_thumbnail_keywords(news_items)
                self._draw_keywords(draw, keywords, colors)

        except Exception as e:
            logger.warning(f"Failed to draw text elements: {e}")

        return image

    def _prepare_main_title(self, title: str, mode: str) -> str:
        """メインタイトルを準備"""
        # 長すぎるタイトルを調整
        if len(title) > 25:
            # 重要キーワードを抽出
            keywords = ["株価", "円安", "円高", "金利", "インフレ", "GDP", "決算"]
            important_words = [word for word in keywords if word in title]

            if important_words:
                # 重要語句を含む短縮版
                return f"{important_words[0]}関連ニュース"
            else:
                # 一般的な短縮
                return title[:20] + "..."

        return title

    def _draw_main_title(self, draw, title: str, colors: Dict, mode: str):
        """メインタイトルを描画"""
        width, height = self.output_size

        # フォントサイズを決定
        font_size = 72 if len(title) <= 15 else 60 if len(title) <= 20 else 48

        font = self._get_font(font_size)

        # テキストを改行
        wrapped_lines = textwrap.fill(title, width=15).split("\n")

        # 全体の高さを計算
        total_height = len(wrapped_lines) * font_size * 1.2

        # 開始Y位置（中央配置）
        start_y = (height - total_height) // 2

        for i, line in enumerate(wrapped_lines):
            # テキストサイズを取得
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # X位置（中央配置）
            x = (width - text_width) // 2
            y = start_y + i * font_size * 1.2

            # 影を描画
            shadow_offset = 4 if mode == "breaking" else 3
            draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=colors["shadow"])

            # メインテキストを描画
            text_color = colors["accent"] if mode == "breaking" else colors["text"]
            draw.text((x, y), line, font=font, fill=text_color)

    def _draw_date(self, draw, date_text: str, colors: Dict):
        """日付を描画"""
        font = self._get_font(24)

        # 右上に配置
        bbox = draw.textbbox((0, 0), date_text, font=font)
        text_width = bbox[2] - bbox[0]

        x = self.output_size[0] - text_width - 20
        y = 20

        # 背景矩形
        draw.rectangle([x - 10, y - 5, x + text_width + 10, y + 30], fill=(*colors["primary"], 180))

        draw.text((x, y), date_text, font=font, fill=colors["secondary"])

    def _draw_mode_badge(self, draw, mode_text: str, colors: Dict, mode: str):
        """モードバッジを描画"""
        font = self._get_font(20)

        # 左上に配置
        x, y = 20, 20

        # バッジ色を決定
        if mode == "breaking":
            badge_color = (255, 69, 0)  # 赤オレンジ
        elif mode == "special":
            badge_color = (255, 215, 0)  # 金色
        else:
            badge_color = colors["primary"]

        # バッジを描画
        bbox = draw.textbbox((0, 0), mode_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        draw.rounded_rectangle([x, y, x + text_width + 20, y + text_height + 10], radius=10, fill=badge_color)

        draw.text((x + 10, y + 5), mode_text, font=font, fill=(255, 255, 255))

    def _draw_keywords(self, draw, keywords: List[str], colors: Dict):
        """キーワードを描画"""
        if not keywords:
            return

        font = self._get_font(16)

        # 下部に配置
        y_start = self.output_size[1] - 80
        x_start = 20

        for i, keyword in enumerate(keywords[:4]):
            x = x_start + i * 150

            # キーワード背景
            bbox = draw.textbbox((0, 0), keyword, font=font)
            text_width = bbox[2] - bbox[0]

            draw.rounded_rectangle(
                [x, y_start, x + text_width + 16, y_start + 25], radius=5, fill=(*colors["accent"], 150)
            )

            draw.text((x + 8, y_start + 4), keyword, font=font, fill=colors["text"])

    def _get_mode_text(self, mode: str) -> str:
        """モードテキストを取得"""
        mode_texts = {"daily": "今日のニュース", "special": "特集", "breaking": "緊急", "test": "テスト"}
        return mode_texts.get(mode, "ニュース")

    def _extract_thumbnail_keywords(self, news_items: List[Dict]) -> List[str]:
        """サムネイル用キーワードを抽出"""
        keywords = []

        economic_keywords = [
            "株価",
            "日経平均",
            "為替",
            "円安",
            "円高",
            "金利",
            "インフレ",
            "GDP",
            "決算",
            "企業",
            "投資",
            "市場",
        ]

        for item in news_items:
            title = item.get("title", "")
            for keyword in economic_keywords:
                if keyword in title and keyword not in keywords:
                    keywords.append(keyword)
                    if len(keywords) >= 4:
                        break

        return keywords

    def _get_font(self, size: int):
        """フォントを取得"""
        from PIL import ImageFont

        # 利用可能なフォントを試行
        for font_name, font_path in self.font_paths.items():
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue

        # フォールバック: デフォルトフォント
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def _add_decorative_elements(self, image, style: str, mode: str):
        """装飾要素を追加"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        colors = self.color_schemes[style]
        width, height = self.output_size

        try:
            # 角の装飾
            corner_size = 30

            # 左上角
            draw.polygon([(0, 0), (corner_size, 0), (0, corner_size)], fill=colors["accent"])

            # 右下角
            draw.polygon(
                [(width, height), (width - corner_size, height), (width, height - corner_size)], fill=colors["accent"]
            )

            # モード別の特別装飾
            if mode == "breaking":
                # 緊急アイコン風の三角形
                triangle_size = 40
                cx, cy = width - 80, 80
                points = [
                    (cx, cy - triangle_size),
                    (cx - triangle_size, cy + triangle_size),
                    (cx + triangle_size, cy + triangle_size),
                ]
                draw.polygon(points, fill=(255, 69, 0))

                # 感嘆符
                font = self._get_font(24)
                if font:
                    draw.text((cx - 6, cy - 10), "!", font=font, fill=(255, 255, 255))

        except Exception as e:
            logger.warning(f"Failed to add decorative elements: {e}")

        return image

    def _optimize_image_quality(self, image):
        """画像品質を最適化"""
        from PIL import ImageEnhance

        try:
            # コントラスト調整
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.1)

            # 彩度調整
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(1.05)

            # シャープネス調整
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)

        except Exception as e:
            logger.warning(f"Image optimization failed: {e}")

        return image

    def _generate_fallback_thumbnail(self, title: str, output_path: str = None) -> str:
        """フォールバック用シンプルサムネイル"""
        try:
            if not self.has_pil:
                # PILが使えない場合は、テキストファイルで代替
                if not output_path:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = f"thumbnail_fallback_{timestamp}.txt"

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"サムネイル画像\n\nタイトル: {title}\n\n")
                    f.write("※ PIL (Python Imaging Library) が利用できないため、\n")
                    f.write("実際の画像ファイルを生成できませんでした。\n")
                    f.write("pip install Pillow でインストールしてください。")

                logger.warning(f"Generated text fallback thumbnail: {output_path}")
                return output_path

            from PIL import Image, ImageDraw

            # シンプルな画像を生成
            image = Image.new("RGB", self.output_size, (25, 35, 45))
            draw = ImageDraw.Draw(image)

            # タイトルテキスト
            font = self._get_font(48)
            if font:
                bbox = draw.textbbox((0, 0), title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                x = (self.output_size[0] - text_width) // 2
                y = (self.output_size[1] - text_height) // 2

                draw.text((x, y), title, font=font, fill=(255, 255, 255))

            # 出力パス決定
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"thumbnail_fallback_{timestamp}.png"

            image.save(output_path, "PNG")
            logger.info(f"Generated fallback thumbnail: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Fallback thumbnail generation failed: {e}")
            return None

    def create_batch_thumbnails(
        self, titles: List[str], styles: List[str] = None, modes: List[str] = None
    ) -> List[str]:
        """バッチでサムネイルを生成"""
        generated_thumbnails = []

        for i, title in enumerate(titles):
            try:
                style = styles[i] if styles and i < len(styles) else "economic_blue"
                mode = modes[i] if modes and i < len(modes) else "daily"

                thumbnail_path = self.generate_thumbnail(title=title, style=style, mode=mode)

                if thumbnail_path:
                    generated_thumbnails.append(thumbnail_path)
                    logger.info(f"Generated thumbnail {i + 1}/{len(titles)}")

            except Exception as e:
                logger.error(f"Failed to generate thumbnail {i + 1}: {e}")
                continue

        return generated_thumbnails


# グローバルインスタンス
thumbnail_generator = ThumbnailGenerator()


def generate_thumbnail(
    title: str, news_items: List[Dict[str, Any]] = None, mode: str = "daily", style: str = "economic_blue"
) -> str:
    """サムネイル生成の簡易関数"""
    return thumbnail_generator.generate_thumbnail(title, news_items, mode, style)


def create_batch_thumbnails(titles: List[str], styles: List[str] = None, modes: List[str] = None) -> List[str]:
    """バッチサムネイル生成の簡易関数"""
    return thumbnail_generator.create_batch_thumbnails(titles, styles, modes)


if __name__ == "__main__":
    # テスト実行
    print("Testing thumbnail generation...")

    # PIL確認
    generator = ThumbnailGenerator()
    print(f"PIL available: {generator.has_pil}")
    print(f"Available fonts: {list(generator.font_paths.keys())}")

    # テスト用データ
    test_titles = ["日経平均が年初来高値更新", "中央銀行が緊急利上げ決定", "米中貿易摩擦が市場に影響"]

    test_news = [
        {"title": "日経平均株価が3日連続上昇", "summary": "好調な企業決算が支援材料となった", "impact_level": "high"}
    ]

    try:
        # 単一サムネイル生成テスト
        print("\n=== 単一サムネイル生成テスト ===")
        thumbnail_path = generator.generate_thumbnail(
            title=test_titles[0], news_items=test_news, mode="daily", style="economic_blue"
        )

        if thumbnail_path:
            print(f"Generated thumbnail: {thumbnail_path}")
            if os.path.exists(thumbnail_path):
                file_size = os.path.getsize(thumbnail_path)
                print(f"File size: {file_size} bytes")

        # 緊急モードテスト
        print("\n=== 緊急モードサムネイルテスト ===")
        breaking_path = generator.generate_thumbnail(title="緊急：金利急上昇", mode="breaking", style="market_red")
        if breaking_path:
            print(f"Generated breaking thumbnail: {breaking_path}")

        # バッチ生成テスト
        print("\n=== バッチ生成テスト ===")
        batch_paths = generator.create_batch_thumbnails(
            titles=test_titles,
            styles=["economic_blue", "financial_green", "market_red"],
            modes=["daily", "special", "breaking"],
        )
        print(f"Generated {len(batch_paths)} thumbnails in batch")

    except Exception as e:
        print(f"Test failed: {e}")

    # カラースキーム表示
    print("\n=== 利用可能カラースキーム ===")
    for scheme_name, colors in generator.color_schemes.items():
        print(f"{scheme_name}: {colors['background']}")

    print("\nThumbnail generation test completed.")
