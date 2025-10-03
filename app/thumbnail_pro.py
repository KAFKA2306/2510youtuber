"""プロYouTuber品質サムネイル生成モジュール

登録者数100万人を目指す高CTR（クリック率）サムネイルを生成します。
人気投資系YouTuberの成功パターンを実装:
- 衝撃的な数字の強調
- 高コントラストな配色
- 感情を刺激する要素
- モバイル視認性最適化
"""

import importlib.util
import logging
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProThumbnailGenerator:
    """プロ品質サムネイル生成クラス（100万登録者レベル）"""

    def __init__(self):
        self.output_size = (1280, 720)  # YouTube推奨サイズ
        self.has_pil = self._check_pil()
        self.font_paths = self._get_available_fonts() if self.has_pil else {}

    def _check_pil(self) -> bool:
        if importlib.util.find_spec("PIL.Image") and importlib.util.find_spec("PIL.ImageDraw") and importlib.util.find_spec("PIL.ImageFont"):
            return True
        else:
            logger.warning("PIL not available, thumbnail generation will be limited")
            return False

    def _get_available_fonts(self) -> Dict[str, str]:
        """利用可能なフォントパスを取得"""
        font_paths = {}
        font_candidates = [
            # 日本語フォント (Linux)
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
            "/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Bold.ttc",
            # 日本語フォント (macOS)
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            # 日本語フォント (Windows)
            "C:/Windows/Fonts/YuGothB.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
        ]

        for font_path in font_candidates:
            if os.path.exists(font_path):
                font_name = Path(font_path).stem.lower()
                font_paths[font_name] = font_path

        logger.info(f"Found {len(font_paths)} fonts for thumbnails")
        return font_paths

    def generate_pro_thumbnail(
        self,
        title: str,
        news_items: List[Dict[str, Any]] = None,
        mode: str = "daily",
        output_path: str = None,
    ) -> str:
        """高CTRサムネイルを生成（100万登録者品質）"""
        if not self.has_pil:
            return self._generate_fallback_thumbnail(title, output_path)

        try:
            # 出力パス設定
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"thumbnail_pro_{timestamp}.png"

            # ベース画像作成
            image = self._create_dynamic_background(mode)

            # 重要な数字を抽出
            key_number = self._extract_key_number(title, news_items)

            # レイアウトタイプを決定（数字ベース or テキストベース）
            if key_number:
                image = self._apply_number_focused_layout(image, title, key_number, mode)
            else:
                image = self._apply_text_focused_layout(image, title, mode)

            # 感情アイコンを追加（YouTubeスタンダード）
            image = self._add_emotion_icons(image, title, mode)

            # 視認性強化（コントラスト・彩度）
            image = self._enhance_for_mobile(image)

            # 保存
            image.save(output_path, "PNG", quality=95, optimize=True)
            logger.info(f"Generated pro thumbnail: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Pro thumbnail generation failed: {e}")
            return self._generate_fallback_thumbnail(title, output_path)

    def _create_dynamic_background(self, mode: str):
        """動的背景を作成（YouTubeトレンドに基づく）"""
        from PIL import Image, ImageDraw

        width, height = self.output_size

        # モード別の配色（高コントラスト）
        bg_colors = {
            "daily": ((5, 15, 30), (25, 45, 80)),  # 深い青グラデーション
            "special": ((30, 5, 5), (80, 20, 20)),  # 赤グラデーション（緊急感）
            "breaking": ((5, 30, 5), (20, 80, 20)),  # 緑グラデーション（上昇）
        }

        start_color, end_color = bg_colors.get(mode, bg_colors["daily"])

        # グラデーション背景
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)

        for y in range(height):
            ratio = y / height
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 放射状グラデーション効果（中央から）
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        center_x, center_y = width // 2, height // 2
        max_radius = int((width**2 + height**2) ** 0.5 / 2)

        for i in range(max_radius, 0, -20):
            alpha = int(30 * (1 - i / max_radius))
            overlay_draw.ellipse([center_x - i, center_y - i, center_x + i, center_y + i], fill=(255, 255, 255, alpha))

        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

        # ビネット効果（周辺暗く）
        vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        vignette_draw = ImageDraw.Draw(vignette)

        for y in range(height):
            for x in range(width):
                # 中心からの距離
                dx = (x - center_x) / (width / 2)
                dy = (y - center_y) / (height / 2)
                distance = (dx**2 + dy**2) ** 0.5
                alpha = int(min(100, distance * 80))
                vignette_draw.point((x, y), fill=(0, 0, 0, alpha))

        image = Image.alpha_composite(image.convert("RGBA"), vignette).convert("RGB")

        return image

    def _extract_key_number(self, title: str, news_items: List[Dict] = None) -> Optional[str]:
        """重要な数字を抽出（パーセンテージ、金額など）"""
        import re

        # タイトルから数字を抽出
        patterns = [
            r"([+\-]?\d+\.?\d*[%％])",  # パーセンテージ
            r"(\d+\.?\d*[兆億万千百十]+円)",  # 金額
            r"(\d+\.?\d*倍)",  # 倍率
            r"([+\-]\d+\.?\d*円)",  # 価格変動
            r"(\d+年)",  # 年数
        ]

        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1)

        # ニュースから数字を抽出
        if news_items:
            for item in news_items[:2]:
                text = item.get("title", "") + " " + item.get("summary", "")
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        return match.group(1)

        return None

    def _apply_number_focused_layout(self, image, title: str, key_number: str, mode: str):
        """数字を中心としたレイアウト（インパクト重視）"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        width, height = self.output_size

        # 巨大な数字を中央に配置
        number_font = self._get_font(size=280)
        if number_font:
            # 数字の位置計算
            bbox = draw.textbbox((0, 0), key_number, font=number_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2 - 50

            # 極太影（5層）
            for offset in range(12, 0, -3):
                shadow_alpha = 255 - (offset * 15)
                draw.text((x + offset, y + offset), key_number, font=number_font, fill=(0, 0, 0, shadow_alpha))

            # 数字本体（黄色 - YouTube定番）
            draw.text((x, y), key_number, font=number_font, fill=(255, 215, 0))

            # 数字の周りに枠
            padding = 20
            draw.rectangle(
                [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
                outline=(255, 255, 255),
                width=8,
            )

        # タイトルテキスト（上部）
        title_font = self._get_font(size=54)
        if title_font:
            # 数字を除去したタイトル
            clean_title = title.replace(key_number, "").strip()
            wrapped_title = textwrap.fill(clean_title, width=18)

            # 上部中央に配置
            bbox = draw.textbbox((0, 0), wrapped_title, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = 40

            # 背景ボックス（視認性）
            padding = 25
            draw.rectangle(
                [x - padding, y - padding // 2, x + text_width + padding, y + (bbox[3] - bbox[1]) + padding],
                fill=(0, 0, 0, 200),
            )

            # テキスト影
            for offset in [4, 2]:
                draw.text((x + offset, y + offset), wrapped_title, font=title_font, fill=(0, 0, 0))

            # テキスト本体（白）
            draw.text((x, y), wrapped_title, font=title_font, fill=(255, 255, 255))

        return image

    def _apply_text_focused_layout(self, image, title: str, mode: str):
        """テキスト中心のレイアウト（インパクト重視）"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        width, height = self.output_size

        # タイトルを整形（改行）
        wrapped_title = textwrap.fill(title, width=16)

        # 大きなフォント
        title_font = self._get_font(size=90)
        if title_font:
            # テキスト位置計算（中央）
            bbox = draw.textbbox((0, 0), wrapped_title, font=title_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2

            # 背景ボックス（黒、半透明）
            padding = 40
            draw.rectangle(
                [x - padding, y - padding, x + text_width + padding, y + text_height + padding], fill=(0, 0, 0, 180)
            )

            # 極太影（6層）
            for offset in range(15, 0, -3):
                shadow_alpha = 255 - (offset * 12)
                draw.text((x + offset, y + offset), wrapped_title, font=title_font, fill=(0, 0, 0, shadow_alpha))

            # テキスト本体（黄色）
            draw.text((x, y), wrapped_title, font=title_font, fill=(255, 215, 0))

            # アンダーライン（強調）
            line_y = y + text_height + 15
            draw.rectangle([x, line_y, x + text_width, line_y + 8], fill=(255, 69, 0))

        return image

    def _add_emotion_icons(self, image, title: str, mode: str):
        """感情アイコンを追加（YouTubeスタンダード）"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        width, height = self.output_size

        # キーワードベースのアイコン選択
        icon_map = {
            "暴落": "📉",
            "急落": "📉",
            "下落": "📉",
            "急騰": "📈",
            "高騰": "📈",
            "上昇": "📈",
            "速報": "⚡",
            "緊急": "🚨",
            "注目": "👀",
            "衝撃": "💥",
        }

        selected_icon = None
        for keyword, icon in icon_map.items():
            if keyword in title:
                selected_icon = icon
                break

        if selected_icon:
            # 右上にアイコン（大きく）
            icon_font = self._get_font(size=120)
            if icon_font:
                draw.text((width - 180, 40), selected_icon, font=icon_font, fill=(255, 255, 255))

        # 日付バッジ（左下）
        date_text = datetime.now().strftime("%m/%d")
        date_font = self._get_font(size=42)
        if date_font:
            # 背景円
            draw.ellipse([30, height - 100, 150, height - 20], fill=(255, 69, 0))
            draw.text((55, height - 80), date_text, font=date_font, fill=(255, 255, 255))

        return image

    def _enhance_for_mobile(self, image):
        """モバイル視認性を最大化"""
        from PIL import ImageEnhance

        # コントラスト強化（モバイルで映える）
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.3)

        # 彩度強化（目を引く）
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.2)

        # シャープネス強化（小画面で鮮明）
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)

        return image

    def _get_font(self, size: int):
        """フォントを取得"""
        from PIL import ImageFont

        for font_path in self.font_paths.values():
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                logger.debug(f"Could not load font {font_path}: {e}")
                continue

        try:
            return ImageFont.load_default()
        except Exception as e:
            logger.warning(f"Could not load default font: {e}")
            return None

    def _generate_fallback_thumbnail(self, title: str, output_path: str = None) -> str:
        """フォールバック用シンプルサムネイル"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"thumbnail_fallback_{timestamp}.txt"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"サムネイル: {title}\n")

        logger.warning("Using fallback thumbnail (PIL not available)")
        return output_path


# グローバルインスタンス
pro_thumbnail_generator = ProThumbnailGenerator()


def generate_pro_thumbnail(
    title: str,
    news_items: List[Dict[str, Any]] = None,
    mode: str = "daily",
    output_path: str = None,
) -> str:
    """プロ品質サムネイル生成（簡易インターフェース）"""
    return pro_thumbnail_generator.generate_pro_thumbnail(title, news_items, mode, output_path)
