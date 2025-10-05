"""動画生成モジュール

音声ファイル、字幕ファイル、背景画像を組み合わせて最終的な動画を生成します。
FFmpegを使用して高品質な動画出力を実現します。
背景テーマのA/Bテストと継続的改善をサポートします。
ストックビデオAPIを使用した無料のプロフェッショナルB-roll映像にも対応。
"""

import logging
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import ffmpeg
from pydub import AudioSegment

from app.config.paths import ProjectPaths
from app.config.settings import settings
from app.services.file_archival import FileArchivalManager
from app.utils import FileUtils
from app.services.media.ffmpeg_support import ensure_ffmpeg_tooling

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
        self.motion_fps = 30

        # Initialize file archival manager
        self.archival_manager = FileArchivalManager()
        self.ffmpeg_path = ensure_ffmpeg_tooling(settings.ffmpeg_path)

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
                        audio_path, subtitle_path, audio_duration, script_content, news_items, output_path
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

            motion_stream = self._build_motion_background_stream(bg_image_path, audio_duration)
            subtitle_style = self._build_subtitle_style()
            sanitized_subtitle_path = self._normalize_subtitle_path(subtitle_path)

            video_stream = motion_stream.filter(
                "subtitles",
                sanitized_subtitle_path,
                force_style=subtitle_style,
            )

            audio_stream = ffmpeg.input(audio_path)

            output = ffmpeg.output(
                video_stream,
                audio_stream,
                output_path,
                shortest=None,
                **self._get_quality_settings(),
            ).overwrite_output()

            ffmpeg.run(output, quiet=True)

            video_info = self._get_video_info(output_path)
            logger.info(f"Video generated successfully: {output_path}")
            logger.info(f"Video info: {video_info}")
            return output_path

        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            self.last_generation_method = "fallback"
            return self._generate_fallback_video(audio_path, subtitle_path, title)
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

            from PIL import Image, ImageDraw

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
                    next_color = (
                        gradient_colors[color_idx + 1]
                        if color_idx + 1 < len(gradient_colors)
                        else gradient_colors[color_idx]
                    )
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
                pos = circle["pos"]
                color = tuple(circle["color"])
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
                    overlay_draw.line(
                        [(i, 0), (i + 600, height * 0.6)], fill=(255, 255, 255, theme.grid_opacity + 1), width=2
                    )

            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(image)

            # ロボットアイコンを追加（テーマ設定に応じた位置）
            if theme.robot_icon_enabled:
                robot_icon_path = str(ProjectPaths.DEFAULT_ROBOT_ICON)
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
                            icon_x, icon_y = (
                                width - theme.robot_icon_size[0] - margin,
                                height - theme.robot_icon_size[1] - margin,
                            )
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

            temp_path = FileUtils.get_temp_file(prefix="bg_", suffix=".png")
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
            temp_path = FileUtils.get_temp_file(prefix="bg_", suffix=".png")
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
        quality_settings.update(
            {"c:a": "aac", "b:a": "128k", "ar": "44100", "pix_fmt": "yuv420p", "movflags": "+faststart"}
        )
        return quality_settings

    def _normalize_subtitle_path(self, subtitle_path: str) -> str:
        """Sanitize subtitle path for ffmpeg filter usage."""
        if os.name == "nt":
            return subtitle_path.replace("\\", "\\\\").replace(":", "\\:")
        return subtitle_path

    def _build_subtitle_style(self) -> str:
        """Return force_style string for subtitles filter."""
        japanese_fonts = [
            "Noto Sans CJK JP Bold",
            "Yu Gothic Bold",
            "Hiragino Sans W6",
            "IPAGothic",
            "Meiryo Bold",
            "MS Gothic",
        ]

        font_name = self._find_available_font(japanese_fonts)
        subtitle_margin_v = 50
        subtitle_margin_h = 100

        style = (
            f"FontName={font_name},"
            f"FontSize={settings.subtitle_font_size},"
            f"PrimaryColour=&H00FFFFFF,"
            f"OutlineColour=&H00000000,"
            f"BackColour=&HE0000000,"
            f"BorderStyle=4,"
            f"Outline={settings.subtitle_outline_width + 1},"
            f"Shadow=3,"
            f"Alignment=2,"
            f"MarginV={subtitle_margin_v},"
            f"MarginL={subtitle_margin_h},"
            f"MarginR={subtitle_margin_h},"
            f"Bold=1,"
            f"Spacing=1,"
            f"ScaleX=100,"
            f"ScaleY=100"
        )

        style_str = "".join(style)
        logger.info(
            "Using subtitle font %s with margins (V:%spx, H:%spx)",
            font_name,
            subtitle_margin_v,
            subtitle_margin_h,
        )
        return style_str

    def _build_subtitle_filter(self, subtitle_path: str) -> str:
        """Legacy helper that returns full subtitles filter string."""
        try:
            normalized = self._normalize_subtitle_path(subtitle_path)
            style = self._build_subtitle_style()
            return f"subtitles={normalized}:force_style='{style}'"
        except Exception as e:
            logger.warning(f"Failed to build subtitle filter: {e}")
            return f"subtitles={self._normalize_subtitle_path(subtitle_path)}"

    def _build_motion_background_stream(self, bg_image_path: str, duration: float):
        """Create subtle motion video stream from a static background."""
        width = settings.video.resolution.width
        height = settings.video.resolution.height
        fps = self.motion_fps

        frames = max(int(math.ceil(duration * fps)) + fps // 2, fps)
        scale_factor = 1.18
        scaled_width = int(width * scale_factor)
        scaled_height = int(height * scale_factor)

        stream = ffmpeg.input(bg_image_path, loop=1, t=duration + 2)
        stream = stream.filter("scale", scaled_width, scaled_height)

        pan_x_margin = max(2, (scaled_width - width) // 2)
        pan_y_margin = max(2, (scaled_height - height) // 2)
        pan_x_amp = max(2, min(pan_x_margin - 1, pan_x_margin // 2))
        pan_y_amp = max(2, min(pan_y_margin - 1, pan_y_margin // 2))

        x_expr = f"iw/2-(iw/zoom/2)+sin(on/{fps * 4})*{pan_x_amp}"
        y_expr = f"ih/2-(ih/zoom/2)+cos(on/{fps * 5})*{pan_y_amp}"

        stream = stream.filter(
            "zoompan",
            z="if(eq(on,0),1.0,min(1.12,zoom+0.00035))",
            s=f"{width}x{height}",
            fps=fps,
            d=frames,
            x=x_expr,
            y=y_expr,
        )
        stream = stream.filter("eq", saturation=1.05, contrast=1.02, brightness=0.01)
        stream = stream.filter("setsar", "1")
        return stream

    def _find_available_font(self, font_candidates: list) -> str:
        """利用可能なフォントを検索"""
        import subprocess

        for font_name in font_candidates:
            try:
                # fc-listでフォントの存在を確認
                result = subprocess.run(["fc-list", f":family={font_name}"], capture_output=True, text=True, timeout=2)
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
            from .services.media import BRollGenerator, StockFootageManager, VisualMatcher

            self._stock_manager = StockFootageManager(
                pexels_api_key=settings.pexels_api_key,
                pixabay_api_key=settings.pixabay_api_key,
            )
            self._visual_matcher = VisualMatcher()
            self._broll_generator = BRollGenerator(ffmpeg_path=self.ffmpeg_path)

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
            subtitle_style = self._build_subtitle_style()
            sanitized_subtitle_path = self._normalize_subtitle_path(subtitle_path)

            video_with_subs = video_stream.filter(
                "subtitles",
                sanitized_subtitle_path,
                force_style=subtitle_style,
            )

            # Combine video + audio
            output = ffmpeg.output(
                video_with_subs,
                audio_stream,
                output_path,
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
        try:
            return self._build_subtitle_style()
        except Exception as e:
            logger.warning(f"Failed to retrieve subtitle style: {e}")
            return ""

    def _generate_fallback_video(self, audio_path: str, subtitle_path: str, title: str) -> str:
        try:
            logger.warning("Generating fallback video...")
            duration = self._get_audio_duration(audio_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"fallback_video_{timestamp}.{self.output_format}"

            video_stream = ffmpeg.input(f"color=c=0x193d5a:size=1920x1080:duration={duration}", f="lavfi")

            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    sanitized_subtitle_path = self._normalize_subtitle_path(subtitle_path)
                    subtitle_style = self._build_subtitle_style()
                    video_stream = video_stream.filter(
                        "subtitles",
                        sanitized_subtitle_path,
                        force_style=subtitle_style,
                    )
                except Exception as subtitle_error:
                    logger.warning(
                        "Failed to render subtitles in fallback video %s: %s",
                        subtitle_path,
                        subtitle_error,
                    )
            else:
                logger.warning("Subtitle file missing for fallback video: %s", subtitle_path)

            audio_stream = ffmpeg.input(audio_path)

            quality_settings = self._get_quality_settings()
            stream = ffmpeg.output(video_stream, audio_stream, output_path, **quality_settings).overwrite_output()

            ffmpeg.run(stream, quiet=True)
            logger.info(f"Fallback video generated: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Fallback video generation error: {e}")
            return None


# グローバルインスタンス（後方互換性のため保持）
# Deprecated: Use container.video_generator instead
def _get_video_generator() -> VideoGenerator:
    """Get video generator from container (backward compatibility)."""
    from app.container import get_container

    return get_container().video_generator


# Legacy global variable (backward compatibility)
class _VideoGeneratorProxy:
    """Proxy object to maintain backward compatibility."""

    def __getattr__(self, name):
        return getattr(_get_video_generator(), name)


video_generator = _VideoGeneratorProxy()


def generate_video(
    audio_path: str,
    subtitle_path: str,
    background_image: str = None,
    title: str = "Economic News",
    script_content: str = "",
    **kwargs,
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
    return _get_video_generator().generate_video(
        audio_path, subtitle_path, background_image, title, script_content=script_content, **kwargs
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
