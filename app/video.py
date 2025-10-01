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
                except Exception:
                    pass

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
        """デフォルト背景を作成（日本語対応）"""
        try:
            import textwrap

            from PIL import Image, ImageDraw, ImageFont

            width, height = 1920, 1080
            image = Image.new("RGB", (width, height), color=(25, 35, 45))
            draw = ImageDraw.Draw(image)

            # 日本語フォントを取得
            font_size = 72
            font = self._get_japanese_font_for_background(font_size)

            if font:
                # 日本語の場合、適切な文字数で改行
                wrapped_title = textwrap.fill(title, width=15)  # 20 -> 15 (日本語対応)
                bbox = draw.textbbox((0, 0), wrapped_title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (width - text_width) // 2
                y = (height - text_height) // 2

                # 影を描画（視認性向上）
                shadow_offset = 4
                draw.text((x + shadow_offset, y + shadow_offset), wrapped_title, font=font, fill=(0, 0, 0))

                # メインテキスト
                draw.text((x, y), wrapped_title, font=font, fill=(255, 255, 255))

            # グラデーション背景
            for y_pos in range(height):
                alpha = int(255 * (1 - y_pos / height) * 0.3)
                overlay = Image.new("RGBA", (width, 1), (70, 130, 180, alpha))
                image.paste(overlay, (0, y_pos), overlay)

            temp_path = tempfile.mktemp(suffix=".png")
            image.save(temp_path, "PNG")
            logger.debug(f"Created default background with Japanese font: {temp_path}")
            return temp_path
        except Exception as e:
            logger.warning(f"Failed to create default background: {e}")
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
        except Exception:
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
        quality_presets = {
            "low": {"preset": "fast", "crf": 28},
            "medium": {"preset": "medium", "crf": 23},
            "high": {"preset": "slow", "crf": 18},
            "ultra": {"preset": "veryslow", "crf": 15},
        }
        settings = quality_presets.get(self.video_quality, quality_presets["medium"])
        settings.update({"c:a": "aac", "b:a": "128k", "ar": "44100", "pix_fmt": "yuv420p", "movflags": "+faststart"})
        return settings

    def _build_subtitle_filter(self, subtitle_path: str) -> str:
        """字幕フィルタを構築（日本語対応、視認性向上）"""
        try:
            # On Windows, paths must be escaped.
            if os.name == "nt":
                subtitle_path = subtitle_path.replace("\\", "\\\\").replace(":", "\\:")

            # 日本語フォントを優先的に使用
            japanese_fonts = [
                "IPAGothic",  # IPA ゴシック (Linux)
                "IPA Gothic",
                "Noto Sans CJK JP",  # Noto Sans 日本語
                "Meiryo",  # Windows
                "Hiragino Sans",  # macOS
                "Yu Gothic",  # Windows/Mac
                "MS Gothic",  # Windows
            ]

            # 利用可能な日本語フォントを検索
            font_name = self._find_available_font(japanese_fonts)

            subtitle_style = (
                f"subtitles={subtitle_path}:force_style='FontName={font_name},"
                f"FontSize=32,"  # 視認性向上: 24 -> 32
                f"PrimaryColour=&H00FFFFFF,"  # 白
                f"OutlineColour=&H00000000,"  # 黒アウトライン
                f"BackColour=&H80000000,"  # 半透明黒背景
                f"BorderStyle=3,"  # ボックス背景
                f"Outline=3,"  # 太いアウトライン
                f"Shadow=1,"  # 影を追加
                f"Alignment=2,"  # 下部中央
                f"MarginV=60,"  # 下部マージン
                f"Bold=1'"  # 太字
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
            except Exception:
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
