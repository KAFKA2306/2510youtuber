"""サムネイル生成モジュール（統合版）

YouTube動画用の魅力的なサムネイル画像を自動生成します。
視覚的インパクトとクリック率向上を目的とした高品質なサムネイルを作成します。

統合内容:
- 標準サムネイル生成（ThumbnailGenerator）
- プロ品質サムネイル生成（ProThumbnailGenerator）
- V2革新的デザイン（左右分割レイアウト）
- 自動切り替え機能
"""

import logging
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """サムネイル生成クラス（V2革新的デザイン統合）"""

    def __init__(self):
        self.output_size = (1280, 720)  # YouTube推奨サイズ
        self.font_paths = self._get_available_fonts()
        self.color_schemes = self._load_color_schemes()
        self.default_icon = "/home/kafka/projects/youtuber/assets/icon/ChatGPT Image 2025年10月2日 19_53_38.png"

        self.has_pil = HAS_PIL
        if self.has_pil:
            logger.info("Thumbnail generator initialized with PIL")
        else:
            logger.warning("PIL not available, thumbnail generation will be limited")

    def _get_available_fonts(self) -> Dict[str, str]:
        """利用可能なフォントパスを取得（日本語優先）"""
        font_paths = {}

        # システムフォントパスの候補（日本語フォント優先）
        font_candidates = [
            # 日本語フォント (Linux)
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
            "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
            # 日本語フォント (macOS)
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
            # 日本語フォント (Windows)
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/YuGothB.ttc",
            "C:/Windows/Fonts/YuGothM.ttc",
            # Noto CJK
            "/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            # 欧文フォント（フォールバック）
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]

        for font_path in font_candidates:
            if os.path.exists(font_path):
                font_name = Path(font_path).stem.lower()
                font_paths[font_name] = font_path

        logger.info(f"Found {len(font_paths)} available fonts (Japanese priority)")
        return font_paths

    def _load_color_schemes(self) -> Dict[str, Dict[str, Any]]:
        """カラースキームを定義（人気YouTubeスタイル）"""
        return {
            "economic_blue": {
                "background": (10, 20, 40),  # より濃い青
                "primary": (0, 120, 215),  # 鮮やかな青
                "secondary": (255, 255, 255),
                "accent": (255, 215, 0),  # 金色（クリック誘導）
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 220),  # 濃い影
                "highlight": (255, 69, 0),  # オレンジ（強調用）
            },
            "financial_green": {
                "background": (5, 30, 15),  # 深緑
                "primary": (0, 180, 80),  # 鮮やかな緑
                "secondary": (255, 255, 255),
                "accent": (255, 215, 0),
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 220),
                "highlight": (255, 193, 7),  # 黄金色
            },
            "market_red": {
                "background": (40, 5, 5),  # 深紅
                "primary": (255, 50, 50),  # 鮮やかな赤
                "secondary": (255, 255, 255),
                "accent": (255, 215, 0),
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 220),
                "highlight": (255, 140, 0),  # オレンジレッド
            },
            "youtube_style": {
                "background": (20, 20, 30),  # ダークグレー
                "primary": (255, 0, 0),  # YouTube赤
                "secondary": (255, 255, 255),
                "accent": (255, 215, 0),  # 金色
                "text": (255, 255, 255),
                "shadow": (0, 0, 0, 230),
                "highlight": (0, 255, 255),  # シアン（目を引く）
            },
        }

    def generate_thumbnail(
        self,
        title: str,
        news_items: List[Dict[str, Any]] = None,
        mode: str = "daily",
        style: str = "economic_blue",
        output_path: str = None,
        layout: str = "v2",
        icon_path: str = None,
    ) -> str:
        """サムネイル画像を生成

        Args:
            title: メインタイトルテキスト
            news_items: ニュース項目（サブテキスト用）
            mode: 動画モード (daily/special/breaking)
            style: カラースキーム
            output_path: 出力パス
            layout: レイアウトタイプ ("v2"=左右分割, "classic"=従来型)
            icon_path: V2レイアウト用アイコン画像パス

        Returns:
            生成されたサムネイル画像のパス

        """
        # V2レイアウトを使用
        if layout == "v2":
            return self._generate_v2_layout(title, icon_path, news_items, mode, output_path)
        try:
            if not self.has_pil:
                return self._generate_fallback_thumbnail(title, output_path)

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
        """メインタイトルを準備（人気YouTubeスタイル）"""
        import re

        # 数値を強調記号で囲む（YouTubeスタイル）
        # 例: "10月利上げ" -> "【10月】利上げ"
        title = re.sub(r"(\d+[%％円ドル年月日])", r"【\1】", title)

        # 重要キーワードを強調
        important_patterns = [
            (r"(速報|緊急|注目|衝撃|驚愕)", r"⚡\1⚡"),
            (r"(暴落|急落|急騰|高騰)", r"📉\1📈"),
        ]

        for pattern, replacement in important_patterns:
            title = re.sub(pattern, replacement, title)

        # 長すぎる場合は調整
        if len(title) > 30:
            # 重要キーワードを抽出
            keywords = ["株価", "円安", "円高", "金利", "インフレ", "GDP", "決算", "速報", "利上げ"]
            important_words = [word for word in keywords if word in title]

            if important_words:
                # 重要語句を含む短縮版
                return f"【{important_words[0]}】最新情報"
            else:
                # 一般的な短縮
                return title[:25] + "..."

        return title

    def _draw_main_title(self, draw, title: str, colors: Dict, mode: str):
        """メインタイトルを描画（人気YouTubeスタイル）"""
        width, height = self.output_size

        # フォントサイズを大きく（視認性・インパクト重視）
        if len(title) <= 10:
            font_size = 90  # 大きく
        elif len(title) <= 15:
            font_size = 80
        elif len(title) <= 20:
            font_size = 70
        else:
            font_size = 60

        font = self._get_font(font_size)

        # 日本語の場合、適切な文字数で改行
        wrapped_lines = textwrap.fill(title, width=12).split("\n")  # 15 -> 12

        # 全体の高さを計算
        total_height = len(wrapped_lines) * font_size * 1.3

        # 開始Y位置（やや上寄り）
        start_y = (height - total_height) // 2 - 50

        for i, line in enumerate(wrapped_lines):
            # テキストサイズを取得
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]

            # X位置（中央配置）
            x = (width - text_width) // 2
            y = start_y + i * font_size * 1.3

            # 多重影（立体感）
            for offset in range(6, 1, -1):
                shadow_alpha = 200 - (offset * 20)
                draw.text((x + offset, y + offset), line, font=font, fill=(0, 0, 0, shadow_alpha))

            # アウトライン（縁取り）
            outline_color = (0, 0, 0)
            for dx in [-2, 0, 2]:
                for dy in [-2, 0, 2]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), line, font=font, fill=outline_color)

            # メインテキストを描画（鮮やかな色）
            text_color = colors.get("highlight", colors["accent"]) if mode == "breaking" else colors["accent"]
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
        """フォントを取得（日本語フォント優先）"""

        # 日本語フォントを優先的に試行
        japanese_font_names = ["ipag", "ipagp", "msgothic", "meiryo", "yugothb", "yugothm", "notosanscjk"]

        # 日本語フォントを優先
        for font_name, font_path in self.font_paths.items():
            if any(jp_name in font_name for jp_name in japanese_font_names):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception as e:
                    logger.debug(f"Failed to load Japanese font {font_path}: {e}")
                    continue

        # その他のフォントも試行
        for font_name, font_path in self.font_paths.items():
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                continue

        # フォールバック: デフォルトフォント
        try:
            logger.warning("Using default font as fallback")
            return ImageFont.load_default()
        except (OSError, IOError) as e:
            logger.error(f"Could not load any font: {e}")
            return None

    def _add_decorative_elements(self, image, style: str, mode: str):
        """装飾要素を追加"""

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

    def _generate_v2_layout(
        self,
        title: str,
        icon_path: str = None,
        news_items: List[Dict[str, Any]] = None,
        mode: str = "daily",
        output_path: str = None,
    ) -> str:
        """V2革新的レイアウト（左右分割：画像右、テキスト左）"""
        if not self.has_pil:
            return self._generate_fallback_thumbnail(title, output_path)

        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"thumbnail_v2_{timestamp}.png"

            # モダン背景
            image = self._create_modern_background(mode)

            # 右側にアイコン配置
            image = self._add_right_icon(image, icon_path or self.default_icon)

            # 左側にキャッチコピー
            image = self._add_left_catchcopy(image, title, mode)

            # モバイル最適化
            image = self._enhance_v2_for_mobile(image)

            image.save(output_path, "PNG", quality=95, optimize=True)
            logger.info(f"Generated V2 thumbnail: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"V2 thumbnail generation failed: {e}")
            return self._generate_fallback_thumbnail(title, output_path)

    def _create_modern_background(self, mode: str):
        """モダンなグラデーション背景（V2専用）"""

        width, height = self.output_size

        bg_schemes = {
            "daily": ((15, 25, 45), (35, 55, 95)),
            "special": ((45, 15, 65), (85, 35, 115)),
            "breaking": ((50, 10, 10), (100, 25, 25)),
        }

        start_color, end_color = bg_schemes.get(mode, bg_schemes["daily"])

        image = Image.new("RGB", (width, height))

        draw = ImageDraw.Draw(image)
        # 斜めグラデーション
        for y in range(height):
            ratio = y / height
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)

            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 中央分割線
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        center_x = width // 2
        for offset in range(-3, 4):
            alpha = 40 - abs(offset) * 10
            overlay_draw.line(
                [(center_x + offset, 0), (center_x + offset, height)], fill=(255, 255, 255, alpha), width=1
            )

        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

        return image

    def _add_right_icon(self, image, icon_path: str):
        """右側に大きなアイコンを配置"""
        width, height = self.output_size

        try:
            if not os.path.exists(icon_path):
                logger.warning(f"Icon not found: {icon_path}")
                return image

            icon = Image.open(icon_path)

            # 右側80%使用
            icon_height = int(height * 0.8)
            aspect_ratio = icon.width / icon.height
            icon_width = int(icon_height * aspect_ratio)

            icon = icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)

            icon_x = width - icon_width - 30
            icon_y = (height - icon_height) // 2

            # 影を追加
            if icon.mode == "RGBA":
                shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow)
                shadow_draw.ellipse(
                    [icon_x - 10, icon_y + icon_height - 50, icon_x + icon_width + 10, icon_y + icon_height + 20],
                    fill=(0, 0, 0, 60),
                )
                image = Image.alpha_composite(image.convert("RGBA"), shadow).convert("RGB")

                image = image.convert("RGBA")
                image.paste(icon, (icon_x, icon_y), icon)
                image = image.convert("RGB")
            else:
                image.paste(icon, (icon_x, icon_y))

            logger.info(f"Icon placed at ({icon_x}, {icon_y})")

        except Exception as e:
            logger.error(f"Failed to add icon: {e}")

        return image

    def _add_left_catchcopy(self, image, title: str, mode: str):
        """左側にWOWキャッチコピーを配置"""
        draw = ImageDraw.Draw(image)
        width, height = self.output_size

        catchcopy = self._create_wow_catchcopy(title)

        left_width = width // 2 - 80
        left_center_x = left_width // 2 + 60

        copy_font = self._get_font(size=120)
        if not copy_font:
            return image

        lines = catchcopy.split("\n")
        total_height = len(lines) * 145
        start_y = (height - total_height) // 2 + 20

        for i, line in enumerate(lines):
            if not line.strip():
                continue

            bbox = draw.textbbox((0, 0), line, font=copy_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = left_center_x - text_width // 2
            y = start_y + i * 145

            # 背景ボックス
            padding = 15
            draw.rectangle(
                [x - padding, y - padding, x + text_width + padding, y + text_height + padding], fill=(0, 0, 0, 150)
            )

            # 多層影
            for offset in range(10, 0, -2):
                shadow_alpha = 200 - (offset * 15)
                draw.text((x + offset, y + offset), line, font=copy_font, fill=(0, 0, 0, shadow_alpha))

            # 極太アウトライン
            for dx in [-3, -2, -1, 0, 1, 2, 3]:
                for dy in [-3, -2, -1, 0, 1, 2, 3]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), line, font=copy_font, fill=(0, 0, 0))

            # メインテキスト
            text_color = self._get_v2_text_color(mode)
            draw.text((x, y), line, font=copy_font, fill=text_color)

        # 日付バッジ
        self._add_v2_date_badge(draw)

        return image

    def _create_wow_catchcopy(self, title: str) -> str:
        """WOWなキャッチコピーを生成"""
        wow_keywords = {
            "暴落": "大暴落\n警報!",
            "急落": "急落\n速報!",
            "急騰": "急騰\n来た!",
            "高騰": "高騰\n注目!",
            "速報": "緊急\n速報!",
            "利上げ": "利上げ\nショック",
            "円安": "円安\n加速!",
            "円高": "円高\n急騰!",
            "株価": "株価\n激変!",
            "金利": "金利\n衝撃!",
            "AI": "AI\n革命!",
            "ビットコイン": "BTC\n爆上げ",
            "仮想通貨": "暗号資産\n祭り!",
        }

        for keyword, copy in wow_keywords.items():
            if keyword in title:
                return copy

        # 数字抽出
        number_patterns = [
            (r"([+\-]?\d+\.?\d*[%％])", "{}%\n激震!"),
            (r"(\d+\.?\d*倍)", "{}\n急上昇"),
            (r"([+\-]\d+円)", "{}\n動く!"),
        ]

        for pattern, template in number_patterns:
            match = re.search(pattern, title)
            if match:
                num = match.group(1)
                return template.format(num)

        # デフォルト
        important_words = ["注目", "速報", "衝撃", "警告", "予測", "分析"]
        for word in important_words:
            if word in title:
                return f"{word}\n情報!"

        words = title.replace(" ", "").replace("　", "")
        if len(words) >= 4:
            first_part = words[:5]
            return f"{first_part}\n速報!"

        return "超注目\n情報!"

    def _get_v2_text_color(self, mode: str) -> tuple:
        """V2用テキストカラー"""
        colors = {
            "daily": (255, 223, 0),
            "special": (255, 105, 180),
            "breaking": (255, 69, 0),
        }
        return colors.get(mode, (255, 223, 0))

    def _add_v2_date_badge(self, draw):
        """V2用日付バッジ"""
        font = self._get_font(size=36)
        if not font:
            return

        date_text = datetime.now().strftime("%m/%d")
        x, y = 40, self.output_size[1] - 90

        draw.ellipse([x - 5, y - 5, x + 110, y + 50], fill=(255, 69, 0))
        draw.text((x + 15, y), date_text, font=font, fill=(255, 255, 255))

    def _enhance_v2_for_mobile(self, image):
        """V2用モバイル最適化"""
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.35)

        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.25)

        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.3)

        return image


# グローバルインスタンス
thumbnail_generator = ThumbnailGenerator()


def generate_thumbnail(
    title: str,
    news_items: List[Dict[str, Any]] = None,
    mode: str = "daily",
    style: str = "economic_blue",
    layout: str = "v2",
    icon_path: str = None,
    output_path: str = None,
) -> str:
    """サムネイル生成の簡易関数（V2レイアウトがデフォルト）"""
    return thumbnail_generator.generate_thumbnail(
        title, news_items, mode, style, output_path, layout=layout, icon_path=icon_path
    )


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
