"""動画生成モジュール

音声ファイル、字幕ファイル、背景画像を組み合わせて最終的な動画を生成します。
FFmpegを使用して高品質な動画出力を実現します。
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict

import ffmpeg
from pydub import AudioSegment

from .config import cfg

logger = logging.getLogger(__name__)


class VideoGenerator:
    """動画生成クラス"""

    def __init__(self):
        self.video_quality = cfg.video_quality or "high"
        self.output_format = "mp4"
        logger.info("Video generator initialized")

    def generate_video(
        self,
        audio_path: str,
        subtitle_path: str,
        background_image: str = None,
        title: str = "Economic News Analysis",
        output_path: str = None,
    ) -> str:
        """動画を生成"""
        try:
            self._validate_input_files(audio_path, subtitle_path, background_image)
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"video_{timestamp}.{self.output_format}"

            bg_image_path = self._prepare_background_image(background_image, title)
            audio_duration = self._get_audio_duration(audio_path)

            stream = ffmpeg.input(bg_image_path, loop=1, t=audio_duration)
            audio_stream = ffmpeg.input(audio_path)

            stream = ffmpeg.output(
                stream,
                audio_stream,
                output_path,
                vf=self._build_subtitle_filter(subtitle_path),
                **self._get_quality_settings(),
            ).overwrite_output()

            ffmpeg.run(stream, quiet=True)

            video_info = self._get_video_info(output_path)
            logger.info(f"Video generated successfully: {output_path}")
            logger.info(f"Video info: {video_info}")
            return output_path

        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return self._generate_fallback_video(audio_path, title)
        finally:
            if "bg_image_path" in locals() and bg_image_path != background_image:
                try:
                    os.remove(bg_image_path)
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"Could not remove background image {bg_image_path}: {e}")

    def _validate_input_files(self, audio_path: str, subtitle_path: str, background_image: str = None):
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if not os.path.exists(subtitle_path):
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
        if background_image and not os.path.exists(background_image):
            logger.warning(f"Background image not found: {background_image}, using default")
        try:
            AudioSegment.from_file(audio_path)
        except Exception as e:
            raise ValueError(f"Invalid audio file format: {e}")

    def _prepare_background_image(self, background_image: str = None, title: str = "News Analysis") -> str:
        if background_image and os.path.exists(background_image):
            return background_image
        return self._create_default_background(title)

    def _create_default_background(self, title: str) -> str:
        """プロ品質の動的背景を作成（投資系YouTuber品質）"""
        try:
            import textwrap
            from PIL import Image, ImageDraw, ImageFont, ImageFilter

            width, height = 1920, 1080

            # 深い青のグラデーション背景（金融・投資のプロフェッショナル感）
            image = Image.new("RGB", (width, height), color=(10, 20, 35))
            draw = ImageDraw.Draw(image)

            # 3段階のグラデーション（上部暗→中央→下部明）
            for y_pos in range(height):
                # より滑らかな3段階グラデーション
                ratio = y_pos / height
                if ratio < 0.3:
                    # 上部: 深い青
                    r = int(10 + (20 - 10) * (ratio / 0.3))
                    g = int(20 + (35 - 20) * (ratio / 0.3))
                    b = int(35 + (50 - 35) * (ratio / 0.3))
                elif ratio < 0.7:
                    # 中央: 標準青
                    r = int(20 + (15 - 20) * ((ratio - 0.3) / 0.4))
                    g = int(35 + (45 - 35) * ((ratio - 0.3) / 0.4))
                    b = int(50 + (70 - 50) * ((ratio - 0.3) / 0.4))
                else:
                    # 下部: やや明るい青（字幕スペース）
                    r = int(15 + (25 - 15) * ((ratio - 0.7) / 0.3))
                    g = int(45 + (60 - 45) * ((ratio - 0.7) / 0.3))
                    b = int(70 + (85 - 70) * ((ratio - 0.7) / 0.3))
                draw.line([(0, y_pos), (width, y_pos)], fill=(r, g, b))

            # 装飾的な幾何学パターン（左上・右下）
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # 左上の円形パターン（アクセント）
            overlay_draw.ellipse([(-100, -100), (400, 400)], fill=(0, 120, 215, 30))
            overlay_draw.ellipse([(-50, -50), (350, 350)], fill=(0, 150, 255, 20))

            # 右下の円形パターン
            overlay_draw.ellipse([(width - 400, height - 400), (width + 100, height + 100)], fill=(255, 215, 0, 25))
            overlay_draw.ellipse([(width - 350, height - 350), (width + 50, height + 50)], fill=(255, 193, 7, 15))

            # グリッドライン（プロフェッショナル感）
            for i in range(0, width, 100):
                overlay_draw.line([(i, 0), (i, height)], fill=(255, 255, 255, 3), width=1)
            for i in range(0, height, 100):
                overlay_draw.line([(0, i), (width, i)], fill=(255, 255, 255, 3), width=1)

            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

            # タイトルテキスト（上部中央）
            font = self._get_japanese_font_for_background(64)
            if font:
                # タイトルを短く整形
                wrapped_title = textwrap.fill(title, width=20)

                # テキストのバウンディングボックス
                bbox = draw.textbbox((0, 0), wrapped_title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (width - text_width) // 2
                y = 150  # 上部に配置

                # 影（複数層で深さを出す）
                for offset in [8, 6, 4, 2]:
                    alpha_val = 255 - (offset * 30)
                    draw.text((x + offset, y + offset), wrapped_title, font=font, fill=(0, 0, 0, alpha_val))

                # メインテキスト（白）
                draw.text((x, y), wrapped_title, font=font, fill=(255, 255, 255))

                # アクセントライン（タイトル下）
                line_y = y + text_height + 20
                draw.rectangle([x, line_y, x + text_width, line_y + 5], fill=(255, 215, 0))

            temp_path = tempfile.mktemp(suffix=".png")
            image.save(temp_path, "PNG", quality=95)
            logger.info(f"Created professional background with dynamic elements: {temp_path}")
            return temp_path
        except Exception as e:
            logger.warning(f"Failed to create professional background: {e}")
            return self._create_simple_background()

    def _get_japanese_font_for_background(self, size: int):
        """背景用の日本語フォントを取得"""
        from PIL import ImageFont

        # 日本語フォントの候補
        japanese_font_paths = [
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",  # IPA ゴシック
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",  # macOS
            "C:/Windows/Fonts/msgothic.ttc",  # Windows
            "C:/Windows/Fonts/YuGothB.ttc",  # Windows Yu Gothic Bold
        ]

        for font_path in japanese_font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception as e:
                    logger.debug(f"Failed to load font {font_path}: {e}")
                    continue

        # フォールバック
        try:
            return ImageFont.load_default()
        except (OSError, IOError) as e:
            logger.warning(f"Could not load default font: {e}")
            return None

    def _create_simple_background(self) -> str:
        try:
            from PIL import Image

            image = Image.new("RGB", (1920, 1080), color=(25, 35, 45))
            temp_path = tempfile.mktemp(suffix=".png")
            image.save(temp_path, "PNG")
            return temp_path
        except Exception as e:
            logger.error(f"Failed to create simple background: {e}")
            return None

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            return 60.0

    def _get_quality_settings(self) -> Dict[str, Any]:
        presets = cfg.video_quality_presets
        settings = presets.get(self.video_quality, presets["medium"])
        settings.update({"c:a": "aac", "b:a": "128k", "ar": "44100", "pix_fmt": "yuv420p", "movflags": "+faststart"})
        return settings

    def _build_subtitle_filter(self, subtitle_path: str) -> str:
        """字幕フィルタを構築（プロYouTuber品質、見切れ防止）"""
        try:
            # On Windows, paths must be escaped.
            if os.name == "nt":
                subtitle_path = subtitle_path.replace("\\", "\\\\").replace(":", "\\:")

            # 日本語フォントを優先的に使用（太字優先）
            japanese_fonts = [
                "Noto Sans CJK JP Bold",  # 最も読みやすい
                "Yu Gothic Bold",  # Windows/Mac 太字
                "Hiragino Sans W6",  # macOS 太字
                "IPAGothic",  # IPA ゴシック (Linux)
                "Meiryo Bold",  # Windows 太字
                "MS Gothic",  # Windows
            ]

            # 利用可能な日本語フォントを検索
            font_name = self._find_available_font(japanese_fonts)

            # プロYouTuber品質の字幕スタイル（設定値は config.py から取得）
            subtitle_style = (
                f"subtitles={subtitle_path}:force_style='FontName={font_name},"
                f"FontSize={cfg.subtitle_font_size},"
                f"PrimaryColour={cfg.subtitle_color},"
                f"OutlineColour=&H00000000,"  # 黒アウトライン
                f"BackColour=&HC0000000,"  # 濃い半透明黒背景
                f"BorderStyle=4,"  # 4=ボックス背景+アウトライン（最強視認性）
                f"Outline={cfg.subtitle_outline_width},"
                f"Shadow=2,"  # 強い影
                f"Alignment=2,"  # 下部中央
                f"MarginV={cfg.subtitle_margin_v},"
                f"MarginL={cfg.subtitle_margin_h},"
                f"MarginR={cfg.subtitle_margin_h},"
                f"Bold=1,"  # 太字
                f"Spacing=0'"  # 文字間隔
            )

            logger.info(f"Using subtitle font: {font_name}")
            return subtitle_style

        except Exception as e:
            logger.warning(f"Failed to build subtitle filter: {e}")
            return None

    def _find_available_font(self, font_candidates: list) -> str:
        """利用可能なフォントを検索"""
        import subprocess

        for font_name in font_candidates:
            try:
                # fc-listでフォントの存在を確認
                result = subprocess.run(
                    ["fc-list", f":family={font_name}"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    return font_name
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                logger.debug(f"Font search failed for {font_name}: {e}")
                continue

        # フォールバック: デフォルト
        logger.warning("No Japanese font found, using default font")
        return "Arial"

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
            file_size = os.path.getsize(video_path)
            info = {
                "file_size_mb": file_size / (1024 * 1024),
                "file_path": video_path,
                "format": self.output_format,
                "duration": float(video_stream.get("duration", 0)),
                "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}",
                "video_codec": video_stream.get("codec_name"),
            }
            return info
        except Exception as e:
            logger.warning(f"Failed to get video info: {e}")
            return {"file_size_mb": 0, "error": str(e)}

    def _generate_fallback_video(self, audio_path: str, title: str) -> str:
        try:
            logger.warning("Generating fallback video...")
            duration = self._get_audio_duration(audio_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"fallback_video_{timestamp}.{self.output_format}"

            stream = ffmpeg.input(f"color=c=0x193d5a:size=1920x1080:duration={duration}", f="lavfi")
            audio_stream = ffmpeg.input(audio_path)

            stream = ffmpeg.output(
                stream, audio_stream, output_path, preset="fast", crf=28, **self._get_quality_settings()
            ).overwrite_output()

            ffmpeg.run(stream, quiet=True)
            logger.info(f"Fallback video generated: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Fallback video generation error: {e}")
            return None


# グローバルインスタンス
video_generator = VideoGenerator()


def generate_video(
    audio_path: str, subtitle_path: str, background_image: str = None, title: str = "Economic News"
) -> str:
    return video_generator.generate_video(audio_path, subtitle_path, background_image, title)


if __name__ == "__main__":
    print("Testing video generation...")
    if os.path.exists("output_audio.wav") and os.path.exists("subtitles.srt"):
        try:
            video_path = generate_video("output_audio.wav", "subtitles.srt")
            if video_path:
                print(f"Video created: {video_path}")
                info = video_generator._get_video_info(video_path)
                print(f"Video info: {info}")
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Test files (output_audio.wav, subtitles.srt) not found, skipping test.")
