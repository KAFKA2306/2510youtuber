"""動画生成モジュール

音声ファイル、字幕ファイル、背景画像を組み合わせて最終的な動画を生成します。
FFmpegを使用して高品質な動画出力を実現します。
背景テーマのA/Bテストと継続的改善をサポートします。
ストックビデオAPIを使用した無料のプロフェッショナルB-roll映像にも対応。
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import ffmpeg
from pydub import AudioSegment

from app.config.settings import settings
from .background_theme import BackgroundTheme, get_theme_manager

logger = logging.getLogger(__name__)


class VideoGenerator:
    """動画生成クラス"""

    def __init__(self):
        self.video_quality = settings.video.quality_preset
        self.output_format = "mp4"
        self.theme_manager = get_theme_manager()
        self.current_theme: Optional[BackgroundTheme] = None

        # Initialize stock footage services (lazy loading)
        self._stock_manager = None
        self._visual_matcher = None
        self._broll_generator = None
        self.last_used_stock_footage = False
        self.last_generation_method = "static"

        logger.info("Video generator initialized with theme management and stock footage support")

    def generate_video(
        self,
        audio_path: str,
        subtitle_path: str,
        background_image: str = None,
        title: str = "Economic News Analysis",
        output_path: str = None,
        theme_name: str = None,
        enable_ab_test: bool = True,
        script_content: str = "",
        news_items: List[Dict] = None,
        use_stock_footage: bool = None,
    ) -> str:
        """動画を生成

        Args:
            audio_path: 音声ファイルパス
            subtitle_path: 字幕ファイルパス
            background_image: カスタム背景画像（Noneの場合はテーマベース生成）
            title: タイトルテキスト
            output_path: 出力ファイルパス
            theme_name: 使用するテーマ名（Noneの場合はA/Bテスト選択）
            enable_ab_test: A/Bテストを有効にするか
            script_content: スクリプト内容（キーワード抽出用）
            news_items: ニュースアイテムリスト（キーワード抽出用）
            use_stock_footage: ストック映像を使用するか（Noneの場合は設定から取得）
        """
        try:
            self._validate_input_files(audio_path, subtitle_path, background_image)
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"video_{timestamp}.{self.output_format}"

            audio_duration = self._get_audio_duration(audio_path)

            # Determine if using stock footage
            if use_stock_footage is None:
                use_stock_footage = settings.enable_stock_footage

            # TRY 1: Stock Footage B-roll (if enabled and configured)
            if use_stock_footage and self._can_use_stock_footage():
                try:
                    logger.info("Attempting to generate video with stock footage B-roll...")
                    video_path = self._generate_with_stock_footage(
                        audio_path, subtitle_path, audio_duration,
                        script_content, news_items, output_path
                    )
                    if video_path:
                        self.last_used_stock_footage = True
                        self.last_generation_method = "stock_footage"
                        logger.info(f"✓ Generated video with stock footage: {video_path}")
                        return video_path
                except Exception as e:
                    logger.warning(f"Stock footage generation failed: {e}, falling back to static")

            # TRY 2: Enhanced Static Background (theme-based, A/B tested)
            logger.info("Generating video with static background...")
            self.last_used_stock_footage = False
            self.last_generation_method = "static"

            # テーマ選択（A/Bテストまたは指定）
            if theme_name:
                self.current_theme = self.theme_manager.get_theme(theme_name)
            elif enable_ab_test:
                self.current_theme = self.theme_manager.select_theme_for_ab_test()
            else:
                self.current_theme = self.theme_manager.get_best_performing_theme()

            if self.current_theme:
                logger.info(f"Using background theme: {self.current_theme.name}")
                self.theme_manager.record_usage(self.current_theme.name)

            bg_image_path = self._prepare_background_image(background_image, title)

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
            self.last_generation_method = "fallback"
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
        """プロ品質の動的背景を作成（テーマベース）with robot icon"""
        try:
            import textwrap
            from PIL import Image, ImageDraw, ImageFont, ImageFilter

            width, height = 1920, 1080

            # テーマが設定されていない場合はデフォルト値を使用
            if not self.current_theme:
                logger.warning("No theme selected, using default")
                self.current_theme = self.theme_manager.get_theme("professional_blue")

            theme = self.current_theme
            logger.info(f"Creating background with theme: {theme.name}")

            # 基本背景色（グラデーション開始色）
            base_color = theme.gradient_colors[0] if theme.gradient_colors else (10, 20, 35)
            image = Image.new("RGB", (width, height), color=base_color)
            draw = ImageDraw.Draw(image)

            # テーマベースのグラデーション生成
            gradient_stops = theme.gradient_stops
            gradient_colors = theme.gradient_colors

            for y_pos in range(height):
                ratio = y_pos / height

                # グラデーションの段階を決定
                color_idx = 0
                for i, stop in enumerate(gradient_stops):
                    if ratio <= stop:
                        color_idx = i
                        break

                # 色を補間
                if color_idx == 0:
                    prev_stop = 0.0
                    prev_color = gradient_colors[0]
                    next_stop = gradient_stops[0]
                    next_color = gradient_colors[1]
                elif color_idx < len(gradient_stops):
                    prev_stop = gradient_stops[color_idx - 1]
                    prev_color = gradient_colors[color_idx]
                    next_stop = gradient_stops[color_idx]
                    next_color = gradient_colors[color_idx + 1] if color_idx + 1 < len(gradient_colors) else gradient_colors[color_idx]
                else:
                    prev_stop = gradient_stops[-1]
                    prev_color = gradient_colors[-1]
                    next_stop = 1.0
                    next_color = gradient_colors[-1]

                # 色の線形補間
                local_ratio = (ratio - prev_stop) / (next_stop - prev_stop) if next_stop != prev_stop else 0
                r = int(prev_color[0] + (next_color[0] - prev_color[0]) * local_ratio)
                g = int(prev_color[1] + (next_color[1] - prev_color[1]) * local_ratio)
                b = int(prev_color[2] + (next_color[2] - prev_color[2]) * local_ratio)

                draw.line([(0, y_pos), (width, y_pos)], fill=(r, g, b))

            # 装飾的なオーバーレイ（テーマベース）
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # アクセント円形パターン（テーマから取得）
            for circle in theme.accent_circles:
                pos = circle['pos']
                color = tuple(circle['color'])
                overlay_draw.ellipse(pos, fill=color)

            # グリッドライン（テーマ設定に応じて）
            if theme.grid_enabled:
                grid_limit_y = int(height * theme.subtitle_zone_height_ratio)
                for i in range(0, width, theme.grid_spacing):
                    overlay_draw.line([(i, 0), (i, grid_limit_y)], fill=(255, 255, 255, theme.grid_opacity), width=1)
                for i in range(0, grid_limit_y, theme.grid_spacing):
                    overlay_draw.line([(0, i), (width, i)], fill=(255, 255, 255, theme.grid_opacity), width=1)

            # 対角線アクセント（テーマ設定に応じて）
            if theme.diagonal_lines:
                for i in range(-500, width + 500, 300):
                    overlay_draw.line([(i, 0), (i + 600, height * 0.6)], fill=(255, 255, 255, theme.grid_opacity + 1), width=2)

            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(image)

            # ロボットアイコンを追加（テーマ設定に応じた位置）
            if theme.robot_icon_enabled:
                robot_icon_path = "/home/kafka/projects/youtuber/assets/icon/ChatGPT Image 2025年10月2日 19_53_38.png"
                if os.path.exists(robot_icon_path):
                    try:
                        robot_img = Image.open(robot_icon_path).convert("RGBA")

                        # テーマベースのサイズとopacity
                        robot_img = robot_img.resize(theme.robot_icon_size, Image.Resampling.LANCZOS)
                        robot_img.putalpha(int(255 * theme.robot_icon_opacity))

                        # テーマベースの位置決定
                        margin = 60
                        if theme.robot_icon_position == "top-left":
                            icon_x, icon_y = margin, margin
                        elif theme.robot_icon_position == "top-right":
                            icon_x, icon_y = width - theme.robot_icon_size[0] - margin, margin
                        elif theme.robot_icon_position == "bottom-left":
                            icon_x, icon_y = margin, height - theme.robot_icon_size[1] - margin
                        elif theme.robot_icon_position == "bottom-right":
                            icon_x, icon_y = width - theme.robot_icon_size[0] - margin, height - theme.robot_icon_size[1] - margin
                        else:
                            icon_x, icon_y = margin, margin

                        image.paste(robot_img, (icon_x, icon_y), robot_img)
                        logger.info(f"Robot icon added at {theme.robot_icon_position}")
                    except Exception as e:
                        logger.warning(f"Could not add robot icon: {e}")

            # タイトルテキスト（テーマベース設定）
            font = self._get_japanese_font_for_background(theme.title_font_size)
            if font:
                # タイトルを短く整形
                wrapped_title = textwrap.fill(title, width=22)

                # テキストのバウンディングボックス
                bbox = draw.textbbox((0, 0), wrapped_title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (width - text_width) // 2
                y = theme.title_position_y

                # 多層シャドウ（テーマ設定のレイヤー数）
                shadow_offsets = list(range(theme.title_shadow_layers * 2, 0, -2))
                for offset in shadow_offsets:
                    alpha_val = max(50, 255 - (offset * 25))
                    draw.text((x + offset, y + offset), wrapped_title, font=font, fill=(0, 0, 0, alpha_val))

                # グロー効果（テーマ設定に応じて）
                if theme.title_glow_enabled:
                    glow_color = (100, 200, 255, 80)
                    for offset_x, offset_y in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                        draw.text((x + offset_x, y + offset_y), wrapped_title, font=font, fill=glow_color)

                # メインテキスト（白、太字感）
                draw.text((x, y), wrapped_title, font=font, fill=(255, 255, 255))

                # アクセントライン（テーマ設定に応じて）
                if theme.accent_lines_enabled:
                    line_y = y + text_height + 25
                    draw.rectangle([x - 20, line_y, x + text_width + 20, line_y + 6], fill=(255, 215, 0))
                    draw.rectangle([x - 15, line_y + 10, x + text_width + 15, line_y + 13], fill=(0, 180, 255))

            # 字幕エリアの明確な区切り（テーマ設定に応じて）
            if theme.subtitle_zone_separator:
                subtitle_zone_y = int(height * theme.subtitle_zone_height_ratio)
                draw.rectangle([0, subtitle_zone_y - 3, width, subtitle_zone_y], fill=(0, 100, 180, 100))

            temp_path = tempfile.mktemp(suffix=".png")
            image.save(temp_path, "PNG", quality=95)
            logger.info(f"Created professional background with robot icon and dynamic elements: {temp_path}")
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
        presets = settings.video_quality_presets
        quality_settings = presets.get(self.video_quality, presets["medium"])
        quality_settings.update({"c:a": "aac", "b:a": "128k", "ar": "44100", "pix_fmt": "yuv420p", "movflags": "+faststart"})
        return quality_settings

    def _build_subtitle_filter(self, subtitle_path: str) -> str:
        """字幕フィルタを構築（プロYouTuber品質、見切れ防止、最下部配置）"""
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

            # 改善: 字幕を下部20%エリア（864px以降）に確実に配置
            # MarginV を大幅に増やして見切れを完全防止
            subtitle_margin_v = 50  # 下部から50pxマージン（1080の下部20%内）
            subtitle_margin_h = 100  # 左右100pxマージン（横の見切れ防止）

            # プロYouTuber品質の字幕スタイル（最強視認性 + 見切れ防止）
            subtitle_style = (
                f"subtitles={subtitle_path}:force_style='FontName={font_name},"
                f"FontSize={settings.subtitle_font_size},"  # config.py から取得（デフォルト48）
                f"PrimaryColour=&H00FFFFFF,"  # 白文字（視認性最強）
                f"OutlineColour=&H00000000,"  # 黒アウトライン
                f"BackColour=&HE0000000,"  # より濃い半透明黒背景（E0=88%不透明）
                f"BorderStyle=4,"  # 4=ボックス背景+アウトライン（最強視認性）
                f"Outline={settings.subtitle_outline_width + 1},"  # アウトライン幅を1px増加
                f"Shadow=3,"  # より強い影（立体感）
                f"Alignment=2,"  # 下部中央
                f"MarginV={subtitle_margin_v},"  # 下部マージン（見切れ防止）
                f"MarginL={subtitle_margin_h},"  # 左マージン
                f"MarginR={subtitle_margin_h},"  # 右マージン
                f"Bold=1,"  # 太字
                f"Spacing=1,"  # 文字間隔を少し開ける（読みやすさ向上）
                f"ScaleX=100,"  # 横スケール
                f"ScaleY=100'"  # 縦スケール
            )

            logger.info(f"Using subtitle font: {font_name}, MarginV: {subtitle_margin_v}px (bottom 20% zone)")
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

    def _can_use_stock_footage(self) -> bool:
        """Check if stock footage generation is available."""
        return bool(settings.pexels_api_key or settings.pixabay_api_key)

    def _ensure_stock_services(self):
        """Lazy load stock footage services."""
        if self._stock_manager is None:
            from .services.media import StockFootageManager, VisualMatcher, BRollGenerator

            self._stock_manager = StockFootageManager(
                pexels_api_key=settings.pexels_api_key,
                pixabay_api_key=settings.pixabay_api_key,
            )
            self._visual_matcher = VisualMatcher()
            self._broll_generator = BRollGenerator(ffmpeg_path=settings.ffmpeg_path)

    def _generate_with_stock_footage(
        self,
        audio_path: str,
        subtitle_path: str,
        audio_duration: float,
        script_content: str,
        news_items: List[Dict],
        output_path: str,
    ) -> Optional[str]:
        """Generate video using stock footage B-roll.

        Args:
            audio_path: Audio file path
            subtitle_path: Subtitle file path
            audio_duration: Duration of audio
            script_content: Script text for keyword extraction
            news_items: News items for context
            output_path: Final video output path

        Returns:
            Output path if successful, None otherwise
        """
        self._ensure_stock_services()

        # Extract visual keywords from script
        keywords = self._visual_matcher.extract_keywords(
            script_content=script_content,
            news_items=news_items or [],
            max_keywords=settings.stock_footage_clips_per_video,
        )

        if not keywords:
            logger.warning("No keywords extracted for stock footage search")
            return None

        logger.info(f"Stock footage keywords: {keywords}")

        # Search for stock footage
        footage_results = self._stock_manager.search_footage(
            keywords=keywords,
            duration_target=audio_duration,
            max_clips=settings.stock_footage_clips_per_video,
        )

        if not footage_results:
            logger.warning("No stock footage found")
            return None

        logger.info(f"Found {len(footage_results)} stock clips")

        # Download clips
        clip_paths = self._stock_manager.download_clips(footage_results)

        if not clip_paths:
            logger.warning("Failed to download stock clips")
            return None

        logger.info(f"Downloaded {len(clip_paths)} clips successfully")

        # Generate B-roll sequence
        broll_path = self._broll_generator.create_broll_sequence(
            clip_paths=clip_paths,
            target_duration=audio_duration,
            transition_duration=1.0,
            enable_effects=True,
        )

        if not broll_path or not os.path.exists(broll_path):
            logger.warning("Failed to create B-roll sequence")
            return None

        logger.info(f"Created B-roll sequence: {broll_path}")

        # Combine B-roll + audio + subtitles
        try:
            video_stream = ffmpeg.input(broll_path)
            audio_stream = ffmpeg.input(audio_path)

            # Apply subtitle overlay
            video_with_subs = video_stream.filter(
                'subtitles',
                subtitle_path,
                force_style=self._get_subtitle_style_string(),
            )

            # Combine video + audio
            output = ffmpeg.output(
                video_with_subs,
                audio_stream,
                output_path,
                vcodec='libx264',
                acodec='aac',
                **self._get_quality_settings(),
            ).overwrite_output()

            ffmpeg.run(output, quiet=True)

            if os.path.exists(output_path):
                video_info = self._get_video_info(output_path)
                logger.info(f"Stock footage video complete: {video_info}")
                return output_path

        except Exception as e:
            logger.error(f"Failed to combine B-roll with audio: {e}")

        return None

    def _get_subtitle_style_string(self) -> str:
        """Get subtitle style as string for ffmpeg filter."""
        # Reuse existing subtitle filter logic
        filter_str = self._build_subtitle_filter("dummy.srt")
        if filter_str and "force_style='" in filter_str:
            # Extract style string
            start = filter_str.find("force_style='") + len("force_style='")
            end = filter_str.find("'", start)
            return filter_str[start:end]
        return ""

    def _generate_fallback_video(self, audio_path: str, title: str) -> str:
        try:
            logger.warning("Generating fallback video...")
            duration = self._get_audio_duration(audio_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"fallback_video_{timestamp}.{self.output_format}"

            stream = ffmpeg.input(f"color=c=0x193d5a:size=1920x1080:duration={duration}", f="lavfi")
            audio_stream = ffmpeg.input(audio_path)

            quality_settings = self._get_quality_settings()
            stream = ffmpeg.output(
                stream, audio_stream, output_path, crf=28, **quality_settings
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
    audio_path: str,
    subtitle_path: str,
    background_image: str = None,
    title: str = "Economic News",
    script_content: str = "",
    **kwargs
) -> str:
    """Generate video from audio and subtitle files

    Args:
        audio_path: Path to audio file
        subtitle_path: Path to subtitle file
        background_image: Optional background image path
        title: Video title
        script_content: Optional script content for B-roll
        **kwargs: Additional arguments passed to VideoGenerator

    Returns:
        Path to generated video file
    """
    return video_generator.generate_video(
        audio_path,
        subtitle_path,
        background_image,
        title,
        script_content=script_content,
        **kwargs
    )


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
